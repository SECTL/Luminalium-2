"""开发用：诊断「窗口背景材质（Mica / Acrylic / Tabbed）到底有没有生效」。

背景
----

2026-10-01 用户报告「RinUI 的 Mica 失效了」，当时写的是「两问法」：
读回 ``DWMWA_SYSTEMBACKDROP_TYPE`` + 另建一只空窗口、背后铺彩条板、截屏采样。
**那套已经不可用了**：

* 脚本自己手搓 ``WindowManager(..., backend=None, ...)``，一调
  ``windows.show_settings()`` 就 ``AttributeError: 'NoneType' object has no
  attribute 'refreshSettings'`` —— 从写下那天起就没跑通过；
* 彩条板 + 全屏截图这条路实测**极不稳定**：``WindowStaysOnBottomHint`` 会把板子
  压到桌面（Progman）之下，板子经常一个像素都没画出来，于是「采样到纯色」既可以
  是「材质生效」也可以是「板子没画 + 身后恰好是纯色」，判据整个失效；
* 而且它会把用户桌面截进去。

现在的做法
----------

**驱动真实的 ``LuminaliumApplication``**（用临时数据目录，不碰用户配置），然后问三件事：

1. **配置解析** —— ``app.backdrop`` 解析成了哪个 ``BackdropEffect``
   （``auto`` 应该按平台落到 mica / acrylic / none）；
2. **事实** —— 每个顶层窗口的 ``DWMWA_SYSTEMBACKDROP_TYPE`` / 暗色位 / 窗口样式，
   以及 QML 侧 ``Utils.backdropEnabled``；
3. **看不看得见** —— 抓窗口**自身渲染结果**（``QQuickWindow.grabWindow``，不截屏、
   不含桌面）看 alpha：客户区是半透明/全透明（``alpha < 255``）才轮得到 DWM 合成
   材质；整片 255 就是被 QML 画死了，材质再对也看不见。

⚠️ 第 3 问只回答「客户区有没有被画死」，**回答不了**「材质是 Mica 还是纯色」——
深色档 Mica 的基色实测就是 ``#202020``，与本项目 ``colors.backgroundColor``
完全同色，所以「开着 Mica 看着像没开」是正常现象，不是失效。

用法::

    .venv\\Scripts\\python.exe tools\\mica_probe.py [none|auto|mica|acrylic|tabbed]
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EFFECT = (sys.argv[1] if len(sys.argv) > 1 else "auto").lower()

#: 临时数据目录：``Config`` 用的是 ``app.config.USER_CONFIG_FILE`` 这个模块级
#: 名字（``app.paths`` 只在导入时解析一次 ``DATA_DIR``，环境变量对它无效），
#: 所以直接替换它，别去动用户的 ``config/config.json``。
#:
#: ⚠️ 临时配置要**从用户真实配置拷一份再改 backdrop**，不能只写 ``{"app":
#: {"backdrop": ...}}``：那样 ``accent`` / ``theme`` 会退回默认值，而
#: ``LuminaliumApplication`` 启动时会把它们写进 RinUI 自己的持久化配置
#: （``RinUI/config/rin_ui.json``）—— 等于用一次探针把用户的主题色和明暗覆盖掉。
TMP = ROOT / "preview" / "_mica_probe_tmp"
(TMP / "config").mkdir(parents=True, exist_ok=True)
from app.paths import USER_CONFIG_FILE as REAL_USER_CONFIG  # noqa: E402

try:
    _real = json.loads(REAL_USER_CONFIG.read_text(encoding="utf-8"))
except Exception:  # 用户还没改过配置 / 文件损坏 —— 用空配置即可
    _real = {}
_real.setdefault("app", {})["backdrop"] = EFFECT
(TMP / "config" / "config.json").write_text(
    json.dumps(_real, ensure_ascii=False), encoding="utf-8"
)
os.chdir(ROOT)

import app.config as app_config  # noqa: E402

app_config.USER_CONFIG_FILE = TMP / "config" / "config.json"
app_config.CONFIG_DIR = TMP / "config"

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402

from app.application import LuminaliumApplication  # noqa: E402

dwmapi = ctypes.windll.dwmapi
user32 = ctypes.windll.user32

GWL_STYLE = -16
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_WINDOW_CORNER_PREFERENCE = 33


def read_int(hwnd: int, attr: int) -> int:
    value = ctypes.c_int(-1)
    dwmapi.DwmGetWindowAttribute(
        ctypes.c_void_p(hwnd), ctypes.c_uint(attr),
        ctypes.byref(value), ctypes.sizeof(value),
    )
    return value.value


def report_window(label: str, win) -> None:
    if win is None:
        print(f"  {label:9s}: (未创建)")
        return
    hwnd = int(win.winId())
    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    bits = [n for n, v in (("WS_CAPTION", WS_CAPTION),
                           ("WS_THICKFRAME", WS_THICKFRAME)) if style & v]
    print(
        f"  {label:9s}: hwnd={hwnd} backdrop={read_int(hwnd, DWMWA_SYSTEMBACKDROP_TYPE)} "
        f"dark={read_int(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE)} "
        f"corner={read_int(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE)} "
        f"style={'+'.join(bits) or '(none)'} visible={win.isVisible()}"
    )


def alpha_verdict(win) -> str:
    """看窗口**自身渲染结果**的 alpha —— 不截屏，拿不到任何桌面内容。"""
    if win is None or not win.isVisible() or not isinstance(win, QQuickWindow):
        return "(不可见 / 非 QQuickWindow，跳过)"
    img = win.grabWindow()
    if img.isNull():
        return "grabWindow() 返回空图"
    img = img.convertToFormat(img.Format.Format_ARGB32)
    w, h, step = img.width(), img.height(), 4
    opaque = transparent = counted = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            a = img.pixelColor(x, y).alpha()
            counted += 1
            if a == 255:
                opaque += 1
            elif a == 0:
                transparent += 1
    if opaque / max(1, counted) > 0.95:
        return (f"全不透明 {opaque / counted:.1%} → 客户区被画死了，"
                "DWM 材质再对也看不见")
    return (f"不透明 {opaque / counted:.1%} / 全透明 {transparent / counted:.1%} "
            "→ 客户区是透的，材质有机会露出来")


def main() -> int:
    app = LuminaliumApplication([])
    tm = app.rinui.theme_manager
    print(f"Windows 版本: {sys.getwindowsversion().build}")
    print(f"[1] app.backdrop = {app.config.get('app.backdrop')!r}"
          f"  → RinUI 实际生效 = {tm.get_backdrop_effect()!r}")

    def stage2() -> None:
        app.windows.show_settings()
        app.windows.show_editor()
        QTimer.singleShot(1800, stage3)

    def stage3() -> None:
        utils = app.rinui.engine.singletonInstance("RinUI", "Utils")
        print(f"\n[2] Utils.backdropEnabled = "
              f"{None if utils is None else utils.property('backdropEnabled')}")
        print(f"    ThemeManager.windows = {tm.windows}")
        for label, win in (
            ("panel", app.windows.panel),
            ("settings", app.windows.settings),
            ("editor", app.windows.editor),
        ):
            report_window(label, win)

        print("\n[3] 客户区透明度（窗口自身渲染，不含桌面）")
        for label, win in (("settings", app.windows.settings),
                           ("editor", app.windows.editor)):
            print(f"  {label:9s}: {alpha_verdict(win)}")

        print(f"\n临时数据目录（可删）: {TMP}")
        app.quit()

    QTimer.singleShot(2200, stage2)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
