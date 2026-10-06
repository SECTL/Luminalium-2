"""QML 桥接层。

QML 只依赖这里暴露的属性与槽函数，不直接触碰配置、Win32 或 PowerPoint 细节。
新增功能时通常只需要：加一个 ``Slot`` + 在 QML 里连上按钮。

2026-10-05：设置系统改成「内建常量 + 动态注册」双轨。加一个设置项仍然是
「加一行」—— 内建项写进 ``SETTING_PATHS`` 常量（副作用按下面的两级表登记），
插件项走 :meth:`Backend.register_setting_path` 运行时注册。插件键命名约定
``plugins_<id>_<name>``：既不会撞内建键，也不会误中 ``presentation_`` 前缀
广播规则。``setSetting`` 的副作用不再是硬编码 if/elif，而是两级查找：
① 键级回调表（精确命中，可带 side_effect）② 前缀 / 集合规则表（按前缀发
整块配置变更信号）。未注册的键照旧被日志丢弃。

2026-10-05（插件系统 Wave 2 任务 5）：快捷面板磁贴目录改成**双来源** ——
config 的 ``quick_panel.shortcut_catalog`` 内建条目 ∪ ``app.plugins.registry``
的插件磁贴，在 :meth:`Backend._catalog` 这个唯一读取点做纯拼接（插件追加在
内建之后，同名 id 内建胜出并记 warning）。合并绝不写回 config：配置层只存
用户启用 / 排序的 id 列表（``quick_panel.shortcuts``），目录内容不落盘是
铁律 —— 列表若走 config 默认层会被用户层的旧列表整体顶掉（详见
``app/plugins/registry.py`` 头注释第 3 条）。

2026-10-05（插件系统 Wave 2 任务 6）：控制条 tools/actions 同样双来源 ——
``presentationConfig`` 返回**深拷贝**后的合并结果（内建数组在前，
``registry.dock_tools()`` / ``dock_actions()`` 的插件条目追加在后，id 冲突
内建胜出）。必须深拷贝的为什么：``Config.get("presentation")`` 返回的是配置
对象的**内部引用**，直接往里 append 会把插件贡献写进 config 内存态 —— 这既
违反「插件贡献不落盘也不进 config 内存态」的铁律，还会让每次读取重复追加
同一条目。拷贝后合并，配置层永远干净、每次读取都是全量重算。QML 零改动：
PresentationDock 的 Repeater 本就遍历这两个数组，插件贡献自动出现。
``selectTool`` 对 ``plugin:`` 前缀的工具 id 不进白名单、不调 ``ppt.set_tool``，
改按动作处理（emit ``actionTriggered``），由应用层的 ``plugin:`` 特权通道
分发给插件处理器 —— 插件工具与 COM / 按键注入零接触。

2026-10-05（插件系统 Wave 2 任务 7）：设置窗口左侧导航同样改成数据驱动 ——
原 ``ui/Settings.qml`` 里硬编码的 ``navigationItems`` 逐字搬进
``_BUILTIN_SETTINGS_NAV``，与 ``registry.settings_pages()`` 的插件设置页在
:meth:`Backend._get_settings_nav_items` 拼接（内建在前、插件在后）后作为
``settingsNavItems`` 属性喂给 QML。搬到 Python 的原因：QML 的静态列表属性
拼不了运行时数据，且动态条目的标题 ``qsTr`` 翻译不了（``qsTr`` 只认字面量），
必须走 ``app.i18n.tr``。条目形状、顺序、「关于 / 更新」钉底部的语义全部照旧。
"""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication

from . import autostart
from . import i18n
from .config import Config
from .paths import RESOURCES_DIR, UI_DIR
from .plugins import registry
from .ppt_controller import PresentationState

log = logging.getLogger(__name__)

#: 设置窗口里可改的项：QML 用的扁平键 -> 配置里的点号路径。
#: 加新开关时**只在这里加一行**，QML 侧用 ``Backend.settings.<扁平键>`` 读、
#: ``Backend.setSetting("<扁平键>", 值)`` 写。
SETTING_PATHS: Dict[str, str] = {
    "theme": "app.theme",
    "accent": "app.accent",
    "language": "app.language",
    "log_level": "app.log_level",
    # ⚠️ ``autostart`` 是**特例**：它的本体是 Windows 注册表（见 ``app/autostart.py``），
    #    配置里的 ``app.autostart`` 只是给日志 / 排查看的一份影子。读写两边都走
    #    注册表 —— ``_get_settings`` 每次回读真实状态，``setSetting`` 也单独分叉
    #    （见 :meth:`Backend._apply_autostart`），不走下面通用的「改内存 + 延迟落盘」。
    "autostart": "app.autostart",
    # ⚠️ ``tray.enabled`` / ``tray.tooltip`` / ``tray.show_on_click`` /
    #    ``tray.notify_on_start`` **没有**登记在这里，配置里的 ``tray`` 段也已删除：
    #    2026-10-01（第二轮）用户指令「托盘整组连着相关的逻辑和代码一块删掉」。
    #    现在托盘是**恒定行为**（常驻 + 提示文字取 app.name + 左键开面板 + 启动不弹
    #    气泡，见 ``application.py::_boot_tray/_boot_ready`` 与 ``TrayIcon``），
    #    没有可配置的路。
    # ⚠️ ``quick_panel.hide_on_deactivate`` 同理删除：失焦收起是**默认行为**
    #    （``windows.py::_on_panel_active_changed`` 恒定生效）。
    "panel_shortcuts_locked": "quick_panel.shortcuts_locked",
    "panel_section_shortcuts": "quick_panel.sections.shortcuts",
    "panel_section_footer": "quick_panel.sections.footer",
    "presentation_poll_interval_ms": "presentation.poll_interval_ms",
    "presentation_margin_x": "presentation.margin_x",
    "presentation_margin_y": "presentation.margin_y",
    "presentation_bar_height": "presentation.bar_height",
    # 控制条组件的整体缩放倍率（设置 → 主界面 → 「缩放大小」）。0.5~2.0 的**小数**
    # （滑块按整数百分比走，写回时再除 100）—— 见 default_config.json 的 ``presentation.scale``。
    "presentation_scale": "presentation.scale",
    "presentation_buttons_show_labels": "presentation.buttons.show_labels",
    "presentation_pager_position": "presentation.pager.position",
    "presentation_screen_index": "presentation.screen_index",
    "presentation_shadow_enabled": "presentation.surface.shadow.enabled",
    "presentation_surface_opacity": "presentation.surface.opacity",
    # ⚠️ ``presentation.divider.enabled`` / ``presentation.pager.enabled`` **没有**
    #    登记在这里：这两个开关 2026-10-01 按用户指令从界面上删除了（配置键仍
    #    生效、默认 true，只是改成纯配置项 —— 想关就在 config/config.json 里写）。
    #    登记进来的话 QML 侧会多一份没人读的代理属性，反而看不出它已经没有界面。
    "presentation_exit_style": "presentation.exit.style",
    # 只在调试窗口出现（隐藏入口：设置标题连点 10 次），普通用户看不到水印开关
    "dev_watermark": "app.dev_watermark",
}

#: 值一变就需要 QML 重新取整块配置的键。
_BROADCAST_KEYS = {"panel_section_shortcuts", "panel_section_footer"}

#: 键级副作用回调的签名：``(config, 扁平键, 新值)``。config 在前是因为这类回调
#: 十有八九是「再连带改几个配置键」（比如翻页组件位置 → corners）；要发信号的
#: 场景走 ``notify`` 信号名，不必在回调里碰 Backend。
SettingSideEffect = Callable[["Config", str, Any], None]

#: 副作用第二级：前缀规则表。扁平键命中前缀即发对应的整块配置变更信号
#: （``(信号名, 是否带 str(值) 作为参数)``）。``presentation_`` 前缀：控制条
#: 外观 / 几何变了；改 ``presentation_screen_index`` 会换一块显示器，还没放映
#: 过时 ``presentationScreen`` 是按配置现算的，所以连 ``presentationScreenChanged``
#: 一起发，给它一个重取的理由。
_PREFIX_NOTIFY_RULES: Tuple[Tuple[str, Tuple[Tuple[str, bool], ...]], ...] = (
    (
        "presentation_",
        (("presentationConfigChanged", False), ("presentationScreenChanged", False)),
    ),
)

#: 键级副作用条目的结构：``signals`` 为 ``(信号名, 是否带值)`` 列表，
#: ``side_effect`` 为可选回调（见 ``SettingSideEffect``）。
_KeyEffect = Dict[str, Any]

#: 「翻页组件位置」的两种形态 -> 该形态下**启用**的角落。
#:
#: 改这一项会连带开关 ``corners`` 里对应的四个角：真实生效的仍是 ``corners``
#: （``windows.py::_load_docks`` 与编辑器预览都只读它），``pager.position``
#: 只是它的人话开关 —— 两种形态二选一，同时开会变成四个翻页栏。
PAGER_POSITION_CORNERS: Dict[str, tuple] = {
    "side": ("middle_left", "middle_right"),
    "bottom": ("bottom_left", "bottom_right"),
}

#: RinUI ``Position`` 枚举里 ``Bottom`` 的整数值（``utils/Position.qml``：
#: Top=0, Bottom=1）。经 QVariant 递到 QML 后是 JS number，
#: ``NavigationBar.qml`` 的 ``item.position === Position.Bottom`` 严格比较成立；
#: 不写 ``position`` 键的条目在 QML 侧读为 ``undefined``，按 NavigationBar 的
#: 判定落入普通区（不钉底）。
_RIN_POSITION_BOTTOM = 1

#: 设置窗口左侧导航的**内建**条目：``(ui/ 下相对页路径, 标题原文, 图标, position)``。
#:
#: 2026-10-05（插件系统 Wave 2 任务 7）从 ``ui/Settings.qml`` 的硬编码
#: ``navigationItems`` **逐字**搬来 —— 标题、图标、页面、顺序、「关于 / 更新」
#: 钉底部的语义全部照旧。搬到 Python 的原因见文件头注释。
#:
#: ⚠️ ``page`` 最终必须是 **file:/// 绝对 URL**：RinUI ``NavigationView`` 用
#: ``Qt.createComponent`` 加载页面，相对路径会以 RinUI 模块自身为基准而解析失败
#: （原 ``Settings.qml`` 头注释里记过的坑）。URL 在这里拼好成品，QML 侧零拼接。
#:
#: 条目的历史沿革（从被删的 QML 注释留档）：
#: - 「通用」：2026-10-01 原挂在它下面的子项「快捷面板」删除后成为叶子节点；
#:   同日第四轮「应用主题 / 强调色」搬去「个性化」，本页只留「快捷方式锁定」
#:   +「界面语言」两张卡。
#: - 「个性化」：2026-10-01（第四轮）新建，承接「应用主题」「强调色」两张卡；
#:   插在「通用」之后、「主界面」之前 —— 它调的是**整个应用**的取色，层级更高。
#: - 「主界面」：2026-10-01 由「外观」改名而来，原页的主题 / 强调色 / 界面语言
#:   三张卡挪走；本页专放主界面自己的设定（可视化编辑在独立的
#:   MainInterfaceEditor 窗口）。
_BUILTIN_SETTINGS_NAV: Tuple[Tuple[str, str, str, Optional[int]], ...] = (
    ("settings/Home.qml", "主页", "ic_fluent_home_20_regular", None),
    ("settings/General/Index.qml", "通用", "ic_fluent_settings_20_regular", None),
    (
        "settings/Personalization.qml",
        "个性化",
        "ic_fluent_paint_brush_20_regular",
        None,
    ),
    ("settings/MainInterface.qml", "主界面", "ic_fluent_window_20_regular", None),
    ("settings/About.qml", "关于", "ic_fluent_info_20_regular", _RIN_POSITION_BOTTOM),
    (
        "settings/Update.qml",
        "更新",
        "ic_fluent_arrow_sync_20_regular",
        _RIN_POSITION_BOTTOM,
    ),
)


class Backend(QObject):
    """面向 QML 的应用后端。"""

    #: 设置项写盘的合并窗口（ms）。滑块拖动 / SpinBox 连点会连续改值，
    #: 这段窗口内的多次改动只落一次盘。
    _SAVE_DEBOUNCE_MS = 400

    # ---- 通知类信号 ----
    presentationActiveChanged = Signal()
    slideChanged = Signal()
    activeToolChanged = Signal()
    #: 墨迹颜色变了（QML 侧的笔选单靠它回显选中的那一格）
    penColorChanged = Signal()
    shortcutsChanged = Signal()
    presentationConfigChanged = Signal()
    #: 编辑器分组清单变了（注册表 ``editor_groups()`` 的列表视图）。
    #: 注册时机固定在窗口加载期（``windows.py::_register_builtin_groups``），
    #: 早于任何 QML 窗口创建，属性现算现读即可；Wave 3 loader 冻结后若出现
    #: 运行期注册，再由任务 11 补发这个信号。
    presentationGroupsChanged = Signal()
    presentationScreenChanged = Signal()
    quickPanelConfigChanged = Signal()
    settingsChanged = Signal()
    #: 设置窗口导航清单变了（插件设置页注册进 ``registry.settings_pages()``）。
    #: 注册时机固定在加载期（冻结前），早于任何 QML 窗口创建，属性现算现读即可；
    #: 若将来出现运行期注册，由注册方负责发这个信号。
    settingsNavItemsChanged = Signal()
    statusChanged = Signal()
    #: 启动画面的进度 / 阶段文字变了
    splashChanged = Signal()

    # ---- 请求类信号（由窗口管理器 / 应用层响应）----
    panelHideRequested = Signal()
    shortcutTriggered = Signal(str)
    actionTriggered = Signal(str)
    #: 重启整个程序（快捷面板底栏的「重启」按钮）：由应用层拉起新进程后退出。
    #: 原 ``reloadRequested``（仅重读配置）已按 2026-10-02 用户指令改成重启 ——
    #: 用户语义里这个按钮就该是「重启程序」，只重读配置反而「点了没反应」。
    restartRequested = Signal()
    quitRequested = Signal()
    settingsRequested = Signal()
    settingsCloseRequested = Signal()
    #: 调试窗口（隐藏入口：设置窗口标题连点 10 次）
    debugWindowRequested = Signal()
    debugWindowCloseRequested = Signal()
    #: 主界面编辑器（入口：快捷面板的「主界面编辑器」快捷方式）
    editorRequested = Signal()
    editorCloseRequested = Signal()
    themeChangeRequested = Signal(str)
    accentChangeRequested = Signal(str)
    #: 启用 / 停用的角落集合变了（翻页组件位置切换）：控制条**换了一组组件**，
    #: 光挪位置不够，得按新的角落重建（``windows.py::rebuild_docks``）。
    docksRebuildRequested = Signal()

    def __init__(self, config: Config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config

        self._presentation_active = False
        self._slide_index = 0
        self._slide_total = 0
        #: 默认工具是**鼠标指针**（``arrow``）。
        #:
        #: ⚠️ 2026-10-01 用户指令「顶层窗口的工具栏的 Segmented 默认工具不应该
        #: 是鼠标指针吗？」—— 这里原本是 ``pen``，与配置里 ``presentation.tools``
        #: 的排布意图（``arrow`` 放第一个，见该段注释）自相矛盾：控制条一出来
        #: 就高亮着「笔」，用户得先点一下指针才能正常放映，等于默认把放映
        #: 变成书写。默认必须是「什么都不做」的那个工具。
        self._active_tool = "arrow"
        #: 墨迹颜色（``#RRGGBB``）。空串 = 还没有选过 —— QML 侧据此决定
        #: 哪一格点亮（见 :meth:`setPenColor`）。
        self._pen_color = ""
        self._status_text = ""

        #: 启动画面进度（0..1）与阶段文字。由应用层按真实里程碑推进
        #: （见 ``application.py::LuminaliumApplication._boot_*``）。
        self._splash_progress = 0.0
        self._splash_stage = ""

        #: 已启用的快捷方式 id（顺序即显示顺序）
        self._shortcut_ids: List[str] = [
            str(item) for item in (config.get("quick_panel.shortcuts", []) or [])
        ]

        #: ``WindowManager`` 推来的**真实**放映显示器几何（顶层窗口铺在哪块屏）。
        #: None 表示还没有放映过，此时 :meth:`_get_presentation_screen` 自己按
        #: 配置索引兜底。见 ``syncPresentationScreen``。
        self._overlay_screen: Optional[Dict[str, Any]] = None

        #: 设置项的**延迟落盘**（见 :meth:`setSetting`）。
        #:
        #: ``Config.set(persist=True)`` 会把整份用户配置重写一遍 —— 滑块拖一次
        #: 会发几十个 ``moved``，逐个落盘就是几十次磁盘写。这里改成「先改内存、
        #: 停手 ``_SAVE_DEBOUNCE_MS`` 之后再写一次」。进程正常退出时
        #: ``application.quit()`` 还会补一次 ``config.save()``，不会丢。
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(self._SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._config.save)

        #: 「关于」页两条**异步**链路的后台线程（取回声洞句子 / 采集诊断信息）。
        #: 只为「同一件事不并发第二次」而持有；线程本身是 daemon，退出即回收。
        self._echo_thread: Optional[threading.Thread] = None
        self._diagnostics_thread: Optional[threading.Thread] = None

        # ---- 设置项注册表（内建常量 + 动态注册）----
        #: 动态注册的「扁平键 -> 点号路径」（插件走 ``register_setting_path``）。
        #: 与 ``SETTING_PATHS`` 合成视图见 :meth:`_setting_paths` —— 内建优先，
        #: 动态注册同名键会被拒绝，防插件顶掉内建行为。
        self._dynamic_paths: Dict[str, str] = {}
        #: 副作用第一级：键级回调表（精确命中优先于前缀规则）。内建特例原样
        #: 登记在这里，行为与重构前的硬编码 if/elif 完全一致：
        #: - ``presentation_pager_position``：连带开关四个角落（两种形态二选一，
        #:   见 ``PAGER_POSITION_CORNERS`` 处的说明）—— 真实生效的是 ``corners``，
        #:   所以这一步不是「副作用」而是这个开关的本体；角落集合变了控制条得按
        #:   新角落重建（``docksRebuildRequested``）。
        #: - ``theme`` / ``accent``：各自带值发请求信号，由应用层真正换肤。
        self._key_effects: Dict[str, _KeyEffect] = {
            "presentation_pager_position": {
                "signals": [("docksRebuildRequested", False)],
                "side_effect": lambda config, key, value: self._apply_pager_position(
                    str(value)
                ),
            },
            "theme": {"signals": [("themeChangeRequested", True)], "side_effect": None},
            "accent": {"signals": [("accentChangeRequested", True)], "side_effect": None},
        }


    # ==================================================================== 常量

    @Property(str, constant=True)
    def appName(self) -> str:
        return str(self._config.get("app.name", "Luminalium 2"))

    @Property(str, constant=True)
    def appVersion(self) -> str:
        from . import __version__

        return __version__

    @Property(str, constant=True)
    def accent(self) -> str:
        return str(self._config.get("app.accent", "#4CC2FF"))

    @Property(str, constant=True)
    def uiDir(self) -> str:
        return str(UI_DIR)

    @Property(bool, constant=True)
    def devWatermark(self) -> bool:
        """开发中水印开关（``app.dev_watermark``）。

        给开发者看的开关：只在**调试窗口**里出现，而调试窗口本身没有可见入口
        （设置窗口标题连点 10 次，见 ``openDebugWindow``）。缺省开启。
        """
        return self._config.get("app.dev_watermark", True) is not False

    @Property(str, constant=True)
    def devCodename(self) -> str:
        return str(self._config.get("app.codename", "AwaSubaru"))

    @Property(str, constant=True)
    def appChannel(self) -> str:
        """发布渠道（``app.channel``）：设置页「关于」的徽章只显示 ``Dev`` /
        ``Release`` 这两档，正式包把配置改成 ``"Release"`` 即可。"""
        return str(self._config.get("app.channel", "Dev"))

    # ================================================================ 启动画面

    @Property(float, notify=splashChanged)
    def splashProgress(self) -> float:
        """启动进度，0..1。"""
        return self._splash_progress

    @Property(str, notify=splashChanged)
    def splashStage(self) -> str:
        """当前阶段的短说明（设计稿里是「创建托盘图标」那一类）。"""
        return self._splash_stage

    @Property(str, constant=True)
    def splashSubtitle(self) -> str:
        """版本行文案：``<版本号> // <开发代号>``（设计稿同款）。"""
        return f"{self.appVersion} // {self.devCodename}"

    @Slot(float, str)
    def setSplashStage(self, progress: float, stage: str) -> None:
        """推进启动画面（应用层每到一个真实里程碑调一次）。"""
        self._splash_progress = max(0.0, min(1.0, float(progress)))
        self._splash_stage = str(stage)
        self.splashChanged.emit()

    @Property(str, constant=True)
    def deviceId(self) -> str:
        """本机短 ID（水印第二行用）：主机名 + MAC 的 SHA1 前 8 位。

        只用于开发者分辨「这是哪台测试机」，不含任何可逆的个人信息。
        """
        import hashlib
        import platform
        import uuid

        raw = f"{platform.node()}|{uuid.getnode():x}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8].upper()

    @Slot(str, result=str)
    def resourceFile(self, name: str) -> str:
        """``resources/`` 下某个品牌资源（logo.svg / logo.ico / banner.png）的
        ``file:///`` URL。

        QML 的 ``Image.source`` 不吃相对路径（基准是 QML 文件所在目录），
        所以统一在这里拼绝对 URL。
        """
        return QUrl.fromLocalFile(str(RESOURCES_DIR / name)).toString()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        """把一段文本放进系统剪贴板（回声洞的「复制」与诊断的「复制全部」共用）。"""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(text))

    # ================================================================ 回声洞

    #: 取句结果：``(句子, 状态)``，状态 ∈ ``ok`` / ``empty``。
    #:
    #: 为什么是**信号**而不是 ``@Slot(result=str)``：取句可能要走一次本地
    #: HTTP（见 ``echo_cave.py``），在槽里同步等会把 UI 线程按住 —— 这正是
    #: L1 用 ``await fetch()`` 避免的事。改成后台线程取、取完发信号，界面
    #: 期间能正常画出「获取中...」。
    echoCaveResult = Signal(str, str)

    @Slot()
    def requestEchoCave(self) -> None:
        """请求一条回声洞句子（异步）。

        ⚠️ **重复点击直接忽略**：句子很短，一次取句通常几十毫秒就回来了；
        真放行并发请求的话，晚回来的那个会盖掉用户刚看到的那句（L1 用
        ``echoCaveAbort`` 取消前一次动画，这里更简单 —— 干脆不并发）。
        """
        if self._echo_thread is not None and self._echo_thread.is_alive():
            return
        self._echo_thread = threading.Thread(
            target=self._fetch_echo_cave, name="echo-cave", daemon=True
        )
        self._echo_thread.start()

    def _fetch_echo_cave(self) -> None:
        """后台线程体：取句 → 发信号（在 Qt 里跨线程发信号会被排队到主线程）。"""
        from .echo_cave import fetch_sentence

        try:
            sentence = fetch_sentence()
        except Exception:  # noqa: BLE001 - 取句失败不该把线程带崩
            log.exception("回声洞取句失败")
            sentence = ""
        self.echoCaveResult.emit(sentence, "ok" if sentence else "empty")

    # ================================================================ 诊断信息

    #: 诊断字段就绪：``QVariantList``，每项 ``{"key": ..., "value": ...}``。
    #:
    #: 同样走**信号**而不是同步返回：硬件查询里有 ``GlobalMemoryStatusEx``
    #: 与注册表遍历，虽然都不起子进程，但没有理由压在 UI 线程上；更重要的是
    #: 同步返回的话界面根本没机会画出「加载中...」——L1 那个加载态正是这么来的。
    diagnosticsReady = Signal("QVariantList")

    @Slot()
    def requestDiagnostics(self) -> None:
        """采集诊断信息（异步）。重复请求同样直接忽略。

        ⚠️ **活体字段在这里先取好再交给线程**：``QGuiApplication.primaryScreen()``
        不是线程安全的，不能在 worker 里调（见 :meth:`_live_diagnostic_fields`）。
        """
        if self._diagnostics_thread is not None and self._diagnostics_thread.is_alive():
            return
        extra = self._live_diagnostic_fields()
        self._diagnostics_thread = threading.Thread(
            target=self._collect_diagnostics, args=(extra,), name="diagnostics", daemon=True
        )
        self._diagnostics_thread.start()

    def _live_diagnostic_fields(self) -> Dict[str, str]:
        """只有活体对象才拿得到的字段（屏幕 / 放映状态 / 日志级别 / 版本号）。

        ⚠️ 必须在**主线程**调用：``QGuiApplication.primaryScreen()`` 不是线程安全的。

        键名照 ClassIsland 的诊断字段（``AppSubChannel`` 对应它的发布渠道），
        与 ``app/diagnostics.py::FIELD_ORDER`` 里的键一一对上。
        """
        screen = QGuiApplication.primaryScreen()
        screen_size = ""
        if screen is not None:
            geometry = screen.geometry()
            screen_size = f"{geometry.width()} × {geometry.height()}"

        presentation = "active" if self._presentation_active else "inactive"
        if self._presentation_active:
            presentation = f"active:{self._slide_index}/{self._slide_total}"

        return {
            "Screen": screen_size,
            "AppVersion": self.appVersion,
            "AppSubChannel": self.appChannel,
            "Presentation": presentation,
            "LogLevel": str(self._config.get("app.log_level", "INFO")),
        }

    def _collect_diagnostics(self, extra: Dict[str, str]) -> None:
        """后台线程体：采集 → 发信号（``extra`` 由主线程预先取好）。"""
        from .diagnostics import collect

        try:
            fields = [{"key": key, "value": value} for key, value in collect(extra)]
        except Exception:  # noqa: BLE001 - 采集失败也要给界面一个交代
            log.exception("诊断信息采集失败")
            fields = []
        self.diagnosticsReady.emit(fields)

    # ================================================================ 放映状态

    def _get_presentation_active(self) -> bool:
        return self._presentation_active

    presentationActive = Property(
        bool, _get_presentation_active, notify=presentationActiveChanged
    )

    def _get_slide_index(self) -> int:
        return self._slide_index

    slideIndex = Property(int, _get_slide_index, notify=slideChanged)

    def _get_slide_total(self) -> int:
        return self._slide_total

    slideTotal = Property(int, _get_slide_total, notify=slideChanged)

    def _get_active_tool(self) -> str:
        return self._active_tool

    activeTool = Property(str, _get_active_tool, notify=activeToolChanged)

    def _get_pen_color(self) -> str:
        return self._pen_color

    #: 当前墨迹颜色（``#RRGGBB``，空串 = 还没选过）。
    #:
    #: ⚠️ 必须是 ``@Property`` 而不是 ``@Slot``：QML 侧把后端的 ``@Slot`` 当
    #: **属性**读**永远不报错**，拿到的是函数的形参个数（0）—— 症状是静默走
    #: 降级分支，这个坑本项目在 ``licenseText`` 上踩过一次。
    penColor = Property(str, _get_pen_color, notify=penColorChanged)

    def _get_status_text(self) -> str:
        return self._status_text

    statusText = Property(str, _get_status_text, notify=statusChanged)

    def apply_state(self, state: PresentationState) -> None:
        """由 :class:`PptController` 调用。"""
        if state.active != self._presentation_active:
            self._presentation_active = state.active
            self.presentationActiveChanged.emit()

        if (state.slide_index, state.slide_total) != (
            self._slide_index,
            self._slide_total,
        ):
            self._slide_index = state.slide_index
            self._slide_total = state.slide_total
            self.slideChanged.emit()

    def set_status_text(self, text: str) -> None:
        if text != self._status_text:
            self._status_text = text
            self.statusChanged.emit()

    # ================================================================== 配置块

    def _get_presentation_config(self) -> Dict[str, Any]:
        """``presentation`` 配置的**深拷贝** + 插件控制条贡献的读取侧合并。

        合并规则（2026-10-05 插件系统 Wave 2 任务 6，理由见文件头注释）：

        * ``tools`` / ``actions`` = config 内建数组在前，registry 的
          ``dock_tools()`` / ``dock_actions()`` 插件条目追加在后；
        * id 冲突时**内建胜出**并记 warning（与磁贴目录同款让位规则）；
        * 先 ``deepcopy`` 再合并 —— ``Config.get`` 返回的是内部引用，直接
          append 会污染配置内存态（铁律：插件贡献不落盘也不进 config
          内存态）；每次读取重新合并，天然不会重复追加。
        """
        merged = copy.deepcopy(self._config.get("presentation", {}) or {})
        for key, extra in (
            ("tools", registry.dock_tools()),
            ("actions", registry.dock_actions()),
        ):
            entries = list(merged.get(key, []) or [])
            builtin_ids = {str(item.get("id")) for item in entries}
            for entry in extra.values():
                entry_id = str(entry.get("id"))
                if entry_id in builtin_ids:
                    log.warning("插件控制条贡献 id 与内建冲突，内建胜出: %s", entry_id)
                    continue
                entries.append(dict(entry))
            merged[key] = entries
        return merged

    presentationConfig = Property(
        "QVariantMap",
        _get_presentation_config,
        notify=presentationConfigChanged,
    )

    def _get_presentation_groups(self) -> List[Dict[str, Any]]:
        """编辑器分组注册表的 QML 列表视图（2026-10-05 插件系统 Wave 2 任务 9）。

        把 ``registry.editor_groups()`` 的 ``{组名: 条目}`` 拍平成
        ``[{name, display_name, icon, dock_qml?, traits, inspector_items}, ...]``，
        主界面编辑器的组件名 / 图标 / 语义判定全部从这里读 —— 组名硬编码
        if 链已随本任务移除，注册表是唯一事实来源。

        每条深拷一层（traits / inspector_items 也拷）：注册表返回的只读视图
        只是浅快照，直接递给 QML 等于共享引用；编辑器只读，但桥接侧不给
        消费方留下「改列表项会污染注册表」的机会。
        """
        view: List[Dict[str, Any]] = []
        for name, entry in registry.editor_groups().items():
            item = {
                "name": name,
                "display_name": str(entry.get("display_name", name)),
                "icon": str(entry.get("icon", "")),
                "traits": copy.deepcopy(entry.get("traits") or {}),
                "inspector_items": copy.deepcopy(entry.get("inspector_items") or []),
            }
            dock_qml = entry.get("dock_qml")
            if dock_qml:
                item["dock_qml"] = str(dock_qml)
            view.append(item)
        return view

    presentationGroups = Property(
        "QVariantList",
        _get_presentation_groups,
        notify=presentationGroupsChanged,
    )

    # ------------------------------------------------- 放映显示器几何（画布基准）

    def _get_presentation_screen(self) -> Dict[str, Any]:
        """放映所在显示器的**逻辑**几何 —— 主界面编辑器画布的坐标基准。

        优先用 :meth:`syncPresentationScreen` 推来的真实结果（放映窗口在哪块屏
        就报哪块）；还没放映过时退回「配置索引 → 主屏」，与
        ``windows.py::_presentation_screen`` 的兜底分支同源。

        ⚠️ 不能用 QML 的 ``Screen`` attached property 代替：那说的是**本窗口**
        所在显示器。双屏时编辑器在主屏、放映在副屏，画布比例会整个错掉。
        """
        if self._overlay_screen is not None:
            return dict(self._overlay_screen)
        try:
            screens = QGuiApplication.screens()
        except Exception:  # pragma: no cover - QApplication 尚未建好
            screens = []
        index = int(self._config.get("presentation.screen_index", -1))
        screen = screens[index] if 0 <= index < len(screens) else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:  # pragma: no cover - 极端情况（无显示器）
            return {"width": 1920, "height": 1080, "name": "",
                    "scale": 1.0, "source": "fallback"}
        geometry = screen.geometry()
        return {
            "width": geometry.width(),
            "height": geometry.height(),
            "name": screen.name(),
            "scale": float(screen.devicePixelRatio()),
            "source": "config",
        }

    presentationScreen = Property(
        "QVariantMap", _get_presentation_screen, notify=presentationScreenChanged
    )

    @Slot(int, int, str, float)
    def syncPresentationScreen(
        self, width: int, height: int, name: str, scale: float
    ) -> None:
        """由 ``WindowManager.show_docks()`` 调用：顶层窗口定位完，把真实屏幕推过来。

        顶层窗口铺在哪块屏是按**放映窗口的物理显示器**判定的（见
        ``windows.py::_presentation_screen``），Bridge 侧复现不了，所以只能推。
        """
        info = {
            "width": int(width),
            "height": int(height),
            "name": str(name),
            "scale": float(scale),
            "source": "overlay",
        }
        if info == self._overlay_screen:
            return
        self._overlay_screen = info
        self.presentationScreenChanged.emit()

    def _get_quick_panel_config(self) -> Dict[str, Any]:
        return self._config.get("quick_panel", {}) or {}

    quickPanelConfig = Property(
        "QVariantMap",
        _get_quick_panel_config,
        notify=quickPanelConfigChanged,
    )

    # ============================================================ 快捷方式清单

    def _catalog(self) -> List[Dict[str, Any]]:
        """全部可用的快捷方式：config 内建目录 ∪ registry 插件磁贴（读取侧纯拼接）。

        合并规则（2026-10-05 插件系统 Wave 2 任务 5）：

        * 插件条目追加在内建之后 —— 面板「+」浮层里插件磁贴自然排在后面；
        * id 冲突时**内建胜出**并记 warning（插件让位，防插件顶掉内建行为）；
        * 合并是纯读取侧拼接，**绝不写回 config**（铁律，见文件头注释）。

        合并必须发生在这一处：``_resolve_shortcuts`` 会静默丢弃目录外的 id，
        在别处合并的插件条目到不了面板。``setShortcutEnabled`` /
        ``activateShortcut`` 的 id 校验走的也是这里，插件 id 天然被认。
        """
        merged = list(self._config.get("quick_panel.shortcut_catalog", []) or [])
        builtin_ids = {str(item.get("id")) for item in merged}
        for entry in registry.shortcuts().values():
            tile_id = str(entry.get("id"))
            if tile_id in builtin_ids:
                log.warning("插件磁贴 id 与内建冲突，内建胜出: %s", tile_id)
                continue
            merged.append(dict(entry))
        return merged

    def shortcut_action(self, shortcut_id: str) -> str:
        """按 id 在**合并后**的目录里查动作串；未命中返回空串。

        应用层（``application.py::_on_shortcut``）专用：目录双来源之后，
        应用层不能再只翻 config，否则插件磁贴的动作永远查不到。
        """
        for item in self._catalog():
            if str(item.get("id")) == shortcut_id:
                return str(item.get("action", ""))
        return ""

    def _resolve_shortcuts(self, ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """把 id 列表解析成目录里的完整条目；未知 id 直接丢弃。"""
        wanted = self._shortcut_ids if ids is None else ids
        by_id = {str(item.get("id")): item for item in self._catalog()}
        return [by_id[item_id] for item_id in wanted if item_id in by_id]

    def _get_shortcut_items(self) -> List[Dict[str, Any]]:
        return self._resolve_shortcuts()

    shortcutItems = Property(
        "QVariantList", _get_shortcut_items, notify=shortcutsChanged
    )

    def _get_available_shortcut_items(self) -> List[Dict[str, Any]]:
        enabled = set(self._shortcut_ids)
        return [item for item in self._catalog() if str(item.get("id")) not in enabled]

    availableShortcutItems = Property(
        "QVariantList", _get_available_shortcut_items, notify=shortcutsChanged
    )

    def _persist_shortcuts(self) -> None:
        self._config.set("quick_panel.shortcuts", list(self._shortcut_ids))
        self.shortcutsChanged.emit()

    @Slot(str, bool)
    def setShortcutEnabled(self, shortcut_id: str, enabled: bool) -> None:
        """快捷方式的启用开关；面板上的「添加 / 移除」都走这里。"""
        exists = any(str(item.get("id")) == shortcut_id for item in self._catalog())
        if not exists:
            log.info("未知快捷方式: %s", shortcut_id)
            return
        if enabled:
            if shortcut_id in self._shortcut_ids:
                return
            self._shortcut_ids.append(shortcut_id)
        else:
            if shortcut_id not in self._shortcut_ids:
                return
            self._shortcut_ids.remove(shortcut_id)
        self._persist_shortcuts()

    @Slot(str, int)
    def moveShortcut(self, shortcut_id: str, index: int) -> None:
        """把快捷方式拖到新位置（``index`` 来自网格的 visualIndex）。"""
        if shortcut_id not in self._shortcut_ids:
            return
        target = max(0, min(int(index), len(self._shortcut_ids) - 1))
        current = self._shortcut_ids.index(shortcut_id)
        if current == target:
            return
        self._shortcut_ids.pop(current)
        self._shortcut_ids.insert(target, shortcut_id)
        self._persist_shortcuts()

    # ================================================================== 设置

    def _setting_paths(self) -> Dict[str, str]:
        """内建 ``SETTING_PATHS`` ∪ 动态注册的合成视图（内建优先）。"""
        return {**self._dynamic_paths, **SETTING_PATHS}

    def register_setting_path(
        self,
        key: str,
        path: str,
        notify: Optional[str] = None,
        side_effect: Optional[SettingSideEffect] = None,
    ) -> bool:
        """动态注册一个设置项（插件用）。

        :param key: 扁平键（QML 侧 ``Backend.settings.<key>`` 读、
            ``Backend.setSetting("<key>", 值)`` 写）。插件键命名约定
            ``plugins_<id>_<name>``，避免撞内建键与 ``presentation_`` 前缀广播。
        :param path: 配置里的点号路径（如 ``plugins._t.volume``）。
        :param notify: 值变更时额外发的信号名字符串（无参，如
            ``"presentationConfigChanged"``）；None 则只发 ``settingsChanged``。
        :param side_effect: 可选回调 ``(config, key, value)``，在改完内存、
            排好延迟落盘之后、发信号之前调用。
        :return: 注册是否成功（与内建键冲突或参数为空会被拒绝并记日志）。
        """
        if not key or not path:
            log.warning("动态注册设置项被拒绝（键或路径为空）: %r -> %r", key, path)
            return False
        if key in SETTING_PATHS:
            log.warning("动态注册与内建设置项冲突，已忽略: %s", key)
            return False
        self._dynamic_paths[key] = path
        if notify is not None or side_effect is not None:
            self._key_effects[key] = {
                "signals": [(notify, False)] if notify else [],
                "side_effect": side_effect,
            }
        log.info("动态注册设置项: %s -> %s", key, path)
        return True

    def _get_settings(self) -> Dict[str, Any]:
        values = {
            key: self._config.get(path)
            for key, path in self._setting_paths().items()
        }
        # 「开机自启」的真相在**注册表**里，不在配置里：用户可能在「任务管理器 →
        # 启动」里禁用它，也可能手动删过那个注册表值 —— 配置里那份影子会骗人。
        # 所以每次都回读一次实际状态（注册表读取是微秒级的，代价可以忽略）。
        values["autostart"] = autostart.is_enabled()
        return values

    settings = Property("QVariantMap", _get_settings, notify=settingsChanged)

    def _get_settings_config(self) -> Dict[str, Any]:
        return self._config.get("settings", {}) or {}

    settingsConfig = Property(
        "QVariantMap", _get_settings_config, notify=settingsChanged
    )

    def _get_settings_nav_items(self) -> List[Dict[str, Any]]:
        """设置窗口左侧导航的数据源（2026-10-05 插件系统 Wave 2 任务 7）。

        = 内建条目（``_BUILTIN_SETTINGS_NAV``，原 QML 硬编码列表逐字搬入）
        ∪ 插件设置页（``registry.settings_pages()``）追加在后。

        * 标题经 ``app.i18n.tr`` 标注：内建项的 context 沿用原 QML 侧的
          ``Settings``（译文已同步进 ``translations/luminalium_py_*.ts``，
          Python 侧 ts 手工维护、lupdate 不碰）；插件条目注册时应自带
          翻译好的 ``title``（约定：插件自己的 ``tr(<插件 id>, ...)``），
          这里原样透传。
        * ``page`` 全部是 **file:/// 绝对 URL**（原因见
          ``_BUILTIN_SETTINGS_NAV`` 的注释）；插件侧给的 ``page_url`` 键名
          在这里映射成 QML 侧的 ``page``（两键名的语义区分见
          ``app/plugins/registry.py`` 头注释第 4 条）。
        * ``position`` 是 RinUI ``Position`` 枚举的**整数值**（经 QVariant
          到 QML 后与 ``Rin.Position.Bottom`` 严格相等）；普通条目不写这个
          键，QML 侧读为 ``undefined``，落入普通区。「关于 / 更新」钉底部
          的语义由表里的 ``_RIN_POSITION_BOTTOM`` 原样保留。
        * 每次读取现算（注册表在加载期冻结，读到的必是全量），且合并结果
          **绝不写回 config**（列表型贡献注入默认层会被用户层整体顶掉 ——
          铁律，见文件头注释与 ``app/plugins/registry.py`` 头注释第 3 条）。
        """
        items: List[Dict[str, Any]] = []
        for rel, title_source, icon, position in _BUILTIN_SETTINGS_NAV:
            item: Dict[str, Any] = {
                "title": i18n.tr("Settings", title_source),
                "page": "file:///" + (UI_DIR / rel).as_posix(),
                "icon": icon,
            }
            if position is not None:
                item["position"] = position
            items.append(item)
        for entry in registry.settings_pages().values():
            plugin_item: Dict[str, Any] = {
                "title": str(entry.get("title", "")),
                "page": str(entry.get("page_url", "")),
                "icon": str(entry.get("icon", "")),
            }
            if "position" in entry:
                plugin_item["position"] = entry["position"]
            items.append(plugin_item)
        return items

    settingsNavItems = Property(
        "QVariantList",
        _get_settings_nav_items,
        notify=settingsNavItemsChanged,
    )

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        """改一项设置。类型按默认值对齐，避免 QML 把 int 传成字符串。"""
        path = self._setting_paths().get(key)
        if path is None:
            log.info("未知设置项: %s", key)
            return

        # 开机自启：**本体是注册表**，单独走一条路。通用的「改内存 + 延迟落盘」
        # 会把「写注册表失败」这件事吞掉 —— 那正是「关了却没关掉」的来源。
        if key == "autostart":
            self._apply_autostart(bool(value))
            return

        current = self._config.get(path)
        if isinstance(current, bool):
            value = bool(value)
        elif isinstance(current, int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return
        elif isinstance(current, float):
            try:
                value = float(value)
            except (TypeError, ValueError):
                return

        if current == value:
            return
        # 只改内存 + 排一次延迟落盘（理由见 ``_save_timer`` 处的注释）。
        self._config.set(path, value, persist=False)
        self._save_timer.start()
        log.info("设置 %s = %r", path, value)

        # 副作用两级查找（注册表驱动，不再是硬编码 if/elif）：
        # ① 键级回调表（精确命中，side_effect 先于信号 —— 翻页位置得先把
        #    corners 改完再喊重建）；② 前缀 / 集合规则表。
        effect = self._key_effects.get(key)
        if effect is not None:
            side_effect: Optional[SettingSideEffect] = effect.get("side_effect")
            if side_effect is not None:
                side_effect(self._config, key, value)
            for signal_name, pass_value in effect["signals"]:
                self._emit_setting_signal(signal_name, value, pass_value)
        if key in _BROADCAST_KEYS:
            self.quickPanelConfigChanged.emit()
        for prefix, signal_specs in _PREFIX_NOTIFY_RULES:
            if key.startswith(prefix):
                for signal_name, pass_value in signal_specs:
                    self._emit_setting_signal(signal_name, value, pass_value)
                break
        self.settingsChanged.emit()

    def _emit_setting_signal(self, signal_name: str, value: Any, pass_value: bool) -> None:
        """按名字发设置类信号；``pass_value`` 为真时带 ``str(值)`` 作为参数。

        按名字查是为了让注册表（内建键级表 / 前缀规则 / 动态注册）不用持有
        Backend 就能声明「改完发什么」；名字打错时记警告而不是静默吞掉。
        """
        signal = getattr(self, signal_name, None)
        if signal is None:
            log.warning("注册的通知信号不存在: %s", signal_name)
            return
        if pass_value:
            signal.emit(str(value))
        else:
            signal.emit()

    def _apply_pager_position(self, position: str) -> None:
        """把「翻页组件位置」落到 ``corners`` 那四个角的开关上。

        ``side`` → 启用 ``middle_left`` / ``middle_right``（竖版两侧中间）、
        关掉底部两只；``bottom`` → 反过来。

        ⚠️ 真实生效的是 ``corners``（``windows.py::_load_docks`` 与编辑器预览
        都只读它），``pager.position`` 只是它的人话开关 —— 两边必须一起改，
        否则「设置里选了横版、屏幕上还是竖版」。
        """
        enabled = PAGER_POSITION_CORNERS.get(position)
        if enabled is None:
            log.info("未知翻页组件位置: %s", position)
            return
        for corners in PAGER_POSITION_CORNERS.values():
            for corner in corners:
                self._config.set(
                    f"presentation.corners.{corner}.enabled", corner in enabled
                )

    def _apply_autostart(self, enabled: bool) -> None:
        """开关开机自启：写注册表 → **回读真实状态** → 同步影子配置 → 广播。

        ⚠️ 回读是关键，不是多余的稳妥：``set_enabled`` 返回成功只说明注册表调用
        没抛异常，不代表最终状态就是想要的（组策略 / 杀软可能半途拦下）。所以以
        ``is_enabled()`` 的回读结果为准 —— 真实状态与用户点的那个不一致时，写进
        影子配置的是**真实状态**，QML 侧的开关跟着弹回去，而不是停在用户点的那
        一格骗人。这就是「关闭也必须有效无误」的落点。
        """
        ok = autostart.set_enabled(enabled)
        actual = autostart.is_enabled()
        self._config.set("app.autostart", actual, persist=False)
        self._save_timer.start()
        if not ok or actual != enabled:
            log.warning("开机自启未能按预期设置：期望 %s，实际 %s", enabled, actual)
        self.settingsChanged.emit()

    @Slot()
    def refreshSettings(self) -> None:
        """让 QML 重新取一遍 ``settings``（``settings`` 里含实时状态，如注册表）。

        入口是 ``windows.py::show_settings`` —— 每次打开设置窗口都刷一次，这样
        「在任务管理器里禁用了开机自启、再打开设置」看到的就是关着的那一格。
        """
        self.settingsChanged.emit()

    @Slot()
    def closeSettings(self) -> None:
        self.settingsCloseRequested.emit()

    @Slot()
    def openDebugWindow(self) -> None:
        """打开调试窗口。

        入口是**隐藏**的：在设置窗口左上角的标题文本上连点 10 次
        （``Settings.qml`` 的 ``debugTitleHotspot``）。调试项不再占用
        设置导航栏的位置。
        """
        self.debugWindowRequested.emit()

    @Slot()
    def closeDebugWindow(self) -> None:
        self.debugWindowCloseRequested.emit()

    @Slot()
    def openMainEditor(self) -> None:
        """打开主界面编辑器窗口。

        与调试窗口不同，这个是**正经入口**：快捷面板的「主界面编辑器」快捷方式
        （``shortcut_catalog`` 里 ``action: "open_editor"``）会派发到这里。
        """
        self.editorRequested.emit()

    @Slot()
    def closeMainEditor(self) -> None:
        self.editorCloseRequested.emit()

    def reload_from_config(self) -> None:
        self._shortcut_ids = [
            str(item) for item in (self._config.get("quick_panel.shortcuts", []) or [])
        ]
        self.shortcutsChanged.emit()
        self.settingsChanged.emit()
        self.presentationConfigChanged.emit()
        self.presentationScreenChanged.emit()
        self.quickPanelConfigChanged.emit()

    # ============================================================ 放映控制槽

    @Slot(str)
    def selectTool(self, tool: str) -> None:
        """切换放映指针：``pen`` / ``eraser`` / ``arrow``；``plugin:`` 前缀走动作通道。"""
        # ``plugin:`` 前缀的工具 id 来自插件（registry.add_dock_tool，2026-10-05
        # 任务 6）：不进白名单校验、不调 ``ppt.set_tool``（与 COM 零接触），改按
        # 动作处理 —— 经 ``actionTriggered`` 走应用层 ``_on_action`` 的 ``plugin:``
        # 特权通道，由动词注册表分发给插件处理器。
        if tool.startswith("plugin:"):
            self.actionTriggered.emit(tool)
            return
        if tool not in ("pen", "eraser", "arrow"):
            return
        if tool != self._active_tool:
            self._active_tool = tool
            self.activeToolChanged.emit()
        self.actionTriggered.emit(f"tool:{tool}")

    @Slot(str)
    def setPenColor(self, color: str) -> None:
        """选墨迹颜色（笔选单里点一格）。

        ``color`` 是 ``#RRGGBB``（可带 alpha，``#AARRGGBB`` 也认，取后六位）。
        先落进本对象（QML 靠它回显选中格），再经 ``actionTriggered`` 交给
        应用层调 PowerPoint 的 ``View.PointerColor``。

        ⚠️ 非法串**直接丢弃**且不改状态：选单里的格子全来自配置，正常不会
        走到这儿，但这里是 QML 能直接调到的公开槽，别让它把 ``penColor``
        写成半截的垃圾值（回显会跟着错）。
        """
        value = str(color or "").strip().lstrip("#").upper()
        if len(value) == 8:  # #AARRGGBB → 取 RGB
            value = value[2:]
        if len(value) != 6 or any(c not in "0123456789ABCDEF" for c in value):
            log.warning("忽略非法的墨迹颜色: %r", color)
            return
        hex_color = "#" + value
        if hex_color != self._pen_color:
            self._pen_color = hex_color
            self.penColorChanged.emit()
        self.actionTriggered.emit(f"pen_color:{hex_color}")

    @Slot(str)
    def triggerAction(self, action_id: str) -> None:
        """面板上的通用动作（清屏等），由应用层分发到 PowerPoint 控制器。"""
        self.actionTriggered.emit(action_id)

    @Slot()
    def nextSlide(self) -> None:
        self.actionTriggered.emit("pager:next")

    @Slot()
    def previousSlide(self) -> None:
        self.actionTriggered.emit("pager:previous")

    @Slot()
    def exitPresentation(self) -> None:
        self.actionTriggered.emit("exit_presentation")

    # ================================================================ 面板交互

    @Slot(str, result=bool)
    def activateShortcut(self, shortcut_id: str) -> bool:
        """触发快捷方式。

        返回是否被受理 —— 面板用它决定要不要顺手收起（CW2 的
        ``executeShortcut`` 也是这个约定）。
        """
        known = any(str(item.get("id")) == shortcut_id for item in self._catalog())
        if not known:
            log.info("未注册的快捷方式: %s", shortcut_id)
            return False
        self.shortcutTriggered.emit(shortcut_id)
        return True

    @Slot()
    def requestSettings(self) -> None:
        self.settingsRequested.emit()

    @Slot()
    def requestRestart(self) -> None:
        self.restartRequested.emit()

    @Slot()
    def requestQuit(self) -> None:
        self.quitRequested.emit()

    @Slot()
    def hidePanel(self) -> None:
        self.panelHideRequested.emit()

    # ------------------------------------------------------------------ 工具
