"""开发用：探测 RinUI 组件在当前版本（0.4.4.1）中是否真的可用。

RinUI 的 qmldir 里登记了部分实现缺失 / 属性对不上的组件，例如
``RoundButton`` 引用了只存在于 ``Rin.Button`` 上的 ``backgroundColor``、
``Expander`` 没有 ``title``、``ScrollView`` 实际注册名是 ``ScrollViewer``。
本脚本先引导一个真实窗口让主题单例就绪，再逐个实例化候选组件，
收集**全部** QML 错误与运行期告警（包含来自 RinUI 内部文件的），
用来决定哪些组件可以安全地作为基础组件使用。

用法::

    .venv\\Scripts\\python.exe tools\\rinui_probe.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QByteArray, QTimer, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402

HEADER = "import QtQuick\nimport RinUI as Rin\n"

CASES: list[tuple[str, str]] = [
    ("Icon", 'Rin.Icon { icon: "ic_fluent_pen_20_regular"; size: 20 }'),
    ("Text", 'Rin.Text { text: "hi"; typography: Rin.Typography.Body }'),
    ("Frame", "Rin.Frame { width: 120; height: 40; radius: 12 }"),
    ("Button.flat", 'Rin.Button { text: ""; flat: true; width: 36; height: 36 }'),
    ("Button.icon", 'Rin.Button { icon.name: "ic_fluent_pen_20_regular"; flat: true; width: 36; height: 36 }'),
    ("Button.accent", 'Rin.Button { highlighted: true; width: 40; height: 40 }'),
    ("RoundButton", "Rin.RoundButton { width: 40; height: 40 }"),
    ("ToolButton", 'Rin.ToolButton { width: 36; height: 36; icon.name: "ic_fluent_settings_20_regular" }'),
    ("ToolSeparator.orient", "Rin.ToolSeparator { orientation: Qt.Vertical }"),
    ("ScrollViewer", "Rin.ScrollViewer { width: 100; height: 60 }"),
    ("ScrollBar", "Rin.ScrollBar { orientation: Qt.Vertical }"),
    ("SettingCard", 'Rin.SettingCard { title: "t"; description: "d" }'),
    ("SettingItem", 'Rin.SettingItem { title: "t" }'),
    ("ToolTip", 'Rin.ToolTip { text: "tip" }'),
    ("Popup", "Rin.Popup { }"),
    ("Flyout", "Rin.Flyout { }"),
    ("Menu", "Rin.Menu { }"),
    ("MenuItem", 'Rin.MenuItem { text: "a" }'),
    ("Shadow", "Rin.Shadow { }"),
    ("ProgressRing", "Rin.ProgressRing { }"),
    ("ListViewDelegate", 'Rin.ListViewDelegate { text: "row" }'),
    ("InfoBar", 'Rin.InfoBar { title: "a" }'),
    ("Clip", "Rin.Clip { width: 50; height: 50 }"),
    ("Expander", "Rin.Expander { }"),
    ("AcrylicBrush", "Rin.AcrylicBrush { width: 50; height: 50 }"),
    ("ToggleButton", 'Rin.ToggleButton { text: "t" }'),
    ("PillButton", 'Rin.PillButton { text: "t" }'),
]

MESSAGES: list[str] = []


def _flat(error) -> str:  # noqa: ANN001
    return " ".join(part.strip() for part in str(error).splitlines() if part.strip())


def main() -> int:
    qt_app = QApplication(sys.argv)

    def handler(mode, context, message):  # noqa: ANN001
        # context.file 可能为 None（Qt 某些消息不带位置信息）
        ctx_file = getattr(context, "file", "") or ""
        ctx_line = getattr(context, "line", 0) or 0
        MESSAGES.append(f"{Path(ctx_file).name}:{ctx_line} {message.rstrip()}")

    qInstallMessageHandler(handler)

    rinui = RinUIWindow()
    rinui.theme_manager.set_theme_color("#4CC2FF")
    rinui.setTheme(Theme.Dark)

    # 先加载一个真实窗口，让 RinUI 的导入路径与 Theme 单例就绪
    boot = Path("tools") / "_probe_boot.qml"
    boot.write_text(
        "import QtQuick\nimport RinUI as Rin\nRin.Window {\n"
        "    width: 200\n    height: 120\n    visible: false\n"
        '    property string themeProbe: Rin.Theme.currentTheme ? "theme-ok" : "theme-null"\n'
        "}\n",
        encoding="utf-8",
    )
    try:
        rinui.load(boot)
        theme_state = rinui.root_window.property("themeProbe")
    finally:
        boot.unlink(missing_ok=True)

    engine = rinui.engine
    lines: list[str] = [f"theme: {theme_state}", ""]

    for name, body in CASES:
        MESSAGES.clear()
        source = HEADER + "Item {\n    " + body + "\n}\n"
        component = QQmlComponent(engine)
        component.setData(QByteArray(source.encode("utf-8")), QUrl("probe://t.qml"))
        if component.isError():
            detail = " | ".join(_flat(e) for e in component.errors())
            lines.append(f"[BROKEN] {name}: {detail}")
            continue
        obj = component.create()
        if obj is None:
            detail = " | ".join(_flat(e) for e in component.errors())
            lines.append(f"[BROKEN] {name}: create() 失败 {detail}")
            continue
        if MESSAGES:
            lines.append(f"[WARN]   {name}: {' | '.join(MESSAGES[:3])}")
        else:
            lines.append(f"[OK]     {name}")

    Path("probe_result.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

    QTimer.singleShot(0, qt_app.quit)
    qt_app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
