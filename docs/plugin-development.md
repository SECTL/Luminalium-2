# Luminalium 2 插件开发指南

写给想给 Luminalium 2 写插件的人。不需要读过任何内部计划，只需要这份文档、
两个活的范例插件（`app/plugins/_demo/` 与 `app/plugins/_demo_dep/`），再加上
仓库根目录 `AGENTS.md` 里的通用约定（界面文案中文、QML 头注释习惯、窗口不
加 `Qt.FramelessWindowHint` 等，本文不再重复，直接去读它）。

插件能做什么：往快捷面板加磁贴、往放映控制条加工具和动作、往设置窗口加
整页、注册自己的设置键、往主界面编辑器加分组、开自己的窗口，以及通过一条
进程内消息总线和其他插件对话。插件不能做什么：没有 unregister、没有热重载，
一切贡献在启动时一次注册完就冻结（为什么这么定，见下文「两阶段加载」）。

---

## 插件形态

一个插件就是两个目录约定加一个入口文件：

```
app/plugins/<id>/plugin.py     # Python 入口：META + DEFAULTS + register(ctx)
ui/plugins/<id>/               # 这个插件的全部 QML（设置页、窗口等）
```

`<id>` 同时是目录名、`META["id"]`、动作动词前缀、设置键前缀、配置路径
`plugins.<id>.*` 里的那段，全仓库用同一个 id 把五处命名空间串起来，所以
起名字时就当它在五张表里都要唯一。

`plugin.py` 必须暴露三样东西（`app/plugins/loader.py` 头注释里的模块约定）：

```python
META = {"id": "my_tool"}                       # 必填，id 与目录名一致
DEFAULTS = {"volume": 50, "enabled": True}     # 可选，见「配置约定」一节

def register(ctx) -> None:                     # 必填，加载期回调
    ctx.add_shortcut(...)
```

发现机制刻意不做目录扫描，分两类：

* **正式插件**：把 id 加进 `app/plugins/__init__.py` 里的 `PLUGINS` 列表。
  显式枚举让启用集合一眼可查，避免「丢个文件夹进去就默默生效」。表内重复
  id 会在启动时直接硬失败（两个插件抢同一个命名空间属于装配错误，不能
  静默放过）。
* **调试插件**：目录名以单下划线 `_` 开头（如 `_demo`），**永不进 PLUGINS**，
  只在配置键 `app.debug = true` 时追加加载。`app.debug` 没有界面开关，
  手改 `config/config.json` 写 `"app": {"debug": true}` 后重启生效。
  调试插件的 `DEFAULTS` 也不注入正式配置默认层，关调试时它连默认值都
  不存在。写新插件时建议先用 `_` 前缀目录调试，定型后再转正。

---

## META 字段全表

| 字段 | 必填 | 类型 | 用途 |
|---|---|---|---|
| `id` | 是 | str | 唯一标识，必须与目录名一致，不一致启动时按导入失败跳过 |
| `name` | 否 | str | 设置窗口「插件」管理页的显示名；不填回落成 id（管理页总得有个能给人看的名字） |
| `version` | 否 | str | 管理页标题栏显示为 `名称  v<version>`；不填不显示 |
| `depends` | 否 | list[str] | 依赖的其他插件 id，详见「依赖与故障语义」 |

管理页的数据来自 `loader.loaded_plugins()` 的加载清单，合成逻辑在
`app/bridge.py` 的 `_get_plugin_items`（`title = META.name or id`）。

---

## 两阶段加载：你的代码什么时候跑

理解这个时序比背 API 更重要，因为好几个「为什么不行」都是时序答案：

```
启动
 │
 ├─ 阶段一 collect_defaults()        ← Config() 构造之前
 │    遍历 PLUGINS，读启用插件的 DEFAULTS 聚合进注册表
 │    ⚠️ 此刻没有 Config：启用判定靠直接 json.load 用户配置文件
 │
 ├─ Config(extra_defaults=...)       ← 插件默认值在此注入默认层（唯一时机）
 │
 ├─ Backend / RinUI / WindowManager 装配，内建窗口 load_windows()
 │
 ├─ _register_builtin_verbs()        ← 内建动作动词进注册表
 │
 ├─ 阶段二 load_plugins(backend, windows)
 │    复核启用态 → 拓扑排序 → 逐插件调 register(ctx) → registry.freeze()
 │
 └─ _wire() 信号接线                  ← 此后注册表只读，消费端假设它是全量
```

为什么是两次而不是一次：Config 的默认值注入只在构造时发生一次，插件默认值
想进默认层（从而「可读但不落盘」）就必须赶在构造前聚合；而 `register(ctx)`
要用 Backend（注册设置键）和 WindowManager（注册窗口），只能等它们就绪。
鸡生蛋的点是启用状态本身存在配置里，阶段一没有 Config 可读，所以阶段一直接
读原始 JSON 文件，读不到一律按启用处理，阶段二拿到正式 Config 再复核一遍。

对你的直接影响：

* **禁用的插件两阶段都跳过**：默认值不注入、`plugin.py` 根本不会被 import。
* **`register(ctx)` 是唯一的贡献窗口**。`load_plugins` 末尾
  `registry.freeze()` 之后，任何 `add_*` 调用直接抛 `RuntimeError`。想在
  运行中「偷偷加个磁贴」没有这条路。
* 启用 / 禁用因此**重启生效**：设置「插件」页拨开关只写
  `plugins.<id>.enabled` 配置，下次启动 loader 按新值过滤。这不是偷懒，
  是注册表冻结加窗口只藏不销毁两个架构前提决定的，本进程内不存在
  反注册这条路。

---

## PluginContext：插件与宿主的唯一通道

`register(ctx)` 收到的 `ctx` 是 `app/plugins/context.py` 的 `PluginContext`
实例。插件**不直接 import** registry / bridge / windows，一切声明经 ctx 转手，
因为 ctx 在这里做越权校验（动词前缀、设置键前缀、描述符形状），把「插件写
错了」变成注册期的明确异常，而不是运行期悬案。

ctx 上还有一个只读属性 `ctx.plugin_id`，就是本插件的 id。

### 1. add_shortcut：快捷面板磁贴

```python
ctx.add_shortcut(
    id: str,
    title: str,
    icon: str,
    action: str,
    icon_source: Optional[str] = None,
) -> None
```

注册一块磁贴，条目形状 `{id, title, icon, action, iconSource?}`，与
`config/default_config.json` 的 `quick_panel.shortcut_catalog` 逐键对齐，
消费端纯拼接、不做转换。读取侧合并规则（`bridge.py::_catalog`）：插件磁贴
排在内建之后，**id 与内建冲突时内建胜出**并记 warning，所以 id 起得独特点。

* `action` 约定写 `plugin:<本插件id>:<动作名>`，点击时经动作动词注册表
  路由到 `add_action_handler` 登记的处理器。
* `title` 要是已经翻译好的文案，插件自己 `app.i18n.tr(<id>, ...)` 处理好
  再传进来，桥接层原样透传（动态字符串喂不进 `qsTr`，见「翻译约定」）。
* `icon` 是 Fluent 图标名（如 `ic_fluent_beaker_20_regular`）；`icon_source`
  是可选的自定义图片资源名，与内建条目的 `iconSource` 键同义。

范例（`_demo/plugin.py`）：

```python
ctx.add_shortcut(
    "_demo_panel", "演示", "ic_fluent_beaker_20_regular", "plugin:_demo:open"
)
```

### 2. add_action_handler：动作动词处理器

```python
ctx.add_action_handler(
    verb_prefix: str,
    handler: Callable[[str], Any],
) -> None
```

注册一个动作动词前缀的处理器。分发规则（`application.py::_match_verb_handler`）：
动作串 `== 动词` 或以 `动词 + ":"` 开头即命中，**最长前缀优先**，处理器拿到
完整动作串自己解析后缀。

**命名空间契约**：`verb_prefix` 必须在 `plugin:<本插件id>` 命名空间内
（`plugin:<id>` 本身或 `plugin:<id>:...`），否则注册时直接 `ValueError`。
动词命名空间是全局的，不拦的话一个插件可以抢注 `open_settings` 或别的插件
的前缀，把别人的动作静默劫走。

**为什么注册时会剥掉尾冒号**：注册表存的是「不含分隔符的裸动词」。如果把
`plugin:<id>:` 原样存进去，匹配规则变成
`动作.startswith("plugin:<id>:" + ":")`，永远为假，插件的所有动作静默落空。
所以 `ctx.add_action_handler("plugin:_demo:", handler)` 是合法且推荐的写法，
ctx 会替你剥成 `plugin:_demo`。

`plugin:` 前缀动作的特权：它在「当前是否在放映」的门控**之前**路由
（`application.py::_on_action`），与 `tool:` / `pen_color:` 同级。也就是说
你的插件动作在非放映时也能从面板或控制条触发，且插件与 PowerPoint COM、
按键注入零接触。

范例（`_demo/plugin.py`）：

```python
def _on_action(action: str) -> None:
    if action == "plugin:_demo:open":
        _window_handle.show()
    elif action == "plugin:_demo:close":
        _window_handle.hide()

ctx.add_action_handler("plugin:_demo:", _on_action)
```

### 3. add_dock_tool / add_dock_action：放映控制条

```python
ctx.add_dock_tool(id: str, label: str, icon: str, tooltip: Optional[str] = None) -> None
ctx.add_dock_action(id: str, label: str, icon: str, tooltip: Optional[str] = None) -> None
```

条目形状都是 `{id, label, icon, tooltip?}`，对齐 `presentation.tools` /
`presentation.actions`，读取时与 config 列表拼接（插件追加在内建之后，
id 冲突内建胜出）。

**id 就是动作串**：控制条上点工具走 `Backend.selectTool(id)`、点动作走
`Backend.triggerAction(id)`，两者对 `plugin:` 前缀的 id 都会转进动作通道。
所以插件条目 id 直接写成 `plugin:<id>:<名字>`（`_demo` 就是这么干的：
`plugin:_demo:tool` / `plugin:_demo:ping`），点它就等于触发这个动作。

**状态别放 QML 侧**：`WindowManager.rebuild_docks` 会销毁并重建 dock 的
Item，dock 里任何 QML 侧持有的状态（开关态、计数）重建时都会蒸发。需要
跨重建存续的状态放插件自己的 Python 模块变量或设置键里。这是三条铁规
的第一条，写在 `context.py` 头注释里。

### 4. add_settings_page：设置窗口整页

```python
ctx.add_settings_page(
    id: str,
    title: str,
    page_qml: str,
    icon: str,
    position: Optional[int] = None,
) -> None
```

把一页并入设置窗口左侧导航。

* `page_qml` 是 `ui/plugins/<本插件id>/` 下的**相对文件名**（如
  `"DemoSettings.qml"`），传绝对路径或带 `..` 会在注册时 `ValueError`。
  ctx 会把它转成 `file:///` 绝对 URL 存进条目的 `page_url` 键，桥接层
  喂给 QML 时映射成导航条目要的 `page` 键，插件不用管这层键名转换。
* 页面 QML 根元素用 `Rin.FluentPage`（参照 `_demo` 的
  `ui/plugins/_demo/DemoSettings.qml`）。
* `title` 同样要是已翻译文案。
* `position` 是 RinUI `Position` 枚举的整数值，用来把条目钉到底部
  （内建的「关于 / 更新」就是这么钉的）；普通条目别传。

### 5. register_setting：扁平设置键

```python
ctx.register_setting(
    key: str,
    path: str,
    *,
    notify: Optional[str] = None,
    side_effect: Optional[Callable[..., Any]] = None,
) -> None
```

注册一个扁平设置键，之后 QML 侧就能用 `Backend.settings.<key>` 读、
`Backend.setSetting("<key>", 值)` 写，与内建设置项走同一条读写链路。

* `key` 必须 `plugins_<本插件id>_` 前缀（注意是下划线，如
  `plugins__demo_flag`，`_demo` 的 id 自带一个下划线所以看着像双写）。
  扁平键与内建键同住一张表，不加前缀拦截的话插件可以覆盖内建键的映射，
  这是越权，注册时 `ValueError` 硬拒绝。这个前缀也顺便避开了
  `presentation_` 前缀的整块配置变更广播规则。
* `path` 是配置里的点号路径，约定 `plugins.<id>.<名字>`，与 `DEFAULTS`
  里的相对键一一对应。
* `notify`：值变更时额外发的信号名字符串；不传则只发 `settingsChanged`。
* `side_effect`：可选回调 `(config, key, value)`，在改完内存、排好延迟
  落盘之后、发信号之前调用。

**Python 侧怎么感知 / 读取设置值**：`PluginContext` 刻意不提供公共的
Backend 访问器（插件与宿主的通道收束到这 8 个 API），所以没有「随时读
一个键」的通用入口。设计上插件应该是**变更驱动**的：在 `side_effect`
回调里接收新值并更新自己的内部状态，而不是需要时去查。`_demo` 夹具走
内部引用写键只是验收脚本的特权做法，真实插件不要学。

QML 侧绑定时有个历史坑：控件 `onToggled` 里改值会把 `checked` 上的 QML
绑定摘掉，需要用 `Qt.binding` 重装，完整写法照抄
`ui/plugins/_demo/DemoSettings.qml` 的开关（注释里写了为什么）。

### 6. add_editor_group：主界面编辑器分组

```python
ctx.add_editor_group(
    name: str,
    *,
    display_name: str,
    icon: str,
    dock_qml: Optional[str] = None,
    inspector_items: Any = (),
    traits: Any = None,
) -> None
```

注册一个编辑器分组，之后用户可以在主界面编辑器里把这个组拖进放映控制条
的任意角落。

* `inspector_items` 是右侧检查器的设置项描述符列表，编辑器 QML 按 `kind`
  分发渲染，插件因此**不需要碰编辑器 QML**。每项形状：

  ```
  {key, kind, title, description?, options?, visible_when_group?}
  ```

  - `key`：扁平设置键（必填），须先经 `register_setting` 登记；
  - `kind`：只支持 `"switch"` / `"combo"` / `"radio"`，与内建检查器的
    能力上限严格对齐，刻意不发明新控件类型；
  - `title`：设置项名称（必填）；
  - `options`：`combo` / `radio` 必填，`[{value, label}, ...]`；
  - `visible_when_group`：可选，仅当选中角的 groups 含该组名才显示，
    用于「我的组与某组同角共存时这项才露面」的跟随场景。

  校验在注册侧做（`windows.py::validate_inspector_items`）：缺 key、未知
  kind、combo/radio 缺 options、`visible_when_group` 指向没注册的组名，
  都会在 `register` 期直接 `ValueError` 炸出来，坏描述符不可能流进
  检查器渲染。

* `traits` 在注册表里**恒为 dict**（`{trait名: True, ...}`），因为 QML
  消费端按 `entry.traits[traitName] === true` 的字典语义读取。传 dict 原样
  拷贝；传名字列表（`["toolbar", ...]` 这种便捷写法）会展开成
  `{名字: True}`；不传是 `{}`。内建组用的 trait 有 `toolbar` / `pager` /
  `section_order` / `divider_before` / `orientation`，语义见
  `windows.py` 的 `_BUILTIN_DOCK_GROUPS` 注释。

* `dock_qml`：该组专属的 dock 渲染组件，UI_DIR 相对路径（如
  `plugins/<id>/MyDock.qml`）。解析规则：groups 中首个「有 dock_qml 且
  `traits.orientation` 与角落朝向匹配」的组胜出，都不匹配回落
  `PresentationDock.qml`。大多数组不需要它。

范例（`_demo/plugin.py`，含一条检查器开关）：

```python
ctx.add_editor_group(
    "_demo_group",
    display_name="演示组件",
    icon="ic_fluent_beaker_20_filled",
    inspector_items=[
        {"key": "plugins__demo_flag", "kind": "switch", "title": "演示开关"}
    ],
)
```

### 7. register_window：自管窗口

```python
handle = ctx.register_window(name: str, qml_path, **options) -> RegisteredWindow
```

插件窗口的**唯一合法创建途径**，透传 `WindowManager.register_window`
（`app/windows.py`）。懒创建（第一次 `show()` 才实例化 QML）、RinUI 接管、
失败兜底、定位、显隐全封装在返回的句柄里。插件不得直接碰
`_attach_to_rinui`，也不得自建 `QQuickWindow`，会漏掉一半该做的事。

返回的 `RegisteredWindow` 句柄只暴露三个方法加一个只读属性：
`show()` / `hide()` / `toggle()` / `window`（未创建时是 None）。
同名重复注册是幂等的：不建新窗口，记 warning 返回既有句柄。

常用 options：

* `position`：`"cursor_screen_center"`（默认，居中到光标所在显示器）、
  `"beside_settings"`（贴设置窗口旁边），或 `callable(window)` 完全自定义；
* `label`：日志和报错文案里的人话名字；
* `post_reattach` / `post_show`：窗口级钩子，签名 `callable(window)`，
  一般用不到。

这里**只注册不 show**，显示时机由你自己的动作处理器决定，所以句柄要存
在插件模块级变量里（`_demo` 的 `_window_handle`）。

窗口 QML 的写法约定（照抄 `ui/plugins/_demo/DemoWindow.qml`）：

* 根元素 `Rin.FluentWindow`，`visible: false`（显隐由句柄管）；
* **禁止** `Qt.FramelessWindowHint`，窗口边框、阴影、圆角全是 RinUI
  接管的，QML 侧插手会把系统阴影一起弄没（历史见 `ui/Settings.qml`
  头注释）；
* 标准关窗路径：用户点标题栏叉时拦掉默认关闭，转走动作通道让插件自己
  决定藏窗口：

  ```qml
  onClosing: function (event) {
      event.accepted = false
      Backend.triggerAction("plugin:<本插件id>:close")
  }
  ```

  然后插件的动作处理器里 `handle.hide()`。这是唯一不依赖 Backend 专用槽
  的通用关窗通道，不要自己发明别的关窗路径。

### 8. publish / subscribe：进程内消息总线

```python
ctx.publish(topic: str, payload: Any = None) -> None
ctx.subscribe(topic: str, handler: Callable[[Any], None]) -> None
```

插件间对话的通道。

* **topic 命名约定** `<发布者id>:<事件名>`（如 `_demo_dep:hello`）。订阅
  任意 topic 都合法（倾听不越权）；发布与自身 id 不符的前缀只记 warning
  不拦截，真正硬防越权的是动作动词和设置键那两处。
* **同步语义**：`publish` 在发布者线程里逐个同步调用订阅者。handler 里
  做重活（IO、COM、sleep）会直接拖住发布者，需要重活就自己丢后台线程
  或 QTimer。单个 handler 抛异常会被捕获记日志，不影响发布者和其他
  订阅者。
* **订阅只在 `register(ctx)` 内生效**。加载窗口一关，运行中调用
  `subscribe` 会被拒绝并记 warning：订阅集随运行时事件漂移的话，「谁在
  听这个 topic」会变成悬案。订阅生命周期与进程一致，不提供退订（与不做
  unregister / 热重载的决定一致）。

端到端范例就是 `_demo_dep` 依赖 `_demo` 这一对：`_demo` 在 register 里
`ctx.subscribe("_demo_dep:hello", _on_hello)`，`_demo_dep` 在 register 里
`ctx.publish("_demo_dep:hello", "ping")`。拓扑序保证 `_demo` 先注册、订阅
已就绪，`_demo_dep` 发布时消息必达。

---

## 配置约定与铁律

**插件贡献绝不落盘用户 `config.json`**，这是整个配置体系的第一原则。配置
层是「用户可改的值」，注册表是「存在哪些东西」，两者混写会让插件卸载后
在用户文件里残留死条目。落地方式分两种形状：

* **dict 型贡献**（`plugins.<id>.*` 的默认值）：走阶段一注入。在
  `plugin.py` 里声明 `DEFAULTS = {"volume": 50}`，`collect_defaults` 聚合后
  随 `Config(extra_defaults=...)` 注入**默认层**。效果：QML 随时能读到值，
  但落盘走 diff（只写与默认层不同的键），用户没改过就不会出现在
  `config.json` 里；用户改过的键照常落盘。loader 会自动给每个插件补
  `"enabled": True` 默认值，你自己声明了就不覆盖。注意 `DEFAULTS` 里**不能
  放列表值**，Config 注入时会剔除并告警（原因见下条）。
* **list 型贡献**（磁贴 / 控制条工具与动作 / 设置页 / 编辑器组）：只能在
  **读取层合并**。`Config._deep_merge` 对列表是整体替换，插件条目若注入
  默认层，用户一旦改过一次对应列表，用户层的旧列表会把插件条目整体顶掉，
  表现为「插件装了但磁贴不出现」。所以这些贡献永远留在注册表里，由
  `bridge.py` 的各个读取点（`_catalog` / `presentationConfig` /
  `_get_settings_nav_items`）做纯拼接，绝不写回 config。

对插件作者来说要做的事很简单：设置项默认值放 `DEFAULTS`（dict，别放
列表），其余贡献全部走 ctx 的 `add_*`，永远不要试图往 config 里写自己的
条目。

调试插件例外重申：`_` 前缀插件的 `DEFAULTS` 不走阶段一注入，关调试时
`plugins._demo.*` 连默认值都不存在，别在调试插件里验证「默认值注入」这条
链路。

---

## 依赖与故障语义

`META["depends"] = ["other_plugin"]` 声明依赖，loader 用拓扑排序保证**被
依赖者先 `register`**。这条保证的典型用法就是总线：依赖者发布时，被依赖
者的订阅一定已就绪（`_demo_dep` 依赖 `_demo` 的全部意义）。

失败时的行为：

* 依赖**缺失 / 被禁用 / 加载失败**：本插件跳过，依赖它的插件递归连带跳过，
  warning 日志列明因果链；
* **循环依赖**：环上插件全部跳过并告警；
* 单插件 **import 或 register 抛异常**：捕获记日志，跳过该插件及其递归
  依赖者，其余插件照常，应用不崩；
* PLUGINS 表内**重复 id**：启动硬失败（装配错误，不静默）。

每次加载的结果清单（谁成功、谁跳过、什么原因）可从
`loader.loaded_plugins()` 拿到，设置「插件」管理页展示的就是它。

---

## 翻译约定

插件文案分两类，走两条路（`registry.py` 头注释第 6 条）：

* **QML 里的静态文案**：直接 `qsTr("中文原文")`。
  `tools/update_translations.py` 的 lupdate 扫 `ui/` 整树，
  `ui/plugins/<id>/` 自动被收录。
* **经 Python 喂给 QML 的动态字符串**（磁贴 `title`、设置页 `title`、
  编辑器组 `display_name` 这些注册表条目的展示文案）：用
  `app.i18n.tr(context, source)` 标注后再传给 ctx。`context` 建议用插件
  id，避免与内置 context（`Splash` / `Tray` / `App` 等）撞名。译文手工
  维护进 `translations/luminalium_py_*.ts`，lupdate 不碰 Python 侧
  （`AGENTS.md` 明令）。两侧 ts 由 lrelease 合并成同一个 qm 加载。

注意 `qsTr` 只认字面量，动态标题塞不进去，这就是动态字符串必须绕行
Python tr 的原因。

---

## 参考范例：_demo 与 _demo_dep

`app/plugins/_demo/` 和 `app/plugins/_demo_dep/` 是框架验收夹具，刻意占位
级（一个标题一行字一个开关），但把每个机制都真用了一遍，是本文全部示例
的出处：

| 文件 | 演示了什么 |
|---|---|
| `_demo/plugin.py` | 8 个 ctx API 各调一遍（顺序即验收清单顺序）、模块级句柄存窗口、动作处理器按后缀分发、总线订阅 |
| `_demo_dep/plugin.py` | `META.depends` 依赖声明、register 期 publish、拓扑序保证 |
| `ui/plugins/_demo/DemoWindow.qml` | 插件窗口标准写法：Rin.FluentWindow、visible:false、onClosing 关窗链路 |
| `ui/plugins/_demo/DemoSettings.qml` | 插件设置页：Rin.FluentPage、SettingCard、开关绑 `Backend.settings.<key>`、`Qt.binding` 重装绑定的坑 |

上手路径建议：开 `app.debug` 把这两个夹具跑起来，设置「插件」页里能看到
它们（带「调试插件」标记），快捷面板「+」浮层里有「演示」磁贴，放映控制
条上有演示工具与动作，设置导航里有「演示插件」页。照着实物的形状写自己
的插件，比对着本文干读快得多。

---

## 常见错误速查

| 症状 | 多半原因 |
|---|---|
| 插件完全没出现 | id 没加进 `PLUGINS`（正式插件）；或 `app.debug` 没开（`_` 前缀调试插件）；或被禁用后没重启 |
| 磁贴 / 工具点了没反应 | 动作没走 `plugin:<id>:` 前缀；或处理器注册时动词带尾冒号且没经 ctx 包装（ctx 会替你剥） |
| 注册期 `ValueError: 动作动词必须在 ... 命名空间内` | `add_action_handler` 的前缀不是 `plugin:<本插件id>` 开头 |
| 注册期 `ValueError: 设置键必须 ... 前缀` | `register_setting` 的 key 不是 `plugins_<id>_` 开头 |
| 设置项在检查器里不出现 | 描述符的 `key` 没先 `register_setting`；或 `visible_when_group` 指了没注册的组名（后者注册期就会炸） |
| `RuntimeError: 插件注册表已冻结` | 在 `register(ctx)` 之外（运行中）调了 `add_*` |
| subscribe 不生效 | 在 register 之外订阅，加载期外订阅会被拒绝并记 warning |
| 控制条上插件组件的状态丢了 | 状态放在了 QML 侧，`rebuild_docks` 重建时蒸发，挪去 Python 侧 |
| 插件窗口没有阴影 / 圆角 | QML 里加了 `Qt.FramelessWindowHint` 或绕开了 `register_window` |
| `DEFAULTS` 里的列表不见了 | 列表值不允许注入默认层，会被剔除并告警；列表型贡献走 ctx 的 `add_*` |
