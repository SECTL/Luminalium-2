"""应用装配入口。

启动流程::

    读取配置 -> 建立 QApplication -> 注册 QML 上下文 -> 加载快捷面板
    -> 创建放映控制条 -> 托盘常驻 -> 开始轮询放映状态
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu
from RinUI import BackdropEffect, RinUIWindow, Theme

from . import __version__
from .bridge import Backend
from .config import Config
from .paths import APP_NAME, LOG_DIR, UI_DIR, ensure_runtime_dirs
from .ppt_controller import COM_PROG_IDS, PptController
from .tray import TrayIcon, build_app_icon
from .windows import WindowManager

log = logging.getLogger("luminalium")

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
        self.config = Config()
        setup_logging(str(self.config.get("app.log_level", "INFO")))
        log.info("Luminalium 2 v%s 启动", __version__)

        self.qt_app = QApplication(argv)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationDisplayName(str(self.config.get("app.name", APP_NAME)))
        self.qt_app.setQuitOnLastWindowClosed(False)
        # 窗口图标：任务栏 / Alt-Tab / 自绘标题栏都取同一份品牌图标
        self.qt_app.setWindowIcon(build_app_icon())

        # ---- 后端 ----
        self.backend = Backend(self.config, self.qt_app)
        self.ppt = PptController(
            interval_ms=int(self.config.get("presentation.poll_interval_ms", 400)),
            config=self.config,
        )
        # 「⋯」溢出菜单。必须持有引用，否则局部变量回收后菜单立即消失。
        self._overflow_menu: Optional[QMenu] = None

        # ---- RinUI 引擎（共享一个 engine，所有窗口共用主题）----
        self.rinui = RinUIWindow()
        self.rinui.engine.addImportPath(str(UI_DIR))
        self.rinui.theme_manager.set_theme_color(str(self.config.get("app.accent", "#4CC2FF")))

        theme_name = str(self.config.get("app.theme", "dark")).lower()
        self.rinui.setTheme({"dark": Theme.Dark, "light": Theme.Light}.get(theme_name, Theme.Auto))

        self.rinui.engine.rootContext().setContextProperty("Backend", self.backend)
        self.rinui.load(UI_DIR / "QuickPanel.qml")
        # 背景材质按配置。none = 实色主题背景；Mica/Acrylic 会让窗口透明、
        # 全靠 DWM 合成，在不支持 / 合成异常的机器上就是一片怪材质。
        backdrop = str(self.config.get("app.backdrop", "none")).lower()
        effect = {
            "mica": BackdropEffect.Mica,
            "acrylic": BackdropEffect.Acrylic,
            "tabbed": BackdropEffect.Tabbed,
        }.get(backdrop, BackdropEffect.None_)
        self.rinui.setBackdropEffect(effect)

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
        self.backend.reloadRequested.connect(self._reload)
        self.backend.quitRequested.connect(self.quit)
        self.backend.themeChangeRequested.connect(self._apply_theme)
        self.backend.accentChangeRequested.connect(self._apply_accent)

    # ================================================================ 启动

    def run(self) -> int:
        """启动画面 + 收尾的启动步骤，然后进事件循环。

        启动步骤**必须用 ``QTimer.singleShot`` 串起来**、不能全都塞在
        ``exec()`` 之前：Qt 在事件循环跑起来之前不会绘制，一律同步做完的话
        用户只会看到一个已经 100% 的窗口一闪而过。串起来之后每个 ``_boot_*``
        之间都会回一次事件循环，启动画面才真的画得出来。
        """
        self.windows.show_splash()
        self._splash(0.15, "初始化")
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
        self._splash(0.60, "创建托盘图标")
        QTimer.singleShot(SPLASH_STEP_MS, self._boot_presenter)

    def _boot_presenter(self) -> None:
        log.info(
            "PPT 控制器启动: 轮询 %dms，窗口类探测 + COM %s",
            int(self.config.get("presentation.poll_interval_ms", 400)),
            "/".join(COM_PROG_IDS),
        )
        self.ppt.start()
        self._splash(0.88, "启动放映探测")
        QTimer.singleShot(SPLASH_STEP_MS, self._boot_ready)

    def _boot_ready(self) -> None:
        # 「启动时提示」气泡已按 2026-10-01（第二轮）用户指令删除（``tray.notify``
        # 方法本身保留：托盘右键「诊断信息（写入日志）」还在用它）。
        self._splash(1.0, "就绪")
        log.info("启动完成")
        QTimer.singleShot(SPLASH_HOLD_MS, self.windows.hide_splash)

    # ================================================================ 动作

    def _on_shortcut(self, shortcut_id: str) -> None:
        """快捷方式分发。

        目前的动作有两类：

        * ``open_settings[:<相对 ui 的页面路径>]`` —— 打开设置窗口（可落到某一页）；
          不带页面的 ``open_settings`` 落在默认页；
        * ``open_editor`` —— 打开**主界面编辑器**独立窗口
          （``ui/MainInterfaceEditor.qml``）。

        Luminalium 没有课表类功能，不再提供占位快捷方式。
        """
        catalog = self.config.get("quick_panel.shortcut_catalog", []) or []
        action = ""
        for item in catalog:
            if str(item.get("id")) == shortcut_id:
                action = str(item.get("action", ""))
                break
        if not action:
            log.info("未注册的快捷方式: %s", shortcut_id)
            return
        if action == "open_settings" or action.startswith("open_settings:"):
            page = action.split(":", 1)[1] if ":" in action else ""
            self._open_settings(page)
            return
        if action == "open_editor":
            # 与 _open_settings 同款：先把托盘面板收起，否则两个浮窗会叠在一起。
            # （QML 侧触发快捷方式时也会 hidePanel，这里再收一次是因为走
            #  ``Backend.activateShortcut`` 之外的入口时面板可能是开着的。）
            self.windows.hide_panel()
            self.windows.show_editor()
            return
        log.info("未实现的快捷方式动作: %s", action)

    def _dump_diagnostics(self) -> None:
        """把「顶层窗口为什么看不见」需要的所有证据写进日志。"""
        for line in self.ppt.diagnose().splitlines():
            log.info("%s", line)
        log.info("顶层窗口状态: %s", self.windows.overlay_report())
        log.info("顶层窗口结论: %s", self.windows.overlay_hint())
        self.tray.notify("诊断信息", "已写入 logs/luminalium.log")

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

    def _reload(self) -> None:
        log.info("重新加载配置")
        self.config = Config()
        self.backend.reload_from_config()
        self.ppt.apply_config(self.config)
        self.ppt.refresh_now()

    # ============================================================ 放映控制

    def _on_action(self, action: str) -> None:
        state = self.ppt.state
        hwnd = state.window_handle

        if action.startswith("tool:"):
            tool = action.split(":", 1)[1]
            self.ppt.set_tool(tool, hwnd)
            log.info("切换工具: %s", tool)
            return

        if action.startswith("pen_color:"):
            # 笔选单里点了一格颜色（``#RRGGBB``）。和 ``tool:`` 一样**先于**
            # 「在放映中吗」的判断 —— 颜色是在 COM 层生效的，不该被窗口探测
            # 的时序挡住；控制条本来就只在放映中出现。
            code = action.split(":", 1)[1].lstrip("#")
            try:
                r, g, b = (int(code[i:i + 2], 16) for i in (0, 2, 4))
            except (ValueError, IndexError):
                log.warning("无法解析墨迹颜色: %r", action)
                return
            self.ppt.set_pen_color(r, g, b, hwnd)
            log.info("切换墨迹颜色: #%s", code.upper())
            return

        if not state.active:
            log.info("当前没有放映，忽略动作: %s", action)
            return

        if action == "exit_presentation":
            self.ppt.exit_slideshow(hwnd)
        elif action == "pager:next":
            self.ppt.next_slide(hwnd)
        elif action == "pager:previous":
            self.ppt.previous_slide(hwnd)
        elif action == "clear_screen":
            self.ppt.clear_screen(hwnd)
        elif action == "overflow":
            self._show_overflow_menu()
        else:
            log.info("未处理的放映动作: %s", action)

        # 翻页后页码要立刻跟上：COM 命令是异步投递的，先等一小会儿让它执行完
        # （命令结束会自己轻量刷一次快照），再 poke 两条线程把新页码送出去。
        # 单次 120ms 有时赶在 COM 命令之前，于是页码要再多等一个周期 —— 这就是
        # 「页码识别迟钝」的观感来源。这里补一次稍晚的重试。
        QTimer.singleShot(90, self.ppt.refresh_now)
        QTimer.singleShot(320, self.ppt.refresh_now)

    def _show_overflow_menu(self) -> None:
        """控制条上「⋯」溢出菜单。

        用原生 ``QMenu`` 而不是 QML 的 ``Popup``：控制条窗口带了
        ``Qt.WindowDoesNotAcceptFocus``，而 QML Popup 会另开一个真窗口并
        抢走聚焦；原生菜单是临时的，用户点击时弹出、关闭后焦点立刻回到
        放映窗口，不会把放映打断。
        """
        if self._overflow_menu is not None:
            self._overflow_menu.close()

        menu = QMenu()
        menu.setStyleSheet(OVERFLOW_MENU_QSS)
        menu.addAction("上一页", self.backend.previousSlide)
        menu.addAction("下一页", self.backend.nextSlide)
        menu.addSeparator()
        for item in self.config.get("presentation.actions", []) or []:
            action_id = str(item.get("id", ""))
            label = str(item.get("label", action_id))
            menu.addAction(
                label,
                lambda aid=action_id: self.backend.triggerAction(aid),
            )
        menu.addSeparator()
        menu.addAction("退出放映", self.backend.exitPresentation)

        # 必须持有引用：menu 是局部变量，回收后菜单会立刻消失
        self._overflow_menu = menu
        menu.popup(QCursor.pos())

    # ================================================================ 退出

    def quit(self) -> None:
        log.info("退出应用")
        self.ppt.stop()
        self.ppt.shutdown()
        self.windows.shutdown()
        self.tray.hide()
        self.config.save()
        self.qt_app.quit()


def main(argv: Optional[list[str]] = None) -> int:
    arguments = list(sys.argv if argv is None else argv)

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("luminalium").critical(
            "未捕获异常", exc_info=(exc_type, exc_value, exc_tb)
        )

    sys.excepthook = _hook
    app = LuminaliumApplication(arguments)
    return app.run()
