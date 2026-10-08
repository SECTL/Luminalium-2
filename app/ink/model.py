"""自建批注的墨迹数据模型（纯 Python，零 Qt 依赖）。

2026-10-07 用户指令：自建批注。PPT 自带的 COM 墨迹（SlideShowView.EraseDrawing 等）
撤销不可靠、橡皮只能整页清，于是墨迹改由我们自己记账、自己烘焙。本文件只管"账"，
渲染与输入在 Qt 侧，这样模型能脱离 QApplication 单独测试。

设计取舍：
1. 坐标归一化（0..1，相对放映窗口）。放映窗口可能跨显示器、跨 DPI 缩放、中途改分辨率，
   存物理像素会在换屏后整体错位；归一化后渲染侧乘当前窗口尺寸即可对齐。
   代价：x/y 两轴单位不等长（窗口不是正方形），hit_test 的半径按归一化单位算，
   调用方自行按窄边换算，模型不掺和窗口尺寸。
2. 按页记账（决策 Q2）：键是 slide_index，任意 int 均可；0 表示拿不到页码时的单页退化。
   每页撤销栈独立——翻回上一页按撤销，撤的应是那一页的最后一笔，而不是全局最后一笔。
3. 两种橡皮（决策 Q3）：
   - 整笔擦除：用网格索引找到被擦过的笔画整条删掉，记为一次可撤销操作。
   - 像素擦除：本身也是一笔（mode="erase"），与普通笔画同列表、同撤销栈，烘焙时按序
     用 CompositionMode_Clear 回放。"擦"和"画"的先后由列表顺序天然保证，撤销擦除
     就是弹掉这一笔，不需要恢复被擦掉的像素——这正是 COM 方案做不到的。
   - 擦除笔画不进空间索引：它没有"可被擦掉的墨"，整笔橡皮不应把它当目标。
4. 撤销删除时按原下标插回：烘焙顺序 = 列表顺序，插错位置会让像素擦除作用到错误的笔画上。
5. clear_all 不可撤销：只在退出放映时调用（决策 Q2/D4，墨迹不写回 PPT，退出即丢弃）。
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Literal

Point = tuple[float, float, float]
StrokeMode = Literal["pen", "erase"]

# 32x32：一页几百笔时每格只剩个位数候选；再细则长笔画登记的格子数膨胀得不偿失。
GRID_SIZE = 32

# 进程内单调递增即可：id 只用于同一次放映里定位笔画，不落盘。
_stroke_ids = itertools.count(1)


@dataclass(frozen=True, slots=True)
class Stroke:
    points: list[Point]
    color: str
    width: float
    mode: StrokeMode = "pen"
    id: int = field(default_factory=lambda: next(_stroke_ids))


@dataclass(frozen=True, slots=True)
class _AddOp:
    stroke: Stroke


@dataclass(frozen=True, slots=True)
class _RemoveOp:
    # (原下标, 笔画)，按下标升序；撤销时升序插回即可还原原顺序。
    removed: list[tuple[int, Stroke]]


@dataclass(frozen=True, slots=True)
class _ClearOp:
    strokes: list[Stroke]


_Op = _AddOp | _RemoveOp | _ClearOp
_Cell = tuple[int, int]


def _cell_of(v: float) -> int:
    # 越界的点（笔拖出窗口）夹到边缘格，保证仍能被查到。
    return min(GRID_SIZE - 1, max(0, int(v * GRID_SIZE)))


def _cells_for_box(x0: float, y0: float, x1: float, y1: float) -> list[_Cell]:
    cx0, cx1 = _cell_of(min(x0, x1)), _cell_of(max(x0, x1))
    cy0, cy1 = _cell_of(min(y0, y1)), _cell_of(max(y0, y1))
    return [(cx, cy) for cx in range(cx0, cx1 + 1) for cy in range(cy0, cy1 + 1)]


def _stroke_cells(stroke: Stroke) -> set[_Cell]:
    pts = stroke.points
    if len(pts) == 1:
        return set(_cells_for_box(pts[0][0], pts[0][1], pts[0][0], pts[0][1]))
    cells: set[_Cell] = set()
    # 按每段包围盒登记而不是整笔包围盒：一条长对角线的整笔包围盒会覆盖半张网格。
    for (ax, ay, _), (bx, by, _) in itertools.pairwise(pts):
        cells.update(_cells_for_box(ax, ay, bx, by))
    return cells


def _segment_dist_sq(px: float, py: float, a: Point, b: Point) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    t = 0.0 if seg_len_sq == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    qx, qy = ax + t * dx - px, ay + t * dy - py
    return qx * qx + qy * qy


def _stroke_within(stroke: Stroke, x: float, y: float, radius: float) -> bool:
    pts = stroke.points
    r_sq = radius * radius
    if len(pts) == 1:
        return _segment_dist_sq(x, y, pts[0], pts[0]) <= r_sq
    # 必须算点到线段距离：快速划过的一笔采样点稀疏，只比顶点会从两点之间漏过去。
    return any(_segment_dist_sq(x, y, a, b) <= r_sq for a, b in itertools.pairwise(pts))


def build_index(strokes: list[Stroke]) -> dict[_Cell, set[int]]:
    """全量建索引。clear 撤销时用；自检也拿它对照增量维护的结果。"""
    grid: dict[_Cell, set[int]] = {}
    for s in strokes:
        if s.mode == "erase":
            continue
        for cell in _stroke_cells(s):
            grid.setdefault(cell, set()).add(s.id)
    return grid


class _Page:
    __slots__ = ("grid", "redo", "strokes", "undo")

    def __init__(self) -> None:
        self.strokes: list[Stroke] = []
        self.undo: list[_Op] = []
        self.redo: list[_Op] = []
        self.grid: dict[_Cell, set[int]] = {}

    def index_add(self, stroke: Stroke) -> None:
        if stroke.mode == "erase":
            return
        for cell in _stroke_cells(stroke):
            self.grid.setdefault(cell, set()).add(stroke.id)

    def index_remove(self, stroke: Stroke) -> None:
        if stroke.mode == "erase":
            return
        for cell in _stroke_cells(stroke):
            bucket = self.grid.get(cell)
            if bucket is not None:
                bucket.discard(stroke.id)
                # 空桶删掉：索引快照才能和全量重建逐键相等。
                if not bucket:
                    del self.grid[cell]

    def apply(self, op: _Op) -> None:
        match op:
            case _AddOp(stroke=s):
                self.strokes.append(s)
                self.index_add(s)
            case _RemoveOp(removed=removed):
                # 降序删除，前面的下标才不会被挪动。
                for idx, s in reversed(removed):
                    del self.strokes[idx]
                    self.index_remove(s)
            case _ClearOp():
                self.strokes = []
                self.grid = {}

    def revert(self, op: _Op) -> None:
        match op:
            case _AddOp(stroke=s):
                # 撤销严格后进先出，被撤的那笔必然在末尾。
                self.strokes.pop()
                self.index_remove(s)
            case _RemoveOp(removed=removed):
                for idx, s in removed:
                    self.strokes.insert(idx, s)
                    self.index_add(s)
            case _ClearOp(strokes=saved):
                self.strokes = list(saved)
                self.grid = build_index(self.strokes)


class PageStore:
    def __init__(self) -> None:
        self._pages: dict[int, _Page] = {}

    def _commit(self, page: int, op: _Op) -> None:
        p = self._pages.setdefault(page, _Page())
        p.apply(op)
        p.undo.append(op)
        # 新操作之后旧的"未来"失效，与所有编辑器一致。
        p.redo.clear()

    def strokes(self, page: int) -> list[Stroke]:
        """烘焙顺序。返回副本，调用方改动不会污染账本。"""
        p = self._pages.get(page)
        return list(p.strokes) if p is not None else []

    def add_stroke(self, page: int, stroke: Stroke) -> None:
        self._commit(page, _AddOp(stroke))

    def remove_strokes(self, page: int, ids: list[int] | set[int]) -> bool:
        p = self._pages.get(page)
        if p is None:
            return False
        wanted = set(ids)
        removed = [(i, s) for i, s in enumerate(p.strokes) if s.id in wanted]
        # 一笔没擦到就不记操作，否则用户按撤销会"什么也没发生"，还白白清掉了重做栈。
        if not removed:
            return False
        self._commit(page, _RemoveOp(removed))
        return True

    def clear_page(self, page: int) -> bool:
        p = self._pages.get(page)
        if p is None or not p.strokes:
            return False
        self._commit(page, _ClearOp(list(p.strokes)))
        return True

    def clear_all(self) -> None:
        self._pages.clear()

    def undo(self, page: int) -> bool:
        p = self._pages.get(page)
        if p is None or not p.undo:
            return False
        op = p.undo.pop()
        p.revert(op)
        p.redo.append(op)
        return True

    def redo(self, page: int) -> bool:
        p = self._pages.get(page)
        if p is None or not p.redo:
            return False
        op = p.redo.pop()
        p.apply(op)
        p.undo.append(op)
        return True

    def can_undo(self, page: int) -> bool:
        p = self._pages.get(page)
        return p is not None and bool(p.undo)

    def can_redo(self, page: int) -> bool:
        p = self._pages.get(page)
        return p is not None and bool(p.redo)

    def hit_test(self, page: int, x: float, y: float, radius: float) -> list[int]:
        """半径内经过的普通笔画 id，按烘焙顺序。擦除笔画不参与。"""
        p = self._pages.get(page)
        if p is None:
            return []
        # 半径可能横跨多个格子：取圆的包围盒覆盖的所有格作候选，再精确判距离。
        candidates: set[int] = set()
        for cell in _cells_for_box(x - radius, y - radius, x + radius, y + radius):
            candidates |= p.grid.get(cell, set())
        if not candidates:
            return []
        return [s.id for s in p.strokes if s.id in candidates and _stroke_within(s, x, y, radius)]

    def index_snapshot(self, page: int) -> dict[_Cell, set[int]]:
        """索引副本，自检用来与 build_index(strokes) 对照。"""
        p = self._pages.get(page)
        return {k: set(v) for k, v in p.grid.items()} if p is not None else {}


__all__ = ["GRID_SIZE", "PageStore", "Point", "Stroke", "StrokeMode", "build_index"]
