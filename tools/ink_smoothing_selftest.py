"""app/ink/smoothing.py 自检（纯 Python，无 pytest）。

2026-10-07 用户指令：自建批注，要求丝滑跟手。本脚本验证 1€ 滤波去抖、快速跟手、抽稀保形、
宽度映射与点按圆点，并做每采样耗时微基准。证据写到 .omo/evidence/self-ink/t5-smoothing.txt。

按路径加载 smoothing.py 而不 import app.ink：包的 __init__ 会拉起 Qt 相关注册，
本自检要证明的恰恰是算法层脱离 Qt 可用。

用法：.venv\\Scripts\\python.exe tools\\ink_smoothing_selftest.py
"""

from __future__ import annotations

import importlib.util
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "ink" / "smoothing.py"
EVIDENCE = ROOT / ".omo" / "evidence" / "self-ink" / "t5-smoothing.txt"

_spec = importlib.util.spec_from_file_location("_ink_smoothing", SRC)
assert _spec is not None and _spec.loader is not None
sm = importlib.util.module_from_spec(_spec)
# 先登记再执行：from __future__ annotations 下 dataclass/类型解析会按模块名回查 sys.modules。
sys.modules["_ink_smoothing"] = sm
_spec.loader.exec_module(sm)

Pt = tuple[float, float]
lines: list[str] = []
failures: list[str] = []


def log(msg: str) -> None:
    lines.append(msg)
    print(msg)


def check(cond: bool, name: str, detail: str) -> None:
    log(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")
    if not cond:
        failures.append(name)


def run(samples: list[tuple[float, float, float, float | None]], *, has_pressure: bool = False,
        min_distance: float = 0.75) -> tuple[list[tuple[float, float, float]], int]:
    """返回 (全部输出点, end() 之前的输出点数)。"""
    s = sm.StrokeSmoother(has_pressure=has_pressure, min_distance=min_distance)
    x, y, t, p = samples[0]
    out = list(s.begin(x, y, t, p))
    for x, y, t, p in samples[1:]:
        out.extend(s.add(x, y, t, p))
    n_before_end = len(out)
    out.extend(s.end())
    return out, n_before_end


def seg_dist(p: Pt, a: Pt, b: Pt) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def poly_dist(p: Pt, poly: list[Pt]) -> float:
    if len(poly) == 1:
        return math.dist(p, poly[0])
    return min(seg_dist(p, a, b) for a, b in zip(poly, poly[1:]))


def variance(vals: list[float]) -> float:
    m = sum(vals) / len(vals)
    return sum((v - m) ** 2 for v in vals) / len(vals)


def test_jitter() -> None:
    # 慢速 100 px/s 水平线 + ±1.5 px 高斯抖动，200 Hz 采样，固定种子。
    rng = random.Random(20261007)
    samples = [(i * 0.5 + rng.gauss(0, 1.5), 100.0 + rng.gauss(0, 1.5), i * 0.005, None) for i in range(600)]
    out, n = run(samples)
    raw_var = variance([s[1] - 100.0 for s in samples])
    # 不计 end() 的追赶段：它按契约要精确落到最后一个（带噪声的）原始点上。
    filt_var = variance([p[1] - 100.0 for p in out[:n]])
    check(filt_var < raw_var * 0.5, "慢速去抖", f"垂向方差 raw={raw_var:.4f} filtered={filt_var:.4f} 点数 {len(samples)}->{len(out)}")


def test_zigzag() -> None:
    # 2000 px/s 折线，1 kHz 采样。
    verts: list[Pt] = [(0.0, 0.0), (300.0, 150.0), (600.0, 0.0), (900.0, 150.0), (1200.0, 0.0)]
    speed, dt = 2000.0, 0.001
    samples: list[tuple[float, float, float, float | None]] = []
    t = 0.0
    for a, b in zip(verts, verts[1:]):
        n = max(1, int(math.dist(a, b) / (speed * dt)))
        for k in range(n):
            f = k / n
            samples.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, t, None))
            t += dt
    samples.append((verts[-1][0], verts[-1][1], t, None))
    out, _ = run(samples)
    max_dev = max(poly_dist((p[0], p[1]), verts) for p in out)
    end_err = math.dist(out[-1][:2], verts[-1])
    check(max_dev < 20.0, "快速折线跟手", f"输出点到原始折线最大偏差 {max_dev:.3f} px（阈值 20）")
    check(end_err <= 0.5, "终点对齐", f"末点与最后原始点距离 {end_err:.4f} px")


def filtered_reference(samples: list[tuple[float, float, float, float | None]]) -> list[Pt]:
    f = sm.OneEuroFilter2D()
    return [f(x, y, t) for x, y, t, _ in samples]


def test_decimation() -> None:
    # 密集直线：250 px/s，1 kHz，0.25 px 一个点。
    line = [(i * 0.25, 50.0 + i * 0.1, i * 0.001, None) for i in range(2000)]
    out, _ = run(line)
    ref = filtered_reference(line)
    # 用含 end() 的完整输出：最后一个输出点之后还扣着不足一帧的暂存点，它们由 end() 的收尾段覆盖，
    # 只比 end() 之前的折线会把这截尾巴（约 4 px）误算成形状偏差。
    poly = [(p[0], p[1]) for p in out]
    dev = max(poly_dist(r, poly) for r in ref)
    factor = len(line) / len(out)
    check(factor >= 10.0, "直线抽稀倍数", f"{len(line)} -> {len(out)} 点，压缩 {factor:.1f}x")
    check(dev < 1.0, "直线抽稀保形", f"滤波轨迹到抽稀折线最大偏差 {dev:.4f} px")
    # 圆：弯道必须保点，形状偏差同样 < 1 px。
    circle = [(200 + 80 * math.cos(i * 0.002), 200 + 80 * math.sin(i * 0.002), i * 0.001, None) for i in range(3142)]
    out_c, n_c = run(circle)
    ref_c = filtered_reference(circle)
    poly_c = [(p[0], p[1]) for p in out_c[:n_c]]
    dev_c = max(poly_dist(r, poly_c) for r in ref_c[: len(ref_c) - 1])
    check(dev_c < 1.0, "圆弧抽稀保形", f"{len(circle)} -> {len(out_c)} 点，最大偏差 {dev_c:.4f} px")


def test_width() -> None:
    # 压感：压力 0.1 -> 1.0 缓升，w 必须单调不减。
    pres = [(i * 0.5, 0.0, i * 0.005, 0.1 + 0.9 * i / 599) for i in range(600)]
    out, _ = run(pres, has_pressure=True)
    drops = [b[2] - a[2] for a, b in zip(out, out[1:]) if b[2] < a[2] - 1e-9]
    check(not drops, "压感宽度单调", f"w {out[0][2]:.3f} -> {out[-1][2]:.3f}，回落次数 {len(drops)}")
    # 速度模拟：先 100 px/s 走 300 px，再 3000 px/s 走 3000 px。
    spd: list[tuple[float, float, float, float | None]] = []
    t = 0.0
    for i in range(3000):
        spd.append((i * 0.1, 0.0, t, None))
        t += 0.001
    for i in range(1000):
        spd.append((300.0 + i * 3.0, 0.0, t, None))
        t += 0.001
    out_s, _ = run(spd)
    slow = [p[2] for p in out_s if 50 <= p[0] <= 280]
    fast = [p[2] for p in out_s if 1000 <= p[0] <= 3000]
    ws, wf = sum(slow) / len(slow), sum(fast) / len(fast)
    check(wf < ws, "速度变细", f"慢段平均 w={ws:.3f}（{len(slow)} 点） 快段平均 w={wf:.3f}（{len(fast)} 点）")


def test_tap() -> None:
    for has_p in (False, True):
        s = sm.StrokeSmoother(has_pressure=has_p)
        out = s.begin(10.0, 10.0, 0.0, 0.5 if has_p else None) + s.end()
        check(any(p[2] > 0 for p in out), f"单点点按（has_pressure={has_p}）", f"输出 {out}")
    s = sm.StrokeSmoother(has_pressure=False)
    out = s.begin(10.0, 10.0, 0.0, None) + s.add(10.2, 10.1, 0.01, None) + s.end()
    check(bool(out) and all(p[2] > 0 for p in out), "微动点按", f"输出 {out}")


def test_no_qt() -> None:
    text = SRC.read_text(encoding="utf-8")
    hits = text.count("PySide6") + text.count("PyQt")
    check(hits == 0, "零 Qt 依赖", f"smoothing.py 中 PySide6/PyQt 命中 {hits} 次")


def bench() -> None:
    n = 10000
    samples = [(300 + (100 + i * 0.02) * math.cos(i * 0.01), 300 + (100 + i * 0.02) * math.sin(i * 0.01), i * 0.001, None)
               for i in range(n)]
    best = math.inf
    for _ in range(3):
        t0 = time.perf_counter()
        run(samples)
        best = min(best, time.perf_counter() - t0)
    us = best / n * 1e6
    # 1 kHz 输入下每采样预算 1000 µs；留出给渲染的余量，算法层要求 < 50 µs。
    check(us < 50.0, "微基准", f"{n} 采样最优 {best * 1000:.1f} ms，{us:.2f} µs/采样")


def main() -> int:
    log(f"ink smoothing selftest  python {sys.version.split()[0]}")
    for fn in (test_jitter, test_zigzag, test_decimation, test_width, test_tap, test_no_qt, bench):
        fn()
    log(f"结果：失败 {len(failures)}" + (f" -> {failures}" if failures else ""))
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
