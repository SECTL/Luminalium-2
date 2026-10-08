"""窗口管理：快捷面板 + 放映「顶层窗口」。

只负责「创建、摆放、显隐」；所有业务参数由 QML 直接读取
:class:`~app.bridge.Backend` 暴露的配置，Python 侧不重复注入，
避免出现两处配置来源。

放映控制条（工具栏 / 翻页栏等）统一托管在**一个置顶的顶层窗口**
（``ui/presentation/TopWindow.qml``）里：窗口整窗鼠标/触摸穿透，
仅当光标落在某个控制条表面矩形内时临时收回穿透，让工具栏可点。

----------------------------------------------------------------------
2026-10-06 起这层遮罩还会**跟着放映窗口走**（``_watch_overlay``，200ms 一拍）：
铺开的大小 / 位置取放映窗口的矩形（全屏放映即整屏），放映窗口不在前台时
把控制条淡出、切回来再淡入 —— 见 ``_apply_overlay_geometry`` 与
``_set_overlay_suppressed``。

----------------------------------------------------------------------
自管窗口（设置 / 调试 / 编辑器 / 插件窗口）约定（2026-10-05）：

* :meth:`WindowManager.register_window` 是创建这类窗口的**唯一合法途径**。
  它封装了「懒创建 → ``_attach_to_rinui`` 三清单注册 → ``_keep_frameless``
  兜底 → 定位 → show/raise/requestActivate」这整套约 90 行的易错清单；
  插件**不得**直接调 ``_attach_to_rinui``（绕过封装会漏掉句柄刷新、
  post_reattach 回调登记与同名幂等检查）。
* 同名重复注册是**幂等**的：返回既有句柄并记 ``log.warning``，绝不建出
  第二个窗口对象。这是刻意决策 —— 插件reload / 多次初始化时不允许
  同一逻辑窗口在屏幕上出现两份。
* QML 侧约定：根项必须是 ``Rin.FluentWindow``（或等价的 Window），声明
  ``visible: false``，并在 ``onClosing`` 里 ``event.accepted = false`` 后
  调 ``Backend`` 的关窗槽（由 ``*CloseRequested`` 信号绕回 Python 侧
  ``hide_*``）；**禁止**给窗口加 ``Qt.FramelessWindowHint``（边框 / 阴影 /
  圆角全由 RinUI 接管，QML 插手会把系统阴影弄没）；Python 侧**禁止**把槽
  连到 ``closing(QQuickCloseEvent*)`` 信号（PySide 无法转换该参数，
  一点关闭按钮就把应用打死，见 ``_bind_panel`` 的注释）。
* 窗口一律懒创建、只藏不销毁（splash 是唯一例外）。

叠加窗口（2026-10-06，聚光灯一类「整屏遮罩 + 镂空」）：与放映顶层窗口
同族的另一类，走 :meth:`WindowManager.register_overlay`（唯一合法途径，
同样幂等）→ :class:`RegisteredOverlay`。与自管窗口的差别：**不做** RinUI
接管（理由同 TopWindow）、QML 根项是带
``Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
Qt.WindowDoesNotAcceptFocus`` 的透明 ``Window``（这里的 Frameless 是
必须的 —— 它不是 RinUI 接管的 FluentWindow，不受上一条约束）、镂空由
Python 按 ``SetWindowRgn`` 塑形（插件经句柄 ``set_hole`` 喂洞）。

----------------------------------------------------------------------
角落组 → dock QML 解析规则（2026-10-05 插件系统 Wave 2 任务 8）：

* 每个启用角落用哪个 QML 组件渲染，由 :meth:`WindowManager._resolve_dock_qml`
  查 ``registry.editor_groups()`` 决定 —— 组名前缀硬编码（``middle_*`` →
  ``SidePager.qml``）已移除。角落朝向从 ``CORNERS`` 的对齐数据推导
  （垂直对齐 ``middle`` = 竖版贴边），**不看角名字符串**。
* 解析顺序：groups 中首个「有 dock_qml 且 orientation 匹配角落朝向」的组
  胜出；没有匹配 → 回落 ``presentation/PresentationDock.qml``（tools /
  actions / exit 无 dock_qml，底部翻页 pill 是它的 pagerOnly 形态）。
* **孤儿容忍**：角落 groups 全部未在注册表登记（手改 config / 插件卸载
  残留）→ 跳过该角 + ``log.warning``，不让一份坏配置打死整个叠加层。
* 内建组（tools/actions/exit/pager）在 :meth:`WindowManager._register_builtin_groups`
  里登记，幂等；注册表是组元数据的**代码侧唯一事实来源**，绝不写进 config。
"""

from __future__ import annotations

import copy
import ctypes
import ctypes.wintypes as wintypes
import logging
from pathlib import Path
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

from . import monitors
from .config import Config
from .paths import UI_DIR
from .plugins import registry
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

# 内建编辑器分组 → 注册表条目（2026-10-05 插件系统 Wave 2 任务 8）。
# 形状对齐 ``app.plugins.registry`` 的 ``editor_groups`` 贡献点：
# ``{dock_qml?, display_name, icon, inspector_items, traits}``。
#
# * ``dock_qml``：该组**专属**的 dock 渲染组件，UI_DIR 相对路径字符串
#   （不写绝对路径 —— 注册表条目要保持「代码侧声明、与安装位置无关」的形状）。
#   只有 ``pager`` 有：竖版两侧角落（CORNERS 垂直对齐为 ``middle``）用它；
#   横条角落没有组级 dock_qml，一律回落 ``PresentationDock.qml``（翻页 pill
#   是它的 ``pagerOnly`` 形态，不是另一个组件）。
# * ``traits`` 承载语义而非外观：``toolbar`` / ``pager`` 供编辑器
#   「有工具栏语义 / 有翻页语义」判定（Wave 2 任务 9 接管），
#   ``section_order`` 与 ``divider_before`` 对齐 ``PresentationDock.qml`` 的
#   ``sectionOrder`` / 分隔线规则，``orientation`` 标记 dock_qml 的朝向变体。
# * ``inspector_items``（2026-10-05 插件系统 Wave 2 任务 10 填入）：主界面
#   编辑器右侧检查器的设置项描述符列表，每项形状
#   ``{key, kind, title, description?, options?, visible_when_group?}``
#   （字段语义与校验规则见 ``app/plugins/registry.py`` 头注释第 7 条）。
#   归属按语义摆：「显示按钮文本」归 ``tools``（按钮是工具栏的主体）、
#   「退出键样式」归 ``exit``（退出键是这枚组的按钮）、「翻页组件位置」归
#   ``pager`` —— 编辑器取「选中角各组 inspector_items 的并集」渲染，
#   内建角落的 groups 配置下与重构前的 trait 显隐逐项一致。
_BUILTIN_DOCK_GROUPS: Dict[str, Dict[str, Any]] = {
    "tools": {
        "display_name": "工具",
        "icon": "ic_fluent_pen_20_filled",
        "inspector_items": [
            {
                "key": "presentation_buttons_show_labels",
                "kind": "switch",
                "title": "显示按钮文本",
            },
        ],
        "traits": {
            "toolbar": True,
            "section_order": 0,
            "divider_before": False,
        },
    },
    "actions": {
        "display_name": "动作",
        "icon": "ic_fluent_broom_20_filled",
        "inspector_items": [],
        "traits": {
            "toolbar": True,
            "section_order": 1,
            "divider_before": False,
        },
    },
    "exit": {
        "display_name": "退出",
        "icon": "ic_fluent_power_20_filled",
        "inspector_items": [
            {
                "key": "presentation_exit_style",
                "kind": "combo",
                "title": "退出键样式",
                "options": [
                    {"value": "default", "label": "白色"},
                    {"value": "danger", "label": "红色（Luminalium 1）"},
                ],
            },
        ],
        "traits": {
            "toolbar": True,
            "section_order": 3,
            "divider_before": True,
        },
    },
    "pager": {
        "display_name": "翻页",
        "icon": "ic_fluent_chevron_left_20_filled",
        "dock_qml": "presentation/SidePager.qml",
        "inspector_items": [
            {
                "key": "presentation_pager_position",
                "kind": "radio",
                "title": "翻页组件位置",
                "options": [
                    {"value": "side", "label": "竖版两侧中间"},
                    {"value": "bottom", "label": "横版两侧下部"},
                ],
            },
        ],
        "traits": {
            "pager": True,
            "section_order": 2,
            "divider_before": True,
            # dock_qml 是竖版变体：只对「贴屏幕左右、垂直居中」的角落生效，
            # 横条角落的翻页 pill 走 PresentationDock 的 pagerOnly 回落。
            "orientation": "vertical",
        },
    },
}

#: 检查器描述符支持的控件类型（能力上限 = 内建三项既有设置，刻意不加新类型）。
_INSPECTOR_KINDS = ("switch", "combo", "radio")


def validate_inspector_items(group_name: str, items: Any) -> None:
    """校验一组编辑器检查器描述符；非法即记日志并抛 ``ValueError``（拒绝注册）。

    校验点：条目必须是 dict；``key`` / ``title`` 是非空 str；``kind`` 在
    ``_INSPECTOR_KINDS`` 内；``combo`` / ``radio`` 必须带非空 ``options``
    （每项 ``{value, label}``）；``visible_when_group`` 若给出必须指向
    **已知的组名**（内建组 ∪ 注册表已登记组 —— 指向没注册的组名多半是
    插件打错了字，静默放过会变成「设置项永远不出现」的悬案）。

    QML 侧不做校验 UI：坏描述符在注册侧就被拦下，不该流进检查器渲染。
    """
    if not isinstance(items, list):
        log.error(
            "编辑器组 %r 的 inspector_items 必须是列表，实际: %r", group_name, items
        )
        raise ValueError(f"编辑器组 {group_name!r} 的 inspector_items 必须是列表")
    known_groups = set(_BUILTIN_DOCK_GROUPS) | set(registry.editor_groups())
    for index, item in enumerate(items):
        where = f"编辑器组 {group_name!r} 的第 {index} 项检查器描述符"
        if not isinstance(item, dict):
            log.error("%s必须是 dict，实际: %r", where, item)
            raise ValueError(f"{where}必须是 dict")
        key = item.get("key")
        if not isinstance(key, str) or not key:
            log.error("%s缺合法的 key（扁平设置键）: %r", where, item)
            raise ValueError(f"{where}缺合法的 key")
        title = item.get("title")
        if not isinstance(title, str) or not title:
            log.error("%s（key=%r）缺合法的 title: %r", where, key, item)
            raise ValueError(f"{where}（key={key!r}）缺合法的 title")
        kind = item.get("kind")
        if kind not in _INSPECTOR_KINDS:
            log.error(
                "%s（key=%r）的 kind 未知: %r（支持 %s）",
                where, key, kind, "/".join(_INSPECTOR_KINDS),
            )
            raise ValueError(f"{where}（key={key!r}）的 kind 未知: {kind!r}")
        if kind in ("combo", "radio"):
            options = item.get("options")
            ok = isinstance(options, list) and len(options) > 0 and all(
                isinstance(opt, dict) and "value" in opt and "label" in opt
                for opt in options
            )
            if not ok:
                log.error(
                    "%s（key=%r，kind=%r）缺合法的 options（[{value, label}, ...]）: %r",
                    where, key, kind, options,
                )
                raise ValueError(
                    f"{where}（key={key!r}，kind={kind!r}）缺合法的 options"
                )
        visible_when_group = item.get("visible_when_group")
        if visible_when_group is not None and (
            not isinstance(visible_when_group, str)
            or visible_when_group not in known_groups
        ):
            log.error(
                "%s（key=%r）的 visible_when_group 未知: %r（已知组: %s）",
                where, key, visible_when_group, sorted(known_groups),
            )
            raise ValueError(
                f"{where}（key={key!r}）的 visible_when_group 未知: "
                f"{visible_when_group!r}"
            )

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
RGN_DIFF = 4
HWND_NOTOPMOST = -2
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


def _build_region_with_hole(
    width: float, height: float, hole: tuple[float, float, float]
) -> Optional[int]:
    """「整窗矩形 − 圆形」的 HRGN（聚光灯一类遮罩的镂空），失败返回 ``None``。

    ``(cx, cy, r)`` 是**已按坐标倍率换算好**的窗口局部物理像素圆心与半径；
    调用方负责换算（见 :meth:`RegisteredOverlay._sync_region`）。椭圆区域用
    ``CreateEllipticRgn``（外接矩形式 API），从整窗矩形里 ``RGN_DIFF`` 掉。
    """
    if not hasattr(ctypes, "windll"):
        return None
    gdi32 = ctypes.windll.gdi32
    cx, cy, radius = hole
    base = gdi32.CreateRectRgn(0, 0, int(round(width)), int(round(height)))
    if not base:
        return None
    hole_rgn = gdi32.CreateEllipticRgn(
        int(round(cx - radius)), int(round(cy - radius)),
        int(round(cx + radius)), int(round(cy + radius)),
    )
    if not hole_rgn:
        gdi32.DeleteObject(base)
        return None
    gdi32.CombineRgn(base, base, hole_rgn, RGN_DIFF)
    gdi32.DeleteObject(hole_rgn)
    return base


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


#: 「这个放映窗口就是全屏」的面积比阈值（2026-10-06，遮罩跟随放映窗口用）。
#: 到比例就直接取**显示器矩形**：全屏放映窗口常带一圈不可见边框，
#: ``GetWindowRect`` 会大出（或小掉）几个像素，照抄会让贴边距离静默偏掉。
FULLSCREEN_SNAP_RATIO = 0.97

#: 「快速切页面板点外部收起」的判定余量（逻辑像素）。面板贴屏幕边时，光标压在
#: 它的边缘上稍微抖一下就会被判成「出去了」→ 面板一闪一闪。四边各放这么宽。
JUMP_DISMISS_SLACK = 6

#: 墨迹窗口「整窗吃输入」的工具（2026-10-07 self-ink）；其余工具一律整窗穿透。
INK_INPUT_TOOLS = ("pen", "eraser")


def _window_pid(hwnd: int) -> int:
    """窗口所属进程 id；取不到返回 0。"""
    if not hwnd or not hasattr(ctypes, "windll"):
        return 0
    try:
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(
            wintypes.HWND(hwnd), ctypes.byref(pid)
        )
        return int(pid.value)
    except OSError:  # pragma: no cover
        return 0


def _foreground_window() -> int:
    """当前前台窗口句柄；没有（锁屏 / 切换途中）返回 0。"""
    if not hasattr(ctypes, "windll"):
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except OSError:  # pragma: no cover
        return 0


def _logical_rect_from_native(screen, rect: tuple[int, int, int, int]) -> QRect:
    """把**物理**矩形 ``(x, y, w, h)`` 换算成 ``screen`` 所属坐标系里的逻辑矩形。

    直接按主屏 DPR 去除是不行的（多屏不同缩放倍率时会打偏到别的屏），
    必须用这块屏自己的「逻辑原点 + 物理原点 + DPR」三者换算。
    """
    native = _native_window_rect_for(screen)
    geometry = screen.geometry()
    dpr = screen.devicePixelRatio() or 1.0
    return QRect(
        geometry.x() + int(round((rect[0] - native[0]) / dpr)),
        geometry.y() + int(round((rect[1] - native[1]) / dpr)),
        max(1, int(round(rect[2] / dpr))),
        max(1, int(round(rect[3] / dpr))),
    )


def _native_rect_from_logical(screen, rect: QRect) -> tuple[int, int, int, int]:
    """:func:`_logical_rect_from_native` 的逆运算（自检对照用）。"""
    native = _native_window_rect_for(screen)
    geometry = screen.geometry()
    dpr = screen.devicePixelRatio() or 1.0
    return (
        native[0] + int(round((rect.x() - geometry.x()) * dpr)),
        native[1] + int(round((rect.y() - geometry.y()) * dpr)),
        int(round(rect.width() * dpr)),
        int(round(rect.height() * dpr)),
    )


def _covers_monitor(hwnd: int, ratio: float = 0.9) -> bool:
    """窗口是否铺满它所在的显示器（面积占比 ≥ ``ratio``）。"""
    rect = _window_rect(hwnd)
    monitor = monitor_rect_for_window(hwnd)
    if rect is None or monitor is None:
        return False
    win_area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
    mon_area = max(1, (monitor[2] - monitor[0]) * (monitor[3] - monitor[1]))
    return win_area / mon_area >= ratio


class RegisteredWindow:
    """:meth:`WindowManager.register_window` 返回的窗口句柄。

    封装一只「自管窗口」的全生命周期：**懒创建**（第一次 :meth:`show` 才
    实例化 QML）、RinUI 三清单接管、失败回退 frameless、按声明的模式定位、
    只藏不销毁。调用方（含插件）只面对 ``show()/hide()/toggle()`` 三个方法
    与只读的 :attr:`window`，不需要、也不允许再碰 ``_attach_to_rinui``
    那套内部清单。

    定位模式（``position`` 参数）：

    * ``"cursor_screen_center"`` —— 居中到**光标所在**显示器（多屏不跑屏）；
    * ``"beside_settings"`` —— 贴在设置窗口旁边（设置窗口没开就退化为上一项），
      调试窗口 / 主界面编辑器这类「从别的窗口里点出来」的窗口用这套；
    * 可调用对象 ``callable(window)`` —— 完全自定义摆位（留给插件）。
    """

    def __init__(
        self,
        manager: "WindowManager",
        name: str,
        qml_path,
        *,
        position="cursor_screen_center",
        label: Optional[str] = None,
        post_reattach=None,
        post_show=None,
    ) -> None:
        self._manager = manager
        self._name = name
        self._qml_path = qml_path
        self._position = position
        #: 只用于日志与「贴在设置窗口旁边」的报错文案，让人一眼看出是谁
        self._label = label or name
        self._post_reattach = post_reattach
        self._post_show = post_show
        self._window: Optional[QQuickWindow] = None
        # WindowManager 上若存在同名属性槽（settings / debug / editor 这三个
        # 内建窗口），创建后同步写入 —— 既有代码与 tools/ 下的自检脚本都直接
        # 读 ``app.windows.settings`` 这种属性，迁移不能改变这个对外形状。
        self._sync_attr = hasattr(manager, name)

    @property
    def name(self) -> str:
        return self._name

    @property
    def window(self) -> Optional[QQuickWindow]:
        """底层窗口对象；尚未懒创建时为 ``None``（读它不会触发创建）。"""
        return self._window

    def is_visible(self) -> bool:
        return self._window is not None and self._window.isVisible()

    def show(self) -> None:
        window = self._ensure_created()
        if window is None:
            log.info("%s 不可用", self._label)
            return
        self._place(window)
        window.show()
        # 显示后的补充钩子（编辑器用它补打亚克力：show() 后系统会重置
        # backdrop，见 ``_attach_editor_acrylic`` 的注释）
        if self._post_show is not None:
            try:
                self._post_show(window)
            except Exception:
                log.warning("%s post_show 钩子执行失败", self._label, exc_info=True)
        window.raise_()
        window.requestActivate()

    def hide(self) -> None:
        if self.is_visible():
            self._window.hide()

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def _ensure_created(self) -> Optional[QQuickWindow]:
        """懒创建窗口并交给 RinUI 接管（失败退回 frameless 兜底）。"""
        if self._window is not None:
            return self._window
        manager = self._manager
        qml_path = self._qml_path
        if not isinstance(qml_path, Path):
            qml_path = Path(qml_path)
        if not qml_path.exists():
            log.warning("%s不存在，跳过: %s", self._label, qml_path)
            return None
        root = manager._create(qml_path, {"visible": False})
        if root is None:
            log.error("%s创建失败: %s", self._label, qml_path)
            return None
        self._window = root
        if self._sync_attr:
            setattr(manager, self._name, root)
        # post_reattach 回调要先登记再接管：接管会挂 visibleChanged →
        # ``_refresh_rinui_handle``，后者按窗口查这张表
        if self._post_reattach is not None:
            manager._reattach_callbacks[root] = self._post_reattach
        # 交给 RinUI 管（否则没有 DWM 阴影 / 圆角 / resize 边框 / Snap，
        # 且 WS_CAPTION 会露出原生标题栏）
        if not manager._attach_to_rinui(root):
            manager._keep_frameless(root)
        # 首次接管也算一次「接管完成」，补一遍 post_reattach（编辑器的亚克力
        # 就是在这里打的：接管补了 WS_CAPTION / frame，次序反了会被覆盖）
        if self._post_reattach is not None:
            try:
                self._post_reattach(root)
            except Exception:
                log.warning("%s post_reattach 钩子执行失败", self._label, exc_info=True)
        return root

    def _place(self, window: QQuickWindow) -> None:
        if callable(self._position):
            self._position(window)
            return
        if self._position == "beside_settings":
            self._manager._place_beside_settings(window, self._label)
            return
        # 默认 "cursor_screen_center"：居中到光标所在显示器（不是主屏），
        # 多屏时窗口不会跑到别的屏幕上
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.left() + (area.width() - window.width()) // 2
        y = area.top() + (area.height() - window.height()) // 2
        window.setPosition(int(x), int(y))

    def _reset(self) -> None:
        """``shutdown()`` 时清掉句柄状态（窗口本身随进程退出回收）。"""
        if self._window is not None:
            self._manager._reattach_callbacks.pop(self._window, None)
        self._window = None
        if self._sync_attr:
            setattr(self._manager, self._name, None)


class RegisteredOverlay:
    """全屏叠加窗口句柄（聚光灯这类「整屏遮罩 + 镂空」窗口的登记句柄）。

    与 :class:`RegisteredWindow`（RinUI 接管的 FluentWindow）不同族：叠加
    窗口与放映顶层窗口（``TopWindow``）同类 —— 无边框、置顶、不抢焦点、
    窗口区域由 Python 塑形，**刻意不做** RinUI 接管（RinUI 的非客户区处理
    会和全屏穿透窗口打架，理由见 ``_attach_to_rinui`` 尾段）。创建仍走
    :meth:`WindowManager.register_overlay` —— 插件不许自建 QQuickWindow，
    这条铁律对叠加窗口同样有效。

    职责边界：本类只管「懒创建 / 全屏摆放 / NOACTIVATE 样式 / 圆形镂空的
    区域塑形（含 SetWindowRgn 坐标倍率校准）」；洞跟谁走、多大是插件自己的
    业务，插件经 :meth:`set_hole` 每拍喂进来（光标轮询由插件侧定时器驱动，
    别把「遮罩用途」写死在窗口管理器里）。

    与 TopWindow 的两点刻意差异：

    * **不加** ``WS_EX_TRANSPARENT`` —— 遮罩要吃点击（遮罩上的控件才可点、
      光标圈外才是「聚焦」语义），镂空里的点击经区域塑形自然穿透；
    * 显示后若放映顶层窗口可见，立刻替它重申一次置顶 —— 两只窗口都在
      置顶带里，后显示的在上；不压回去，遮罩会把控制条盖住、吃掉它的点击。
    """

    def __init__(
        self,
        manager: "WindowManager",
        name: str,
        qml_path,
        *,
        label: Optional[str] = None,
    ) -> None:
        self._manager = manager
        self._name = name
        self._qml_path = qml_path if isinstance(qml_path, Path) else Path(qml_path)
        self._label = label or name
        self._window: Optional[QQuickWindow] = None
        #: 镂空圆 ``(cx, cy, r)``——窗口局部**逻辑**坐标（set_hole 的入参原样存，
        #: 换算成物理像素在 _sync_region 里做）
        self._hole: Optional[tuple[int, int, int]] = None
        self._screen: Optional[QScreen] = None
        #: SetWindowRgn 的坐标单位倍率（与 WindowManager._region_scale 同义，
        #: 各窗口各有一份 —— 不同屏的 DPR 可以不同）
        self._region_scale: Optional[float] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def window(self) -> Optional[QQuickWindow]:
        """底层窗口对象；尚未懒创建时为 ``None``。"""
        return self._window

    def is_visible(self) -> bool:
        return self._window is not None and self._window.isVisible()

    def show(self) -> None:
        """全屏铺到光标所在显示器（多屏时聚哪块屏由光标决定，不猜配置）。"""
        window = self._ensure_created()
        if window is None:
            log.info("%s 不可用", self._label)
            return
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            try:
                window.setScreen(screen)
                window.setGeometry(screen.geometry())
            except Exception:  # pragma: no cover - 平台差异
                log.debug("%s 定屏失败", self._label, exc_info=True)
            self._screen = screen
        window.show()
        window.raise_()
        self._apply_styles()
        self._sync_region()
        # 放映顶层窗口可见时替它重申置顶（本句柄刚把自己顶到了置顶带顶端）
        if self._manager.overlay is not None and self._manager.overlay.isVisible():
            self._manager._assert_topmost()

    def hide(self) -> None:
        if not self.is_visible():
            return
        # 先摘区域再藏窗口：区域留着的话，下次 show() 的第一帧仍是旧镂空
        try:
            _set_window_region(int(self._window.winId()), None)
        except (RuntimeError, OSError):  # pragma: no cover - 窗口已释放
            pass
        self._hole = None
        self._window.hide()

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def set_hole(self, cx: int, cy: int, radius: int) -> None:
        """更新镂空圆（窗口局部逻辑坐标），遮罩可见时立刻重新塑形。"""
        self._hole = (int(cx), int(cy), max(8, int(radius)))
        if self.is_visible():
            self._sync_region()

    def _ensure_created(self) -> Optional[QQuickWindow]:
        """懒创建叠加窗口。不走 RinUI 接管（理由见类头注释），失败仅记日志。"""
        if self._window is not None:
            return self._window
        if not self._qml_path.exists():
            log.warning("%s不存在，跳过: %s", self._label, self._qml_path)
            return None
        try:
            root = self._manager._create(self._qml_path, {"visible": False})
        except RuntimeError as exc:
            log.error("%s创建失败: %s（%s）", self._label, self._qml_path, exc)
            return None
        if root is None:
            log.error("%s创建失败: %s", self._label, self._qml_path)
            return None
        self._window = root
        return root

    def _apply_styles(self) -> None:
        """补 ``WS_EX_NOACTIVATE``（点击遮罩不抢前台焦点，方向键仍归放映窗口）。

        ⚠️ 与 ``_apply_overlay_base_styles`` 同款纪律：只加不减，
        ``WS_EX_LAYERED`` 一个 bit 都不能动。
        """
        if self._window is None:
            return
        try:
            hwnd = int(self._window.winId())
        except RuntimeError:  # pragma: no cover - 窗口已释放
            return
        if not hwnd:
            return
        style = _window_ex_style(hwnd)
        _set_window_ex_style(hwnd, style | WS_EX_NOACTIVATE)

    def _sync_region(self) -> None:
        """把窗口塑形为「整屏 − 镂空圆」。

        ``SetWindowRgn`` 的坐标单位（逻辑 vs 物理）不猜：按候选倍率各试一次，
        用 ``GetWindowRgn + GetRgnBox`` 读回外接矩形对照 —— 「整屏减圆」的
        外接矩形就是整窗矩形，尺寸随倍率线性变，正好当校准判据（与
        ``WindowManager._update_overlay_region`` 同一招）。倍率校准成功后
        缓存复用，之后每次只是重建区域。
        """
        if self._window is None or not self._window.isVisible() or self._hole is None:
            return
        try:
            hwnd = int(self._window.winId())
        except RuntimeError:  # pragma: no cover - 窗口已释放
            return
        if not hwnd or not hasattr(ctypes, "windll"):
            return
        width = float(self._window.width())
        height = float(self._window.height())
        if width <= 0 or height <= 0:
            return
        cx, cy, radius = self._hole
        dpr = self._window.devicePixelRatio() or 1.0
        candidates = [self._region_scale, dpr, 1.0]
        seen: set[float] = set()
        for scale in candidates:
            if not scale or scale <= 0 or scale in seen:
                continue
            seen.add(scale)
            hrgn = _build_region_with_hole(
                width * scale, height * scale,
                (cx * scale, cy * scale, radius * scale),
            )
            if hrgn is None:
                continue
            if not _set_window_region(hwnd, hrgn):
                ctypes.windll.gdi32.DeleteObject(hrgn)
                continue
            actual = _region_box(hwnd)
            expected_w = int(round(width * scale))
            expected_h = int(round(height * scale))
            if actual is None or abs(actual[2] - expected_w) > 2 \
                    or abs(actual[3] - expected_h) > 2:
                # SetWindowRgn 成功后区域已归系统所有，绝不能再 DeleteObject
                # （下一次 SetWindowRgn 会换掉它），直接试下一个候选。
                continue
            self._region_scale = scale
            try:
                self._window.requestUpdate()
            except (AttributeError, RuntimeError):  # pragma: no cover
                pass
            return
        # 塑形全失败：遮罩没有洞（整屏变暗），但遮罩上的关闭按钮仍可点，
        # 用户能自己退出去 —— 记 error 别静默。
        log.error("%s 区域塑形失败（坐标单位未校准），遮罩暂时没有镂空", self._label)


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
        # 以下三个属性槽由 :meth:`register_window` 的句柄在懒创建时同步写入
        # （句柄名与属性名一致）；不要直接赋值，一律走 ``_registered_windows``
        # 里对应句柄的 ``show()/hide()/toggle()``。
        self.settings: Optional[QQuickWindow] = None
        #: 调试窗口（隐藏入口：设置窗口标题连点 10 次）
        self.debug: Optional[QQuickWindow] = None
        #: 主界面编辑器（入口：快捷面板的「主界面编辑器」快捷方式）
        self.editor: Optional[QQuickWindow] = None
        #: 错误 / 崩溃报告（入口：``ErrorHandler`` 捕获到未捕获异常）。
        #: 定位逻辑带尺寸夹取、且在异常栈里被调用，刻意不走 register_window。
        self.error_report: Optional[QQuickWindow] = None
        #: 已注册的自管窗口句柄：名字 -> :class:`RegisteredWindow`
        self._registered_windows: Dict[str, RegisteredWindow] = {}
        #: 已注册的全屏叠加窗口句柄：名字 -> :class:`RegisteredOverlay`
        #: （聚光灯一类；面板被遮罩盖住时要把面板顶进置顶带，见
        #: :meth:`_push_panel_above_overlays`）
        self._registered_overlays: Dict[str, RegisteredOverlay] = {}
        #: 窗口对象 -> post_reattach 回调（``_refresh_rinui_handle`` 按窗口查）
        self._reattach_callbacks: Dict[Any, Any] = {}
        self.overlay: Optional[QQuickWindow] = None
        #: 自建墨迹叠加窗口（2026-10-07 计划 self-ink 第 3 项）：由
        #: :meth:`_ensure_ink_window` 懒创建、只藏不销毁，几何由
        #: :meth:`_apply_ink_geometry` 跟随 TopWindow 同一份 ``_overlay_rect``，
        #: z 序由 :meth:`_place_ink_below_top` 夹在放映窗口与 TopWindow 之间。
        self.ink_window: Optional[QQuickWindow] = None
        #: 调用方要求「放映中显示墨迹窗口」（set_ink_active）；放映结束不清它，
        #: 只把窗口藏起来 —— 下一次放映开始时由 show_docks 按它恢复。
        self._ink_active = False
        #: 当前墨迹页键（2026-10-07 计划 self-ink 第 7 项）：放映期间由
        #: _sync_ink_page 按 slide_index 维护；None = 不在放映/还没同步过页键。
        #: 键 0 = 基线**待定**（首次同步时 COM 还没读出页码），之后读到真实页码
        #: 即升级为按页记忆（2026-10-08 修复：此前键 0 会锁死整场，翻页永不换
        #: 墨迹快照）；基线确立后 slide_index=0 一律忽略 —— COM 瞬时读不到页码
        #: 不该把用户踢回空页。
        self._ink_page_key: Optional[int] = None
        #: 基线待定（COM 读不到页码，先共用键 0）只记一次日志
        self._ink_single_page_logged = False
        #: 当前墨迹工具：pen / eraser 整窗吃输入，其余（arrow）整窗穿透
        self._ink_tool = "arrow"
        #: 墨迹窗口当前所在屏（逻辑↔物理换算要它自己的 DPR，同 _overlay_screen）
        self._ink_screen: Optional[QScreen] = None
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

        #: 遮罩当前实际铺开的逻辑矩形（= :meth:`_apply_overlay_geometry` 的结果，
        #: 也是 :meth:`_position_dock` 的摆放基准）。全屏放映时等于整屏几何。
        self._overlay_rect: Optional[QRect] = None
        #: 遮罩当前所在的显示器 —— 逻辑↔物理换算要它自己的 DPR
        self._overlay_screen: Optional[QScreen] = None
        #: 是否因「放映窗口不在前台」而临时隐去（见 :meth:`_set_overlay_suppressed`）
        self._suppressed = False
        #: 顶层窗口「智能跟随」看护：放映窗口挪动 / 缩放 → 遮罩跟着动；
        #: 放映窗口不在前台 → 临时隐去。一拍只做两次系统调用，代价可忽略。
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(
            max(80, int(self._config.get("presentation.follow_interval_ms", 200)))
        )
        self._watch_timer.timeout.connect(self._watch_overlay)

    # ================================================================== 装配

    def load_windows(self) -> None:
        if self.panel is None:
            self._create_panel()
        else:
            self._bind_panel()
        # 组登记必须先于 dock 创建：``_create_docks`` 靠注册表解析渲染组件。
        self._register_builtin_groups()
        self._load_docks()
        self._register_builtin_windows()
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

    def _resolve_dock_qml(self, name: str, groups: List[str]) -> Optional[Path]:
        """解析角落 ``name`` 该用哪个 QML 组件渲染（组 → 组件，注册表驱动）。

        规则（2026-10-05 插件系统 Wave 2 任务 8，替代 ``middle_*`` 字符串
        前缀硬编码）：

        1. **孤儿容忍**：``groups`` 里一个注册表认识的组都没有（用户手改
           config 写了不存在的组名 / 插件已卸载但配置残留）→ 记
           ``log.warning`` 并返回 ``None``，调用方跳过该角，**不崩**。
        2. 取 ``groups`` 中**首个**在注册表里有 ``dock_qml`` 且其
           ``traits.orientation`` 与角落朝向匹配的组，用它的 ``dock_qml``。
           角落朝向**从 CORNERS 的对齐数据推导**（垂直对齐 ``middle`` =
           竖版贴边），不看角名前缀 —— 角名只是配置的键，对齐才是语义。
        3. 没有匹配的组级 dock_qml（tools/actions/exit 本来就没有；pager 的
           竖版变体在横条角落不适用）→ 回落横向 ``PresentationDock.qml``
           （现状行为：底部翻页 pill 是它的 ``pagerOnly`` 形态）。
        """
        registered = registry.editor_groups()
        if groups and not any(g in registered for g in groups):
            log.warning(
                "角落 %s 的组全部未在注册表登记（孤儿组）: %s，跳过该角",
                name, groups,
            )
            return None
        _, vertical = CORNERS.get(name, ("left", "bottom"))
        orientation = "vertical" if vertical == "middle" else "horizontal"
        for group in groups:
            entry = registered.get(group)
            if entry is None:
                continue
            dock_qml = entry.get("dock_qml")
            if not dock_qml:
                continue
            traits = entry.get("traits") or {}
            if (traits.get("orientation") or "horizontal") != orientation:
                continue
            return UI_DIR / dock_qml
        return UI_DIR / "presentation" / "PresentationDock.qml"

    def _create_docks(self, container) -> None:
        """按当前配置给各角落建控制条（挂到顶层窗口的容器里）。

        与 :meth:`_load_docks` 分开是为了**重建**：改「翻页组件位置」会换掉
        启用的角落集合（竖版两侧 ↔ 横版下部），而且两边的组件根本不是一个
        QML 文件（``SidePager`` vs ``PresentationDock``）—— 光挪位置不够，
        得整批销毁重建。

        用哪个 QML 组件由 :meth:`_resolve_dock_qml` 按注册表决定，这里不再
        关心组名语义；孤儿角落（组全都不认识）被跳过，只留一条 warning。
        """
        corners = self._config.get("presentation.corners", {}) or {}
        for name in CORNERS:
            settings = corners.get(name) or {}
            if not settings.get("enabled", False):
                continue
            qml_path = self._resolve_dock_qml(name, settings.get("groups") or [])
            if qml_path is None:
                continue
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
            # 句柄重建、以及本次显隐引起的 frame 重应用都可能把窗口自定义的
            # DWM 效果清掉（编辑器的亚克力就是挂在 hwnd 上的），所以按注册时
            # 声明的 post_reattach 回调补一拍 —— 不再硬编码「是哪个窗口」。
            callback = self._reattach_callbacks.get(window)
            if callback is not None:
                callback(window)
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

    # ======================================================== 自管窗口注册

    def register_window(
        self,
        name: str,
        qml_path,
        *,
        position="cursor_screen_center",
        label: Optional[str] = None,
        post_reattach=None,
        post_show=None,
    ) -> RegisteredWindow:
        """注册一只自管窗口（设置 / 调试 / 编辑器 / 插件窗口），返回句柄。

        这是这类窗口的**唯一合法创建途径**（2026-10-05 起，插件系统 Wave 1
        的地基）：懒创建、RinUI 接管、失败兜底、定位、显隐三件套全部封装在
        返回的 :class:`RegisteredWindow` 里，插件不得直接调
        ``_attach_to_rinui``。

        **幂等**：同名重复注册不建新窗口、不覆盖既有配置，记一条
        ``log.warning`` 并返回既有句柄 —— 插件 reload / 重复初始化时
        屏幕上绝不允许出现两份同一逻辑窗口。

        参数：

        * ``position``：定位模式，见 :class:`RegisteredWindow` 的说明；
        * ``post_reattach``：可选回调 ``callable(window)``，在**每次**
          RinUI 接管完成 / 原生句柄刷新后调用（窗口专属 DWM 效果的补打
          入口，编辑器亚克力走的就是这里）；
        * ``post_show``：可选回调 ``callable(window)``，每次 ``show()``
          之后、``raise_()`` 之前调用。
        """
        existing = self._registered_windows.get(name)
        if existing is not None:
            log.warning("窗口 %s 重复注册，返回既有句柄（幂等）", name)
            return existing
        handle = RegisteredWindow(
            self,
            name,
            qml_path,
            position=position,
            label=label,
            post_reattach=post_reattach,
            post_show=post_show,
        )
        self._registered_windows[name] = handle
        return handle

    def register_overlay(
        self,
        name: str,
        qml_path,
        *,
        label: Optional[str] = None,
    ) -> RegisteredOverlay:
        """注册一只全屏叠加窗口（聚光灯一类），返回 :class:`RegisteredOverlay`。

        这是叠加窗口的**唯一合法创建途径**（与 :meth:`register_window`
        同一条铁律的叠加窗口分支）：懒创建、全屏摆放、NOACTIVATE 样式、
        圆形镂空的区域塑形全封装在句柄里；插件不得自建 QQuickWindow。
        与 ``register_window`` 的差别（为什么不是同一张表）：叠加窗口刻意
        不做 RinUI 接管、不参与 ``_reattach_callbacks``，生命周期完全独立
        （见 :class:`RegisteredOverlay` 头注释）。

        **幂等**：同名重复注册返回既有句柄，与 :meth:`register_window` 同款。
        """
        existing = self._registered_overlays.get(name)
        if existing is not None:
            log.warning("叠加窗口 %s 重复注册，返回既有句柄（幂等）", name)
            return existing
        handle = RegisteredOverlay(self, name, qml_path, label=label)
        self._registered_overlays[name] = handle
        return handle

    def _register_builtin_groups(self) -> None:
        """把四个内建编辑器分组登记进 ``registry.editor_groups()``。

        只登记、不消费 —— 消费在 ``_create_docks`` 的组件解析里。

        **幂等**：先查 ``editor_groups()`` 再登记。注册表对重复 id 抛
        ``ValueError``（刻意设计，防两个插件抢 id 时静默覆盖），而
        ``load_windows()`` 理论上可能被多次进入（重启装配 / 测试夹具），
        不查重就会把正常流程打成异常。
        """
        already = registry.editor_groups()
        for name, entry in _BUILTIN_DOCK_GROUPS.items():
            if name in already:
                continue
            # 深拷一层再交出去：模块级字典是模板，注册表条目不能共享引用。
            # 登记前先过描述符校验（任务 10）：内建描述符写错属于编程错误，
            # 让 ValueError 直接炸出来，比渲染出一个坏检查器好查。
            validate_inspector_items(name, entry.get("inspector_items", []))
            registry.add_editor_group(name, copy.deepcopy(entry))

    def _register_builtin_windows(self) -> None:
        """注册三只内建自管窗口（只登记，不创建 —— 懒创建语义不变）。

        错误报告窗口**刻意不在**这里：它的定位带尺寸夹取、且在异常处理栈里
        被调用（要自己包 try），保持原来的手写路径。
        """
        self.register_window(
            "settings", UI_DIR / "Settings.qml", label="设置窗口"
        )
        self.register_window(
            "debug",
            UI_DIR / "DebugWindow.qml",
            position="beside_settings",
            label="调试窗口",
        )
        # 编辑器的亚克力：post_reattach 负责「接管 / 句柄刷新后补打」，
        # post_show 负责「show() 后再打 + 320ms 补拍」（原因见
        # ``_attach_editor_acrylic`` 的注释），两个钩子缺一不可。
        self.register_window(
            "editor",
            UI_DIR / "MainInterfaceEditor.qml",
            position="beside_settings",
            label="主界面编辑器",
            post_reattach=lambda w: self._attach_editor_acrylic(schedule=True),
            post_show=lambda w: self._attach_editor_acrylic(schedule=True),
        )

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
        # 「目标显示器」变更 → 放映中立刻换屏，不等 200ms 看护一拍（且
        # ``follow_window_rect=false`` 时看护根本不跑几何那段，不接线就永远
        # 不挪）。信号是整块放映配置粒度的（改边距等也会跟着发），槽里按几何
        # 前后比对，没变就空转。
        self._backend.presentationScreenChanged.connect(
            self._on_presentation_screen_changed
        )

    def _on_presentation_state(self, state) -> None:
        # 状态只往两处去：bridge（QML 侧读 presentationActive / 页码）与控制条显隐。
        # 2026-10-01 起不再把整份快照塞给 bridge —— 那是为「设置页显示实际认到
        # 哪家软件 / 哪个窗口」那几张卡片准备的，卡片已随用户指令删除。
        self._backend.apply_state(state)
        if state.active:
            self.show_docks()
        else:
            self.hide_docks()
        # 按页墨迹（计划 self-ink 第 7 项）要放在 show/hide_docks **之后**：
        # 第一次 active 状态到达时墨迹窗口可能还没建，show_docks 按意图
        # 建好之后这里才拿得到层。
        self._sync_ink_page(state)

    def _on_presentation_screen_changed(self) -> None:
        """钉屏显示器变更 → 遮罩立刻重铺（放映中换「目标显示器」即时生效）。

        2026-10-08 之前 ``presentationScreenChanged`` 只有主界面编辑器的画布
        在读：设置里换钉屏后，控制条要等下一次 ``show_docks``（退出放映再进，
        或靠 200ms 看护捡上）才挪窝。未放映时遮罩本来就藏着，什么都不用做，
        下一次 ``show_docks`` 自会按新钉屏铺。
        """
        if self.overlay is None or not self.overlay.isVisible():
            return
        before = self._overlay_rect
        after = self._apply_overlay_geometry()
        if before == after:
            return
        # 与 _watch_overlay 的几何变更分支同一份清单：区域矩形集作废 +
        # 重摆控制条 + 重算穿透 + 墨迹窗口同走（它与遮罩共用 _overlay_rect）
        self._last_region_rects = None
        for name in self._docks:
            self._position_dock(name)
        self._sync_input_mode()
        self._apply_ink_geometry()

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
        # 有全屏遮罩（聚光灯一类）开着时，面板要顶进置顶带才看得见
        self._push_panel_above_overlays()

    def hide_panel(self) -> None:
        if self.panel is not None and self.panel.isVisible():
            self.panel.hide()
        self._push_panel_above_overlays()

    def _push_panel_above_overlays(self) -> None:
        """面板与全屏遮罩的 z 序协调。

        快捷面板是普通带的窗口；聚光灯这类全屏置顶遮罩显示时，面板
        ``show() + raise_()`` 只在普通带里升 —— 顶不穿遮罩，用户看到的是
        「托盘点了没反应」。遮罩可见时用原生 ``SetWindowPos`` 把面板临时
        推进置顶带，遮罩都收了再放回普通带。走原生调用而不是改 Qt 的
        ``flags``：改 flags 会触发 Qt 重建原生窗口，RinUI 按 hwnd 登记的
        三份清单（``_attach_to_rinui``）就全断了。
        """
        if self.panel is None or not hasattr(ctypes, "windll"):
            return
        try:
            hwnd = int(self.panel.winId())
        except (RuntimeError, AttributeError):  # pragma: no cover - 窗口未建
            return
        if not hwnd:
            return
        overlay_up = any(h.is_visible() for h in self._registered_overlays.values())
        band = HWND_TOPMOST if overlay_up else HWND_NOTOPMOST
        try:
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(hwnd), wintypes.HWND(band),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        except OSError:  # pragma: no cover
            log.debug("调整面板 z 序失败", exc_info=True)

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

    def toggle_settings(self) -> None:
        self._registered_windows["settings"].toggle()

    def show_settings(self, page: str = "") -> None:
        """打开设置窗口；``page`` 为 ``ui`` 下相对路径（可空 = 默认页）。

        页面跳转通过 QML 侧 ``Settings.qml::openPage()``（内部走
        ``NavigationView.push``）。用 ``QMetaObject.invokeMethod`` 调，
        因为 QML 函数不在 Python 的静态元对象里。
        """
        # 每次打开都让 QML 重取一遍设置项：``settings`` 里混着**实时状态**
        # （「开机自启」读的是注册表，用户可能在任务管理器里刚把它禁掉），
        # 而页面是按需创建、之后只隐藏不销毁的 —— 不主动刷就会显示上次的旧值。
        self._backend.refreshSettings()
        handle = self._registered_windows["settings"]
        handle.show()
        if self.settings is None:
            return
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
        self._registered_windows["settings"].hide()

    # ================================================================ 调试窗口

    def show_debug(self) -> None:
        self._registered_windows["debug"].show()

    def hide_debug(self) -> None:
        self._registered_windows["debug"].hide()

    def toggle_debug(self) -> None:
        self._registered_windows["debug"].toggle()

    def _place_beside_settings(self, window, label: str) -> None:
        """把 ``window`` 摆在设置窗口旁边，没有设置窗口就居中到光标所在显示器。

        两个窗口都是居中摆放的话会**完全重叠** —— 调试窗口 / 编辑器是从别的
        窗口里点出来的，贴边并排才符合「母子关系」的直觉。右侧放不下就翻到
        左侧；两侧都放不下（窄屏上两个窗口加起来比屏还宽，很常见）就退到
        右下角错开，至少让设置窗口露出一角。

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
        # 定位与「show 后补打亚克力」都在句柄里（注册时声明的 position /
        # post_show 钩子），这里只剩一行
        self._registered_windows["editor"].show()

    def hide_editor(self) -> None:
        self._registered_windows["editor"].hide()

    def toggle_editor(self) -> None:
        self._registered_windows["editor"].toggle()

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
        """放映开始：遮罩铺到放映窗口（全屏放映时即整屏），控制条落到各角落。

        顺序很重要：**先定屏 → 再定几何 → 再摆控制条 → 最后才谈穿透**。

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

        # 几何跟着**放映窗口**走（拿不到就退回整块显示器），见
        # :meth:`_apply_overlay_geometry`。
        self._apply_overlay_geometry(screen)
        for name in self._docks:
            self._position_dock(name)

        # 把「放映铺在哪块屏」告诉 Bridge：主界面编辑器的画布比例以它为准
        # （Bridge 自己复现不了这段判定 —— 它依赖放映窗口的**物理**显示器，
        # 见 :meth:`_presentation_screen`）。
        #
        # ⚠️ 这里推的仍是**整屏**几何，不是 ``_overlay_rect``：编辑器舞台是
        # 「屏幕舞台」（1:1 屏幕坐标系 + 屏框），全屏放映时两者本来就相等；
        # 窗口化放映时编辑器预览会比真实遮罩大一圈，这是**已知边界**，
        # 别顺手改成 ``_overlay_rect``（会连带改掉编辑器的画布与屏框）。
        geometry = screen.geometry()
        self._backend.syncPresentationScreen(
            geometry.width(), geometry.height(), screen.name(),
            float(screen.devicePixelRatio()),
        )

        self.overlay.show()
        self._overlay_ever_shown = True
        self._apply_overlay_base_styles(transparent=False)
        # 墨迹意图跨放映保留（set_ink_active）：放映开始时按它恢复墨迹窗口
        if self._ink_active:
            self._show_ink_window()
        self._assert_topmost()
        self._sync_input_mode()

        self._topmost_timer.start()
        self._watch_timer.start()
        QTimer.singleShot(0, self.reposition_all_docks)
        # 立刻按当前前景判一次「该不该露脸」：不走这一步的话，用户从别的
        # 程序里用遥控器翻页触发 stateChanged 时，控制条会白亮 200ms
        QTimer.singleShot(0, self._watch_overlay)
        # 放映窗口刚起来时会重申 z 序；等它安顿完再压一次顶并自检
        QTimer.singleShot(300, self._assert_topmost)
        QTimer.singleShot(int(self._config.get("presentation.verify_after_ms", 500)),
                          lambda: self._verify_overlay(False))

        log.info(
            "顶层窗口显示 屏幕 %s 遮罩=%s（显示器 %s），控制条 x%d",
            screen.name(), self._overlay_rect, screen.geometry(), len(self._docks),
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
        # 墨迹窗口随放映一起藏（只藏不销毁；_ink_active 意图保留到下次放映）
        self._hide_ink_window()
        self._hit_timer.stop()
        self._topmost_timer.stop()
        self._watch_timer.stop()
        self._manual_shown = False
        self._below_slideshow = 0
        # ⚠️ 必须先解除「临时隐去」：它落在 QML 的 ``suppressed`` 上，
        # 带着它藏窗口的话，下一次 show() 出来的是**整窗透明**（看着像没显示）。
        self._set_overlay_suppressed(False)
        if self.overlay is not None and self.overlay.isVisible():
            if self.overlay.isVisible():
                _set_window_region(int(self.overlay.winId()), None)
            self._last_region_rects = None
            self.overlay.hide()
        self._overlay_rect = None
        self._overlay_screen = None
        self._click_through = True

    def reposition_all_docks(self) -> None:
        for name in self._docks:
            self._position_dock(name)
        self._sync_input_mode()

    # ------------------------------------------------------- 墨迹叠加窗口
    # 2026-10-07 计划 self-ink 第 3 项。为什么墨迹要单独一只窗口：TopWindow 被
    # SetWindowRgn 裁成「只剩控制条几块」，区域外不绘制也不命中，墨迹画在它里面
    # 等于画在看不见的地方。z 序：放映窗口 < 墨迹 < （聚光灯一类叠加窗口）< TopWindow。

    def _ensure_ink_window(self) -> Optional[QQuickWindow]:
        """懒创建墨迹窗口（进程内只建一次、只藏不销毁）；失败记日志返回 None。

        与 :class:`RegisteredOverlay` 同族：**不做** RinUI 接管（全屏穿透窗口和
        RinUI 的非客户区处理会打架，理由见 ``_attach_to_rinui`` 尾段）。这里
        不走 ``register_overlay``：那套句柄自带「全屏铺光标屏 + 圆形镂空」语义，
        墨迹要的是「跟随放映窗口矩形 + 整窗穿透开关」，硬套只会两头别扭。

        QML 类型注册是幂等的（``app.ink`` 模块级旗标），application.py 先调过
        也无妨；这里补一次是为了让「先建窗口、后装配」的调用次序也不炸。
        """
        if self.ink_window is not None:
            return self.ink_window
        qml_path = UI_DIR / "ink" / "InkOverlay.qml"
        if not qml_path.exists():
            log.warning("墨迹窗口不存在，跳过: %s", qml_path)
            return None
        try:
            from . import ink as _ink

            _ink.register_qml_types()
        except Exception:
            # 墨迹是附加能力：注册失败只让墨迹不可用，不许把放映控制条带崩
            log.error("墨迹 QML 类型注册失败，墨迹不可用", exc_info=True)
            return None
        try:
            root = self._create(qml_path, {"visible": False})
        except RuntimeError as exc:
            log.error("墨迹窗口创建失败: %s（%s）", qml_path, exc)
            return None
        if root is None:
            log.error("墨迹窗口创建失败: %s", qml_path)
            return None
        self.ink_window = root
        # 窗口建出来之前调用方可能已经切过工具：补一次，别让 QML 侧停在默认值
        layer = self.ink_layer()
        if layer is not None:
            layer.setProperty("tool", self._ink_layer_tool())
            self._apply_ink_config(layer)
            # 工具卡「点空白收起」的起笔钩子（2026-10-08 自建批注）：
            # 层起笔前问一遍，有卡开着就把这一按消费成收卡（见 _dismiss_tool_cards）
            layer.card_dismiss_hook = self._dismiss_tool_cards
        return root

    def _apply_ink_config(self, layer: QQuickItem) -> None:
        """把墨迹相关配置套到层上（2026-10-07 计划 self-ink 第 8 项）。

        层是懒创建的：设置改动发生时它多半还不存在，所以建窗这一刻要从配置把
        手掌擦除参数 / 橡皮子模式补齐；运行中的改动由 application 的
        ``Config.on_change`` 再推一遍（两处读的是同一个配置源，键在
        bridge.SETTING_PATHS）。"""
        layer.setProperty("eraserMode", str(self._config.get("presentation.ink.eraser_mode", "pixel")))
        layer.setProperty("palmEraseEnabled", bool(self._config.get("presentation.ink.palm_erase", True)))
        layer.setProperty("palmThresholdMm", float(self._config.get("presentation.ink.palm_threshold_mm", 20)))

    def ink_layer(self) -> Optional[QQuickItem]:
        """墨迹窗口里的 InkLayer（按 objectName ``inkLayer`` 找）；没建 / 找不到返回 None。

        按 objectName 找而不是按类名：QML 派生类型的类名带 ``_QMLTYPE_<n>``。
        """
        window = self.ink_window
        if window is None:
            return None
        try:
            layer = window.findChild(QQuickItem, "inkLayer")
            if layer is None:
                content = window.contentItem()
                if content is not None:
                    layer = content.findChild(QQuickItem, "inkLayer")
        except RuntimeError:  # pragma: no cover - 窗口已释放
            return None
        return layer

    def set_ink_active(self, active: bool) -> None:
        """要求「放映中显示墨迹窗口」与否。

        只记意图、不强行显示：没在放映（TopWindow 没露脸）时只存 ``_ink_active``，
        等 :meth:`show_docks` 按它恢复 —— 墨迹窗口脱离放映单独挂在桌面上，
        就是一块盖住全屏的透明玻璃。
        """
        self._ink_active = bool(active)
        if not self._ink_active:
            self._hide_ink_window()
            return
        if self.overlay is None or not self.overlay.isVisible():
            return
        self._show_ink_window()

    def set_ink_tool(self, tool: str) -> None:
        """切墨迹工具：pen / eraser 整窗吃输入，其余（arrow 等）整窗穿透。

        穿透只靠加减 ``WS_EX_TRANSPARENT``（见 :meth:`_apply_ink_styles`），
        QML 侧不挂 MouseArea —— 穿透态下事件根本进不了进程。
        """
        self._ink_tool = str(tool)
        layer = self.ink_layer()
        if layer is not None:
            layer.setProperty("tool", self._ink_layer_tool())
        self._apply_ink_styles()

    def _ink_layer_tool(self) -> str:
        """交给 InkLayer 的工具名：非笔 / 橡皮一律折成 ``arrow``。

        InkLayer 只认 arrow / pen / eraser，收到别的（laser 等）会拒收并**停在
        上一个工具**（2026-10-07 实测停在 pen）—— 窗口已整窗穿透、层却还以为
        在笔态，两边状态对不上。折成 arrow 让层与穿透状态永远一致。
        """
        return self._ink_tool if self._ink_tool in INK_INPUT_TOOLS else "arrow"

    def _sync_ink_page(self, state) -> None:
        """按页墨迹（2026-10-07 计划 self-ink 第 7 项）：放映状态流驱动 InkLayer 换页。

        页键规则（用户决策 Q2：按页记忆、退出清空、不写回 PPT）：

        - 页键只认 >0 的 slide_index。放映首次同步若 COM 还没读出页码（恒 0），
          基线**待定**：先共用键 0、记一次日志；之后读到真实页码立即升级为按页
          记忆（2026-10-08 修复：窗口探测比 COM attach 快，首次同步常拿到 0，
          旧逻辑把它当单页锁死，整场翻页永不换墨迹快照）。整场都读不到页码
          （WPS 无 COM 之类）则自然等价于旧的单页退化，语义不变。
        - 基线确立之后再收到 0 一律忽略（COM 瞬时抽风不该把用户踢回空页）。
        - 同页键内的状态变化（黑屏 / 白屏 / 切换动画）不碰墨迹：页键变了才
          ``setPage``，干纹理重建在 InkLayer 里做。
        - active→False 边沿清空全部墨迹并把层拨回键 0，下次放映从干净状态开始。
          待定期间落在键 0 的墨也随退出清空（Q2「退出清空」决策不变）。
        """
        layer = self.ink_layer()
        if layer is None:
            return
        if not state.active:
            if self._ink_page_key is not None:
                # 放映中 → 退出的边沿；hide_docks 已藏窗口，这里只管清数据。
                # 退出态的状态更新可能来好几条，靠 _ink_page_key=None 只清一次。
                layer.clearAll()
                layer.setPage(0)
                self._ink_page_key = None
                self._ink_single_page_logged = False
            return
        slide = int(state.slide_index or 0)
        if self._ink_page_key is None:
            # 首次同步：确立本次放映的页键基线
            if slide > 0:
                self._ink_page_key = slide
            else:
                # COM 还没读出页码：基线待定，先共用键 0。之后读到真实页码走
                # 下面的升级分支；整场读不到就自然等价于单页退化。
                self._ink_page_key = 0
                if not self._ink_single_page_logged:
                    log.warning("COM 暂未读到页码：墨迹先落在公共页键 0（单页模式），读到真实页码后自动按页切换")
                    self._ink_single_page_logged = True
            if layer.currentPage != self._ink_page_key:
                layer.setPage(self._ink_page_key)
        elif self._ink_page_key == 0:
            # 基线待定：真实页码一到达就升级为按页记忆。待定期间落在键 0 的墨
            # 不迁页 —— 落墨时页码尚未揭晓、归属无从断定；留在键 0，退出时清空。
            if slide > 0:
                self._ink_page_key = slide
                layer.setPage(slide)
                log.info("COM 已读到页码，墨迹切换为按页记忆（页键 %s）", slide)
        elif slide > 0 and slide != self._ink_page_key:
            layer.setPage(slide)
            self._ink_page_key = slide

    def _show_ink_window(self) -> None:
        window = self._ensure_ink_window()
        if window is None:
            return
        self._apply_ink_geometry()
        if not window.isVisible():
            window.show()
        # 样式要在 show() 之后补：原生窗口首次展示时 Qt 会重新应用一遍 exstyle
        self._apply_ink_styles()
        # 墨迹刚显示时排在置顶带最上面，会盖住控制条 —— 立刻让 TopWindow 压回去
        self._assert_topmost()

    def _hide_ink_window(self) -> None:
        if self.ink_window is not None and self.ink_window.isVisible():
            self.ink_window.hide()
        # 与 hide_docks 复位 _overlay_screen 同理：下次显示重新定屏
        self._ink_screen = None

    def _apply_ink_geometry(self) -> None:
        """墨迹窗口铺到与 TopWindow **同一份** ``_overlay_rect`` 上。

        不自己再算一遍放映窗口矩形：物理↔逻辑换算、全屏吸附、多屏 DPR
        全在 :meth:`_apply_overlay_geometry` 里，两只窗口各算一份迟早对不齐
        （墨迹和控制条错位几个像素，用户会以为笔画偏了）。
        """
        window = self.ink_window
        rect = self._overlay_rect
        screen = self._overlay_screen
        if window is None or rect is None or screen is None:
            return
        if self._ink_screen is not screen:
            try:
                window.setScreen(screen)
            except Exception:  # pragma: no cover - 平台差异
                log.debug("墨迹窗口 setScreen 失败", exc_info=True)
            self._ink_screen = screen
        if window.geometry() != rect:
            window.setGeometry(rect)

    def _apply_ink_styles(self) -> None:
        """按工具加减 ``WS_EX_TRANSPARENT``，并补 ``WS_EX_NOACTIVATE``。

        ⚠️ ``WS_EX_LAYERED`` 一个 bit 都不能动（Qt 透明窗口自带，动了整窗隐形）。
        放映窗口不在前台（TopWindow 临时隐去）时强制穿透：笔态的墨迹窗口
        留在别的程序上面就是一堵吃点击的墙（聚光灯的教训）。
        """
        window = self.ink_window
        if window is None:
            return
        try:
            hwnd = int(window.winId())
        except RuntimeError:  # pragma: no cover - 窗口已释放
            return
        if not hwnd:
            return
        style = _window_ex_style(hwnd)
        new_style = style | WS_EX_NOACTIVATE
        if self._ink_tool in INK_INPUT_TOOLS and not self._suppressed:
            new_style &= ~WS_EX_TRANSPARENT
        else:
            new_style |= WS_EX_TRANSPARENT
        if new_style != style:
            _set_window_ex_style(hwnd, new_style)

    def _place_ink_below_top(self) -> None:
        """把墨迹窗口插到「TopWindow 与可见叠加窗口里最低的那只」正下方。

        用 ``SetWindowPos(ink, anchor)``（插在 anchor 之下）而不是 HWND_TOPMOST：
        后者会把墨迹顶到置顶带最上面，压住控制条和聚光灯。anchor 本身已在
        置顶带里，插在它下面墨迹仍是 TOPMOST，于是仍压得住放映窗口。
        """
        window = self.ink_window
        if window is None or not window.isVisible() or self.overlay is None:
            return
        if not hasattr(ctypes, "windll"):
            return
        try:
            ink_hwnd = int(window.winId())
            anchor = int(self.overlay.winId())
        except RuntimeError:  # pragma: no cover - 窗口已释放
            return
        if not ink_hwnd or not anchor:
            return
        for handle in self._registered_overlays.values():
            if not handle.is_visible() or handle.window is None:
                continue
            try:
                other = int(handle.window.winId())
            except RuntimeError:  # pragma: no cover
                continue
            # 现 anchor 在它之上 → 它更低，换它当 anchor（不改聚光灯与 TopWindow 的相对序）
            if other and other != anchor and _zorder_above(anchor, other):
                anchor = other
        try:
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(ink_hwnd), wintypes.HWND(anchor),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        except OSError:  # pragma: no cover
            log.debug("调整墨迹窗口 z 序失败", exc_info=True)

    # ------------------------------------------------- 遮罩跟随放映窗口 / 前台

    def _apply_overlay_geometry(self, screen: Optional[QScreen] = None) -> Optional[QRect]:
        """把遮罩摆到**放映窗口**的矩形上（拿不到就退回整块显示器）。

        2026-10-06 用户指令：「根据放映窗口的大小和位置自动调节遮罩总大小和
        位置」。全屏放映时两者本就重合，但这里做了一次**吸附**：窗口面积占到
        显示器 :data:`FULLSCREEN_SNAP_RATIO` 以上就按显示器矩形算 —— 全屏放映
        窗口常带一圈不可见边框，``GetWindowRect`` 会大出几个像素，照抄会让贴边
        距离静默偏掉。窗口化放映（PPT 的「观众自行浏览」、WPS 窗口放映）时
        遮罩就贴着那个窗口。

        返回实际生效的逻辑矩形，它同时是 :meth:`_position_dock` 的摆放基准。
        """
        if self.overlay is None:
            return None
        if screen is None:
            screen = self._presentation_screen()
        if screen is None:
            return None

        rect: Optional[QRect] = None
        # 钉了目标显示器就不跟窗口矩形走：遮罩铺满钉的那块整屏。否则窗口化
        # 放映时矩形是按放映窗口所在屏算的，贴到另一块屏上会错位。
        if self._config.get("presentation.follow_window_rect", True) and (
            self._screen_pin() is None
        ):
            rect = self._slideshow_logical_rect(screen)
        if rect is None or rect.width() <= 0 or rect.height() <= 0:
            rect = QRect(screen.geometry())

        # 先把「这只窗口属于哪块屏」告诉 Qt：多屏 / 多 DPI 时代 Window 的
        # 逻辑↔物理换算依赖它，漏了这一步窗口可能被摆到别的屏幕上。
        if self._overlay_screen is not screen:
            try:
                self.overlay.setScreen(screen)
            except Exception:  # pragma: no cover - 平台差异
                log.debug("setScreen 失败", exc_info=True)
            self._overlay_screen = screen
        if self.overlay.geometry() != rect:
            self.overlay.setGeometry(rect)
        self._overlay_rect = QRect(rect)
        return rect

    def _slideshow_native_rect(self) -> Optional[tuple[int, int, int, int]]:
        """放映窗口的**物理**矩形 ``(x, y, w, h)``；没有放映窗口返回 None。"""
        hwnd = int(self._ppt.state.window_handle or 0)
        if not hwnd:
            return None
        window = _window_rect(hwnd)
        if window is None or window[2] <= 0 or window[3] <= 0:
            return None
        monitor = monitor_rect_for_window(hwnd)
        if monitor is None:
            return window
        mon_w = max(1, monitor[2] - monitor[0])
        mon_h = max(1, monitor[3] - monitor[1])
        if (window[2] * window[3]) / float(mon_w * mon_h) >= FULLSCREEN_SNAP_RATIO:
            return (monitor[0], monitor[1], mon_w, mon_h)
        # 窗口化放映：夹进它所在的显示器，别让控制条摆到屏幕外
        left = max(monitor[0], window[0])
        top = max(monitor[1], window[1])
        right = min(monitor[2], window[0] + window[2])
        bottom = min(monitor[3], window[1] + window[3])
        if right - left <= 0 or bottom - top <= 0:
            return window
        return (left, top, right - left, bottom - top)

    def _slideshow_logical_rect(self, screen) -> Optional[QRect]:
        """放映窗口在 ``screen`` 坐标系里的逻辑矩形；拿不到返回 None。"""
        native = self._slideshow_native_rect()
        if native is None:
            return None
        return _logical_rect_from_native(screen, native)

    def _slideshow_in_foreground(self) -> bool:
        """放映窗口是否在前台（**拿不到放映窗口时恒为真**，宁可露着）。

        判据是**进程**而不是句柄：放映时演示软件常有好几只窗口（PPT 的
        「演示者视图」在前台、放映窗口在第二块屏上就是这种局面），只比句柄会把
        正常的单屏 / 双屏放映误判成「用户切走了」，控制条一闪一闪。
        """
        hwnd = int(self._ppt.state.window_handle or 0)
        if not hwnd:
            return True
        foreground = _foreground_window()
        if not foreground:
            return False              # 锁屏 / 切换途中：此刻隐去最不打扰
        if foreground == hwnd:
            return True
        pid = _window_pid(hwnd)
        return bool(pid) and pid == _window_pid(foreground)

    def _watch_overlay(self) -> None:
        """顶层窗口看护（``presentation.follow_interval_ms`` 一拍）。

        两件事：放映窗口挪动 / 缩放了 → 遮罩跟着走；放映窗口不在前台了 →
        临时隐去。以前这里什么都没有，遮罩在放映开始那一刻定死，用户把放映
        窗口拖动 / 从全屏切到窗口化之后，控制条就留在原地不跟了。
        """
        if self.overlay is None or not self.overlay.isVisible():
            return
        if self._config.get("presentation.follow_window_rect", True):
            before = self._overlay_rect
            after = self._apply_overlay_geometry()
            if before != after:
                # 尺寸 / 原点一变，控制条的**局部**坐标全变了：区域塑形的矩形集
                # 也必须整份重算（短路判据是按 rects 逐项比的，留着旧的就停在
                # 旧位置：「看不见的控制条」正是这么来的）。
                self._last_region_rects = None
                for name in self._docks:
                    self._position_dock(name)
                self._sync_input_mode()
                # 墨迹窗口与遮罩共用 _overlay_rect，放映窗口一动就跟着走
                self._apply_ink_geometry()
        # 快速切页面板的「点外部收起」—— 见 _dismiss_jump_panels。
        # ⚠️ 必须放在下面 ``_manual_shown`` 的提前 return **之前**：手动显示
        #    （托盘菜单叫出控制条）时这条路径会被跳过，面板就再也收不掉了。
        self._dismiss_jump_panels()
        # 工具卡（笔色板 / 橡皮卡）的穿透态收起同理（2026-10-08 自建批注）——
        # self 引擎笔/橡皮态下它自己跳过，那一路由 InkLayer 起笔钩子负责
        self._dismiss_tool_cards_on_leave()
        # 手动显示（托盘菜单）时不隐去：那条路径本来就没有放映窗口可依，
        # 而且用户刚点完托盘菜单，前台窗口是开始菜单 / 托盘，隐去等于白点。
        if self._manual_shown:
            return
        if self._config.get("presentation.follow_foreground", True):
            self._set_overlay_suppressed(not self._slideshow_in_foreground())

    def _dismiss_jump_panels(self) -> None:
        """光标移出控制条 → 收起「快速切页面板」（= 点外部收起）。

        QML 侧**收不到**「面板以外」的点击：区域塑形模式下那些地方是系统级穿透的
        （``WS_EX_TRANSPARENT``），事件根本进不了这个进程 —— 挂多少个 MouseArea
        都白搭。所以判据只能在 Python 侧用光标位置做，而这个看护本来
        （``_watch_overlay``，200ms 一拍）就在跑，搭车判断不必另开定时器。

        判据是控制条的 ``interactiveRect`` —— 它**已经把面板自己算进去了**
        （见 ``PresentationDock.interactiveRect`` / ``SidePager.interactiveRect``），
        所以光标落在面板上时仍算「里面」，不会自己把自己关掉。四边各放
        ``_JUMP_DISMISS_SLACK`` 的余量：面板贴边时，光标压在边缘上抖一帧就收
        会很烦。"""
        if self._suppressed:
            # 临时隐去期间内容本来就看不见（容器淡成 0），不必管；
            # 恢复显示时会重新判一次
            return
        if self.overlay is None or not self.overlay.isVisible():
            return
        cursor = QCursor.pos()
        for dock in self._docks.values():
            try:
                opened = bool(dock.property("jumpPanelOpened"))
            except (RuntimeError, TypeError):  # pragma: no cover - 组件已释放 / 没这个属性
                continue
            if not opened:
                continue
            rect = self._dock_global_rect(dock).adjusted(
                -JUMP_DISMISS_SLACK, -JUMP_DISMISS_SLACK,
                JUMP_DISMISS_SLACK, JUMP_DISMISS_SLACK)
            if not rect.contains(cursor):
                self._close_jump_panel(dock)

    def _close_jump_panel(self, dock: QQuickItem) -> None:
        """调 QML 侧 ``closeJumpPanel()`` 收起面板。

        包 try：QML 侧函数缺失 / 组件已释放只记日志 —— 这个调用点在看护定时器
        里，抛出去会把事件循环带崩。"""
        try:
            QMetaObject.invokeMethod(dock, "closeJumpPanel")
        except Exception:  # pragma: no cover - QML 侧没实现 / 对象已销毁
            log.debug("控制条缺 closeJumpPanel()", exc_info=True)

    def _dismiss_tool_cards(self) -> bool:
        """收起所有开着的工具卡（笔色板卡 / 橡皮子模式卡）；有卡被收返回 True。

        2026-10-08 用户报告：自建批注 —— 笔/橡皮的二级卡开着时点画布空白不收起。
        两个调用方共用这一条：

        * InkLayer 的起笔钩子（self 引擎笔/橡皮态，画布上的按下落在墨迹窗口）：
          返回 True 时那一按被消费成「收起卡片」、不起笔，之后的按下正常落墨；
        * :meth:`_dismiss_tool_cards_on_leave`（com 引擎等穿透态，点击进不了
          进程）：按「光标离开即收」代为调用。

        卡片开合是 QML 侧状态，关闭走 ``closeToolCards()`` —— 与 closeJumpPanel
        同一个通道，不另发明一条路。QML 缺函数 / 组件已释放只记日志：这个
        调用点在事件与定时器路径上，抛出去会把事件循环带崩。
        """
        dismissed = False
        for dock in self._docks.values():
            try:
                opened = bool(dock.property("paletteOpened")) or bool(dock.property("eraserPaletteOpened"))
            except (RuntimeError, TypeError):  # pragma: no cover - 组件已释放 / 没这个属性
                continue
            if not opened:
                continue
            try:
                QMetaObject.invokeMethod(dock, "closeToolCards")
            except Exception:  # pragma: no cover - QML 侧没实现 / 对象已销毁
                log.debug("控制条缺 closeToolCards()", exc_info=True)
            dismissed = True
        return dismissed

    def _dismiss_tool_cards_on_leave(self) -> None:
        """穿透态下的工具卡收起：光标离开控制条即收（与切页面板同一个判据、
        同一班看护）。2026-10-08 用户报告：自建批注。

        com 引擎（或放映窗口不在前台）时画布上的点击穿透到放映程序，进程内
        谁也收不到，「点空白收起」只能退化为这个轮询判据。

        ⚠️ 墨迹窗口正在吃输入（self 引擎的笔/橡皮态）时**必须跳过**：那条路上
        「第一按 = 收起卡片」由 InkLayer 的起笔钩子消费（见 _dismiss_tool_cards），
        这里再按光标位置抢收，用户把光标从卡片移向画布时卡就先关了，
        「第一按消费成收卡」的约定就永远轮不到。"""
        if self._suppressed:
            # 临时隐去期间内容本来就看不见（容器淡成 0），不必管（同切页面板）
            return
        if self.overlay is None or not self.overlay.isVisible():
            return
        window = self.ink_window
        if (window is not None and window.isVisible()
                and self._ink_tool in INK_INPUT_TOOLS):
            return
        cursor = QCursor.pos()
        for dock in self._docks.values():
            try:
                opened = bool(dock.property("paletteOpened")) or bool(dock.property("eraserPaletteOpened"))
            except (RuntimeError, TypeError):  # pragma: no cover - 组件已释放 / 没这个属性
                continue
            if not opened:
                continue
            rect = self._dock_global_rect(dock).adjusted(
                -JUMP_DISMISS_SLACK, -JUMP_DISMISS_SLACK,
                JUMP_DISMISS_SLACK, JUMP_DISMISS_SLACK)
            if not rect.contains(cursor):
                self._dismiss_tool_cards()
                return

    def _set_overlay_suppressed(self, suppressed: bool) -> None:
        """临时隐去 / 恢复遮罩（放映窗口不在前台时）。

        走 QML 侧的 ``suppressed``（容器淡出）+ **整窗穿透**，而不是 ``hide()``：
        把一只全屏分层窗口藏起来再显示会闪一帧，而这里只是「先让开」，
        淡出更合这套 Fluent 2 的动效语言。淡出期间显式打开整窗穿透 ——
        内容看不见了，但那几块命中区还在，不穿透的话会继续吃掉点击
        （点别处的窗口「没反应」就是这么来的）。
        """
        if self.overlay is None or suppressed == self._suppressed:
            return
        self._suppressed = suppressed
        try:
            self.overlay.setProperty("suppressed", bool(suppressed))
        except (RuntimeError, TypeError):  # pragma: no cover - 老组件没这个属性
            log.debug("顶层窗口缺 suppressed 属性", exc_info=True)
        if suppressed:
            self._apply_overlay_base_styles(transparent=True)
            self._click_through = True
        else:
            self._apply_overlay_base_styles(transparent=False)
            self._last_region_rects = None
            self._sync_input_mode()
        # 隐去期间墨迹窗口强制穿透，恢复时按工具复原（见 _apply_ink_styles）
        self._apply_ink_styles()
        log.info(
            "顶层窗口已%s（放映窗口%s前台）",
            "临时隐去" if suppressed else "恢复显示",
            "不在" if suppressed else "在",
        )

    def _position_dock(self, corner: str) -> None:
        """把控制条摆到遮罩容器内的对应角落。

        坐标是**遮罩局部**坐标 —— 遮罩铺在放映窗口上（``_overlay_rect``），
        全屏放映时它就是整屏矩形。

        ⚠️ 基准必须是 ``_overlay_rect``（= 放映窗口 / 整屏矩形），不能用
        ``availableGeometry()``（避开任务栏的工作区）—— 放映时任务栏被放映窗口
        整个盖住，用户眼里的基准就是屏幕边缘，而 Windows 的「工作区」在任务栏
        被盖住时**照样把它算掉**：本机实测下边比屏幕下边高 48px，于是
        「左右 20px 正常、纵向变成 68px」。Luminalium 1 也是按整屏算的
        （overlay 窗口铺满整屏 + ``bottom: 20px``）。

        窗口化放映时基准自然变成那个窗口的矩形 —— ``margin_*`` 也就成了
        「距放映窗口边缘」的距离，这正是「遮罩跟着放映窗口走」该有的样子。

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

        base = self._overlay_rect
        if base is None or base.width() <= 0 or base.height() <= 0:
            screen = self._presentation_screen()
            if screen is None:
                return
            base = screen.geometry()
        width, height = base.width(), base.height()

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
        # TopWindow 刚顶到最上：墨迹插回它（及可见叠加窗口）之下、放映窗口之上
        self._place_ink_below_top()
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
        # 临时隐去期间保持整窗穿透：控制条只是**淡成 0**，``isVisible()`` 仍是
        # True、命中矩形也都还在 —— 这里一放行，那块看不见的条又开始吃点击
        if self._suppressed:
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
        if self._suppressed:
            # 临时隐去期间只保证「整窗穿透」，不碰区域：``_assert_topmost``
            # 每 800ms 会走到这里一次，不设这道闸它会把穿透位收回去
            self._apply_overlay_base_styles(transparent=True)
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
            f"显示过={self._overlay_ever_shown} 手动={self._manual_shown} "
            f"遮罩={self._overlay_rect} 临时隐去={self._suppressed} "
            f"放映窗口前台={self._slideshow_in_foreground()}"
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
        if self._suppressed:
            return ("顶层窗口因**放映窗口不在前台**而临时隐去（这是设计行为，"
                    "切回放映窗口即自动恢复；想关掉就把 presentation.follow_foreground 设为 false）")
        if self._below_slideshow >= 3:
            return "顶层窗口被放映窗口压住了，且重申置顶无效（见上面的 z 序告警）"
        cloaked = _dwm_cloaked(int(self.overlay.winId()))
        if cloaked != 0:
            return f"顶层窗口被 DWM 披风化（cloaked={cloaked}），系统不会合成它"
        return "顶层窗口已显示且未被压住；若屏幕上看不到，属于该屏/演示程序的呈现限制"

    def _expected_native_rect(self) -> Optional[tuple[int, int, int, int]]:
        """遮罩**应该**落在的物理矩形（对照实际窗口用）。

        基准是**放映窗口**而不是显示器 —— 窗口化放映时两者本来就不是一回事，
        拿显示器当期望值会判成「位置不对」再纠正回去。**例外：钉了目标显示器
        时期望值是钉屏的整屏**（与 ``_apply_overlay_geometry`` 的钉屏分支同一份
        结论，且与遮罩当前在哪无关 —— 取 ``_overlay_rect`` 现值会让自检对
        「窗口根本没在钉屏上」失明）。2026-10-08 之前这里漏判钉屏：看护
        （200ms 一拍）刚按钉屏把遮罩搬走，置顶自检（``_assert_topmost`` 里那拍）
        又按放映窗口矩形把它 ``SetWindowPos`` 拽回来，两只定时器来回拔河 ——
        控制条在两屏之间闪，且多数时间被拽在放映窗口那屏（用户看到的
        「钉屏不生效 + 主界面闪」）。

        ⚠️ 每次**现读**放映窗口，不要用 ``_overlay_rect`` 那份最多 200ms 前的
        缓存：``_verify_overlay`` 一旦发现不符就 ``SetWindowPos`` 硬纠正，用缓存
        的话用户拖放映窗口时会被 800ms 一拍的纠正**拽回旧位置**、再由看护拉回来，
        一路抖。
        """
        pinned = self._screen_pin()
        if pinned is not None:
            return _native_window_rect_for(pinned)
        if self._config.get("presentation.follow_window_rect", True):
            native = self._slideshow_native_rect()
            if native is not None:
                return native
        if self._overlay_rect is not None and self._overlay_screen is not None:
            return _native_rect_from_logical(self._overlay_screen, self._overlay_rect)
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

    def _screen_pin(self) -> Optional[QScreen]:
        """用户在「目标显示器」里钉的那块屏；没钉（跟随放映窗口）返回 None。

        判定与 ``bridge.py::_get_presentation_screen`` 共用
        ``app/monitors.py::resolve_screen``（名称优先、索引兜底）。钉屏找不到
        同名显示器（拔掉了）时按索引语义落，索引也不中返回 None —— 调用方
        继续走跟随 / 主屏兜底，不会僵住。
        """
        return monitors.resolve_screen(
            str(self._config.get("presentation.screen_name", "") or ""),
            int(self._config.get("presentation.screen_index", -1)),
            QGuiApplication.screens(),
        )

    def _presentation_screen(self) -> Optional[QScreen]:
        """优先钉屏（配置了目标显示器），否则跟随放映窗口，最后回退主屏。

        窗口类是**物理**三角形给出的（``MonitorFromWindow`` 的 ``MONITORINFO``），
        Qt 侧则是逻辑矩形；混用会错位。这里把每块屏的逻辑矩形换算回物理再去比，
        而不是拿主屏的 DPR 去除 —— 多屏不同缩放倍率时后者会打偏到别的屏幕，
        控制条就被画到你看不见的地方去了。

        ⚠️ 2026-10-08 之前是「跟随优先、索引兜底」：放映窗口在时 ``screen_index``
        永远不生效，「固定在主显示器上」名存实亡。现在钉屏（名称或索引）先判，
        钉了就不跟窗口走；``screen_index == -1``（默认）时行为与旧版逐字节一致。
        """
        pinned = self._screen_pin()
        if pinned is not None:
            return pinned

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

        return QGuiApplication.primaryScreen()

    # ================================================================== 收尾

    def shutdown(self) -> None:
        self._destroy_splash()
        self.hide_panel()
        # 注册窗口统一清理：逐句柄隐藏并复位（含同名属性槽同步置 None）；
        # 错误报告窗口不走注册封装（见 _register_builtin_windows），单独收。
        for handle in self._registered_windows.values():
            handle.hide()
        for handle in self._registered_overlays.values():
            handle.hide()
        self.hide_error_report()
        self.hide_docks()
        self._docks.clear()
        self._components.clear()
        self.panel = None
        for handle in self._registered_windows.values():
            handle._reset()
        self._registered_overlays.clear()
        self.error_report = None
        self.overlay = None
