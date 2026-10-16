"""自建批注的输入平滑：原始指针采样 → 滤波后的中心线点 + 宽度因子（纯 Python，零 Qt 依赖）。

2026-10-07 用户指令：自建批注，要求丝滑跟手。本文件只做算法，事件接入在 InkLayer 侧；
输出 (x, y, w) 直接喂 InkLayer.beginStroke/extendStroke/endStroke，x/y 与输入同单位（逻辑像素），
w 是宽度因子（1.0 = penWidth）。

设计取舍：
1. 为什么用 1€ 滤波（Casiez 等，CHI 2012）：定截止频率的低通只能在"慢时不抖"和"快时不拖"之间二选一。
   1€ 按速度自适应截止频率——慢速时截止低，手抖被压平；快速时截止升高，滞后变小。
   两轴共用一个速度模长（OneEuroFilter2D），否则斜线方向两轴截止不同，轨迹会被各向异性地拉歪。
2. 为什么抽稀：关掉高频事件压缩后，触笔 / 高回报率鼠标每秒上千个点，几乎全落在直线段上；
   不抽稀的话湿几何三角带与烘焙路径都白白膨胀。规则是"距离 + 弦偏差"：被丢掉的点到保留弦的
   距离不超过 CURVE_TOL，于是直线段大量丢点、弯道的点被保留；首点与末点永不丢。
   弦偏差每个采样只扫"上次输出以来暂存的点"，暂存数有上限（MAX_HELD / MAX_HOLD），
   所以每点开销有界，与整笔长度无关，长笔画不掉帧。
3. 为什么无压感时按速度模拟宽度：鼠标 / 无压感触屏的笔迹宽度恒定会显得呆板；真实墨水笔走得快
   出墨少、线更细。按速度变细并做时间域平滑，宽度才不会随单个采样的速度噪声闪烁。
   有压感时压力本身就是起收笔的锥度，不再叠加锥度，否则起笔过细。
4. 起收笔锥度（perfect-freehand 风格）：只作用在 w 上，并有下限，快速点按仍是一个可见的圆点。
   收笔锥度只铺在"滤波滞后的追赶段"上：快速甩笔时这一段有十几像素，正好需要锥度；
   慢速收笔时追赶段很短，笔头自然圆钝，与真实笔慢收的观感一致。不靠扣留尾巴实现锥度，
   因为扣留就是可见的跟手滞后，违背本需求的首要目标。
"""

from __future__ import annotations

import math

OutPoint = tuple[float, float, float]
# (x, y, w, t)：暂存与已输出的点都带时间戳，抽稀的"最多扣留多久"按它算。
_Sample = tuple[float, float, float, float]

# 1 Hz：静止 / 慢写时手抖（约 4-12 Hz）被压到很低；再低则慢速书写的滞后肉眼可见。
MIN_CUTOFF = 1.0
# 0.02（每 px/s）：2000 px/s 的快划截止升到约 41 Hz，滞后约 4 ms；
# 常见的 0.007 是针对归一化坐标量级的，换到像素单位快划会拖出一截。
BETA = 0.02
# 1 Hz：速度估计本身要平滑，否则抖动的导数会把截止频率抬高，慢速时又抖起来。
D_CUTOFF = 1.0
# 0.5 ms：同一毫秒内的多个事件（时间戳精度只到毫秒）不能让 dt=0 除零，也不能让 alpha 失真太多。
MIN_DT = 0.0005

# 0.3 px：低于半个像素的偏差在抗锯齿后看不出，留出余量给后续宽度轮廓的取整。
CURVE_TOL = 0.3
# 12 px：直线段最长一段弦；太长时末端湿笔画会停在上一个输出点，看着像"没跟上"。
MAX_SEGMENT = 12.0
# 16 ms：一帧（60 Hz）。扣留不足一帧的点渲染上看不出来，超过就是可见的跟手滞后。
MAX_HOLD = 0.016
# 48：弦偏差每点要扫一遍暂存点，48 个以内每采样开销仍是常数级。
MAX_HELD = 48

# 压感映射 0.35..1.6：轻触变细但不消失；重压最多 1.6 倍，再粗就糊成一片。
PRESSURE_W_MIN = 0.35
PRESSURE_W_MAX = 1.6
# 设备报 has_pressure 却给了 None 时按 0.5 处理（计划：鼠标恒 0.5），映射后约为 1.0。
MOUSE_PRESSURE = 0.5
# 15 ms：压力读数逐点有量化噪声，平滑一帧以内，既不闪也不拖。
PRESSURE_TAU = 0.015

# 速度模拟：最快时细到 0.55 倍；再细快速书写会像断墨。
SPEED_THIN = 0.45
# 3000 px/s 以上视为"全速"，约等于 1080p 屏上 0.6 秒横扫全屏。
SPEED_FULL = 3000.0
# 60 ms：宽度变化比位置变化慢半拍才自然，太快则单个快采样就让线条忽粗忽细。
SPEED_TAU = 0.06

# 起笔锥度在前 8 px 内从 0.4 倍长到全宽：短到不影响写字，长到能看出笔锋。
START_TAPER_PX = 8.0
START_FLOOR = 0.4
# 收笔追赶段每 2 px 一个点，锥度过渡才平滑；末点缩到 0.4 倍。
END_STEP_PX = 2.0
END_FLOOR = 0.4
# 全局宽度兜底：锥度 × 速度变细叠加时不至于细到看不见。
W_MIN = 0.2
W_MAX = PRESSURE_W_MAX


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


def _ease_out(t: float) -> float:
    # 二次缓出：起笔前几像素长得快，后段平缓，避免锥度末端出现可见的"台阶"。
    return t * (2.0 - t)


def _clamp_w(w: float) -> float:
    return min(W_MAX, max(W_MIN, w))


def _seg_dist(px: float, py: float, a: _Sample, b: _Sample) -> float:
    ax, ay = a[0], a[1]
    dx, dy = b[0] - ax, b[1] - ay
    len_sq = dx * dx + dy * dy
    t = 0.0 if len_sq == 0.0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


class OneEuroFilter:
    """标准一维 1€ 滤波，时间戳单位为秒。"""

    __slots__ = ("_dx", "_primed", "_t", "_x", "beta", "d_cutoff", "min_cutoff")

    def __init__(self, *, min_cutoff: float = MIN_CUTOFF, beta: float = BETA, d_cutoff: float = D_CUTOFF) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._primed = False
        self._x = self._dx = self._t = 0.0

    def __call__(self, x: float, t: float) -> float:
        if not self._primed:
            self._primed, self._x, self._dx, self._t = True, x, 0.0, t
            return x
        dt = max(t - self._t, MIN_DT)
        self._t = t
        self._dx += _alpha(self.d_cutoff, dt) * ((x - self._x) / dt - self._dx)
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        self._x += _alpha(cutoff, dt) * (x - self._x)
        return self._x


class OneEuroFilter2D:
    """二维 1€：两轴共用速度模长决定截止频率（见头注释第 1 条）。"""

    __slots__ = ("_dx", "_dy", "_primed", "_t", "_x", "_y", "beta", "d_cutoff", "min_cutoff")

    def __init__(self, *, min_cutoff: float = MIN_CUTOFF, beta: float = BETA, d_cutoff: float = D_CUTOFF) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._primed = False
        self._x = self._y = self._dx = self._dy = self._t = 0.0

    @property
    def speed(self) -> float:
        """平滑后的速度模长（输入单位 / 秒）。"""
        return math.hypot(self._dx, self._dy)

    def __call__(self, x: float, y: float, t: float) -> tuple[float, float]:
        if not self._primed:
            self._primed, self._x, self._y, self._t = True, x, y, t
            self._dx = self._dy = 0.0
            return x, y
        dt = max(t - self._t, MIN_DT)
        self._t = t
        ad = _alpha(self.d_cutoff, dt)
        self._dx += ad * ((x - self._x) / dt - self._dx)
        self._dy += ad * ((y - self._y) / dt - self._dy)
        a = _alpha(self.min_cutoff + self.beta * self.speed, dt)
        self._x += a * (x - self._x)
        self._y += a * (y - self._y)
        return self._x, self._y


class StrokeSmoother:
    """一笔一用：begin → add* → end，每步返回本次新增、应追加到笔画末尾的 (x, y, w)。"""

    def __init__(
        self,
        *,
        has_pressure: bool,
        min_distance: float = 0.75,
        min_cutoff: float = MIN_CUTOFF,
        beta: float = BETA,
    ) -> None:
        self._has_pressure = has_pressure
        self._min_dist = min_distance
        self._filter = OneEuroFilter2D(min_cutoff=min_cutoff, beta=beta)
        self._last: _Sample | None = None
        self._held: list[_Sample] = []
        self._start = self._raw = self._prev = (0.0, 0.0)
        self._t_prev = self._base = self._length = self._travel = 0.0
        self._emitted = 0

    def _target_w(self, pressure: float | None) -> float:
        if self._has_pressure:
            p = min(1.0, max(0.0, MOUSE_PRESSURE if pressure is None else pressure))
            return PRESSURE_W_MIN + (PRESSURE_W_MAX - PRESSURE_W_MIN) * p
        return 1.0 - SPEED_THIN * _ease_out(min(1.0, self._filter.speed / SPEED_FULL))

    def _taper(self) -> float:
        if self._has_pressure:
            return 1.0
        return START_FLOOR + (1.0 - START_FLOOR) * _ease_out(min(1.0, self._length / START_TAPER_PX))

    def _emit(self, s: _Sample, out: list[OutPoint]) -> None:
        out.append((s[0], s[1], s[2]))
        self._last = s
        self._emitted += 1

    def begin(self, x: float, y: float, t: float, pressure: float | None) -> list[OutPoint]:
        self._filter.reset()
        self._filter(x, y, t)
        self._held = []
        self._start = self._raw = self._prev = (x, y)
        self._t_prev, self._length, self._travel, self._emitted = t, 0.0, 0.0, 0
        self._base = self._target_w(pressure)
        out: list[OutPoint] = []
        self._emit((x, y, _clamp_w(self._base * self._taper()), t), out)
        return out

    def add(self, x: float, y: float, t: float, pressure: float | None) -> list[OutPoint]:
        if self._last is None:
            # 按下事件被别处吃掉（如平板事件先被系统手势截走）时，第一个移动点当起笔。
            return self.begin(x, y, t, pressure)
        dt = max(t - self._t_prev, MIN_DT)
        self._t_prev = t
        fx, fy = self._filter(x, y, t)
        self._raw = (x, y)
        self._travel = max(self._travel, math.hypot(x - self._start[0], y - self._start[1]))
        self._length += math.hypot(fx - self._prev[0], fy - self._prev[1])
        self._prev = (fx, fy)
        tau = PRESSURE_TAU if self._has_pressure else SPEED_TAU
        self._base += (1.0 - math.exp(-dt / tau)) * (self._target_w(pressure) - self._base)
        self._held.append((fx, fy, _clamp_w(self._base * self._taper()), t))
        return self._decimate()

    def _decimate(self) -> list[OutPoint]:
        out: list[OutPoint] = []
        held = self._held
        last = self._last
        assert last is not None  # add() 已保证 begin 过
        newest = held[-1]
        if len(held) >= 2 and math.dist(last[:2], held[-2][:2]) >= self._min_dist:
            dev = max(_seg_dist(s[0], s[1], last, newest) for s in held[:-1])
            if dev > CURVE_TOL:
                # 弦拉到最新点会削掉弯道：保留上一个候选点，它与此前丢掉的点都已验证在容差内。
                self._emit(held[-2], out)
                last = held[-2]
                held = self._held = [newest]
        d = math.dist(last[:2], newest[:2])
        if d >= self._min_dist and (d >= MAX_SEGMENT or newest[3] - last[3] >= MAX_HOLD or len(held) >= MAX_HELD):
            self._emit(newest, out)
            self._held = []
        elif len(held) >= MAX_HELD:
            # 原地悬停：暂存全在 min_distance 以内，只留最新的一个，扫描开销保持有界。
            self._held = [newest]
        return out

    def end(self) -> list[OutPoint]:
        last = self._last
        if last is None:
            return []
        out: list[OutPoint] = []
        rx, ry = self._raw
        if self._emitted == 1 and self._travel < self._min_dist:
            # 点按：在原位追加一个不带起笔锥度的点，圆头笔帽画出可见的圆点。
            self._last = None
            return [(rx, ry, _clamp_w(self._base))]
        if self._held and math.dist(last[:2], self._held[-1][:2]) >= self._min_dist:
            self._emit(self._held[-1], out)
            last = self._held[-1]
        self._held = []
        gap = math.hypot(rx - last[0], ry - last[1])
        if gap > 0.0:
            # 追赶滤波滞后，保证笔画精确停在最后一个原始位置；锥度铺在这段上（头注释第 4 条）。
            n = max(1, math.ceil(gap / END_STEP_PX))
            for k in range(1, n + 1):
                f = k / n
                scale = 1.0 if self._has_pressure else 1.0 - (1.0 - END_FLOOR) * _ease_out(f)
                out.append((last[0] + (rx - last[0]) * f, last[1] + (ry - last[1]) * f, _clamp_w(last[2] * scale)))
        self._last = None
        return out


__all__ = ["OneEuroFilter", "OneEuroFilter2D", "OutPoint", "StrokeSmoother"]
