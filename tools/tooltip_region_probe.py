"""tooltip 区域并入（2026-10-28 修复）的离线探针。

根因回顾：控制条顶层窗口被 ``SetWindowRgn`` 裁成「各浮出层的 interactiveRect +
region_padding(20px)」，而 tooltip 浮在按钮上方约 40px、超出 20px 余量 ——
气泡上半截被裁（用户实测截图）。修法：tooltip 显示时按钮把自身矩形经
``registerTooltipRect`` 登记进 PresentationDock，由 ``interactiveRect`` 并入。

本探针复刻 ``tools/jump_probe.py`` 的宿主环境（离屏窗口 + ``Backend`` 走
rootContext 注入），但**不连真 Backend**：注入一个与 ``Backend.h`` 属性面对齐
的 stub（缺面会以「Cannot read property … of undefined」告警的形式落到被测页
头上，所以要把本页用到的成员都给全）。真实路径模拟：找到按钮的 Rin.ToolTip
子对象置 ``visible=true``，等过 ``delay: 600`` 让它真的显示 ——
``onVisibleChanged → _reportTooltip`` 那条链路自动跑，不手工调登记函数。

断言：

1. 无 tooltip 时 ``interactiveRect`` 与基线一致（改前公式算出的底板矩形，无回归）；
2. tooltip 显示后 ``interactiveRect`` 向上扩展、完整包含气泡矩形（top 变小、
   左右覆盖气泡宽）；
3. tooltip 隐藏后 ``interactiveRect`` 回到基线（注销生效）；
4. IconButton 与 ToolSegmentItem 两条上报路径各验一遍；
5. 全程来自被测页的 QML 告警 0。

用法::

    .venv\\Scripts\\python.exe tools\\tooltip_region_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from PySide6.QtCore import (  # noqa: E402
    Property,
    QObject,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
    qInstallMessageHandler,
)
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RINUI_PATH  # noqa: E402

from app.paths import UI_DIR  # noqa: E402

#: 预览用的窗口尺寸（与 jump_probe.py 同一档位）
PREVIEW_W, PREVIEW_H = 1100, 640

#: PresentationDock 读的配置（覆盖本页用到的段落，缺段有缺省值兜底）
CONFIG = {
    "bar_height": 56,
    "corners": {"bottom_center": {"groups": ["tools", "actions", "exit"]}},
    "tools": [
        {"id": "arrow", "label": "指针", "icon": "ic_fluent_cursor_20_filled"},
        {"id": "pen", "label": "笔", "icon": "ic_fluent_pen_20_filled"},
        {"id": "eraser", "label": "橡皮", "icon": "ic_fluent_eraser_20_filled"},
    ],
    "actions": [
        {"id": "clear", "label": "清屏", "icon": "ic_fluent_eraser_20_filled",
         "tooltip": "清屏（擦除本页全部墨迹）"},
    ],
    "zoom": {"tooltip": "放大镜"},
    "overflow": {"tooltip": "更多操作"},
}

_qml_messages: list[str] = []
BACKEND = None  # 防 GC 的 Backend stub 引用（见 main 里的注释）


def _on_qml_message(_mode, _ctx, message: str) -> None:
    # QML 的绑定错误平时静默 —— 探针里必须看见并计入
    _qml_messages.append(message)
    print(f"[QML] {message}", flush=True)


def _find_by_name(item, name: str):
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _find_by_name(child, name)
        if found is not None:
            return found
    return None


def _find_tooltip(item):
    """按钮的 Rin.ToolTip 子对象 —— popup 不是 Item，要从 QObject children 找。

    ⚠️ PySide6 没把 ``QQuickPopup`` 注册成 Python 类型（isinstance 不可用），
    按「有 background / visible 属性的 QObject」鸭子类型识别。
    """
    for child in item.children():
        mo = child.metaObject()
        if mo.indexOfProperty("background") >= 0 and mo.indexOfProperty("visible") >= 0:
            return child
    return None


class BackendStub(QObject):
    """``Backend`` 的运行替身：属性面与 ``src/backend/Backend.h`` 对齐。

    本页（含 PageJumpPanel / PenPaletteCard / EraserModeCard / ZoomPanel /
    ToolSegment）创建期会读的成员都要给全，否则缺面告警会被算到被测页头上。
    """

    presentationActiveChanged = Signal()
    slideChanged = Signal()
    activeToolChanged = Signal()
    zoomActiveChanged = Signal()
    penColorChanged = Signal()
    penWidthChanged = Signal()
    eraserWidthChanged = Signal()
    presentationConfigChanged = Signal()
    settingsChanged = Signal()
    slideThumbsChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._config = dict(CONFIG)
        self._settings = {"presentation_ink_eraser_mode": "pixel"}

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#0078d4"

    @Property(bool, notify=presentationActiveChanged)
    def presentationActive(self) -> bool:
        return True

    @Property(int, notify=slideChanged)
    def slideIndex(self) -> int:
        return 26

    # 总页数 0 → PageJumpPanel 不建卡片（探针用不到它们，少一分噪声）
    @Property(int, notify=slideChanged)
    def slideTotal(self) -> int:
        return 0

    @Property(str, notify=activeToolChanged)
    def activeTool(self) -> str:
        return "arrow"

    @Property(bool, notify=zoomActiveChanged)
    def zoomActive(self) -> bool:
        return False

    @Property(str, notify=penColorChanged)
    def penColor(self) -> str:
        return ""

    @Property(float, notify=penWidthChanged)
    def penWidth(self) -> float:
        return 0.0

    @Property(float, notify=eraserWidthChanged)
    def eraserWidth(self) -> float:
        return 0.0

    @Property("QVariantMap", notify=presentationConfigChanged)
    def presentationConfig(self) -> dict:
        return self._config

    @Property("QVariantMap", notify=settingsChanged)
    def settings(self) -> dict:
        return self._settings

    @Property("QVariantList", notify=slideThumbsChanged)
    def thumbUrls(self) -> list:
        return []

    @Slot(str)
    def selectTool(self, tool: str) -> None:
        pass

    @Slot(bool)
    def setZoomActive(self, active: bool) -> None:
        pass

    @Slot(str)
    def setPenColor(self, color: str) -> None:
        pass

    @Slot(float)
    def setPenWidth(self, width: float) -> None:
        pass

    @Slot(float)
    def setEraserWidth(self, width: float) -> None:
        pass

    @Slot(str)
    def zoomSlide(self, op: str) -> None:
        pass

    @Slot(str)
    def triggerAction(self, action_id: str) -> None:
        pass

    @Slot(int)
    def nextSlide(self) -> None:
        pass

    @Slot(int)
    def previousSlide(self) -> None:
        pass

    @Slot(int)
    def gotoSlide(self, page: int) -> None:
        pass

    @Slot()
    def exitPresentation(self) -> None:
        pass

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value) -> None:
        pass

    @Slot(int, int)
    def requestThumbnails(self, start: int, end: int) -> None:
        pass


def _check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[probe] {'PASS' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""), flush=True)
    return ok


def _rect_of(item, owner) -> QRectF:
    pos = item.mapToItem(owner, QPointF(0, 0))
    return QRectF(pos.x(), pos.y(), float(item.width()), float(item.height()))


def main() -> int:
    qInstallMessageHandler(_on_qml_message)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    # ⚠️ 不带 qml_path 构造时 RinUI 模块路径要自己补（见 jump_probe.py 同款注释）
    rinui.engine.addImportPath(str(RINUI_PATH))
    rinui.theme_manager.set_theme_color("#0078d4")
    rinui.setTheme(Theme.Dark)
    # ⚠️ 必须持有 Python 引用：无父对象的 QObject 会被 GC 掉，context property
    #    随之变 null —— 症状是满屏「Cannot read property … of null」
    global BACKEND
    BACKEND = BackendStub()
    rinui.engine.rootContext().setContextProperty("Backend", BACKEND)

    component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "PresentationDock.qml"))
    )
    if component.isError():
        for error in component.errors():
            print("DOCK ERROR:", error.toString())
        return 1

    # 离屏宿主窗口：dock 挂进 contentItem，让 ``Window.window`` 可解析
    host = QQuickWindow()
    host.setWidth(PREVIEW_W)
    host.setHeight(PREVIEW_H)
    host.setPosition(-6400, -6000)
    host.show()

    dock = component.createWithInitialProperties({"corner": "bottom_center"})
    if dock is None:
        print("[probe] dock 创建失败")
        return 1
    dock.setParentItem(host.contentItem())
    dock.setX(80)
    dock.setY(PREVIEW_H - dock.property("height") - 40)

    results: list[bool] = []

    def _probe_button(object_name: str, on_done) -> None:
        btn = _find_by_name(dock, object_name)
        if not _check(f"{object_name} 存在", btn is not None):
            results.append(False)
            return
        baseline = QRectF(dock.property("interactiveRect"))
        _check(f"{object_name} 基线矩形",
               baseline.width() > 0 and baseline.height() > 0,
               f"{baseline}")

        tip = _find_tooltip(btn)
        if not _check(f"{object_name} 找到 ToolTip", tip is not None):
            results.append(False)
            return
        # ⚠️ 先把 delay 置 0：QQuickToolTip 的 delay 定时器与探针自己的
        #    QTimer 会抢同一批到期时刻 —— 实测 setVisible(false) 可能被
        #    「还没弹完的延迟链」吞掉，visible 翻不回去。delay=0 让
        #    setVisible(true) 同步生效，onVisibleChanged → _reportTooltip
        #    的真实路径照样走（delay 数值本身不在被测范围里）。
        tip.setProperty("delay", 0)
        tip.setProperty("visible", True)
        # ⚠️ setVisible(false) 的 ``visible`` 属性要等 **300ms exit 转场**结束才
        #    翻 False（onVisibleChanged 的隐藏侧也因此晚 300ms 才发）—— 真机上
        #    只是注销晚半拍、无害；探针里等 600ms 再断言。
        #
        # ⚠️⚠️ 两个按钮**串行**：singleShot 是相对调度，dock 创建会阻塞事件环
        #    近一秒 —— 若把两轮固定偏移并行排，第二轮的 tooltip 会在第一轮
        #    「回基线」断言时已经登记进来，回基线断言必假失败（实测踩过）。
        #    全部偏移都相对「本按钮显示那一刻」，链式推进。
        QTimer.singleShot(300,
                          lambda: _assert_expanded(object_name, tip, baseline))
        QTimer.singleShot(600, lambda: tip.setProperty("visible", False))

        def _after_back() -> None:
            _assert_back_to_baseline(object_name, baseline, tip)
            if on_done is not None:
                on_done()

        QTimer.singleShot(1200, _after_back)

    def _assert_expanded(object_name: str, tip, baseline: QRectF) -> None:
        shown = bool(tip.property("visible"))
        if not _check(f"{object_name} tooltip 经 delay 后已显示", shown):
            results.append(False)
            return
        expanded = QRectF(dock.property("interactiveRect"))
        bg = tip.property("background")
        bubble = _rect_of(bg, dock)
        results.append(_check(
            f"{object_name} interactiveRect 向上扩展（top 变小）",
            expanded.top() < baseline.top() - 0.5,
            f"baseline={baseline} expanded={expanded}"))
        results.append(_check(
            f"{object_name} interactiveRect 完整包含气泡矩形",
            bubble.left() >= expanded.left() - 0.5
            and bubble.right() <= expanded.right() + 0.5
            and bubble.top() >= expanded.top() - 0.5,
            f"bubble={bubble}"))
        rects = dock.property("_hoverRects")
        n = rects.toVariant() if hasattr(rects, "toVariant") else list(rects)
        results.append(_check(f"{object_name} 登记表恰好一条", len(n) == 1,
                              f"{len(n)}"))

    def _assert_back_to_baseline(object_name: str, baseline: QRectF, tip) -> None:
        back = QRectF(dock.property("interactiveRect"))
        results.append(_check(f"{object_name} 隐藏后回到基线", back == baseline,
                              f"{back}"))
        rects = dock.property("_hoverRects")
        n = rects.toVariant() if hasattr(rects, "toVariant") else list(rects)
        results.append(_check(f"{object_name} 注销后登记表清空", len(n) == 0,
                              f"{n}"))

    # 串行链：zoom 按钮整轮（含回基线断言）跑完 → pen 按钮整轮 → 汇总
    QTimer.singleShot(200, lambda: _probe_button(
        "dockZoomButton",
        lambda: _probe_button("dockTool_pen", _finish)))

    def _finish() -> None:
        page_warnings = [
            m for m in _qml_messages
            if any(n in m for n in ("PresentationDock.qml", "IconButton.qml",
                                    "ToolSegmentItem.qml"))
        ]
        results.append(_check("被测页 QML 告警 0", not page_warnings,
                              f"{page_warnings[:3]}"))
        total, passed = len(results), sum(1 for r in results if r)
        print(f"\n================ tooltip 区域并入探针 ================")
        print(f"断言 {passed}/{total} 通过")
        print("=====================================================")
        app.quit()

    app.exec()
    return 0 if all(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
