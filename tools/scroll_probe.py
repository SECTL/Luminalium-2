"""开发用：核对 ``Rin.ScrollableTextArea`` 与 ``Rin.TextArea`` 的可滚动性。

结论（2026-10-04 实测，本机 1755×987 / PySide6 6.11.2）::

    Rin.ScrollableTextArea  contentItem = QQuickFlickable
                            contentHeight = 692 / height = 180   → 能滚
    Rin.TextArea            contentItem = None
                            implicitHeight = 652 / height = 180  → 只是被裁掉

所以「关于」页诊断对话框里的只读文本框用前者。背景：2026-10-04 用户指令
「滚不动」—— 那一版用的就是 ``Rin.TextArea``，文本超长时既不能滚也不能拖。

顺带钉住两个坑：

* ``ScrollableTextArea`` 里写着 ``implicitHeight: defaultHeight``，而
  ``defaultHeight`` 在 RinUI 里根本没有定义（上游笔误）—— 这条绑定求值失败、
  ``implicitHeight`` 落到 **0**。所以外面**必须**给 ``Layout.preferredHeight``。
* ``Rin.TextArea`` 把 ``enabled`` 绑在 ``editable`` 上，用 ``editable: false``
  实现只读会把整框打成禁用。只读要用 ``readOnly``。

用法::

    .venv\\Scripts\\python.exe tools\\scroll_probe.py

输出（控制台）：两个框的 ``contentItem`` 类型、内容高 / 视口高、以及「写
``contentY`` 认不认账」。探针 QML 写在 ``preview/_scroll_probe.qml`` 且**不删**
（``QQmlEngine`` 会给每个 QML 源文件挂监视器，源文件消失会连带回收对象）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QPointF, QTimer, QUrl  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import BackdropEffect, RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RINUI_PATH  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402

OFFSCREEN = -6000
OUT_DIR = ROOT / "preview"

#: 两个候选文本框并排摆出来。长文本固定 40 行 —— 只要它比 180 的视口高就行。
PROBE_QML = """import QtQuick
import QtQuick.Layouts
import RinUI as Rin

Rin.Window {
    id: host
    width: 560
    height: 460
    titleBarHeight: 0
    titleEnabled: false
    closeVisible: false
    minimizeVisible: false
    maximizeVisible: false
    flags: Qt.Tool | Qt.FramelessWindowHint

    property string longText: {
        var lines = []
        for (var i = 0; i < 40; ++i)
            lines.push("Key" + i + ": value-" + i + " / a somewhat long value")
        return lines.join("\\n")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        Rin.ScrollableTextArea {
            objectName: "probeScrollable"
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            readOnly: true
            font.family: "Consolas"
            font.pixelSize: 13
            text: host.longText
        }

        Rin.TextArea {
            objectName: "probePlain"
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            readOnly: true
            font.family: "Consolas"
            font.pixelSize: 13
            text: host.longText
        }
    }
}
"""


def _find_named(item, name: str):
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _find_named(child, name)
        if found is not None:
            return found
    return None


def _dump(tag: str, box) -> None:
    if box is None:
        print(f"  {tag}: <not found>")
        return
    print(f"  {tag}: class={box.metaObject().className()}")
    print(f"    implicitHeight={box.property('implicitHeight')} "
          f"height={box.property('height')} width={box.property('width')}")
    ci = box.property("contentItem")
    if ci is None:
        # ``Rin.TextArea`` 走到这里：它底子是 ``QtQuick.Controls.Basic`` 的
        # TextArea，内容项在 C++ 侧，``contentItem`` 取回来就是 None。
        print("    contentItem=None（= 没有可滚的容器）")
        return
    print(f"    contentItem class={ci.metaObject().className()}")
    for prop in ("contentY", "contentHeight", "height", "width"):
        print(f"      contentItem.{prop}={ci.property(prop)}")


def _drag_content(ci) -> bool:
    """直接写 ``contentY``：Flickable 认这个值就说明它真能滚（不是被裁死的静态块）。"""
    if ci is None:
        return False
    limit = float(ci.property("contentHeight") or 0.0) - float(ci.property("height") or 0.0)
    ci.setProperty("contentY", min(200.0, max(0.0, limit)))
    got = float(ci.property("contentY") or 0.0)
    print(f"    contentY 写入 -> {got}（可滚上限 {limit:.0f}）")
    return got > 0.5


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    qml_path = OUT_DIR / "_scroll_probe.qml"
    qml_path.write_text(PROBE_QML, encoding="utf-8")

    config = Config()
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, qt_app)
    rinui = RinUIWindow()
    # RinUI 模块的 import path 是在 ``RinUIWindow.load()`` 里才加的；本脚本不
    # load 那个窗口，所以手动补上（与 tools/check_qml.py 同一个常量）。
    rinui.engine.addImportPath(str(RINUI_PATH))
    rinui.engine.addImportPath(str(UI_DIR))
    # ⚠️ ``setTheme`` 会**持久化到 ``RinUI/config/rin_ui.json``**，所以先记下原值、
    # 跑完切回去 —— 否则开发机上整个应用的下次启动会跟着变（preview.py 同款处理）。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.setBackdropEffect(BackdropEffect.None_)

    component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(qml_path)))
    if component.isError():
        for error in component.errors():
            print("PROBE ERROR:", error.toString())
        return 1
    window = component.createWithInitialProperties({"visible": True})
    if window is None:
        for error in component.errors():
            print("CREATE ERROR:", error.toString())
        return 1
    window._probe_component = component  # 持有引用防引擎回收
    window.setPosition(OFFSCREEN, OFFSCREEN)
    window.show()

    def run() -> None:
        try:
            root = window.contentItem()
            for name in ("probeScrollable", "probePlain"):
                box = _find_named(root, name)
                _dump(name, box)
                if box is not None:
                    print(f"    contentY-write={_drag_content(box.property('contentItem'))}")
        except Exception:  # noqa: BLE001 - 探针脚本，别吞掉堆栈
            import traceback

            traceback.print_exc()
        finally:
            # 主题要还原（见上面那段注释）—— 必须在窗口还在的时候切，否则没东西重绘
            if rinui.theme_manager.get_theme_name() != previous_theme:
                rinui.theme_manager.toggle_theme(previous_theme)
                print(f"[OK] 主题已还原为 {previous_theme}")
            qt_app.quit()

    QTimer.singleShot(900, run)
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
