"""Luminalium 2 插件系统 —— ``PluginContext``（插件与宿主之间的唯一通道）。

每个插件在加载期拿到一个 ``PluginContext`` 实例（持有本插件 id 与对
``Backend`` / ``WindowManager`` 的引用），插件的 ``register(ctx)`` 通过它
声明全部贡献。插件**不直接 import** registry / bridge / windows —— 上下文
在这里做类型化包装与越权校验（动词前缀、设置键前缀、描述符校验），把
「插件写错了」的代价从运行期悬案变成注册期的明确异常。

三条铁规（2026-10-05 插件系统计划 Wave 3 任务 11）：

1. **dock 驻留插件组件的状态必须放 Python 侧**。
   ``WindowManager.rebuild_docks`` 会销毁并重建 dock Item，QML 侧（含插件
   dock_qml）持有的任何状态都会在重建时蒸发；需要跨重建存续的状态
   （开关态、计数、缓存）一律放插件自己的 Python 模块 / Backend 设置键里。
2. **注册表加载期只写、加载后冻结**。
   loader 在全部插件 ``register`` 完成后调 ``registry.freeze()``，之后任何
   ``add_*``（含经本上下文转手的）直接抛 ``RuntimeError``。消费端因此能
   假设「读到的就是全量」，插件也因此不能玩「运行中偷偷加磁贴」。
3. **总线是同步的，handler 里别干重活**。
   ``publish`` 在发布者线程里逐个同步调用订阅者；handler 里做重活（IO、
   COM、sleep）会直接拖住发布者。需要重活的场景由 handler 自己丢进
   后台线程 / QTimer。

通信总线约定：

* topic 命名约定 ``<发布者id>:<事件名>``（如 ``_demo_dep:hello``）。订阅
  任意 topic 合法（订阅是倾听，不越权）；发布与自身 id 不符的前缀只记
  warning 不拦截 —— 真正需要防越权的是动作动词与设置键（那两处是
  ``ValueError`` 硬拒绝）。
* 订阅表是**本模块级** dict，刻意不进 registry：注册表只管「存在哪些
  贡献」（加载期聚合、冻结后只读），总线是运行时设施，冻结不影响收发。
* handler 异常逐个捕获 + ``log.exception``，不影响发布者与其他订阅者。
* 订阅只在加载期（``register(ctx)`` 内）生效：loader 在注册循环前
  ``begin_load()``、结束后 ``end_load()``；加载后调用 ``subscribe`` 记
  ``log.warning`` 并拒绝。订阅随注册发生、生命周期与进程一致，不提供
  退订（与「不做 unregister / 热重载」的计划决定一致）。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ..paths import UI_DIR
from . import registry

log = logging.getLogger(__name__)

__all__ = [
    "PluginContext",
    "begin_load",
    "end_load",
    "is_loading",
    "register_plugin_defaults",
    "subscribers_snapshot",
]

# —— 总线运行时状态（模块级；订阅表不进 registry，原因见头注释）——
_subscribers: Dict[str, List[Callable[[Any], None]]] = {}
_loading = False


def begin_load() -> None:
    """打开订阅窗口（loader 在逐插件 ``register`` 循环之前调用）。"""
    global _loading
    _loading = True


def end_load() -> None:
    """关闭订阅窗口（loader 在注册循环结束后调用，其后 subscribe 被拒）。"""
    global _loading
    _loading = False


def is_loading() -> bool:
    return _loading


def register_plugin_defaults(plugin_id: str, defaults: Dict[str, Any]) -> None:
    """``plugins.<id>.*`` 默认值 dict 的注册通道（阶段一由 loader 使用）。

    插件声明默认值的方式是在 ``plugin.py`` 里放 ``DEFAULTS`` 常量，
    loader 的 ``collect_defaults`` 读取后经这里聚进 registry；本函数只是
    把「context 侧」与「registry 侧」的命名对齐的薄封装，插件本身不需要
    也不应该直接调它（``DEFAULTS`` 是唯一声明入口）。
    """
    registry.register_plugin_defaults(plugin_id, defaults)


def subscribers_snapshot() -> Dict[str, List[Callable[[Any], None]]]:
    """订阅表浅拷快照（诊断 / 自检用；运行逻辑不要依赖它）。"""
    return {topic: list(handlers) for topic, handlers in _subscribers.items()}


class PluginContext:
    """单个插件的宿主通道实例。loader 逐插件构造，插件只在 ``register`` 内持有。"""

    def __init__(self, plugin_id: str, backend: Any, windows: Any) -> None:
        self._plugin_id = plugin_id
        self._backend = backend
        self._windows = windows

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    # ---------------------------------------------------------- 配置（只读）

    def config_get(self, path: str, default: Any = None) -> Any:
        """只读配置访问口（2026-10-19 插件审计 D11/D-F11 收口）。

        插件此前一律穿透 Backend 的内部配置属性（``_config``）做私有
        直读——属性一改名 / 变结构全体插件在其账上炸。这里是
        唯一的读口：点路径读、键不存在回落 ``default``、backend 缺失或
        配置树未就绪同样回落 ``default``（对齐 ``add_shortcut`` 读内建
        磁贴目录的容错先例）。**只读**：不提供写口，配置写入与落盘纪律
        （贡献不落盘用户 config.json）不经插件之手。
        """
        try:
            return self._backend._config.get(path, default)
        except Exception:
            return default

    # ---------------------------------------------------------- 快捷面板

    def add_shortcut(
        self,
        id: str,
        title: str,
        icon: str,
        action: str,
        icon_source: Optional[str] = None,
    ) -> None:
        """注册快捷面板磁贴（形状对齐 ``quick_panel.shortcut_catalog``）。

        ``action`` 约定 ``plugin:<本插件id>:<动作名>``，触发时经动词注册表
        路由到 :meth:`add_action_handler` 登记的处理器。``title`` 应是
        插件已翻译好的文案（约定插件自己 ``app.i18n.tr(<id>, ...)``，透传
        —— ⚠️ 必须在 ``register`` 内现场调用：模块顶层跑在翻译器安装
        之前，那时 tr 永远回中文原文，见 ``docs/plugin-development.md``
        翻译约定一节）。
        """
        entry: Dict[str, Any] = {
            "id": id,
            "title": title,
            "icon": icon,
            "action": action,
        }
        if icon_source is not None:
            entry["iconSource"] = icon_source
        # 磁贴 id 与内建目录冲突 → 注册期就拒绝（2026-10-18 plugin-audit
        # D3）：合并规则「内建胜出」是有意的，但那意味着冲突磁贴**永不
        # 出现** —— 加载「成功」而磁贴无影无踪、唯一线索在日志，对作者
        # 是纯坑。这里炸出来，loader 把原因记在插件自己的账上。运行期
        # 用户改配置造成的新冲突仍由 bridge._catalog 的 warning 兜底。
        catalog = self.config_get("quick_panel.shortcut_catalog", []) or []
        builtin_ids = {
            str(item.get("id")) for item in catalog if isinstance(item, dict)
        }
        if id in builtin_ids:
            raise ValueError(
                f"插件 {self._plugin_id!r} 的磁贴 id {id!r} 与内建目录冲突"
                f"（内建胜出规则下永不出现），请改名"
            )
        registry.add_shortcut(entry)

    # ---------------------------------------------------------- 动作动词

    def add_action_handler(
        self, verb_prefix: str, handler: Callable[[str], Any]
    ) -> None:
        """注册动作动词前缀处理器。

        动词必须 ``plugin:<本插件id>`` 命名空间内（``plugin:<id>`` 或
        ``plugin:<id>:…``）—— 动词命名空间是全局的，不拦的话一个插件可以
        抢注 ``open_settings`` 或别的插件的前缀，把别人的动作静默劫走
        （越权）。这里直接 ``ValueError`` 硬拒绝。
        处理器签名 ``handler(action: str)``：拿到完整动作串自己解析后缀。

        ⚠️ 注册前剥掉尾冒号（2026-10-06 任务 12 实锤的接缝缺陷）：注册表
        动词的既定契约是「**不含分隔符**的裸动词」—— 分发侧
        ``application.py::_match_verb_handler`` 按 ``动作 == 动词`` 或
        ``动作.startswith(动词 + ":")`` 匹配；若把 ``plugin:<id>:`` 原样
        存进去，``动作.startswith("plugin:<id>:" + ":")`` 永远为假，
        插件的所有动作静默落空（任务 5/6 的 QA 直接往 registry 塞裸动词，
        没经过本包装，所以直到任务 12 全链路验收才暴露）。
        """
        bare = f"plugin:{self._plugin_id}"
        if verb_prefix != bare and not verb_prefix.startswith(bare + ":"):
            raise ValueError(
                f"插件 {self._plugin_id!r} 的动作动词必须在 {bare!r} 命名空间内，"
                f"实际: {verb_prefix!r}（禁止抢注其它命名空间）"
            )
        verb = verb_prefix[:-1] if verb_prefix.endswith(":") else verb_prefix
        registry.add_action_handler(verb, handler)

    # ---------------------------------------------------------- 放映控制条

    def add_dock_tool(
        self, id: str, label: str, icon: str, tooltip: Optional[str] = None
    ) -> None:
        """注册放映控制条工具（形状对齐 ``presentation.tools``）。"""
        entry: Dict[str, Any] = {"id": id, "label": label, "icon": icon}
        if tooltip is not None:
            entry["tooltip"] = tooltip
        registry.add_dock_tool(entry)

    def add_dock_action(
        self, id: str, label: str, icon: str, tooltip: Optional[str] = None
    ) -> None:
        """注册放映控制条动作（形状对齐 ``presentation.actions``）。"""
        entry: Dict[str, Any] = {"id": id, "label": label, "icon": icon}
        if tooltip is not None:
            entry["tooltip"] = tooltip
        registry.add_dock_action(entry)

    # ---------------------------------------------------------- 设置页

    def add_settings_page(
        self,
        id: str,
        title: str,
        page_qml: str,
        icon: str,
        position: Optional[int] = None,
    ) -> None:
        """注册设置页（并入设置窗口左侧导航）。

        ``page_qml`` 是 ``ui/plugins/<本插件id>/`` 下的**相对文件名**
        （如 ``"DemoSettings.qml"``），这里转成 ``file:///`` 绝对 URL 存进
        ``page_url`` —— 与内建导航条目的 ``page`` 形状对齐，消费端纯拼接。
        ``title`` 应是已翻译文案（约定插件自己 tr，透传）。

        路径纪律（2026-10-18 plugin-audit B8 收口）：拒绝反斜杠（Windows
        分隔符混进 URL 拼接是隐形坑）与 ``..`` 段（越出插件目录），且
        **注册期就检查文件存在** —— 坏路径在加载期炸出来（loader 隔离、
        只Fail该插件），别等用户点进设置页才白屏。
        """
        if (
            page_qml.startswith(("/", "\\"))
            or "\\" in page_qml
            or ".." in page_qml.split("/")
        ):
            raise ValueError(
                f"插件 {self._plugin_id!r} 的 page_qml 必须是 "
                f"ui/plugins/{self._plugin_id}/ 下的相对文件名（拒绝反斜杠与 "
                f".. 段），实际: {page_qml!r}"
            )
        page_file = UI_DIR / "plugins" / self._plugin_id / page_qml
        if not page_file.is_file():
            raise ValueError(
                f"插件 {self._plugin_id!r} 的 page_qml 文件不存在: {page_qml!r}"
                f"（应在 ui/plugins/{self._plugin_id}/ 下）"
            )
        page_url = "file:///" + page_file.as_posix()
        entry: Dict[str, Any] = {
            "id": id,
            "title": title,
            "page_url": page_url,
            "icon": icon,
        }
        if position is not None:
            entry["position"] = position
        registry.add_settings_page(entry)

    # ---------------------------------------------------------- 设置键

    def register_setting(
        self,
        key: str,
        path: str,
        *,
        notify: Optional[str] = None,
        side_effect: Optional[Callable[..., Any]] = None,
    ) -> None:
        """注册扁平设置键（QML 侧 ``Backend.settings.<key>`` 读写）。

        ``key`` 必须 ``plugins_<本插件id>_`` 前缀 —— 扁平键与内建键同住
        一张表，不拦的话插件可以覆盖内建键的映射（越权）。``path`` 必须
        ``plugins.<本插件id>.`` 前缀（2026-10-18 plugin-audit B6 收口）——
        设置键本质是「配置子树的一张合成视图」，path 不锁命名空间的话，
        插件可以注册 ``app.language`` 这类视图把任意配置子树读走 / 写坏。
        双写两处：registry（代码侧贡献事实来源，冻结后可审计）与
        ``Backend.register_setting_path``（运行期读写链路，任务 3 的 API）。
        """
        required = f"plugins_{self._plugin_id}_"
        if not key.startswith(required):
            raise ValueError(
                f"插件 {self._plugin_id!r} 的设置键必须 {required!r} 前缀，"
                f"实际: {key!r}（禁止占用内建 / 其它插件的键命名空间）"
            )
        required_path = f"plugins.{self._plugin_id}."
        if not path.startswith(required_path):
            raise ValueError(
                f"插件 {self._plugin_id!r} 的设置 path 必须 {required_path!r} "
                f"前缀（plugins.<id>.* 命名空间），实际: {path!r}"
            )
        registry.add_setting_path(
            key, {"path": path, "notify": notify, "side_effect": side_effect}
        )
        self._backend.register_setting_path(
            key, path, notify=notify, side_effect=side_effect
        )

    # ---------------------------------------------------------- 编辑器分组

    def add_editor_group(
        self,
        name: str,
        *,
        display_name: str,
        icon: str,
        dock_qml: Optional[str] = None,
        inspector_items: Any = (),
        traits: Any = None,
    ) -> None:
        """注册主界面编辑器分组。

        ``inspector_items`` 先过 ``app.windows.validate_inspector_items``
        （任务 10 的校验；内建组已全部登记，``visible_when_group`` 可查）
        再进注册表 —— 坏描述符在注册期炸出来，绝不流进检查器渲染。

        ``traits`` 的**输出形状恒为 dict**（``{trait名: True, ...}``）：
        这是注册表里组条目的既定契约 —— 内建组
        （``windows.py::_BUILTIN_DOCK_GROUPS``）就是字典形状，QML 消费端
        （``MainInterfaceEditor.qml`` 的 ``cornerHasTrait`` 等）按
        ``entry.traits[traitName] === true`` 的字典语义读取。两种输入都
        接受，统一到该形状：

        * Mapping（首选，与内建组同款）：``dict(traits)`` 原样拷贝；
        * 名字可迭代（``["toolbar", ...]`` 这类便捷写法）：展开为
          ``{名字: True}`` —— 绝不能 ``list(traits)`` 了事，dict 会被
          转成键名列表、QML 侧永远查不到（本 bug 的历史形态）；
        * None / 空集：``{}``。
        """
        # 延迟 import：windows 模块重（Qt 全家桶），context 要保持轻量可导。
        from collections.abc import Mapping as _Mapping

        from ..windows import validate_inspector_items

        items = list(inspector_items)
        validate_inspector_items(name, items)
        if traits is None:
            normalized_traits: Dict[str, Any] = {}
        elif isinstance(traits, _Mapping):
            normalized_traits = dict(traits)
        else:
            normalized_traits = {str(trait): True for trait in traits}
        group: Dict[str, Any] = {
            "display_name": display_name,
            "icon": icon,
            "inspector_items": items,
            "traits": normalized_traits,
        }
        if dock_qml is not None:
            group["dock_qml"] = dock_qml
        registry.add_editor_group(name, group)

    # ---------------------------------------------------------- 窗口

    def register_window(self, name: str, qml_path: Any, **options: Any) -> Any:
        """注册一只自管窗口，透传 ``WindowManager.register_window``。

        插件窗口与内建窗口走同一条懒创建路径（RinUI 接管 / 失败兜底 /
        定位 / 显隐三件套全封装）；插件**不得**直接碰 ``_attach_to_rinui``
        或自建 QQuickWindow。这里只注册不 show —— 显示时机由插件自己的
        动作处理器决定。

        冲突纪律（2026-10-18 plugin-audit D1/D2 收口）：窗口贡献先进注册表
        （``window_specs`` 从死代码接上 —— 注册表自称代码侧贡献唯一事实
        来源，窗口链此前不在册，审计与冻结语义对窗口失效）；插件间的同名
        冲突由 ``_put`` 的重复 id 硬拒绝（此前 ``register_window`` 的幂等
        分支会静默复用先到者的窗口，后注册一家的 ``toggle()`` 开的是别人
        的窗）；与内建窗口（settings/debug/editor，不经注册表）的冲突在
        这里显式拒绝。
        """
        manager_windows = getattr(self._windows, "_registered_windows", None) or {}
        if name in manager_windows:
            raise ValueError(
                f"插件 {self._plugin_id!r} 的窗口名 {name!r} 与内建窗口冲突，请改名"
            )
        registry.add_window_spec(
            name, {"qml_path": str(qml_path), "owner": self._plugin_id}
        )
        return self._windows.register_window(name, qml_path, **options)

    def register_overlay(
        self, name: str, qml_path: Any, *, label: Optional[str] = None
    ) -> Any:
        """注册一只全屏叠加窗口（聚光灯这类「整屏遮罩 + 镂空」）。

        与 :meth:`register_window` 不同族的窗口（2026-10-06 随聚光灯插件
        新增）：透明置顶、不抢焦点、无 RinUI 非客户区接管，返回的句柄除
        ``show() / hide() / toggle()`` 外还有 ``set_hole(cx, cy, radius)``
        —— 插件自己的定时器轮询光标，把镂空圆（窗口局部逻辑坐标）一拍
        一拍喂进来，区域塑形由 ``app/windows.py`` 统一做。

        为什么单独开一条口子而不是让插件走 ``register_window``：RinUI
        接管的全屏透明窗口会把 DWM 非客户区处理套上来跟遮罩打架（与
        放映顶层窗口刻意不接管的理由相同，见 ``app/windows.py``）。铁律
        不变 —— 插件仍然不得自建 QQuickWindow，叠加窗口也得走这里登记。
        """
        return self._windows.register_overlay(name, qml_path, label=label)

    # ---------------------------------------------------------- 全局配置

    def narration_language(self) -> str:
        """全局旁白 / 配音语言：``zh_CN``（中配）/ ``en_US``（英配）/ ``ja_JP``（日配）。

        2026-10-17 用户指令：配音语种是**对外暴露的全局配置**，插件里的旁白 /
        配音场景一律读这里，不要自己往配置里塞一份语种项。返回值**保证**
        落在三档之内（用户没配过 / 配置被改坏都回退 ``zh_CN``，见
        ``app/narration.py::language``），调用方不需要再判空或兜底。

        这是本上下文唯一的「读宿主机配置」入口 —— 仍然是**类型化包装**，
        不是把 Backend 交出去（铁律不变：插件不直接碰 bridge / config）。
        需要「改了就跟着变」的插件把自己的状态缓存起来、在需要时重读即可：
        配音通常在触发那一刻才用得上，现读成本可忽略。
        """
        return self._backend.narration_language()

    # ---------------------------------------------------------- 运行时状态

    def publish_state(self, key: str, value: Any) -> None:
        """发布一条插件运行时状态（pluginState 通道，QML 侧只读）。

        与 :meth:`register_setting` 的差别：设置键是**持久配置**的合成视图
        （有落盘语义），运行时状态是**会话级**事实——聚光灯「试出来的」
        光斑大小这类调整不写回配置（写回会把试出的值变成永久默认），但
        设置页 QML 又需要读到它。通道**无回环**：QML 读 ``pluginState``
        渲染，写仍走 ``setSetting``（``onMoved`` 仅用户拖动触发），程序
        推送不会引起任何持久化。值全等时宿主侧静默不发信号。
        """
        self._backend.set_plugin_state(self._plugin_id, key, value)

    # ---------------------------------------------------------- 通信总线

    def publish(self, topic: str, payload: Any = None) -> None:
        """同步发布一条总线消息。

        逐个同步调用订阅者；单个 handler 的异常捕获 + ``log.exception``
        后继续，不影响发布者与其他订阅者（故障隔离与插件加载同原则）。
        ⚠️ handler 跑在发布者线程里 —— 铁规 3：handler 里别干重活。
        """
        expected = f"{self._plugin_id}:"
        if not topic.startswith(expected):
            log.warning(
                "插件 %s 发布了非自身前缀的 topic %r（约定 %r 开头），已放行",
                self._plugin_id, topic, expected,
            )
        for handler in list(_subscribers.get(topic, ())):
            try:
                handler(payload)
            except Exception:
                log.exception(
                    "总线 topic %r 的订阅者 %r 抛异常，已跳过（不影响其它订阅者）",
                    topic, handler,
                )

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """订阅一个总线 topic；handler 签名 ``handler(payload)``。

        只在加载期（``register(ctx)`` 内）生效 —— 加载后订阅意味着「订阅
        集随运行时事件漂移」，排查「谁在听这个 topic」会变成悬案，故拒绝。
        """
        if not _loading:
            log.warning(
                "插件 %s 在加载期外订阅 topic %r，已拒绝（订阅只能在 register 内登记）",
                self._plugin_id, topic,
            )
            return
        _subscribers.setdefault(topic, []).append(handler)
