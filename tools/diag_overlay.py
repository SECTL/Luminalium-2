"""真机诊断：放映时「顶层窗口到底看得见吗」。

**不需要改动任何配置**，直接在 PPT 放映过程中运行::

    .venv\\Scripts\\python.exe tools/diag_overlay.py

它会同时做两件事，用于把问题二分:

1. 用真实代码路径（``app.windows``）把顶层窗口 + 控制条显示出来 ``--seconds`` 秒；
2. 在屏幕中央额外显示一个**纯红实心方块**（不透明、无透明材质、同样 TOPMOST）。

判定方法::

    看到控制条           -> 修好了
    只看到红方块         -> 我们的渲染链路有问题，看下面 report 里的 exstyle / region
    两个都看不到         -> 这块屏 / 演示软件压根不允许别的窗口盖上去
                           （例如 PowerPoint 硬件图形加速导致它走了独占呈现），
                           属于环境限制，与本项目代码无关

同时会把一份自诊断 ``report`` 打到 stdout：窗口句柄、扩展样式、真实矩形、
DWM 是否披风化、区域塑形是否生效、以及它排不排在放映窗口之上。
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from app.application import LuminaliumApplication  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402
from app.windows import _dwm_cloaked  # noqa: E402

GWL_EXSTYLE = -20


def ex_style(hwnd: int) -> str:
    style = ctypes.windll.user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE) & 0xFFFFFFFF
    return f"0x{style:08X}"


def _make_probe_box(seconds: int) -> QWidget:
    """一块不透明红方块：用来判定「这块屏到底能不能被别的窗口盖住」。"""
    box = QWidget(
        None,
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
        | Qt.WindowType.WindowDoesNotAcceptFocus,
    )
    box.setFixedSize(360, 120)
    box.setStyleSheet("background: #FF0000;")
    return box


def main() -> int:
    parser = argparse.ArgumentParser(description="顶层窗口真机诊断")
    parser.add_argument("--seconds", type=int, default=12, help="显示多久（默认 12 秒）")
    parser.add_argument("--no-box", action="store_true", help="不显示红色测试方块")
    args = parser.parse_args()

    app = LuminaliumApplication(sys.argv)

    # 用真实链路把顶层窗口叫出来（跳过 PPT 探测，直接注入放映中状态）
    app.ppt.inject_state(
        PresentationState(active=True, slide_index=26, slide_total=41)
    )

    box = None
    if not args.no_box:
        screen = QApplication.primaryScreen()
        box = _make_probe_box(args.seconds)
        geometry = screen.geometry()
        box.move(
            geometry.x() + (geometry.width() - box.width()) // 2,
            geometry.y() + (geometry.height() - box.height()) // 2,
        )
        box.show()

    def report() -> None:
        overlay = app.windows.overlay
        print("\n=============== 顶层窗口自诊断 ===============")
        print(app.windows.overlay_report())
        if overlay is not None:
            hwnd = int(overlay.winId())
            print(f"  exstyle(文本) = {ex_style(hwnd)}")
            print(f"  DWM cloaked   = {_dwm_cloaked(hwnd)}")
        print(f"  区域塑形      = {app.windows._region_mode} "
              f"（倍率 {app.windows._region_scale}）")
        print(f"  控制条 x{len(app.windows._docks)}: {list(app.windows._docks)}")
        print("=============================================")
        print(f"\n请在 {args.seconds} 秒内看屏幕：")
        print("  · 左下应有工具条、右下应有页码 pill")
        print("  · 屏幕正中应有一块红色方块（判定屏幕是否允许叠加）\n")
        sys.stdout.flush()

    QTimer.singleShot(1200, report)

    def finish() -> None:
        if box is not None:
            box.close()
        app.qt_app.quit()

    QTimer.singleShot(args.seconds * 1000, finish)

    print("已在真实位置显示顶层窗口；保持 PPT 放映，看屏幕上有没有东西...")
    code = app.qt_app.exec()
    app.ppt.shutdown()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
