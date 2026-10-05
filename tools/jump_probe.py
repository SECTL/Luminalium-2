"""``PageJumpPanel`` 的独立探针 —— 复刻 ``preview.py`` 的宿主环境，几秒出图 + 验交互。

为什么值得单独开一个：完整预览（``preview.py``）一轮要几分钟，而这块面板要调的
是**几何**（列数 / 卡片高度 / 滚动位置），看一眼图就知道对错。探针只建
``TopWindow`` + 竖版翻页条，把面板展开后直接 ``grabWindow`` 写 PNG。

宿主刻意照抄 ``preview.py``（离屏 + ``Qt.Tool`` 透明顶层窗口 + ``Backend`` 走
rootContext 注入），所以复现的就是预览里那个环境。它同时把 QML 侧的
console / 警告转发出来（``[QML] ...``）—— QML 里的绑定错误平时是静默的。

用法::

    .venv\\Scripts\\python.exe tools\\jump_probe.py
    # 图写在 <项目>/preview/probe_jump.png

环境变量：

* ``LUMI_PROBE_CORNERS=middle_left`` —— 只建一侧（默认 ``middle_left,middle_right``）。
  测单侧几何时必须这么用：两个面板看得见的那块会盖住另一块，断言会串味。
* ``LUMI_PROBE_NOWATERMARK=1`` —— 关掉左下角的**开发水印**。⚠️ 水印正好画在左
  翻页条那一侧，会盖住面板最底下一行数字，看起来活像「面板被裁了一行」；排查
  这块面板时第一件事就是把它关掉。
* ``LUMI_PROBE_OFFSCREEN=0`` —— 把窗口摆到**屏幕内**真实渲染（默认离屏）。
  用来分清真画错了 vs 离屏抓图的假象。

跑完会打印三组东西：几何诊断、图路径、以及一行**交互结论** ——
「点页码 → 展开 / 点一格 → 发 ``pager:goto:N`` / 跳完收起」。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import (  # noqa: E402
    QPoint,
    QPointF,
    Qt,
    QTimer,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RINUI_PATH  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402

#: 预览用的紧凑尺寸（与 preview.py 同一个档位）
PREVIEW_W, PREVIEW_H = 1100, 640


def _on_qml_message(_mode, _ctx, message: str) -> None:
    # QML 的绑定错误平时静默 —— 探针里必须看见
    print(f"[QML] {message}", flush=True)


def _find_by_name(item, name: str):
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _find_by_name(child, name)
        if found is not None:
            return found
    return None


def main() -> int:
    qInstallMessageHandler(_on_qml_message)

    config = Config()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, app)
    backend.apply_state(PresentationState(active=True, slide_index=26, slide_total=41))

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    # ⚠️ ``RinUIWindow(qml_path)`` 才顺手加 RinUI 自己的模块路径；不带路径构造时
    #    得自己补，否则 ``import RinUI`` 直接报 module is not installed。
    rinui.engine.addImportPath(str(RINUI_PATH))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent")))
    rinui.setTheme(Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)

    top_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "TopWindow.qml"))
    )
    side_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "SidePager.qml"))
    )
    for name, comp in (("TOP", top_component), ("SIDE", side_component)):
        if comp.isError():
            for error in comp.errors():
                print(f"{name} ERROR:", error.toString())
            return 1

    top = top_component.createWithInitialProperties({"visible": True})
    top._probe_top = top_component
    top.setWidth(PREVIEW_W)
    top.setHeight(PREVIEW_H)
    # ⚠️ 实验开关：``LUMI_PROBE_OFFSCREEN=0`` 时把窗口摆到**屏幕内真实渲染**，
    #    用来区分「真的画错了」和「离屏 grabWindow 的假象」。
    if os.environ.get("LUMI_PROBE_OFFSCREEN", "1") not in ("", "0"):
        top.setPosition(-6400, -6000)
    else:
        top.setPosition(120, 120)
    top.show()

    docks = {}
    panels = {}

    def _setup() -> None:
        container = top.property("container")
        margin_x, margin_y = 20, 20
        # 默认两侧都建；``LUMI_PROBE_CORNERS=middle_left`` 只建一侧 —— 只测一侧
        # 才能排除「两块面板互相遮挡」这种假象（重叠时看得见的那块会骗人）。
        corners = [c.strip() for c in
                   os.environ.get("LUMI_PROBE_CORNERS", "middle_left,middle_right").split(",")
                   if c.strip()]
        for corner in corners:
            dock = side_component.createWithInitialProperties({"corner": corner})
            dock._probe_side = side_component
            dock.setParentItem(container)
            shadow = float(dock.property("shadowMargin") or 0)
            if corner.endswith("left"):
                dock.setX(margin_x - shadow)
            else:
                dock.setX(PREVIEW_W - dock.width() - margin_x + shadow)
            dock.setY((PREVIEW_H - dock.height()) // 2)
            docks[corner] = dock
            panel = _find_by_name(dock, "sidePageJumpPanel")
            if panel is None:
                print(f"[probe] {corner} 找不到面板")
                continue
            panels[corner] = panel
            panel.setProperty("animate", False)
            panel.setProperty("opened", True)

    def _hide_watermark() -> None:
        """关掉左下角的**开发水印**。

        ⚠️ 这块水印就画在左下角，正是左翻页条那一侧 —— 它的两行文字会盖住面板
        最底下一行，看起来活像「面板被裁了一行」（2026-10-06 排查了半天，根因
        就是它；右侧面板没被遮，于是左右一对比更像个 bug）。"""
        wm = top.property("watermarkItem")
        if wm is not None:
            wm.setVisible(False)
            print("[probe] 开发水印已关")

    def _report() -> None:
        for corner, panel in panels.items():
            flick = _find_by_name(panel, "pageJumpFlickable")
            grid = _find_by_name(panel, "pageJumpGrid")
            cells = grid.childItems() if grid is not None else []
            print(f"[probe] {corner} panel x={panel.x():.0f} y={panel.y():.0f} "
                  f"card={panel.property('cardWidth'):.0f}x"
                  f"{panel.property('cardHeight'):.0f} "
                  f"rows={panel.property('rows')} cols={panel.property('effColumns')} "
                  f"scroll={panel.property('scrollable')}")
            if flick is not None:
                print(f"[probe] {corner} flick h={flick.height():.0f} "
                      f"contentH={flick.property('contentHeight'):.0f} "
                      f"contentY={flick.property('contentY'):.0f}")
            card = _find_by_name(panel, "pageJumpCard")
            if card is not None:
                print(f"[probe] {corner} cardItem x={card.x():.0f} y={card.y():.0f} "
                      f"w={card.width():.0f} h={card.height():.0f} "
                      f"vis={card.isVisible()}")
            print(f"[probe] {corner} panelItem w={panel.width():.0f} "
                  f"h={panel.height():.0f} vis={panel.isVisible()}")
            if grid is not None:
                print(f"[probe] {corner} grid h={grid.height():.0f} "
                      f"x={grid.x():.0f} y={grid.y():.0f} "
                      f"cells={len(cells)}")
            # 逐格看最后几格：位置 / 尺寸 / 有效可见性（``Item.visible`` 是
            # 「有效可见性」，祖先不可见时读出来也是 False —— 图上不画的那一格
            # 到底是被裁了还是被藏了，这里一眼就能分开）
            for n in (36, 40, 41):
                cell = _find_by_name(panel, f"pageJumpCell_{n}")
                if cell is None:
                    print(f"[probe] {corner} cell{n} 不存在")
                    continue
                mapped = cell.mapToItem(panel, QPointF(0, 0))
                print(f"[probe] {corner} cell{n} y={cell.y():.0f} "
                      f"h={cell.height():.0f} w={cell.width():.0f} "
                      f"mapY={mapped.y():.0f} vis={cell.isVisible()} "
                      f"op={cell.property('opacity')}")

    # 额外窗口：preview.py 里在同一进程建了 settings / splash / debug / editor /
    # 一组设置页宿主窗，而探针里只有 TopWindow。怀疑「多窗口」才是预览里那块面板
    # 被裁的理由，所以这里补几个同样离屏的普通窗口来复现（QQuickWindow 就够，
    # 不需要真的加载那些页面）。
    extra_windows = []

    def _add_extra_windows() -> None:
        from PySide6.QtQuick import QQuickWindow  # noqa: PLC0415

        for i in range(4):
            win = QQuickWindow()
            win.setWidth(900 + i * 20)
            win.setHeight(700)
            win.setPosition(-6400 - i * 1200, -6000)
            win.show()
            extra_windows.append(win)
        print(f"[probe] 额外建了 {len(extra_windows)} 个窗口")

    def _shoot() -> None:
        image = top.grabWindow() if hasattr(top, "grabWindow") else None
        if image is not None and not image.isNull():
            out = ROOT / "preview" / "probe_jump.png"
            image.save(str(out))
            print(f"[probe] 图 -> {out} {image.width()}x{image.height()}")

    # ------------------------------------------------------------ 交互链路
    # 「点页码 → 展开面板 → 点一格 → 跳页并收起」是这个功能**唯一值得自动化**
    # 的部分：几何可以看图，但「点了有没有反应」只能靠真投递事件。
    # ``QTest`` 直接往窗口投事件、不走 Win32 命中测试，所以离屏窗口照样点得到
    # （与 ``smoke.py::_click_dock_item`` 同一套做法）。
    actions: list[str] = []

    def _click(item) -> None:
        center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        QTest.mouseClick(top, Qt.LeftButton, Qt.NoModifier,
                         QPoint(int(round(center.x())), int(round(center.y()))))
        QTest.qWait(120)

    def _verify_interaction() -> None:
        backend.actionTriggered.connect(lambda a: actions.append(a))
        # 只验一个角落：两个面板重叠时点击会落到上面那块，断言会串味
        corner, panel = next(iter(panels.items()))
        hit = _find_by_name(docks[corner], "sidePagerHit")
        if hit is None:
            print(f"[probe] {corner} 找不到页码热区（sidePagerHit）")
            return
        # 抓图那一轮已经把面板打开了，先收起来 —— 要验的是「点一下才展开」
        panel.setProperty("opened", False)
        QTest.qWait(80)

        _click(hit)
        opened = bool(panel.property("opened"))

        target = 15
        cell = _find_by_name(panel, f"pageJumpCell_{target}")
        if cell is None:
            print(f"[probe] {corner} 面板里找不到第 {target} 格")
            return
        actions.clear()
        _click(cell)
        closed_again = not bool(panel.property("opened"))

        print(f"[probe] 交互：点页码→展开={'OK' if opened else 'FAIL'}  "
              f"点第{target}格→{'OK' if f'pager:goto:{target}' in actions else 'FAIL'}"
              f"(actions={actions})  "
              f"跳完收起={'OK' if closed_again else 'FAIL'}")

    QTimer.singleShot(300, _setup)
    if os.environ.get("LUMI_PROBE_NOWATERMARK", "") not in ("", "0"):
        QTimer.singleShot(450, _hide_watermark)
    QTimer.singleShot(500, _add_extra_windows)
    QTimer.singleShot(900, _report)
    QTimer.singleShot(1200, _shoot)
    QTimer.singleShot(1600, _verify_interaction)
    QTimer.singleShot(2200, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
