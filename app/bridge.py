"""QML 桥接层。

QML 只依赖这里暴露的属性与槽函数，不直接触碰配置、Win32 或 PowerPoint 细节。
新增功能时通常只需要：加一个 ``Slot`` + 在 QML 里连上按钮。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication

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

#: 「翻页组件位置」的两种形态 -> 该形态下**启用**的角落。
#:
#: 改这一项会连带开关 ``corners`` 里对应的四个角：真实生效的仍是 ``corners``
#: （``windows.py::_load_docks`` 与编辑器预览都只读它），``pager.position``
#: 只是它的人话开关 —— 两种形态二选一，同时开会变成四个翻页栏。
PAGER_POSITION_CORNERS: Dict[str, tuple] = {
    "side": ("middle_left", "middle_right"),
    "bottom": ("bottom_left", "bottom_right"),
}


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
    presentationScreenChanged = Signal()
    quickPanelConfigChanged = Signal()
    settingsChanged = Signal()
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
        return self._config.get("presentation", {}) or {}

    presentationConfig = Property(
        "QVariantMap",
        _get_presentation_config,
        notify=presentationConfigChanged,
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
        # 只改内存 + 排一次延迟落盘（理由见 ``_save_timer`` 处的注释）。
        self._config.set(path, value, persist=False)
        self._save_timer.start()
        log.info("设置 %s = %r", path, value)

        # 翻页组件位置：连带开关四个角落（两种形态二选一，见常量处的说明）。
        # 真实生效的是 ``corners``，所以这一步不是「副作用」而是这个开关的本体。
        if key == "presentation_pager_position":
            self._apply_pager_position(str(value))
            self.docksRebuildRequested.emit()

        if key == "theme":
            self.themeChangeRequested.emit(str(value))
        elif key == "accent":
            self.accentChangeRequested.emit(str(value))
        if key in _BROADCAST_KEYS:
            self.quickPanelConfigChanged.emit()
        if key.startswith("presentation_"):
            self.presentationConfigChanged.emit()
            # 改 ``presentation_screen_index`` 会换一块显示器；还没放映过时
            # ``presentationScreen`` 是按配置现算的，得给它一个重取的理由。
            self.presentationScreenChanged.emit()
        self.settingsChanged.emit()

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
        """切换放映指针：``pen`` / ``eraser`` / ``arrow``。"""
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
