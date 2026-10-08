"""三种橡皮自检（计划 self-ink 第 8 项）。

2026-10-07 用户指令：自建批注。仓库没有 pytest，按 tools/ink_*_selftest.py 的惯例直接运行：
    .venv/Scripts/python.exe -X utf8 tools/ink_eraser_selftest.py

两段：
* A 整笔 / 像素橡皮（t8-erasers.txt）：stroke 子模式命中即删整笔、undo 逐点复原、
  redo 再删、空划不记操作（用「redo 栈未被顶掉」功能性证明）；pixel 子模式照旧
  走 mode=erase 笔画；eraserMode 属性词表校验（pixel/stroke，非法拒收）。
* B 手掌擦除（t8-palm.txt）：_palm_pick 决策单测（大接触 / ≥3 指 / 抬起排除 /
  开关关闭）；状态机走**真实事件流**——PySide6.11 合成 QEventPoint 带不了直径
  （见 tools/ink_input_selftest.py 的说明），大接触面用子类注入
  ``_palm_trigger_point`` 的返回值代替，注入之后的进墨 / 抬笔 / 撤销全部走
  真实 TouchUpdate / TouchEnd 事件路径。断言：手上那笔先落账、擦除宽度=接触
  直径、工具属性全程不动（Q3「抬起即还原」零成本）、TouchCancel 作废、无直径
  驱动日志恰好一条、鼠标划过恒为笔。

任何断言失败退出码 1；输出分别写到 .omo/evidence/self-ink/t8-erasers.txt 与
t8-palm.txt。
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import time
import traceback
from pathlib import Path

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


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QSizeF, Qt  # noqa: E402
from PySide6.QtGui import QEventPoint, QGuiApplication, QInputDevice, QPointingDevice, QTouchEvent  # noqa: E402

from app.ink import configure_input_attributes  # noqa: E402
from app.ink.layer import InkLayer  # noqa: E402

W, H = 800.0, 600.0
TOUCH_DEVICE = None  # main() 里初始化


class FakePalm:
    """duck-typed QEventPoint：带直径的触点合成不出来（PySide6.11 限制），手掌触发用注入代替。"""

    def __init__(self, pid: int, x: float, y: float, contact_px: float) -> None:
        self._id, self._x, self._y, self._px = pid, x, y, contact_px

    def id(self) -> int:
        return self._id

    def state(self) -> QEventPoint.State:
        return QEventPoint.State.Pressed

    def position(self) -> QPointF:
        return QPointF(self._x, self._y)

    def pressure(self) -> float:
        return 1.0

    def ellipseDiameters(self) -> QSizeF:
        return QSizeF(self._px, self._px * 0.7)  # 接触面是椭圆，_contact_px 取长轴


class PalmLayer(InkLayer):
    """固定阈值 50 逻辑 px（windowless 拿不到屏幕物理参数），并可注入假掌面触发点。"""

    def __init__(self) -> None:
        super().__init__()
        self.fake_palm: FakePalm | None = None

    def _palm_threshold_px(self) -> float:
        return 50.0

    def _palm_trigger_point(self, ev: QTouchEvent) -> QEventPoint | None:
        if self.fake_palm is not None:
            palm, self.fake_palm = self.fake_palm, None
            return palm
        return super()._palm_trigger_point(ev)


def send(obj, ev: QEvent) -> bool:
    return QCoreApplication.sendEvent(obj, ev)


def touch_ev(et: QEvent.Type, t_ms: int, *ids: int) -> QTouchEvent:
    # 位置/直径合成不出来（模块 docstring）；事件本身只驮 id/state
    pts = [QEventPoint(i, QEventPoint.State.Pressed if k == 0 else QEventPoint.State.Updated,
                       QPointF(0, 0), QPointF(0, 0)) for k, i in enumerate(ids)]
    if et in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
        pts = [QEventPoint(i, QEventPoint.State.Released, QPointF(0, 0), QPointF(0, 0)) for i in ids]
    ev = QTouchEvent(et, TOUCH_DEVICE, Qt.KeyboardModifier.NoModifier, pts)
    ev.setTimestamp(t_ms)
    return ev


def draw_stroke(layer: InkLayer, x0: float, y0: float, x1: float, y1: float) -> None:
    layer.setProperty("tool", "pen")
    layer.beginStroke(x0, y0, 1.0)
    steps = 20
    layer.extendStroke([[x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps, 1.0] for k in range(1, steps + 1)])
    layer.endStroke()


def part_erasers(layer: InkLayer) -> None:
    log("== A. 整笔 / 像素橡皮")
    layer.setProperty("tool", "pen")
    layer.setProperty("penWidth", 20.0)  # 擦除半径 10px，命中带留足余量
    layer.clearAll()
    draw_stroke(layer, 100, 100, 300, 200)   # 笔画 A
    draw_stroke(layer, 100, 400, 300, 500)   # 笔画 B
    strokes = layer.store.strokes(0)
    check(len(strokes) == 2, "1 铺两笔")
    a = strokes[0]
    check(a.mode == "pen", "1 笔画 A 是 pen")

    layer.setProperty("eraserMode", "stroke")
    check(layer.property("eraserMode") == "stroke", "2 eraserMode 属性切到 stroke")
    layer.setProperty("tool", "eraser")
    # 沿 A 的路径划一遍（贴线 3px 内）：A 命中被整笔删掉，B 无恙
    layer.beginStroke(120, 112, 1.0)
    layer.extendStroke([[140, 122, 1.0], [200, 152, 1.0], [260, 182, 1.0]])
    layer.endStroke()
    strokes = layer.store.strokes(0)
    check(len(strokes) == 1 and strokes[0].id != a.id, "3 整笔擦除：A 整笔消失、B 保留")
    check(layer.undo() is True, "4 整笔擦除可 undo")
    strokes = layer.store.strokes(0)
    check(len(strokes) == 2, "4 undo 后 A 恢复")
    restored = next(s for s in strokes if s.id == a.id)
    check([tuple(p) for p in restored.points] == [tuple(p) for p in a.points], "4 undo 后 A 逐点复原")
    check(layer.redo() is True and len(layer.store.strokes(0)) == 1, "4 redo 再删 A")
    check(layer.undo() is True and len(layer.store.strokes(0)) == 2, "4 再 undo 回到两笔")

    # 空地划过：无命中 → 不记操作。功能性证明：此前的 redo 项若被顶掉即说明记了操作。
    layer.beginStroke(700, 80, 1.0)
    layer.extendStroke([[720, 90, 1.0]])
    layer.endStroke()
    check(len(layer.store.strokes(0)) == 2, "5 空地划过：无笔可删")
    check(layer.redo() is True, "5 空划没记撤销操作（此前的 redo 项仍在）")
    check(layer.undo() is True and len(layer.store.strokes(0)) == 2, "5 收尾：undo 回到两笔")

    # 像素模式回归：erase 笔画进栈，undo 撤掉
    layer.setProperty("eraserMode", "pixel")
    check(layer.property("eraserMode") == "pixel", "6 eraserMode 切回 pixel")
    layer.beginStroke(120, 415, 1.0)
    layer.extendStroke([[200, 455, 1.0]])
    layer.endStroke()
    strokes = layer.store.strokes(0)
    check(strokes[-1].mode == "erase", "6 像素橡皮产生 mode=erase 笔画")
    b_id = next(s.id for s in strokes if s.mode == "pen")
    check(layer.undo() is True and any(s.id == b_id for s in layer.store.strokes(0)),
          "6 undo 撤掉像素擦除、B 回来")

    # 词表校验：非法子模式拒收
    layer.setProperty("eraserMode", "whole")
    check(layer.property("eraserMode") == "pixel", "7 非法子模式拒收（词表是 pixel/stroke）")


def part_palm(layer: PalmLayer) -> None:
    log("== B. 手掌擦除")
    # ---- _palm_pick 决策单测
    layer.setProperty("palmEraseEnabled", True)
    pick = layer._palm_pick
    check(pick([(1, False, 120.0, 300, 200)]) == (1, 300, 200, 120.0), "1 单个大接触（≥50px）触发")
    check(pick([(1, False, 30.0, 300, 200), (2, False, 40.0, 310, 210)]) is None, "1 两个小接触不触发")
    three = [(1, False, 10.0, 100, 100), (2, False, 12.0, 200, 200), (3, False, 8.0, 300, 300)]
    check(pick(three) == (2, 200, 200, 12.0), "1 ≥3 指触发，取接触最大者")
    check(pick([(1, True, 120.0, 300, 200)]) is None, "1 已抬起的触点不触发")
    layer.setProperty("palmEraseEnabled", False)
    check(pick([(1, False, 120.0, 300, 200)]) is None, "1 手掌开关关闭不触发")
    layer.setProperty("palmEraseEnabled", True)
    check(bool(layer.property("palmEraseEnabled")), "1 开关回开")
    check(float(layer.property("palmThresholdMm")) == 20.0, "1 阈值属性默认 20mm")

    # ---- 状态机：真实事件流 + 注入触发点
    layer.setProperty("tool", "pen")
    layer.clearAll()
    send(layer, touch_ev(QEvent.Type.TouchBegin, 5000, 7))
    check(layer._device == "touch" and layer._pts is not None, "2 手指先起笔（正常触摸笔画）")
    send(layer, touch_ev(QEvent.Type.TouchUpdate, 5010, 7))
    layer.fake_palm = FakePalm(9, 300, 200, 120.0)
    send(layer, touch_ev(QEvent.Type.TouchUpdate, 5020, 7, 9))
    check(layer._palm_erasing and layer._touch_id == 9, "3 大接触落下：切手掌擦除，跟踪切到掌面")
    check(layer._mode == "erase" and layer._width == 120.0, "3 临时像素擦除，擦除宽度=接触直径 120")
    check(layer.property("tool") == "pen", "3 工具属性没动（「抬起即还原」的实现方式）")
    strokes = layer.store.strokes(0)
    check(len(strokes) == 1 and strokes[0].mode == "pen", "3 手上那笔先落账")
    for k in range(5):
        send(layer, touch_ev(QEvent.Type.TouchUpdate, 5030 + 10 * k, 9))
    check(layer._pts is not None and len(layer._pts) == 6, "4 掌面移动直接进擦除轨迹（不平滑）")
    send(layer, touch_ev(QEvent.Type.TouchEnd, 5090, 9))
    strokes = layer.store.strokes(0)
    check(len(strokes) == 2 and strokes[-1].mode == "erase" and strokes[-1].width == 120.0,
          "5 掌面抬起：擦除笔画落账（宽度 120 → 烘焙半径 60）")
    check(not layer._palm_erasing and layer.property("tool") == "pen", "5 抬起还原：旗标复位、工具没变过")
    check(layer.undo() is True and len(layer.store.strokes(0)) == 1, "6 手掌擦除笔画可 undo")
    check(layer.redo() is True and len(layer.store.strokes(0)) == 2, "6 redo 再擦")
    # TouchCancel 作废手掌擦除
    layer.fake_palm = FakePalm(11, 500, 300, 90.0)
    send(layer, touch_ev(QEvent.Type.TouchBegin, 6000, 11))
    check(layer._palm_erasing and layer._mode == "erase", "7 再次手掌擦除")
    send(layer, touch_ev(QEvent.Type.TouchCancel, 6010, 11))
    check(not layer._palm_erasing and len(layer.store.strokes(0)) == 2, "7 TouchCancel 作废手掌擦除")


def part_no_diameter(layer: PalmLayer, capture: _LogCapture) -> None:
    log("== C. 无直径驱动：手掌静默禁用 + 日志恰好一条；鼠标不触发手掌")
    layer.setProperty("tool", "pen")
    layer.clearAll()
    send(layer, touch_ev(QEvent.Type.TouchBegin, 7000, 21))
    send(layer, touch_ev(QEvent.Type.TouchEnd, 7010, 21))
    strokes = layer.store.strokes(0)
    check(len(strokes) == 1 and strokes[0].mode == "pen", "1 无直径触摸走正常笔画（不触发手掌）")
    for k in range(3):
        send(layer, touch_ev(QEvent.Type.TouchBegin, 7020 + 10 * k, 30 + k))
        send(layer, touch_ev(QEvent.Type.TouchEnd, 7025 + 10 * k, 30 + k))
    hits = [r for r in capture.records if "接触直径" in r]
    check(len(hits) == 1, f"2 不报直径的日志恰好一条（实测 {len(hits)}）")
    # 鼠标快速划过：恒为笔（手掌判定只在触摸路径上，鼠标/平板事件根本不进判定）
    layer.setProperty("tool", "pen")
    layer.beginStroke(50, 50, 0.5)
    layer.extendStroke([[400, 300, 0.5]])
    layer.endStroke()
    check(layer.store.strokes(0)[-1].mode == "pen", "3 鼠标划过恒为笔")


def main() -> int:
    faulthandler.enable()
    faulthandler.dump_traceback_later(120, exit=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    head = f"# t8 三种橡皮自检 {time.strftime('%Y-%m-%d %H:%M:%S')}\n# 命令：.venv/Scripts/python.exe -X utf8 tools/ink_eraser_selftest.py\n"

    configure_input_attributes()
    app = QGuiApplication(sys.argv)
    configure_input_attributes()
    global TOUCH_DEVICE
    TOUCH_DEVICE = QPointingDevice("qa-touch", 2, QInputDevice.DeviceType.TouchScreen,
                                   QPointingDevice.PointerType.Finger,
                                   QPointingDevice.Capability.Position, 10, 0)

    capture = _LogCapture()
    ink_log = logging.getLogger("luminalium.ink")  # layer.py 的 logger 名（不是模块路径）
    ink_log.addHandler(capture)
    ink_log.setLevel(logging.INFO)  # 不报直径的提示是 info 级，默认 WARNING 会拦掉

    plain = InkLayer()
    plain.setWidth(W)
    plain.setHeight(H)
    palm = PalmLayer()
    palm.setWidth(W)
    palm.setHeight(H)

    try:
        part_erasers(plain)
    except Exception:
        log(traceback.format_exc())
        check(False, "part_erasers 抛异常")
    split = len(_lines)
    (EVIDENCE / "t8-erasers.txt").write_text(head + "\n".join(_lines) + "\n", encoding="utf-8")

    try:
        part_palm(palm)
        part_no_diameter(palm, capture)
    except Exception:
        log(traceback.format_exc())
        check(False, "part_palm/part_no_diameter 抛异常")
    (EVIDENCE / "t8-palm.txt").write_text(head + "\n".join(_lines[split:]) + "\n", encoding="utf-8")

    ok = not _fails
    log(f"== 结果：{'全部通过' if ok else f'{len(_fails)} 项失败'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
