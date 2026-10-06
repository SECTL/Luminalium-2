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
TOOLS = Path(__file__).resolve().parent
for _path in (str(ROOT), str(TOOLS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
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
from app.slide_thumbs import SlideThumbCache, _corner_radius  # noqa: E402
from fake_slides import FakeSlideExporter, write_fake_slide  # noqa: E402

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


def _check_thumb_cache(cache) -> None:
    """缩略图缓存自己的逻辑断言（纯 Python，与 QML 无关）。

    这块以前只能靠「图上有画面」目检，而画面又只能靠真机 COM 才有 ——
    变成一个「不接 PowerPoint 就没法验」的盲区。用假导出器把队列喂满之后，
    目录管理 / 代次号保护 / 烤圆角这些纯逻辑就能在这里钉死。

    ⚠️ 自己收尾：最后重新灌满 41 张 —— 后面还要抓图，面板上不能是空的。
    """
    from PIL import Image  # noqa: PLC0415

    problems: list[str] = []

    def check(ok: bool, what: str, detail: str = "") -> None:
        print(f"[probe] {'PASS' if ok else 'FAIL'} {what}"
              + (f" — {detail}" if detail else ""))
        if not ok:
            problems.append(what)

    urls = cache.urls
    check(len(urls) == 41, "缩略图表长度 = 总页数", f"{len(urls)}")
    check(all(u.startswith("file:///") for u in urls), "每张都是 file:// URL")
    files = [Path(QUrl(u).toLocalFile()) for u in urls]
    check(all(f.exists() and f.stat().st_size > 0 for f in files), "文件真的都落盘了",
          f"例: {files[0].name}")

    # 烤圆角：角上透明、中心不透明（QML 侧没有蒙版，全靠这一步）
    with Image.open(files[0]) as img:
        check(img.mode == "RGBA", "PNG 带 alpha 通道（烤圆角的前提）", img.mode)
        if img.mode == "RGBA":
            w, h = img.size
            corner = img.getpixel((1, 1))[3]
            center = img.getpixel((w // 2, h // 2))[3]
            check(corner == 0 and center == 255,
                  "圆角已烤进 alpha（角透明 / 中心不透明）",
                  f"corner={corner} center={center} r={_corner_radius()}")

    # 同一场里状态快照每 400ms 来一次，重复 set_show 不能把已有的图冲掉
    cache.set_show(True, 41)
    check(len(cache.urls) == 41 and cache.urls[0] != "",
          "同一场里重复 set_show 不冲掉缓存")

    # 换一场 / 退出放映：表清空、目录清掉、上一场迟到的结果被丢
    old_generation = cache._generation
    cache.set_show(False, 0)
    check(cache.urls == [], "退出放映后缩略图表清零")
    cache.set_show(True, 41)
    check(cache.urls == [""] * 41, "新一场从全空开始")
    stale = cache.directory / f"{old_generation}-5-raw.png"
    stale.parent.mkdir(parents=True, exist_ok=True)
    write_fake_slide(str(stale), 5)
    cache._on_ready(5, str(stale))
    check(cache.urls[4] == "" and not stale.exists(),
          "上一场迟到的缩略图被丢弃（代次号保护）")

    # 收尾：重新灌满，后面抓图要有内容
    cache.set_show(False, 0)
    cache.set_show(True, 41)
    cache.request(1, 41, burst=41)
    check(sum(1 for u in cache.urls if u) == 41, "收尾重新灌满 41 张")

    if problems:
        print(f"[probe] 缩略图链路：失败项 {len(problems)} —— {problems}")
    else:
        print("[probe] 缩略图链路：失败项 0")


def main() -> int:
    qInstallMessageHandler(_on_qml_message)

    config = Config()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, app)
    backend.apply_state(PresentationState(active=True, slide_index=26, slide_total=41))

    # 缩略图：真 cache + 假导出器（见 tools/fake_slides.py 的说明）。
    # 面板上「空卡片 + 页码」是 L1 的加载态、不是坏了，所以这块**必须**喂上，
    # 否则探针出的图永远是加载态，看不出「像不像 L1」。
    thumbs = SlideThumbCache(FakeSlideExporter(), backend)
    backend.attach_slide_thumbs(thumbs)
    thumbs.set_show(True, 41)
    thumbs.request(1, 41, burst=41)  # 假导出器没有 COM 开销，一次投满
    _check_thumb_cache(thumbs)

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
            list_item = _find_by_name(panel, "pageJumpList")
            cells = list_item.childItems() if list_item is not None else []
            print(f"[probe] {corner} panel x={panel.x():.0f} y={panel.y():.0f} "
                  f"item={panel.property('itemWidth'):.0f}x"
                  f"{panel.property('itemHeight'):.0f} "
                  f"thumbs={panel.property('readyCount')}/"
                  f"{panel.property('total')} "
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
            if list_item is not None:
                print(f"[probe] {corner} list h={list_item.height():.0f} "
                      f"x={list_item.x():.0f} y={list_item.y():.0f} "
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

        # ⚠️ 必须挑一张**真的在视口里**的卡：单列列表展开时会把当前页滚到正中
        #    （L1 的 ``scrollIntoView(block: 'center')``），页码小的那些早被滚到
        #    视口外了 —— 点它们等于点在窗口外，``actions`` 会是空的。
        #    2026-10-06 从「5 列网格」返工成「单列」之后，这个坑当场复现过一次
        #    （写死页码 15 的旧写法直接假失败）。
        flick = _find_by_name(panel, "pageJumpFlickable")
        rect = flick.mapToScene(QPointF(0, 0)) if flick is not None else QPointF(0, 0)
        size = flick.size() if flick is not None else None
        target, cell = None, None
        for n in range(1, 42):
            item = _find_by_name(panel, f"pageJumpCell_{n}")
            if item is None:
                continue
            center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
            if size is None or (
                rect.x() <= center.x() <= rect.x() + size.width()
                and rect.y() <= center.y() <= rect.y() + size.height()
            ):
                target, cell = n, item
                break
        if cell is None:
            print(f"[probe] {corner} 面板里找不到任何可见的卡")
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
