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
import sys
import traceback
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow, Theme

from . import __version__
from . import echo_cave
from . import i18n
from . import launch
from . import multi_instance
from . import rinui_patch
from .bridge import Backend
from .config import Config
from .error_handler import ErrorHandler
from .paths import APP_NAME, UI_DIR
from .ppt_controller import COM_PROG_IDS, PptController
from .page_memory import PageMemory
from .slide_thumbs import SlideThumbCache
from .startup import apply_backdrop_effect, configure_rinui, setup_logging
from .tray import TrayIcon, build_app_icon
from .windows import WindowManager

log = logging.getLogger("luminalium")


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


def _report_action_exception(action: str, exc_tb) -> None:
    """插件动作处理器抛异常的留痕出口：日志 + 错误报告（非致命）。

    对齐插件总线的隔离纪律（``PluginContext.publish`` 同款）：单个插件
    的动作炸了只记报告，不炸面板、不炸后续动作。 ErrorHandler 挂在
    ``QApplication`` 下（``LuminaliumApplication`` 构造时 ``parent=qt_app``），
    模块级函数经 ``findChild`` 找它 —— 找不到（测试装配等）只留日志。
    """
    log.exception("插件动作 %r 处理器抛异常", action)
    try:
        from .error_handler import ErrorHandler

        app = QCoreApplication.instance()
        reporter = app.findChild(ErrorHandler) if app is not None else None
        if reporter is not None:
            reporter.reportError(
                f"插件动作 {action} 处理器抛异常",
                "".join(traceback.format_exception(*exc_tb)) or repr(exc_tb[1]),
            )
    except Exception:
        log.debug("错误报告通道不可用", exc_info=True)


def _dispatch_shortcut_action(action: str) -> bool:
    """把快捷方式动作串交给动词注册表分发；返回是否有处理器受理。

    未命中只记日志、不抛异常 —— 插件被卸载后其磁贴 id 可能还留在用户的
    启用列表里，点击时必须安全落空而不是把面板点崩。

    处理器调用包在 try/except 里（2026-10-18 plugin-audit B2，对齐总线
    隔离纪律）：单个插件动作抛异常落日志 + 错误报告（见
    :meth:`_report_action_exception`），面板与后续动作照常 —— 但绝不
    静默吞掉，留痕是硬要求。
    """
    handler = _match_verb_handler(action)
    if handler is None:
        log.info("未实现的快捷方式动作: %s", action)
        return False
    try:
        handler(action)
    except Exception:
        _report_action_exception(action, sys.exc_info())
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


class LuminaliumApplication:
    """把各模块拼装成一个可运行的应用。"""

    def __init__(self, argv: list[str]) -> None:
        # 启动开关（2026-11-22，维护模式窗口的「安全模式 / 诊断模式」落在
        # 这两处，别处不再各读一份 argv）：
        # * 安全模式 = **不加载任何插件**（插件炸了导致起不来的唯一自救路）；
        # * 诊断模式 = 日志级别拉到 DEBUG（写文件，不假装有控制台）。
        self._safe_mode = launch.safe_mode_requested(argv)
        self._diagnostic_mode = launch.diagnostic_requested(argv)
        # 多实例询问窗里点了「取消」时置位：装配段提前收尾，``run()`` 空跑一圈
        # 事件循环后退出（直接 return 会在解释器收尾时崩 0xC0000409）。
        self._startup_cancelled = False
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
        setup_logging(
            "DEBUG"
            if self._diagnostic_mode
            else str(self.config.get("app.log_level", "INFO"))
        )
        if self._diagnostic_mode:
            log.info("诊断模式：日志级别已提升到 DEBUG")
        if self._safe_mode:
            log.info("安全模式：本次启动不加载插件")
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
        # 续播（2026-11-08）：按课件文件记住上次讲到第几页。与缩略图缓存
        # 同一个装配位 —— 一头是 PptController 的消费者（stateChanged 给页码、
        # deckReady 给课件身份），一头是桥的数据源（``Backend.pageMemory``）。
        # 见 app/page_memory.py。
        # ⚠️ 不传 parent：``LuminaliumApplication`` 是纯 Python 装配类，
        # **不是 QObject**（传进去 Qt 会抛 TypeError）。生命周期由本实例持有，
        # 与 ``slide_thumbs`` 同一条（那个的 parent 是 Backend）。
        self.page_memory = PageMemory(self.config, self.ppt)
        self.backend.attach_page_memory(self.page_memory)
        # 墨迹引擎改道的两份运行期状态（引擎本身**不**缓存，每次现读 config，
        # 见 ``_ink_engine``）：
        # * ``_current_tool``：最近一次选中的工具。放映中切换引擎时要把它重新
        #   套到新引擎上，否则控制条显示「笔」、实际却谁都不画。
        # * ``_ppt_pointer_is_arrow``：进入 self 模式后是否已把 PPT 指针复位成
        #   arrow。只复位一次 —— 每点一次工具都往 COM 线程投一次 set_tool 是
        #   白白的跨线程往返（还会让 WPS 的快捷键回退通道多按一次 Ctrl+A）。
        self._current_tool = "arrow"
        self._ppt_pointer_is_arrow = False
        #: 上一次收到的放映状态（``state.active``）。工具归位只在**翻转的边沿**
        #: 做一次：``stateChanged`` 每次页码变化都会来一条，逐条归位会把用户
        #: 刚选的笔当成残留清掉（见 ``_on_presentation_state``）。
        self._presentation_active = False

        # ---- RinUI 引擎（共享一个 engine，所有窗口共用主题）----
        # 主题 / 强调色 / 背景材质的装配抽在 :func:`configure_rinui`（维护模式
        # 那套精简装配要开自己的引擎，外观必须与这里逐字一致）。
        self.rinui = RinUIWindow()
        configure_rinui(self.rinui, self.config)

        self.rinui.engine.rootContext().setContextProperty("Backend", self.backend)
        self.rinui.engine.rootContext().setContextProperty(
            "ErrorHandler", self.error_handler
        )
        self.rinui.load(UI_DIR / "QuickPanel.qml")
        # 背景材质必须排在 load **之后**：load 才把 root_window 交出去，
        # 早一步设材质的话窗口名单还是空的，一次都落不到面板上。
        apply_backdrop_effect(self.rinui, self.config)

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

        # ---- 多实例检测（2026-11-22，照 Luminalium 1）----
        # ⚠️ 必须排在 ``WindowManager`` 之后：询问窗建完要立刻
        # ``_attach_to_rinui``，RinUI 不接管的话 ``WS_CAPTION`` 会变成真的
        # 原生标题栏压在自绘标题栏上（2026-11-22 用户反馈「你这也不是 RinUI
        # 窗口啊」就是这个）。仍然排在控制条 / 插件之前 —— 取消启动时那些
        # 都还没建。
        self._guard_multi_instance()
        if self._startup_cancelled:
            return

        # 2026-10-13 修复「软件内自带插件有时候不显示在胶囊上」：
        # 先登记内建编辑器组、内建窗口句柄与内建动作动词（三者均幂等，且必须在
        # load_plugins 末尾 registry.freeze() 之前入表），随后立即跑 load_plugins，
        # 最后才调 load_windows() 创建 TopWindow 与各角落 PresentationDock。
        #
        # 此前 load_windows() 排在 load_plugins() 之前，导致控制条实例化时
        # registry.dock_actions() 还是空表，PresentationDock.actionsCfg 只绑到了
        # ['clear_screen']（宽 366px）；除非用户进设置改一次放映配置间接触发
        # presentationConfigChanged，否则计时器 / 小黑板 / 聚光灯在整个会话里都
        # 不会出现在胶囊上。
        self.windows._register_builtin_groups()
        self.windows._register_builtin_windows()
        self._register_builtin_verbs()

        # 插件加载阶段二（Wave 3 任务 11）。顺序约束：
        # * 必须在内建组 / 内建窗口 / _register_builtin_verbs **之后** —— loader
        #   末尾会 registry.freeze()，内建项得赶在冻结前进注册表；
        # * 必须在 load_windows() 与 _wire() **之前** —— 控制条创建与信号接线后
        #   消费端（导航 / 磁贴 / 控制条 / 动词分发）直接读取已完备冻结的注册表。
        # include_debug 门控用 app.debug 配置键：不注入默认值（缺失即
        # False），开调试插件得手改 config.json 写 "app": {"debug": true}
        # 或由 smoke 临时写入。
        #
        # 2026-11-22：安全模式（``--safe``）整段跳过 —— 插件是「应用起不来」
        # 最常见的元凶，维护模式里那条「以安全模式继续使用」就是为它准备的。
        if self._safe_mode:
            log.info("安全模式：跳过插件加载（含内建调试插件）")
        elif self._plugin_loader is not None:
            self._plugin_loader.load_plugins(
                self.backend,
                self.windows,
                include_debug=bool(self.config.get("app.debug")),
            )
        # 导航 / 磁贴都是「读取侧拼接」（注册表加载后才有插件贡献），
        # 而 QML 侧绑的是 ``settingsNavItems`` 这个 Property —— 不发通知
        # 的话，加载前就已打开的面板会停在「只有内建项」的状态。
        # 设置窗口虽是懒创建（正常路径赶得上），快捷面板不是；
        # 顺带也让 `setPluginEnabled` 之后的未来刷新有处可挂。
        # ⚠️ 它必须留在 ``if`` **外面**（安全模式 / loader 缺席时也要发）：
        # 面板在装配段就已加载完毕，这一条是它唯一一次取导航清单的机会。
        self.backend.settingsNavItemsChanged.emit()

        self.windows.load_windows()

        self._wire()

    # ============================================================ 多实例检测

    def _guard_multi_instance(self) -> None:
        """检测同入口的其它实例，按 Luminalium 1 的规则处理。

        三种走向（与 L1 一致）：

        * **重启拉起的本进程** —— 不弹框，等旧实例自己退（最多 3s），超时才
          kill。重启是排班交接，不是用户主动多开；
        * **用户再点一次程序** —— 弹 ``ui/MultiInstanceDialog.qml`` 询问：
          重启旧实例 / 仍然启动 / 取消；
        * **取消** —— 置 ``_startup_cancelled``，``__init__`` 提前收尾。

        检测本身（``app/multi_instance.py``）失败一律静默放行：多实例检测是
        防呆，不是启动的前置条件。
        """
        if multi_instance.is_disabled():
            log.info("多实例检测已禁用（%s）", multi_instance.DISABLE_ENV)
            return

        # 重启标记必须先读：旧实例通常就是本进程的父进程，``find_existing_instances``
        # 会主动跳过父进程，光看扫描结果会误判成「没有冲突」然后把对话框弹出来。
        restart, restart_pid = multi_instance.consume_restart_request()

        try:
            pids = multi_instance.find_existing_instances()
        except Exception:
            log.exception("多实例检测失败，按无冲突继续启动")
            return

        if restart:
            wait_pids = list(pids)
            if restart_pid and restart_pid not in wait_pids:
                wait_pids.append(restart_pid)
            if wait_pids:
                log.info("检测到重启交接，等待旧实例退出: %s", wait_pids)
                alive = multi_instance.wait_for_exit(wait_pids)
                if alive:
                    log.warning("旧实例未在限时内退出，强制结束: %s", alive)
                    multi_instance.terminate_instances(alive)
            return

        if not pids:
            return

        log.warning("检测到已有实例: %s", pids)
        self._ask_multi_instance(pids)

    def _ask_multi_instance(self, pids: list[int]) -> None:
        """弹询问窗并等用户决定；窗口只发信号，不直接引用 ``multi_instance``。"""
        component = QQmlComponent(
            self.rinui.engine,
            QUrl.fromLocalFile(str(UI_DIR / "MultiInstanceDialog.qml")),
        )
        if component.isError():
            for error in component.errors():
                log.error("多实例窗口加载失败: %s", error.toString())
            return

        window = component.create()
        if window is None:
            for error in component.errors():
                log.error("多实例窗口创建失败: %s", error.toString())
            return

        # 持有引用，防止引擎把组件 / 窗口当垃圾回收；局部 QEventLoop 让启动流程
        # 停在用户决定之前 —— 此时控制条 / 插件都还没建。
        self._multi_instance_component = component
        self._multi_instance_window = window

        # RinUI 接管：不接管的话 FramelessWindowHint 被摘掉后 WS_CAPTION 会
        # 露出原生标题栏，叠在 QML 自绘的 Fluent 标题栏上（用户 2026-11-22
        # 反馈的「不是 RinUI 窗口」）。
        if not self.windows._attach_to_rinui(window):
            self.windows._keep_frameless(window)

        decision = {"value": "cancel"}
        loop = QEventLoop()

        def finish(value: str) -> None:
            if loop.isRunning():
                loop.quit()
            decision["value"] = value
            window.hide()

        window.restartRequested.connect(lambda: finish("restart"))
        window.continueRequested.connect(lambda: finish("continue"))
        window.cancelRequested.connect(lambda: finish("cancel"))

        window.show()
        window.requestActivate()
        loop.exec()

        # 按仓库约定「窗口只藏不销毁」：这次决定之后不会再弹，但也不主动
        # deleteLater —— QML 窗口在解释器收尾阶段销毁更容易踩 Qt 的收尾时序。
        window.hide()

        if decision["value"] == "restart":
            multi_instance.terminate_instances(pids)
        elif decision["value"] == "cancel":
            log.info("用户取消：保留已有实例，本次启动退出")
            self._startup_cancelled = True

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
        # 设置标题栏「更多」→「重新启动并进入维护模式」（2026-11-22）。
        # 与上面的「重启」共用同一条拉起通道，只多带一个 --maintenance。
        self.backend.maintenanceModeRequested.connect(self._enter_maintenance)
        self.backend.quitRequested.connect(self.quit)
        self.backend.themeChangeRequested.connect(self._apply_theme)
        self.backend.accentChangeRequested.connect(self._apply_accent)
        # 设置标题栏「更多」→ 创建快捷方式的结果：菜单点完就收，没有能挂横幅
        # 的地方，用托盘气泡回一句「成了 / 没成」。
        self.backend.shortcutCreateResult.connect(self._on_shortcut_created)
        # 放映开始 / 结束的边沿 → 工具三态归位（2026-10-17，见 _reset_tool_state）。
        # 接在这里而不是 QML：墨迹工具那一半只存在于 Python 侧，QML 看不见它。
        self.ppt.stateChanged.connect(self._on_presentation_state)

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
        if self._startup_cancelled:
            # 询问窗点了「取消」：装配段已经提前收尾（控制条 / 插件 / 启动画面
            # 都还没建；托盘与 WindowManager 已存在，但不弹任何窗口）。
            # 仍然让 Qt 跑一圈再退 —— 直接 return 会让 QML 窗口和 RinUI 的监听器
            # 在解释器退出时才销毁，实测会在收尾阶段崩一次（0xC0000409）。
            QTimer.singleShot(0, self.qt_app.quit)
            return self.qt_app.exec()
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

    def _on_shortcut_created(self, ok: bool, message: str) -> None:
        """「更多」菜单创建快捷方式的结果 → 托盘气泡（2026-11-21）。

        设置窗口此时可能还开着，但菜单已经收起来了，往页面上插横幅反而突兀；
        托盘气泡是这类「一次性系统动作」最省事、也最不打断的反馈方式。
        """
        if not ok:
            log.warning("创建快捷方式失败: %s", message)
        self.tray.notify(i18n.tr("MoreMenu", "快捷方式"), message)

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

    def _restart(self, maintenance: bool = False, safe: bool = False,
                 diagnostic: bool = False) -> None:
        """重启整个程序（快捷面板底栏按钮 / 维护模式入口 / 报告窗）。

        2026-10-02 用户指令「快捷面板的重新加载按钮实则应当是重新启动程序
        按钮 点了之后需要重启程序」—— 原来这个按钮只重读配置，用户点了
        感知不到任何变化。现在的流程：先把配置落盘（新进程要读），再拉起
        一个**分离的**新进程（与当前控制台 / 父进程解绑，本进程退出不会
        连带杀掉它），最后走正常退出流程（停探测 / 收窗口 / 存托盘）。

        2026-11-22：命令行拼装搬到 ``app/launch.py``（维护模式要从另一套
        装配里做同一件事），这里只决定带哪几个开关：

        * ``maintenance`` —— ``--maintenance``：新进程走维护模式装配
          （设置标题栏「更多」→「重新启动并进入维护模式」）；
        * ``safe`` / ``diagnostic`` —— 维护模式窗口里「以安全 / 诊断模式
          继续使用」的两个开关，落到新进程的插件加载与日志级别上。
        """
        extra = []
        if maintenance:
            extra.append(launch.MAINTENANCE_FLAG)
        if safe:
            extra.append(launch.SAFE_FLAG)
        if diagnostic:
            extra.append(launch.DIAGNOSTIC_FLAG)
        log.info("重启应用%s", f"（{' '.join(extra)}）" if extra else "")
        # 先落盘再拉起：新进程读的是磁盘上的配置。
        self.config.save()
        # 拉不起来就别退了 —— 退了用户手里就什么都不剩了。
        if not launch.relaunch(extra):
            return
        self.quit()

    def _enter_maintenance(self) -> None:
        """设置标题栏「更多」→「重新启动并进入维护模式」。"""
        self._restart(maintenance=True)

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

    def _on_presentation_state(self, state) -> None:
        """放映开始 / 结束的边沿 → 工具状态归位到「选择」（2026-10-17）。

        病灶（用户报的「退出时的笔还亮在下一场」）：工具栏选中项
        （``Backend._active_tool``）与墨迹工具都是**跨场保留**的，而 PowerPoint
        结束放映时自己把指针收回 arrow。于是上一场用笔退出、下一场进来时，
        控制条亮着「笔」、PPT 不在批注态、也不是「选择」—— 三处各说各话。

        所以只在**翻转边沿**归位一次（页码变化也会发 stateChanged，逐条归位
        会把用户刚选的笔清掉）。归位内容见 :meth:`_reset_tool_state`。

        退出这一侧同时是「下一场从干净状态开始」的保证：退出时归位，下一场
        进入时才有东西可同步；进入时也归位一次，是为了兜住「本进程启动前
        演示软件里就留着笔态」这种历史状态。
        """
        active = bool(getattr(state, "active", False))
        if active == self._presentation_active:
            return
        self._presentation_active = active
        self._reset_tool_state()

    def _reset_tool_state(self) -> None:
        """把工具三态一起拨回 arrow（选择）。

        三处**必须同时清**，只清一处就是换个地方不一致：

        * ``Backend.activeTool`` —— 分段 ``currentIndex`` 的源，QML 那条
          ``onActiveToolChanged`` 会连带把笔选单 / 放大镜收掉；
        * ``_current_tool`` / ``_ppt_pointer_is_arrow`` —— 应用侧记忆；
        * ``WindowManager._ink_tool`` —— 最容易漏的一处：它决定墨迹窗口是
          「整窗吃输入」还是「整窗穿透」。残留的 pen 会让下一场的透明墨迹层
          挡住放映窗口，用户点版面毫无反应。

        ⚠️ **这里一次都不碰演示软件**，两个方向都不能碰：

        * 退出时放映已结束，``ppt.set_tool`` 会退化成「往那个 hwnd 注入
          Ctrl+A/P/E」（见 ``_cmd_tool``）；
        * 进入时放映窗口的 ``View`` 还没进 ``SlideShowWindows`` 集合，
          ``_cmd_tool`` 的重试阶梯会睡掉半秒再退回注入快捷键 —— 那正好卡在
          控制条刚出现、页码最该跟上的那一拍。

        指针本身不必我们管：每次新开放映，播放器都从 arrow 起（``PointerType``
        跟着 ``SlideShowWindow`` 实例走）。
        """
        if self.backend.activeTool != "arrow":
            log.info("放映状态翻转：工具归位到「选择」（原为 %s）", self.backend.activeTool)
        self._current_tool = "arrow"
        # 下一场第一次用工具时再确认一次箭头：别把上一场的记忆当成
        # 「PPT 现在就是 arrow」
        self._ppt_pointer_is_arrow = False
        self.backend.resetTool()
        self.windows.set_ink_tool("arrow")

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
            # 行为逐字不变）。统一成无参 callable：ppt 方法都要 hwnd。
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

    # ================================================================ 退出

    def quit(self) -> None:
        log.info("退出应用")
        self.ppt.stop()
        self.ppt.shutdown()
        # 缩略图缓存是纯临时物（下一次放映会重新导），退出时顺手清掉，
        # 别在数据目录里留一堆没人认领的 PNG。
        self.slide_thumbs.clear()
        # 续播的记忆**不能清**（它要跨会话保留），只把还没落盘的尾巴写掉。
        # 退出放映时 ``PageMemory.observe`` 已经会强制落一次，这里是兜底
        # （比如放映中途直接退出程序）。
        self.page_memory.flush()
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
    # 维护模式（2026-11-22）：与正常启动**完全分开**的一条装配 —— 不建托盘 /
    # 不放映探测 / 不加载插件，只开一张维护窗口（见 app/maintenance.py）。
    # 分叉放在这里而不是 LuminaliumApplication 内部：那套装配从头到尾都假定
    # 自己要管理放映控制条，前半段建完再回头拆不干净。
    if launch.maintenance_requested(arguments):
        from .maintenance import run_maintenance

        return run_maintenance(arguments)
    app = LuminaliumApplication(arguments)
    return app.run()
