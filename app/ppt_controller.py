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
   ``PowerPoint.Application``（MS Office）、``Kwpp.Application``（WPS 演示）
   与永中那套 ProgID，读取当前页码 / 总页数；窗口类没探到但 COM 报告有
   放映窗口时（例如窗口类改名 / 异常形态），用 COM 的
   ``SlideShowWindows(1).HWND`` 兜底判定为放映中。

**软件族（kind）**：探测成功后会再判一次「这是哪家的放映」（``ppt`` / ``wps`` /
``yozo``）。这不是锦上添花 —— 控制腿要靠它选路线：

* ``View.PointerType`` 直写三族通用，是首选；
* 失败后的快捷键回退**按族区分**：PowerPoint / WPS 用 ``Ctrl+P`` / ``Ctrl+E`` /
  ``Ctrl+A``，永中只发它认得的 ``Ctrl+E`` / ``Ctrl+A``（给它发 ``Ctrl+P`` 是无效动作）；
* 墨迹调色板（``InkColorPicker``）与「退出时保留墨迹」是 **PowerPoint 专属**，
  对 WPS / 永中下发只会白等一轮。

控制操作（翻页 / 退出 / 笔 / 清屏）COM 失败时回退为向放映窗口发按键。按键注入按
**完整性级别**选路：同级 / 更低走 ``keybd_event``，本进程级别更高时 UIPI 会把
``keybd_event`` 静默吞掉（不报错也不生效），改走 ``PostMessage`` 直投放映窗口 ——
这是「按钮点了没反应」最隐蔽的成因。翻页另有一道 1 秒窗口的限流（对齐
Luminalium 1 ``PPT.PageTurnRateLimit``），超出的直接丢弃。

**线程模型（务必遵守，这是一次真机事故换来的）**：窗口探测与 COM 是**两条独立线程**。
:class:`_ProbeThread` 只做 Win32 枚举（毫秒级），:class:`_ComThread` 承担全部 COM 调用。
原因：PowerPoint 是单套间（STA），它自己的主线程不抽消息时（放映中 / 弹模态框 /
保存时）跨进程调用会**一直排队**；早前两者挤在一条线程里，一次 `GetActiveObject`
卡住就把整条探测链路拖死 —— 日志静默、控制条永不出现。拆分后 COM 卡住只退化成
「页码 0/0 + 键盘回退」，窗口探测照常。主线程另有看护定时器，两条线程静默超时
就写「卡在哪个阶段、卡了多久」。

所有状态变化都以 INFO 级写日志（``luminalium.ppt``），真机排查
「顶层窗口为什么没出来」先看这里有没有 ``放映开始`` 一行，再看有没有
``放映链路卡住`` 一行（后者会直接点名卡住的线程与阶段）。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import QObject, QThread, QTimer, Signal

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

# ---------------------------------------------------------------- 软件族（kind）
# 「哪家的放映」决定控制腿怎么走（照 Luminalium 1 的 kind 区分）：
# PowerPoint 有完整的 COM 指针控制 + InkColorPicker 调色板；
# WPS / 永中要靠 Ctrl+P / Ctrl+E 那套快捷键，且别对它们下 PowerPoint 专属的 MSO 命令。
# 每一族各自持有一份「类名 / 进程名」规则，探测时先定族、再用**该族**的规则复判，
# 避免「用 PowerPoint 的规则去否掉一个 WPS 窗口」这类张冠李戴。
APP_KIND_PPT = "ppt"
APP_KIND_WPS = "wps"
APP_KIND_YOZO = "yozo"

KIND_CLASS_HINTS: dict[str, tuple[str, ...]] = {
    APP_KIND_PPT: ("screenclass",),
    APP_KIND_WPS: ("wppslideshowwindowclass", "wpp slideshow window",
                   "wpp slideshow window 8.0", "wps"),
    APP_KIND_YOZO: ("yozo",),
}
KIND_PROCESS_HINTS: dict[str, tuple[str, ...]] = {
    APP_KIND_PPT: ("POWERPNT.EXE", "PPTVIEW.EXE"),
    APP_KIND_WPS: ("WPP.EXE", "KWPP.EXE", "WPS.EXE"),
    APP_KIND_YOZO: ("YOZO_IMPRESS.EXE", "YOZOPG.EXE", "YOZO_OFFICE.EXE"),
}
# 各族在自己的窗口上，**确实能用**的快捷键。Ctrl+P 开笔 / Ctrl+E 开橡皮 / Ctrl+A 回指针，
# 这三个在 PowerPoint 与 WPS 演示上都成立（L1 的 set_pointer_type 用的就是它们）；
# 永中只保证 A/E（笔要靠方向键那套，不稳，宁可不发）。
KIND_TOOL_SHORTCUTS: dict[str, dict[str, int]] = {
    APP_KIND_PPT: {"pen": ord("P"), "eraser": ord("E"), "arrow": ord("A")},
    APP_KIND_WPS: {"pen": ord("P"), "eraser": ord("E"), "arrow": ord("A")},
    APP_KIND_YOZO: {"eraser": ord("E"), "arrow": ord("A")},
}
# 调色板（InkColorPicker）只有 PowerPoint 认；WPS / 永中不走这条，只做 COM 直写。
KIND_SUPPORTS_INK_PALETTE = {APP_KIND_PPT}
# 退出前问「墨迹留不留」只有 PowerPoint 有原生那套（DisplayAlerts + InkAnnotations）。
KIND_SUPPORTS_INK_PROMPT = {APP_KIND_PPT}

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

# PpSlideShowPointerType（Microsoft Learn 的枚举表逐项核对过 —— ⚠️ **3 不是橡皮**，
# 是 AlwaysHidden：之前写 3，切橡皮的结果就是「光标消失、点击行为等同指针」，
# 因为 PowerPoint 把它当成了「指针永远隐藏」）：
#   0=None 1=Arrow 2=Pen 3=AlwaysHidden 4=AutoArrow **5=Eraser**
PP_POINTER_NONE = 0
PP_POINTER_ARROW = 1
PP_POINTER_PEN = 2
PP_POINTER_ALWAYS_HIDDEN = 3
PP_POINTER_AUTO_ARROW = 4
PP_POINTER_ERASER = 5

# PpSlideShowState：1=运行中 2=暂停 3=黑屏 4=白屏 5=已结束 6=切场中。
# 只有「已结束」要当成不在放映；黑屏 / 白屏仍是放映态（还要翻页、还要退出）。
PP_SHOW_DONE = 5

# 语义化工具名 -> COM 指针类型
TOOL_TO_POINTER = {
    "none": PP_POINTER_NONE,
    "arrow": PP_POINTER_ARROW,
    "pen": PP_POINTER_PEN,
    "eraser": PP_POINTER_ERASER,
}

# 指针切换的重试阶梯 —— **逐字照抄 Luminalium 1 ``set_pointer_type``** 的
# ``delays = (0.0, 0.08, 0.16, 0.28)``：每个间隔后面再试一次直写 COM。
# 这个「多试几次」不是凑数：PowerPoint 在刚切完模式的瞬间会拒绝属性写入，
# 立刻重试就成功，而单发一次失败后直接掉进键盘回退反而更容易出问题。
L1_POINTER_RETRY_DELAYS = (0.0, 0.08, 0.16, 0.28)
# 发快捷键前后的等待（L1 用 0.02 / 0.05；这里略放宽，放映窗口抢焦点本身有延迟）
L1_SHORTCUT_GAP_S = 0.03
L1_SHORTCUT_SETTLE_S = 0.06

# 放映态按键（COM 不可用时的降级路径）
VK_NEXT = 0x22  # PageDown
VK_PRIOR = 0x21  # PageUp
VK_DOWN = 0x28  # ↓（部分放映软件只认方向键，Luminalium 1 同款兜底）
VK_UP = 0x26    # ↑
VK_ESCAPE = 0x1B
VK_ERASE = 0x45  # E

# 键盘消息（PostMessage 降级路径用）
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


@dataclass(frozen=True)
class PresentationState:
    """一次探测的结果快照。"""

    active: bool = False
    slide_index: int = 0
    slide_total: int = 0
    window_handle: int = 0
    title: str = ""
    source: str = ""  # "window" = 窗口类命中；"com" = COM 兜底
    kind: str = ""    # "ppt" / "wps" / "yozo"：判定为放映的软件族，决定控制走哪条腿

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


def _class_matches_kind(class_name: str, kind: str) -> bool:
    """类名是否属于 ``kind`` 这一族。"""
    lowered = str(class_name or "").lower()
    return any(hint in lowered for hint in KIND_CLASS_HINTS.get(kind, ()))


def _process_matches_kind(process_name: str, kind: str) -> bool:
    """进程映像名是否属于 ``kind`` 这一族。"""
    upper = str(process_name or "").upper()
    return any(upper == hint or hint in upper
               for hint in KIND_PROCESS_HINTS.get(kind, ()))


def _kind_from_window(class_name: str, process_name: str, title: str) -> str:
    """按「类名 → 进程名 → 标题」的顺序判定这个窗口是哪一族的放映。

    返回 ``""`` 表示认不出（那就谁都不像，不猜）。判定顺序照 Luminalium 1：
    类名最准，进程名次之，标题只在前两者都空时兜底。
    """
    for kind in (APP_KIND_PPT, APP_KIND_WPS, APP_KIND_YOZO):
        if _class_matches_kind(class_name, kind):
            return kind
    for kind in (APP_KIND_PPT, APP_KIND_WPS, APP_KIND_YOZO):
        if _process_matches_kind(process_name, kind):
            return kind
    if _title_looks_like_slideshow(title):
        # 标题只说「这是放映」，说不出是哪家 —— 交给接下来的进程名/类名细节
        return ""
    return ""


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


def _near_miss_reason(facts) -> Optional[str]:
    """疑似放映却被拒时的**拒绝原因**；判定成功或离得远返回 ``None``。

    只关心「进程命中白名单 +（标题像放映 或 铺满整屏）」的近失窗口：
    再远（游戏 / 视频播放器这类全屏窗口）就与本工具无关，不该产生日志噪音。
    """
    hwnd, class_name, title, pid, visible, _rect = facts
    if not hwnd or not visible:
        return None
    lowered = class_name.lower()
    if lowered in SLIDESHOW_WINDOW_CLASSES or "slideshow" in lowered:
        return None  # 判定成功
    title_hint = _title_looks_like_slideshow(title)
    fullscreen = True if title_hint else _covers_monitor(hwnd)
    if not (title_hint or fullscreen):
        return None  # 离得远
    if _process_name(pid) not in SLIDESHOW_PROCESS_NAMES:
        return None  # 不是演示软件，不关心
    if title_hint:
        return None  # 标题像放映的直接判成是，到这里说明已成功
    if class_name.startswith(CONSOLE_WINDOW_CLASS_PREFIXES):
        return f"编辑器主窗口（类名前缀命中 {class_name}）"
    if ctypes.windll.user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE) & WS_CAPTION:
        return "有标题栏（WS_CAPTION）"
    return "全部条件通过却未命中（逻辑矛盾，视为 bug）"


def find_slideshow_window() -> tuple[int, str, str]:
    """查找正在放映的窗口，返回 ``(hwnd, title, kind)``；未找到返回 ``(0, "", "")``。

    ``kind`` 是软件族（``ppt`` / ``wps`` / ``yozo``，认不出为 ``""``）——
    控制腿要靠它选路线（见 ``KIND_TOOL_SHORTCUTS``）。

    **前台窗口优先**（Luminalium 1 同款）：放映时放映窗口就是前台窗口，先看它
    既快又能避开「同名窗口挑错」的问题（双屏放映、演示者视图下会有多个候选）；
    前台不是再枚举全部顶层窗口逐个判定。
    """
    if not hasattr(ctypes, "windll"):
        return (0, "", "")
    user32 = ctypes.windll.user32
    try:
        foreground = int(user32.GetForegroundWindow() or 0)
    except OSError:  # pragma: no cover
        foreground = 0
    if foreground:
        try:
            facts = _window_facts(foreground)
            if _looks_like_slideshow(facts):
                return (int(facts[0]), facts[2], _facts_kind(facts))
        except OSError:  # pragma: no cover - 窗口在查询过程中销毁
            log.debug("读取前台窗口信息失败", exc_info=True)

    try:
        windows = _enum_windows()
    except OSError:  # pragma: no cover - 极端情况下的 Win32 失败
        log.debug("枚举窗口失败", exc_info=True)
        return (0, "", "")

    for facts in windows:
        if _looks_like_slideshow(facts):
            return (int(facts[0]), facts[2], _facts_kind(facts))
    return (0, "", "")


def _facts_kind(facts) -> str:
    """由窗口事实推定软件族（认不出返回 ``""``）。

    比 ``_kind_from_window`` 多做一步「兜底」：类名与进程名都认不出时，
    按进程名在**全局白名单**里的位置猜 —— 我们只会在白名单窗口上调这个函数，
    所以哪怕是很旧的 WPS 变体（进程名不在族规则里）也能归到最近的族，
    不至于因为认不出族而把控制腿退化成「什么都控制不了」。
    """
    _hwnd, class_name, title, pid, _visible, _rect = facts
    process = _process_name(pid)
    kind = _kind_from_window(class_name, process, title)
    if kind:
        return kind
    upper = str(process or "").upper()
    if any(token in upper for token in ("WPP", "WPS", "KWPP")):
        return APP_KIND_WPS
    if "YOZO" in upper:
        return APP_KIND_YOZO
    if process:
        return APP_KIND_PPT
    return ""


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


# --------------------------------------------------------------------------- 前台激活


# 前台锁定（foreground lock）允许「谁在最近 N 毫秒内拥有过前台」再次夺回前台。
# 演示软件本来就是用户正在看的窗口，这条时限内把它拉回前台是允许的；
# 超过时限才会被系统拒绝（返回 0 但不抛异常）。
_FOREGROUND_LOCK_MS = 0x20000000


def focus_slideshow_window(hwnd: int) -> bool:
    """把放映窗口拉到前台，**这是切换指针的必要前提**。

    ⚠️ 真机踩过（Luminalium 1 ``_try_apply_pointer_type`` 里的关键一句，
    我们上一版漏了）：PowerPoint 的 ``View.PointerType`` **只对处于前台的放映
    窗口生效**。窗口不在前台时：

    * ``view.PointerType = 2`` 不抛异常 —— 看起来「写成功了」；
    * 但 PowerPoint 内部**根本不切指针**，读回仍是旧值；
    * 于是走 Ctrl+P / Ctrl+E 回退，而 ``keybd_event`` 又要求窗口在前台，
      ``SetForegroundWindow`` 若被前台锁定拒绝，整条链路**静默全灭**。

    用户看到的就是「橡皮点了没反应」。

    这里是三条腿，按可靠性递进：

    1. ``AllowSetForegroundWindow(ASFW_ANY)`` + ``SetForegroundWindow``；
    2. ``SetWindowPos(HWND_TOPMOST)`` 顶一下再 ``SetForegroundWindow``
       （有些全屏放映窗口只认这条，与我们的穿透塑形逻辑不冲突）；
    3. ``SetActiveWindow`` 兜底。

    只负责「尝试」，不保证成功 —— 返回是否已经在前台，调用方不必据此分枝，
    照常往下走即可（写属性本身有读回校验兜着）。
    """
    if not hwnd or not hasattr(ctypes, "windll"):
        return False
    user32 = ctypes.windll.user32
    try:
        handle = wintypes.HWND(int(hwnd))
        if int(user32.GetForegroundWindow() or 0) == int(hwnd):
            return True
    except OSError:  # pragma: no cover
        return False
    try:
        # 允许本进程把任意窗口设成前台（否则前台锁定会拒绝跨进程调用）
        user32.AllowSetForegroundWindow(wintypes.HWND(-1))
    except (OSError, AttributeError):  # pragma: no cover
        pass
    for attempt in (
        lambda: user32.SetForegroundWindow(handle),
        lambda: (
            user32.SetWindowPos(handle, wintypes.HWND(-1), 0, 0, 0, 0, 0x0003),  # NOMOVE|NOSIZE
            user32.SetForegroundWindow(handle),
        ),
        lambda: user32.SetActiveWindow(handle),
    ):
        try:
            attempt()
        except OSError:  # pragma: no cover - 窗口销毁竞态
            continue
        try:
            if int(user32.GetForegroundWindow() or 0) == int(hwnd):
                return True
        except OSError:  # pragma: no cover
            pass
    return False


# --------------------------------------------------------------------------- 按键回退


def _window_pid(hwnd: int) -> int:
    """窗口所属进程 PID；失败返回 0。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return 0
    try:
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(
            wintypes.HWND(int(hwnd)), ctypes.byref(pid)
        )
        return int(pid.value)
    except OSError:  # pragma: no cover - 窗口销毁竞态
        return 0


def _key_lparam(vk: int, key_up: bool = False) -> int:
    """构造 ``WM_KEYDOWN`` / ``WM_KEYUP`` 的 lParam。

    lParam 不是随便填 0 就能用的：它带**扫描码**与「抬起」标志位，填错的
    消息很多程序会当成无效按键直接丢掉（Luminalium 1 ``_build_key_lparam``
    的做法）。
    """
    scan = 0
    try:
        scan = int(ctypes.windll.user32.MapVirtualKeyW(int(vk), 0) or 0)
    except (OSError, AttributeError):  # pragma: no cover - 非 Windows
        pass
    lparam = 1 | (scan << 16)
    if key_up:
        lparam |= 0xC0000000  # 前一次按键状态位 + 抬起转换位
    return lparam


def _post_key_to_window(hwnd: int, vk: int) -> bool:
    """把按键**直接投递**到指定窗口，不依赖前台焦点。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return False
    user32 = ctypes.windll.user32
    try:
        handle = wintypes.HWND(int(hwnd))
        user32.PostMessageW(handle, WM_KEYDOWN, int(vk), _key_lparam(vk, False))
        user32.PostMessageW(handle, WM_KEYUP, int(vk), _key_lparam(vk, True))
        return True
    except OSError:  # pragma: no cover
        return False


def send_slideshow_key(vk_code: int, hwnd: int = 0) -> bool:
    """把按键送到放映窗口 —— COM 不可用 / COM 执行失败时的降级路径。

    两条腿，按**完整性级别**选路（UAC 的 UIPI 只允许向**同级或更低**级别注入）：

    * 同级 / 更低：``SetForegroundWindow`` 后 ``keybd_event``（最可靠，
      真实走一遍键盘输入栈）；
    * **本进程级别更高**：``keybd_event`` 会被 UIPI **静默丢弃**（不报错也
      不生效），直接 ``PostMessage`` 到放映窗口即可 —— 向低级别窗口投递
      消息是允许的。

    Luminalium 1 也是这两条腿（``_send_vk_to_slideshow``：先 keybd_event、
    异常时退 ``PostMessage``）；这里额外把「谁会失败」提前判掉，因为
    keybd_event 被吞掉时**不会有任何异常**可捕获 —— 那正是「按钮点了没反应」
    最隐蔽的成因。
    """
    if not hasattr(ctypes, "windll"):
        return False
    user32 = ctypes.windll.user32
    target = _window_pid(hwnd) if hwnd else 0
    if target and _integrity_rank(target) < _self_integrity_rank():
        log.debug("目标进程完整性级别更低，keybd_event 会被 UIPI 丢弃，改用 PostMessage")
        return _post_key_to_window(hwnd, vk_code)
    try:
        if hwnd:
            user32.SetForegroundWindow(wintypes.HWND(int(hwnd)))
        user32.keybd_event(int(vk_code), 0, 0, 0)
        user32.keybd_event(int(vk_code), 0, 0x0002, 0)  # KEYEVENTF_KEYUP
        return True
    except OSError:  # pragma: no cover
        log.debug("keybd_event 注入失败，改用 PostMessage", exc_info=True)
        return _post_key_to_window(hwnd, vk_code)


VK_CONTROL = 0x11  # Ctrl


def _post_ctrl_key_to_window(hwnd: int, vk: int) -> bool:
    """Ctrl+<vk> 组合键直投窗口（``send_slideshow_key`` 的 Ctrl 版）。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return False
    user32 = ctypes.windll.user32
    try:
        handle = wintypes.HWND(int(hwnd))
        for message, vk_code, up in (
            (WM_KEYDOWN, VK_CONTROL, False),
            (WM_KEYDOWN, int(vk), False),
            (WM_KEYUP, int(vk), True),
            (WM_KEYUP, VK_CONTROL, True),
        ):
            user32.PostMessageW(handle, message, vk_code, _key_lparam(vk_code, up))
        return True
    except OSError:  # pragma: no cover
        return False


def send_slideshow_ctrl_key(vk: int, hwnd: int = 0) -> bool:
    """把 ``Ctrl+<vk>`` 送到放映窗口（切换笔 / 橡皮 / 指针用的降级腿）。

    为什么要发 Ctrl 组合而不是单键：放映态下 ``P`` / ``E`` / ``A`` 单键在很多
    版本里被当成导航（``P`` 是上一页、``A`` 是自动播放），**Ctrl+P / Ctrl+E /
    Ctrl+A** 才是标注工具的标准快捷键 —— Luminalium 1 ``set_pointer_type``
    走的正是这一组。选路规则与 :func:`send_slideshow_key` 完全一致。
    """
    if not hasattr(ctypes, "windll"):
        return False
    user32 = ctypes.windll.user32
    target = _window_pid(hwnd) if hwnd else 0
    if target and _integrity_rank(target) < _self_integrity_rank():
        log.debug("目标进程完整性级别更低，改用 PostMessage 投递 Ctrl 组合")
        return _post_ctrl_key_to_window(hwnd, vk)
    try:
        if hwnd:
            user32.SetForegroundWindow(wintypes.HWND(int(hwnd)))
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(int(vk), 0, 0, 0)
        user32.keybd_event(int(vk), 0, 0x0002, 0)
        user32.keybd_event(VK_CONTROL, 0, 0x0002, 0)
        return True
    except OSError:  # pragma: no cover
        log.debug("Ctrl 组合注入失败，改用 PostMessage", exc_info=True)
        return _post_ctrl_key_to_window(hwnd, vk)


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

    @property
    def kind(self) -> str:
        """当前连上的 COM 实例属于哪一族（``ppt`` / ``wps`` / ``yozo``）。

        靠已 attach 的 ProgID 反推：``Kwpp.Application`` 是 WPS 演示，
        永中那套有 ``Yozo`` 字样，其余（``PowerPoint.Application``）算 PowerPoint。
        窗口通道认不出族时（WPS 放映窗口类名随版本变），这一份是最可靠的补充。
        """
        prog_id = (self._prog_id or "").lower()
        if not prog_id:
            return ""
        if "kwpp" in prog_id or "wpp" in prog_id or "wps" in prog_id:
            return APP_KIND_WPS
        if "yozo" in prog_id:
            return APP_KIND_YOZO
        return APP_KIND_PPT

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

    def _attached(self, force_refresh: bool = False):
        """拿到正在运行的演示软件实例；没有则返回 ``None``。

        依次尝试各 ProgID；某个 ProgID 一旦 attach 成功就记住，
        避免每 400ms 把三个都试一遍。应用退出后 ProgID 会失效，
        失效时清空缓存重新探测。

        ``force_refresh=True`` 时**忽略 ``_prog_id`` 缓存**、把全部 ProgID 重试
        一遍。用于「拿到的对象模型是半吊子」的场景：真机上遇到过 ROT 里的
        ``PowerPoint.Application`` 引用**不暴露 ``SlideShowWindows``**
        （抛 ``AttributeError``），此时重新 ``GetActiveObject`` 往往能拿到一个
        完整的引用 —— 缓存本身没错，是那一次拿到的东西不对。
        """
        client = self._get_client()
        if client is None:
            return None

        candidates = COM_PROG_IDS if force_refresh else (
            (self._prog_id,) if self._prog_id else COM_PROG_IDS
        )
        for prog_id in candidates:
            try:
                app = client.GetActiveObject(prog_id)
            except Exception:
                continue
            if self._prog_id != prog_id:
                log.info("COM 已连接: %s", prog_id)
            self._prog_id = prog_id
            return app
        if self._prog_id is not None and not force_refresh:
            # 之前连上的实例已退出
            log.info("COM 连接失效（%s 已退出），重新探测", self._prog_id)
            self._prog_id = None
        return None

    def release(self) -> None:
        self._client = None
        self._prog_id = None

    # -- 读取 ---------------------------------------------------------------

    @staticmethod
    def _safe_count(collection) -> int:
        """集合的 ``Count``；集合为 ``None`` 或对象模型不暴露该属性时返回 0。

        照 L1 ``_safe_count``。这是与 PowerPoint 动态绑定打交道时**必须**的
        一层保护：绑不上的属性抛的是 ``AttributeError``（不是返回空集合），
        直接写 ``app.SlideShowWindows.Count`` 会一炸一个准。
        """
        try:
            return int(getattr(collection, "Count", 0) or 0)
        except Exception:
            return 0

    def _slideshow_windows(self, retry: bool = True):
        """``app.SlideShowWindows`` 集合；**取不到一律返回 ``None``**。

        ⚠️ 真机日志里反复出现的 ``AttributeError:
        PowerPoint.Application.SlideShowWindows`` 就出在这里 —— ROT 里取到的
        ``Application`` 对象在动态绑定下**不一定暴露 ``SlideShowWindows``**
        （PowerPoint 未进入放映、或该 COM 引用是"半吊子"对象时都会）。
        以前这里直接 ``app.SlideShowWindows.Count``，一抛异常就被外层
        ``except`` 吞成「没有放映窗口」，于是：页码永远 0/0、橡皮等所有需要
        ``View`` 的操作全部静默失效。

        现在：先 ``getattr`` 安全取；属性不可用时（且 ``retry`` 为真）**换一个
        新鲜的 ``Application`` 引用再试一次** —— 这是真机上唯一有效的补救。
        """
        app = self._attached()
        if app is None:
            return None
        try:
            windows = getattr(app, "SlideShowWindows", None)
        except Exception:
            windows = None
        if windows is not None:
            return windows
        if retry:
            # 换一个引用再试：半吊子 COM 引用重新 GetActiveObject 常能修好
            fresh = self._attached(force_refresh=True)
            if fresh is not None and fresh is not app:
                try:
                    windows = getattr(fresh, "SlideShowWindows", None)
                except Exception:
                    windows = None
                if windows is not None:
                    log.info("重新获取 PowerPoint.Application 后 SlideShowWindows 可用了")
                    return windows
            log.debug("Application 对象不暴露 SlideShowWindows（未放映或引用不完整）")
        return None

    def _slideshow_window(self):
        """返回正在放映的 ``SlideShowWindow``，没有则 ``None``。"""
        window = self._slideshow_window_from(self._slideshow_windows(retry=False))
        if window is not None:
            return window
        # 第一个引用说不清（属性不可用 / 集合为空）时，换新引用再判一次 ——
        # 「明明在放映却读不到」多半是第一次拿到的 COM 引用不完整。
        fresh = self._slideshow_windows(retry=True)
        if fresh is None:
            return None
        return self._slideshow_window_from(fresh)

    def _slideshow_window_from(self, windows):
        """从 ``SlideShowWindows`` 集合里取放映窗口并过滤「已结束」。"""
        if windows is None or self._safe_count(windows) <= 0:
            return None
        try:
            window = windows(1)
        except Exception:
            log.debug("取 SlideShowWindow(1) 失败", exc_info=True)
            return None
        # 放映窗口对象可能还挂着，但放映其实已经结束（State = ppSlideShowDone）。
        # 这时若仍算「放映中」，退出放映后控制条会赖着不走。
        # Luminalium 1 用 ``view.State in (1, 2)`` 判定，代价是按 B/W 键
        # 黑屏(3)/白屏(4) 时也会被判成没在放映；这里只排除「已结束」。
        try:
            if int(window.View.State) == PP_SHOW_DONE:
                return None
        except Exception:
            pass  # 读不到 State 就不下判断，退回「有窗口即在放映」
        return window

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

    def read_position(self) -> Optional[tuple[int, int]]:
        """**轻量**读当前页 —— 只取 ``CurrentShowPosition``，不碰总页数。

        总页数在一场放映里是**常量**，每次刷新都去读只是白白多两次跨进程调用
        （``Presentation.Slides.Count`` 走的是完整对象模型，比读一个整数慢得多）。
        所以翻页后的即时刷新走这条：页码要快，总页数由常规刷新（或首次进入
        放映时）补上。返回 ``None`` 表示读不到放映窗口。
        """
        window = self._slideshow_window()
        if window is None:
            return None
        try:
            view = window.View
        except Exception:
            return None
        try:
            position = int(view.CurrentShowPosition)
        except Exception:
            return None
        try:
            hwnd = int(window.HWND)
        except Exception:
            hwnd = 0
        return (position, hwnd)

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
            presentations = None
        # 用 _safe_count 而不是直接取属性：动态绑定下 SlideShowWindows 可能
        # 整个不存在（抛 AttributeError），那种情况要说「属性不可用」而不是
        # 含混地报「0 个」—— 这两者排查方向完全不同。
        windows = self._slideshow_windows()
        if windows is None:
            shows = "属性不可用"
        else:
            shows = f"{self._safe_count(windows)}"
        shown_presentations = "属性不可用" if presentations is None else str(presentations)
        return (f"COM 已连接 {self._prog_id}：演示文稿 {shown_presentations} 个，"
                f"放映窗口 {shows}")

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

    def set_pointer(self, pointer_type: int, hwnd: int = 0) -> bool:
        """切换放映指针（笔 / 橡皮 / 箭头）。

        这里照 Luminalium 1 ``_try_apply_pointer_type`` 做了两件容易被省掉、
        但**缺一不可**的事：

        1. **先把放映窗口拉到前台**（``focus_slideshow_window``）。这是 L1 里的
           ``self._focus_slideshow_window(hwnd)`` —— PowerPoint 的
           ``View.PointerType`` 只对前台放映窗口生效，窗口不在前台时写属性不抛
           异常却**不会真正切指针**。上一版漏了这一步，「橡皮点了没反应」就是
           这个原因（写"成功"了 → 读回不符 → 走快捷键 → 快捷键又要求前台 →
           前台锁定拒绝 → 全链静默失败）。
        2. **先无条件设一次「箭头」再设目标值**。PowerPoint 的
           ``View.PointerType`` 在「已经处于某个标注模式」时，直接写同一个族的
           值有时不生效（橡皮 → 笔尤其明显）；先回落到箭头清掉模式，目标值才
           落得下。

        写完还要**读回校验**，因为写属性失败在这条通道上同样不抛异常。
        """
        view = self._view()
        if view is None:
            return False
        if hwnd:
            focus_slideshow_window(int(hwnd))
        pointer_type = int(pointer_type)
        if pointer_type != PP_POINTER_ARROW:
            try:  # 先清模式（L1: force_arrow_reset）
                view.PointerType = PP_POINTER_ARROW
            except Exception:
                pass
        try:
            view.PointerType = pointer_type
        except Exception:
            log.debug("切换指针失败", exc_info=True)
            return False
        try:
            current = getattr(view, "PointerType", None)
            if callable(current):
                current = current()
            if current is not None and int(current) != pointer_type:
                log.debug("指针切换后读回不符：期望 %s，实际 %s", pointer_type, current)
                return False
        except Exception:
            pass  # 读不回来就当它成功了（有些对象模型不暴露可读的 PointerType）
        return True

    def read_pointer_color(self) -> Optional[tuple[int, int, int]]:
        """当前墨迹颜色的 ``(r, g, b)``；读不到返回 ``None``。

        注意 COM 的 ``Color.RGB`` 是 **BGR** 打包（``r | g<<8 | b<<16``）。
        """
        view = self._view()
        if view is None:
            return None
        try:
            color = getattr(view, "PointerColor", None)
            if color is None:
                return None
            rgb = getattr(color, "RGB", None)
            if callable(rgb):
                rgb = rgb()
            if rgb is None:
                return None
            value = int(rgb) & 0xFFFFFF
            return (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF)
        except Exception:
            return None

    def set_pointer_color(self, r: int, g: int, b: int) -> bool:
        """直接写 ``View.PointerColor.RGB``（L1 ``_try_apply_pointer_color``）。

        写完**读回校验**：这条通道的失败同样不抛异常，只看返回码会把
        「压根没写进去」当成成功。
        """
        view = self._view()
        if view is None:
            return False
        r, g, b = int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF
        try:
            view.PointerColor.RGB = r + (g << 8) + (b << 16)
        except Exception:
            log.debug("写入墨迹颜色失败", exc_info=True)
            return False
        return self.read_pointer_color() == (r, g, b)

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

    def execute_mso_command(self, command_id: str) -> bool:
        """执行 Office 的 MSO 命令（``Application.CommandBars.ExecuteMso``）。

        只有 PowerPoint 认这套（L1 ``_execute_mso_command``）；换墨迹颜色时
        要先 ``AnnotInkPen`` 让调色板命令变为可用，再 ``InkColorPicker`` 打开调色板。
        """
        app = self._attached()
        if app is None:
            return False
        try:
            commandbars = getattr(app, "CommandBars", None)
            execute = getattr(commandbars, "ExecuteMso", None)
            if not callable(execute):
                return False
            execute(str(command_id))
            return True
        except Exception:
            log.debug("执行 MSO 命令 %s 失败", command_id, exc_info=True)
            return False

    def read_ink_annotations(self):
        """当前页的墨迹批注集合（退出时问「留不留」用）；取不到返回 ``None``。"""
        view = self._view()
        if view is None:
            return None
        try:
            return getattr(view, "InkAnnotations", None)
        except Exception:
            return None

    def set_display_alerts(self, value: int) -> Optional[int]:
        """临时改 ``Application.DisplayAlerts``（1=ppAlertsNone，压掉 PowerPoint
        自带的墨迹提示框）；返回原值以便还原，失败返回 ``None``。"""
        app = self._attached()
        if app is None:
            return None
        try:
            original = int(app.DisplayAlerts)
        except Exception:
            original = None
        try:
            app.DisplayAlerts = int(value)
        except Exception:
            return None
        return original


# --------------------------------------------------------------------------- 控制器


# 单次进度超过这个时长就告警（只告一次，避免刷屏）
SLOW_CYCLE_MS = 1500
# 看护定时器间隔 / 心跳静默多久算「卡住」/ 同一阶段最多多久报一次
WATCHDOG_INTERVAL_MS = 1000
WATCHDOG_STALE_S = 3.0
WATCHDOG_REPEAT_S = 15.0
# 翻页限流：1 秒窗口内最多放行 N 次（对齐 Luminalium 1 ``PPT.PageTurnRateLimit``）
PAGE_TURN_WINDOW_S = 1.0
PAGE_TURN_LIMIT_DEFAULT = 2


class _Heartbeat:
    """后台线程的「最后一次进度」，用来回答「它到底卡在哪」。

    只有拥有者线程写（``enter`` / ``finish``），别的线程只读；全是单个属性的
    读写，在 GIL 下不会读到半截值。

    为什么需要它：探测链路一旦卡住，现象是「日志里什么都没有、控制条不出现」，
    用户报障时完全无从下手（本项目就吃过这个亏）。有了心跳，日志能直接写成
    「窗口探测线程：阶段『枚举顶层窗口』已 42.0s，静默 42.0s」——一眼定位。
    """

    __slots__ = ("name", "phase", "phase_since", "last_beat", "cycles",
                 "last_ms", "max_ms", "warned_at")

    def __init__(self, name: str) -> None:
        now = time.monotonic()
        self.name = name
        self.phase = "未启动"
        self.phase_since = now
        self.last_beat = now
        self.cycles = 0
        self.last_ms = 0.0
        self.max_ms = 0.0
        self.warned_at = 0.0

    def enter(self, phase: str) -> None:
        now = time.monotonic()
        self.phase = phase
        self.phase_since = now
        self.last_beat = now

    def finish(self, elapsed_ms: float, phase: str = "待命") -> None:
        now = time.monotonic()
        self.last_beat = now
        self.phase = phase
        self.phase_since = now
        self.cycles += 1
        self.last_ms = float(elapsed_ms)
        if elapsed_ms > self.max_ms:
            self.max_ms = float(elapsed_ms)

    def idle_seconds(self) -> float:
        """距最后一次进度过了多久。"""
        return time.monotonic() - self.last_beat

    def phase_seconds(self) -> float:
        return time.monotonic() - self.phase_since

    def describe(self) -> str:
        return (
            f"{self.name}: 周期 {self.cycles} 次，最后 {self.last_ms:.0f}ms / "
            f"最长 {self.max_ms:.0f}ms，阶段「{self.phase}」已 {self.phase_seconds():.1f}s，"
            f"静默 {self.idle_seconds():.1f}s"
        )


# --------------------------------------------------------------------------- 完整性级别

# UAC 完整性级别 —— 「COM 连不上」的第一大原因：运行对象表（ROT）按完整性级别隔离，
# Medium 的进程看不见 High 的注册项（反之亦然）。连不上时翻页 / 页码 / 退出放映
# 就只剩键盘回退，而 UIPI 连注入按键也一起挡掉。真机实测过：探针进程 High +
# PowerPoint Medium 时 GetActiveObject 直接 0x800401E3（操作无法使用）。
_TOKEN_QUERY = 0x0008
_TOKEN_INTEGRITY_LEVEL = 25
_INTEGRITY_NAMES = {
    0x0000: "Untrusted", 0x1000: "Low", 0x2000: "Medium",
    0x2100: "MediumPlus", 0x3000: "High(管理员)", 0x4000: "System",
}


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TokenMandatoryLabel(ctypes.Structure):
    _fields_ = [("Label", _SidAndAttributes)]


def _integrity_rid(pid: int) -> int:
    """进程完整性级别的 RID（``0x2000`` = Medium、``0x3000`` = High…）；拿不到返回 0。

    纯 Win32 查询、不依赖 pywin32，任何一步失败都安静返回 0。返回 RID 而不是
    名字，是为了能**比大小** —— UIPI 只允许向同级或更低级别注入输入。
    """
    if not pid or not hasattr(ctypes, "windll"):
        return 0
    try:
        advapi32 = ctypes.windll.advapi32
        # ctypes 默认按 32 位截断返回值，SID 相关 API 必须显式声明，否则指针被截断
        advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
        advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
        advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        ]
        advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return 0
        try:
            token = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(handle, _TOKEN_QUERY, ctypes.byref(token)):
                return 0
            try:
                size = wintypes.DWORD(0)
                advapi32.GetTokenInformation(
                    token, _TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(size)
                )
                if not size.value:
                    return 0
                buffer = ctypes.create_string_buffer(size.value)
                if not advapi32.GetTokenInformation(
                    token, _TOKEN_INTEGRITY_LEVEL, buffer, size.value, ctypes.byref(size)
                ):
                    return 0
                label = ctypes.cast(
                    buffer, ctypes.POINTER(_TokenMandatoryLabel)
                ).contents
                if not label.Label.Sid:
                    return 0
                sid = ctypes.c_void_p(label.Label.Sid)
                count = advapi32.GetSidSubAuthorityCount(sid).contents.value
                # 强制标签 SID 形如 S-1-16-<RID> —— **只有 1 个子授权**，
                # RID 就在下标 0。这里曾写成 `count < 2` 直接放弃，结果整个函数
                # 永远返回 0：diagnose() 的「权限级别（UAC）」一行从来没打印过，
                # 而按键选路也一直落在「查不到 ⇒ 按 Medium」的兜底分支上。
                if count < 1:
                    return 0
                return int(advapi32.GetSidSubAuthority(sid, count - 1).contents.value)
            finally:
                kernel32.CloseHandle(token)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # pragma: no cover - 诊断辅助，拿不到就算了
        return 0


def _process_integrity(pid: int) -> str:
    """完整性级别的可读名字（诊断用）；拿不到返回空串。"""
    rid = _integrity_rid(pid)
    return _INTEGRITY_NAMES.get(rid, "0x%04X" % rid) if rid else ""


# 「查不到」一律按 Medium 处理：宁可走 keybd_event 这条常规路径，也不要因为
# 拿不到级别就把对方误判成「更低」而改用 PostMessage。
MEDIUM_INTEGRITY_RID = 0x2000
_self_rid = -1


def _self_integrity_rank() -> int:
    """本进程的完整性级别 RID（缓存一次，避免每次按键都查一遍令牌）。"""
    global _self_rid
    if _self_rid < 0:
        current = int(ctypes.windll.kernel32.GetCurrentProcessId())
        _self_rid = _integrity_rid(current) or MEDIUM_INTEGRITY_RID
    return _self_rid


def _integrity_rank(pid: int) -> int:
    """目标进程的完整性级别 RID；查不到按 Medium（保守，见上）。"""
    return _integrity_rid(pid) or MEDIUM_INTEGRITY_RID


# --------------------------------------------------------------------------- 线程


@dataclass(frozen=True)
class _ComSnapshot:
    """COM 线程最后一次读到的放映快照。

    不可变对象 + 整体替换 ⇒ 读取端拿到的永远是一份**自洽**的数据快照，
    不用加锁、更不会因为「锁被一个卡住的 COM 调用握着」而把窗口线程一起拖死
    （这点很关键：跨线程传状态时，**绝不能让锁跨越可能阻塞的调用**）。
    """

    presenting: bool = False
    slide_index: int = 0
    slide_total: int = 0
    window_handle: int = 0
    status: str = "尚未探测"
    kind: str = ""        # COM 连上的是哪一族（ppt / wps / yozo），窗口认不出族时用它补
    pen_color: Optional[tuple] = None  # 墨迹颜色 (r, g, b)，顺带读的
    at: float = 0.0       # 采集时刻（time.monotonic）
    ok_at: float = 0.0    # 最后一次「确认在放映」的时刻

    def age(self) -> float:
        """距上次刷新过了多少秒；从未刷新过返回 ``-1``。"""
        return time.monotonic() - self.at if self.at else -1.0


class _ComThread(QThread):
    """**只做 COM** 的线程。

    为什么必须和窗口探测分开：PowerPoint 是单套间（STA），**它自己的主线程不抽消息时
    任何跨进程调用都会一直排队**（放映中、弹模态框、保存 / 另存为时都会）。之前
    COM 与窗口枚举挤在同一条线程里，那次 ``GetActiveObject`` /
    ``SlideShowWindows.Count`` 一卡住，**整条探测链路跟着死**：日志静默、
    控制条永远不出现 —— 正是用户报的「明明在放映却毫无反应」。

    拆开之后：窗口探测（纯 Win32、毫秒级）永远不受影响，控制条照常出现；
    COM 卡住只退化成「页码 0/0 + 翻页走键盘回退」，而且看护逻辑会把它明确写进日志。
    """

    def __init__(self, interval_ms: int = 800, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._interval_ms = max(300, int(interval_ms))
        self._running = True
        self._com = _ComBackend()
        self._commands: "queue.Queue[Tuple[str, tuple]]" = queue.Queue()
        self._wake = threading.Event()
        self._snapshot = _ComSnapshot()
        self._ticks = 0
        self.heartbeat = _Heartbeat("COM 线程")

    # ---------------------------------------------------- 主线程侧（非阻塞）

    def request(self, name: str, *args) -> None:
        """投递一个控制命令，交给 COM 线程执行，立即返回。"""
        self._commands.put((name, args))
        self._wake.set()

    @property
    def snapshot(self) -> _ComSnapshot:
        return self._snapshot

    def poke(self) -> None:
        self._wake.set()

    def set_probe_interval(self, interval_ms: int) -> None:
        self._interval_ms = max(300, int(interval_ms))
        self._wake.set()

    def stop_async(self) -> None:
        self._running = False
        self._wake.set()

    def stop(self) -> None:  # pragma: no cover - 兼容调用习惯
        self.stop_async()
        self.wait(3000)

    # ------------------------------------------------------------ COM 线程

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
                    self.heartbeat.enter("读放映快照")
                    self._refresh_snapshot()
                except Exception:  # COM 异常不能中断轮询
                    log.exception("放映状态 COM 探测失败")
                    self.heartbeat.finish(0.0, "上一轮出错")
                # 可被 poke() 提前唤醒，不必死等一个整周期
                self._wake.wait(self._interval_ms / 1000.0)
                self._wake.clear()
        finally:
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:  # pragma: no cover
                    pass

    def _refresh_snapshot(self, light: bool = False) -> None:
        """读一次页码 / 放映窗口并整体替换快照（只在 COM 线程调用）。

        ``light=True`` 时**只读页码**，跳过 ``describe()`` / ``read_pointer_color()``
        这两次纯诊断性的跨进程属性读取。翻页命令执行完会立刻用 ``light`` 刷一次
        —— 页码要第一时间跟上手势，而诊断字段晚一拍无所谓（这正是「页码识别
        迟钝」的病灶：一次命令后的刷新被两个诊断调用拖长了）。
        """
        started = time.perf_counter()
        previous = self._snapshot
        if light and previous.presenting:
            # 轻量路径：只读当前页（一次跨进程整数读），总页数沿用上一份。
            # 总页数在场内是常量，没必要每次翻页都重读对象模型。
            try:
                position = self._com.read_position()
            except Exception:
                log.debug("轻量读取当前页失败", exc_info=True)
                position = None
            if position is not None:
                slide_index, hwnd = position
                slide_total = previous.slide_total
                presenting = True
            else:
                slide_index = previous.slide_index
                slide_total = previous.slide_total
                hwnd = previous.window_handle
                presenting = False
        else:
            try:
                numbers = self._com.read_state()
            except Exception:
                log.debug("读取放映页码失败", exc_info=True)
                numbers = None
            if numbers is not None:
                presenting = True
                slide_index, slide_total, hwnd = numbers
            else:
                try:
                    presenting = self._com.is_presenting()
                except Exception:
                    presenting = False
                slide_index = slide_total = hwnd = 0

        self._ticks += 1
        if light:
            # 轻量刷新：沿用上一次诊断字段，只把页码换新
            status = previous.status or "COM 已连接"
            pen_color = previous.pen_color if presenting else None
        else:
            # 状态文本只服务诊断，却要额外两次跨进程属性读取（也是最容易排队的
            # 调用），所以每 5 个周期刷新一次即可 —— 卡住时诊断会同时给出
            # 「静默 N 秒」。
            if self._ticks % 5 == 1 or presenting != previous.presenting or not previous.status:
                try:
                    status = self._com.describe()
                except Exception:  # pragma: no cover - 只服务诊断
                    status = "COM 状态读取失败"
            else:
                status = previous.status

            # 墨迹颜色同理：只服务设置页的色板回显，没必要每个周期都跨进程读一次
            if presenting and self._ticks % 5 == 2:
                try:
                    pen_color = self._com.read_pointer_color()
                except Exception:
                    pen_color = previous.pen_color
            else:
                pen_color = previous.pen_color if presenting else None

        now = time.monotonic()
        self._snapshot = _ComSnapshot(
            presenting=bool(presenting),
            slide_index=int(slide_index or 0),
            slide_total=int(slide_total or 0),
            window_handle=int(hwnd or 0),
            status=status,
            kind=self._com.kind,
            pen_color=pen_color,
            at=now,
            ok_at=now if presenting else previous.ok_at,
        )
        self.heartbeat.finish((time.perf_counter() - started) * 1000)

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
        self.heartbeat.enter("执行命令「%s」" % name)
        try:
            handler(*args)
        except Exception:
            log.exception("执行「%s」失败", name)
        finally:
            # 命令执行完立刻刷一次，页码不必再等一个周期。
            # 用轻量刷新：命令（尤其是翻页）后页码要马上跟上手势，但诊断字段
            # 可以晚一拍 —— 两次跨进程诊断读会把「点击 → 页码更新」拉长成几百毫秒。
            try:
                self._refresh_snapshot(light=True)
            except Exception:  # pragma: no cover
                pass

    # 命令实现（只在 COM 线程被调用）

    def _cmd_next(self, hwnd: int) -> None:
        if not self._com.next_slide():
            # 先 PageDown；连注入都失败再退方向键（部分放映软件只认 ↓，L1 同款）
            if not send_slideshow_key(VK_NEXT, hwnd):
                send_slideshow_key(VK_DOWN, hwnd)

    def _cmd_previous(self, hwnd: int) -> None:
        if not self._com.previous_slide():
            if not send_slideshow_key(VK_PRIOR, hwnd):
                send_slideshow_key(VK_UP, hwnd)

    def _cmd_goto(self, hwnd: int, index: int) -> None:
        if not self._com.goto_slide(index):
            log.info("跳转页码失败，目标 %s", index)

    def _cmd_exit(self, hwnd: int, keep_ink: bool = False, kind: str = "") -> None:
        """退出放映。``keep_ink`` 为真时先把墨迹「留下」再退（L1 的保留墨迹语义）。

        L1 退出前会弹「墨迹留不留」并据此调 ``InkAnnotations.Save`` /
        ``EraseDrawing``；这个 UI 目前不做，但**留墨迹那条路要留着**：
        默认退出会把 PowerPoint 自带的「保留墨迹」提示框压掉（``DisplayAlerts``），
        否则退出放映时用户会莫名多挨一个模态框。
        """
        if keep_ink:
            self._apply_ink_keep()
        if not self._com.exit_slideshow():
            send_slideshow_key(VK_ESCAPE, hwnd)

    def _cmd_pen_color(self, r: int, g: int, b: int, kind: str = "") -> None:
        if kind and kind != APP_KIND_PPT:
            log.info("墨迹颜色只支持 PowerPoint（当前 %s），忽略", kind)
            return
        if not self._com.set_pointer_color(r, g, b):
            log.info("设置墨迹颜色 #%02X%02X%02X 失败（该 Office 状态可能不暴露颜色入口）",
                     r, g, b)

    def _apply_ink_keep(self) -> None:
        """把当前页墨迹保存下来（L1 ``_apply_ink_keep``：``InkAnnotations.Save``）。"""
        annotations = self._com.read_ink_annotations()
        if annotations is None:
            return
        try:
            save = getattr(annotations, "Save", None)
            if callable(save):
                save()
        except Exception:
            log.debug("保存墨迹失败", exc_info=True)

    def _cmd_clear(self, hwnd: int, kind: str = "") -> None:
        """清屏。

        ⚠️ PowerPoint 的 ``View.EraseDrawing()`` 是「**隐藏**墨迹」不是「删除」
        —— Microsoft Q&A 实锤的已知 bug（隐藏态会被**下一笔 undo 回来**，
        症状正是用户报的「清屏后再写新东西，旧残余显形」；VBA 社区的
        ``GotoSlide`` 重进页之类的绕法都有闪烁）。而键盘 ``E`` 走的是放映
        原生「擦除所有墨迹」动作，**真删** —— 用户实测 E 没有这个问题。

        所以 PowerPoint 族在 COM 擦除成功后**补发一次 E**：E 送达则墨迹真删
        （隐藏态随之无关紧要）；E 没送达也不比原来差 —— 双发无害（对空墨迹
        按 E 是 no-op）。COM 擦除失败则维持原来的纯按键回退。其他族没有
        这个 bug 的实锤（WPS 的 COM 是自家实现），维持原样不发按键。
        """
        if not self._com.erase_drawings():
            send_slideshow_key(VK_ERASE, hwnd)
            return
        if kind == APP_KIND_PPT:
            send_slideshow_key(VK_ERASE, hwnd)

    def _cmd_tool(self, hwnd: int, tool: str, kind: str = "") -> None:
        """切换笔 / 橡皮 / 指针 —— 腿的**顺序照 Luminalium 1 ``set_pointer_type``**。

        L1 的实测经验：光写一次 ``view.PointerType`` 经常「看起来成功了但没换」。
        它用的是**递进式重试**：先直写 COM（第 0 次带一次箭头复位），不行再写一次、
        再不行补一次，仍不行才发快捷键。这里照抄这个阶梯，只是把「发快捷键」那步
        按**软件族**分开：PowerPoint / WPS 用 Ctrl+P / Ctrl+E / Ctrl+A，
        永中只发它认得的两个 —— 给 WPS 下 PowerPoint 专属的 MSO 命令是无效动作，
        只会白等一轮。

        ⚠️ 在 COM 线程里 ``time.sleep`` 会阻塞快照刷新（页码就靠它），所以阶梯的
        总睡眠压到 L1 同量级后就**不再多等**；真正让它生效的是 ``set_pointer``
        里的「先拉前台」。
        """
        pointer = TOOL_TO_POINTER.get(tool)
        if pointer is None:
            log.warning("未知工具: %s", tool)
            return

        # 第一件事就是拉前台：后面无论是写 PointerType 还是发 Ctrl 快捷键都要求
        # 放映窗口在前台，这一步失败则整条链路都不会生效（L1 同款前置动作）。
        if hwnd:
            focus_slideshow_window(int(hwnd))

        for attempt, delay in enumerate(L1_POINTER_RETRY_DELAYS):
            if delay > 0:
                time.sleep(delay)
            if self._com.set_pointer(pointer, hwnd):
                return

        shortcut = KIND_TOOL_SHORTCUTS.get(kind or APP_KIND_PPT, {}).get(tool)
        if shortcut is None:
            log.info("切换 %s 失败：COM 拒绝且 %s 族没有可靠的快捷键通道",
                     tool, kind or "?")
            return
        # 橡皮在有些版本里嵌在笔模式内，先回指针再切（L1 对 pointer_type==2 的处理）
        if tool == "pen" and "arrow" in KIND_TOOL_SHORTCUTS.get(kind or APP_KIND_PPT, {}):
            send_slideshow_ctrl_key(
                KIND_TOOL_SHORTCUTS[kind or APP_KIND_PPT]["arrow"], hwnd
            )
            time.sleep(L1_SHORTCUT_GAP_S)
        if not send_slideshow_ctrl_key(shortcut, hwnd):
            log.info("切换 %s 失败：COM 与快捷键通道都没送出去", tool)
            return
        time.sleep(L1_SHORTCUT_SETTLE_S)
        if self._com.set_pointer(pointer, hwnd):
            return
        log.info("切换 %s：快捷键已发出但读回不符（演示软件可能没响应）", tool)


class _ProbeThread(QThread):
    """窗口探测线程：**一次 COM 都不碰**。

    只用 ``EnumWindows`` 那一套（纯 Win32，毫秒级）。页码从 COM 线程的快照里取
    （滞后最多一个 COM 周期），于是「PowerPoint 正忙着放映、COM 调用在排队」
    再也不会把状态上报挡在门外 —— 控制条该出现就一定出现。

    这条线程唯一还能卡住的理由是「日志写入阻塞」（stdout 是一条没人读的管道时，
    写满 64KB 就会把调用它的线程按在那里），看护定时器会把它记进日志。
    """

    # 用基本类型而不是 object：跨线程排队连接不需要 Python 对象做元类型转换
    stateReady = Signal(bool, int, int, int, str, str, str)

    def __init__(
        self,
        interval_ms: int = 400,
        com: Optional[_ComThread] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._interval_ms = max(100, int(interval_ms))
        self._com = com
        self._running = True
        self._wake = threading.Event()
        self._last = PresentationState()
        # 近失窗口（疑似放映却被拒）的日志节流：同一签名 30 秒最多一条
        self._near_miss_sig = ""
        self._near_miss_at = 0.0
        self.heartbeat = _Heartbeat("窗口探测线程")

    # ---------------------------------------------------- 主线程侧（非阻塞）

    def poke(self) -> None:
        """唤醒一次探测（不等下一个周期）。"""
        self._wake.set()

    def set_probe_interval(self, interval_ms: int) -> None:
        self._interval_ms = max(100, int(interval_ms))
        self._wake.set()

    def stop_async(self) -> None:
        self._running = False
        self._wake.set()

    def stop(self) -> None:  # pragma: no cover - 兼容调用习惯
        self.stop_async()
        self.wait(3000)

    # ------------------------------------------------------------ 工作线程

    def run(self) -> None:
        state = PresentationState()
        try:
            while self._running:
                self.heartbeat.enter("枚举顶层窗口")
                started = time.perf_counter()
                try:
                    state = self._probe_once()
                except Exception:  # 探测异常不能中断轮询
                    log.exception("放映状态窗口探测失败")
                    state = PresentationState()
                    self.heartbeat.finish(
                        (time.perf_counter() - started) * 1000, "上一轮出错"
                    )
                else:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    self.heartbeat.finish(elapsed_ms)
                    if elapsed_ms > SLOW_CYCLE_MS:
                        log.warning(
                            "一次窗口探测耗时 %.0fms（纯 Win32 枚举不该这么慢）", elapsed_ms
                        )
                if state.marker != self._last.marker:
                    self._log_change(state)
                    self._last = state
                    self.stateReady.emit(
                        state.active, state.slide_index, state.slide_total,
                        state.window_handle, state.title, state.source, state.kind,
                    )
                if not state.active:
                    self._report_near_miss()
                # 可被 poke() 提前唤醒，不必死等一个整周期
                self._wake.wait(self._interval_ms / 1000.0)
                self._wake.clear()
        finally:
            self.heartbeat.enter("已退出")

    # ------------------------------------------------------------ 探测本身

    def _probe_once(self) -> PresentationState:
        """单次探测：**窗口通道说了算，COM 只补页码**。只在窗口线程调用。"""
        hwnd, title, kind = find_slideshow_window()
        snapshot = self._com.snapshot if self._com is not None else _ComSnapshot()
        if hwnd:
            slide_index = slide_total = 0
            # 快照里还留着上一场放映的页码时不要串页
            if not snapshot.window_handle or snapshot.window_handle == hwnd:
                slide_index, slide_total = snapshot.slide_index, snapshot.slide_total
            # 窗口认不出族时，用 COM 连上的 ProgID 补一个（WPS 系最常走这条：
            # 它的放映窗口类名随版本变，但 COM 一 attach 就知道是 Kwpp 还是 PowerPoint）
            resolved_kind = kind or snapshot.kind
            return PresentationState(
                active=True,
                slide_index=slide_index,
                slide_total=slide_total,
                window_handle=hwnd,
                title=title,
                source="window",
                kind=resolved_kind,
            )
        # 窗口类没探到：COM 报告有放映窗口也算放映中
        if snapshot.presenting:
            return PresentationState(
                active=True,
                slide_index=snapshot.slide_index,
                slide_total=snapshot.slide_total,
                window_handle=max(int(snapshot.window_handle), 0),
                title="",
                source="com",
                kind=snapshot.kind,
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

    def _report_near_miss(self) -> None:
        """未检测到放映时，看一眼**前台窗口**有没有「疑似放映却被拒」的。

        用户报障最常见的形态是「明明在放映却毫无反应」——这条日志把拒绝
        原因直接写进日志，不用再让用户跑诊断脚本。只看前台窗口，代价可忽略；
        同一签名 30 秒最多一条，不刷屏。
        """
        if not hasattr(ctypes, "windll"):
            return
        try:
            fg = int(ctypes.windll.user32.GetForegroundWindow() or 0)
            if not fg:
                return
            facts = _window_facts(fg)
        except OSError:  # 窗口在查询过程中销毁是常态
            return
        reason = _near_miss_reason(facts)
        if reason is None:
            return
        hwnd, class_name, title, pid, _visible, _rect = facts
        sig = f"{hwnd}:{reason}"
        now = time.monotonic()
        if sig == self._near_miss_sig and now - self._near_miss_at < 30.0:
            return
        self._near_miss_sig = sig
        self._near_miss_at = now
        log.info(
            "疑似放映窗口未判定为放映: hwnd=0x%08X class=%r title=%r proc=%s 原因=%s"
            "（若这确实是放映窗口，把 class/proc 填进 "
            "presentation.window_classes / presentation.process_names）",
            hwnd, class_name, title, _process_name(pid) or "?", reason,
        )


class PptController(QObject):
    """放映状态轮询 + 放映控制的**独立**入口。

    内部是两条后台线程 + 一个看护定时器：

    * :class:`_ProbeThread` —— 纯 Win32 窗口枚举，**探测的唯一权威**；
    * :class:`_ComThread` —— 全部 COM 读写与放映控制命令（可能被 PowerPoint 拖住）；
    * 主线程看护定时器 —— 两条线程静默超时就往日志写「卡在哪」，主线程永远不会被拖住。

    于是「放映中检测没反应」这类故障不可能再是静默的：要么探测正常工作，
    要么日志里明明白白写着哪条线程卡在哪个阶段、卡了多久。

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
        self._com = _ComThread(max(450, int(interval_ms * 1.5)), self)
        self._thread = _ProbeThread(interval_ms, self._com, self)
        self._thread.stateReady.connect(self._on_state_ready)
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(WATCHDOG_INTERVAL_MS)
        self._watchdog.timeout.connect(self._on_watchdog)
        self._page_turns: deque = deque()
        self._page_turn_limit = PAGE_TURN_LIMIT_DEFAULT
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
            self.set_page_turn_limit(
                int(config.get("presentation.page_turn_rate_limit",
                               PAGE_TURN_LIMIT_DEFAULT))
            )
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
        for thread in (self._com, self._thread):
            if not thread.isRunning():
                thread.start()
        if not self._watchdog.isActive():
            self._watchdog.start()

    def stop(self) -> None:
        self._thread.stop_async()
        self._com.stop_async()
        self._watchdog.stop()

    def set_interval(self, interval_ms: int) -> None:
        """探测间隔（窗口探测 / COM 各自一档）。

        窗口探测用原值；COM 只负责补页码，跟随手势要够快 —— 但仍比窗口探测慢
        一档，因为跨进程 COM 调用本身就贵，跟着 100ms 跑只会把 PowerPoint 拖住
        （它一忙我们就集体排队）。经验值：窗口的 1.5 倍、下限 300ms。
        """
        interval_ms = int(interval_ms)
        self._thread.set_probe_interval(interval_ms)
        self._com.set_probe_interval(max(300, int(interval_ms * 1.5)))

    def set_page_turn_limit(self, limit: int) -> None:
        """每秒最多放行多少次翻页（``presentation.page_turn_rate_limit``）。"""
        self._page_turn_limit = max(1, int(limit))

    def _consume_page_turn(self) -> bool:
        """翻页令牌：1 秒窗口内放行 ``limit`` 次，超出的**直接丢弃**。

        为什么必须有这道闸：放映中连点会把 COM 调用与键盘消息一股脑推给演示软件，
        它忙不过来时要么拒绝调用（``RPC_E_CALL_REJECTED``）、要么把输入排队，
        用户看到的就是「点了没反应，然后突然连跳好几页」。Luminalium 1 同样有
        这道闸（``_consume_page_turn_token``，默认 2 次/秒）。
        """
        now = time.monotonic()
        turns = self._page_turns
        while turns and now - turns[0] > PAGE_TURN_WINDOW_S:
            turns.popleft()
        if len(turns) >= self._page_turn_limit:
            log.debug("翻页过快（上限 %d 次/秒），本次丢弃", self._page_turn_limit)
            return False
        turns.append(now)
        return True

    def refresh_now(self) -> None:
        self._thread.poke()
        self._com.poke()

    def shutdown(self) -> None:
        self._thread.stop_async()
        self._com.stop_async()
        self._watchdog.stop()
        for thread in (self._thread, self._com):
            if thread.isRunning():
                thread.wait(3000)

    # ------------------------------------------------------------------ 看护

    def _on_watchdog(self) -> None:
        """两条后台线程的看护：静默太久就把「卡在哪」写进日志。

        跑在**主线程**（QTimer），所以即使两条工作线程全卡死，这条告警照样能出来
        ——「日志里什么都没有」这种最难查的情况就此绝迹。
        """
        now = time.monotonic()
        for heartbeat in (self._thread.heartbeat, self._com.heartbeat):
            if heartbeat.idle_seconds() < WATCHDOG_STALE_S:
                heartbeat.warned_at = 0.0  # 恢复正常，下次卡住可以再报
                continue
            if heartbeat.warned_at and now - heartbeat.warned_at < WATCHDOG_REPEAT_S:
                continue
            heartbeat.warned_at = now
            if heartbeat is self._com.heartbeat:
                hint = ("COM 卡住不影响窗口探测，控制条该出现还是出现；"
                        "受影响的是页码与 COM 翻页（会退化成键盘回退）")
            else:
                hint = ("窗口探测只做 Win32 枚举，慢成这样通常是日志输出被阻塞"
                        "（stdout 管道写满 / 调试控制台没人读）或系统整体卡顿")
            log.warning("放映链路卡住: %s —— %s", heartbeat.describe(), hint)

    # ------------------------------------------------------------------ 信号

    def _on_state_ready(
        self, active: bool, slide_index: int, slide_total: int,
        window_handle: int, title: str, source: str, kind: str = "",
    ) -> None:
        """探测线程 -> 主线程。这里只组装对象再转发，不做任何阻塞操作。"""
        state = PresentationState(
            active=bool(active),
            slide_index=int(slide_index),
            slide_total=int(slide_total),
            window_handle=int(window_handle),
            title=str(title),
            source=str(source),
            kind=str(kind),
        )
        self._state = state
        self.stateChanged.emit(state)

    # ------------------------------------------------------------------ 自检

    def inject_state(self, state: PresentationState) -> None:
        """自检用：跳过探测线程直接注入一个状态（例如伪造「正在放映」）。"""
        self._thread._last = state
        self._on_state_ready(
            state.active, state.slide_index, state.slide_total,
            state.window_handle, state.title, state.source, state.kind,
        )

    def diagnose(self) -> str:
        """返回一段人读的诊断信息（写进日志，用于真机排查）。

        这份诊断必须**能自证**：先给两条线程的心跳（卡住时会直接写「卡在哪个阶段、
        卡了多久」），再给窗口候选清单、前台窗口、权限级别对照，最后给结论。
        放映时跑一次就能定位到具体环节，不必再靠猜。
        """
        lines = ["PPT 控制器诊断:"]
        for heartbeat in (self._thread.heartbeat, self._com.heartbeat):
            lines.append(f"  {heartbeat.describe()}")

        com_idle = self._com.heartbeat.idle_seconds()
        if com_idle >= WATCHDOG_STALE_S:
            lines.append(
                f"  ⚠ COM 线程已静默 {com_idle:.1f}s 没有结果 —— 大概率卡在 PowerPoint 的"
                "跨进程调用里（放映中 / 弹模态框 / 保存时它不抽消息）。窗口探测与 COM "
                "是两条独立线程，控制条不受影响；受影响的是页码与 COM 翻页 / 笔 / 退出"
            )
        probe_idle = self._thread.heartbeat.idle_seconds()
        if probe_idle >= WATCHDOG_STALE_S:
            lines.append(
                f"  ⚠ 窗口探测线程已静默 {probe_idle:.1f}s —— 它只做 Win32 枚举（应为毫秒级），"
                "请检查日志输出是否被阻塞（stdout 管道写满 / 调试控制台没人读）"
            )

        lines.append(
            f"  当前状态: active={self._state.active} source={self._state.source!r} "
            f"kind={self._state.kind or '?'} "
            f"hwnd=0x{self._state.window_handle:08X} "
            f"页码={self._state.slide_index}/{self._state.slide_total}"
        )
        snapshot = self._com.snapshot
        age = snapshot.age()
        lines.append(
            f"  COM 快照: {snapshot.status}"
            + ("（还没刷新过）" if age < 0 else f"（距上次刷新 {age:.1f}s）")
        )

        hwnd, title, kind = find_slideshow_window()
        lines.append(f"  窗口探测: hwnd=0x{hwnd:08X} title={title!r} kind={kind or '?'} "
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
        demo_pids: dict[int, str] = {}
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
            if known_process:
                demo_pids.setdefault(pid, process)
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

        # 前台窗口：看「用户眼前是什么」，很多误判一眼就能看出来
        try:
            fg = int(user32.GetForegroundWindow() or 0)
            if fg:
                fg_hwnd, fg_class, fg_title, _fg_pid, fg_visible, _fg_rect = _window_facts(fg)
                lines.append(
                    f"  前台窗口: hwnd=0x{fg_hwnd:08X} class={fg_class!r} "
                    f"title={fg_title[:36]!r} visible={fg_visible} "
                    f"判定={'放映中' if _looks_like_slideshow((fg_hwnd, fg_class, fg_title, _fg_pid, fg_visible, _fg_rect)) else '否'}"
                )
        except OSError:  # pragma: no cover
            pass

        # 权限级别对照 —— 「COM 连不上」的头号原因，实测一遍比讲道理有用
        own_level = _process_integrity(ctypes.windll.kernel32.GetCurrentProcessId())
        if own_level:
            parts = [f"本程序={own_level}"]
            mismatch = False
            for pid, process in sorted(demo_pids.items(), key=lambda item: item[1]):
                level = _process_integrity(pid) or "未知"
                if level not in ("未知", own_level):
                    mismatch = True
                parts.append(f"{process}={level}")
            lines.append("  权限级别（UAC）: " + "，".join(parts))
            if mismatch:
                lines.append(
                    "  ⚠ 权限级别不一致 —— UAC 按完整性级别隔离 COM（运行对象表），"
                    "级别不同就互相看不见，注入按键也会被 UIPI 挡掉。"
                    "请把 Luminalium 与演示软件设成**相同**的权限级别（通常都是普通启动）"
                )

        if not self._state.active:
            lines.append(
                "  结论: 三条通道都没判定为放映（窗口类 / 进程兜底 / COM）。"
                "若此时确实在放映，把上面候选里的 class / proc 填进 "
                "presentation.window_classes / presentation.process_names"
            )
        else:
            lines.append("  结论: 判定为正在放映，顶层窗口应当已按屏幕铺满并显示控制条")
        return "\n".join(lines)

    # ------------------------------------------------------------------ 控制

    def next_slide(self, hwnd: int = 0) -> bool:
        """下一页。返回 ``False`` 表示这次**被限流丢弃**（不是失败）。"""
        if not self._consume_page_turn():
            return False
        self._com.request("next", int(hwnd or 0))
        return True

    def previous_slide(self, hwnd: int = 0) -> bool:
        """上一页。返回 ``False`` 表示这次**被限流丢弃**（不是失败）。"""
        if not self._consume_page_turn():
            return False
        self._com.request("previous", int(hwnd or 0))
        return True

    def goto_slide(self, index: int, hwnd: int = 0) -> bool:
        self._com.request("goto", int(hwnd or 0), int(index))
        return True

    def exit_slideshow(self, hwnd: int = 0) -> bool:
        self._com.request("exit", int(hwnd or 0))
        return True

    def set_tool(self, tool: str, hwnd: int = 0) -> bool:
        """切换笔 / 橡皮 / 箭头。``tool`` 取 ``pen``/``eraser``/``arrow``/``none``。

        带上当前放映的 **kind** 一起投递 —— COM 线程靠它选快捷键回退通道
        （PowerPoint / WPS 用 Ctrl+P/E/A，永中只发 E/A）。
        """
        if tool not in TOOL_TO_POINTER:
            log.warning("未知工具: %s", tool)
            return False
        self._com.request("tool", int(hwnd or 0), tool, self._state.kind)
        return True

    def set_pen_color(self, r: int, g: int, b: int, hwnd: int = 0) -> bool:
        """设置墨迹颜色（``View.PointerColor``，L1 ``set_pen_color``）。

        只有 PowerPoint 走得通；WPS / 永中会直接返回失败（不报错，也不假装成功）。
        """
        for channel, value in (("r", r), ("g", g), ("b", b)):
            if not 0 <= int(value) <= 255:
                log.warning("墨迹颜色分量越界: %s=%s", channel, value)
                return False
        self._com.request("pen_color", int(r), int(g), int(b), self._state.kind)
        return True

    def exit_slideshow(self, hwnd: int = 0, keep_ink: bool = False) -> bool:
        """退出放映。``keep_ink=True`` 时先留墨迹再退（PowerPoint 专属）。"""
        self._com.request("exit", int(hwnd or 0), bool(keep_ink), self._state.kind)
        return True

    def clear_screen(self, hwnd: int = 0) -> bool:
        """清屏：擦除本页墨迹。"""
        self._com.request("clear", int(hwnd or 0), self._state.kind)
        return True

    def read_pen_color(self) -> Optional[tuple[int, int, int]]:
        """当前墨迹颜色（``(r, g, b)``）；本进程不碰 COM，只读 COM 线程的快照。

        颜色由 COM 线程在刷新快照时顺带读一次，主线程直接取用 ——
        主线程**永远不碰 COM**（这是本模块的线程铁律）。
        """
        return self._com.snapshot.pen_color
