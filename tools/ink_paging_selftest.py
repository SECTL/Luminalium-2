"""按页墨迹接线自检（计划 self-ink 第 7 项）。

2026-10-07 用户指令：自建批注。仓库没有 pytest，按 tools/ink_*_selftest.py 的惯例直接运行：
    .venv/Scripts/python.exe -X utf8 tools/ink_paging_selftest.py

三段（对应计划的 happy / failure 两路 QA + 2026-10-08 回归）：
* A 按页记忆：合成状态流 1→2→1→同页键状态更新（黑屏/白屏/动画）→瞬时页码 0→退出
  →重新放映，断言各页笔画随页键存取、退出清空、同页键状态变化不清墨。
* B 单页退化：模拟 COM 整场读不到页码（slide_index 恒 0）的放映——单页日志恰好
  一次、翻页（页内容变但页键不变）不清墨、退出清空、下一场恢复正常。
* C 基线待定（2026-10-08 修复「翻页不切墨迹快照」的回归用例）：开场 COM 未就绪
  （slide_index=0）→ 真实页码 1→2→1 到达 → 墨迹必须按页切换。修复前基线 0 会
  锁死整场单页模式，本段在第 2 步即 FAIL。

不建真实 WindowManager（overlay/config 一大串依赖）：``object.__new__`` 造一个
壳，只填 _sync_ink_page 用到的属性；ink_window 用真 QQuickWindow + 真 InkLayer
（objectName ``inkLayer``，ink_layer() 的 findChild 路径原样走通）。画笔走
InkLayer 直接 API（todo 5 的输入链路已在 t5 验证过，这里不重复）。
任何断言失败退出码 1；输出写到 .omo/evidence/self-ink/t7-paging.txt 与
t7-single-page.txt。
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / ".omo" / "evidence" / "self-ink"

_lines: list[str] = []
_fails: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    _lines.append(msg)


def check(cond: bool, msg: str) -> None:
    log(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _fails.append(msg)


from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402

from app.ink.layer import InkLayer  # noqa: E402
from app.windows import WindowManager  # noqa: E402

W, H = 800.0, 600.0
SINGLE_PAGE_MARK = "单页模式"


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


def make_manager(layer: InkLayer, win: QQuickWindow) -> WindowManager:
    """最小 WindowManager 壳：只填 _sync_ink_page / ink_layer() 碰到的属性。

    WindowManager 不是纯 object 子类，object.__new__ 不安全，用它自己的 __new__。
    """
    mgr = WindowManager.__new__(WindowManager)
    mgr.ink_window = win
    mgr._ink_page_key = None
    mgr._ink_single_page_logged = False
    # ink_layer() 按 objectName findChild —— findChild 走 QObject 父链，
    # setParentItem 只给视觉父，两个都要设（QML 装载时两边是同一个）。
    layer.setObjectName("inkLayer")
    content = win.contentItem()
    layer.setParentItem(content)
    layer.setParent(content)
    return mgr


def draw_dot(layer: InkLayer, x: float, y: float, t0: int) -> None:
    layer.setProperty("tool", "pen")
    layer.beginStroke(x, y, 1.0)
    layer.extendStroke([[x + 8, y + 4, 1.0], [x + 16, y + 6, 1.0]])
    layer.endStroke()


def state(active: bool, slide: int, total: int = 41) -> SimpleNamespace:
    return SimpleNamespace(active=active, slide_index=slide, slide_total=total)


def test_paging(mgr: WindowManager, layer: InkLayer) -> None:
    log("== A. 按页记忆（状态流 1→2→1→同页更新→瞬时 0→退出→重开）")
    mgr._sync_ink_page(state(True, 1))
    check(layer.currentPage == 1 and mgr._ink_page_key == 1, "1 首次同步：页键确立为 slide 1")
    draw_dot(layer, 100, 100, 1000)
    check(len(layer.store.strokes(1)) == 1, "1 页 A 落一笔")
    mgr._sync_ink_page(state(True, 2))
    check(layer.currentPage == 2, "2 翻到页 B：InkLayer 换页（干纹理重建）")
    check(len(layer.store.strokes(1)) == 1, "2 页 A 的墨迹还在 PageStore 里（按页记忆）")
    draw_dot(layer, 400, 300, 2000)
    check(len(layer.store.strokes(2)) == 1, "2 页 B 落一笔")
    mgr._sync_ink_page(state(True, 1))
    check(layer.currentPage == 1 and len(layer.store.strokes(1)) == 1, "3 翻回页 A：墨迹完整重现")
    mgr._sync_ink_page(state(True, 1))
    check(layer.currentPage == 1 and len(layer.store.strokes(1)) == 1, "4 同页键状态更新（黑屏/白屏/动画）：不清墨不换页")
    # 瞬时读不到页码（COM 抽风）：维持现页键，绝不能踢回空页
    mgr._sync_ink_page(state(True, 0))
    check(layer.currentPage == 1 and len(layer.store.strokes(1)) == 1, "5 瞬时 slide_index=0：维持页 A 不清墨")
    mgr._sync_ink_page(state(True, 3))
    check(layer.currentPage == 3 and len(layer.store.strokes(3)) == 0, "5 页码恢复后正常跟随到页 C")
    mgr._sync_ink_page(state(False, 0))
    check(len(layer.store.strokes(1)) == 0 and len(layer.store.strokes(2)) == 0 and len(layer.store.strokes(3)) == 0,
          "6 退出放映：Q2 决策 —— 全部页键清空")
    check(layer.currentPage == 0 and mgr._ink_page_key is None and not mgr._ink_single_page_logged,
          "6 层拨回键 0，页键/单页日志旗标复位")
    mgr._sync_ink_page(state(False, 0))
    check(layer.currentPage == 0, "7 退出态的重复状态更新不重复清（幂等）")
    mgr._sync_ink_page(state(True, 3))
    check(layer.currentPage == 3 and len(layer.store.strokes(3)) == 0, "8 重新放映：从干净页开始")


def test_single_page(mgr: WindowManager, layer: InkLayer, capture: _LogCapture) -> None:
    log("== B. 单页退化（COM 整场读不到页码，恒 0）")
    # C 段结束已退场；退出态重复状态更新是幂等的，再来一条无妨
    mgr._sync_ink_page(state(False, 0))
    capture.records.clear()
    mgr._sync_ink_page(state(True, 0))
    check(layer.currentPage == 0 and mgr._ink_page_key == 0, "1 slide_index=0：基线待定，用键 0")
    check(len([r for r in capture.records if SINGLE_PAGE_MARK in r]) == 1,
          f"1 单页退化日志恰好一条（实测 {len([r for r in capture.records if SINGLE_PAGE_MARK in r])}）")
    draw_dot(layer, 200, 200, 3000)
    check(len(layer.store.strokes(0)) == 1, "1 键 0 落一笔")
    # 「翻页」：幻灯片内容变了但 COM 依旧读不到页码 —— 页键不变，墨迹不清
    mgr._sync_ink_page(state(True, 0, total=41))
    mgr._sync_ink_page(state(True, 0, total=41))
    check(layer.currentPage == 0 and len(layer.store.strokes(0)) == 1, "2 翻页（页键不变）不清墨")
    check(len([r for r in capture.records if SINGLE_PAGE_MARK in r]) == 1, "2 日志仍然恰好一条")
    # 2026-10-08 修复后「待定基线后来读到页码 → 升级按页」由 C 段覆盖；
    # 恒 0 到退场才是单页退化的本来语义
    mgr._sync_ink_page(state(False, 0))
    check(len(layer.store.strokes(0)) == 0 and mgr._ink_page_key is None, "3 退出清空、旗标复位")
    # 下一场放映页码正常：不再单页
    mgr._sync_ink_page(state(True, 1))
    check(layer.currentPage == 1 and mgr._ink_page_key == 1, "4 下一场放映恢复正常页键")
    check(len([r for r in capture.records if SINGLE_PAGE_MARK in r]) == 1, "4 单页日志没有再冒出来")


def test_pending_promotion(mgr: WindowManager, layer: InkLayer, capture: _LogCapture) -> None:
    """2026-10-08 回归：开场 COM 未就绪（slide_index=0）不能锁死整场单页模式。

    用户实测「切换页面时不会切换墨迹快照」的病灶：窗口探测比 COM attach 快，
    首次同步拿到 0，旧逻辑把基线 0 当单页锁死，之后真实页码永远无法升级。
    """
    log("== C. 基线待定（开场 0 → 真实页码 1→2→1 → 瞬时 0 → 退出）")
    # A 段结束时还停在放映中（页键 3）：先退场，让 C 段从全新放映开始
    mgr._sync_ink_page(state(False, 0))
    capture.records.clear()
    mgr._sync_ink_page(state(True, 0))
    check(layer.currentPage == 0 and mgr._ink_page_key == 0, "1 开场 slide_index=0：基线待定，先落键 0")
    draw_dot(layer, 150, 150, 4000)
    check(len(layer.store.strokes(0)) == 1, "1 待定窗口内落的墨记在键 0")
    # COM 读到真实页码：基线升级（修复前这里锁死在键 0，整段 FAIL）
    mgr._sync_ink_page(state(True, 1))
    check(layer.currentPage == 1 and mgr._ink_page_key == 1, "2 读到真实页码：基线升级为页 1（修复点）")
    check(len(layer.store.strokes(0)) == 1, "2 待定期间的键 0 墨迹不丢（留在键 0，退出时清）")
    draw_dot(layer, 100, 100, 5000)
    mgr._sync_ink_page(state(True, 2))
    check(layer.currentPage == 2 and len(layer.store.strokes(1)) == 1, "3 翻到页 2：页 1 墨迹保留在存储里")
    draw_dot(layer, 400, 300, 6000)
    mgr._sync_ink_page(state(True, 1))
    check(layer.currentPage == 1 and len(layer.store.strokes(1)) == 1, "4 翻回页 1：墨迹重现（按页切换生效）")
    # 基线确立后的瞬时 0：维持现页键（与 A 段第 5 步同一规则）
    mgr._sync_ink_page(state(True, 0))
    check(layer.currentPage == 1 and len(layer.store.strokes(1)) == 1, "5 瞬时 slide_index=0：维持页 1 不清墨")
    mgr._sync_ink_page(state(False, 0))
    check(len(layer.store.strokes(0)) == 0 and len(layer.store.strokes(1)) == 0 and len(layer.store.strokes(2)) == 0,
          "6 退出：待定期间键 0 的墨也一并清空（Q2 决策不变）")
    check(mgr._ink_page_key is None and not mgr._ink_single_page_logged, "6 页键/单页日志旗标复位")


def main() -> int:
    faulthandler.enable()
    faulthandler.dump_traceback_later(120, exit=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    head = f"# t7 按页墨迹接线自检 {time.strftime('%Y-%m-%d %H:%M:%S')}\n# 命令：.venv/Scripts/python.exe -X utf8 tools/ink_paging_selftest.py\n"

    from app.ink import configure_input_attributes
    configure_input_attributes()
    app = QGuiApplication(sys.argv)
    configure_input_attributes()

    win = QQuickWindow()
    win.resize(int(W), int(H))
    layer = InkLayer()
    layer.setWidth(W)
    layer.setHeight(H)

    capture = _LogCapture()
    logging.getLogger("app.windows").addHandler(capture)

    mgr = make_manager(layer, win)
    for step in (test_paging, test_single_page, test_pending_promotion):
        try:
            step(mgr, layer, capture) if step is not test_paging else step(mgr, layer)
        except Exception as exc:  # 自检入口：任何异常都记为失败并继续后面的项
            log(traceback.format_exc())
            check(False, f"{step.__name__} 抛异常 {exc!r}")

    ok = not _fails
    log(f"== 结果：{'全部通过' if ok else f'{len(_fails)} 项失败'}")
    (EVIDENCE / "t7-paging.txt").write_text(head + "\n".join(_lines) + "\n", encoding="utf-8")
    # 两段共用一份输出；failure 档（单页退化）单独落一份，方便按计划引用
    (EVIDENCE / "t7-single-page.txt").write_text(head + "（与 t7-paging 同一次运行，B 段为 failure 档）\n" + "\n".join(_lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
