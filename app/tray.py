"""托盘常驻。

应用启动后默认只存在于托盘：不显示主窗口，左键点击托盘图标切换快捷面板，
右键弹出菜单。
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from PySide6.QtCore import QObject, QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .paths import ASSETS_DIR, RESOURCES_DIR

log = logging.getLogger(__name__)

# 品牌资源：``resources/logo.ico``（多尺寸，托盘 / 任务栏 / 标题栏都够用），
# 缺失时回落到 ``assets/icons/luminalium.svg``。
ICON_FILE = RESOURCES_DIR / "logo.ico"
FALLBACK_ICON_FILE = ASSETS_DIR / "icons" / "luminalium.svg"


def build_app_icon(size: int = 64) -> QIcon:
    """优先使用品牌图标，缺失时用 QPainter 现画一个，保证托盘一定有图标。"""
    for path in (ICON_FILE, FALLBACK_ICON_FILE):
        if path.exists():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return QIcon(_paint_fallback_pixmap(size))


def _paint_fallback_pixmap(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#4CC2FF"))
    gradient.setColorAt(1.0, QColor("#7A6BFF"))

    path = QPainterPath()
    path.addRoundedRect(1.0, 1.0, size - 2.0, size - 2.0, size * 0.26, size * 0.26)
    painter.fillPath(path, gradient)

    # 四角星（"光点"），象征 Luminalium
    cx = cy = size / 2.0
    outer = size * 0.26
    inner = outer * 0.30
    star = QPolygonF()
    for index in range(8):
        radius = outer if index % 2 == 0 else inner
        # 0° 朝上
        import math

        angle = math.radians(-90 + index * 45)
        star.append(QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    painter.setBrush(QColor("#FFFFFF"))
    painter.setPen(Qt.NoPen)
    painter.drawPolygon(star)
    painter.end()

    return pixmap


class TrayIcon(QObject):
    """系统托盘图标。"""

    panelToggleRequested = Signal()
    settingsRequested = Signal()
    quitRequested = Signal()
    diagnoseRequested = Signal()
    overlayToggleRequested = Signal()

    def __init__(self, tooltip: str = "Luminalium 2", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(build_app_icon(), self)
        self._tray.setToolTip(tooltip)
        self._menu = QMenu()
        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)

    # ------------------------------------------------------------------ api

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, build_app_icon(), 4000)

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    # ------------------------------------------------------------- internals

    def _build_menu(self) -> None:
        open_action = QAction("打开快捷面板", self._menu)
        open_action.triggered.connect(self.panelToggleRequested.emit)
        self._menu.addAction(open_action)

        settings_action = QAction("设置", self._menu)
        settings_action.triggered.connect(self.settingsRequested.emit)
        self._menu.addAction(settings_action)

        # 探测没认出放映窗口时的兜底：不依赖探测，直接把控制条叫出来
        overlay_action = QAction("显示/隐藏放映控制条（手动）", self._menu)
        overlay_action.triggered.connect(self.overlayToggleRequested.emit)
        self._menu.addAction(overlay_action)

        diagnose_action = QAction("诊断信息（写入日志）", self._menu)
        diagnose_action.triggered.connect(self.diagnoseRequested.emit)
        self._menu.addAction(diagnose_action)

        self._menu.addSeparator()

        quit_action = QAction("退出", self._menu)
        quit_action.triggered.connect(self.quitRequested.emit)
        self._menu.addAction(quit_action)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.panelToggleRequested.emit()
