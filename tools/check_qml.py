"""开发用：静态检查 ``ui/`` 下**全部** QML 文件能否编译。

``tools/preview.py`` 只会实例化被渲染的那几个窗口（快捷面板 / 控制条 / 设置首页），
设置窗口里其余页面是 ``NavigationView`` 点开时才创建的 —— 写错了要等到用户点进去
才发现。本脚本把每个 ``.qml`` 都当 ``QQmlComponent`` 编译一遍并汇总错误，
不创建窗口、不弹界面。

注意只做**编译**检查：不创建对象实例，所以「缺 context property」「运行期
ReferenceError」这类问题仍需 ``preview.py`` / ``smoke.py`` 覆盖。

用法::

    .venv\\Scripts\\python.exe tools\\check_qml.py
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
from RinUI import RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RINUI_PATH, RinConfig  # noqa: E402

from app.paths import UI_DIR  # noqa: E402

#: ``ui/Luminalium`` 是**模块目录**：里面的组件靠 ``import Luminalium`` 自引用
#: （``Lumi`` 单例，见 AuroraFlow / GlassLogo），单独编译它们会拿到「模块自引用」
#: 那类噪声。它们仍会被**间接**检查到 —— 用到它们的页面（如 MainInterfaceEditor
#: 用 InspectorSetting）在下面逐个编译时，依赖组件一并进编译。
SKIP_DIRS = {"Luminalium"}


def main() -> int:
    qt_app = QApplication(sys.argv)

    rinui = RinUIWindow()
    # ``RinUIWindow.load()`` 才把 RinUI 模块目录塞进 importPathList；
    # 本脚本不加载任何窗口，所以要自己补上，否则所有 ``import RinUI`` 都报
    # "module RinUI is not installed"。
    rinui.engine.addImportPath(str(RINUI_PATH))
    rinui.engine.addImportPath(str(UI_DIR))
    # ⚠️⚠️ ``setTheme`` 会**持久化到 ``RinUI/config/rin_ui.json``**（真机下次启动
    # 读的就是那份）。本脚本只编译、不截图，所以固定钉深色；但**必须记下原值、
    # 收尾切回去并落盘** —— 否则它就是个静默的主题泄漏源：本脚本是「三层验证」
    # 里跑得最勤的一环，每跑一次就把用户的 ``current_theme`` 写成 ``Dark``，
    # 之后所有预览工具读到「原值 = Dark」也就跟着还原成 Dark，
    # 看起来像「预览没还原」，其实是这里先污染的（2026-10-05 实测）。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Dark)

    files = sorted(
        path
        for path in UI_DIR.rglob("*.qml")
        if not SKIP_DIRS & set(path.relative_to(UI_DIR).parts)
    )

    failures: list[str] = []
    for path in files:
        component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(path)))
        if component.isError():
            detail = " | ".join(
                " ".join(str(error).split()) for error in component.errors()
            )
            failures.append(f"[FAIL] {path.relative_to(ROOT)}: {detail}")
        else:
            print(f"[OK]   {path.relative_to(ROOT)}")

    print("\n================ 编译检查 ================")
    for line in failures:
        print(line)
    print(f"共 {len(files)} 个文件，失败 {len(failures)} 个")
    print("=========================================")

    # 还原主题（``toggle_theme`` 只改内存，写文件的是 ``clean_up()`` —— 在退出时
    # 才跑，所以这里必须显式 ``save_config()``，否则屏幕上打印「已还原」而文件
    # 里还是 Dark）。
    if rinui.theme_manager.get_theme_name() != previous_theme:
        rinui.theme_manager.toggle_theme(previous_theme)
        RinConfig.save_config()
        print(f"[OK] 主题已还原并落盘为 {previous_theme}")

    QTimer.singleShot(0, qt_app.quit)
    qt_app.exec()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
