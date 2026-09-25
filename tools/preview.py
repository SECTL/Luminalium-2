"""开发用：把界面离屏渲染成 PNG，便于快速核对版式。

用法::

    .venv\\Scripts\\python.exe tools\\preview.py

输出到 ``preview/``：

- ``quick_panel.png``      —— 快捷面板
- ``top_window.png``       —— 「顶层窗口」（全屏叠加层）+ 内嵌的下中部工具栏与
  左右两只翻页 pill（预览里用紧凑尺寸代替真实全屏，版式一致）
- ``settings.png``         —— 设置窗口（主页）
- ``page_*.png``           —— 设置窗口里每个页面单独渲染一张（``NavigationView``
  只有在用户点进去时才创建页面，所以这里用临时宿主窗口把它们全跑一遍）

窗口会被放到屏幕外（x = -6000）并强制渲染，因此**不会打扰桌面**。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import BackdropEffect, RinUIWindow, Theme  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402

OFFSCREEN_X = -6000
OFFSCREEN_Y = -6000
OUT_DIR = ROOT / "preview"
CORNERS = ("bottom_left", "bottom_center", "bottom_right")


def main() -> int:
    config = Config()
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, qt_app)
    backend.apply_state(
        PresentationState(active=True, slide_index=26, slide_total=41)
    )

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent")))
    rinui.setTheme(Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(UI_DIR / "QuickPanel.qml")
    # 预览图不需要 DWM 背景特效，关掉能拿到实色背景（结束后恢复，避免污染用户配置）
    previous_effect = rinui.theme_manager.get_backdrop_effect()
    rinui.setBackdropEffect(BackdropEffect.None_)

    panel = rinui.root_window
    panel.setPosition(OFFSCREEN_X, OFFSCREEN_Y)
    panel.show()

    # ---- 顶层窗口（全屏叠加层）+ 内嵌控制条 ----
    # 预览用紧凑尺寸（1100x640）代替真实全屏；定位逻辑与 app/windows.py 一致。
    PREVIEW_W, PREVIEW_H = 1100, 640
    top_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "TopWindow.qml"))
    )
    top_window = None
    if top_component.isError():
        for error in top_component.errors():
            print("TOP WINDOW ERROR:", error.toString())
    else:
        top_window = top_component.createWithInitialProperties({"visible": True})
        if top_window is None:
            print("TOP WINDOW CREATE ERROR")
        else:
            top_window._top_component = top_component  # 持有引用防引擎回收
            top_window.setWidth(PREVIEW_W)
            top_window.setHeight(PREVIEW_H)
            top_window.setPosition(OFFSCREEN_X - 400, OFFSCREEN_Y)
            top_window.show()

    dock_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "PresentationDock.qml"))
    )
    if dock_component.isError():
        for error in dock_component.errors():
            print("DOCK ERROR:", error.toString())

    container = top_window.property("container") if top_window is not None else None
    margin_x = int(config.get("presentation.margin_x", 20))
    margin_y = int(config.get("presentation.margin_y", 20))
    corners_cfg = config.get("presentation.corners", {}) or {}
    for corner in CORNERS:
        if not (corners_cfg.get(corner) or {}).get("enabled", False):
            continue
        dock = dock_component.createWithInitialProperties({"corner": corner})
        if dock is None:
            for error in dock_component.errors():
                print(f"DOCK {corner} ERROR:", error.toString())
            continue
        dock._dock_component = dock_component  # 持有引用防引擎回收
        dock.setParentItem(container)
        # 与 windows.py::_position_dock 同语义：margin 是**视觉距离**，
        # 要扣掉控制条自带的投影余量（否则预览里的间距会比真机大 24px）
        shadow = int(dock.property("shadowMargin") or 0)
        if corner.endswith("left"):
            x = margin_x - shadow
        elif corner.endswith("center"):
            x = (PREVIEW_W - dock.width()) // 2
        else:
            x = PREVIEW_W - dock.width() - margin_x + shadow
        dock.setX(x)
        dock.setY(PREVIEW_H - dock.height() - margin_y + shadow)

    # 设置窗口：默认页由 NavigationView 在 Component.onCompleted 里推入
    settings = None
    settings_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "Settings.qml"))
    )
    if settings_component.isError():
        for error in settings_component.errors():
            print("SETTINGS ERROR:", error.toString())
    else:
        settings = settings_component.createWithInitialProperties({"visible": True})
        if settings is None:
            for error in settings_component.errors():
                print("SETTINGS CREATE ERROR:", error.toString())
        else:
            settings.setPosition(OFFSCREEN_X, OFFSCREEN_Y - 900)
            settings.show()

    # 各设置页单独渲染：用临时宿主窗口 + Loader 承载，逐页跑一遍
    page_hosts = _build_page_hosts(rinui.engine)

    OUT_DIR.mkdir(exist_ok=True)

    def capture() -> None:
        targets = [("quick_panel.png", panel)]
        if top_window is not None:
            targets.append(("top_window.png", top_window))
        if settings is not None:
            targets.append(("settings.png", settings))
        targets += page_hosts

        for name, window in targets:
            try:
                image = window.grabWindow()
            except RuntimeError as exc:  # 窗口已被 QML 引擎回收
                print(f"[FAIL] {name}: {exc}")
                continue
            path = OUT_DIR / name
            if image.isNull():
                print(f"[FAIL] {name}: grabWindow() 返回空图")
                continue
            image.save(str(path))
            print(f"[OK] {name} -> {path} ({image.width()}x{image.height()})")
        qt_app.quit()

    QTimer.singleShot(1800, capture)
    return qt_app.exec()


PAGE_HOST_QML = """import QtQuick
import RinUI as Rin

Rin.Window {
    id: host
    property url pageUrl: ""

    width: 780
    height: 640
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


def _build_page_hosts(engine) -> list[tuple[str, object]]:
    """把 ``ui/settings`` 下每个页面塞进一个临时宿主窗口，返回 ``(文件名, 窗口)``。

    宿主 QML **写在 ``preview/`` 里且不删**：``QQmlEngine`` 会给每个 QML 源文件挂
    文件监视器，源文件一旦消失，引擎会判定文档失效并**回收由它创建的全部对象**
    （表现为 ``Internal C++ object already deleted``）。这也是为什么
    ``_probe_boot.qml`` 那种「写完就删」的用法只适合立即读属性的场景。
    """
    OUT_DIR.mkdir(exist_ok=True)
    host_path = OUT_DIR / "_page_host.qml"
    host_path.write_text(PAGE_HOST_QML, encoding="utf-8")

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(host_path)))
    if component.isError():
        for error in component.errors():
            print("PAGE HOST ERROR:", error.toString())
        return []

    hosts: list[tuple[str, object]] = []
    for index, page in enumerate(sorted((UI_DIR / "settings").rglob("*.qml"))):
        window = component.createWithInitialProperties(
            {
                "pageUrl": QUrl.fromLocalFile(str(page)),
                "visible": True,
            }
        )
        if window is None:
            for error in component.errors():
                print(f"PAGE {page.name} ERROR:", error.toString())
            continue
        # 持有 component 引用：PySide 中 create() 出来的对象生命周期与组件绑定
        window._host_component = component
        window.setPosition(OFFSCREEN_X - index * 900, OFFSCREEN_Y - 1800)
        window.show()
        hosts.append((f"page_{page.stem}.png", window))
    return hosts


if __name__ == "__main__":
    raise SystemExit(main())
