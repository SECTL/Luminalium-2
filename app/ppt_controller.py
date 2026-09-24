"""PPT 控制器模块（独立）。

单一职责：**探测 + 控制 + 广播**放映状态，不依赖窗口管理层。

探测三通道（互为补充，命中任一即认为在放映）：

1. **窗口类探测（无依赖）** —— 全屏放映窗口的类名是 ``screenClass``
   （PowerPoint；WPS 演示兼容模式同样用这个类名，这里不区分大小写匹配），
   ``EnumWindows`` 毫秒级完成。
2. **进程名 + 全屏无边框探测** —— 只看窗口类会漏掉改过名的演示软件
   （新版 WPS / LibreOffice / 各种播放器）。条件：进程名在白名单里
   **且**该窗口可见、**无标题栏**（编辑器主窗口有）、**铺满整块屏幕**。
3. **COM 自动化（需 pywin32）** —— ``GetActiveObject`` 依次尝试
   ``PowerPoint.Application``（MS Office）与 ``Kwpp.Application``（WPS 演示），
   读取当前页码 / 总页数；窗口类没探到但 COM 报告有放映窗口时
   （例如窗口类改名 / 异常形态），用 COM 的 ``SlideShowWindows(1).HWND``
   兜底判定为放映中。

控制操作（翻页 / 退出 / 笔 / 清屏）COM 失败时回退为向放映窗口发按键。

所有状态变化都以 INFO 级写日志（``luminalium.ppt``），真机排查
「顶层窗口为什么没出来」先看这里有没有 ``放映开始`` 一行。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal

log = logging.getLogger("luminalium.ppt")

# --------------------------------------------------------------------------- 常量

# 全屏放映窗口类名（不区分大小写匹配；类名里带 slideshow 的一并认）。
# 这张表照 Luminalium 1（SECTL/Luminalium::ppt_monitor）补齐过：WPS 演示的
# 放映窗口**不是** screenClass，而是下面这几个——只认 screenClass 会把 WPS
# 整个漏掉（本项目踩过：WPS 放映时探测一直说没检测到）。
SLIDESHOW_WINDOW_CLASSES = {
    "screenclass",              # Microsoft PowerPoint
    "wppslideshowwindowclass",  # WPS 演示
    "wpp slideshow window",
    "wpp slideshow window 8.0",
    "sdl_app",                  # LibreOffice Impress
}
# 进程名命中但类名不认时，靠**窗口标题**兜底（Luminalium 1 的做法）。
# PowerPoint 全屏放映窗口的标题往往就是文件名，不含这些词，所以这只是
# 「类名不认识」时的补充渠道，不是主判定。
SLIDESHOW_TITLE_HINTS = (
    "slide show", "slideshow", "slide-show",
    "幻灯片放映", "幻燈片放映", "投影片放映", "放映",
    "スライド ショー", "スライドショー",
    "슬라이드 쇼", "슬라이드쇼",
    "wps presentation", "wps persentation",
    "diaporama", "bildschirmprasentation", "bildschirmpräsentation",
)
# 编辑器主窗口类名前缀（PowerPoint 主窗口；WPS 兼容模式同样套 PP**FrameClass）。
# 进程名探测会**排除**这些类：编辑器窗口即使最大化了也不是放映。
CONSOLE_WINDOW_CLASS_PREFIXES = ("PP97FrameClass", "PP12FrameClass", "PPTFrameClass")
# COM ProgID 候选：MS Office 在前，WPS 演示兜底（对象模型与 PowerPoint 同构）
COM_PROG_IDS = ("PowerPoint.Application", "Kwpp.Application", "wpp.Application")

# 进程名兜底：**窗口类名各家不统一且会随版本变，进程名反而是最稳的锚**。
# 只有「可见 + 无标题栏 + 覆盖整屏 + 进程名命中」才判定为放映窗口，
# 避免把最大化了的编辑器主窗口误判成放映。
SLIDESHOW_PROCESS_NAMES = {
    "POWERPNT.EXE",   # Microsoft PowerPoint
    "PPTVIEW.EXE",    # PowerPoint Viewer
    "WPP.EXE",        # WPS 演示
    "KWPP.EXE",       # WPS 演示（部分版本）
    "WPS.EXE",        # WPS 套件（部分版本由它承载放映窗口）
    "SOFFICE.BIN",    # LibreOffice（Impress 放映）
    "SOFFICE.EXE",
    "IMPRESS.EXE",
    "YOZO_IMPRESS.EXE",  # 永中 Office
    "YOZOPG.EXE",
    "YOZO_OFFICE.EXE",
}
# 覆盖显示器面积达到这个比例才算「全屏放映」
FULLSCREEN_COVER_RATIO = 0.70

# Win32：判定「全屏放映窗口」用的样式位与常量
GWL_STYLE = -16
WS_CAPTION = 0x00C00000     # 有标题栏 => 编辑器主窗口，不是放映
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2


def configure_detection(
    window_classes=(),
    process_names=(),
    fullscreen_ratio: Optional[float] = None,
) -> None:
    """按配置覆盖探测规则（配置是唯一来源，这里只是把值装进模块常量）。"""
    global SLIDESHOW_WINDOW_CLASSES, SLIDESHOW_PROCESS_NAMES, FULLSCREEN_COVER_RATIO
    if window_classes:
        SLIDESHOW_WINDOW_CLASSES = {str(name).lower() for name in window_classes}
    if process_names:
        SLIDESHOW_PROCESS_NAMES = {str(name).upper() for name in process_names}
    if fullscreen_ratio:
        FULLSCREEN_COVER_RATIO = float(fullscreen_ratio)

# PpSlideShowPointerType
PP_POINTER_NONE = 0
PP_POINTER_ARROW = 1
PP_POINTER_PEN = 2
PP_POINTER_ERASER = 3
PP_POINTER_AUTO_ARROW = 4

# 语义化工具名 -> COM 指针类型
TOOL_TO_POINTER = {
    "none": PP_POINTER_NONE,
    "arrow": PP_POINTER_ARROW,
    "pen": PP_POINTER_PEN,
    "eraser": PP_POINTER_ERASER,
}

# 放映态按键（COM 不可用时的降级路径）
VK_NEXT = 0x22  # PageDown
VK_PRIOR = 0x21  # PageUp
VK_ESCAPE = 0x1B
VK_ERASE = 0x45  # E


@dataclass(frozen=True)
class PresentationState:
    """一次探测的结果快照。"""

    active: bool = False
    slide_index: int = 0
    slide_total: int = 0
    window_handle: int = 0
    title: str = ""
    source: str = ""  # "window" = 窗口类命中；"com" = COM 兜底

    @property
    def marker(self) -> tuple:
        """用于判断状态是否发生变化的轻量标识。"""
        return (self.active, self.slide_index, self.slide_total, self.window_handle)


# --------------------------------------------------------------------------- 窗口探测


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _enum_windows():
    """枚举顶层窗口，返回 ``(hwnd, class_name, title, pid, visible, rect)`` 列表。

    ``rect`` 是**物理像素**的 ``(left, top, right, bottom)``；``pid`` 供
    进程名兜底识别使用（拿进程映像名比猜窗口类名可靠得多）。
    """
    user32 = ctypes.windll.user32
    results = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    pid = wintypes.DWORD(0)
    rect = wintypes.RECT()

    def _callback(hwnd, _lparam):
        # ⚠️ GetClassNameW **不支持**「传 NULL 先查长度」这种写法（那是
        # GetWindowTextLength 的套路）。nMaxCount=0 时它直接返回 0，
        # 于是类名永远是空串 —— 窗口类探测会静默彻底失效，症状就是
        # 「PowerPoint 明明在放映，探测却说没有」。必须直接给缓冲区。
        class_buffer = ctypes.create_unicode_buffer(256)
        class_name = (
            class_buffer.value
            if user32.GetClassNameW(hwnd, class_buffer, 256)
            else ""
        )

        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length:
            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
            title = title_buffer.value
        else:
            title = ""

        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            box = (rect.left, rect.top, rect.right, rect.bottom)
        else:  # pragma: no cover - 窗口在枚举过程中销毁
            box = (0, 0, 0, 0)
        results.append(
            (int(hwnd), class_name, title, int(pid.value),
             bool(user32.IsWindowVisible(hwnd)), box)
        )
        return True

    user32.EnumWindows(WNDENUMPROC(_callback), 0)
    return results


def _covers_monitor(hwnd: int, ratio: Optional[float] = None) -> bool:
    """窗口是否覆盖了它所在显示器面积的 ``ratio`` 以上（判定「全屏放映」）。

    ``ratio`` 缺省取**当前**的 ``FULLSCREEN_COVER_RATIO``：配置可以在运行期
    改写它，不能把它绑死在函数定义时的默认值上。
    """
    if not hasattr(ctypes, "windll") or not hwnd:
        return False
    ratio = FULLSCREEN_COVER_RATIO if ratio is None else ratio
    user32 = ctypes.windll.user32
    monitor = user32.MonitorFromWindow(wintypes.HWND(hwnd), MONITOR_DEFAULTTONEAREST)
    if not monitor:
        return False
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(_MonitorInfo)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    screen = info.rcMonitor
    screen_w, screen_h = screen.right - screen.left, screen.bottom - screen.top
    if screen_w <= 0 or screen_h <= 0:
        return False
    rect = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return False
    overlap_w = max(0, min(rect.right, screen.right) - max(rect.left, screen.left))
    overlap_h = max(0, min(rect.bottom, screen.bottom) - max(rect.top, screen.top))
    return (overlap_w * overlap_h) / float(screen_w * screen_h) >= ratio


def _process_name(pid: int) -> str:
    """进程的映像文件名（大写）；拿不到（权限 / 已退出）返回空串。"""
    if not pid or not hasattr(ctypes, "windll"):
        return ""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value.replace("\\", "/").rsplit("/", 1)[-1].upper()
    except OSError:  # pragma: no cover
        return ""
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _window_facts(hwnd: int) -> tuple[int, str, str, int, bool, tuple[int, int, int, int]]:
    """取单个窗口的 ``(hwnd, class, title, pid, visible, rect)``（给前台窗口用）。"""
    user32 = ctypes.windll.user32
    handle = wintypes.HWND(hwnd)
    buffer = ctypes.create_unicode_buffer(256)
    class_name = buffer.value if user32.GetClassNameW(handle, buffer, 256) else ""
    length = user32.GetWindowTextLengthW(handle)
    title = ""
    if length:
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, title_buffer, length + 1)
        title = title_buffer.value
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    box = wintypes.RECT()
    rect = (0, 0, 0, 0)
    if user32.GetWindowRect(handle, ctypes.byref(box)):
        rect = (box.left, box.top, box.right, box.bottom)
    return (int(hwnd), class_name, title, int(pid.value),
            bool(user32.IsWindowVisible(handle)), rect)


def _title_looks_like_slideshow(title: str) -> bool:
    """窗口标题里有没有「放映」字样（多语言）。"""
    lowered = str(title or "").strip().lower()
    if not lowered:
        return False
    return any(hint in lowered for hint in SLIDESHOW_TITLE_HINTS)


def _looks_like_slideshow(facts) -> bool:
    """单个窗口像不像放映窗口。

    从快到慢、从准到广（判定顺序照 Luminalium 1 ``_is_slideshow_hwnd``）：

    1. 不可见直接否；
    2. **类名命中** —— 最准，且不用查进程；
    3. 只有「标题像放映」或「铺满整屏」时才去查进程名（``OpenProcess`` 不便宜，
       不能对每个窗口都来一次，桌面上有几百个顶层窗口）；
    4. 进程名命中 + 标题像放映 → 是；
    5. 进程名命中 + 铺满整屏 + **不是编辑器主窗口**（类名前缀 / 有标题栏）→ 是。
       最后这条是防止「最大化了的 PowerPoint / WPS 编辑器」被误判成放映。
    """
    hwnd, class_name, title, pid, visible, _rect = facts
    if not hwnd or not visible:
        return False
    lowered = class_name.lower()
    if lowered in SLIDESHOW_WINDOW_CLASSES or "slideshow" in lowered:
        return True

    title_hint = _title_looks_like_slideshow(title)
    fullscreen = True if title_hint else _covers_monitor(hwnd)
    if not (title_hint or fullscreen):
        return False
    if _process_name(pid) not in SLIDESHOW_PROCESS_NAMES:
        return False
    if title_hint:
        return True
    if class_name.startswith(CONSOLE_WINDOW_CLASS_PREFIXES):
        return False
    return not (
        ctypes.windll.user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE) & WS_CAPTION
    )


def find_slideshow_window() -> tuple[int, str]:
    """查找正在放映的窗口，返回 ``(hwnd, title)``；未找到返回 ``(0, "")``。

    **前台窗口优先**（Luminalium 1 同款）：放映时放映窗口就是前台窗口，先看它
    既快又能避开「同名窗口挑错」的问题（双屏放映、演示者视图下会有多个候选）；
    前台不是再枚举全部顶层窗口逐个判定。
    """
    if not hasattr(ctypes, "windll"):
        return (0, "")
    user32 = ctypes.windll.user32
    try:
        foreground = int(user32.GetForegroundWindow() or 0)
    except OSError:  # pragma: no cover
        foreground = 0
    if foreground:
        try:
            facts = _window_facts(foreground)
            if _looks_like_slideshow(facts):
                return (int(facts[0]), facts[2])
        except OSError:  # pragma: no cover - 窗口在查询过程中销毁
            log.debug("读取前台窗口信息失败", exc_info=True)

    try:
        windows = _enum_windows()
    except OSError:  # pragma: no cover - 极端情况下的 Win32 失败
        log.debug("枚举窗口失败", exc_info=True)
        return (0, "")

    for facts in windows:
        if _looks_like_slideshow(facts):
            return (int(facts[0]), facts[2])
    return (0, "")


def find_powerpoint_console_window() -> int:
    """查找演示软件主窗口（非放映态也有），用于确保实例化 COM 时不新建进程。"""
    if not hasattr(ctypes, "windll"):
        return 0
    try:
        for hwnd, class_name, _title, *_rest in _enum_windows():
            if class_name.startswith(CONSOLE_WINDOW_CLASS_PREFIXES):
                return hwnd
    except OSError:  # pragma: no cover
        log.debug("枚举演示主窗口失败", exc_info=True)
    return 0


# --------------------------------------------------------------------------- 按键回退


def send_slideshow_key(vk_code: int, hwnd: int = 0) -> bool:
    """把按键发送到放映窗口，用于 COM 不可用时的降级路径。

    仅在本进程拥有前台权限时才生效；失败时静默返回 ``False``。
    """
    if not hasattr(ctypes, "windll"):
        return False
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    try:
        if hwnd:
            user32.SetForegroundWindow(hwnd)
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
        return True
    except OSError:  # pragma: no cover
        log.debug("发送按键失败", exc_info=True)
        return False


# --------------------------------------------------------------------------- COM 后端


class _ComBackend:
    """封装对 PowerPoint / WPS COM 对象模型的访问，失败时自动降级。

    WPS 演示的 COM 对象模型与 PowerPoint 同构（``SlideShowWindows`` /
    ``View.Next`` / ``EraseDrawing`` ...），同一套代码两条 ProgID 通吃。
    """

    def __init__(self) -> None:
        self._client = None
        self._pywin32_missing = False
        self._prog_id: Optional[str] = None  # 已 attach 的 ProgID

    # -- 生命周期 -----------------------------------------------------------

    def _get_client(self):
        if self._pywin32_missing:
            return None
        if self._client is None:
            try:
                import win32com.client  # type: ignore[import-not-found]
            except ImportError:
                log.info("未安装 pywin32，COM 通道禁用（仅保留窗口类探测）")
                self._pywin32_missing = True
                return None
            self._client = win32com.client
        return self._client

    def _attached(self):
        """拿到正在运行的演示软件实例；没有则返回 ``None``。

        依次尝试各 ProgID；某个 ProgID 一旦 attach 成功就记住，
        避免每 400ms 把三个都试一遍。应用退出后 ProgID 会失效，
        失效时清空缓存重新探测。
        """
        client = self._get_client()
        if client is None:
            return None

        candidates = (self._prog_id,) if self._prog_id else COM_PROG_IDS
        for prog_id in candidates:
            try:
                app = client.GetActiveObject(prog_id)
            except Exception:
                continue
            if self._prog_id != prog_id:
                log.info("COM 已连接: %s", prog_id)
            self._prog_id = prog_id
            return app
        if self._prog_id is not None:
            # 之前连上的实例已退出
            log.info("COM 连接失效（%s 已退出），重新探测", self._prog_id)
            self._prog_id = None
        return None

    def release(self) -> None:
        self._client = None
        self._prog_id = None

    # -- 读取 ---------------------------------------------------------------

    def _slideshow_window(self):
        """返回正在放映的 ``SlideShowWindow``，没有则 ``None``。"""
        app = self._attached()
        if app is None:
            return None
        try:
            if app.SlideShowWindows.Count == 0:
                return None
            return app.SlideShowWindows(1)
        except Exception:
            log.debug("读取 SlideShowWindows 失败", exc_info=True)
            return None

    def read_state(self) -> Optional[tuple[int, int, int]]:
        """返回 ``(当前页, 总页数, 放映窗口句柄)``，无法读取时返回 ``None``。

        ⚠️ 真机踩过：``view.Presentation`` **不一定存在**（PPT 动态 COM 绑定下
        直接抛 ``AttributeError``），一炸就是页码永远 0/0。页码与总页数必须
        分开取、各有回退（Luminalium 1 同款思路）：

        * 当前页优先 ``View.CurrentShowPosition``（放映序号，最准），
          回退 ``View.Slide.SlideIndex``；
        * 总页数从**放映窗口**的 ``Presentation`` 取，取不到再退回
          ``Application.ActivePresentation``。
        """
        window = self._slideshow_window()
        if window is None:
            return None
        try:
            view = window.View
        except Exception:
            log.debug("读取 SlideShowView 失败", exc_info=True)
            return None

        slide_index = 0
        for getter in (
            lambda: int(view.CurrentShowPosition),
            lambda: int(view.Slide.SlideIndex),
        ):
            try:
                value = getter()
                if value > 0:
                    slide_index = value
                    break
            except Exception:
                continue

        total = 0
        app = self._attached()
        for source in (window, app):
            if source is None:
                continue
            try:
                presentation = getattr(source, "Presentation", None)
            except Exception:
                presentation = None
            if presentation is None:
                continue
            try:
                total = int(presentation.Slides.Count)
            except Exception:
                total = 0
            if total > 0:
                break
        if total <= 0 and app is not None:
            try:
                total = int(app.ActivePresentation.Slides.Count)
            except Exception:
                total = 0

        try:
            hwnd = int(window.HWND)
        except Exception:
            hwnd = 0
        if slide_index <= 0 and total <= 0:
            log.debug("页码与总页数都没读到（COM 对象模型不兼容？）")
        return (slide_index, total, hwnd)

    def is_presenting(self) -> bool:
        """COM 视角：是否有放映窗口存在（页码读不出来也算）。"""
        return self._slideshow_window() is not None

    def describe(self) -> str:
        """一行 COM 通道状态，给诊断用（区分「连不上」和「连上了但没放映」）。"""
        if self._pywin32_missing:
            return "COM 未启用（未安装 pywin32，只剩窗口探测）"
        try:
            app = self._attached()
        except Exception:  # pragma: no cover - COM 异常不该带崩诊断
            return "COM 探测异常"
        if app is None:
            return "COM 未连接（ROT 里没有运行中的演示软件实例）"
        try:
            presentations = int(getattr(app, "Presentations", None).Count or 0)
        except Exception:
            presentations = -1
        try:
            shows = int(app.SlideShowWindows.Count or 0)
        except Exception:
            shows = -1
        return f"COM 已连接 {self._prog_id}：演示文稿 {presentations} 个，放映窗口 {shows} 个"

    # -- 操作 ---------------------------------------------------------------

    def _view(self):
        window = self._slideshow_window()
        return window.View if window is not None else None

    def next_slide(self) -> bool:
        view = self._view()
        if view is None:
            return False
        try:
            view.Next()
            return True
        except Exception:
            log.debug("下一页失败", exc_info=True)
            return False

    def previous_slide(self) -> bool:
        view = self._view()
        if view is None:
            return False
        try:
            view.Previous()
            return True
        except Exception:
            log.debug("上一页失败", exc_info=True)
            return False

    def goto_slide(self, index: int) -> bool:
        view = self._view()
        if view is None:
            return False
        try:
            view.GotoSlide(int(index))
            return True
        except Exception:
            log.debug("跳转页码失败", exc_info=True)
            return False

    def exit_slideshow(self) -> bool:
        view = self._view()
        if view is None:
            return False
        try:
            view.Exit()
            return True
        except Exception:
            log.debug("退出放映失败", exc_info=True)
            return False

    def set_pointer(self, pointer_type: int) -> bool:
        view = self._view()
        if view is None:
            return False
        try:
            view.PointerType = pointer_type
            return True
        except Exception:
            log.debug("切换指针失败", exc_info=True)
            return False

    def erase_drawings(self) -> bool:
        """擦除当前页的墨迹（对应放映态快捷键 ``E``）。"""
        view = self._view()
        if view is None:
            return False
        try:
            view.EraseDrawing()
            return True
        except Exception:
            log.debug("COM 擦除墨迹失败，将回退到按键方案", exc_info=True)
            return False


# --------------------------------------------------------------------------- 控制器


class _ProbeThread(QThread):
    """放映探测线程。

    **所有** Win32 枚举与 COM 调用都只发生在这个线程里。

    为什么必须挪出主线程：PowerPoint 的 COM 服务器是单套间（STA），
    放映过程中它随时可能忙碌（渲染动画 / 切换电源状态）。在主线程里每 400ms
    ``GetActiveObject`` + ``View.Slide.SlideIndex``，一次卡住就是整界面卡死
    ——托盘点不动、控制条不刷新，用户看到的就是「卡死了」。
    """

    # 用基本类型而不是 object：跨线程排队连接不需要 Python 对象做元类型转换
    stateReady = Signal(bool, int, int, int, str, str)

    def __init__(self, interval_ms: int = 400, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._interval_ms = max(100, int(interval_ms))
        self._running = True
        self._com = _ComBackend()
        self._commands: "queue.Queue[Tuple[str, tuple]]" = queue.Queue()
        self._wake = threading.Event()
        self._last = PresentationState()
        self._slow_logged = False
        # 每次探测刷新的 COM 通道状态（主线程只在诊断时读一下，够用）
        self._com_status = "尚未探测"

    # ---------------------------------------------------- 主线程侧（非阻塞）

    def request(self, name: str, *args) -> None:
        """投递一个控制命令，交给工作线程执行，立即返回。"""
        self._commands.put((name, args))
        self._wake.set()

    def poke(self) -> None:
        """唤醒一次探测（不等下一个周期）。"""
        self._wake.set()

    def set_probe_interval(self, interval_ms: int) -> None:
        self._interval_ms = max(100, int(interval_ms))
        self._wake.set()

    def stop_async(self) -> None:
        self._running = False
        self._wake.set()

    # ------------------------------------------------------------ 工作线程

    def stop(self) -> None:  # pragma: no cover - 兼容调用习惯
        self.stop_async()
        self.wait(3000)

    def run(self) -> None:
        pythoncom = None
        try:
            import pythoncom as _pc  # type: ignore

            pythoncom = _pc
            pythoncom.CoInitialize()
        except Exception:  # 没有 pywin32 也可以只做窗口类探测
            pythoncom = None
        try:
            while self._running:
                try:
                    self._drain_commands()
                    started = time.perf_counter()
                    state = self._probe_once()
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    if elapsed_ms > 1500 and not self._slow_logged:
                        log.warning(
                            "一次放映探测耗时 %.0fms（演示程序可能正忙）；"
                            "探测已在独立线程，界面不受影响",
                            elapsed_ms,
                        )
                        self._slow_logged = True
                    if state.marker != self._last.marker:
                        self._log_change(state)
                        self._last = state
                        self.stateReady.emit(
                            state.active, state.slide_index, state.slide_total,
                            state.window_handle, state.title, state.source,
                        )
                except Exception:  # 探测异常不能中断轮询
                    log.exception("放映状态探测失败")
                # 可被 poke() 提前唤醒，不必死等一个整周期
                self._wake.wait(self._interval_ms / 1000.0)
                self._wake.clear()
        finally:
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:  # pragma: no cover
                    pass

    def _drain_commands(self) -> None:
        while True:
            try:
                name, args = self._commands.get_nowait()
            except queue.Empty:
                return
            self._dispatch(name, args)

    def _dispatch(self, name: str, args: tuple) -> None:
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is None:
            log.warning("未知的控制命令: %s", name)
            return
        try:
            handler(*args)
        except Exception:
            log.exception("执行「%s」失败", name)

    # 命令实现（只在探测线程被调用）

    def _cmd_next(self, hwnd: int) -> None:
        if not self._com.next_slide():
            send_slideshow_key(VK_NEXT, hwnd)

    def _cmd_previous(self, hwnd: int) -> None:
        if not self._com.previous_slide():
            send_slideshow_key(VK_PRIOR, hwnd)

    def _cmd_goto(self, hwnd: int, index: int) -> None:
        if not self._com.goto_slide(index):
            log.info("跳转页码失败，目标 %s", index)

    def _cmd_exit(self, hwnd: int) -> None:
        if not self._com.exit_slideshow():
            send_slideshow_key(VK_ESCAPE, hwnd)

    def _cmd_clear(self, hwnd: int) -> None:
        if not self._com.erase_drawings():
            send_slideshow_key(VK_ERASE, hwnd)

    def _cmd_tool(self, hwnd: int, tool: str) -> None:
        pointer = TOOL_TO_POINTER.get(tool)
        if pointer is None:
            log.warning("未知工具: %s", tool)
            return
        if not self._com.set_pointer(pointer):
            fallback_keys = {"pen": 0x50, "arrow": 0x41, "eraser": 0x45}
            vk = fallback_keys.get(tool)
            if vk is not None:
                send_slideshow_key(vk, hwnd)

    # ------------------------------------------------------------ 探测本身

    def _probe_once(self) -> PresentationState:
        """单次探测（窗口类优先，COM 兜底）。只在探测线程调用。"""
        try:
            self._com_status = self._com.describe()
        except Exception:  # pragma: no cover - COM 状态只服务诊断，失败无所谓
            self._com_status = "COM 状态读取失败"
        hwnd, title = find_slideshow_window()
        if hwnd:
            slide_index = slide_total = 0
            numbers = self._com.read_state()
            if numbers is not None:
                slide_index, slide_total, _ = numbers
            return PresentationState(
                active=True,
                slide_index=slide_index,
                slide_total=slide_total,
                window_handle=hwnd,
                title=title,
                source="window",
            )

        # 窗口类没探到：COM 报告有放映窗口也算放映中
        try:
            numbers = self._com.read_state()
        except Exception:
            numbers = None
        if numbers is not None or self._com.is_presenting():
            if numbers is None:
                numbers = (0, 0, 0)
            slide_index, slide_total, com_hwnd = numbers
            if int(slide_index) < 0 or int(slide_total) < 0:
                slide_index, slide_total = 0, 0
            return PresentationState(
                active=True,
                slide_index=int(slide_index),
                slide_total=int(slide_total),
                window_handle=max(int(com_hwnd), 0),
                title="",
                source="com",
            )
        return PresentationState(active=False)

    def _log_change(self, state: PresentationState) -> None:
        old = self._last
        if state.active != old.active:
            if state.active:
                log.info(
                    "放映开始: hwnd=0x%08X 来源=%s 页码=%s/%s",
                    state.window_handle, state.source or "?",
                    state.slide_index or "?", state.slide_total or "?",
                )
            else:
                log.info("放映结束")
        elif state.active:
            log.info("放映状态更新: 页码=%s/%s", state.slide_index, state.slide_total)


class PptController(QObject):
    """放映状态轮询 + 放映控制的**独立**入口。

    对外的用法没变，但内部的探测与所有 COM 调用都跑在
    :class:`_ProbeThread` 里，主线程只收发信号，**永不被演示程序拖住**::

        ppt = PptController(interval_ms=400)
        ppt.stateChanged.connect(on_state)
        ppt.start()
        ...
        ppt.next_slide(state.window_handle)   # 只投递命令，立即返回
    """

    stateChanged = Signal(object)  # PresentationState（在主线程发出）

    def __init__(
        self,
        interval_ms: int = 400,
        config=None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._state = PresentationState()
        self._thread = _ProbeThread(interval_ms, self)
        self._thread.stateReady.connect(self._on_state_ready)
        self.apply_config(config)

    # ------------------------------------------------------------------ 配置

    def apply_config(self, config) -> None:
        """按配置刷新探测规则与轮询间隔（``presentation.*`` 是唯一来源）。"""
        if config is None:
            return
        try:
            configure_detection(
                config.get("presentation.window_classes", []) or [],
                config.get("presentation.process_names", []) or [],
                config.get("presentation.fullscreen_ratio", None),
            )
            self.set_interval(int(config.get("presentation.poll_interval_ms", 400)))
        except Exception:  # 配置异常不能连累探测
            log.debug("应用放映探测配置失败", exc_info=True)

    # ------------------------------------------------------------------ 状态

    @property
    def state(self) -> PresentationState:
        return self._state

    @property
    def controller(self) -> "PptController":
        """兼容旧调用（原来 watcher 与 controller 分离），现在就是自己。"""
        return self

    # ------------------------------------------------------------------ 生命周期

    def start(self) -> None:
        if not self._thread.isRunning():
            self._thread.start()

    def stop(self) -> None:
        self._thread.stop_async()

    def set_interval(self, interval_ms: int) -> None:
        self._thread.set_probe_interval(interval_ms)

    def refresh_now(self) -> None:
        self._thread.poke()

    def shutdown(self) -> None:
        self._thread.stop_async()
        if self._thread.isRunning():
            self._thread.wait(3000)

    # ------------------------------------------------------------------ 信号

    def _on_state_ready(
        self, active: bool, slide_index: int, slide_total: int,
        window_handle: int, title: str, source: str,
    ) -> None:
        """探测线程 -> 主线程。这里只组装对象再转发，不做任何阻塞操作。"""
        state = PresentationState(
            active=bool(active),
            slide_index=int(slide_index),
            slide_total=int(slide_total),
            window_handle=int(window_handle),
            title=str(title),
            source=str(source),
        )
        self._state = state
        self.stateChanged.emit(state)

    # ------------------------------------------------------------------ 自检

    def inject_state(self, state: PresentationState) -> None:
        """自检用：跳过探测线程直接注入一个状态（例如伪造「正在放映」）。"""
        self._thread._last = state
        self._on_state_ready(
            state.active, state.slide_index, state.slide_total,
            state.window_handle, state.title, state.source,
        )

    def diagnose(self) -> str:
        """返回一段人读的诊断信息（写进日志，用于真机排查）。

        **放映时跑一次这份诊断就能定位**：它会把当前所有「像放映窗口」的
        顶层窗口连同类名 / 标题 / 进程名 / 矩形一起列出来——如果真正的放映
        窗口在列表里但没被认出来，把它的类名或进程名填进
        ``presentation.window_classes`` / ``presentation.process_names`` 即可。
        """
        lines = ["PPT 控制器诊断:"]
        lines.append(f"  探测线程运行中: {self._thread.isRunning()} "
                     f"间隔 {self._thread._interval_ms}ms")
        lines.append(
            f"  当前状态: active={self._state.active} source={self._state.source!r} "
            f"hwnd=0x{self._state.window_handle:08X}"
        )
        lines.append(f"  COM 通道: {self._thread._com_status}")
        hwnd, title = find_slideshow_window()
        lines.append(f"  窗口探测: hwnd=0x{hwnd:08X} title={title!r} "
                     f"(类名白名单 {sorted(SLIDESHOW_WINDOW_CLASSES)})")
        if not hasattr(ctypes, "windll"):
            return "\n".join(lines)

        try:
            windows = _enum_windows()
        except OSError:  # pragma: no cover
            lines.append("  枚举窗口失败")
            return "\n".join(lines)

        frames = [f"0x{h:08X}({c})" for h, c, *_ in windows
                  if c.startswith(CONSOLE_WINDOW_CLASS_PREFIXES)]
        lines.append(f"  演示主窗口: {frames or '无'}")

        user32 = ctypes.windll.user32
        scored: list[tuple[int, str]] = []
        for facts in windows:
            cand_hwnd, class_name, cand_title, pid, visible, rect = facts
            if not visible:
                continue
            lowered = class_name.lower()
            known_class = lowered in SLIDESHOW_WINDOW_CLASSES or "slideshow" in lowered
            title_hint = _title_looks_like_slideshow(cand_title)
            # 桌面窗口成百上千，OpenProcess 不便宜：只有值得看的才去查进程名
            fullscreen = True if title_hint else _covers_monitor(cand_hwnd)
            if not (known_class or title_hint or fullscreen):
                continue
            process = _process_name(pid) if (title_hint or fullscreen) else ""
            known_process = process in SLIDESHOW_PROCESS_NAMES
            caption = bool(
                user32.GetWindowLongW(wintypes.HWND(cand_hwnd), GWL_STYLE) & WS_CAPTION
            )
            verdict = _looks_like_slideshow(facts)
            scored.append((
                # 已被判定为放映的排最前，其次命中白名单，桌面外壳自然沉底
                (8 if verdict else 0) + (4 if known_class else 0)
                + (2 if known_process else 0) + (1 if fullscreen else 0)
                + (1 if title_hint else 0),
                f"  候选: {'判定=放映中' if verdict else '判定=否     '} "
                f"hwnd=0x{cand_hwnd:08X} class={class_name!r} "
                f"title={cand_title[:36]!r} proc={process or '?'} "
                f"size={rect[2] - rect[0]}x{rect[3] - rect[1]} "
                f"全屏={fullscreen} 标题栏={caption} 标题像放映={title_hint} "
                f"类名命中={known_class} 进程命中={known_process}",
            ))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        listed = [text for _score, text in scored[:12]]
        lines.append("  可见顶层窗口中的可疑者（放映时放映窗口应在这里，"
                     "且「判定=放映中」应当出现一次；按相关度排序）:")
        lines.extend(listed or ["    （无）"])
        # 演示软件在跑但 COM 连不上 —— 十有八九是 UAC 完整性级别不一致：
        # ROT 按完整性级别隔离，级别不同就互相看不见（实测：本进程 High +
        # PowerPoint Medium 时 ROT 条目数为 0，GetActiveObject 直接 0x800401E3）。
        if "未连接" in self._thread._com_status and frames:
            lines.append(
                "  提示: 演示软件在运行但 COM 连不上 —— 通常本程序与演示软件的"
                "**权限级别不一致**（一个以管理员运行、另一个不是）。UAC 会按完整性"
                "级别隔离 COM，连不上时翻页 / 笔 / 页码 / 退出放映只剩键盘回退。"
                "请以与演示软件**相同**的权限级别运行 Luminalium。"
            )
        if not self._state.active:
            lines.append(
                "  结论: 未检测到放映，顶层窗口不会显示。若此时确实在放映，"
                "把上面候选里的 class / proc 填进 presentation.window_classes "
                "/ presentation.process_names"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ 控制

    def next_slide(self, hwnd: int = 0) -> bool:
        self._thread.request("next", int(hwnd or 0))
        return True

    def previous_slide(self, hwnd: int = 0) -> bool:
        self._thread.request("previous", int(hwnd or 0))
        return True

    def goto_slide(self, index: int, hwnd: int = 0) -> bool:
        self._thread.request("goto", int(hwnd or 0), int(index))
        return True

    def exit_slideshow(self, hwnd: int = 0) -> bool:
        self._thread.request("exit", int(hwnd or 0))
        return True

    def set_tool(self, tool: str, hwnd: int = 0) -> bool:
        """切换笔 / 橡皮 / 箭头。``tool`` 取 ``pen``/``eraser``/``arrow``/``none``。"""
        if tool not in TOOL_TO_POINTER:
            log.warning("未知工具: %s", tool)
            return False
        self._thread.request("tool", int(hwnd or 0), tool)
        return True

    def clear_screen(self, hwnd: int = 0) -> bool:
        """清屏：擦除本页墨迹。"""
        self._thread.request("clear", int(hwnd or 0))
        return True
