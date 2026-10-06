#!/usr/bin/env python
"""量设置页版式：把一棵 QML 子树里所有具名项的坐标/尺寸打出来（逻辑坐标）。

用途：目检 ``page_*.png`` 时发现「某两处之间空了一大片 / 某块贴太近」，
光看图分不清是「本来就这样」还是「有个控件塌陷/撑高了」。这里直接读 QML 树。

用法::

    python tools/measure_page.py <页面文件> [--names a,b,c] [--all]

默认打印 ``--names`` 给的项（相对页面根的 x/y/宽/高）+ 页面根的
``contentItem`` 高度，省得跟无关项混在一起。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from RinUI import RinUIWindow  # noqa: E402

OFFSCREEN = -6000
HOST_QML = """import QtQuick
import RinUI as Rin

Rin.Window {
    id: host
    property url pageUrl: ""
    width: 961
    height: 940
    titleBarHeight: 0
    titleEnabled: false
    closeVisible: false
    minimizeVisible: false
    maximizeVisible: false
    flags: Qt.Tool | Qt.FramelessWindowHint

    Loader {
        anchors.fill: parent
        anchors.margins: 16
        source: host.pageUrl
    }
}
"""


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def _walk_depth(item, depth: int = 0):
    yield depth, item
    for child in item.childItems():
        yield from _walk_depth(child, depth + 1)


def pump(app, ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    QCoreApplication.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("page", help="相对仓库根或绝对路径的 QML 文件")
    parser.add_argument("--names", default="", help="要打印的 objectName，逗号分隔")
    parser.add_argument("--all", action="store_true", help="打印所有具名项")
    parser.add_argument("--texts", action="store_true",
                        help="打印所有 Text 节点（文字/可见/颜色/映射坐标），"
                             "用来查「树里说可见、图上却没字」")
    parser.add_argument("--under", default="",
                        help="配合 --texts：只看这个 objectName 子树里的文字")
    parser.add_argument("--tree", action="store_true",
                        help="把 --under 那棵子树逐层打出来（类型/可见/几何），"
                             "用来查「谁把谁藏了」")
    parser.add_argument("--prop", action="append", default=[],
                        help="读任意属性，格式 objectName,属性名（可重复）。"
                             "读不到会打成 <无此属性>，不会中断")
    parser.add_argument("--wait", type=int, default=900, help="抓之前等多久(ms)")
    parser.add_argument(
        "--set", action="append", default=[],
        help="加载后设属性，格式 objectName,prop,value（可重复）。"
             "用来把页面切到某个状态再量，例如 updateTabs,currentIndex,1",
    )
    args = parser.parse_args()

    page_path = Path(args.page)
    if not page_path.is_absolute():
        page_path = ROOT / page_path
    wanted = [n.strip() for n in args.names.split(",") if n.strip()]

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = Config()
    backend = Backend(config, app)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(ROOT / "ui"))
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(ROOT / "ui" / "QuickPanel.qml")
    rinui.root_window.setPosition(OFFSCREEN, OFFSCREEN)
    rinui.root_window.show()

    host_path = ROOT / "preview" / "_measure_page_host.qml"
    host_path.write_text(HOST_QML, encoding="utf-8")
    component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(host_path)))
    if component.isError():
        for error in component.errors():
            print("HOST ERROR:", error.toString())
        return 1
    window = component.createWithInitialProperties({
        "pageUrl": QUrl.fromLocalFile(str(page_path)),
        "visible": True,
    })
    if window is None:
        print("WINDOW CREATE ERROR")
        return 1
    window._host_component = component
    window.setPosition(OFFSCREEN - 900, OFFSCREEN - 1800)
    window.show()
    pump(app, args.wait)

    page = window.contentItem()

    # 先按 --set 把页面摆到目标状态（例如切 Tab），再等一拍让它收敛
    if args.set:
        for spec in args.set:
            parts = spec.split(",")
            if len(parts) != 3:
                print(f"[WARN] --set 只认 objectName,prop,value，收到 {spec!r}")
                continue
            target_name, prop, raw = (p.strip() for p in parts)
            target = next((n for n in walk(page) if n.objectName() == target_name), None)
            if target is None:
                print(f"[WARN] --set 找不到 {target_name!r}")
                continue
            value: object = raw
            if raw.lstrip("-").isdigit():
                value = int(raw)
            elif raw.lower() in ("true", "false"):
                value = raw.lower() == "true"
            target.setProperty(prop, value)
            print(f"[SET] {target_name}.{prop} = {value!r}")
        pump(app, 1200)

    print(f"page root objectName={page.objectName()!r} "
          f"w={float(page.property('width')):.1f} h={float(page.property('height')):.1f}")
    print(f"{'objectName':38} {'x':>8} {'y':>8} {'w':>8} {'h':>8} {'vis':>5}")

    emitted = set()
    for node in walk(page):
        name = node.objectName()
        if not name:
            continue
        if not args.all and name not in wanted:
            continue
        key = (name, id(node))
        if key in emitted:
            continue
        emitted.add(key)
        pos = node.mapToItem(page, 0, 0)
        try:
            vis = bool(node.property("visible"))
        except Exception:
            vis = None
        print(f"{name:38} {pos.x():8.1f} {pos.y():8.1f} "
              f"{float(node.property('width')):8.1f} "
              f"{float(node.property('height')):8.1f} {str(vis):>5}")

    if args.prop:
        print()
        print("--- 指定属性 ---")
        for spec in args.prop:
            parts = [p.strip() for p in spec.split(",")]
            if len(parts) != 2:
                print(f"[WARN] --prop 只认 objectName,属性名，收到 {spec!r}")
                continue
            target_name, prop = parts
            target = next((n for n in walk(page)
                           if n.objectName() == target_name), None)
            if target is None:
                print(f"{target_name}.{prop} = <找不到该项>")
                continue
            try:
                value = target.property(prop)
            except Exception as exc:      # 枚举之类 Python 读不了
                print(f"{target_name}.{prop} = <读不了: {exc}>")
                continue
            print(f"{target_name}.{prop} = {value!r}")

    if args.tree:
        if not args.under:
            print("[WARN] --tree 要配 --under")
        else:
            scope = next((n for n in walk(page)
                          if n.objectName() == args.under), None)
            if scope is None:
                print(f"[WARN] --under 找不到 {args.under!r}")
            else:
                print()
                print(f"--- {args.under} 子树 ---")
                for depth, node in _walk_depth(scope):
                    cls = node.metaObject().className()
                    try:
                        vis = bool(node.property("visible"))
                    except Exception:
                        vis = None
                    pos = node.mapToItem(page, 0, 0)
                    print(f"{'  ' * depth}{cls}{' #' + node.objectName() if node.objectName() else ''}"
                          f"  vis={vis} x={pos.x():.0f} y={pos.y():.0f}"
                          f" w={float(node.property('width')):.0f}"
                          f" h={float(node.property('height')):.0f}")
                    for prop in ("text", "title", "description"):
                        if node.metaObject().indexOfProperty(prop) >= 0:
                            val = node.property(prop)
                            if isinstance(val, str) and val.strip():
                                print(f"{'  ' * (depth + 1)}· {prop}={val[:48]!r}")

    if args.texts:
        scope = page
        if args.under:
            scope = next((n for n in walk(page)
                          if n.objectName() == args.under), None)
            if scope is None:
                print(f"[WARN] --under 找不到 {args.under!r}")
        print()
        print("--- Text 节点 ---")
        print(f"{'text':44} {'x':>8} {'y':>8} {'w':>7} {'h':>6} "
              f"{'vis':>5} {'opac':>5} color")
        for node in walk(scope):
            cls = node.metaObject().className()
            if not cls.startswith("Text_"):
                continue
            text = str(node.property("text") or "")
            if not text.strip():
                continue
            pos = node.mapToItem(page, 0, 0)
            color = node.property("color")
            print(f"{text[:42]!r:44} {pos.x():8.1f} {pos.y():8.1f} "
                  f"{float(node.property('width')):7.1f} "
                  f"{float(node.property('height')):6.1f} "
                  f"{str(bool(node.property('visible'))):>5} "
                  f"{float(node.property('opacity')):5.2f} {color!r}")

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())