"""开发用探针：遮罩「智能跟随」两件套（2026-10-06 用户指令）。

    「其实我觉得放映工具顶层窗口可以更智能些，比如说放映窗口不在前台时
      自动临时隐去，另外根据放映窗口的大小和位置自动调节遮罩总大小和位置。」

不依赖 PowerPoint：拿**本进程里的快捷面板**当假的放映窗口（一只真实存在、
几何随便改的 Win32 窗口），把它的 hwnd 塞进注入的 ``PresentationState``。
「不在前台」那一档用 ``Progman``（explorer.exe 的桌面窗口）当假放映窗口 ——
它一定不是当前前台，而且**跨进程**，正好压到「同进程才算前台」那条判据。

跑法：

    .venv\\Scripts\\python.exe tools\\probe_follow.py
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from app.application import LuminaliumApplication  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402
from app.windows import (  # noqa: E402
    GWL_EXSTYLE,
    WS_EX_TRANSPARENT,
    _foreground_window,
    _logical_rect_from_native,
    _window_pid,
    _window_rect,
)

RESULTS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")


def skip(label: str, why: str) -> None:
    RESULTS.append(f"[SKIP] {label} — {why}")


def _progman() -> int:
    """explorer.exe 的桌面窗口（一个确定存在的**外部进程**窗口）。"""
    try:
        return int(ctypes.windll.user32.FindWindowW("Progman", None) or 0)
    except OSError:
        return 0


def main() -> int:
    app = LuminaliumApplication(sys.argv)
    qt_app = app.qt_app

    def run_checks() -> None:
        wm = app.windows
        overlay = wm.overlay
        panel = wm.panel
        check("顶层窗口已创建", overlay is not None and panel is not None)
        if overlay is None or panel is None:
            return

        check(
            "默认配置里有三个新键",
            app.config.get("presentation.follow_window_rect") is True
            and app.config.get("presentation.follow_foreground") is True
            and int(app.config.get("presentation.follow_interval_ms") or 0) == 200,
            f"{app.config.get('presentation.follow_window_rect')}/"
            f"{app.config.get('presentation.follow_foreground')}/"
            f"{app.config.get('presentation.follow_interval_ms')}",
        )

        # ---------------------------------------------------------- 假放映窗口
        # 快捷面板：本进程里的真窗口，几何我说了算。
        panel.setGeometry(240, 160, 800, 500)
        panel.show()
        QTest.qWait(200)
        panel_hwnd = int(panel.winId())
        fake_rect = _window_rect(panel_hwnd)
        check("假放映窗口（快捷面板）有真实矩形", bool(fake_rect), f"{fake_rect}")
        if not fake_rect:
            return

        # ------------------------------------------------- ① 遮罩跟随放映窗口
        app.ppt.inject_state(
            PresentationState(active=True, slide_index=1, slide_total=9,
                              window_handle=panel_hwnd)
        )
        QTest.qWait(400)
        screen = QGuiApplication.screenAt(panel.position()) or QGuiApplication.primaryScreen()
        geom = screen.geometry()
        rect = wm._overlay_rect
        expect = _logical_rect_from_native(screen, fake_rect)
        check(
            "遮罩尺寸跟随放映窗口（不是整屏）",
            rect is not None and rect.width() != geom.width(),
            f"遮罩={rect} 屏幕={geom.width()}x{geom.height()}",
        )
        check(
            "遮罩矩形 = 放映窗口矩形（逻辑换算）",
            rect is not None
            and abs(rect.width() - expect.width()) <= 2
            and abs(rect.height() - expect.height()) <= 2
            and abs(rect.x() - expect.x()) <= 2
            and abs(rect.y() - expect.y()) <= 2,
            f"{rect} vs {expect}",
        )
        check(
            "窗口实际几何 = 遮罩请求的几何（Qt 真吃下去了）",
            abs(overlay.width() - expect.width()) <= 2
            and abs(overlay.height() - expect.height()) <= 2
            and abs(overlay.x() - expect.x()) <= 2
            and abs(overlay.y() - expect.y()) <= 2,
            f"overlay=({overlay.x()},{overlay.y()},{overlay.width()}x{overlay.height()}) "
            f"期望={expect}",
        )

        # 控制条按**遮罩**（而不是屏幕）贴边
        dock = wm._docks.get("bottom_center")
        if dock is not None and rect is not None:
            margin_y = int(app.config.get("presentation.margin_y", 20))
            shadow = int(dock.property("shadowMargin") or 0)
            visual_bottom = rect.height() - (dock.y() + dock.height() - shadow)
            center_gap = abs((dock.x() + dock.width() / 2) - rect.width() / 2)
            check(
                "控制条按遮罩贴边（距遮罩下沿 = margin_y）",
                abs(visual_bottom - margin_y) <= 2,
                f"视觉={visual_bottom} 期望={margin_y} shadow={shadow}",
            )
            check(
                "控制条在遮罩里居中（不是屏幕中心）",
                center_gap <= 2,
                f"条中心 x={dock.x() + dock.width() / 2} 遮罩中心 x={rect.width() / 2}",
            )
        else:
            skip("控制条按遮罩贴边", "没有 bottom_center 控制条")

        # ------------------------------------------------- ② 窗口挪动 → 跟随
        panel.setGeometry(120, 90, 1000, 640)
        QTest.qWait(200)
        moved = _window_rect(int(panel.winId()))
        wm._watch_overlay()
        QTest.qWait(120)
        after = wm._overlay_rect
        expect_moved = _logical_rect_from_native(screen, moved)
        check(
            "看护一拍把遮罩跟到新几何（窗口拖动 / 缩放）",
            after is not None
            and abs(after.width() - expect_moved.width()) <= 2
            and abs(after.x() - expect_moved.x()) <= 2,
            f"{after} vs {expect_moved}",
        )
        if dock is not None and after is not None:
            margin_y = int(app.config.get("presentation.margin_y", 20))
            shadow = int(dock.property("shadowMargin") or 0)
            check(
                "挪动后控制条重摆到新遮罩里",
                abs((after.height() - (dock.y() + dock.height() - shadow)) - margin_y) <= 2,
                f"视觉={after.height() - (dock.y() + dock.height() - shadow)} 期望={margin_y}",
            )

        # ------------------------------------------------- ③ 全屏放映吸附整屏
        # ⚠️ 这一步不能用快捷面板当假窗口：它 QML 里写死 375×440 且 min/max
        # 也是这个数，``setGeometry`` 铺不满（QML 当场改回来，实测 800×500 →
        # 375×440）。改用 ``Progman`` —— 它铺满整块桌面，正好演「全屏放映」。
        progman = _progman()
        if not progman:
            skip("铺满显示器时吸附成整屏矩形", "找不到 Progman 窗口")
        else:
            app.ppt.inject_state(
                PresentationState(active=True, slide_index=1, slide_total=9,
                                  window_handle=progman)
            )
            QTest.qWait(400)
            primary = QGuiApplication.primaryScreen().geometry()
            check(
                "铺满显示器时吸附成整屏矩形（躲开那圈不可见边框）",
                wm._overlay_rect == primary,
                f"{wm._overlay_rect} vs {primary}",
            )

        # ------------------------------------------------- ④ 不在前台 → 隐去
        if not progman:
            skip("放映窗口不在前台时临时隐去", "找不到 Progman 窗口")
        else:
            check(
                "pid 判据有区分度（Progman 与本进程不同）",
                _window_pid(progman) != _window_pid(panel_hwnd),
                f"progman={_window_pid(progman)} 本进程={_window_pid(panel_hwnd)}",
            )
            app.ppt.inject_state(
                PresentationState(active=True, slide_index=1, slide_total=9,
                                  window_handle=progman)
            )
            QTest.qWait(500)
            ex = int(ctypes.windll.user32.GetWindowLongW(
                ctypes.wintypes.HWND(int(overlay.winId())), GWL_EXSTYLE))
            check(
                "放映窗口不在前台 → 控制条临时隐去",
                wm._suppressed is True
                and overlay.property("suppressed") is True
                and bool(ex & WS_EX_TRANSPARENT),
                f"suppressed={wm._suppressed} QML={overlay.property('suppressed')} "
                f"exstyle=0x{ex:08X}",
            )
            check(
                "隐去后遮罩没被 hide()（窗口还在，只淡出）",
                overlay.isVisible() and overlay.property("suppressed") is True,
                f"visible={overlay.isVisible()}",
            )
            container = overlay.property("container")
            check(
                "隐去真的是**淡出**（容器 opacity 落到 0）",
                container is not None and abs(float(container.property("opacity"))) <= 0.02,
                f"opacity={container.property('opacity') if container else None}",
            )

            # --------------------------------------- ⑤ 切回前台 → 自动恢复
            # ⚠️ 不依赖「真前台是谁」：本环境抢不到前台，而且真前台随时在变
            # （``GetForegroundWindow`` 返回 0 时判据直接算「不在前台」）→
            # 把「前台」指到放映窗口自己身上，测的是恢复链路，不是抢焦点。
            import app.windows as win_mod

            fg = _foreground_window()
            target = fg if fg else int(overlay.winId())
            _fg_hook = win_mod._foreground_window
            try:
                win_mod._foreground_window = lambda: target
                app.ppt.inject_state(
                    PresentationState(active=True, slide_index=1, slide_total=9,
                                      window_handle=target)
                )
                QTest.qWait(500)
                ex = int(ctypes.windll.user32.GetWindowLongW(
                    ctypes.wintypes.HWND(int(overlay.winId())), GWL_EXSTYLE))
                check(
                    "放映窗口回到前台 → 自动恢复",
                    wm._suppressed is False
                    and overlay.property("suppressed") is False
                    and not (ex & WS_EX_TRANSPARENT),
                    f"suppressed={wm._suppressed} QML={overlay.property('suppressed')} "
                    f"exstyle=0x{ex:08X}",
                )
                container = overlay.property("container")
                check(
                    "恢复也是淡入（容器 opacity 回到 1）",
                    container is not None
                    and abs(float(container.property("opacity")) - 1.0) <= 0.02,
                    f"opacity={container.property('opacity') if container else None}",
                )

                # 前台不是放映窗口、但**同进程**：不该隐去。
                # 这是「演示者视图在前台、放映窗口在第二块屏」的日常局面 ——
                # 只比句柄会把正常的双屏放映判成「用户切走了」，控制条一闪一闪。
                # 把「放映窗口」指回面板、「前台」指到本进程的另一只窗口上，
                # 直接测那条判据本身（真去抢前台不可靠）。
                app.ppt.inject_state(
                    PresentationState(active=True, slide_index=1, slide_total=9,
                                      window_handle=panel_hwnd)
                )
                QTest.qWait(400)
                win_mod._foreground_window = lambda: int(overlay.winId())
                # 上面那段 ``qWait`` 里看护已经用**旧**的前台值判过一轮了
                # （可能已把控制条隐去），所以这里必须再走一拍看护让它翻回来 ——
                # 只读 ``_slideshow_in_foreground()`` 会读到上一拍的残留状态。
                wm._watch_overlay()
                QTest.qWait(150)
                check(
                    "同进程的另一只窗口在前台 → 仍算放映在前台（不隐去）",
                    wm._slideshow_in_foreground() is True and wm._suppressed is False,
                    f"放映窗口=0x{panel_hwnd:08X} 前台=顶层窗口（同进程） "
                    f"suppressed={wm._suppressed}",
                )
                if progman:
                    win_mod._foreground_window = lambda: progman
                    check(
                        "外部进程的窗口在前台 → 判为不在前台",
                        wm._slideshow_in_foreground() is False,
                        f"放映窗口=0x{panel_hwnd:08X} 前台=Progman",
                    )
            finally:
                win_mod._foreground_window = _fg_hook

        # ------------------------------------------------- ⑥ 手动模式不隐去
        app.ppt.inject_state(
            PresentationState(active=True, slide_index=1, slide_total=9,
                              window_handle=progman or 0)
        )
        QTest.qWait(400)
        wm._manual_shown = True
        wm._set_overlay_suppressed(False)
        wm._watch_overlay()
        QTest.qWait(120)
        check(
            "手动显示（托盘菜单）不受「不在前台」影响",
            wm._suppressed is False,
            f"suppressed={wm._suppressed} manual={wm._manual_shown}",
        )
        wm._manual_shown = False

        # ---------------------------------------------- ⑦ 关配置项就退回旧行为
        app.config.set("presentation.follow_window_rect", False, persist=False)
        app.config.set("presentation.follow_foreground", False, persist=False)
        app.ppt.inject_state(
            PresentationState(active=True, slide_index=1, slide_total=9,
                              window_handle=panel_hwnd)
        )
        QTest.qWait(400)
        wm._watch_overlay()
        QTest.qWait(120)
        check(
            "两个开关关掉后：遮罩恒整屏、永不隐去（退回 2026-10-06 之前的行为）",
            wm._overlay_rect == geom and wm._suppressed is False,
            f"遮罩={wm._overlay_rect} suppressed={wm._suppressed}",
        )
        app.config.set("presentation.follow_window_rect", True, persist=False)
        app.config.set("presentation.follow_foreground", True, persist=False)

        check("诊断串带上了新状态", "临时隐去=" in wm.overlay_report(),
              wm.overlay_report())

    def guarded() -> None:
        try:
            run_checks()
        except Exception:
            traceback.print_exc()
            RESULTS.append("[FAIL] 探针过程抛出异常（见上方 traceback）")
        finally:
            qt_app.quit()

    QTimer.singleShot(900, guarded)
    code = qt_app.exec()
    app.ppt.shutdown()
    app.windows.shutdown()

    print("\n================ 跟随 / 前台 探针 ================")
    for line in RESULTS:
        print(line)
    fails = sum(1 for line in RESULTS if line.startswith("[FAIL]"))
    print(f"=================================================")
    print(f"失败项: {fails}")
    return 1 if fails or code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
