"""开发用：实测「窗口有没有被 RinUI 完整接管」在 Win32 / DWM 层的差异。

RinUI 的窗口外观（去掉原生标题栏、系统阴影、圆角、暗色、Mica/Acrylic）
**全部**由两处 Windows 侧代码承担：

* ``RinUI.core.window.WinEventFilter`` —— 处理 ``WM_NCCALCSIZE``（把非客户区
  压掉，视觉上只剩 RinUI 自绘标题栏）、``WM_NCHITTEST``（8px resize 边框 +
  ``HTCAPTION`` 拖动）、``WM_GETMINMAXINFO``（Snap / 最小尺寸）；
* ``RinUI.core.theme.ThemeManager`` —— 对 ``self.windows``（**hwnd 列表**）
  逐个 ``DwmSetWindowAttribute``：圆角、阴影（``NCRENDERING_POLICY``）、
  边框色、标题栏色、暗色、backdrop。

这两个名单都**只在 ``launcher.load()`` 那一刻确定一次**：取
``[root_window] + root_window.findChildren(QQuickWindow)`` 里带
``isRinUIWindow`` 的那些。之后用 ``QQmlComponent`` 另建的顶层窗口永远进不去
—— 既没有圆角 / 阴影 / 暗色 / backdrop，也没有任何东西替它处理
``WM_NCCALCSIZE``（于是 ``WS_CAPTION`` 一加上，原生标题栏就真的画出来）。

本脚本走**生产路径**（``WindowManager.show_settings/show_debug`` →
``_attach_to_rinui``），把 Win32 / DWM 的读回值和窗口外圈的像素剖面都打出来，
再截一张图存档。

用法::

    .venv\\Scripts\\python.exe tools\\window_frame_probe.py
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402

from app.config import Config  # noqa: E402
from app.windows import WindowManager  # noqa: E402

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_EX_LAYERED = 0x00080000
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33

CORNER_NAMES = {0: "Default", 1: "DoNotRound", 2: "Round", 3: "RoundSmall"}


def _style_bits(style: int) -> str:
    bits = [
        name
        for name, value in (
            ("WS_CAPTION", WS_CAPTION),
            ("WS_THICKFRAME", WS_THICKFRAME),
            ("WS_SYSMENU", WS_SYSMENU),
        )
        if style & value
    ]
    return "+".join(bits) if bits else "(none)"


def report(win, label: str, app_rinui) -> None:
    hwnd = int(win.winId())
    style = user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_STYLE)
    exstyle = user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    corner = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(
        hwnd, ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE), ctypes.byref(corner), ctypes.sizeof(corner)
    )
    dark = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(
        hwnd, ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE), ctypes.byref(dark), ctypes.sizeof(dark)
    )
    filter_hwnds = {int(h) for h in app_rinui.win_event_filter.hwnds.values()}
    theme_hwnds = {int(h) for h in app_rinui.theme_manager.windows}
    floor = int(user32.GetWindowLongPtrW(wintypes.HWND(hwnd), -8))  # GWL_HINSTANCE 占位，仅用于占位打印

    print(f"\n=== {label} ===")
    print(f"  hwnd              : {hwnd}")
    print(f"  WinEventFilter 管 : {hwnd in filter_hwnds}  (WM_NCCALCSIZE / WM_NCHITTEST / WM_GETMINMAXINFO)")
    print(f"  ThemeManager 管   : {hwnd in theme_hwnds}  (圆角 / 阴影 / 暗色 / 边框色 / backdrop)")
    print(f"  GWL_STYLE         : {hex(style)}  {_style_bits(style)}")
    print(f"  GWL_EXSTYLE       : {hex(exstyle)}  {'+WS_EX_LAYERED' if exstyle & WS_EX_LAYERED else ''}")
    print(f"  corner_preference : {corner.value} ({CORNER_NAMES.get(corner.value, '?')})")
    print(f"  immersive_dark    : {dark.value}")
    del floor


def main() -> int:
    app = QApplication(sys.argv)

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(ROOT / "ui"))
    rinui.theme_manager.set_theme_color("#4CC2FF")
    rinui.setTheme(Theme.Dark)
    rinui.load(ROOT / "ui" / "QuickPanel.qml")

    print("## RinUI 在 load() 时登记了哪些窗口")
    print(f"   launcher.windows       : {len(rinui.windows)} 个")
    print(f"   ThemeManager.windows   : {sorted(rinui.theme_manager.windows)}")
    print(f"   WinEventFilter.windows : {len(rinui.win_event_filter.windows)} 个")

    # 走生产路径：WindowManager 创建 + _attach_to_rinui 接管
    windows = WindowManager(rinui.engine, Config(), None, None, rinui=rinui)
    windows.show_settings()
    windows.show_debug()

    def finish() -> None:
        report(windows.settings, "设置窗口（生产路径：WindowManager）", rinui)
        report(windows.debug, "调试窗口（生产路径：WindowManager）", rinui)

        # 摆到屏上固定位置，便于像素剖面分析
        windows.settings.setPosition(420, 160)
        windows.debug.setPosition(1100, 300)

        def shot() -> None:
            screen = QApplication.primaryScreen()
            path = ROOT / "preview" / "_dwm_probe.png"
            path.parent.mkdir(exist_ok=True)
            screen.grabWindow(0).save(str(path))
            print(f"\n截图: {path}")
            app.quit()

        QTimer.singleShot(600, shot)

    QTimer.singleShot(500, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
