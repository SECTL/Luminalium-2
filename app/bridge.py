"""QML 桥接层。

QML 只依赖这里暴露的属性与槽函数，不直接触碰配置、Win32 或 PowerPoint 细节。
新增功能时通常只需要：加一个 ``Slot`` + 在 QML 里连上按钮。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtCore import QUrl

from .config import Config
from .paths import RESOURCES_DIR, UI_DIR
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
    "tray_enabled": "tray.enabled",
    "tray_tooltip": "tray.tooltip",
    "tray_show_on_click": "tray.show_on_click",
    "tray_notify_on_start": "tray.notify_on_start",
    "panel_width": "quick_panel.width",
    "panel_height": "quick_panel.height",
    "panel_offset_y": "quick_panel.offset_y",
    "panel_hide_on_deactivate": "quick_panel.hide_on_deactivate",
    "panel_shortcuts_locked": "quick_panel.shortcuts_locked",
    "panel_section_shortcuts": "quick_panel.sections.shortcuts",
    "panel_section_status": "quick_panel.sections.status",
    "panel_section_footer": "quick_panel.sections.footer",
    "presentation_enabled": "presentation.enabled",
    "presentation_poll_interval_ms": "presentation.poll_interval_ms",
    "presentation_margin_x": "presentation.margin_x",
    "presentation_margin_y": "presentation.margin_y",
    "presentation_bar_height": "presentation.bar_height",
    "presentation_screen_index": "presentation.screen_index",
    "presentation_shadow_enabled": "presentation.surface.shadow.enabled",
    "presentation_divider_enabled": "presentation.divider.enabled",
    "presentation_pager_enabled": "presentation.pager.enabled",
}

#: 值一变就需要 QML 重新取整块配置的键。
_BROADCAST_KEYS = {"panel_width", "panel_height", "panel_section_shortcuts",
                   "panel_section_status", "panel_section_footer"}


class Backend(QObject):
    """面向 QML 的应用后端。"""

    # ---- 通知类信号 ----
    presentationActiveChanged = Signal()
    slideChanged = Signal()
    activeToolChanged = Signal()
    shortcutsChanged = Signal()
    presentationConfigChanged = Signal()
    quickPanelConfigChanged = Signal()
    settingsChanged = Signal()
    statusChanged = Signal()

    # ---- 请求类信号（由窗口管理器 / 应用层响应）----
    panelHideRequested = Signal()
    shortcutTriggered = Signal(str)
    actionTriggered = Signal(str)
    reloadRequested = Signal()
    quitRequested = Signal()
    settingsRequested = Signal()
    settingsCloseRequested = Signal()
    themeChangeRequested = Signal(str)
    accentChangeRequested = Signal(str)

    def __init__(self, config: Config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config

        self._presentation_active = False
        self._slide_index = 0
        self._slide_total = 0
        self._active_tool = "pen"
        self._status_text = ""

        #: 已启用的快捷方式 id（顺序即显示顺序）
        self._shortcut_ids: List[str] = [
            str(item) for item in (config.get("quick_panel.shortcuts", []) or [])
        ]


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

    @Slot(str, result=str)
    def resourceFile(self, name: str) -> str:
        """``resources/`` 下某个品牌资源（logo.svg / logo.ico / banner.png）的
        ``file:///`` URL。

        QML 的 ``Image.source`` 不吃相对路径（基准是 QML 文件所在目录），
        所以统一在这里拼绝对 URL。
        """
        return QUrl.fromLocalFile(str(RESOURCES_DIR / name)).toString()

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
        return self._config.get("presentation", {}) or {}

    presentationConfig = Property(
        "QVariantMap",
        _get_presentation_config,
        notify=presentationConfigChanged,
    )

    def _get_quick_panel_config(self) -> Dict[str, Any]:
        return self._config.get("quick_panel", {}) or {}

    quickPanelConfig = Property(
        "QVariantMap",
        _get_quick_panel_config,
        notify=quickPanelConfigChanged,
    )

    # ============================================================ 快捷方式清单

    def _catalog(self) -> List[Dict[str, Any]]:
        """全部可用的快捷方式（``shortcut_catalog``）。"""
        return list(self._config.get("quick_panel.shortcut_catalog", []) or [])

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

    def _get_settings(self) -> Dict[str, Any]:
        return {key: self._config.get(path) for key, path in SETTING_PATHS.items()}

    settings = Property("QVariantMap", _get_settings, notify=settingsChanged)

    def _get_settings_config(self) -> Dict[str, Any]:
        return self._config.get("settings", {}) or {}

    settingsConfig = Property(
        "QVariantMap", _get_settings_config, notify=settingsChanged
    )

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        """改一项设置。类型按默认值对齐，避免 QML 把 int 传成字符串。"""
        path = SETTING_PATHS.get(key)
        if path is None:
            log.info("未知设置项: %s", key)
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
        self._config.set(path, value)
        log.info("设置 %s = %r", path, value)

        if key == "theme":
            self.themeChangeRequested.emit(str(value))
        elif key == "accent":
            self.accentChangeRequested.emit(str(value))
        if key in _BROADCAST_KEYS:
            self.quickPanelConfigChanged.emit()
        if key.startswith("presentation_"):
            self.presentationConfigChanged.emit()
        self.settingsChanged.emit()

    @Slot()
    def closeSettings(self) -> None:
        self.settingsCloseRequested.emit()

    def reload_from_config(self) -> None:
        self._shortcut_ids = [
            str(item) for item in (self._config.get("quick_panel.shortcuts", []) or [])
        ]
        self.shortcutsChanged.emit()
        self.settingsChanged.emit()
        self.presentationConfigChanged.emit()
        self.quickPanelConfigChanged.emit()

    # ============================================================ 放映控制槽

    @Slot(str)
    def selectTool(self, tool: str) -> None:
        """切换放映指针：``pen`` / ``eraser`` / ``arrow``。"""
        if tool not in ("pen", "eraser", "arrow"):
            return
        if tool != self._active_tool:
            self._active_tool = tool
            self.activeToolChanged.emit()
        self.actionTriggered.emit(f"tool:{tool}")

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
    def requestReload(self) -> None:
        self.reloadRequested.emit()

    @Slot()
    def requestQuit(self) -> None:
        self.quitRequested.emit()

    @Slot()
    def hidePanel(self) -> None:
        self.panelHideRequested.emit()

    # ------------------------------------------------------------------ 工具

    @Slot(result=str)
    def describeSlideProgress(self) -> str:
        if not self._presentation_active:
            return "未在放映"
        if self._slide_total <= 0:
            return "放映中"
        return f"{self._slide_index}/{self._slide_total}"
