"""应用装配入口。

启动流程::

    读取配置 -> 建立 QApplication -> 注册 QML 上下文 -> 加载快捷面板
    -> 创建放映控制条 -> 托盘常驻 -> 开始轮询放映状态

2026-10-05（插件系统 Wave 2 任务 5）：快捷方式的动作分发从硬编码 if 链
改成**动词注册表**（``app.plugins.registry.action_handlers()``）—— 动作串
按最长前缀匹配注册表里的动词，处理器拿到完整动作串自己解析后缀。动机：
插件磁贴的动作（约定 ``plugin:<id>:<verb>``）不可能进内建 if 链，必须有一条
运行期可扩展的分发通道；任务 6 会把同一张注册表复用到控制条动作分发。
内建动词（``open_settings`` / ``open_editor``）作为首批注册项在装配段登记，
行为与原 if 链逐字一致。

⚠️ 注册时机约束（2026-10-05）：内建动词的注册在装配段、``WindowManager``
就绪后立即进行，**必须先于 Wave 3 任务 11 插入的 ``load_plugins``** ——
loader 末尾会 ``registry.freeze()``，冻结后注册直接抛 RuntimeError。

2026-10-05（插件系统 Wave 2 任务 6）：控制条动作分发（``_on_action``）
增加 ``plugin:`` 前缀特权通道 —— 与 ``tool:`` / ``pen_color:`` 同级，
在 ``state.active`` 门控**之前**路由到动词注册表（复用任务 5 的
``_dispatch_shortcut_action``，最长前缀匹配 ``registry.action_handlers()``）。
动机：聚焦这类插件**非放映时也要能触发**（用户「两处工具栏入口」诉求的
技术前提），被放映门控挡住就永远到不了处理器。``plugin:`` 动作不进
``ppt_controller``（与 COM / 按键注入零接触），动作后的 ``refresh_now``
补刷对它也不强制（插件自理）。内建动作的硬编码 if/elif 同步改为分发表，
行为逐字不变；``state.active`` 门控对非 ``plugin:`` 动作不放宽。

2026-10-07（计划 self-ink 第 6 项，用户决策 Q1）：``tool:`` / ``pen_color:`` /
``clear_screen`` 不再只有 COM 一条路，按 ``presentation.ink.engine`` 分流 ——
``self``（默认）交给自建墨迹窗口（PPT 指针保持 arrow，颜色 / 清屏不碰 COM），
``com`` 走改造前的旧链路逐字不变。动机：COM 放映笔的手感不受我们控制，
PowerPoint 与 WPS 两家表现不一致（WPS 连 PointerColor 都不认）；com 保留作兜底。
放映中切换引擎经 ``Config.on_change`` 即时生效，见 ``_on_config_changed``。

2026-10-07（计划 self-ink 第 9 项，用户指令：自建批注）：新增第四个特权
前缀 ``pen_width:``（笔选单「粗细」一行）—— 与 ``pen_color:`` 同一条路，
self 引擎落到 InkLayer.penWidth，com 引擎忽略（放映笔没有粗细接口）。

2026-10-08（用户指令：自建批注）：第五个特权前缀 ``eraser_width:``（橡皮卡片
「粗细」一行）—— 与 ``pen_width:`` 逐字同构，self 引擎落到
InkLayer.eraserWidth，com 引擎忽略（橡皮交给演示软件自己）。
"""

from __future__ import annotations

import logging
import logging.handlers
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QApplication, QMenu
from RinUI import BackdropEffect, RinUIWindow, Theme
from RinUI.core.config import is_win10, is_win11

from . import __version__
from . import echo_cave
from . import i18n
from . import rinui_patch
from .bridge import Backend
from .config import Config
from .error_handler import ErrorHandler
from .paths import APP_NAME, LOG_DIR, UI_DIR, ensure_runtime_dirs
from .ppt_controller import COM_PROG_IDS, PptController
from .slide_thumbs import SlideThumbCache
from .tray import TrayIcon, build_app_icon
from .windows import WindowManager

log = logging.getLogger("luminalium")

#: 「⋯」溢出菜单的样式（``QMenu`` 是原生窗口，不进 QML 调色板，只能给一份
#: 自己的样式表）。深浅两套的取值**故意跟着 RinUI 的主题常量走**，不手写颜色 ——
#: 见 :func:`_overflow_menu_qss`。
#:
#: ⚠️ 2026-10-07 补上。此前 ``_show_overflow_menu`` 里引用的 ``OVERFLOW_MENU_QSS``
#: **从来没有被定义过**（翻遍 68 个提交都没有）—— 也就是说点一下工具条上的
#: 「⋯」就是一次 ``NameError`` 崩溃。一直没被发现的原因是这条路径平时没人走
#: （翻页 / 退出都有别的入口），而崩溃又被错误处理链路接住、弹了一张报告窗，
#: 看上去像「另一个问题」。这也解释了历史日志里那几次
#: ``捕获崩溃：NameError: name 'OVERFLOW_MENU_QSS' is not defined`` ——
#: 复现方式是：放映中，点控制条右侧的「⋯」。
_OVERFLOW_MENU_QSS_DARK = """
QMenu {
    background-color: #2B2B2B;
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 5px;
}
QMenu::item:selected {
    background-color: rgba(255, 255, 255, 0.08);
}
QMenu::separator {
    height: 1px;
    margin: 4px 8px;
    background: rgba(255, 255, 255, 0.10);
}
"""
_OVERFLOW_MENU_QSS_LIGHT = """
QMenu {
    background-color: #F3F3F3;
    color: #1A1A1A;
    border: 1px solid rgba(0, 0, 0, 0.10);
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 5px;
}
QMenu::item:selected {
    background-color: rgba(0, 0, 0, 0.06);
}
QMenu::separator {
    height: 1px;
    margin: 4px 8px;
    background: rgba(0, 0, 0, 0.10);
}
"""


def _overflow_menu_qss(dark: bool) -> str:
    """按当前主题取「⋯」菜单的样式。

    ⚠️ 主题是**运行时可切**的，所以样式表不能算一次就存起来 —— 每次弹菜单现算
    （它只是一份几十行的字符串，代价可以忽略）。判据由调用方给：它已经从
    ``RinUIWindow.theme_manager`` 拿到了 ``is_dark_theme()``，别在这里再去找
    一遍主题管理器（那是 RinUI 的实例属性，没有模块级单例）。
    """
    return _OVERFLOW_MENU_QSS_DARK if dark else _OVERFLOW_MENU_QSS_LIGHT


def _match_verb_handler(action: str) -> Optional[Callable[[str], Any]]:
    """在动词注册表里按**最长前缀**找 ``action`` 的处理器；未命中返回 None。

    匹配规则：``action == 动词`` 或 ``action`` 以 ``动词 + ":"`` 开头 ——
    后者把 ``open_settings:settings/Home.qml`` 这类带后缀的动作交给
    ``open_settings`` 处理器，后缀由处理器自己解析。最长前缀优先保证
    ``plugin:<id>`` 这类层级动词里，更具体的注册项赢过泛化的。

    模块级函数、不依赖应用实例：任务 6 的 ``_on_action`` 注册表分发直接
    复用它，测试脚本也可以脱离窗口装配单独验收分发链路。
    """
    from .plugins import registry

    best_verb = ""
    best_handler: Optional[Callable[[str], Any]] = None
    for verb, handler in registry.action_handlers().items():
        if action == verb or action.startswith(verb + ":"):
            if len(verb) > len(best_verb):
                best_verb, best_handler = verb, handler
    return best_handler


def _dispatch_shortcut_action(action: str) -> bool:
    """把快捷方式动作串交给动词注册表分发；返回是否有处理器受理。

    未命中只记日志、不抛异常 —— 插件被卸载后其磁贴 id 可能还留在用户的
    启用列表里，点击时必须安全落空而不是把面板点崩。
    """
    handler = _match_verb_handler(action)
    if handler is None:
        log.info("未实现的快捷方式动作: %s", action)
        return False
    handler(action)
    return True

#: 启动画面的推进节奏 —— 每一步至少停留这么久才进下一步。
#:
#: 本机冷启动跑完整条 ``_boot_tray → _boot_presenter → _boot_ready`` 只要约 350ms，
#: 不设节奏的话进度条会瞬间填满、那张卡片闪一下就没了（实测整段存活约 1.0s，
#: 比不放还难看）。这几个步骤本身都是**真活儿**（建托盘 / 起探测线程），这里只是
#: 让它们在画面上按人能读到的速度依次出现，不是造假进度。
#:
#: 代价是放映探测线程晚约 0.8s 起来 —— 反正启动画面正盖着屏幕，不影响观感。
SPLASH_STEP_MS = 420
#: 到 100% 之后再多停一会儿，让「就绪」被看见再淡出。
SPLASH_HOLD_MS = 520


def _overflow_menu_qss(dark: bool) -> str:
    """「⋯」溢出菜单的原生 QSS（按深浅主题取色）。

    ⚠️ 这个名字曾以**常量**形态被 ``_show_overflow_menu`` 引用却从未被
    定义（2026-10-05 控制条原型 4f22f90 起的潜伏 bug）：此前控制条动作
    少、「⋯」按钮从未出现过，直到 2026-10-06 三个正式插件把动作区挤出
    可视容量，第一次点「⋯」就 NameError 崩溃（错误报告窗接住）。改成
    **函数**是为了让配色跟随主题 —— Python 侧读不到 RinUI 的 QML 单例，
    深浅两套色值照抄 ``ui/Luminalium/Lumi.qml`` 的菜单语境令牌手工对齐。
    """
    if dark:
        bg, border, text, text_dim = "#2B2B2B", "rgba(255,255,255,0.08)", "#FFFFFF", "rgba(255,255,255,0.36)"
        hover, separator = "rgba(255,255,255,0.08)", "rgba(255,255,255,0.08)"
    else:
        bg, border, text, text_dim = "#F6F6F6", "rgba(0,0,0,0.06)", "#1A1A1A", "rgba(0,0,0,0.36)"
        hover, separator = "rgba(0,0,0,0.05)", "rgba(0,0,0,0.08)"
    return f"""
QMenu {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    color: {text};
    background: transparent;
    padding: 7px 26px 7px 12px;
    border-radius: 5px;
}}
QMenu::item:selected {{ background: {hover}; }}
QMenu::item:disabled {{ color: {text_dim}; }}
QMenu::separator {{
    height: 1px;
    background: {separator};
    margin: 4px 8px;
}}
QMenu::right-arrow {{
    width: 12px; height: 12px;
    background: {text_dim};
}}
"""


def setup_logging(level: str = "INFO") -> None:
    ensure_runtime_dirs()
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "luminalium.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # 只在**真终端**上再挂一份 stdout 日志。
    #
    # 为什么必须判断：Windows 管道的缓冲区写满（一般 64KB）时，写入方会被**阻塞**，
    # 而不是丢弃。从 VS Code 的「调试控制台」这类没有人持续读取的管道启动时，
    # 后台探测线程只要在 log 调用上撞到满缓冲区，就会被永远按在那里 ——
    # 现象是「线程 isRunning=True 但一个探测周期都不完成、日志静默、控制条不出现」。
    # 日志文件本身不受影响（先写文件再写 stdout），所以这里直接跳过最安全。
    if sys.stdout is not None and sys.stdout.isatty():
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)
    else:
        log.info(
            "标准输出不是终端（管道 / 调试控制台），已跳过控制台日志以免写满管道"
            "阻塞后台探测线程；日志见 %s", LOG_DIR / "luminalium.log",
        )


class LuminaliumApplication:
    """把各模块拼装成一个可运行的应用。"""

    def __init__(self, argv: list[str]) -> None:
        # 插件加载阶段一（Wave 3 任务 11）：collect_defaults 必须在 Config()
        # 构造**之前**跑 —— 插件默认值只能随 extra_defaults 在构造时注入默认
        # 层，错过这个窗口就永远进不去（两阶段时机的为什么见 loader 头注释）。
        # 保留防御式回退：loader 模块导入失败时退化为纯 Config()，插件全缺席
        # 也比应用起不来强。
        self._plugin_loader = None
        try:
            from app.plugins import loader
            self._plugin_loader = loader
            self.config = Config(extra_defaults=loader.collect_defaults())
        except ImportError:
            self.config = Config()
        setup_logging(str(self.config.get("app.log_level", "INFO")))
        log.info("Luminalium 2 v%s 启动", __version__)

        # 自建墨迹的输入前提：关高频指针事件合并（为什么前后各调一次见 configure_input_attributes
        # 的 docstring——Qt 6.11/Windows 构造期间会把属性翻回 True，构造后再调才真正生效）
        from .ink import configure_input_attributes
        configure_input_attributes()

        self.qt_app = QApplication(argv)
        configure_input_attributes()
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationDisplayName(str(self.config.get("app.name", APP_NAME)))
        self.qt_app.setQuitOnLastWindowClosed(False)
        # 窗口图标：任务栏 / Alt-Tab / 自绘标题栏都取同一份品牌图标
        self.qt_app.setWindowIcon(build_app_icon())

        # ---- i18n / UI 字体 ----
        # ⚠️ 必须在引擎加载任何 QML 之前做完：翻译器要赶在 qsTr 求值前装好；
        # 默认 QLocale 是 RinUI 字体补丁的语言信号（日语 → Yu Gothic UI）。
        # 翻译 / 字体都在重启后生效（设置页文案「切换后需要重新加载应用」）。
        language = str(self.config.get("app.language", i18n.SOURCE_LANGUAGE))
        i18n.apply_locale(language)
        i18n.install_translators(self.qt_app, language)
        i18n.apply_ui_font(self.qt_app, language)
        rinui_patch.apply()
        # 自建墨迹的 QML 类型（Luminalium.Ink 1.0）必须赶在首次 rinui.load 之前
        # 登记：引擎编译到 ``import Luminalium.Ink`` 时类型表里没有就直接报
        # 「module not installed」，事后再注册救不回已失败的组件。
        from .ink import register_qml_types
        register_qml_types()

        # ---- 后端 ----
        # 先把 socket 栈预热掉：Windows 上进程内第一次网络调用可能被 Winsock
        # 惰性初始化 / 杀软挂钩 / 沙箱拦网拖住好几秒，而那笔账会记在第一个碰
        # 网络的线程头上（回声洞取句正跑在后台线程里）。详见 echo_cave.warm_up。
        echo_cave.warm_up()
        self.backend = Backend(self.config, self.qt_app)
        # 错误处理：接管 sys.excepthook / threading.excepthook，把未捕获异常
        # 变成一张「崩溃报告 / 错误报告」窗（见 app/error_handler.py）。
        # 钩子在这里就装上（而不是等窗口都建完）—— 装上之后剩下的装配过程
        # 里再出异常，至少还能进日志；此时 ``reportRequested`` 还没接接收者，
        # 所以窗口那一步自然落空，不会拿一个半成品窗口去吓人。
        self.error_handler = ErrorHandler(self.config, self.qt_app)
        self.error_handler.install()
        self.ppt = PptController(
            interval_ms=int(self.config.get("presentation.poll_interval_ms", 400)),
            config=self.config,
        )
        # 幻灯片缩略图缓存（页码快速跳转面板上那几十张画面）。它一头是
        # PptController 的**消费者**（往 COM 线程投 ``Slides(i).Export``）、
        # 一头是桥的**数据源**（``Backend.thumbUrls``），所以在这儿把两头接上。
        # 见 app/slide_thumbs.py。
        self.slide_thumbs = SlideThumbCache(self.ppt, self.backend)
        self.backend.attach_slide_thumbs(self.slide_thumbs)
        # 「⋯」溢出菜单。必须持有引用，否则局部变量回收后菜单立即消失。
        self._overflow_menu: Optional[QMenu] = None
        # 墨迹引擎改道的两份运行期状态（引擎本身**不**缓存，每次现读 config，
        # 见 ``_ink_engine``）：
        # * ``_current_tool``：最近一次选中的工具。放映中切换引擎时要把它重新
        #   套到新引擎上，否则控制条显示「笔」、实际却谁都不画。
        # * ``_ppt_pointer_is_arrow``：进入 self 模式后是否已把 PPT 指针复位成
        #   arrow。只复位一次 —— 每点一次工具都往 COM 线程投一次 set_tool 是
        #   白白的跨线程往返（还会让 WPS 的快捷键回退通道多按一次 Ctrl+A）。
        self._current_tool = "arrow"
        self._ppt_pointer_is_arrow = False

        # ---- RinUI 引擎（共享一个 engine，所有窗口共用主题）----
        self.rinui = RinUIWindow()
        self.rinui.engine.addImportPath(str(UI_DIR))
        self.rinui.theme_manager.set_theme_color(str(self.config.get("app.accent", "#4CC2FF")))

        theme_name = str(self.config.get("app.theme", "dark")).lower()
        self.rinui.setTheme({"dark": Theme.Dark, "light": Theme.Light}.get(theme_name, Theme.Auto))

        self.rinui.engine.rootContext().setContextProperty("Backend", self.backend)
        self.rinui.engine.rootContext().setContextProperty(
            "ErrorHandler", self.error_handler
        )
        self.rinui.load(UI_DIR / "QuickPanel.qml")
        # 背景材质按配置。默认 "auto" = **按平台选**，与 RinUI 自带策略一致：
        # Win11 → Mica / Win10 → Acrylic / 其余 → none。
        #
        # ⚠️ 这里以前默认 "none"，并且**无条件**调用 setBackdropEffect() ——
        # 等于把 RinUI 自己的平台判断整个覆盖掉。后果是 Win11 上永远铺实色
        # 主题背景（colors.backgroundColor = #202020），窗口一次都不会透明，
        # 看起来就像「RinUI 的 Mica 没生效」。实测（build 26300）只要把值放成
        # mica，DWMWA_SYSTEMBACKDROP_TYPE 立刻变 2、客户区 alpha 从 255 掉到 77，
        # DWM 确实在合成 —— 所以问题从来不在 RinUI 那侧，而在这行覆盖。
        #
        # 显式写 none 仍然完全可用（窗口退回实色主题背景）。
        backdrop = str(self.config.get("app.backdrop", "auto")).lower()
        if backdrop == "auto":
            effect = (
                BackdropEffect.Mica
                if is_win11()
                else BackdropEffect.Acrylic
                if is_win10()
                else BackdropEffect.None_
            )
        else:
            effect = {
                "mica": BackdropEffect.Mica,
                "acrylic": BackdropEffect.Acrylic,
                "tabbed": BackdropEffect.Tabbed,
            }.get(backdrop, BackdropEffect.None_)
        self.rinui.setBackdropEffect(effect)
        log.info("背景材质: %s（配置 app.backdrop=%s）", effect.value, backdrop)

        # ---- 窗口 ----
        # 托盘提示文字 = 应用名（2026-10-01 第二轮用户指令：原来的「托盘提示文字」
        # 设置项连着配置键一起删掉了，这里直接取 app.name）。
        self.tray = TrayIcon(str(self.config.get("app.name", APP_NAME)))
        self.windows = WindowManager(
            self.rinui.engine,
            self.config,
            self.backend,
            self.ppt,
            tray=self.tray,
            # 把 RinUI 实例交出去：Python 侧另建的窗口要补登记进它的
            # WinEventFilter / ThemeManager / WinEventManager，否则那些窗口
            # 拿不到 DWM 阴影、圆角、resize 边框与 Snap（见 _attach_to_rinui）
            rinui=self.rinui,
        )
        self.windows.attach_panel(self.rinui.root_window)
        self.windows.load_windows()

        # 内建动作动词注册：必须在 Wave 3 的 load_plugins（末尾 freeze 注册表）
        # 之前完成，且处理器闭包要用 windows，所以卡在这个位置。
        # 详见 _register_builtin_verbs 与文件头注释。
        self._register_builtin_verbs()

        # 插件加载阶段二（Wave 3 任务 11）。顺序约束：
        # * 必须在 _register_builtin_verbs **之后** —— loader 末尾会
        #   registry.freeze()，内建动词得赶在冻结前进注册表；
        # * 必须在 _wire() **之前** —— 信号接线后消费端（导航 / 磁贴 /
        #   控制条 / 动词分发）假设注册表已完备冻结，不能再有写入。
        # include_debug 门控用 app.debug 配置键：不注入默认值（缺失即
        # False），开调试插件得手改 config.json 写 "app": {"debug": true}
        # 或由 smoke 临时写入。
        if self._plugin_loader is not None:
            self._plugin_loader.load_plugins(
                self.backend,
                self.windows,
                include_debug=bool(self.config.get("app.debug")),
            )

        self._wire()

    # ================================================================ 连接

    def _wire(self) -> None:
        self.tray.panelToggleRequested.connect(self.windows.toggle_panel)
        self.tray.settingsRequested.connect(self._open_settings)
        self.tray.quitRequested.connect(self.quit)
        self.tray.diagnoseRequested.connect(self._dump_diagnostics)
        self.tray.overlayToggleRequested.connect(self.windows.toggle_docks_manual)

        self.backend.shortcutTriggered.connect(self._on_shortcut)
        self.backend.actionTriggered.connect(self._on_action)
        self.backend.settingsRequested.connect(self._open_settings)
        self.backend.restartRequested.connect(self._restart)
        self.backend.quitRequested.connect(self.quit)
        self.backend.themeChangeRequested.connect(self._apply_theme)
        self.backend.accentChangeRequested.connect(self._apply_accent)

        # 墨迹引擎：放映中切换即时改道（Config 只有一处来源，监听它而不是另存一份）。
        # self 模式下墨迹窗口的「意图」在启动时就登记好：WindowManager 只记意图，
        # 真正露脸要等放映开始（show_docks 按 _ink_active 恢复）；当前工具是
        # arrow 时窗口整窗穿透，不吃点击。
        self.config.on_change(self._on_config_changed)
        if self._ink_engine() == "self":
            self.windows.set_ink_active(True)
            self.windows.set_ink_tool(self._current_tool)

        # ---- 错误 / 崩溃报告 ----
        # 采集到报告 → 弹窗；「忽略」→ 收窗继续跑；「重新启动 / 退出程序」→
        # 走与快捷面板底栏同一套动作（先把报告窗收掉，免得重启时它还挂在屏幕上）。
        self.error_handler.reportRequested.connect(self.windows.show_error_report)
        self.error_handler.dismissRequested.connect(self.windows.hide_error_report)
        self.error_handler.restartRequested.connect(self._report_restart)
        self.error_handler.quitRequested.connect(self._report_quit)

    # ================================================================ 启动

    def run(self) -> int:
        """启动画面 + 收尾的启动步骤，然后进事件循环。

        启动步骤**必须用 ``QTimer.singleShot`` 串起来**、不能全都塞在
        ``exec()`` 之前：Qt 在事件循环跑起来之前不会绘制，一律同步做完的话
        用户只会看到一个已经 100% 的窗口一闪而过。串起来之后每个 ``_boot_*``
        之间都会回一次事件循环，启动画面才真的画得出来。
        """
        self.windows.show_splash()
        self._splash(0.15, i18n.tr("Splash", "初始化"))
        # 第一步也要占满一个节拍 —— 否则 ``singleShot(0)`` 会在同一帧就把进度推到
        # 0.60，「初始化」这一档用户根本看不到（左标签会一直停在「正在启动」）。
        QTimer.singleShot(SPLASH_STEP_MS, self._boot_tray)
        log.info("进入事件循环")
        return self.qt_app.exec()

    def _splash(self, progress: float, stage: str) -> None:
        self.backend.setSplashStage(float(progress), stage)

    def _boot_tray(self) -> None:
        """创建托盘图标。

        ⚠️ 2026-10-01（第二轮）用户指令「托盘整组连着相关的逻辑和代码一块删掉」：
        原来的 ``tray.enabled`` 判断已删除 —— 托盘是**恒定行为**，也是应用的唯一
        入口（左键唤出快捷面板、右键菜单），不再有「关掉托盘」这条路。
        系统托盘不可用（极少数被魔改的 shell）时退回直接显示快捷面板，
        否则用户将完全无法唤出界面。
        """
        if self.tray.available:
            self.tray.show()
        else:
            log.warning("系统托盘不可用，直接显示快捷面板作为兜底")
            self.windows.show_panel()
        self._splash(0.60, i18n.tr("Splash", "创建托盘图标"))
        QTimer.singleShot(SPLASH_STEP_MS, self._boot_presenter)

    def _boot_presenter(self) -> None:
        log.info(
            "PPT 控制器启动: 轮询 %dms，窗口类探测 + COM %s",
            int(self.config.get("presentation.poll_interval_ms", 400)),
            "/".join(COM_PROG_IDS),
        )
        self.ppt.start()
        self._splash(0.88, i18n.tr("Splash", "启动放映探测"))
        QTimer.singleShot(SPLASH_STEP_MS, self._boot_ready)

    def _boot_ready(self) -> None:
        # 「启动时提示」气泡已按 2026-10-01（第二轮）用户指令删除（``tray.notify``
        # 方法本身保留：托盘右键「诊断信息（写入日志）」还在用它）。
        self._splash(1.0, i18n.tr("Splash", "正在进行启动后操作"))
        log.info("启动完成")
        QTimer.singleShot(SPLASH_HOLD_MS, self.windows.hide_splash)
        # 自动检查更新（ClassIsland ``AppStartupBackground`` 的开机检查同款）：
        # update.mode >= 1 就在启动收尾后查一次。放在启动画面淡出**之后**再错开
        # 一拍 —— 检查在后台线程跑，不抢装配的场；等 1.5s 是让刚开屏的应用
        # 别立刻就往外发请求（回声洞预热线程同理，错峰）。
        QTimer.singleShot(1500, self.backend.autoCheckUpdates)

    # ================================================================ 动作

    def _on_shortcut(self, shortcut_id: str) -> None:
        """快捷方式分发：查动作串 → 动词注册表最长前缀匹配 → 处理器执行。

        动作串从**合并后**的目录取（``Backend.shortcut_action``，config 内建
        ∪ registry 插件）；分发给注册表处理器，内建动词的行为由
        :meth:`_register_builtin_verbs` 登记的那两个闭包保证与原 if 链一致。
        注册表未命中时记日志落空（不抛异常）。

        Luminalium 没有课表类功能，不再提供占位快捷方式。
        """
        action = self.backend.shortcut_action(shortcut_id)
        if not action:
            log.info("未注册的快捷方式: %s", shortcut_id)
            return
        _dispatch_shortcut_action(action)

    def _register_builtin_verbs(self) -> None:
        """把内建动词注册进插件注册表（``open_settings`` / ``open_editor``）。

        ⚠️ 时机约束（2026-10-05）：必须在 Wave 3 任务 11 的 ``load_plugins``
        **之前**调用 —— loader 末尾会 ``registry.freeze()``，冻结后注册
        直接抛 RuntimeError。所以这一步放在装配段、``WindowManager`` 就绪后
        立即进行（处理器闭包要用 ``self.windows``）。

        幂等的原因：装配可能被重复执行（测试脚本 / 未来多实例装配场景），而
        registry 对重复动词抛 ValueError，所以先查 ``action_handlers()``
        再注册；已存在就直接跳过，不覆盖（后到的装配不该顶掉先注册的行为）。

        处理器签名统一为 ``handler(action: str)``：拿到完整动作串、自己解析
        后缀 —— ``open_settings:settings/Update.qml`` 的页面段就是这么来的。
        """
        from .plugins import registry

        def _open_settings_verb(action: str) -> None:
            page = action.split(":", 1)[1] if ":" in action else ""
            self._open_settings(page)

        def _open_editor_verb(action: str) -> None:
            # 与 _open_settings 同款：先把托盘面板收起，否则两个浮窗会叠在一起。
            # （QML 侧触发快捷方式时也会 hidePanel，这里再收一次是因为走
            #  ``Backend.activateShortcut`` 之外的入口时面板可能是开着的。）
            self.windows.hide_panel()
            self.windows.show_editor()

        builtins = {
            "open_settings": _open_settings_verb,
            "open_editor": _open_editor_verb,
        }
        registered = registry.action_handlers()
        for verb, handler in builtins.items():
            if verb in registered:
                continue
            registry.add_action_handler(verb, handler)

    def _dump_diagnostics(self) -> None:
        """把「顶层窗口为什么看不见」需要的所有证据写进日志。"""
        for line in self.ppt.diagnose().splitlines():
            log.info("%s", line)
        log.info("顶层窗口状态: %s", self.windows.overlay_report())
        log.info("顶层窗口结论: %s", self.windows.overlay_hint())
        self.tray.notify(
            i18n.tr("App", "诊断信息"),
            i18n.tr("App", "已写入 logs/luminalium.log"),
        )

    def _open_settings(self, page: str = "") -> None:
        """打开设置：先把托盘面板收起（否则两个浮窗会叠在一起）。"""
        self.windows.hide_panel()
        self.windows.show_settings(page or "")

    def _apply_theme(self, theme_name: str) -> None:
        mapping = {"dark": Theme.Dark, "light": Theme.Light, "auto": Theme.Auto}
        self.rinui.setTheme(mapping.get(theme_name.lower(), Theme.Auto))
        log.info("切换主题: %s", theme_name)

    def _apply_accent(self, color: str) -> None:
        self.rinui.theme_manager.set_theme_color(color)
        log.info("切换强调色: %s", color)

    def _restart(self) -> None:
        """重启整个程序（快捷面板底栏按钮）。

        2026-10-02 用户指令「快捷面板的重新加载按钮实则应当是重新启动程序
        按钮 点了之后需要重启程序」—— 原来这个按钮只重读配置，用户点了
        感知不到任何变化。现在的流程：先把配置落盘（新进程要读），再拉起
        一个**分离的**新进程（与当前控制台 / 父进程解绑，本进程退出不会
        连带杀掉它），最后走正常退出流程（停探测 / 收窗口 / 存托盘）。

        命令行怎么拼：

        * 打包后（``sys.frozen``）：直接再跑 ``sys.executable``；
        * 源码运行：``sys.executable + 脚本绝对路径``。工程入口是根目录的
          ``main.py``（文档化用法 ``python main.py``），``sys.argv[0]`` 就是
          它；解析成绝对路径保证与启动时的工作目录无关。
        """
        log.info("重启应用")
        self.config.save()
        if getattr(sys, "frozen", False):
            cmd = [sys.executable]
            cwd = str(Path(sys.executable).parent)
        else:
            script = Path(sys.argv[0] if sys.argv else "main.py").resolve()
            cmd = [sys.executable, str(script)]
            cwd = str(script.parent)
        # DETACHED_PROCESS：脱离控制台（GUI 程序本来也没有）；窗口控制在
        # DWM/Win32 侧，不需要继承任何句柄。close_fds 兜底防句柄泄漏。
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        try:
            subprocess.Popen(
                cmd,
                cwd=cwd,
                close_fds=True,
                creationflags=creationflags,
            )
        except OSError:
            # 拉不起来就别退了 —— 退了用户手里就什么都不剩了。
            log.exception("重启失败：无法拉起新进程 %r，保持当前实例运行", cmd)
            return
        self.quit()

    # ======================================================== 错误 / 崩溃报告

    def _report_restart(self) -> None:
        """报告窗的「重新启动」：先收掉报告窗，再走正常重启流程。"""
        self.windows.hide_error_report()
        self._restart()

    def _report_quit(self) -> None:
        """报告窗的「退出程序」：先收掉报告窗，再走正常退出流程。"""
        self.windows.hide_error_report()
        self.quit()

    # ============================================================ 放映控制

    def _on_action(self, action: str) -> None:
        """控制条动作分发。

        五个特权前缀（``tool:`` / ``pen_color:`` / ``pen_width:`` /
        ``eraser_width:`` / ``plugin:``）都先于「在放映中吗」门控；其余动作查
        内建分发表，且要求 ``state.active``。
        """
        state = self.ppt.state
        hwnd = state.window_handle

        if action.startswith("tool:"):
            # 2026-10-07（计划 self-ink 第 6 项，用户决策 Q1）：按墨迹引擎分流。
            # self：笔 / 橡皮交给自建墨迹窗口，PPT 指针保持 arrow；com：旧链路
            # 逐字不变（COM 笔手感不受控、PowerPoint / WPS 两家不一致，只作兜底）。
            tool = action.split(":", 1)[1]
            self._current_tool = tool
            if self._ink_engine() == "self":
                self._apply_tool_to_self_ink(tool, hwnd)
            else:
                self.windows.set_ink_active(False)
                self.ppt.set_tool(tool, hwnd)
                self._ppt_pointer_is_arrow = False
            log.info("切换工具: %s", tool)
            return

        if action.startswith("pen_color:"):
            # 笔选单里点了一格颜色（``#RRGGBB``）。和 ``tool:`` 一样**先于**
            # 「在放映中吗」的判断 —— 颜色不该被窗口探测的时序挡住；控制条
            # 本来就只在放映中出现。self 引擎下颜色只落到 InkLayer，**不碰 COM**
            # （PointerColor 只有 PowerPoint 认，这正是改用自建墨迹的动机之一）。
            code = action.split(":", 1)[1].lstrip("#")
            try:
                r, g, b = (int(code[i:i + 2], 16) for i in (0, 2, 4))
            except (ValueError, IndexError):
                log.warning("无法解析墨迹颜色: %r", action)
                return
            if self._ink_engine() == "self":
                layer = self.windows.ink_layer()
                if layer is None:
                    log.info("墨迹层尚未创建，颜色待下次放映生效: #%s", code.upper())
                else:
                    layer.setProperty("penColor", QColor(r, g, b))
            else:
                self.ppt.set_pen_color(r, g, b, hwnd)
            log.info("切换墨迹颜色: #%s", code.upper())
            return

        if action.startswith("pen_width:"):
            # 笔选单「粗细」一行点了一档（2026-10-07 计划 self-ink 第 9 项，
            # 用户指令：自建批注）。与 ``pen_color:`` 同级：先于「在放映中吗」
            # 门控。只有 self 引擎有粗细可言 —— PowerPoint / WPS 的放映笔
            # 没有粗细接口（这正是自建墨迹的动机之一），com 下只记日志。
            try:
                width = float(action.split(":", 1)[1])
            except (ValueError, IndexError):
                log.warning("无法解析笔粗细: %r", action)
                return
            if not width > 0:
                log.warning("非法笔粗细: %r", action)
                return
            if self._ink_engine() == "self":
                layer = self.windows.ink_layer()
                if layer is None:
                    log.info("墨迹层尚未创建，粗细待下次放映生效: %g", width)
                else:
                    layer.setProperty("penWidth", width)
            else:
                log.debug("com 引擎无笔粗细接口，忽略: %g", width)
                return
            log.info("切换笔粗细: %g", width)
            return

        if action.startswith("eraser_width:"):
            # 橡皮卡片「粗细」一行点了一档（2026-10-08 用户指令：自建批注）。
            # 与 ``pen_width:`` 逐字同构：先于「在放映中吗」门控；只有 self 引擎
            # 有橡皮粗细可言 —— com 下橡皮是演示软件自己的，只记日志。
            try:
                width = float(action.split(":", 1)[1])
            except (ValueError, IndexError):
                log.warning("无法解析橡皮粗细: %r", action)
                return
            if not width > 0:
                log.warning("非法橡皮粗细: %r", action)
                return
            if self._ink_engine() == "self":
                layer = self.windows.ink_layer()
                if layer is None:
                    log.info("墨迹层尚未创建，橡皮粗细待下次放映生效: %g", width)
                else:
                    layer.setProperty("eraserWidth", width)
            else:
                log.debug("com 引擎无橡皮粗细接口，忽略: %g", width)
                return
            log.info("切换橡皮粗细: %g", width)
            return

        if action.startswith("zoom:"):
            # 放大镜（放大 / 缩小 / 复位 / 四向移位）。与 ``tool:`` / ``pen_color:``
            # 一样**先于**「在放映中吗」的门控：走的是放映软件自己的缩放键，
            # 不该被窗口探测的时序挡住 —— 控制条本来就只在放映中出现。
            op = action.split(":", 1)[1]
            self.ppt.zoom(op, hwnd)
            log.info("放大镜: %s", op)
            return

        if action.startswith("plugin:"):
            # 2026-10-05（插件系统 Wave 2 任务 6）：``plugin:`` 前缀动作在
            # ``state.active`` 门控**之前**路由 —— 与 ``tool:`` / ``pen_color:``
            # 同级的特权前缀。动机：聚焦这类插件在非放映时也要能从面板 /
            # 控制条触发（见文件头注释）。分发复用任务 5 建好的模块级函数
            # （最长前缀匹配 ``registry.action_handlers()``），插件与 COM /
            # 按键注入零接触；动作后的 ``refresh_now`` 补刷对 ``plugin:``
            # 动作不强制（插件自理），所以这里直接 return。
            _dispatch_shortcut_action(action)
            return

        if not state.active:
            log.info("当前没有放映，忽略动作: %s", action)
            return

        if action.startswith("pager:goto:"):
            # 快速切页面板点了一格（页码 1-based）。与 next/previous 一样不占
            # 「翻页限流」—— 它是直接定位，不是连打翻页手势。带参数（页码），
            # 放不进下面的无参分发表，单独前置处理。
            try:
                page = int(action.rsplit(":", 1)[1])
            except (ValueError, IndexError):
                log.warning("无法解析跳转页码: %r", action)
                return
            self.ppt.goto_slide(page, hwnd)
            log.info("跳转到第 %s 页", page)
        else:
            # 内建动作分发表（2026-10-05 任务 6 由硬编码 if/elif 改表驱动，
            # 行为逐字不变）。统一成无参 callable：ppt 方法都要 hwnd，溢出菜单不要。
            handlers: Dict[str, Callable[[], Any]] = {
                "exit_presentation": lambda: self.ppt.exit_slideshow(hwnd),
                "pager:next": lambda: self.ppt.next_slide(hwnd),
                "pager:previous": lambda: self.ppt.previous_slide(hwnd),
                # 清屏按墨迹引擎分流：self 清自建墨迹的当前页，com 走旧 COM 清屏
                "clear_screen": (
                    self._clear_self_ink_page
                    if self._ink_engine() == "self"
                    else lambda: self.ppt.clear_screen(hwnd)
                ),
                "overflow": self._show_overflow_menu,
            }
            handler = handlers.get(action)
            if handler is None:
                log.info("未处理的放映动作: %s", action)
            else:
                handler()

        # 翻页后页码要立刻跟上：COM 命令是异步投递的，先等一小会儿让它执行完
        # （命令结束会自己轻量刷一次快照），再 poke 两条线程把新页码送出去。
        # 单次 120ms 有时赶在 COM 命令之前，于是页码要再多等一个周期 —— 这就是
        # 「页码识别迟钝」的观感来源。这里补一次稍晚的重试。
        QTimer.singleShot(90, self.ppt.refresh_now)
        QTimer.singleShot(320, self.ppt.refresh_now)

    # ======================================================== 墨迹引擎改道

    def _ink_engine(self) -> str:
        """当前墨迹引擎：``self``（自建，默认）或 ``com``（PowerPoint / WPS 放映笔）。

        每次现读 config、不另存一份：配置只有一处来源，设置页 / 手改
        config.json 改了它，下一次动作就按新值走。未知值按默认 self 处理。
        """
        engine = str(self.config.get("presentation.ink.engine", "self")).lower()
        return "com" if engine == "com" else "self"

    def _ensure_ppt_arrow(self, hwnd: int) -> None:
        """self 模式下把 PPT 指针复位成 arrow —— 只投递一次。

        PPT 侧若停在笔态，放映窗口会和墨迹窗口抢着画；但每点一次工具都
        投一次 set_tool 是白跑的 COM 往返，所以用 ``_ppt_pointer_is_arrow`` 记住。
        """
        if self._ppt_pointer_is_arrow:
            return
        self.ppt.set_tool("arrow", hwnd)
        self._ppt_pointer_is_arrow = True

    def _apply_tool_to_self_ink(self, tool: str, hwnd: int) -> None:
        """把工具套到自建墨迹上：窗口始终在场，笔 / 橡皮吃输入、其余穿透。"""
        self._ensure_ppt_arrow(hwnd)
        self.windows.set_ink_active(True)
        self.windows.set_ink_tool(tool if tool in ("pen", "eraser") else "arrow")

    def _call_ink_layer(self, slot: str) -> None:
        """调 InkLayer 上的一个无参槽（clearPage / clearAll）；层或槽缺失只记日志。

        防御式取槽：这些槽由并行任务补进 InkLayer，旧层上没有时不能把动作分发带崩。
        """
        layer = self.windows.ink_layer()
        if layer is None:
            log.info("墨迹层尚未创建，跳过 %s", slot)
            return
        method = getattr(layer, slot, None)
        if method is None:
            log.warning("墨迹层缺少 %s 槽，跳过", slot)
            return
        method()

    def _clear_self_ink_page(self) -> None:
        self._call_ink_layer("clearPage")

    def _on_config_changed(self, path: str, value: Any) -> None:
        """放映中切换墨迹引擎即时生效（挂在 ``Config.on_change`` 上）。"""
        if path == "presentation.ink.eraser_mode":
            # 橡皮子模式（计划第 8 项）：控制条卡片写配置，这里推给在场的层；
            # 层还没建的话 _apply_ink_config 会在建窗时补
            layer = self.windows.ink_layer()
            if layer is not None:
                layer.setProperty("eraserMode", str(value) if str(value) in ("pixel", "stroke") else "pixel")
            return
        if path in ("presentation.ink.palm_erase", "presentation.ink.palm_threshold_mm"):
            # 手掌擦除开关 / 阈值（计划第 8 项）：与上同理，实时推给在场的层
            layer = self.windows.ink_layer()
            if layer is not None:
                layer.setProperty("palmEraseEnabled", bool(self.config.get("presentation.ink.palm_erase", True)))
                layer.setProperty("palmThresholdMm", float(self.config.get("presentation.ink.palm_threshold_mm", 20)))
            return
        if path != "presentation.ink.engine":
            return
        hwnd = self.ppt.state.window_handle
        if self._ink_engine() == "com":
            # self→com：收起并清空自建墨迹，工具交还给 COM 放映笔
            self._call_ink_layer("clearAll")
            self.windows.set_ink_active(False)
            self._ppt_pointer_is_arrow = False
            self.ppt.set_tool(self._current_tool, hwnd)
        else:
            # com→self：PPT 指针复位 arrow（一次），再把当前工具套到墨迹窗口
            self._ppt_pointer_is_arrow = False
            self._apply_tool_to_self_ink(self._current_tool, hwnd)
        log.info("墨迹引擎切换为: %s", self._ink_engine())

    def _show_overflow_menu(self) -> None:
        """控制条上「⋯」溢出菜单。

        用原生 ``QMenu`` 而不是 QML 的 ``Popup``：控制条窗口带了
        ``Qt.WindowDoesNotAcceptFocus``，而 QML Popup 会另开一个真窗口并
        抢走聚焦；原生菜单是临时的，用户点击时弹出、关闭后焦点立刻回到
        放映窗口，不会把放映打断。

        样式现取（见 :func:`_overflow_menu_qss`）：主题运行时可切，算一次存起来
        会一直停在启动那一刻的那套颜色。
        """
        if self._overflow_menu is not None:
            self._overflow_menu.close()

        menu = QMenu()
        # 半透明底 + 圆角 QSS：不设这个属性的话 QSS 的 border-radius 外面
        # 会露出一圈方角黑底
        menu.setAttribute(Qt.WA_TranslucentBackground, True)
        # 主题明暗走 ``windows._dark_theme()``：内部已带 try/except（RinUI 未就绪
        # 按深色兜底），与早先这里的内联 try/except 同语义，别写第二份。
        menu.setStyleSheet(_overflow_menu_qss(self.windows._dark_theme()))
        menu.addAction(i18n.tr("Overflow", "上一页"), self.backend.previousSlide)
        menu.addAction(i18n.tr("Overflow", "下一页"), self.backend.nextSlide)
        menu.addSeparator()
        # 动作列表镜像控制条本体：读 ``presentationConfig``（config 内建 ∪
        # 插件 dock 动作，读取侧合并），**不能**只读 config 的
        # ``presentation.actions`` —— 那样插件动作在条上、菜单里却缺席，
        # 「⋯」恰恰是被插件动作挤出来的，不一致一眼可见。
        for item in self.backend.presentationConfig.get("actions", []) or []:
            action_id = str(item.get("id", ""))
            label = str(item.get("label", action_id))
            menu.addAction(
                label,
                lambda aid=action_id: self.backend.triggerAction(aid),
            )
        menu.addSeparator()
        menu.addAction(i18n.tr("Overflow", "退出放映"), self.backend.exitPresentation)

        # 必须持有引用：menu 是局部变量，回收后菜单会立刻消失
        self._overflow_menu = menu
        menu.popup(QCursor.pos())

    # ================================================================ 退出

    def quit(self) -> None:
        log.info("退出应用")
        self.ppt.stop()
        self.ppt.shutdown()
        # 缩略图缓存是纯临时物（下一次放映会重新导），退出时顺手清掉，
        # 别在数据目录里留一堆没人认领的 PNG。
        self.slide_thumbs.clear()
        self.windows.shutdown()
        self.tray.hide()
        self.config.save()
        self.qt_app.quit()


def main(argv: Optional[list[str]] = None) -> int:
    arguments = list(sys.argv if argv is None else argv)

    def _hook(exc_type, exc_value, exc_tb):
        """**应用起来之前**的兜底钩子。

        ``LuminaliumApplication`` 构造时会用 ``ErrorHandler`` 把 ``sys.excepthook``
        整个换掉（那时才有能力弹报告窗）；在那之前（导入期 / 建 QApplication 期）
        挂掉的异常只能进日志 —— 这一段 Qt 还没起来，画不出任何窗口。
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("luminalium").critical(
            "未捕获异常（应用尚未就绪）", exc_info=(exc_type, exc_value, exc_tb)
        )

    sys.excepthook = _hook
    app = LuminaliumApplication(arguments)
    return app.run()
