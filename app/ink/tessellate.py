"""墨迹几何：湿墨迹三角网格生成 + 干墨迹 QPainter 烘焙。

2026-10-07 用户指令：自建批注（计划 self-ink 第 4 项）。从 ``layer.py`` 拆出来，
这样 layer 只负责场景图节点和线程交接，「笔画长什么样」只写在这一个文件里。

为什么干湿两套代码必须放在一起：落笔时湿网格消失、干纹理接手，同一帧里换掉。
两边算出的形状但凡差半个像素，抬笔那一下就会「跳」一下。所以两边共用
``radius_of``（宽度函数），形状也一样，都是「每个采样点一个圆 + 相邻两点之间一个梯形」
的并集：

* 湿：``WetMesh`` 把圆和梯形拆成三角形（DrawTriangles）。外圈加一条宽 1 设备像素
  的羽化带，内沿 alpha=满、外沿 alpha=0，这就是抗锯齿（QSGVertexColorMaterial 按顶点
  插值颜色，不需要 MSAA）。用 DrawTriangles 而不用 DrawTriangleStrip：圆头和圆角
  是一圈扇形，塞进 strip 得插退化三角形，顶点数差不多，还更难读。
* 干：宽度恒定时直接让 QPainter 描一条 RoundCap + RoundJoin 的折线，结果和圆与
  梯形的并集完全一样，而且一次填充，没有重叠。宽度变化时逐个画圆和梯形，与湿网格逐片对齐。

湿网格的顶点预算：5000 点的长笔画如果每点都放一个圆，顶点量是几 MB，而且全在
Python 循环里生成。相邻两个梯形在共享点上半宽相同、端边重合，只有拐弯外侧会缺
一个楔形。所以中间点的圆只在楔形的弦高超过约 0.1 设备像素时才永久并入；末点的圆
（笔尖）放在 ``_tail`` 里，每来一个新点就换掉。0.1px 远小于 1px 的羽化带，所以和
干图「每点一圆」的形状看不出差别。

坐标约定：``Stroke.points`` 是归一化坐标（0..1）。这里一律换算成 item 的**逻辑像素**；
干图通过 ``QImage.setDevicePixelRatio`` 让 QPainter 也用逻辑坐标画，这样两边的数字一模一样。
"""

from __future__ import annotations

import math
import struct

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF

from .model import Stroke

#: 最细半径（逻辑像素）。压感趋零时笔画不能消失成 0 宽，否则湿网格退化、干图画不出东西。
MIN_RADIUS = 0.25
#: 羽化带宽（设备像素）。1px 和 QPainter 抗锯齿的过渡宽度相当，干湿边缘的软硬一致。
FEATHER_DEVICE_PX = 1.0
#: 拐点楔形允许的最大弦高（设备像素），超过才把该点的圆并入湿网格。
JOIN_TOLERANCE_DEVICE_PX = 0.1
#: ColoredPoint2D：float x, float y, uchar r g b a（预乘）。
VERTEX_SIZE = 12

_XY = struct.Struct("<ff")
_TRANSPARENT = b"\x00\x00\x00\x00"
_circle_cache: dict[int, list[tuple[float, float]]] = {}


def radius_of(width: float, w: float) -> float:
    """干湿共用的宽度函数：penWidth × 宽度因子 = 直径。"""
    return max(width * w * 0.5, MIN_RADIUS)


def premultiplied_rgba(color: QColor) -> bytes:
    # QSGVertexColorMaterial 要求预乘颜色，不预乘的半透明色会发亮
    a = color.alpha()
    return bytes((color.red() * a // 255, color.green() * a // 255, color.blue() * a // 255, a))


def _unit_circle(steps: int) -> list[tuple[float, float]]:
    table = _circle_cache.get(steps)
    if table is None:
        table = [(math.cos(2 * math.pi * i / steps), math.sin(2 * math.pi * i / steps)) for i in range(steps + 1)]
        _circle_cache[steps] = table
    return table


def _disc_steps(radius_dev: float) -> int:
    # 把弦高误差 r(1-cos(π/n)) 压到约 0.1 设备像素：小于抗锯齿过渡带，肉眼看不出棱角
    return max(8, min(48, math.ceil(math.pi / math.sqrt(0.2 / max(radius_dev, 0.2)))))


class WetMesh:
    """进行中这一笔的三角网格，只能追加。GUI 线程写，渲染线程通过 ``snapshot()`` 拿副本。"""

    __slots__ = ("_col", "_dpr", "_feather", "_last", "_prev_dir", "_tail", "buffer")

    def __init__(self, color: QColor, dpr: float) -> None:
        self.buffer = bytearray()
        self._col = premultiplied_rgba(color)
        self._dpr = dpr
        self._feather = FEATHER_DEVICE_PX / dpr
        self._last: tuple[float, float, float] | None = None
        self._prev_dir: tuple[float, float] | None = None
        self._tail = b""

    def add(self, x: float, y: float, r: float) -> None:
        last = self._last
        if last is None:
            # 起笔圆头永久保留
            self.buffer += self._disc(x, y, r)
            self._last = (x, y, r)
            return
        lx, ly, lr = last
        length = math.hypot(x - lx, y - ly)
        if length < 1e-3:
            # 原地不动（压感变化除外）不产生几何：画上去没区别，只会多出顶点
            if abs(r - lr) < 1e-3:
                return
            self._commit_tail()
        else:
            d = ((x - lx) / length, (y - ly) / length)
            if self._tail and self._needs_join(d, lr):
                self._commit_tail()
            self.buffer += self._segment(last, (x, y, r))
            self._prev_dir = d
        self._last = (x, y, r)
        self._tail = self._disc(x, y, r)

    def snapshot(self) -> bytes:
        return bytes(self.buffer) + self._tail

    def _commit_tail(self) -> None:
        self.buffer += self._tail
        self._tail = b""

    def _needs_join(self, d: tuple[float, float], r: float) -> bool:
        prev = self._prev_dir
        if prev is None:
            return True
        cos_turn = max(-1.0, min(1.0, prev[0] * d[0] + prev[1] * d[1]))
        cos_half = math.sqrt((1.0 + cos_turn) * 0.5)
        # 楔形弦高 = r(1 - cos(θ/2))，换算到设备像素后与容差比较
        return r * self._dpr * (1.0 - cos_half) > JOIN_TOLERANCE_DEVICE_PX

    def _disc(self, cx: float, cy: float, r: float) -> bytes:
        out = bytearray()
        pack = _XY.pack
        half = self._feather * 0.5
        ri, ro = max(r - half, 0.0), r + half
        c, z = self._col, _TRANSPARENT
        table = _unit_circle(_disc_steps(r * self._dpr))
        center = pack(cx, cy) + c
        for (c0, s0), (c1, s1) in zip(table, table[1:], strict=False):
            i0 = pack(cx + ri * c0, cy + ri * s0) + c
            i1 = pack(cx + ri * c1, cy + ri * s1) + c
            o0 = pack(cx + ro * c0, cy + ro * s0) + z
            o1 = pack(cx + ro * c1, cy + ro * s1) + z
            out += center + i0 + i1 + i0 + o0 + o1 + i0 + o1 + i1
        return bytes(out)

    def _segment(self, a: tuple[float, float, float], b: tuple[float, float, float]) -> bytes:
        (x0, y0, r0), (x1, y1, r1) = a, b
        length = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / length, (x1 - x0) / length
        half = self._feather * 0.5
        ri0, ri1 = max(r0 - half, 0.0), max(r1 - half, 0.0)
        ro0, ro1 = r0 + half, r1 + half
        c, z, pack = self._col, _TRANSPARENT, _XY.pack
        pi0 = pack(x0 + nx * ri0, y0 + ny * ri0) + c
        mi0 = pack(x0 - nx * ri0, y0 - ny * ri0) + c
        pi1 = pack(x1 + nx * ri1, y1 + ny * ri1) + c
        mi1 = pack(x1 - nx * ri1, y1 - ny * ri1) + c
        po0 = pack(x0 + nx * ro0, y0 + ny * ro0) + z
        mo0 = pack(x0 - nx * ro0, y0 - ny * ro0) + z
        po1 = pack(x1 + nx * ro1, y1 + ny * ro1) + z
        mo1 = pack(x1 - nx * ro1, y1 - ny * ro1) + z
        return (
            pi0 + mi0 + pi1 + mi0 + mi1 + pi1          # 实心芯
            + pi0 + po0 + po1 + pi0 + po1 + pi1        # 正侧羽化带
            + mi0 + mo0 + mo1 + mi0 + mo1 + mi1        # 负侧羽化带
        )


def bake(image: QImage, stroke: Stroke, size: tuple[float, float]) -> None:
    """把一笔按序画进干图。``size`` 是 item 逻辑尺寸；image 必须已设好 devicePixelRatio。"""
    w_log, h_log = size
    pts = [(x * w_log, y * h_log, radius_of(stroke.width, w)) for x, y, w in stroke.points]
    if not pts:
        return
    color = QColor(stroke.color)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if stroke.mode == "erase":
            # 像素橡皮：Clear 模式按覆盖率把目标清成透明，源颜色无关紧要
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            color = QColor(0, 0, 0, 255)
        r0 = pts[0][2]
        if len(pts) > 1 and all(abs(r - r0) < 1e-3 for _, _, r in pts):
            path = QPainterPath(QPointF(pts[0][0], pts[0][1]))
            for x, y, _ in pts[1:]:
                path.lineTo(x, y)
            pen = QPen(QBrush(color), 2 * r0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.strokePath(path, pen)
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        prev: tuple[float, float, float] | None = None
        for x, y, r in pts:
            if prev is not None:
                px, py, pr = prev
                length = math.hypot(x - px, y - py)
                if length > 1e-6:
                    nx, ny = -(y - py) / length, (x - px) / length
                    painter.drawPolygon(QPolygonF([
                        QPointF(px + nx * pr, py + ny * pr), QPointF(x + nx * r, y + ny * r),
                        QPointF(x - nx * r, y - ny * r), QPointF(px - nx * pr, py - ny * pr),
                    ]))
            painter.drawEllipse(QPointF(x, y), r, r)
            prev = (x, y, r)
    finally:
        painter.end()


__all__ = [
    "FEATHER_DEVICE_PX", "JOIN_TOLERANCE_DEVICE_PX", "MIN_RADIUS", "VERTEX_SIZE",
    "WetMesh", "bake", "premultiplied_rgba", "radius_of",
]
