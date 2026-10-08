"""InkLayer 输入接线自检（计划 self-ink 第 5 项）。

2026-10-07 用户指令：自建批注。仓库没有 pytest，按 tools/ink_*_selftest.py 的惯例直接运行：
    .venv/Scripts/python.exe -X utf8 tools/ink_input_selftest.py

三段：
* A 压缩关断：三个子进程分别「不设 / 仅构造前设 / 构造前后各设」
  AA_CompressHighFrequencyEvents 再建 QApplication，读回属性断言。Qt 6.11/Windows
  实测：默认开、构造前设置会被 QApplication 构造翻回 True、构造前后各调
  configure_input_attributes() 才真正关掉（坑与结论见 configure_input_attributes
  docstring）；随后静态检查 application.py / check_qml.py / preview.py 的每个
  QApplication( 创建点前后都有 configure_input_attributes() 调用。
* B 合成输入：QMouseEvent / QTabletEvent / QTouchEvent 构造后 sendEvent 直投
  InkLayer（windowless，不经窗口投递）。触摸事件的位置信息合成不出来——
  QEventPoint.position 由 QQuickDeliveryAgent 投递时换算，PySide6.11 没绑定
  QMutableEventPoint、拷贝构造的 kwarg 覆盖也全被拒（桩与运行时不符，2026-10-07
  实测）——所以触摸断言只看分支/入账/钩子，不看坐标；坐标语义由鼠标与平板
  的事件（position() 来自构造参数）覆盖。曾试过经 QQuickWindow 投递让 agent 换算
  坐标，但 agent 会把合成的「部分抬起 TouchEnd」归一成 TouchUpdate——这个实测
  反而钉住了真实平台的语义（TouchEnd 只在全抬时才发），据此修掉了层的抬笔判定。
* C 直径正路径：ellipseDiameters 的「驱动给直径」分支用 duck-typed 假触点直测
  _track_contact（真构造物给不了直径，见 B 的说明）。

等待一律 processEvents + 小步 sleep：QTest.qWait 攥着 GIL（AGENTS.md）。
任何断言失败退出码 1；输出分别写到 .omo/evidence/self-ink/t5-compression-off.txt
与 t5-input-events.txt。
"""

from __future__ import annotations

import faulthandler
import re
import subprocess
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


# ---------------------------------------------------------------- A 压缩关断


def probe_attr(mode: str) -> bool:
    """子进程入口。mode：'none' / 'pre' / 'pre+post'；返回 True 表示压缩已关。

    Qt 6.11/Windows 实测（configure_input_attributes docstring）：默认 True（开）、
    构造前设置会被构造推翻、构造后再设才真正生效——三态探针把这三件事都钉住。
    """
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtWidgets import QApplication

    if "pre" in mode:
        from app.ink import configure_input_attributes
        configure_input_attributes()
    _app = QApplication(sys.argv[1:])  # noqa: F841 - 保活
    if "post" in mode:
        from app.ink import configure_input_attributes
        configure_input_attributes()
    return not QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_CompressHighFrequencyEvents)


def part_a() -> None:
    log("== A. AA_CompressHighFrequencyEvents 关断（Qt 6.11 三态探针）")
    codes = {
        "默认不设": "print(s.probe_attr('none'))",
        "仅构造前设(计划原方案)": "print(s.probe_attr('pre'))",
        "构造前后各设(实际方案)": "print(s.probe_attr('pre+post'))",
    }
    out: dict[str, str] = {}
    for name, body in codes.items():
        code = f"import sys; sys.path.insert(0, r'{ROOT}'); import tools.ink_input_selftest as s; {body}"
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True, timeout=120)
        out[name] = r.stdout.strip()
        log(f"  子进程[{name}] stdout={r.stdout.strip()!r} rc={r.returncode}" + (f" stderr={r.stderr[-200:]!r}" if r.returncode else ""))
    check(out.get("默认不设") == "False", "Windows 默认压缩开启（读到 True）——对照组，证明断言有牙")
    check(out.get("仅构造前设(计划原方案)") == "False", "仅构造前设置：QApplication 构造期间被翻回 True（Qt 6.11 坑，实测钉住）")
    check(out.get("构造前后各设(实际方案)") == "True", "构造前后各调 configure_input_attributes()，压缩已关（读到 False）")
    if not all(v in ("True", "False") for v in out.values()):
        check(False, f"子进程输出异常：{out}")
        return
    log("== A2. 入口时序（每个 QApplication( 创建点前后都有 configure_input_attributes()）")
    for rel in ("app/application.py", "tools/check_qml.py", "tools/preview.py"):
        path = ROOT / rel
        lines = path.read_text(encoding="utf-8").splitlines()
        sites = [i + 1 for i, ln in enumerate(lines) if re.search(r"=\s*QApplication\(", ln)]
        cfgs = [i + 1 for i, ln in enumerate(lines) if "configure_input_attributes()" in ln and "def " not in ln]
        if not sites:
            check(False, f"{rel} 找到 0 个 QApplication 创建点，检查逻辑失效")
            continue
        for idx, site in enumerate(sites):
            prev_site = sites[idx - 1] if idx else 0
            next_site = sites[idx + 1] if idx + 1 < len(sites) else len(lines) + 1
            before_ok = any(prev_site < c <= site for c in cfgs)
            after_ok = any(site < c < next_site for c in cfgs)
            check(before_ok and after_ok,
                  f"{rel}:L{site} 的 QApplication 前后都有 configure_input_attributes()（候选 {cfgs}）")


# ---------------------------------------------------------------- B/C 合成输入

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QEvent,
    QPointF,
    QSizeF,
    Qt,
)
from PySide6.QtGui import (  # noqa: E402
    QEventPoint,
    QGuiApplication,
    QInputDevice,
    QMouseEvent,
    QPointingDevice,
    QTabletEvent,
    QTouchEvent,
)

from app.ink import configure_input_attributes  # noqa: E402
from app.ink.layer import InkLayer  # noqa: E402

W, H = 800.0, 600.0
TOUCH_DEVICE = None  # main() 里初始化（QGuiApplication 之后）
PEN_DEVICE = None


class SpyLayer(InkLayer):
    """记录 _on_contact_sample 调用次数与入参，其余行为不变。"""

    def __init__(self) -> None:
        super().__init__()
        self.contact_samples: list[tuple[tuple[float, float] | None, float | None]] = []

    def _on_contact_sample(self, diameters: tuple[float, float] | None, pressure: float | None) -> None:
        self.contact_samples.append((diameters, pressure))
        super()._on_contact_sample(diameters, pressure)


class FakePoint:
    """duck-typed QEventPoint：只为 _track_contact 的直径正路径（真构造物给不了直径，见模块 docstring）。"""

    def __init__(self, diameter: tuple[float, float] | None, pressure: float | None) -> None:
        self._d, self._p = diameter, pressure

    def ellipseDiameters(self) -> QSizeF:
        return QSizeF(*self._d) if self._d else QSizeF(0.0, 0.0)

    def pressure(self) -> float | None:
        return self._p


def send(obj, ev: QEvent) -> bool:
    return QCoreApplication.sendEvent(obj, ev)


def mouse_ev(et: QEvent.Type, x: float, y: float, t_ms: int, pressed: bool) -> QMouseEvent:
    ev = QMouseEvent(et, QPointF(x, y), QPointF(x, y), Qt.MouseButton.LeftButton,
                     Qt.MouseButton.LeftButton if pressed else Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier)
    ev.setTimestamp(t_ms)
    return ev


def touch_ev(et: QEvent.Type, t_ms: int, *specs: dict) -> QTouchEvent:
    # position() 合成不出来（模块 docstring），断言不看坐标；id/state 是构造参数、真实可用
    pts = [QEventPoint(s["id"], s["state"], QPointF(0, 0), QPointF(0, 0)) for s in specs]
    ev = QTouchEvent(et, TOUCH_DEVICE, Qt.KeyboardModifier.NoModifier, pts)
    ev.setTimestamp(t_ms)
    return ev


def tablet_ev(et: QEvent.Type, x: float, y: float, t_ms: int, pressure: float, pressed: bool) -> QTabletEvent:
    # PySide6.11 签名：(..., z, keyState, button, buttons)——keyState 在前
    ev = QTabletEvent(et, PEN_DEVICE, QPointF(x, y), QPointF(x, y), pressure,
                      0.0, 0.0, 0.0, 0.0, 0.0,
                      Qt.KeyboardModifier.NoModifier,
                      Qt.MouseButton.LeftButton if et == QEvent.Type.TabletPress else Qt.MouseButton.NoButton,
                      Qt.MouseButton.LeftButton if pressed else Qt.MouseButton.NoButton)
    ev.setTimestamp(t_ms)
    return ev


def pt(id_: int, state: QEventPoint.State) -> dict:
    return dict(id=id_, state=state)


def pressed() -> QEventPoint.State:
    return QEventPoint.State.Pressed


def updated() -> QEventPoint.State:
    return QEventPoint.State.Updated


def released() -> QEventPoint.State:
    return QEventPoint.State.Released


def test_mouse_stroke(L: SpyLayer) -> None:
    L.setProperty("tool", "pen")
    L.setProperty("penWidth", 5.0)
    L.clearAll()
    t = 1000
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 100, 120, t, True))
    check(L._device == "mouse" and L._smoother is not None and L._pts is not None, "1 鼠标按下：滤波器与在途笔画建立")
    n_moves = 40
    for k in range(1, n_moves + 1):
        t += 10
        jitter = 1.5 if k % 3 else -1.2  # 假手抖
        send(L, mouse_ev(QEvent.Type.MouseMove, 100 + 10 * k, 120 + 0.4 * k + jitter, t, True))
    check(len(L.store.strokes(0)) == 0, "1 抬笔前 PageStore 不入账")
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 520, 140, t + 10, False))
    strokes = L.store.strokes(0)
    check(len(strokes) == 1 and strokes[0].mode == "pen", "1 抬笔后落账 1 笔 pen")
    s = strokes[0]
    # 计数只断言有界：带 1.5px 抖动的路径弦偏差 > CURVE_TOL(0.3px)，抽稀按设计要保留
    # 这些点；收笔追赶段每 2px 补点。形状保真断言在 t5-smoothing（第 5a 项自测）里。
    check(2 <= len(s.points) <= n_moves + 12, f"1 落账点数有界（注入 {n_moves} move，落账 {len(s.points)} 点）")
    x0, y0, _w0 = s.points[0]
    xe, ye, _ = s.points[-1]
    check(abs(x0 * W - 100) < 1.0 and abs(y0 * H - 120) < 1.0, f"1 起点对准按下位置（归一化 {x0:.4f},{y0:.4f}）")
    check(abs(xe * W - 520) < 1.0 and abs(ye * H - 140) < 1.0, f"1 末点精确停在抬笔位置（{xe * W:.1f},{ye * H:.1f}）")
    check(all(0.2 <= p[2] <= 1.6 for p in s.points), f"1 宽度因子全程在 [0.2,1.6]（实测 {min(p[2] for p in s.points):.2f}..{max(p[2] for p in s.points):.2f}）")
    check(L._smoother is None and L._device is None, "1 抬笔后滤波器与设备态复位")


def test_arrow_rejects(L: SpyLayer) -> None:
    L.setProperty("tool", "arrow")
    L.clearAll()
    n0 = len(L.contact_samples)
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 200, 200, 5000, True))
    send(L, mouse_ev(QEvent.Type.MouseMove, 260, 240, 5010, True))
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 300, 260, 5020, False))
    send(L, touch_ev(QEvent.Type.TouchBegin, 5030, pt(3, pressed())))
    send(L, touch_ev(QEvent.Type.TouchEnd, 5040, pt(3, released())))
    check(len(L.store.strokes(0)) == 0, "2 arrow 态：鼠标+触屏事件全部拒绝，0 笔入账")
    check(L._smoother is None and L._touch_id == -1, "2 arrow 态不产生滤波器/触点态")
    check(len(L.contact_samples) == n0, "2 arrow 态连接触样本钩子都不该进（TouchBegin 未被消费）")


def test_touch_sequences(L: SpyLayer) -> None:
    L.setProperty("tool", "pen")
    L.clearAll()
    L._last_contact_diameters = None
    # 单指完整序列
    send(L, touch_ev(QEvent.Type.TouchBegin, 6000, pt(7, pressed())))
    check(L._touch_id == 7 and L._device == "touch", f"3 触屏起笔：跟踪触点 7（实测 id={L._touch_id} device={L._device}）")
    check(L._smoother is not None and L._smoother._has_pressure is False,
          "3 无直径触屏 pressure 恒 1.0 → 按无压感走速度模拟")
    for k in range(1, 11):
        send(L, touch_ev(QEvent.Type.TouchUpdate, 6000 + 12 * k, pt(7, updated())))
    check(len(L.store.strokes(0)) == 0 and L._pts is not None, "3 触点 7 书写中不入账")
    # 多指：第二指随 TouchUpdate 落下（真实平台语义），跟踪目标不变
    send(L, touch_ev(QEvent.Type.TouchUpdate, 6130, pt(7, updated()), pt(8, pressed())))
    check(L._touch_id == 7, f"4 第二指落下不换跟踪目标（实测 id={L._touch_id}）")
    check(len(L.store.strokes(0)) == 0 and L._device == "touch", "4 第二指没有另起笔画、原笔画继续")
    # 触点 7 先抬（多指部分抬起 = TouchUpdate 载 Released 点；QQuickDeliveryAgent 实测语义）：
    # 状态判定立刻收笔，不能悬挂
    send(L, touch_ev(QEvent.Type.TouchUpdate, 6140, pt(7, released()), pt(8, updated())))
    strokes = L.store.strokes(0)
    check(len(strokes) == 1, f"5 触点 7 抬起（TouchUpdate 载 Released）即刻落账 1 笔（实测 {len(strokes)}）")
    check(L._touch_id == -1 and L._device is None and L._smoother is None, "5 抬笔后触点/滤波器/设备态复位")
    # 触点 8 自己抬起：已不在跟踪，不应产生新笔画
    send(L, touch_ev(QEvent.Type.TouchEnd, 6150, pt(8, released())))
    check(len(L.store.strokes(0)) == 1, "5 剩余触点的 TouchEnd 不产生第二笔")
    # TouchEnd（整组抬起）路径
    send(L, touch_ev(QEvent.Type.TouchBegin, 6200, pt(9, pressed())))
    send(L, touch_ev(QEvent.Type.TouchEnd, 6210, pt(9, released())))
    check(len(L.store.strokes(0)) == 2, f"6 整组 TouchEnd 正常落账（实测 {len(L.store.strokes(0))} 笔）")
    # 重复 TouchBegin（驱动补发形态）不换目标
    send(L, touch_ev(QEvent.Type.TouchBegin, 6220, pt(11, pressed())))
    check(L._touch_id == 11 and L._device == "touch", "7 触点 11 正常起新笔")
    send(L, touch_ev(QEvent.Type.TouchBegin, 6230, pt(12, pressed())))
    check(L._touch_id == 11, f"7 重复 TouchBegin 不换跟踪目标（实测 id={L._touch_id}）")
    # 跟丢触点（Update 里没有 id=11）：按抬笔收尾兜底
    send(L, touch_ev(QEvent.Type.TouchUpdate, 6240, pt(13, updated())))
    check(len(L.store.strokes(0)) == 3 and L._smoother is None and L._touch_id == -1, "7 跟丢触点按抬笔收尾，不悬挂")
    # TouchCancel：系统抢走手势，在途笔画作废
    send(L, touch_ev(QEvent.Type.TouchBegin, 6300, pt(14, pressed())))
    check(L._pts is not None, "8 TouchCancel 前在途笔画存在")
    send(L, touch_ev(QEvent.Type.TouchCancel, 6310, pt(14, updated())))
    check(len(L.store.strokes(0)) == 3 and L._smoother is None and L._touch_id == -1, "8 TouchCancel 作废在途笔画")


def test_contact_hook_paths(L: SpyLayer) -> None:
    n = len(L.contact_samples)
    L._track_contact(FakePoint((42, 30), 0.6))
    check(L._last_contact_diameters == (42.0, 30.0), f"9 驱动给直径：_last_contact_diameters 记录（实测 {L._last_contact_diameters}）")
    check(len(L.contact_samples) == n + 1 and L.contact_samples[-1] == ((42.0, 30.0), 0.6),
          "9 钩子拿到直径与压力（手掌擦除据此触发）")
    L._track_contact(FakePoint((60, 50), 1.0))
    check(L._last_contact_diameters == (60.0, 50.0) and L.contact_samples[-1] == ((60.0, 50.0), 1.0),
          "9 大接触面样本同样直达钩子")
    L._track_contact(FakePoint(None, 1.0))
    check(L._last_contact_diameters is None and L.contact_samples[-1] == (None, 1.0),
          "9 驱动不给直径（宽高非正）→ None，手掌擦除据此静默禁用")


def test_tablet_pressure(L: SpyLayer) -> None:
    L.setProperty("tool", "pen")
    L.clearAll()
    t = 7000
    send(L, tablet_ev(QEvent.Type.TabletPress, 100, 400, t, 0.15, True))
    check(L._device == "tablet" and L._smoother is not None and L._smoother._has_pressure, "10 平板起笔：压感设备判定")
    for k in range(1, 31):
        t += 16
        send(L, tablet_ev(QEvent.Type.TabletMove, 100 + 8 * k, 400, t, min(0.9, 0.15 + 0.025 * k), True))
    send(L, tablet_ev(QEvent.Type.TabletRelease, 350, 400, t + 16, 0.9, False))
    s = L.store.strokes(0)[0]
    ws = [p[2] for p in s.points]
    check(len(s.points) >= 3 and ws[-1] > ws[0] * 1.5, f"10 压感宽度随压力增大（{ws[0]:.2f} → {ws[-1]:.2f}）")
    xe = s.points[-1][0] * W
    check(abs(xe - 350) < 1.0, f"10 末点精确停在 TabletRelease 位置（{xe:.1f}）")
    # 设备互斥：鼠标笔画进行中，平板 move 不得串扰
    L.clearAll()
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 300, 200, 8000, True))
    check(L._device == "mouse", "11 鼠标笔画进行中")
    send(L, tablet_ev(QEvent.Type.TabletMove, 500, 500, 8010, 0.5, True))
    check(L._device == "mouse" and L._smoother is not None, "11 平板 move 未打断鼠标笔画")
    if L._pts:
        check(abs(L._pts[-1][0] * W - 500) > 5, "11 平板 move 的坐标没有混进鼠标笔画")
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 320, 210, 8020, False))
    check(len(L.store.strokes(0)) == 1, "11 鼠标笔画正常收尾")


def test_double_click_and_zero_time(L: SpyLayer) -> None:
    L.setProperty("tool", "pen")
    L.clearAll()
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 200, 100, 0, True))
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 200, 100, 0, False))
    # 第二次按下以 MouseButtonDblClick 形态到达（timestamp 也不给，dt 兜底）
    send(L, mouse_ev(QEvent.Type.MouseButtonDblClick, 350, 120, 0, True))
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 355, 122, 0, False))
    strokes = L.store.strokes(0)
    check(len(strokes) == 2, f"12 双击出两个圆点（实测 {len(strokes)} 笔）")
    check(all(len(s.points) >= 2 for s in strokes), "12 点按也落账（smoothing 点按语义：圆头两笔）")
    check(L._smoother is None and L._device is None, "12 时间戳全 0 不炸（MIN_DT 兜底）")


def test_dismiss_press(L: SpyLayer) -> None:
    """13 工具卡「点空白收起」（2026-10-08 自建批注）：起笔钩子返回 True 时
    第一按被消费成收卡、不起笔；返回 False / 无钩子时按下正常起笔。"""
    L.setProperty("tool", "pen")
    L.clearAll()
    calls: list[int] = []

    def hook_open() -> bool:  # 有卡开着：WindowManager 会收卡并让我们消费这一按
        calls.append(1)
        return True

    L.card_dismiss_hook = hook_open
    t = 9000
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 100, 100, t, True))
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 100, 100, t + 10, False))
    check(calls == [1], f"13 第一按只询问了一次起笔钩子（实测 {len(calls)} 次）")
    check(L._smoother is None and L._device is None and L._pts is None,
          "13 第一按被消费：未建立滤波器 / 设备态 / 在途笔画")
    check(len(L.store.strokes(0)) == 0, "13 第一按不入账（消费为收起卡片）")
    # 钩子返回 False（没有卡开着 / 已收完）：下一按正常起笔落账
    L.card_dismiss_hook = lambda: False
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 200, 200, t + 20, True))
    check(L._smoother is not None and L._device == "mouse", "13 第二按正常起笔")
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 220, 210, t + 30, False))
    check(len(L.store.strokes(0)) == 1, "13 第二按落账 1 笔")
    # 无钩子（自检直造 / 窗口侧未接线）：老行为兜底，按下直接起笔
    L.clearAll()
    L.card_dismiss_hook = None
    send(L, mouse_ev(QEvent.Type.MouseButtonPress, 300, 300, t + 40, True))
    check(L._smoother is not None, "13 无钩子时按下直接起笔（老行为兜底）")
    send(L, mouse_ev(QEvent.Type.MouseButtonRelease, 300, 300, t + 50, False))
    check(len(L.store.strokes(0)) == 1, "13 无钩子时落账 1 笔")


def part_b_and_c(app: QGuiApplication) -> None:
    log("== B. 合成事件直投 InkLayer（windowless；触摸坐标合成不出来，见模块 docstring）")
    L = SpyLayer()
    L.setWidth(W)
    L.setHeight(H)
    log(f"  InkLayer {L.width()}x{L.height()} tool={L.property('tool')}")
    for step in (test_mouse_stroke, test_arrow_rejects, test_touch_sequences,
                 test_contact_hook_paths, test_tablet_pressure, test_double_click_and_zero_time,
                 test_dismiss_press):
        try:
            step(L)
        except Exception as exc:  # 自检入口：任何异常都记为失败并继续后面的项
            log(traceback.format_exc())
            check(False, f"{step.__name__} 抛异常 {exc!r}")
    log(f"  全程接触样本钩子调用 {len(L.contact_samples)} 次")


def main() -> int:
    faulthandler.enable()
    faulthandler.dump_traceback_later(180, exit=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    head = f"# t5 输入接线自检 {time.strftime('%Y-%m-%d %H:%M:%S')}\n# 命令：.venv/Scripts/python.exe -X utf8 tools/ink_input_selftest.py\n"
    part_a()
    lines_a = list(_lines)
    _fails.clear()
    (EVIDENCE / "t5-compression-off.txt").write_text(head + "\n".join(lines_a) + "\n", encoding="utf-8")

    global TOUCH_DEVICE, PEN_DEVICE
    configure_input_attributes()  # 构造前（计划原案；Qt 6.11 会被构造翻回，见 A 段）
    app = QGuiApplication(sys.argv)
    configure_input_attributes()  # 构造后（Qt 6.11/Windows 上真正生效的那次）
    TOUCH_DEVICE = QPointingDevice("qa-touch", 2, QInputDevice.DeviceType.TouchScreen,
                                   QPointingDevice.PointerType.Finger,
                                   QPointingDevice.Capability.Position, 10, 0)
    PEN_DEVICE = QPointingDevice("qa-pen", 3, QInputDevice.DeviceType.Stylus, QPointingDevice.PointerType.Pen,
                                 QPointingDevice.Capability.Pressure | QPointingDevice.Capability.Position, 1, 0)
    part_b_and_c(app)
    ok = not _fails
    log(f"== 结果：{'全部通过' if ok else f'{len(_fails)} 项失败'}")
    (EVIDENCE / "t5-input-events.txt").write_text(
        head + "（A 段证据在 t5-compression-off.txt）\n" + "\n".join(_lines[len(lines_a):]) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
