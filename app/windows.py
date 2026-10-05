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

from PySide6.QtCore import (
    Q_ARG,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    Slot,
)
from PySide6.QtGui import QCursor, QGuiApplication, QScreen
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickWindow

from .config import Config
from .paths import UI_DIR
from .ppt_controller import PptController

log = logging.getLogger(__name__)

# 角标识 -> (水平对齐, 垂直对齐)
# ``center`` 用于**独立于工具栏的居中组块**（默认布局：工具栏在下中部，
# 翻页栏左右各一只 pill）；``middle`` 用于**竖版两侧翻页**（屏幕左右边缘、
# 垂直居中 —— Luminalium 1 ``.flipper`` 的默认形态）。
CORNERS: Dict[str, tuple[str, str]] = {
    "bottom_left": ("left", "bottom"),
    "bottom_right": ("right", "bottom"),
    "bottom_center": ("center", "bottom"),
    "top_left": ("left", "top"),
    "top_right": ("right", "top"),
    "top_center": ("center", "top"),
    "middle_left": ("left", "middle"),
    "middle_right": ("right", "middle"),
}

#: 亚克力在窗口**显示之后**要补打的那一拍（毫秒）。
#: 实测：``show()`` 之后的 ~200ms 内系统会把 ``DWMWA_SYSTEMBACKDROP_TYPE``
#: 重置回 0（Qt 首次展示时的平台窗口初始化会重新应用 frame），之后重打即稳定。
ACRYLIC_REAPPLY_MS = 320

#: 快捷面板弹出时，面板顶边在光标下方多少像素（CW2 的托盘面板惯例 30）。
#: 2026-10-01 起是**常量**：原 ``quick_panel.offset_y`` 配置键连同设置项一起
#: 按用户指令删除，位置行为不再可配（光标锚定行为本身保留）。
PANEL_OFFSET_Y = 30

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
WS_EX_TOPMOST = 0x00000008
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

# ---- DWM 系统背景材质（Win11 22H2 / build 22621 起可用）----
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_SYSTEMBACKDROP_TYPE = 38
#: ``DWMSBT_TRANSIENTWINDOW`` —— 也就是「亚克力」。
DWMSBT_TRANSIENTWINDOW = 3
#: ``DWMWA_COLOR_NONE`` —— 让 DWM 不要给该处上色（既用于边框也用于标题栏）。
DWMWA_COLOR_NONE = 0xFFFFFFFE
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


class _Margins(ctypes.Structure):
    """``DwmExtendFrameIntoClientArea`` 的 ``MARGINS``。"""

    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
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


def _covers_monitor(hwnd: int, ratio: float = 0.9) -> bool:
    """窗口是否铺满它所在的显示器（面积占比 ≥ ``ratio``）。"""
    rect = _window_rect(hwnd)
    monitor = monitor_rect_for_window(hwnd)
    if rect is None or monitor is None:
        return False
    win_area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
    mon_area = max(1, (monitor[2] - monitor[0]) * (monitor[3] - monitor[1]))
    return win_area / mon_area >= ratio


class WindowManager(QObject):
    """集中管理所有顶层窗口。"""

    def __init__(
        self,
        engine,
        config: Config,
        backend,
        ppt: PptController,
        tray=None,
        rinui=None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._config = config
        self._backend = backend
        self._ppt = ppt
        self._tray = tray
        #: ``RinUIWindow`` 实例 —— 用于把 Python 侧另建的窗口补登记进 RinUI
        #: 的 WinEventFilter / ThemeManager / WinEventManager（见 ``_attach_to_rinui``）
        self._rinui = rinui
        self._rinui_windows: List[Any] = list(rinui.windows) if rinui is not None else []
        self._rinui_hooked: List[Any] = []

        self.panel: Optional[QQuickWindow] = None
        #: 启动画面（只在启动阶段存在，淡出后销毁）
        self.splash: Optional[QQuickWindow] = None
        self.settings: Optional[QQuickWindow] = None
        #: 调试窗口（隐藏入口：设置窗口标题连点 10 次）
        self.debug: Optional[QQuickWindow] = None
        #: 主界面编辑器（入口：快捷面板的「主界面编辑器」快捷方式）
        self.editor: Optional[QQuickWindow] = None
        #: 错误 / 崩溃报告（入口：``ErrorHandler`` 捕获到未捕获异常）
        self.error_report: Optional[QQuickWindow] = None
        self.overlay: Optional[QQuickWindow] = None
        self._docks: Dict[str, QQuickItem] = {}
        self._components: List[QQmlComponent] = []

        # 输入模式：True = 区域塑形（首选，系统级穿透）；False = 整窗穿透轮询（兜底）
        self._region_mode = False
        self._region_scale: Optional[float] = None  # SetWindowRgn 的实际坐标单位倍率
        # 上次**实际应用**到 Win32 区域的矩形集 —— 判据必须是 rects 本身：
        # 2026-10-01 实锤，用外接 box 当判据会漏掉「新块完全落在旧外接矩形
        # **内部**」的变化（笔选单：左右竖版翻页块从 y=383 就开始了，比卡片
        # 顶 578 更靠上 → 加进卡片后 box 纹丝不动 → 被当成「区域没变」短路，
        # 卡片那块从未进过 Win32 区域，账面对、屏幕上整块画不出来）。
        self._last_region_rects: Optional[tuple[tuple[int, int, int, int], ...]] = None

        # 顶层窗口是否至少显示过一次：没显示过的话 Win32 矩形还是 Qt 的默认
        # 160x160（诊断里看着像「窗口尺寸不对」，其实只是从未用过）
        self._overlay_ever_shown = False
        # 连续多少次自检发现「排在放映窗口之下」（用于告警，不是每次都刷屏）
        self._below_slideshow = 0
        # 置顶层里排在我们之上的窗口集合签名（变化才告警一次）
        self._above_sig = ""
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
        # 关闭拦截写在 QML 侧（``onClosing`` + ``event.accepted = false``）。
        # **不要**在这里把 Python 槽连到 ``closing(QQuickCloseEvent*)``：
        # PySide 无法把 QQuickCloseEvent 转成 Python 参数，点关闭按钮时抛
        # TypeError: Cannot call meta function ... cannot be converted，
        # 冒泡成未捕获异常直接把应用打死（2026-09-25 真机日志实锤）。
        self.panel.activeChanged.connect(self._on_panel_active_changed)

    def _create_panel(self) -> None:
        qml_path = UI_DIR / "QuickPanel.qml"
        root = self._create(qml_path, {"visible": False})
        if root is None or not hasattr(root, "show"):
            raise RuntimeError(f"快捷面板根节点必须是 Window: {qml_path}")
        self.panel = root
        self._bind_panel()

    def _on_panel_active_changed(self) -> None:
        # 失焦收起是**默认行为**（2026-10-01 第二轮用户指令：原来的
        # 「失去焦点时收起」设置项与 ``quick_panel.hide_on_deactivate`` 配置键
        # 一并删除）。这里不再读配置，面板失活就（延迟 140ms）收起。
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
        self._create_docks(container)
        log.info(
            "顶层窗口已创建，控制条 x%d: %s", len(self._docks), list(self._docks)
        )

    # ---------------------------------------------------------------- 控制条

    def _create_docks(self, container) -> None:
        """按当前配置给各角落建控制条（挂到顶层窗口的容器里）。

        与 :meth:`_load_docks` 分开是为了**重建**：改「翻页组件位置」会换掉
        启用的角落集合（竖版两侧 ↔ 横版下部），而且两边的组件根本不是一个
        QML 文件（``SidePager`` vs ``PresentationDock``）—— 光挪位置不够，
        得整批销毁重建。
        """
        corners = self._config.get("presentation.corners", {}) or {}
        for name in CORNERS:
            settings = corners.get(name) or {}
            if not settings.get("enabled", False):
                continue
            # 竖版两侧翻页（middle_*）用独立的竖排组件，其余角落仍是横向 dock
            if name.startswith("middle"):
                qml_path = UI_DIR / "presentation" / "SidePager.qml"
            else:
                qml_path = UI_DIR / "presentation" / "PresentationDock.qml"
            root = self._create(qml_path, {"corner": name})
            if root is None or not isinstance(root, QQuickItem):
                log.error("控制条加载失败: %s", name)
                continue
            root.setParentItem(container)
            root.widthChanged.connect(lambda *_, n=name: self._schedule_reposition(n))
            root.heightChanged.connect(lambda *_, n=name: self._schedule_reposition(n))
            # 命中矩形**不是**跟着尺寸走的：笔的选单（PenPaletteCard）浮在控制条
            # 上方 —— 那是 dock Item 的包围盒之外，尺寸一点没变，但区域塑形必须
            # 把这块补进去（否则卡片既画不出来也点不动，点击会穿透到 PowerPoint
            # 在幻灯片上乱画）。控制条为此发 ``hitRectChanged``。
            self._connect_hit_rect(root)
            self._docks[name] = root

    def _connect_hit_rect(self, dock) -> None:
        """接住控制条的 ``hitRectChanged``，尽快重算窗口区域。

        区域塑形平时跟着 ``_assert_topmost``（800ms 一拍）走，对「拖窗口」这类
        慢变化够了；笔选单却是点一下瞬间长出来的，那 800ms 里新增的那块还没进
        区域。转发到 ``QTimer.singleShot(0, ...)``：等 QML 的绑定都落地了再读
        ``interactiveRect``，读到的一定是新值。
        """
        signal = getattr(dock, "hitRectChanged", None)
        if signal is None:  # pragma: no cover - 别的控制条还没有这个信号
            return
        try:
            signal.connect(self._schedule_region_sync)
        except (RuntimeError, TypeError):  # pragma: no cover
            log.debug("控制条 %s 的 hitRectChanged 接不上", dock.objectName(),
                      exc_info=True)

    def _schedule_region_sync(self) -> None:
        QTimer.singleShot(0, self._sync_input_mode)

    def _destroy_docks(self) -> None:
        """销毁全部控制条实例（重建前用）。

        ⚠️ 先从容器上摘下来再 ``deleteLater()``：直接删会让场景图在那一帧
        还持有指向已释放对象的指针。
        """
        for name, dock in list(self._docks.items()):
            try:
                dock.setParentItem(None)
                dock.deleteLater()
            except RuntimeError:  # pragma: no cover - 已被 Qt 提前释放
                log.debug("控制条已提前释放: %s", name)
        self._docks.clear()
        # 区域塑形是按控制条的矩形算的，形状变了必须重算（否则穿透区域还留在
        # 旧位置，新的控制条点不动）
        self._last_region_rects = None

    def rebuild_docks(self) -> None:
        """按当前配置**重建**全部控制条（角落集合变了时）。

        ``presentationConfigChanged`` 已经把新配置推给了 QML（控制条自己会
        跟着改宽度 / 显隐），但**启用哪些角落**只有这里知道 —— 换形态要换
        QML 组件，所以走一遍销毁 + 重建。
        """
        if self.overlay is None:
            return
        container = self.overlay.property("container")
        if container is None:
            log.warning("顶层窗口缺 container，控制条未重建")
            return
        self._destroy_docks()
        self._create_docks(container)
        log.info("控制条已重建 x%d: %s", len(self._docks), list(self._docks))
        if self.overlay.isVisible():
            self.reposition_all_docks()

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

    # ======================================================== RinUI 窗口接管

    def _attach_to_rinui(self, window) -> bool:
        """把 Python 侧另建的顶层窗口**完整**交给 RinUI 接管。

        RinUI 只在 ``launcher.load()`` 那一刻登记窗口：它取
        ``[root_window] + root_window.findChildren(QQuickWindow)`` 里带
        ``isRinUIWindow`` 的那些，**之后不再接受新成员**。我们用
        ``QQmlComponent`` 另建的设置 / 调试窗口一份名单都进不去，于是三层
        一起塌（都是 Win32 / DWM 层的事实，与 QML 画得对不对无关）：

        * ``ThemeManager.windows`` 里没有它 → 没有 ``DWMWA_WINDOW_CORNER_PREFERENCE``
          （圆角）、没有 ``DWMWA_NCRENDERING_POLICY``（**系统阴影 —— 实测未接管的
          窗口外圈是 1 像素硬边，接管后立刻出现 10 像素渐变阴影**）、没有暗色 /
          边框色 / backdrop；
        * ``WinEventFilter.hwnds`` 里没有它 → ``WM_NCCALCSIZE`` 不处理（于是
          ``WS_CAPTION`` 一加上就变成**真的原生标题栏**，这正是当初只能在 QML 里
          ``flags |= FramelessWindowHint`` 兜底的原因）、``WM_NCHITTEST`` 不处理
          （没有 8px resize 边框与 ``HTCAPTION`` 拖动）、``WM_GETMINMAXINFO``
          不处理（``minimumWidth/minimumHeight`` 递不到系统）；
        * ``WinEventManager.windows`` 里没有它 → 系统改窗口 frame 之后没人重新
          应用上述效果。

        三份名单缺一不可 —— 实测只补 ``hwnds`` 不补 ``windows`` 时，
        ``nativeEventFilter`` 遍历不到它，原生标题栏会直接画出来。

        ``TopWindow``（放映叠加层）**刻意不接管**：它是全屏 ``WS_EX_TRANSPARENT``
        ＋ ``SetWindowRgn`` 塑形的穿透窗口，RinUI 那套非客户区处理会和它打架。
        """
        if self._rinui is None or window is None:
            return False
        try:
            event_filter = self._rinui.win_event_filter
            theme = self._rinui.theme_manager
            hwnd = int(window.winId())
        except Exception:
            log.warning("RinUI 接管失败：拿不到窗口句柄", exc_info=True)
            return False

        # ① WinEventFilter：WM_NCCALCSIZE / WM_NCHITTEST / WM_GETMINMAXINFO 按 hwnd 分发
        if window not in event_filter.windows:
            event_filter.windows.append(window)
        event_filter.hwnds[window] = hwnd
        event_filter.sync_window_backdrop(window)
        # 窗口若被 Qt 重建（改 flags / 换屏 / DPI 变化），hwnd 会变，跟着刷一次
        if window not in self._rinui_hooked:
            self._rinui_hooked.append(window)
            # ⚠️ ``visibleChanged`` 在 Qt 6 里是 **带参信号**（``visibleChanged(bool)``）。
            # 写成 ``lambda w=window: ...`` 会被信号那个 bool 顶掉默认值 —— 实测症状是
            # 每次显示/隐藏都往日志里灌一条 ``AttributeError: 'bool' object has no
            # attribute 'isVisible'``，而且**句柄刷新其实一次都没跑成**（hwnd 变了也没人同步）。
            # 用 ``*_args`` 把信号参数吞掉，真正的窗口从默认值来。
            window.visibleChanged.connect(
                lambda *_args, w=window: self._refresh_rinui_handle(w)
            )

        # ② ThemeManager：圆角 / 阴影 / 暗色 / 边框色 / backdrop
        if hwnd not in theme.windows:
            theme.set_window(window)

        # ③ WinEventManager：系统改 frame 后重新应用效果
        manager = self._rinui.win_event_manager
        if window not in self._rinui_windows:
            self._rinui_windows.append(window)
        manager.set_windows(self._rinui_windows, manager.on_window_frame_changed)

        # 加 WS_CAPTION|WS_THICKFRAME 并 SWP_FRAMECHANGED（DWM 阴影 / resize / Snap 的前提）
        manager.syncWindowFrame(window)
        theme.apply_window_effects()
        theme._update_window_theme()  # RinUI 没有公开的「重新应用」入口

        # 背景材质：这里**不能**去读 ``app.backdrop`` 再判断三选一。
        #
        # RinUI 只在 ``launcher.load()`` 那一刻广播过一次材质，而设置 / 调试 /
        # 编辑器 / 错误报告这四个窗口都是**之后**才用 ``QQmlComponent`` 建的 ——
        # 它们生来就不在那一轮广播的名单里。原来的写法是「配置里显式写了
        # mica / acrylic / tabbed 才补一次」，于是 ``app.backdrop = "auto"``
        # （按平台选）时新窗口**一个都补不上**，面板有材质、设置窗口却是实色底。
        #
        # 正确做法是重放 RinUI **当前实际生效**的值 —— 它已经在启动时解析完
        # auto / 平台能力 / 21H2 回退，这里照抄即可，新旧窗口自然一致。
        theme.apply_backdrop_effect(theme.get_backdrop_effect())

        ok = (
            window in event_filter.windows
            and event_filter.hwnds.get(window) == hwnd
            and hwnd in theme.windows
            and window in self._rinui_windows
        )
        if ok:
            log.info("RinUI 已接管窗口: %s (hwnd=%s)", window.metaObject().className(), hwnd)
        else:
            log.warning("RinUI 未接管窗口: %s (hwnd=%s)", window.metaObject().className(), hwnd)
        return ok

    def _refresh_rinui_handle(self, window) -> None:
        """窗口重新显示时同步一次 hwnd（Qt 重建原生窗口后句柄会变）。"""
        if self._rinui is None or window is None:
            return
        try:
            if not window.isVisible():
                return
            hwnd = int(window.winId())
            event_filter = self._rinui.win_event_filter
            if event_filter.hwnds.get(window) != hwnd:
                event_filter.hwnds[window] = hwnd
            if hwnd not in self._rinui.theme_manager.windows:
                self._rinui.theme_manager.set_window(window)
            event_filter.sync_window_backdrop(window)
            # 编辑器窗口的亚克力是挂在 hwnd 上的：句柄重建、以及本次显隐引起的
            # frame 重应用都会把它清掉，所以这里也补一拍
            if window is self.editor:
                self._attach_editor_acrylic(schedule=True)
        except Exception:
            log.debug("刷新 RinUI 窗口句柄失败", exc_info=True)

    def _keep_frameless(self, window) -> None:
        """接管失败时的兜底：退回「纯 frameless」。

        没有 RinUI 处理 ``WM_NCCALCSIZE`` 时，``WS_CAPTION`` 会变成真的原生
        标题栏压在自绘标题栏上 —— 宁可不要系统阴影，也不能要这条标题栏。
        """
        try:
            window.setFlags(window.flags() | Qt.FramelessWindowHint)
            log.info("已退回 frameless 兜底: %s", window.metaObject().className())
        except Exception:
            log.warning("frameless 兜底失败", exc_info=True)

    def _schedule_reposition(self, corner: str) -> None:
        QTimer.singleShot(0, lambda: self._position_dock(corner))

    # ================================================================== 信号

    def _wire_signals(self) -> None:
        self._backend.panelHideRequested.connect(self.hide_panel)
        self._backend.settingsCloseRequested.connect(self.hide_settings)
        self._backend.debugWindowRequested.connect(self.show_debug)
        self._backend.debugWindowCloseRequested.connect(self.hide_debug)
        self._backend.editorRequested.connect(self.show_editor)
        self._backend.editorCloseRequested.connect(self.hide_editor)
        # 翻页组件位置切换 → 换了一组角落（不只是挪位置），要重建
        self._backend.docksRebuildRequested.connect(self.rebuild_docks)
        self._ppt.stateChanged.connect(self._on_presentation_state)

    def _on_presentation_state(self, state) -> None:
        # 状态只往两处去：bridge（QML 侧读 presentationActive / 页码）与控制条显隐。
        # 2026-10-01 起不再把整份快照塞给 bridge —— 那是为「设置页显示实际认到
        # 哪家软件 / 哪个窗口」那几张卡片准备的，卡片已随用户指令删除。
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

        # 尺寸取 **QML 声明的意图值**（``panelWidth`` / ``panelHeight``），
        # 不能直接读 ``panel.width()`` / ``height()``：窗口在**第一次 show()
        # 之前**，Qt 报的几何还带着无边框窗口的 resize 边框余量 —— 实测
        # 387x453（QML 里明明是 375x440，min/max 也都是 375x440）。拿它算位置
        # 会让首次弹窗整体偏 13px，甚至翻页判断失效、把面板压在光标上
        # （2026-10-01 自检实锤：cursor=(657,475) → panel=(464,473)，光标落在
        # 面板里）。show() 之后两者才一致，所以只影响「第一次弹出」。
        def _intent(name: str, fallback: int) -> int:
            try:
                value = int(self.panel.property(name))
            except (TypeError, ValueError):  # 属性不存在（老组件）→ 用几何
                return fallback
            return value if value > 0 else fallback

        width = _intent("panelWidth", self.panel.width())
        height = _intent("panelHeight", self.panel.height())
        anchor = pos if pos is not None else QCursor.pos()
        offset_y = PANEL_OFFSET_Y
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

    # ================================================================ 启动画面

    def show_splash(self) -> None:
        """显示启动画面（应用启动时最先出现、最后一个消失的东西）。

        **刻意不 ``_attach_to_rinui``**：RinUI 接管会给窗口加 ``WS_CAPTION``
        并让 DWM 画系统圆角与阴影，而设计稿是一整块**无边框圆角 92（设计值）**
        的卡片、卡外全透明（同 ``TopWindow`` 的理由）。

        只显示不销毁 —— 淡出结束后由 ``_destroy_splash`` 收掉，因为那张
        1717×1640 的插画贴图常驻一份不划算（约 11MB 显存 / 内存）。
        """
        if self.splash is None:
            qml_path = UI_DIR / "SplashWindow.qml"
            if not qml_path.exists():
                log.warning("启动画面不存在，跳过: %s", qml_path)
                return
            root = self._create(qml_path, {"visible": False})
            if root is None:
                log.error("启动画面创建失败: %s", qml_path)
                return
            self.splash = root
            # 淡出动画结束 → 收窗口。无参信号，从 Python 侧接安全。
            try:
                root.fadeOutFinished.connect(self._destroy_splash)
            except Exception:  # pragma: no cover - 信号缺失只影响回收时机
                log.debug("启动画面没有 fadeOutFinished 信号", exc_info=True)

        self._position_splash()
        self.splash.show()
        self.splash.raise_()

    def hide_splash(self) -> None:
        """淡出启动画面；真正收窗口在 ``fadeOutFinished`` 里。"""
        if self.splash is None or not self.splash.isVisible():
            self._destroy_splash()
            return
        try:
            QMetaObject.invokeMethod(self.splash, "fadeOut")
        except Exception:
            log.debug("启动画面淡出调用失败，直接收窗口", exc_info=True)
            self._destroy_splash()

    def _destroy_splash(self) -> None:
        if self.splash is None:
            return
        window, self.splash = self.splash, None
        try:
            window.hide()
            window.deleteLater()
        except RuntimeError:  # 对象已被 QML 引擎回收
            pass

    def _position_splash(self) -> None:
        """居中到主屏。

        用 ``availableGeometry``（避开任务栏）而不是整屏 —— 启动画面不贴着
        屏幕边，居中在可视区里才对。
        """
        if self.splash is None:
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.left() + (area.width() - self.splash.width()) // 2
        y = area.top() + (area.height() - self.splash.height()) // 2
        self.splash.setPosition(int(x), int(y))

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
        # 交给 RinUI 管（否则没有 DWM 阴影 / 圆角 / resize 边框 / Snap）
        if not self._attach_to_rinui(root):
            self._keep_frameless(root)

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
        # 每次打开都让 QML 重取一遍设置项：``settings`` 里混着**实时状态**
        # （「开机自启」读的是注册表，用户可能在任务管理器里刚把它禁掉），
        # 而页面是按需创建、之后只隐藏不销毁的 —— 不主动刷就会显示上次的旧值。
        self._backend.refreshSettings()
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

    # ================================================================ 调试窗口

    def _create_debug(self) -> None:
        """按需创建调试窗口。

        入口是隐藏的（设置窗口标题连点 10 次，见 ``Backend.openDebugWindow``），
        与设置窗口同理：不打开就一个对象都不建。
        """
        if self.debug is not None:
            return
        qml_path = UI_DIR / "DebugWindow.qml"
        if not qml_path.exists():
            log.warning("调试窗口不存在，跳过: %s", qml_path)
            return
        root = self._create(qml_path, {"visible": False})
        if root is None:
            log.error("调试窗口创建失败: %s", qml_path)
            return
        self.debug = root
        # 同设置窗口：不接管的话没有系统阴影 / 圆角，且 WS_CAPTION 会露原生标题栏
        if not self._attach_to_rinui(root):
            self._keep_frameless(root)

    def show_debug(self) -> None:
        self._create_debug()
        if self.debug is None:
            log.info("调试窗口不可用")
            return
        self._position_debug()
        self.debug.show()
        self.debug.raise_()
        self.debug.requestActivate()

    def hide_debug(self) -> None:
        if self.debug is not None and self.debug.isVisible():
            self.debug.hide()

    def toggle_debug(self) -> None:
        if self.debug is not None and self.debug.isVisible():
            self.hide_debug()
        else:
            self.show_debug()

    def _position_debug(self) -> None:
        """摆在设置窗口旁边（设置窗口开着的时候），否则居中到光标所在显示器。

        两个窗口都是居中摆放的话会**完全重叠** —— 调试窗口是从设置窗口里点
        出来的，贴边并排才符合「母子关系」的直觉。右侧放不下就翻到左侧；
        两侧都放不下（窄屏上两个窗口加起来比屏还宽，很常见）就退到右下角
        错开，至少让设置窗口露出一角。
        """
        self._place_beside_settings(self.debug, "调试窗口")

    def _position_editor(self) -> None:
        """主界面编辑器：与调试窗口同一套摆位（设置窗口开着就贴边并排）。

        编辑器的入口是**快捷面板**而不是设置窗口，但两者仍可能同时在屏幕上，
        居中摆放会整块压住设置窗口；沿用同一套「先贴边、放不下再错开」的策略
        比各写一份更省心。
        """
        self._place_beside_settings(self.editor, "主界面编辑器")

    def _place_beside_settings(self, window, label: str) -> None:
        """把 ``window`` 摆在设置窗口旁边，没有设置窗口就居中到光标所在显示器。

        ``label`` 只用于日志（窗口没建起来时能一眼看出是谁没位置）。
        """
        if window is None:
            log.debug("%s 尚未创建，跳过摆位", label)
            return
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width, height = window.width(), window.height()

        anchor = self.settings if (self.settings is not None and self.settings.isVisible()) else None
        if anchor is None:
            x = area.left() + (area.width() - width) // 2
            y = area.top() + (area.height() - height) // 2
        else:
            gap = 16
            right = anchor.x() + anchor.width() + gap
            left = anchor.x() - gap - width
            if right + width <= area.right() + 1:
                x, y = right, anchor.y()
            elif left >= area.left():
                x, y = left, anchor.y()
            else:
                # 两侧都放不下：退到右下角错开
                inset = 12
                x = area.right() + 1 - width - inset
                y = area.bottom() + 1 - height - inset
            # 夹回屏内（设置窗口本身可能就贴着屏幕边缘）
            x = max(area.left(), min(x, area.right() + 1 - width))
            y = max(area.top(), min(y, area.bottom() + 1 - height))
        window.setPosition(int(x), int(y))

    # ========================================================== 主界面编辑器

    def _dark_theme(self) -> bool:
        """当前是否暗色主题（问不到就按暗色算 —— 本项目默认暗色）。"""
        try:
            return bool(self._rinui.theme_manager.is_dark_theme())
        except Exception:  # pragma: no cover - RinUI 未就绪
            return True

    def _apply_acrylic(self, window) -> bool:
        """给**单只**窗口铺亚克力（DWM 系统背景材质）。

        ⚠️ 刻意**不走** ``rinui.setBackdropEffect()``：那个 API 是**全局**的 ——
        它把值写进 ``RinConfig``，再遍历 ``ThemeManager.windows`` 广播给每一只
        已登记窗口；一调，设置窗口 / 调试窗口 / 快捷面板会跟着全变亚克力。
        这里直接对目标 hwnd 打 DWM 属性，只影响这一只。

        需要 QML 侧配合两件事，缺一不可：

        * 根项声明 ``property bool backdropEnabled: true`` —— RinUI 的**按窗口**
          钩子（``core/window.py::extend_frame_into_client_area``），它会调
          ``DwmExtendFrameIntoClientArea(-1,-1,-1,-1)`` 把 frame 铺满客户区；
        * ``background`` 画成透明 —— 否则不透明底色把亚克力整个盖住。

        这里自己再调一次 ``DwmExtendFrameIntoClientArea``：不依赖 RinUI 那条
        钩子是否真的被触发（登记顺序 / 版本差异都可能让它落空）。
        """
        # 平台判断照项目惯例用 ``hasattr(ctypes, "windll")``，不引 sys
        if window is None or not hasattr(ctypes, "windll"):
            return False
        try:
            hwnd = int(window.winId())
        except Exception:  # pragma: no cover - 尚无原生句柄
            return False
        if not hwnd:
            return False

        try:
            dwm = ctypes.windll.dwmapi
            handle = wintypes.HWND(hwnd)

            dark = ctypes.c_int(1 if self._dark_theme() else 0)
            dwm.DwmSetWindowAttribute(
                handle,
                ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
                ctypes.byref(dark),
                ctypes.sizeof(dark),
            )

            backdrop = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
            dwm.DwmSetWindowAttribute(
                handle,
                ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
                ctypes.byref(backdrop),
                ctypes.sizeof(backdrop),
            )

            # 标题栏与边框都不许 DWM 上色：标题栏实色块、窗口描边都由 QML 画，
            # 系统再叠一层会跟 Fluent 配色打架（也会在圆角处露出一圈系统色）。
            none = ctypes.c_int(DWMWA_COLOR_NONE)
            for attribute in (DWMWA_CAPTION_COLOR, DWMWA_BORDER_COLOR):
                dwm.DwmSetWindowAttribute(
                    handle,
                    ctypes.c_uint(attribute),
                    ctypes.byref(none),
                    ctypes.sizeof(none),
                )

            margins = _Margins(-1, -1, -1, -1)
            dwm.DwmExtendFrameIntoClientArea(handle, ctypes.byref(margins))
        except Exception:
            log.warning("亚克力背景应用失败", exc_info=True)
            return False
        return True

    def _create_editor(self) -> None:
        """按需创建主界面编辑器窗口（**占位骨架**，正文待填）。

        入口是快捷面板的「主界面编辑器」快捷方式（``shortcut_catalog`` 里
        ``action: "open_editor"``）。与设置 / 调试窗口同理：不打开就一个对象
        都不建。
        """
        if self.editor is not None:
            return
        qml_path = UI_DIR / "MainInterfaceEditor.qml"
        if not qml_path.exists():
            log.warning("主界面编辑器不存在，跳过: %s", qml_path)
            return
        root = self._create(qml_path, {"visible": False})
        if root is None:
            log.error("主界面编辑器创建失败: %s", qml_path)
            return
        self.editor = root
        # 同设置窗口：不接管的话没有系统阴影 / 圆角，且 WS_CAPTION 会露原生标题栏
        if not self._attach_to_rinui(root):
            self._keep_frameless(root)
        # 亚克力背景（用户指令：窗口整体背景除标题栏外都是亚克力）。
        # 要在接管之后打：接管会补 WS_CAPTION / 扩展 frame，属性次序反了会被覆盖。
        self._attach_editor_acrylic()

    def _attach_editor_acrylic(self, schedule: bool = False) -> None:
        """给编辑器窗口铺亚克力，并把结果写回 QML（自检读得到）。

        ⚠️ **必须在 ``show()`` 之后**再补打一次（``schedule=True``）。实测：窗口
        显示前的调用是「成功」的（回读得到 ``DWMWA_SYSTEMBACKDROP_TYPE = 3``），
        但 ``show()`` 之后的 ~200ms 内系统会把它**重置回 0** —— 那个时间窗里
        Qt 正在做首次展示的平台窗口初始化 / 重新应用 frame。之后再打就稳定了
        （实测补打后 700ms 仍保持 3）。
        """
        if self.editor is None:
            return
        ok = self._apply_acrylic(self.editor)
        try:
            self.editor.setProperty("acrylicActive", bool(ok))
        except Exception:  # pragma: no cover - 属性尚未注册
            log.debug("回写 acrylicActive 失败", exc_info=True)
        if schedule:
            QTimer.singleShot(ACRYLIC_REAPPLY_MS, self._reapply_editor_acrylic)

    def _reapply_editor_acrylic(self) -> None:
        """延迟补打的那一拍（窗口已经关掉就跳过）。"""
        if self.editor is not None and self.editor.isVisible():
            self._attach_editor_acrylic()

    def show_editor(self) -> None:
        self._create_editor()
        if self.editor is None:
            log.info("主界面编辑器不可用")
            return
        self._position_editor()
        self.editor.show()
        # 显示后再打一次，并排一拍补打（原因见 _attach_editor_acrylic 的注释：
        # show() 后 ~200ms 内系统会把 backdrop 重置回 0）
        self._attach_editor_acrylic(schedule=True)
        self.editor.raise_()
        self.editor.requestActivate()

    def hide_editor(self) -> None:
        if self.editor is not None and self.editor.isVisible():
            self.editor.hide()

    def toggle_editor(self) -> None:
        if self.editor is not None and self.editor.isVisible():
            self.hide_editor()
        else:
            self.show_editor()

    # ======================================================= 错误 / 崩溃报告

    def _create_error_report(self) -> None:
        """按需创建错误 / 崩溃报告窗口。

        入口是 ``ErrorHandler`` 捕获到未捕获异常（``application.py`` 把
        ``reportRequested`` 连到 :meth:`show_error_report`）。与设置 / 调试 /
        编辑器窗口同理：不出现就一个对象都不建。
        """
        if self.error_report is not None:
            return
        qml_path = UI_DIR / "ErrorReport" / "ErrorReportWindow.qml"
        if not qml_path.exists():
            log.warning("错误报告窗口不存在，跳过: %s", qml_path)
            return
        root = self._create(qml_path, {"visible": False})
        if root is None:
            log.error("错误报告窗口创建失败: %s", qml_path)
            return
        self.error_report = root
        # 同设置窗口：不接管的话没有系统阴影 / 圆角，且 WS_CAPTION 会露原生标题栏
        if not self._attach_to_rinui(root):
            self._keep_frameless(root)

    def show_error_report(self) -> None:
        """弹出报告窗口（``ErrorHandler.reportRequested`` 的接收端）。

        ⚠️ 整体包 try：这条路径是在**异常处理栈里**被调用的（excepthook →
        信号 → 这里），自己再抛出去会变成「异常套异常」，把原始崩溃盖掉。
        """
        try:
            self._create_error_report()
            if self.error_report is None:
                log.info("错误报告窗口不可用")
                return
            self._position_error_report()
            self.error_report.show()
            self.error_report.raise_()
            self.error_report.requestActivate()
        except Exception:  # pragma: no cover - 报告窗本身建不起来时只剩日志
            log.exception("显示错误报告窗口失败")

    def hide_error_report(self) -> None:
        if self.error_report is not None and self.error_report.isVisible():
            self.error_report.hide()

    def _position_error_report(self) -> None:
        """居中到光标所在显示器（多屏时不会跑到别的屏幕上）。

        窗口尺寸由 QML 自己按屏幕夹（上限 720×600，见 ``ErrorReportWindow.qml``）；
        屏幕比它还小时这里再按可用区夹一刀，免得报告窗的按钮落在屏幕外点不到。
        """
        if self.error_report is None:
            return
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(int(self.error_report.width()), area.width())
        height = min(int(self.error_report.height()), area.height())
        x = area.left() + (area.width() - width) // 2
        y = area.top() + (area.height() - height) // 2
        self.error_report.setPosition(int(x), int(y))

    # ================================================================ 顶层窗口

    def show_docks(self) -> None:
        """放映开始：顶层窗口全屏铺到放映所在显示器，控制条落到各角落。

        顺序很重要：**先定屏 → 再全屏 → 再摆控制条 → 最后才谈穿透**。

        2026-10-01 起没有「放映总开关」了（``presentation.enabled`` 已按用户
        指令删除）：探测到放映就显示，不再读任何开关。
        """
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

        # 把「放映铺在哪块屏」告诉 Bridge：主界面编辑器的画布比例以它为准
        # （Bridge 自己复现不了这段判定 —— 它依赖放映窗口的**物理**显示器，
        # 见 :meth:`_presentation_screen`）。
        geometry = screen.geometry()
        self._backend.syncPresentationScreen(
            geometry.width(), geometry.height(), screen.name(),
            float(screen.devicePixelRatio()),
        )

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
            self._last_region_rects = None
            self.overlay.hide()
        self._click_through = True

    def reposition_all_docks(self) -> None:
        for name in self._docks:
            self._position_dock(name)
        self._sync_input_mode()

    def _position_dock(self, corner: str) -> None:
        """把控制条摆到顶层窗口容器内的对应角落。

        坐标是**顶层窗口局部**坐标（顶层窗口整屏铺在放映所在显示器，
        原点 = screen geometry 左上角）。

        ⚠️ 基准必须是**整屏几何** ``screen.geometry()``，不能用
        ``availableGeometry()``（避开任务栏的工作区）—— 放映时任务栏被放映窗口
        整个盖住，用户眼里的基准就是屏幕边缘，而 Windows 的「工作区」在任务栏
        被盖住时**照样把它算掉**：本机实测下边比屏幕下边高 48px，于是
        「左右 20px 正常、纵向变成 68px」。Luminalium 1 也是按整屏算的
        （overlay 窗口铺满整屏 + ``bottom: 20px``）。

        控制条 Item 自带投影余量（shadowMargin），而 ``margin_x`` / ``margin_y``
        的语义是**视觉距离** —— 屏幕底板边缘到屏幕边缘的距离（对齐 Luminalium 1
        的默认 20px：``Overlay.SafeArea`` 默认 0、贴边内边距固定 20px 四边一致，
        只有 StrictEdgeAlignment 打开才贴死）。所以摆放时要把投影余量扣掉，
        否则屏幕上量到的会是 ``margin + shadowMargin``。
        """
        dock = self._docks.get(corner)
        if dock is None or self.overlay is None:
            return
        horizontal, vertical = CORNERS.get(corner, ("left", "bottom"))
        margin_x = int(self._config.get("presentation.margin_x", 20))
        margin_y = int(self._config.get("presentation.margin_y", 20))
        # 控制条 Item 为了投影不被窗口边界裁掉而自带 shadowMargin 余量：
        # margin_* 说的是**视觉距离**（屏幕上量到的底板到屏幕边缘），
        # 所以这里把它扣掉。margin 小于余量时多出的部分只是阴影尾部被屏幕裁掉。
        try:
            shadow = int(dock.property("shadowMargin") or 0)
        except TypeError:  # pragma: no cover - 属性尚未就绪
            shadow = 0

        screen = self._presentation_screen()
        if screen is None:
            return
        geom = screen.geometry()
        width, height = geom.width(), geom.height()

        if horizontal == "left":
            x = margin_x - shadow
        elif horizontal == "center":
            x = (width - dock.width()) // 2
        else:
            x = width - dock.width() - margin_x + shadow
        if vertical == "top":
            y = margin_y - shadow
        elif vertical == "middle":
            # 竖版两侧翻页：屏幕左右、**垂直居中**（L1 .flipper 默认形态）。
            # dock 尺寸含对称的投影余量，居中后底板也在屏幕竖直中线上。
            y = (height - dock.height()) // 2
        else:
            y = height - dock.height() - margin_y + shadow
        prev_x, prev_y = dock.x(), dock.y()
        dock.setX(x)
        dock.setY(y)
        # ⚠️ 位置变了必须补一次区域重算：``interactiveRect`` 是 dock **局部**
        # 坐标（不随 x/y 变），挪动不会触发 ``hitRectChanged`` —— 区域里留着
        # 的是旧位置的块。实测（2026-10-01）：「显示按钮文本」收窄时宽度先变、
        # x 后归位，中间态里区域被算成「旧 x + 新宽」的缝合块
        # （(519,885,357,101)，条实际已在 x=698），工具栏中心恰好被切出去。
        # 旧判据（外接 box）碰巧因「box 不变→短路」跳过了那次错块重建，这里
        # 修的是根：重摆结束就同步。
        if (int(x) != int(prev_x) or int(y) != int(prev_y)) \
                and self._region_mode:
            self._schedule_region_sync()

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

        另外扫描**整个置顶层**里排在我们之上的可见窗口（别的常驻overlay，
        例如 Class Widgets 2 的全屏 TOPMOST 桌面窗口）：谁在我们上面就点名
        记录，集合变化才记一次，避免刷屏。
        """
        slideshow = self._ppt.state.window_handle
        if not slideshow:
            self._below_slideshow = 0
        else:
            hwnd = int(self.overlay.winId())
            if hwnd and hwnd != slideshow:
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

        above = self._visible_topmost_above()
        sig = ";".join(above)
        if sig != self._above_sig:
            self._above_sig = sig
            if above:
                log.warning(
                    "置顶层里排在本应用之上的可见窗口（可能盖住控制条）: %s",
                    " | ".join(above),
                )

    def _visible_topmost_above(self, cover_only: bool = True) -> list[str]:
        """置顶层里排在**本应用之上**的可见窗口，``["hwnd class title"]``。

        从自己的窗口用 ``GW_HWNDPREV`` 一路向上走：这条路径无歧义，走到的
        每一个都是「在我们之上」。（早前用「从 ``GW_HWNDFIRST`` 向下走到遇到
        自己为止」，若 256 步内没遇到自己就会把整带都误报成在上方。）

        ``cover_only=True`` 时只保留**铺满所在显示器**的窗口：实测置顶带里
        绝大多数是系统/驱动的隐藏辅助窗（AMD DVR overlay、TabTip、
        ThumbnailDeviceHelper 等），它们不可能盖住控制条，报出来只有噪音。
        会遮挡的只有铺满整屏的窗口——例如桌面小组件类应用的全屏叠加层
        （Class Widgets 2 就是）。注意：铺满 ≠ 一定不透明，z 序也不等于
        视觉遮挡（实测 CW2 虽在 z 序之上，但它是逐像素透明的，控制条照样可见），
        所以这条只作线索，不作结论。
        """
        if self.overlay is None or not hasattr(ctypes, "windll"):
            return []
        user32 = ctypes.windll.user32
        hwnd_self = int(self.overlay.winId())
        if not hwnd_self:
            return []
        out: list[str] = []
        hwnd = user32.GetWindow(wintypes.HWND(hwnd_self), GW_HWNDPREV)
        steps = 0
        while hwnd and steps < 256:
            if user32.IsWindowVisible(hwnd):
                ex = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
                if ex & WS_EX_TOPMOST and (not cover_only or _covers_monitor(hwnd)):
                    buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
                    cls = buf.value
                    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 256)
                    out.append(f"0x{int(hwnd):08X} {cls} {buf.value.strip()}")
            hwnd = user32.GetWindow(hwnd, GW_HWNDPREV)
            steps += 1
        return out

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
        if not hit:
            # 区域塑形没生效的兜底模式下，水印也要能被看见（不穿透）。
            wm = self._watermark_rect_local()
            if wm is not None:
                wm_rect = QRect(wm[0], wm[1], wm[2], wm[3])
                origin = self.overlay.position()
                wm_rect.translate(origin)
                hit = wm_rect.contains(cursor)
        self._set_overlay_click_through(not hit)

    # ---------------------------------------------------------- 区域塑形

    def _watermark_rect_local(self) -> Optional[tuple[int, int, int, int]]:
        """左下角**开发水印**的矩形（顶层窗口局部坐标，逻辑像素）。

        区域塑形会把窗口裁成「只有控制条几块」，区域外不绘制也不命中 ——
        水印若不显式算进区域就会被整块裁掉。QML 侧在 ``TopWindow`` 上
        用 ``watermarkItem`` 暴露这个 Item；没暴露 / 不可见就返回 None。
        """
        if self.overlay is None:
            return None
        wm = self.overlay.property("watermarkItem")
        if not isinstance(wm, QQuickItem) or not wm.isVisible():
            return None
        scene = wm.mapRectToScene(QRectF(0, 0, wm.width(), wm.height())).toRect()
        if scene.width() <= 0 or scene.height() <= 0:
            return None
        return (scene.x(), scene.y(), scene.width(), scene.height())

    def _dock_rects_local(self) -> list[tuple[int, int, int, int]]:
        """各控制条表面矩形（顶层窗口局部坐标，逻辑像素）。

        开发水印的矩形也一并返回（小余量）：区域塑形模式下不把它算进去
        就等于看不见。
        """
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
        # 开发水印：余量给小一点（文字贴边即可），别多吃可点面积
        wm = self._watermark_rect_local()
        if wm is not None:
            wm_padding = 6
            x = max(0, wm[0] - wm_padding)
            y = max(0, wm[1] - wm_padding)
            right = min(limit_w, wm[0] + wm[2] + wm_padding)
            bottom = min(limit_h, wm[1] + wm[3] + wm_padding)
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
        rects_key = tuple(tuple(r) for r in rects)
        if rects_key == self._last_region_rects and self._region_scale is not None:
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
            self._last_region_rects = rects_key
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
            f"上方TOPMOST={self._visible_topmost_above() or '无'} "
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
        self._destroy_splash()
        self.hide_panel()
        self.hide_settings()
        self.hide_debug()
        self.hide_editor()
        self.hide_error_report()
        self.hide_docks()
        self._docks.clear()
        self._components.clear()
        self.panel = None
        self.settings = None
        self.debug = None
        self.editor = None
        self.error_report = None
        self.overlay = None
