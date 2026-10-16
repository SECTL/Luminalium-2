# 给来这个仓库干活的 AI

我是这个项目的维护者。下面这些是我希望你进门之前就知道的事，按想到的顺序写的，没什么讲究。

## 这是个什么项目

Luminalium 2，纯粹的演示注释工具：托盘 + 快捷面板，检测到 PowerPoint / WPS 放映时在屏幕上叠一层控制条（翻页、笔、指针那套）。PySide6 + RinUI（QML），没有网页前端、没有 node，别往这个方向想。

源码跑起来就是：

```
.venv\Scripts\python.exe main.py
```

## 动手之前

**先把你要改的那个 QML 文件的头注释整个读一遍。** 这个仓库的习惯是：每个非显然的决定都写在文件头注释里，带日期和来历（「2026-10-05 用户指令：……」），坑也记在里面。很多注释看起来啰嗦，但每一段背后都是一次真实的踩坑，先读再动手能省你一半时间。反过来，你做的改动如果推翻了某条旧注释，把注释一起改掉，别留一段说着已经不存在的事情的文字在那骗下一个人。

代码注释、界面文案全用中文。注释解释"为什么"，不解释"是什么"——那种 `# 设置标题` 式的注释别写。

## 改完之后怎么验收

三步，顺序来的：

1. `.venv\Scripts\python.exe tools\check_qml.py` —— 全部 QML 过一遍编译，几秒钟，失败 0 才算完。
2. `.venv\Scripts\python.exe tools\preview.py` —— 离屏渲染一堆 PNG 到 `preview/`，你自己看图。环境变量在文件头注释里，浅色主题是 `LUMI_PREVIEW_THEME=light`。
3. `.venv\Scripts\python.exe tools\smoke.py` —— 端到端自检，跑得慢（几分钟），但它是真的在开窗口、点按钮。注意它会**真的开关一次本机的注册表 Run 键**（测开机自启），测完自己恢复，这是设计好的，别被吓到也别跳过。

跑 smoke 之前记得确认你的改动没有把窗口搞崩——smoke 挂了优先怀疑自己的改动，其次怀疑时序（它输出里会写）。

## 几条硬规矩

- **RinUI 是 pip 装的包，别改它**。仓库根目录那个 `RinUI/` 文件夹里只有 `config/rin_ui.json`，是 RinUI 自己持久化主题状态用的，跑预览会被改，正常。哪天 RinUI 真缺组件（比如 `IconWidget`、`EmptyState` 这种新版才有），在项目里照着样子自己写一个，别去动 site-packages。
- **别给窗口加 `Qt.FramelessWindowHint`**。窗口边框、阴影、圆角、贴边全是 RinUI 接管的，QML 侧再插手会把系统阴影一起弄没。这段历史在 `ui/Settings.qml` 的头注释里。
- **窗口都是懒创建、只藏不销毁**（设置、编辑器、调试窗都是）。重建窗口没有必要，托盘常驻应用里也没人喜欢窗口闪一下。
- **配置只有一处来源**：`config/default_config.json` 是默认值，里面可以用 `"//xxx"` 这种键写注释；用户数据在 `config/config.json`（不进包）。QML 一律从 `Backend` 读，Python 侧不要另外再注入一份。
- **插件贡献绝不落盘用户 `config.json`**。dict 型默认值（`plugins.<id>.*`）走 `Config(extra_defaults=...)` 注入默认层；list 型贡献（磁贴 / 工具 / 动作 / 角落组）只能在读取层拼接，注入默认层会被用户层的旧列表整体顶掉。理由与证据在 `app/plugins/registry.py` 头注释第 3 条。
- **插件窗口只能走 `WindowManager.register_window`**（全屏叠加遮罩走 `register_overlay`，同属 `app/windows.py` 的封装）。它封装了懒创建、RinUI 接管、失败兜底、定位、显隐这一整套易错清单；插件直接碰 `_attach_to_rinui` 或自建窗口都会漏掉一半。约定全文在 `app/windows.py` 头注释。
- **用户明令删掉的东西别加回来**。托盘设置那一组、"重新加载"按钮（现在是重启）、关于页的开源许可项，都是一条条指令删的，历史理由写在对应文件注释里。你要是觉得该恢复，先问，别自作主张。
- 翻译：界面文案用 `qsTr`，`translations/` 里有 ts。语言名用各自的母语名（简体中文 / English / 日本語），这是惯例不是bug。

## 一些救过命的坑（详见各文件注释，这里只点名）

- `QTest.qWait` 攥着 GIL 不放，会饿死纯 Python 后台线程——轮询步长别调大。
- QML 里的裸 `window` 标识符是宿主相关的，页面可能被塞进 Loader 宿主（preview.py 就这么干），拿窗口用 `Window.window`。
- 异步大图别急着断言，等 `paintedWidth > 0`；`Image.status` 是枚举，PySide 读不回来。
- QML 派生类型的类名带 `_QMLTYPE_<n>`，按 `objectName` 找东西，别按类名。
- 深色主题下"看不见的描边"多半是黑色 alpha 描边压在深色底上，用 `Lumi.hairline`。

## 版本号

版本号长这样：**年份.中版本.小版本.状态**，定义在 `app/__init__.py` 的 `__version__`，别处（设置标题栏、关于页、诊断信息）都是读它，改版本只改这一个地方。

最后一位是状态：**1 是开发版，0-10 里除了 1 都是正式版**。所以 `26.0.707.1` = 2026 年、开发版。发正式版就是把状态位从 1 换成别的数，别动前三位。

## 最后

改完代码自己先看一眼渲染出来的图再说话。预览图就在 `preview/`，别拿"应该没问题"交差。

## 任务 → 代码位置速查

详细的架构与链路说明在 `.memory/topics/project-overview.md`（若存在），这里只放最常用的定位。

| 要干什么 | 去哪 |
|---|---|
| 加/改一个设置项 | `app/bridge.py` 的 `SETTING_PATHS`（加一行）+ 对应 `ui/settings/*.qml` 页面 |
| 改放映检测 / 翻页 / 笔 / 指针 | `app/ppt_controller.py`（`PptController`，探测与控制全在这一个文件） |
| 改控制条外观与布局 | `ui/presentation/`（`PresentationDock.qml` 本体、`SidePager.qml` 竖版翻页）；显隐与定位在 `app/windows.py` |
| 改托盘或快捷面板 | 托盘：`app/tray.py`（恒定行为，无配置项）；面板：`ui/QuickPanel.qml` + `ui/QuickPanel/`，摆放在 `app/windows.py` |
| 改窗口创建 / 摆放 / 穿透 | `app/windows.py`（`WindowManager`，所有窗口的创建中枢） |
| 改启动流程 / 信号接线 | `app/application.py`（装配 + `_wire` + 动作分发） |
| 改颜色 / 间距 / 尺寸 | `ui/Luminalium/Lumi.qml`（设计令牌单例） |
| 改版本号 | `app/__init__.py` 的 `__version__`（唯一一处） |
| 改崩溃 / 错误报告 | `app/error_handler.py` + `ui/ErrorReport/` |
| 改翻译 | `translations/`（QML 侧 lupdate 生成；Python 侧 ts 手工维护，别用 lupdate 碰） |
| 排查"控制条没出来/按钮没反应" | 按链路逐跳：探测 `ppt_controller` → `windows._on_presentation_state` → `bridge.Backend.apply_state` → QML |
| 写/改一个插件 | `app/plugins/`（registry/context/loader）+ `ui/plugins/<id>/`，约定见 `docs/plugin-development.md` |
| 改外部插件导入 / 卸载 | `app/plugins/external.py`（校验/拷贝）+ `ui/settings/Plugins.qml`（导入 UI），装好的插件在数据根 `plugins/` |

---

## 记忆规则（zcode 结构：索引 + 主题文件，本地约定）

项目记忆采用 **索引 + 主题文件** 两级结构，沉淀的知识统一写入 `.memory/`（已 gitignore，不入库），禁止散落在对话或临时笔记中。

### 结构

```
.memory/
├── MEMORY.md            # 索引（唯一入口，单行摘要 + 链接）
└── topics/
    ├── <主题A>.md        # 主题文件（详细内容）
    └── <主题B>.md
```

- **`.memory/MEMORY.md`**：索引。每条记忆一行，格式 `- [主题](topics/<文件>.md) — 一句话摘要`。只放导航，不放正文。
- **`.memory/topics/<主题>.md`**：主题文件。一个主题一个文件，文件名用短横线小写英文（如 `build-pipeline.md`、`qml-i18n.md`）。

### 写入时机

出现以下内容时，**立即写入**，不要等任务结束批量补：

- 排查过的问题与根因（错误现象 → 原因 → 修复）
- 项目特有的约定、坑、隐性约束
- 调试/构建/发布流程中验证有效的命令
- 架构决策及理由
- 用户明确说"记住"的内容

### 追加流程

1. **先看索引**：`.memory/MEMORY.md` 中是否已有同主题文件。
2. **有** → 往该主题文件追加条目，必要时更新索引摘要行。
3. **没有** → 新建 `.memory/topics/<主题>.md`，并在索引末尾加一行链接。
4. 写完即完成，不需要额外汇报。

### 主题文件格式

```markdown
# <主题名>

## <条目标题>（YYYY-MM-DD）
<内容：现象 / 结论 / 命令 / 代码片段，按类型组织>
```

- 条目按时间倒序追加（新的在上面）。
- 电报体，只写非显而易见的结论；人尽皆知的常识不写。
- 命令和代码用代码块，注明适用场景。

### 维护规则

- 索引只存单行摘要，摘要变化时同步修改对应行。
- 同一主题不重复建文件；主题膨胀到难以检索时再拆分，拆分后更新索引。
- 过时的条目标注 `~~删除线~~ + 作废原因`，不直接删除（保留决策痕迹）。
- 记忆是项目级资产，写入内容不包含个人隐私、密钥、临时路径。
