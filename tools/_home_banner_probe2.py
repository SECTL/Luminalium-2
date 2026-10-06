"""临时探针：Home 页横幅的 y 在页面稳定后落在哪儿（smoke 断言排查用）。"""
import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import os
os.chdir(ROOT)
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow, Theme, BackdropEffect
from app.bridge import Backend
from app.config import Config
from app.paths import UI_DIR

HOST = """
import QtQuick
import RinUI as Rin
Rin.Window {
    property url pageUrl: ""
    width: 961; height: 940
    titleBarHeight: 0; titleEnabled: false
    closeVisible: false; minimizeVisible: false; maximizeVisible: false
    flags: Qt.Tool | Qt.FramelessWindowHint
    Loader { anchors.fill: parent; source: host.pageUrl }
}
"""

app = QApplication([]); app.setQuitOnLastWindowClosed(False)
backend = Backend(Config(), app)
rinui = RinUIWindow(); rinui.engine.addImportPath(str(UI_DIR)); rinui.setTheme(Theme.Dark)
# 离屏窗口拿不到 DWM 合成层；与 tools/preview.py 同款显式关掉 backdrop。
rinui.setBackdropEffect(BackdropEffect.None_)
rinui.engine.rootContext().setContextProperty("Backend", backend)
rinui.load(UI_DIR / "QuickPanel.qml")
rinui.root_window.setPosition(-6000, -6000); rinui.root_window.show()


def find(item, name):
    for c in item.childItems():
        if c.objectName() == name:
            return c
        r = find(c, name)
        if r is not None:
            return r


host_path = ROOT / "preview" / "_tmp_home_host.qml"
host_path.write_text(HOST, encoding="utf-8")
comp = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(host_path)))
if comp.isError():
    for e in comp.errors():
        print("COMPONENT ERROR:", e.toString())
win = comp.createWithInitialProperties({
    "pageUrl": QUrl.fromLocalFile(str(UI_DIR / "settings/Update.qml")),
    "visible": True,
})
win._c = comp
win.setPosition(-6900, -7800)
win.show()

def names(item, depth=0, out=None):
    if out is None:
        out = []
    out.append((depth, item.objectName()))
    for c in item.childItems():
        names(c, depth + 1, out)
    return out

end = time.perf_counter() + 8
printed = False
while time.perf_counter() < end:
    app.processEvents()
    time.sleep(0.005)
    b = find(win.contentItem(), "homeBannerImage")
    if b is not None:
        y = b.mapToItem(win.contentItem(), 0, 0).y()
        pw = float(b.property("paintedWidth") or 0)
        print(f"y={y:.0f} paintedWidth={pw:.0f}")
        if pw > 100:
            break
    elif not printed and time.perf_counter() > end - 7.5:
        printed = True
        all_names = []

        def walk(item, depth=0):
            nm = item.objectName()
            if nm:
                all_names.append("  " * depth + nm)
            for c in item.childItems():
                walk(c, depth + 1)

        walk(win.contentItem())
        print("非空 objectName 共 %d 个:" % len(all_names))
        for nm in all_names[:80]:
            print(nm)
print("done")
