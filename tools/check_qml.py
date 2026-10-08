"""开发用：静态检查 ``ui/`` 下**全部** QML 文件能否编译。

``tools/preview.py`` 只会实例化被渲染的那几个窗口（快捷面板 / 控制条 / 设置首页），
设置窗口里其余页面是 ``NavigationView`` 点开时才创建的 —— 写错了要等到用户点进去
才发现。本脚本把每个 ``.qml`` 都当 ``QQmlComponent`` 编译一遍并汇总错误，
不创建窗口、不弹界面。

注意只做**编译**检查：不创建对象实例，所以「缺 context property」「运行期
ReferenceError」这类问题仍需 ``preview.py`` / ``smoke.py`` 覆盖。

主题副作用（2026-10-07 自建批注 todo 11）：固定钉深色编译会碰
``RinUI/config/rin_ui.json``，跑完按**文件字节**快照还原（finally），
内存 toggle 之外再兜一层，任何中断路径都不漏主题。

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
    # 2026-10-07 自建批注 todo 11：在内存 toggle 还原主题（见下方原注释）之外，
    # 再把 ``RinUI/config/rin_ui.json`` 的**文件内容**按字节快照、finally 里写回。
    # 内存还原兜不住的情形：编译中途崩溃 / 异常跳过了 toggle、RinConfig 在退出
    # 时序里再落一次盘 —— 本脚本是三层验证里跑得最勤的一环，任何一次主题泄漏
    # 都会污染后续所有预览工具的「原值」。
    rin_ui_cfg = ROOT / "RinUI" / "config" / "rin_ui.json"
    snapshot = rin_ui_cfg.read_bytes() if rin_ui_cfg.exists() else None
    try:
        return _compile_all()
    finally:
        if snapshot is None:
            # 跑之前文件不存在：RinUI 在运行中建了它，删掉才算真正还原
            if rin_ui_cfg.exists():
                rin_ui_cfg.unlink()
        else:
            rin_ui_cfg.write_bytes(snapshot)


def _compile_all() -> int:
    # 墨迹输入前提：关高频事件合并（前后各调一次，原因见 configure_input_attributes docstring）
    from app.ink import configure_input_attributes
    configure_input_attributes()
    qt_app = QApplication(sys.argv)
    configure_input_attributes()
    # 自建墨迹的 Python 类型（Luminalium.Ink 1.0）要在编译任何 QML 之前登记，
    # 否则 ui/ink/ 下 import 它的文件会被误报为编译失败（与 application.py 同一时序）。
    from app.ink import register_qml_types
    register_qml_types()

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
