"""开发用：确认「亚克力」在真机上真的生效（**唯一**的验证手段）。

为什么不能并进 ``preview.py``：

* ``preview.py`` 跑的是**离屏抓图**（``QQuickWindow.grabWindow``），拿到的是 Qt
  自己的渲染结果，**不含 DWM 的合成层** —— 亚克力 / 云母这类系统材质一个像素都
  抓不到，离屏时连兜底色都看不到（窗口被摆在 x = -6000）。
* 所以只能把窗口摆到**屏幕内**、压到最前，再用 ``QScreen.grabWindow(0)`` 截整屏，
  回头看内容区的像素是不是「被系统模糊过的下层窗口 / 壁纸」。

⚠️ 这个脚本会**真的在屏幕上弹出编辑器窗口并置顶约 1.5 秒**（不弹的话会被其他
全屏窗口整个盖住，截图上什么都看不到）。所以它不进 ``preview.py`` 的常规流程，
只在需要确认材质时手动跑。

用法::

    .venv\\Scripts\\python.exe tools\\acrylic_probe.py

产出 ``preview/acrylic_check.png``（整屏截图）。判据：

* **内容区** —— 能模糊透出下方窗口 / 壁纸（不是纯色、不是透明）；
* **标题栏** —— 实色，下方内容一个像素都透不上来。

环境变量：

* ``LUMI_PREVIEW_EDIT=<corner>`` —— 让编辑器停在**编辑态**（聚焦这个角落的控制条、
  右侧设置面板展开）再截。默认是全景态。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402
from app.ppt_controller import PptController  # noqa: E402
from app.windows import WindowManager  # noqa: E402

OFFSCREEN_X = -6000
OFFSCREEN_Y = -6000

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040


def pin_on_top(hwnd: int) -> None:
    """压到置顶层 —— 否则全屏的浏览器 / 编辑器会把它整个盖住。"""
    ctypes.windll.user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )


def main() -> int:
    config = Config()
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, qt_app)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent")))
    # ⚠️ ``setTheme()`` 会**持久化到 RinUI/config/rin_ui.json**（跑这个脚本本来
    # 是为了截深色下的亚克力，但别把开发机的主题留在 Dark 上）。模式与
    # ``preview.py`` 相同：记原值，结束时切回去。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(UI_DIR / "QuickPanel.qml")
    # 托盘面板挪出屏幕：截图时别挡着编辑器
    rinui.root_window.setPosition(OFFSCREEN_X, OFFSCREEN_Y)

    # 不 start()：这里只量窗口外观，不需要探测线程
    ppt = PptController(interval_ms=400, config=config)
    windows = WindowManager(
        rinui.engine, config, backend, ppt, tray=None, rinui=rinui
    )

    report: dict[str, object] = {}

    def capture() -> None:
        editor = windows.editor
        if editor is not None:
            report["geometry"] = (editor.x(), editor.y(), editor.width(), editor.height())
            report["backdropEnabled"] = editor.property("backdropEnabled")
            report["acrylicActive"] = editor.property("acrylicActive")
        shot = QGuiApplication.primaryScreen().grabWindow(0)
        out = ROOT / "preview" / "acrylic_check.png"
        shot.save(str(out))
        report["shot"] = f"{out} ({shot.width()}x{shot.height()})"

        # 切回原主题（``setTheme`` 会落盘）—— 必须在 quit() 之前、事件循环还在时做
        if rinui.theme_manager.get_theme_name() != previous_theme:
            rinui.theme_manager.toggle_theme(previous_theme)
            report["theme"] = f"已还原为 {previous_theme}"
        qt_app.quit()

    def start() -> None:
        windows.show_editor()
        editor = windows.editor
        if editor is not None:
            # ``LUMI_PREVIEW_EDIT=<corner>``：让编辑器停在编辑态（聚焦某条控制条、
            # 右侧面板展开）再截 —— 亚克力只在内容区透出来，面板是压在它上面的一层
            # 实色「层」，两者叠一起的效果只有真机截屏看得到。
            focus = os.environ.get("LUMI_PREVIEW_EDIT", "").strip()
            if focus:
                editor.setProperty("selectedCorner", focus)
            pin_on_top(int(editor.winId()))
            pin_on_top(int(rinui.root_window.winId()))
        QTimer.singleShot(1200, capture)

    QTimer.singleShot(300, start)
    code = qt_app.exec()
    for key, value in report.items():
        print(f"{key}: {value}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
