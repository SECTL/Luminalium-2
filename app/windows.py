"""窗口管理：快捷面板 + 放映「顶层窗口」。

只负责「创建、摆放、显隐」；所有业务参数由 QML 直接读取
:class:`~app.bridge.Backend` 暴露的配置，Python 侧不重复注入，
避免出现两处配置来源。

放映控制条（工具栏 / 翻页栏等）统一托管在**一个全屏置顶的顶层窗口**
（``ui/presentation/TopWindow.qml``）里：窗口整窗鼠标/触摸穿透，
仅当光标落在某个控制条表面矩形内时临时收回穿透，让工具栏可点。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QPoint, QRect, QRectF, QTimer, QUrl, Slot
from PySide6.QtGui import QCursor, QGuiApplication, QScreen
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickWindow

from .config import Config
from .paths import UI_DIR
from .ppt_controller import PptController

log = logging.getLogger(__name__)

# 角标识 -> (水平对齐, 垂直对齐)
# ``center`` 用于**独立于工具栏的居中组块**（默认布局：工具栏在下中部，
# 翻页栏左右各一只 pill）。
CORNERS: Dict[str, tuple[str, str]] = {
    "bottom_left": ("left", "bottom"),
    "bottom_right": ("right", "bottom"),
    "bottom_center": ("center", "bottom"),
    "top_left": ("left", "top"),
    "top_right": ("right", "top"),
    "top_center": ("center", "top"),
}

# ---------------------------------------------------------------- Win32 穿透
# 顶层窗口「除控制条以外的区域」鼠标/触摸穿透。首选方案是**区域塑形**
# （SetWindowRgn）：把全屏窗口裁成只有控制条那几块的形状，区域外既不绘制
# 也不参与命中测试 —— 由系统保证穿透，不需要任何轮询，也不可能出现
# 「整块屏幕吃掉点击」的假死态。轮询改样式只是塑形不可用时的兜底。
#
# ⚠️ 铁律：**绝不动 Qt 自己加的 WS_EX_LAYERED**。
# Qt 为了给顶层透明窗口画逐像素 alpha，自己会给窗口加 WS_EX_LAYERED 并走
# UpdateLayeredWindow 通道（实测 exstyle = 0x08080088）。任何外部干预都会让
# 它失效，症状就是「窗口存在、isVisible=True，但屏幕上什么都不画」：
#   * 剥掉这个 bit      —— UpdateLayeredWindow 调用全部报错，整窗隐形；
#   * 调 SetLayeredWindowAttributes —— 与 UpdateLayeredWindow **互斥**，同样隐形。
# 这两个坑本项目都踩过。正确做法：一个 bit 都不碰，透明渲染与点击穿透
# 互不干涉。
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020  # 仅兜底方案使用：整窗穿透（命中测试跳过）
WS_EX_LAYERED = 0x00080000      # Qt 透明窗口自带 —— 只读，用于自检与诊断
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
GW_HWNDFIRST = 0
GW_HWNDNEXT = 2
GW_HWNDPREV = 3
GW_OWNER = 4
RGN_OR = 2
DWMWA_CLOAKED = 14
_dwm_ready = True


def _window_ex_style(hwnd: int) -> int:
    if not hwnd or not hasattr(ctypes, "windll"):
        return 0
    try:
        value = ctypes.windll.user32.GetWindowLongW(
            wintypes.HWND(hwnd), GWL_EXSTYLE
        )
    except OSError:  # pragma: no cover
        return 0
    return value & 0xFFFFFFFF


def _set_window_ex_style(hwnd: int, style: int) -> None:
    if not hwnd or not hasattr(ctypes, "windll"):
        return
    try:
        ctypes.windll.user32.SetWindowLongW(
            wintypes.HWND(hwnd), GWL_EXSTYLE, style & 0xFFFFFFFF
        )
    except OSError:  # pragma: no cover
        log.debug("设置窗口扩展样式失败", exc_info=True)


def _window_rect(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """窗口在**物理像素**里的矩形 ``(x, y, w, h)``。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return None
    try:
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except OSError:  # pragma: no cover
        return None


def _native_window_rect_for(screen) -> tuple[int, int, int, int]:
    """把一块屏幕的 Qt 逻辑矩形换算成物理像素矩形。"""
    geometry = screen.geometry()
    dpr = screen.devicePixelRatio() or 1.0
    return (
        int(round(geometry.x() * dpr)),
        int(round(geometry.y() * dpr)),
        int(round(geometry.width() * dpr)),
        int(round(geometry.height() * dpr)),
    )


def _dwm_cloaked(hwnd: int) -> int:
    """``DWMWA_CLOAKED``：非 0 表示系统已把窗口「披风化」，永远不会被合成。"""
    global _dwm_ready
    if not hwnd or not hasattr(ctypes, "windll") or not _dwm_ready:
        return -1
    try:
        value = ctypes.c_int(0)
        ok = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), ctypes.c_uint(DWMWA_CLOAKED),
            ctypes.byref(value), ctypes.sizeof(value),
        )
        return int(value.value) if ok == 0 else -1
    except (OSError, AttributeError):  # pragma: no cover
        _dwm_ready = False
        return -1


def _is_window_visible(hwnd: int) -> bool:
    if not hwnd or not hasattr(ctypes, "windll"):
        return False
    return bool(ctypes.windll.user32.IsWindowVisible(wintypes.HWND(hwnd)))


def _zorder_above(top_hwnd: int, other_hwnd: int) -> Optional[bool]:
    """``top_hwnd`` 是否排在 ``other_hwnd`` 之上（z 序里更靠前 = 更上面）。

    从 ``other_hwnd`` **向上**走（``GW_HWNDPREV``），而不是从桌面枚举整条链再
    ``index()``：实测后者经常退化成 ``None``（桌面 500+ 顶层窗口，放映窗口
    又在频繁创建 / 销毁，枚举过程中链就变了 → 查不到 → 「不知道」）。
    从目标窗口出发只走它**上面**那一段，短、快、且不会漏。
    """
    if not hasattr(ctypes, "windll") or not top_hwnd or not other_hwnd:
        return None
    top_hwnd, other_hwnd = int(top_hwnd), int(other_hwnd)
    if top_hwnd == other_hwnd:
        return None
    user32 = ctypes.windll.user32
    hwnd = user32.GetWindow(wintypes.HWND(other_hwnd), GW_HWNDPREV)
    steps = 0
    while hwnd and steps < 4096:  # 防御：某些环境下的环形链表
        if int(hwnd) == top_hwnd:
            return True
        hwnd = user32.GetWindow(wintypes.HWND(hwnd), GW_HWNDPREV)
        steps += 1
    return False


# ------------------------------------------------------------------ 区域塑形

def _build_region(rects: list[tuple[int, int, int, int]]) -> Optional[int]:
    """把若干矩形 ``(x, y, w, h)`` 合并成一个 HRGN。失败返回 ``None``。"""
    if not hasattr(ctypes, "windll") or not rects:
        return None
    gdi32 = ctypes.windll.gdi32
    handles: list[int] = []
    result: Optional[int] = None
    for x, y, width, height in rects:
        if width <= 0 or height <= 0:
            continue
        hrgn = gdi32.CreateRectRgn(int(x), int(y), int(x + width), int(y + height))
        if not hrgn:
            continue
        handles.append(hrgn)
        if result is None:
            result = hrgn
        else:
            gdi32.CombineRgn(hrgn, result, hrgn, RGN_OR)
            result = hrgn
    if result is None:
        return None
    for hrgn in handles:
        if hrgn != result:
            gdi32.DeleteObject(hrgn)
    return result


def _set_window_region(hwnd: int, hrgn: Optional[int]) -> bool:
    """挂 / 摘窗口区域。``hrgn`` 为 ``None`` 表示恢复矩形窗口。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return False
    try:
        ok = ctypes.windll.user32.SetWindowRgn(
            wintypes.HWND(hwnd), wintypes.HRGN(hrgn) if hrgn else None, True
        )
        return bool(ok)
    except OSError:  # pragma: no cover
        log.debug("SetWindowRgn 失败", exc_info=True)
        return False


def _region_box(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """读回窗口当前区域的外接矩形 —— 用来校准 SetWindowRgn 的坐标单位。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return None
    try:
        gdi32 = ctypes.windll.gdi32
        hrgn = gdi32.CreateRectRgn(0, 0, 0, 0)
        if not hrgn:
            return None
        try:
            if ctypes.windll.user32.GetWindowRgn(wintypes.HWND(hwnd), hrgn) == 0:
                return None
            rect = wintypes.RECT()
            if gdi32.GetRgnBox(hrgn, ctypes.byref(rect)) == 0:
                return None
            return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        finally:
            gdi32.DeleteObject(hrgn)
    except OSError:  # pragma: no cover
        return None


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def monitor_rect_for_window(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """返回指定窗口所在显示器的**物理**矩形 ``(left, top, right, bottom)``。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return None
    try:
        user32 = ctypes.windll.user32
        monitor = user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)  # DEFAULTTONEAREST
        if not monitor:
            return None
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        rect = info.rcMonitor
        return (rect.left, rect.top, rect.right, rect.bottom)
    except OSError:  # pragma: no cover
        log.debug("获取显示器信息失败", exc_info=True)
        return None


class WindowManager(QObject):
    """集中管理所有顶层窗口。"""

    def __init__(
        self,
        engine,
        config: Config,
        backend,
        ppt: PptController,
        tray=None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._config = config
        self._backend = backend
        self._ppt = ppt
        self._tray = tray

        self.panel: Optional[QQuickWindow] = None
        self.settings: Optional[QQuickWindow] = None
        self.overlay: Optional[QQuickWindow] = None
        self._docks: Dict[str, QQuickItem] = {}
        self._components: List[QQmlComponent] = []

        # 输入模式：True = 区域塑形（首选，系统级穿透）；False = 整窗穿透轮询（兜底）
        self._region_mode = False
        self._region_scale: Optional[float] = None  # SetWindowRgn 的实际坐标单位倍率
        self._last_region_box: Optional[tuple[int, int, int, int]] = None

        # 顶层窗口是否至少显示过一次：没显示过的话 Win32 矩形还是 Qt 的默认
        # 160x160（诊断里看着像「窗口尺寸不对」，其实只是从未用过）
        self._overlay_ever_shown = False
        # 连续多少次自检发现「排在放映窗口之下」（用于告警，不是每次都刷屏）
        self._below_slideshow = 0
        # 手动显示（托盘菜单）：探测不到放映时也能把控制条叫出来
        self._manual_shown = False

        self._click_through = True
        self._hit_timer = QTimer(self)
        self._hit_timer.setInterval(
            max(10, int(self._config.get("presentation.hit_poll_ms", 25)))
        )
        self._hit_timer.timeout.connect(self._update_overlay_hit)

        # 放映窗口会重申自己的 TOPMOST，这里周期性压回去
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(
            max(200, int(self._config.get("presentation.topmost_interval_ms", 2000)))
        )
        self._topmost_timer.timeout.connect(self._assert_topmost)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(140)
        self._hide_timer.timeout.connect(self._maybe_hide_panel)

    # ================================================================== 装配

    def load_windows(self) -> None:
        if self.panel is None:
            self._create_panel()
        else:
            self._bind_panel()
        self._load_docks()
        self._wire_signals()

    # ---------------------------------------------------------------- 面板

    def attach_panel(self, window) -> None:
        """接入外部（RinUI 引擎）创建好的快捷面板窗口。"""
        if window is None or not hasattr(window, "show"):
            raise RuntimeError("快捷面板根节点必须是 Window")
        self.panel = window
        window.hide()

    def _bind_panel(self) -> None:
        try:
            self.panel.closing.connect(self._on_panel_closing)
        except (AttributeError, TypeError):  # pragma: no cover - 平台差异
            log.debug("无法连接窗口 closing 信号，改由 hide_on_deactivate 处理")
        self.panel.activeChanged.connect(self._on_panel_active_changed)

    def _create_panel(self) -> None:
        qml_path = UI_DIR / "QuickPanel.qml"
        root = self._create(qml_path, {"visible": False})
        if root is None or not hasattr(root, "show"):
            raise RuntimeError(f"快捷面板根节点必须是 Window: {qml_path}")
        self.panel = root
        self._bind_panel()

    def _on_panel_closing(self, *args: Any) -> None:
        """拦截关闭按钮：托盘常驻应用只隐藏，不销毁窗口。"""
        event = args[0] if args else None
        if event is not None and hasattr(event, "ignore"):
            event.ignore()
        self.hide_panel()

    def _on_panel_active_changed(self) -> None:
        if not self._config.get("quick_panel.hide_on_deactivate", True):
            return
        if self.panel is not None and not self.panel.isActive():
            self._hide_timer.start()

    def _maybe_hide_panel(self) -> None:
        if self.panel is not None and self.panel.isVisible() and not self.panel.isActive():
            self.hide_panel()

    # ---------------------------------------------------------------- 顶层窗口

    def _load_docks(self) -> None:
        """创建顶层窗口（全屏叠加层），并把各角落的控制条挂进去。

        控制条本体是 ``PresentationDock.qml`` 的 Item 实例，父级为
        顶层窗口的 ``container``；位置由 :meth:`_position_dock` 按角落计算。
        """
        overlay = self._create(UI_DIR / "presentation" / "TopWindow.qml", {})
        container = overlay.property("container") if overlay is not None else None
        if container is None:
            log.error("顶层窗口加载失败（缺 container 容器属性）")
            return
        self.overlay = overlay

        corners = self._config.get("presentation.corners", {}) or {}
        qml_path = UI_DIR / "presentation" / "PresentationDock.qml"
        for name in CORNERS:
            settings = corners.get(name) or {}
            if not settings.get("enabled", False):
                continue
            root = self._create(qml_path, {"corner": name})
            if root is None or not isinstance(root, QQuickItem):
                log.error("控制条加载失败: %s", name)
                continue
            root.setParentItem(container)
            root.widthChanged.connect(lambda *_, n=name: self._schedule_reposition(n))
            root.heightChanged.connect(lambda *_, n=name: self._schedule_reposition(n))
            self._docks[name] = root
        log.info(
            "顶层窗口已创建，控制条 x%d: %s", len(self._docks), list(self._docks)
        )

    # ------------------------------------------------------------- 组件工具

    def _create(self, qml_path, initial: Dict[str, Any]):
        component = QQmlComponent(self._engine, QUrl.fromLocalFile(str(qml_path)))
        self._components.append(component)
        if component.isError():
            for error in component.errors():
                log.error("QML 错误 [%s] %s", qml_path.name, error.toString())
            raise RuntimeError(f"QML 组件存在错误: {qml_path}")
        try:
            root = component.createWithInitialProperties(initial)
        except AttributeError:  # 老版本 PySide6 回退路径
            root = component.create()
            for key, value in initial.items():
                if root is not None:
                    root.setProperty(key, value)
        if root is None:
            for error in component.errors():
                log.error("QML 实例化失败 [%s] %s", qml_path.name, error.toString())
        return root

    def _schedule_reposition(self, corner: str) -> None:
        QTimer.singleShot(0, lambda: self._position_dock(corner))

    # ================================================================== 信号

    def _wire_signals(self) -> None:
        self._backend.panelHideRequested.connect(self.hide_panel)
        self._backend.settingsCloseRequested.connect(self.hide_settings)
        self._ppt.stateChanged.connect(self._on_presentation_state)

    def _on_presentation_state(self, state) -> None:
        self._backend.apply_state(state)
        if state.active:
            self.show_docks()
        else:
            self.hide_docks()

    # ================================================================== 面板

    def toggle_panel(self) -> None:
        if self.panel is None:
            return
        if self.panel.isVisible():
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self, pos: Optional[QPoint] = None) -> None:
        if self.panel is None:
            return
        self._position_panel(pos)
        self.panel.show()
        self.panel.raise_()
        self.panel.requestActivate()

    def hide_panel(self) -> None:
        if self.panel is not None and self.panel.isVisible():
            self.panel.hide()

    def _position_panel(self, pos: Optional[QPoint] = None) -> None:
        """把面板摆到**光标**附近。

        这是 Class Widgets 2 ``TrayPanel.qml`` 的 ``onTogglePanel(pos)`` 做法：
        光标下方 ``offset_y`` 处、水平居中对齐；下方放不下就翻到光标上方，
        再整体夹取进屏幕可用区。

        为什么不用 ``QSystemTrayIcon.geometry()``：Windows 上 Qt 返回的是空矩形
        （macOS 才有实现），拿它当锚点只会退化成「屏幕正中」，看起来像没对齐。
        """
        if self.panel is None:
            return

        width, height = self.panel.width(), self.panel.height()
        anchor = pos if pos is not None else QCursor.pos()
        offset_y = int(self._config.get("quick_panel.offset_y", 30))
        margin = 12

        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()

        x = anchor.x() - width // 2
        y = anchor.y() + offset_y
        # 下方放不下（托盘在屏幕底部）才翻到光标上方；但**只有翻上去确实放得下才翻** ——
        # 否则「翻了也放不下」会被后面的夹取推到屏幕顶上，看起来像面板跑掉了。
        if y + height > area.bottom():
            flipped = anchor.y() - height - offset_y
            if flipped >= area.top():
                y = flipped

        x = max(area.left() + margin, min(x, area.right() - width - margin))
        y = max(area.top() + margin, min(y, area.bottom() - height - margin))
        self.panel.setPosition(int(x), int(y))

    # ================================================================ 设置窗口

    def _create_settings(self) -> None:
        """按需创建设置窗口。

        不在启动时建：``FluentWindow`` 会连带建出导航栏 / 内容层 / 页面栈，
        托盘常驻应用里没必要为一个可能一直不开的窗口付这份开销。
        """
        if self.settings is not None:
            return
        qml_path = UI_DIR / "Settings.qml"
        if not qml_path.exists():
            log.warning("设置界面不存在，跳过: %s", qml_path)
            return
        root = self._create(qml_path, {"visible": False})
        if root is None:
            log.error("设置窗口创建失败: %s", qml_path)
            return
        self.settings = root

    def toggle_settings(self) -> None:
        if self.settings is not None and self.settings.isVisible():
            self.hide_settings()
        else:
            self.show_settings()

    def show_settings(self, page: str = "") -> None:
        """打开设置窗口；``page`` 为 ``ui`` 下相对路径（可空 = 默认页）。

        页面跳转通过 QML 侧 ``Settings.qml::openPage()``（内部走
        ``NavigationView.push``）。用 ``QMetaObject.invokeMethod`` 调，
        因为 QML 函数不在 Python 的静态元对象里。
        """
        self._create_settings()
        if self.settings is None:
            log.info("设置界面不可用")
            return
        self._position_settings()
        self.settings.show()
        self.settings.raise_()
        self.settings.requestActivate()
        if page:
            resolved = (UI_DIR / page).as_posix()
            # PySide6 没有 QVariant 类型可导入；Q_ARG 接受类型名字符串。
            # 包 try：QML 侧函数缺失 / 参数不匹配只记日志，不能炸掉事件循环。
            def _invoke() -> None:
                try:
                    QMetaObject.invokeMethod(
                        self.settings, "openPage", Q_ARG("QVariant", "file:///" + resolved)
                    )
                except Exception:
                    log.error("跳转设置页失败: %s", page, exc_info=True)

            QTimer.singleShot(0, _invoke)

    def hide_settings(self) -> None:
        if self.settings is not None and self.settings.isVisible():
            self.settings.hide()

    def _position_settings(self) -> None:
        """居中到光标所在显示器（不是主屏），多屏时不会跑到别的屏幕上。"""
        if self.settings is None:
            return
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.left() + (area.width() - self.settings.width()) // 2
        y = area.top() + (area.height() - self.settings.height()) // 2
        self.settings.setPosition(int(x), int(y))

    # ================================================================ 顶层窗口

    def show_docks(self) -> None:
        """放映开始：顶层窗口全屏铺到放映所在显示器，控制条落到各角落。

        顺序很重要：**先定屏 → 再全屏 → 再摆控制条 → 最后才谈穿透**。
        """
        if not self._config.get("presentation.enabled", True):
            return
        if self.overlay is None:
            log.warning("顶层窗口未创建，无法显示控制条")
            return
        screen = self._presentation_screen()
        if screen is None:
            log.warning("找不到放映所在显示器，控制条未显示")
            return

        # 先把「这只窗口属于哪块屏」告诉 Qt：多屏 / 多 DPI 时代 Window 的
        # 逻辑↔物理换算依赖它，漏了这一步窗口可能被摆到别的屏幕上。
        try:
            self.overlay.setScreen(screen)
        except Exception:  # pragma: no cover - 平台差异
            log.debug("setScreen 失败", exc_info=True)
        self.overlay.setGeometry(screen.geometry())
        for name in self._docks:
            self._position_dock(name)

        self.overlay.show()
        self._overlay_ever_shown = True
        self._apply_overlay_base_styles(transparent=False)
        self._assert_topmost()
        self._sync_input_mode()

        self._topmost_timer.start()
        QTimer.singleShot(0, self.reposition_all_docks)
        # 放映窗口刚起来时会重申 z 序；等它安顿完再压一次顶并自检
        QTimer.singleShot(300, self._assert_topmost)
        QTimer.singleShot(int(self._config.get("presentation.verify_after_ms", 500)),
                          lambda: self._verify_overlay(False))

        log.info(
            "顶层窗口显示于屏幕 %s（请求 geometry=%s），控制条 x%d",
            screen.name(), screen.geometry(), len(self._docks),
        )

    def toggle_docks_manual(self) -> None:
        """手动显示 / 隐藏控制条（托盘菜单）。

        探测没认出放映窗口时用来兜底：不依赖任何探测结果，直接按当前配置
        把顶层窗口叫出来，用来区分「探测没认出来」和「窗口画不出来」。
        """
        if self.overlay is None:
            log.warning("顶层窗口未创建，无法显示控制条")
            return
        if self.overlay.isVisible():
            self._manual_shown = False
            self.hide_docks()
            return
        self._manual_shown = True
        self.show_docks()

    def hide_docks(self) -> None:
        """放映结束：收起顶层窗口（穿透状态复位，轮询停止）。"""
        self._hit_timer.stop()
        self._topmost_timer.stop()
        self._manual_shown = False
        self._below_slideshow = 0
        if self.overlay is not None and self.overlay.isVisible():
            if self.overlay.isVisible():
                _set_window_region(int(self.overlay.winId()), None)
            self._last_region_box = None
            self.overlay.hide()
        self._click_through = True

    def reposition_all_docks(self) -> None:
        for name in self._docks:
            self._position_dock(name)
        self._sync_input_mode()

    def _position_dock(self, corner: str) -> None:
        """把控制条摆到顶层窗口容器内的对应角落。

        坐标是**顶层窗口局部**坐标（顶层窗口全屏铺在放映所在显示器，
        原点 = 屏幕 geometry 左上角）；工具栏仍按可用区（避开任务栏）摆放。
        控制条 Item 自带投影余量（shadowMargin），所以视觉贴边距离 =
        margin + shadowMargin，与旧的多窗口方案一致。
        """
        dock = self._docks.get(corner)
        if dock is None or self.overlay is None:
            return
        horizontal, vertical = CORNERS.get(corner, ("left", "bottom"))
        margin_x = int(self._config.get("presentation.margin_x", 32))
        margin_y = int(self._config.get("presentation.margin_y", 32))

        screen = self._presentation_screen()
        if screen is None:
            return
        origin = screen.geometry().topLeft()
        area = screen.availableGeometry().translated(-origin)

        if horizontal == "left":
            x = area.left() + margin_x
        elif horizontal == "center":
            # 居中按可用区（避开任务栏）算，不用整屏几何
            x = area.left() + (area.width() - dock.width()) // 2
        else:
            x = area.right() - dock.width() - margin_x
        if vertical == "top":
            y = area.top() + margin_y
        else:
            y = area.bottom() - dock.height() - margin_y
        dock.setX(x)
        dock.setY(y)

    # ------------------------------------------------------- 穿透 / 可见性

    def _apply_overlay_base_styles(self, transparent: bool) -> None:
        """给顶层窗口设置扩展样式。

        **只加不减**：``WS_EX_NOACTIVATE``（点按钮不抢放映窗口焦点）与可选的
        ``WS_EX_TRANSPARENT``。

        ⚠️ ``WS_EX_LAYERED`` 是 Qt 自己加的，一个 bit 都不能动 —— 剥掉它、
        或额外调 ``SetLayeredWindowAttributes``，都会让 Qt 的逐像素 alpha
        通道失效，结果是「窗口存在、isVisible=True，但整窗不画」。
        """
        if self.overlay is None:
            return
        hwnd = int(self.overlay.winId())
        if not hwnd:
            return
        style = _window_ex_style(hwnd)
        style |= WS_EX_NOACTIVATE
        if transparent:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        _set_window_ex_style(hwnd, style)

    def _assert_topmost(self) -> None:
        """把顶层窗口压回 TOPMOST。

        PowerPoint 的放映窗口本身也是 TOPMOST，且在启动 / 翻页时会
        重申自己的 z 序；我们的窗口必须周期性地压回去，否则会被放映
        窗口盖住（表现同样为「看不到控制条」）。
        """
        if self.overlay is None or not self.overlay.isVisible():
            return
        hwnd = int(self.overlay.winId()) if self.overlay is not None else 0
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(int(self.overlay.winId())),
                wintypes.HWND(HWND_TOPMOST),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        except OSError:  # pragma: no cover
            log.debug("SetWindowPos 重申置顶失败", exc_info=True)
        self._check_zorder()
        self._sync_input_mode()
        self._verify_overlay(verbose=False)

    def _check_zorder(self) -> None:
        """对照放映窗口检查 z 序：压不上去时明确告警。

        ``SetWindowPos(HWND_TOPMOST)`` 把窗口放到置顶层顶端，但放映窗口同样
        是 TOPMOST 且会自己重申；压不过去的表现就是「窗口可见但被盖住」。
        这里不猜，直接问系统：同一顶层序列里我们排在它前面还是后面。
        """
        slideshow = self._ppt.state.window_handle
        if not slideshow:
            self._below_slideshow = 0
            return
        hwnd = int(self.overlay.winId())
        if not hwnd or hwnd == slideshow:
            return
        if _zorder_above(hwnd, slideshow) is False:
            self._below_slideshow += 1
            if self._below_slideshow >= 3:
                # 已经重申过多次仍然在下面：不是竞态，是压根压不过去
                log.error(
                    "顶层窗口排在放映窗口(0x%08X)之下，重申置顶 %d 次仍失败；"
                    "放映程序可能用了独占呈现，或它的窗口重申频率高于本应用",
                    slideshow, self._below_slideshow,
                )
        else:
            self._below_slideshow = 0

    def _set_overlay_click_through(self, through: bool) -> None:
        """切换整窗穿透；状态不变时不写（避免高频 SetWindowLong）。"""
        if self.overlay is None or self._click_through == through:
            return
        hwnd = int(self.overlay.winId())
        style = _window_ex_style(hwnd)
        if through:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        _set_window_ex_style(hwnd, style)
        self._click_through = through

    def _dock_global_rect(self, dock: QQuickItem) -> QRect:
        """控制条表面（不含投影余量）在**全局逻辑坐标**里的矩形。"""
        origin = self.overlay.position() if self.overlay is not None else QPoint(0, 0)
        scene_origin = dock.mapToScene(QPoint(0, 0)).toPoint()
        rect = dock.property("interactiveRect")
        if rect is None:  # pragma: no cover - QML 属性缺失时退化为整个 Item
            scene = dock.mapRectToScene(
                QRectF(0, 0, dock.width(), dock.height())
            ).toRect()
            return QRect(origin.x() + scene.x(), origin.y() + scene.y(),
                         scene.width(), scene.height())
        inner = rect.toRect()
        return QRect(
            origin.x() + scene_origin.x() + inner.x(),
            origin.y() + scene_origin.y() + inner.y(),
            inner.width(),
            inner.height(),
        )

    def _update_overlay_hit(self, pos: Optional[QPoint] = None) -> None:
        """兜底方案：光标在控制条表面内 → 收回穿透；否则恢复整窗穿透。

        区域塑形生效时这个方法不做事（遍历一次只是浪费）。
        ``pos`` 参数供自检注入（不挪动真实光标）。
        """
        if self._region_mode:
            return
        if self.overlay is None or not self.overlay.isVisible():
            return
        cursor = pos if pos is not None else QCursor.pos()
        hit = False
        for dock in self._docks.values():
            if dock.isVisible() and self._dock_global_rect(dock).contains(cursor):
                hit = True
                break
        self._set_overlay_click_through(not hit)

    # ---------------------------------------------------------- 区域塑形

    def _dock_rects_local(self) -> list[tuple[int, int, int, int]]:
        """各控制条表面矩形（顶层窗口局部坐标，逻辑像素）。"""
        if self.overlay is None:
            return []
        padding = int(self._config.get("presentation.region_padding", 20))
        origin = self.overlay.position()
        limit_w = int(self.overlay.width())
        limit_h = int(self.overlay.height())
        rects: list[tuple[int, int, int, int]] = []
        for dock in self._docks.values():
            if not dock.isVisible():
                continue
            rect = self._dock_global_rect(dock)
            x = max(0, rect.x() - origin.x() - padding)
            y = max(0, rect.y() - origin.y() - padding)
            right = min(limit_w, rect.right() - origin.x() + padding)
            bottom = min(limit_h, rect.bottom() - origin.y() + padding)
            if right > x and bottom > y:
                rects.append((x, y, right - x, bottom - y))
        return rects

    def _update_overlay_region(self) -> Optional[float]:
        """把顶层窗口裁成「只有控制条」的形状，返回实际生效的坐标倍率。

        ``SetWindowRgn`` 的坐标单位（逻辑 vs 物理）跟进程 DPI 模式有关，
        **不猜**：先按候选倍率设一次、再用 ``GetWindowRgn + GetRgnBox``
        读回外接矩形对照，对不上就换下一个候选。
        """
        if self.overlay is None or not self.overlay.isVisible():
            return None
        rects = self._dock_rects_local()
        if not rects:
            return None
        hwnd = int(self.overlay.winId())
        if not hwnd:
            return None

        box = (
            min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects),
        )
        if self._last_region_box == box and self._region_scale is not None:
            return self._region_scale

        dpr = self.overlay.devicePixelRatio() or 1.0
        candidates = [self._region_scale, dpr, 1.0] if self._region_scale else [dpr, 1.0]
        for scale in candidates:
            if not scale or scale <= 0:
                continue
            hrgn = _build_region([(r[0] * scale, r[1] * scale,
                                   r[2] * scale, r[3] * scale) for r in rects])
            if hrgn is None:
                continue
            if not _set_window_region(hwnd, hrgn):
                ctypes.windll.gdi32.DeleteObject(hrgn)
                continue
            actual = _region_box(hwnd)
            expected_w = int((box[2] - box[0]) * scale)
            expected_h = int((box[3] - box[1]) * scale)
            if actual is None or abs(actual[2] - expected_w) > 2 or abs(actual[3] - expected_h) > 2:
                continue
            self._region_scale = scale
            self._last_region_box = box
            # 改了区域 Qt 不一定知道：显式要一帧，避免第一屏画不出来
            try:
                self.overlay.requestUpdate()
            except (AttributeError, RuntimeError):  # pragma: no cover
                pass
            return scale
        log.warning("顶层窗口区域塑形失败（坐标单位未校准），将退回整窗穿透轮询")
        return None

    def _sync_input_mode(self) -> None:
        """选择穿透方案：区域塑形优先，失败才退回轮询改样式。"""
        if self.overlay is None or not self.overlay.isVisible():
            return
        scale = self._update_overlay_region()
        if scale is not None:
            if not self._region_mode:
                self._region_mode = True
                self._hit_timer.stop()
                log.info(
                    "顶层窗口已按控制条形状裁剪（区域塑形，坐标倍率 %.2f），其余区域系统级穿透",
                    scale,
                )
            self._apply_overlay_base_styles(transparent=False)
            return
        # 兜底
        if self._region_mode:
            log.warning("区域塑形失效，退回整窗穿透轮询")
        self._region_mode = False
        if self._config.get("presentation.pass_through", True):
            self._apply_overlay_base_styles(transparent=True)
            self._click_through = True
            self._hit_timer.start()
        else:
            self._apply_overlay_base_styles(transparent=False)

    # ---------------------------------------------------------- 自检诊断

    def overlay_report(self) -> str:
        """一行 diagnosis：把「为什么看不见」需要的证据全部写进日志。"""
        if self.overlay is None:
            return "顶层窗口未创建"
        try:
            hwnd = int(self.overlay.winId())
        except RuntimeError:  # pragma: no cover - 对象已销毁
            return "顶层窗口已销毁"
        if not hwnd:
            return "顶层窗口还没有 native handle"
        style = _window_ex_style(hwnd)
        rect = _window_rect(hwnd)
        cloaked = _dwm_cloaked(hwnd)
        region = _region_box(hwnd)
        slideshow = self._ppt.state.window_handle
        above = _zorder_above(hwnd, slideshow) if slideshow else None
        return (
            f"hwnd=0x{hwnd:08X} visible={self.overlay.isVisible()}/"
            f"Win32={_is_window_visible(hwnd)} rect={rect} expected={self._expected_native_rect()} "
            f"exstyle=0x{style:08X}[LAYERED={'Y' if style & WS_EX_LAYERED else 'N'} "
            f"TRANSPARENT={'Y' if style & WS_EX_TRANSPARENT else 'N'}] "
            f"cloaked={cloaked} region={region} 区域塑形={self._region_mode} "
            f"above_slideshow={above} (slideshow=0x{slideshow:08X}) "
            f"显示过={self._overlay_ever_shown} 手动={self._manual_shown}"
        )

    def overlay_hint(self) -> str:
        """一句人话结论：把 report 里的数字翻成「下一步该干什么」。"""
        if self.overlay is None:
            return "顶层窗口未创建"
        if not self.overlay.isVisible():
            if not self._overlay_ever_shown:
                return ("顶层窗口从未显示过（Win32 矩形仍是 Qt 默认 160x160）——"
                        "探测没有进入放映态，先看上面有没有「放映开始」")
            return "顶层窗口当前处于隐藏状态（未检测到放映）"
        if self._below_slideshow >= 3:
            return "顶层窗口被放映窗口压住了，且重申置顶无效（见上面的 z 序告警）"
        cloaked = _dwm_cloaked(int(self.overlay.winId()))
        if cloaked != 0:
            return f"顶层窗口被 DWM 披风化（cloaked={cloaked}），系统不会合成它"
        return "顶层窗口已显示且未被压住；若屏幕上看不到，属于该屏/演示程序的呈现限制"

    def _expected_native_rect(self) -> Optional[tuple[int, int, int, int]]:
        screen = self._presentation_screen()
        return _native_window_rect_for(screen) if screen is not None else None

    def _verify_overlay(self, verbose: bool = True) -> bool:
        """把实际窗口状态与目标对照；不一致就重申几何 / 置顶并记日志。"""
        if self.overlay is None or not self.overlay.isVisible():
            return False
        hwnd = int(self.overlay.winId())
        expected = self._expected_native_rect()
        actual = _window_rect(hwnd)
        ok = True
        if expected and actual and (
            abs(actual[0] - expected[0]) > 4 or abs(actual[1] - expected[1]) > 4
            or abs(actual[2] - expected[2]) > 4 or abs(actual[3] - expected[3]) > 4
        ):
            ok = False
            # Qt 的逻辑坐标没落到预期位置：直接用原生 SetWindowPos 纠正
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(hwnd), wintypes.HWND(HWND_TOPMOST),
                expected[0], expected[1], expected[2], expected[3],
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            log.warning(
                "顶层窗口实际位置 %s 与目标 %s 不符，已用 SetWindowPos 纠正",
                actual, expected,
            )
        if _dwm_cloaked(hwnd) != 0:
            ok = False
            log.error("顶层窗口被系统披风化（cloaked），DWM 不会合成它")
        if expected and hwnd and not _is_window_visible(hwnd):
            ok = False
            log.error("顶层窗口 Win32 层面不可见（IsWindowVisible=0）")
        if verbose or not ok:
            log.info("顶层窗口自检: %s", self.overlay_report())
        return ok

    def _presentation_screen(self) -> Optional[QScreen]:
        """优先跟随放映窗口所在显示器，其次按配置索引，最后回退主屏。

        窗口类是**物理**三角形给出的（``MonitorFromWindow`` 的 ``MONITORINFO``），
        Qt 侧则是逻辑矩形；混用会错位。这里把每块屏的逻辑矩形换算回物理再去比，
        而不是拿主屏的 DPR 去除 —— 多屏不同缩放倍率时后者会打偏到别的屏幕，
        控制条就被画到你看不见的地方去了。
        """
        rect = monitor_rect_for_window(self._ppt.state.window_handle)
        if rect is not None:
            screens = QGuiApplication.screens()
            for screen in screens:
                if _native_window_rect_for(screen) == tuple(rect):
                    return screen
            # 兜底：按物理中心点命中（整除误差不影响归属判断）
            center_x = (rect[0] + rect[2]) // 2
            center_y = (rect[1] + rect[3]) // 2
            for screen in screens:
                x, y, width, height = _native_window_rect_for(screen)
                if x <= center_x < x + width and y <= center_y < y + height:
                    return screen

        index = int(self._config.get("presentation.screen_index", -1))
        screens = QGuiApplication.screens()
        if 0 <= index < len(screens):
            return screens[index]
        return QGuiApplication.primaryScreen()

    # ================================================================== 收尾

    def shutdown(self) -> None:
        self.hide_panel()
        self.hide_settings()
        self.hide_docks()
        self._docks.clear()
        self._components.clear()
        self.panel = None
        self.settings = None
        self.overlay = None
