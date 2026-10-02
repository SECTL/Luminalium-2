"""一次性探针：验证 RinUI 字体补丁 + 默认 QLocale 的联动。

流程：QLocale.setDefault(ja_JP) → 引擎里实例化一个引用 ``Utils.fontFamily``
的最小组件 → 回读字体名。预期 ``Yu Gothic UI``；切回 zh_CN 预期
``Microsoft YaHei``（补丁对非日语环境零影响）。

用法::

    .venv/Scripts/python.exe tools/probe_ja_font.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEventLoop, QLocale, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402

import RinUI  # noqa: F401,E402 —— 触发 qmldir 注册

from app.rinui_patch import apply  # noqa: E402

PROBE_QML = """
import QtQuick
import RinUI
QtObject {
    property string family: Utils.fontFamily
}
"""


def probe(language: str) -> str:
    QLocale.setDefault(QLocale(language))
    engine = QQmlEngine()
    engine.addImportPath(str(Path(RinUI.__file__).parent.parent))
    component = QQmlComponent(engine)
    component.setData(PROBE_QML.encode("utf-8"), QUrl("probe://ja-font.qml"))
    # RinUI 单例的解析是异步的（status=Loading），必须等 statusChanged
    if component.status() == QQmlComponent.Status.Loading:
        loop = QEventLoop()
        component.statusChanged.connect(lambda _: loop.quit())
        loop.exec()
    if component.isError():
        print(component.errorString())
        raise SystemExit(1)
    obj = component.create()
    family = obj.property("family")
    obj.deleteLater()
    engine.deleteLater()
    print(f"{language:>6} -> {family}")
    return family


def main() -> int:
    apply()  # 幂等
    app = QGuiApplication(sys.argv)  # noqa: F841 —— QML 引擎需要应用对象
    results = {lang: probe(lang) for lang in ("ja_JP", "zh_CN", "en_US")}
    QTimer.singleShot(0, app.quit)
    app.exec()
    ok = (
        results["ja_JP"] == "Yu Gothic UI"
        and results["zh_CN"] == "Microsoft YaHei"
        and results["en_US"] == "Microsoft YaHei"
    )
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
