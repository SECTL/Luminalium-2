r"""显示器枚举 —— 给「目标显示器」设置提供带厂商/型号的真实名单。

2026-10-08 用户反馈：设置里「目标显示器」只有「跟随放映窗口 / 主显示器」两项，
认不出具体是哪台显示器。参考旧版 Luminalium 1 的做法
（``webview_runner.py::get_screen_list``）：**不用 WMI / EDID 自解析**，直接读
``QScreen.manufacturer()`` / ``QScreen.model()`` —— Qt 在 Windows 上就是从
EDID（``WmiMonitorID`` 同源数据）里解出这两个字段的，省掉 ctypes/WMI 那一整套
易错链路，还能跨平台。

几个刻意的选择：

* **稳定 id 用 ``QScreen.name()``**（Windows 上是 ``\\.\DISPLAY2`` 这类设备名
  或 EDID 型号串，随 Qt 版本而定）：枚举顺序会随热插拔 / 驱动重排，按索引存
  配置不可靠；这个名字跟着物理接口走。Luminalium 1 存的也是这个 key。
* **显示名 = 厂商 + 型号**（如 ``DELL U2720Q``）；两者都读不到时留空串，
  由 QML 侧翻成「显示器 N」（回退文案是界面文案，要走 ``qsTr``，不能在
  Python 侧写死中文）。
* **同名去重**：两台同型号显示器标签一样时追加设备名（``DELL U2720Q
  (\\.\DISPLAY3)``），照搬 Luminalium 1 ``settings.html::updateScreenList``
  的 ``nameCounts`` 逻辑 —— 不然下拉里两项长得一模一样，选了等于没选。
* **懒枚举 + 缓存**：枚举本身只是读 Qt 已缓存的 EDID 字段，代价可忽略；
  缓存只是为了不给每次属性求值都重建列表。显示器热插拔时由调用方
  （``bridge.py`` 接 ``screenAdded`` / ``screenRemoved``）调
  :func:`invalidate` 作废缓存。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

#: 枚举结果缓存；None = 还没枚举过（或刚被 :func:`invalidate` 作废）。
_cache: Optional[List[Dict[str, Any]]] = None


def _clean(text: str) -> str:
    """剥掉 EDID 字符串里的 NUL 与首尾空白（Luminalium 1 同款处理）。"""
    return (text or "").replace("\x00", "").strip()


def enumerate_monitors() -> List[Dict[str, Any]]:
    """枚举当前接入的显示器。

    每项::

        {"name": "\\\\.\\DISPLAY2",   # 稳定 id（QScreen.name()）
         "label": "DELL U2720Q",      # 厂商+型号；读不到 EDID 时为 ""
         "primary": True}             # 是否主显示器

    需要在 ``QGuiApplication`` 存在之后调用；没有 QGuiApplication（比如纯
    脚本上下文）时返回空表，由调用方兜底。
    """
    global _cache
    if _cache is not None:
        return list(_cache)

    monitors: List[Dict[str, Any]] = []
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        screens = list(app.screens()) if app is not None else []
        primary = app.primaryScreen() if app is not None else None
    except Exception:  # pragma: no cover - Qt 尚未就绪
        log.debug("显示器枚举失败（QGuiApplication 未就绪）", exc_info=True)
        screens, primary = [], None

    for screen in screens:
        manufacturer = _clean(screen.manufacturer())
        model = _clean(screen.model())
        label = f"{manufacturer} {model}".strip()
        monitors.append(
            {
                "name": _clean(screen.name()),
                "label": label,
                "primary": bool(primary is not None and screen == primary),
            }
        )

    # 同名去重：标签撞车时追加设备名（见模块 docstring）
    counts: Dict[str, int] = {}
    for item in monitors:
        if item["label"]:
            counts[item["label"]] = counts.get(item["label"], 0) + 1
    for item in monitors:
        if item["label"] and counts.get(item["label"], 0) > 1 and item["name"]:
            item["label"] = f"{item['label']} ({item['name']})"

    _cache = monitors
    return list(monitors)


def invalidate() -> None:
    """作废缓存（显示器热插拔后由 ``bridge.py`` 的信号槽调用）。"""
    global _cache
    _cache = None


def resolve_screen(name: str, index: int, screens: list):
    """按配置挑显示器：钉屏名称优先，其次旧索引语义，都不命中返回 ``None``。

    ``name`` 是 ``presentation.screen_name``（``QScreen.name()``，空串 = 未钉），
    ``index`` 是 ``presentation.screen_index``（-1 = 跟随放映窗口，不在此解析）。
    调用方拿到 ``None`` 后自行决定兜底（跟随放映窗口 / 主屏）。

    抽成共享函数是因为 ``bridge.py::_get_presentation_screen`` 与
    ``windows.py::_presentation_screen`` 必须按**同一份**优先级解析，
    各写一份迟早会漂移（2026-10-08）。
    """
    if name:
        for screen in screens:
            if screen.name() == name:
                return screen
        # 钉的那台被拔掉了：落到索引语义，而不是僵在「找不到」上
    if 0 <= index < len(screens):
        return screens[index]
    return None
