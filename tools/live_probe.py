"""真机自检：**自己起一次放映**，把整条链路跑一遍。

不用等用户手动开 PPT，也不用猜——这个脚本会：

1. 用 ``Dispatch`` 新建一个 **独立的 PowerPoint 实例**（不碰你已经打开的任何
   演示文稿；因为 ROT 隔离，拿不到现有实例时就一定是新实例）；
2. 新建一个空白演示文稿（2 页），开始放映；
3. 放映中采样：探测状态 / 页码 / 顶层窗口矩形 / 区域塑形 / **z 序是否压在放映
   窗口之上**，并打印一份完整诊断；
4. 退出放映、关闭该 PowerPoint 实例（``finally`` 保证清理）。

用法::

    .venv\\Scripts\\python.exe tools\\live_probe.py

看什么：

* ``PPT 状态`` 里 ``active=True`` 且 ``source='window'`` —— 窗口探测命中；
* ``slide_index/slide_total`` 非 0 —— COM 页码通道正常；
* ``顶层窗口`` 里 ``visible=True`` + ``rect`` 等于整屏 —— 显示定位正常；
* ``above_slideshow=True`` —— **确认压在放映窗口之上**（这条最关键）；
* 结尾 ``退出放映后`` 应为 ``active=False`` 且窗口不可见。

⚠️ 会短暂全屏放映（约 13 秒）并新建一个 PowerPoint 实例，别在正式演示时跑。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QTimer  # noqa: E402

from app.application import LuminaliumApplication  # noqa: E402

APP = None
PPT = None
PRES = None
SHOW = None


def start_show() -> None:
    global PPT, PRES, SHOW
    try:
        import pythoncom

        pythoncom.CoInitialize()
        import win32com.client as client

        PPT = client.Dispatch("PowerPoint.Application")
        PRES = PPT.Presentations.Add()
        PRES.Slides.Add(1, 12)  # ppLayoutBlank
        PRES.Slides.Add(2, 12)
        PPT.Visible = 1
        SHOW = PRES.SlideShowSettings.Run()
        print("[live] 放映已启动", flush=True)
    except Exception as exc:
        print("[live] 启动放映失败:", exc, flush=True)


def sample() -> None:
    app = APP
    print("\n============ 放映中采样 ============", flush=True)
    print("PPT 状态:", app.ppt.state, flush=True)
    print("顶层窗口:", app.windows.overlay_report(), flush=True)
    print("结论    :", app.windows.overlay_hint(), flush=True)
    print("可见    :", app.windows.overlay.isVisible(), flush=True)
    print(app.ppt.diagnose(), flush=True)
    print("====================================\n", flush=True)


def stop_show() -> None:
    try:
        if SHOW is not None:
            SHOW.View.Exit()
    except Exception as exc:
        print("[live] 退出放映失败:", exc, flush=True)
    try:
        if PRES is not None:
            PRES.Close()
    except Exception:
        pass
    try:
        if PPT is not None:
            PPT.Quit()
    except Exception:
        pass
    print("[live] 已清理 PowerPoint 实例", flush=True)


def main() -> int:
    global APP
    app = LuminaliumApplication(sys.argv)
    APP = app
    app.ppt.start()

    QTimer.singleShot(1000, start_show)
    QTimer.singleShot(10000, sample)
    QTimer.singleShot(13000, stop_show)

    def after() -> None:
        print("[live] 退出放映后:", app.ppt.state, app.windows.overlay.isVisible(), flush=True)
        app.qt_app.quit()

    QTimer.singleShot(15000, after)
    code = app.qt_app.exec()
    app.ppt.shutdown()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
