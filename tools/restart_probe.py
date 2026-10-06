#!/usr/bin/env python
"""开发用：验证「改到需要重启的设置项」时的提示链路（标题栏按钮 + 询问框）。

对应 ClassIsland ``ClassIsland/Views/SettingsWindowNew.axaml{,.cs}``：::

    private void CommandBindingRestartApp_OnExecuted(...)
    {
        ViewModel.IsRequestedRestart = true;   // → 标题栏亮出「需要重启」按钮
        ShowRestartDialog();                   // → 立刻弹框问一次
    }

    原标题「需要重启」/ 正文「部分设置需要重启以应用」/ 主按钮「重启」/ 次按钮「取消」

本项目把「请求」这一步挪进了 ``Backend.setSetting``（见 ``RESTART_REQUIRED_KEYS``），
所以这里直接改设置就能把整条链路走通，不用去点 QML 控件。

验的东西：
* 初始不亮按钮、不弹框；
* 改 ``language``（要重启）→ ``restartPending`` 翻 true + 按钮可见 + 框弹出，
  且四处文案与 ClassIsland 逐字一致；
* 点「取消」→ 框关掉，但**按钮留着**（ClassIsland 的 ``IsRequestedRestart`` 同样不复位）；
* 点「重启」→ 发 ``restartRequested``（探针里没接应用层，不会真的重启）；
* 改**不**需要重启的项 → 不发 ``restartSuggested``、不弹框；
* 标题栏版式：按钮落在 ``titleBarHost`` 内（不被 ``clip`` 裁）、且在版本号左侧。

⚠️ 用临时用户配置（与 ``update_probe.py`` 同款），不碰真 ``config/config.json``。
⚠️ 会 ``setTheme`` → 记原值并在收尾还原 + 落盘，否则污染 ``rin_ui.json``。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QObject, QUrl, QTimer  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RinConfig  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402

OFFSCREEN = -6000
#: 本探针固定跑深色，文件名后缀跟着写死（别与其它工具撞名）。
THEME_TAG = "dark"

FAILURES: list[str] = []
#: ``restartSuggested`` 被发了几次（改「不需要重启」的项时应当不增）。
SUGGESTED = 0
#: ``restartRequested`` 被发了几次（点「重启」应当 +1）。
REQUESTED = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {label}" + (f" —— {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def pump(app, ms: float) -> None:
    """GIL 友好的事件泵（``qWait`` 会饿死线程）。"""
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.005)


def wait_until(app, predicate, timeout: float = 3000.0,
               step: float = 40.0) -> bool:
    """轮询等到 ``predicate()`` 为真，超时返回 False。

    ⚠️ **别用固定 ``pump()`` 等 RinUI 的对话框**：它带进/退场过渡
    （``Dialog.qml`` 的 ``enter`` / ``exit``，各 ~600ms），而 ``visible``
    要等**退场动画跑完**才落 false、``onOpened``（里面才设主按钮高亮）
    要等**进场动画跑完**才发 —— 实测（2026-10-05）：

    ::

        close() 后  +60ms  visible=True  opacity=0.33
                   +160ms  visible=True  opacity=0.00
                   +900ms  visible=False        ← 这里才关
        open()  后  +600ms  scale=1.001（还在动）highlighted=False
                  +2000ms  scale=1.000         highlighted=True

    也就是说「等 400ms 就断言」会稳定失败两处，而这是**等待不够**不是缺陷。
    又因为动画由渲染循环推进，窗口离屏时更慢，所以这里一律轮询。
    """
    end = time.perf_counter() + timeout / 1000.0
    while time.perf_counter() < end:
        if predicate():
            return True
        app.processEvents()
        time.sleep(step / 1000.0)
    return predicate()


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def find_by_name(item, name: str):
    for node in walk(item):
        if node.objectName() == name:
            return node
    return None


def find_obj(root_obj, name: str):
    """按 objectName 找**任意** QObject 子代。

    ⚠️ ``Rin.Dialog`` 是 ``QQC2.Dialog``（Popup），**不在** ``QQuickItem`` 那棵树里
    —— 它是窗口 ``freeContainter.data`` 的成员、渲染时挂在 Overlay 上，
    所以只遍历 ``childItems()`` 是**永远找不到**它的（实测第一版就这么扑空）。
    这类非 Item 的对象要走 ``QObject.findChild``。
    """
    return root_obj.findChild(QObject, name) if root_obj is not None else None


def main() -> int:
    global SUGGESTED, REQUESTED

    tmp_config = Path(tempfile.gettempdir()) / "lumi_restart_probe_config.json"
    tmp_config.write_text("{}", encoding="utf-8")
    config = Config(user_file=str(tmp_config))

    real_config = ROOT / "config" / "config.json"
    real_before = real_config.read_text(encoding="utf-8") if real_config.exists() else ""
    real_mtime = real_config.stat().st_mtime_ns if real_config.exists() else 0

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, app)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    # ⚠️ setTheme 会落盘到 RinUI/config/rin_ui.json → 记原值，收尾还原。
    previous_theme = rinui.theme_manager.get_theme_name()
    previous_effect = rinui.theme_manager.get_backdrop_effect()
    rinui.setTheme(Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(UI_DIR / "QuickPanel.qml")
    rinui.root_window.setPosition(OFFSCREEN, OFFSCREEN)
    rinui.root_window.show()

    # 统计两个信号
    def _on_suggested() -> None:
        global SUGGESTED
        SUGGESTED += 1

    def _on_requested() -> None:
        global REQUESTED
        REQUESTED += 1

    backend.restartSuggested.connect(_on_suggested)
    backend.restartRequested.connect(_on_requested)

    component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "Settings.qml")))
    if component.isError():
        for error in component.errors():
            print("SETTINGS ERROR:", error.toString())
        return 1
    window = component.createWithInitialProperties({"visible": True})
    if window is None:
        for error in component.errors():
            print("SETTINGS CREATE ERROR:", error.toString())
        return 1
    window._component = component
    window.setPosition(OFFSCREEN - 900, OFFSCREEN - 900)
    window.show()
    pump(app, 900)

    root = window.contentItem()
    button = find_by_name(root, "settingsRestartButton")
    version = find_by_name(root, "settingsVersionLabel")
    # ⚠️ 对话框是 Popup，走 find_obj（见该函数注释）
    dialog = find_obj(window, "settingsRestartDialog")

    # ==================================================== A. 初始态
    check("「需要重启」按钮存在", button is not None)
    check("重启询问框存在", dialog is not None)
    if button is None or dialog is None:
        app.quit()
        return 1
    check("初始不显示「需要重启」按钮", not bool(button.property("visible")))
    check("初始 restartPending = false",
          backend.property("restartPending") is False)
    check("初始不弹框", not bool(dialog.property("visible")))

    # ==================================================== B. 改「要重启」的项
    backend.setSetting("language", "en_US")
    wait_until(app, lambda: bool(dialog.property("visible")))

    check("改语言后 restartPending = true",
          backend.property("restartPending") is True)
    check("标题栏「需要重启」按钮亮出", bool(button.property("visible")))
    check("询问框自动弹出", bool(dialog.property("visible")))
    if not bool(dialog.property("visible")):
        # 诊断：Popup 没开是「Connections 没调到」还是「开了但没生效」
        print("   [诊断] dialog.parent =", dialog.property("parent"))
        print("   [诊断] dialog.visible =", dialog.property("visible"))
        dialog.open()
        pump(app, 300)
        print("   [诊断] 手动 open() 后 opened =", dialog.property("visible"))
        dialog.close()
        pump(app, 200)
    check("restartSuggested 发了 1 次", SUGGESTED == 1, f"{SUGGESTED}")

    # 四处文案与 ClassIsland 逐字一致
    check("框标题 = 需要重启",
          str(dialog.property("title") or "") == "需要重启",
          str(dialog.property("title") or ""))
    body = find_obj(dialog, "settingsRestartDialogBody")
    check("框正文 = 部分设置需要重启以应用",
          body is not None and str(body.property("text") or "") == "部分设置需要重启以应用",
          str(body.property("text") or "") if body is not None else "<无正文项>")
    # ---------------------------------------------------------------- 正文样式
    # 2026-10-05 修的真 bug：正文原先写成 ``Lumi.textSecondary``（灰），而 WinUI /
    # ClassIsland 的 ``ContentDialog.Content`` 走的是 TextFillColorPrimary（实色），
    # 于是「标题实色 + 正文灰」看着不像一套。这里把层级钉住，防再退化。
    # ⚠️ 判据取「与同类差多少」而不是写死色值：主题一换具体 RGB 全变。
    ci = dialog.property("contentItem")
    title_label = None
    if ci is not None:
        for node in walk(ci):
            if str(node.property("text") or "") == "需要重启":
                title_label = node
                break
    # 已知是 textSecondary 的那枚（标题栏版本号），拿来当「灰」的参照物
    secondary_label = version

    if body is None or title_label is None:
        check("正文/标题都在 ContentLayout 里", False,
              f"body={body is not None}, title={title_label is not None}")
    else:
        bc = QColor(body.property("color"))
        tc = QColor(title_label.property("color"))
        check("正文是实色（与标题同一个前景）", bc == tc,
              "" if bc == tc else f"body={bc.name(QColor.HexArgb)} title={tc.name(QColor.HexArgb)}")
        if secondary_label is not None:
            sc = QColor(secondary_label.property("color"))
            check("正文没掉回 secondary 灰", bc != sc,
                  "" if bc != sc else f"都成了 {bc.name(QColor.HexArgb)}")
        # ⚠️ Rin.Text 设的是 ``font.pixelSize``（不是 pointSize），拿 pointSizeF 会读到 -1
        bs = float(body.property("font").pixelSize())
        ts = float(title_label.property("font").pixelSize())
        check("正文比标题小一级（Subtitle > Body）", 0 < bs < ts,
              "" if 0 < bs < ts else f"body={bs} title={ts}")

    cancel_button = find_obj(dialog, "settingsRestartCancelButton")
    confirm_button = find_obj(dialog, "settingsRestartConfirmButton")
    check("次按钮 = 取消",
          cancel_button is not None and str(cancel_button.property("text") or "") == "取消",
          str(cancel_button.property("text") or "") if cancel_button else "<无>")
    check("主按钮 = 重启",
          confirm_button is not None and str(confirm_button.property("text") or "") == "重启",
          str(confirm_button.property("text") or "") if confirm_button else "<无>")
    # ⚠️ 高亮由 ``onOpened`` 设，而它要等**进场动画跑完**才发（见 wait_until 注释）
    wait_until(app, lambda: bool(confirm_button.property("highlighted")))
    check("主按钮高亮（DefaultButton=Primary 的对应物）",
          confirm_button is not None and bool(confirm_button.property("highlighted")))

    # ==================================================== C. 点「取消」
    cancel_button.clicked.emit()
    wait_until(app, lambda: not bool(dialog.property("visible")))
    check("点取消后框关掉", not bool(dialog.property("visible")))
    check("点取消后按钮仍留着（restartPending 不复位）",
          bool(button.property("visible")))
    check("点取消时没有触发重启", REQUESTED == 0, f"{REQUESTED}")

    # ==================================================== D. 再点标题栏那枚按钮，弹框 + 点「重启」
    button.clicked.emit()
    wait_until(app, lambda: bool(dialog.property("visible")))
    check("点标题栏按钮能再次弹框", bool(dialog.property("visible")))
    confirm_button.clicked.emit()
    wait_until(app, lambda: not bool(dialog.property("visible")))
    check("点重启后框关掉", not bool(dialog.property("visible")))
    check("点重启发出 restartRequested", REQUESTED == 1, f"{REQUESTED}")

    # ==================================================== E. 改不需要重启的项
    before = SUGGESTED
    backend.setSetting("panel_shortcuts_locked", True)
    pump(app, 400)
    check("改普通设置不发 restartSuggested", SUGGESTED == before,
          f"{before} -> {SUGGESTED}")
    check("改普通设置不弹框", not bool(dialog.property("visible")))

    # ==================================================== F. 标题栏版式
    if version is not None:
        bx = float(button.mapToItem(root, 0, 0).x())
        by = float(button.mapToItem(root, 0, 0).y())
        bw = float(button.property("width"))
        bh = float(button.property("height"))
        vx = float(version.mapToItem(root, 0, 0).x())
        check("「需要重启」在版本号左侧", bx + bw <= vx + 1.0,
              f"按钮右缘 {bx + bw:.0f} / 版本号左缘 {vx:.0f}")

        # ⚠️ ``titleBarHost`` 带 ``clip: true``，越界会被**裁掉**（版本号那段
        # 注释里记过这个坑），所以必须比右缘。
        host = button.parentItem()
        if host is not None:
            hx = float(host.mapToItem(root, 0, 0).x())
            hy = float(host.mapToItem(root, 0, 0).y())
            hw = float(host.property("width"))
            hh = float(host.property("height"))
            check("按钮没越出标题栏托管区（否则会被 clip 裁）",
                  bx + bw <= hx + hw + 1.0,
                  f"按钮右缘 {bx + bw:.0f} / 托管区右缘 {hx + hw:.0f}")
            check("按钮高度落在标题栏内（32 高那条）", 16 <= bh <= hh + 0.5,
                  f"按钮 {bh:.0f} / 标题栏 {hh:.0f}")
            off = abs((by + bh / 2) - (hy + hh / 2))
            check("按钮竖直居中于标题栏", off <= 4.0, f"中心差 {off:.1f}px")

    # ==================================================== G. 出一张剧情图
    # 最后把「标题栏亮着『需要重启』+ 询问框开着」这个样子存下来给人工目检。
    # ⚠️ 别和其它工具抢文件名（本文件固定前缀 ``restart_prompt_*``）。
    restartDialog_png = ROOT / "preview" / f"restart_prompt_{THEME_TAG}.png"
    button.clicked.emit()
    wait_until(app, lambda: bool(dialog.property("visible")))
    wait_until(app, lambda: bool(confirm_button.property("highlighted")))
    window.grabWindow()          # 丢第一帧：待处理的场景图更新要推进一次才落进画面
    img = window.grabWindow()
    if img.isNull():
        check("剧情图已生成", False, "grabWindow() 返回空图")
    else:
        img.save(str(restartDialog_png))
        check("剧情图已生成", True,
              f"{restartDialog_png.name} ({img.width()}x{img.height()})")

    # ==================================================== H. 真配置未被碰
    if real_config.exists():
        check("真配置未被本次探针改动",
              real_config.read_text(encoding="utf-8") == real_before,
              f"{real_config.stat().st_mtime_ns} vs {real_mtime}")

    # ---- 收尾：还原主题 / 背景特效并落盘 ----
    if rinui.theme_manager.get_theme_name() != previous_theme:
        rinui.theme_manager.toggle_theme(previous_theme)
        RinConfig.save_config()
        print(f"[OK] 主题已还原并落盘为 {previous_theme}")
    if rinui.theme_manager.get_backdrop_effect() != previous_effect:
        rinui.theme_manager.apply_backdrop_effect(previous_effect)
        RinConfig.save_config()
        print(f"[OK] 背景特效已还原为 {previous_effect}")

    print()
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
