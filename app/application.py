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

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)


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
        self.tray = TrayIcon(str(self.config.get("tray.tooltip", APP_NAME)))
        self.windows = WindowManager(
            self.rinui.engine,
            self.config,
            self.backend,
            self.ppt,
            tray=self.tray,
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
        if self.config.get("tray.enabled", True):
            if self.tray.available:
                self.tray.show()
            else:
                log.warning("系统托盘不可用，快捷面板只能通过命令启动")
                self.windows.show_panel()

        log.info(
            "PPT 控制器启动: 轮询 %dms，窗口类探测 + COM %s",
            int(self.config.get("presentation.poll_interval_ms", 400)),
            "/".join(COM_PROG_IDS),
        )
        self.ppt.start()

        if self.config.get("tray.notify_on_start", False):
            self.tray.notify(
                str(self.config.get("app.name", APP_NAME)),
                "已驻留托盘，点击图标打开快捷面板。",
            )

        log.info("进入事件循环")
        return self.qt_app.exec()

    # ================================================================ 动作

    def _on_shortcut(self, shortcut_id: str) -> None:
        """快捷方式分发。

        目前的动作都是「打开设置（可选落到某一页）」，格式
        ``open_settings:<相对 ui 的页面路径>``；不带页面的 ``open_settings``
        落在默认页。Luminalium 没有课表类功能，不再提供占位快捷方式。
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

        QTimer.singleShot(120, self.ppt.refresh_now)

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
