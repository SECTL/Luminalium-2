"""开发用：诊断「窗口背景材质（Mica / Acrylic / Tabbed）到底有没有生效」。

2026-10-01 用户报告「RinUI 的 Mica 失效了」。本脚本把判定拆成两问，分别读事实：

1. **打没打上** —— 对真实窗口（QuickPanel + 设置 / 调试 / 编辑器）读回
   ``DWMWA_SYSTEMBACKDROP_TYPE``（38）、``GWL_STYLE`` / ``GWL_EXSTYLE``、
   以及 QML 侧 ``Utils.backdropEnabled``；
2. **看不看得见** —— 另建一只**空 QQuickWindow**（`setColor(Qt.transparent)`，
   窗口里什么都不画），依次打 ``0(none) / 2(Mica) / 3(Acrylic) / 4(Tabbed)``，
   在四个状态各截一次屏，再采样窗口正中与左右两点的像素。

第 2 步是关键：**材质是"壁纸基"的**（Mica / Acrylic / Tabbed 都取桌面壁纸那一层，
不会把身后的**窗口**内容糊进来）。所以：
* 采样值 == 身后那块彩条板的颜色 → 材质**没上**（窗口只是透明）；
* 采样值是**一片纯色**（与彩条板无关） → 材质**上了**，那一片纯色就是材质的基色。

⚠️ 深色档 Mica 的基色实测就是 ``#202020`` —— 与本项目 ``colors.backgroundColor``
**完全同色**，所以「开着 Mica 看着像没开」是正常现象，不是失效。要区分「材质没上」
与「材质上了但和底色同色」，必须做第 2 步的纯色/彩条判别。

用法::

    .venv\\Scripts\\python.exe tools\\mica_probe.py
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication, QPixmap  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402
from RinUI import BackdropEffect, RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import is_win11, is_win11_22h2  # noqa: E402

from app.config import Config  # noqa: E402
from app.windows import WindowManager  # noqa: E402

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
WS_EX_LAYERED, WS_EX_WINDOWEDGE = 0x00080000, 0x00000100
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_NCRENDERING_POLICY = 2

EFFECTS = [(0, "none"), (2, "Mica"), (3, "Acrylic"), (4, "Tabbed")]

OUT = Path(os.environ.get("LUMI_MICA_OUT", ROOT / "preview"))
BOARD = (60, 60, 1600, 1000)   # 彩条板（判材质"上没上"的对照组）
WIN = (400, 260, 900, 600)     # 空窗口


# ------------------------------------------------------------------ 读事实


def read_backdrop(win) -> int:
    value = ctypes.c_int(-1)
    dwmapi.DwmGetWindowAttribute(
        int(win.winId()), ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
        ctypes.byref(value), ctypes.sizeof(value),
    )
    return value.value


def report_window(label: str, win, engine) -> None:
    if win is None:
        print(f"  {label:9s}: (未创建)")
        return
    hwnd = int(win.winId())
    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    exstyle = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    bits = [n for n, v in (("WS_CAPTION", WS_CAPTION), ("WS_THICKFRAME", WS_THICKFRAME)) if style & v]
    ex_bits = [n for n, v in (("WS_EX_LAYERED", WS_EX_LAYERED), ("WS_EX_WINDOWEDGE", WS_EX_WINDOWEDGE)) if exstyle & v]
    utils = engine.singletonInstance("RinUI", "Utils")
    flag = None if utils is None else utils.property("backdropEnabled")
    print(
        f"  {label:9s}: backdrop={read_backdrop(win)} "
        f"Utils.backdropEnabled={flag} "
        f"style={'+'.join(bits) or '(none)'} exstyle={'+'.join(ex_bits) or '(none)'}"
    )


def set_backdrop(window, value: int) -> None:
    """给**单只**窗口打材质（绕开 RinUI 的全局广播，便于逐窗口对照）。"""
    hwnd = int(window.winId())
    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME)
    dark = ctypes.c_int(1)
    dwmapi.DwmSetWindowAttribute(
        hwnd, ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE), ctypes.byref(dark), ctypes.sizeof(dark)
    )
    ncr = ctypes.c_int(1)
    dwmapi.DwmSetWindowAttribute(
        hwnd, ctypes.c_uint(DWMWA_NCRENDERING_POLICY), ctypes.byref(ncr), ctypes.sizeof(ncr)
    )
    v = ctypes.c_int(value)
    dwmapi.DwmSetWindowAttribute(
        hwnd, ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE), ctypes.byref(v), ctypes.sizeof(v)
    )
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004)


def make_board(path: Path) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (BOARD[2], BOARD[3]), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    cols = [(255, 40, 40), (255, 180, 0), (255, 255, 0), (40, 220, 40),
            (0, 200, 255), (40, 60, 255), (200, 40, 255), (255, 255, 255)]
    band = BOARD[2] // len(cols)
    for i, colour in enumerate(cols):
        draw.rectangle([i * band, 0, (i + 1) * band, BOARD[3]], fill=colour)
    for y in range(0, BOARD[3], 16):
        draw.line([(0, y), (BOARD[2], y)], fill=(0, 0, 0), width=3)
    img.save(path)


def sample(png: Path, rect) -> str:
    """在窗口矩形里取左/中/右三点：三点同色 = 材质铺满（纯色材质），
    三点不同 = 看到的是身后的内容（窗口只是透明，材质没上）。"""
    from PIL import Image

    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    left, top = round(rect.x() * dpr) + 12, round(rect.y() * dpr) + 12
    right, bottom = round((rect.x() + rect.width()) * dpr) - 12, round((rect.y() + rect.height()) * dpr) - 12
    img = Image.open(png).convert("RGB")
    mid_y = (top + bottom) // 2
    span = max(1, (right - left) // 8)
    pts = [img.getpixel((left + span, mid_y)),
           img.getpixel(((left + right) // 2, mid_y)),
           img.getpixel((right - span, mid_y))]
    same = len(set(pts)) == 1
    verdict = "**纯色 → 材质已生效**" if same else "三点不同色 → 只见身后内容（材质没上）"
    return f"{pts[0]} / {pts[1]} / {pts[2]} … {verdict}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    print(f"Windows 版本: {sys.getwindowsversion().build}  is_win11={is_win11()} is_win11_22h2={is_win11_22h2()}")

    cfg = Config()
    cfg.set("app.backdrop", "mica", persist=False)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(ROOT / "ui"))
    rinui.setTheme(Theme.Dark)
    rinui.load(ROOT / "ui" / "QuickPanel.qml")
    # ⚠️ setBackdropEffect 会**持久化进 RinUI 自己的配置**（RinUI/config/rin_ui.json），
    # 跑完必须还原 —— 否则下次启动 launcher.load() 会先按这个残留值铺材质。
    previous_effect = rinui.theme_manager.get_backdrop_effect()
    rinui.setBackdropEffect(BackdropEffect.Mica)

    windows = WindowManager(rinui.engine, cfg, None, None, rinui=rinui)
    windows.show_settings()
    windows.show_debug()
    windows.show_editor()

    board_png = OUT / "_mica_board.png"
    make_board(board_png)
    board = QWidget()
    board.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
    board.setGeometry(*BOARD)
    label = QLabel(board)
    label.setPixmap(QPixmap(str(board_png)))
    label.setScaledContents(True)
    label.resize(BOARD[2], BOARD[3])

    empty = QQuickWindow()
    empty.setFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
    empty.setColor(Qt.transparent)
    empty.setGeometry(*WIN)

    screen = QGuiApplication.primaryScreen()
    shots: list[tuple[str, Path, object]] = []

    def step(index: int) -> None:
        if index >= len(EFFECTS):
            finish()
            return
        value, name = EFFECTS[index]
        set_backdrop(empty, value)
        QTimer.singleShot(500, lambda: capture(value, name, index))

    def capture(value: int, name: str, index: int) -> None:
        path = OUT / f"_mica_{name}.png"
        screen.grabWindow(0).save(str(path))
        shots.append((name, path, empty.frameGeometry()))
        step(index + 1)

    def finish() -> None:
        print("\n=== 1. 应用窗口：材质打上了吗 ===")
        report_window("panel", rinui.root_window, rinui.engine)
        report_window("settings", windows.settings, rinui.engine)
        report_window("debug", windows.debug, rinui.engine)
        report_window("editor", windows.editor, rinui.engine)

        print("\n=== 2. 空窗口：材质看得见吗（背后是彩条板）===")
        for name, path, rect in shots:
            print(f"  {name:8s} 采样 {sample(path, rect)}  → {path.name}")
        print(
            "\n提示：纯色即材质生效。深色档 Mica 基色 = #202020，与本项目背景色同色，"
            "所以「开着像没开」属正常；Acrylic(3) 基色 #545454 明显更亮。"
        )
        # 还原 RinUI 的持久化材质（见开头说明）
        try:
            back = {"none": BackdropEffect.None_, "mica": BackdropEffect.Mica,
                    "acrylic": BackdropEffect.Acrylic, "tabbed": BackdropEffect.Tabbed}
            rinui.setBackdropEffect(back.get(str(previous_effect), BackdropEffect.None_))
        except Exception:
            pass
        app.quit()

    def begin() -> None:
        board.show()
        board.raise_()
        empty.show()
        empty.raise_()
        empty.requestActivate()
        QTimer.singleShot(700, lambda: step(0))

    QTimer.singleShot(900, begin)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
