"""app/ink/model.py 的自检脚本（无 pytest，纯 assert）。

2026-10-07 用户指令：自建批注。仓库没有 tests/ 目录、venv 里也没有 pytest，
按约定放在 tools/ 下，直接 `.venv\\Scripts\\python.exe tools\\ink_model_selftest.py` 运行。
按文件路径加载 model.py：app/ink/__init__.py 由并行任务负责，这里不依赖它是否存在。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODEL_PATH = Path(__file__).resolve().parent.parent / "app" / "ink" / "model.py"
_spec = importlib.util.spec_from_file_location("ink_model_under_test", _MODEL_PATH)
assert _spec is not None and _spec.loader is not None
m = importlib.util.module_from_spec(_spec)
# dataclass 解析注解时要能在 sys.modules 里找到模块。
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)

Stroke = m.Stroke
PageStore = m.PageStore


def pen(*xy: tuple[float, float]) -> "m.Stroke":
    return Stroke(points=[(x, y, 1.0) for x, y in xy], color="#FF0000", width=3.0)


def erase(*xy: tuple[float, float]) -> "m.Stroke":
    return Stroke(points=[(x, y, 1.0) for x, y in xy], color="#000000", width=10.0, mode="erase")


def ids(store: "m.PageStore", page: int = 1) -> list[int]:
    return [s.id for s in store.strokes(page)]


def assert_index_ok(store: "m.PageStore", page: int = 1) -> None:
    # 增量维护的索引必须与全量重建逐键相等，否则整笔橡皮会擦到幽灵笔画或漏擦。
    assert store.index_snapshot(page) == m.build_index(store.strokes(page)), "索引与重建不一致"


def test_add_undo_redo() -> None:
    s = PageStore()
    a, b = pen((0.1, 0.1), (0.2, 0.2)), pen((0.3, 0.3), (0.4, 0.4))
    s.add_stroke(1, a)
    s.add_stroke(1, b)
    assert ids(s) == [a.id, b.id]
    assert s.undo(1) is True and ids(s) == [a.id]
    assert s.undo(1) is True and ids(s) == []
    assert s.undo(1) is False
    assert s.redo(1) is True and ids(s) == [a.id]
    assert s.redo(1) is True and ids(s) == [a.id, b.id]
    assert s.redo(1) is False
    assert a.id < b.id


def test_new_op_clears_redo() -> None:
    s = PageStore()
    a, b, c = pen((0.1, 0.1)), pen((0.2, 0.2)), pen((0.3, 0.3))
    s.add_stroke(1, a)
    s.add_stroke(1, b)
    s.undo(1)
    assert s.can_redo(1)
    s.add_stroke(1, c)
    assert not s.can_redo(1) and s.redo(1) is False
    assert ids(s) == [a.id, c.id]


def test_remove_undo_restores_order() -> None:
    s = PageStore()
    st = [pen((0.1 * i, 0.5), (0.1 * i + 0.05, 0.5)) for i in range(1, 6)]
    for x in st:
        s.add_stroke(1, x)
    original = ids(s)
    assert s.remove_strokes(1, {st[1].id, st[3].id}) is True
    assert ids(s) == [st[0].id, st[2].id, st[4].id]
    assert_index_ok(s)
    assert s.undo(1) is True
    assert ids(s) == original
    assert_index_ok(s)
    assert s.redo(1) is True
    assert ids(s) == [st[0].id, st[2].id, st[4].id]
    assert_index_ok(s)
    # 一笔都没命中不应产生操作
    assert s.remove_strokes(1, {999999}) is False


def test_clear_page_undo() -> None:
    s = PageStore()
    a, b = pen((0.1, 0.1), (0.9, 0.9)), erase((0.5, 0.5))
    s.add_stroke(1, a)
    s.add_stroke(1, b)
    assert s.clear_page(1) is True and ids(s) == []
    assert s.index_snapshot(1) == {}
    assert s.undo(1) is True and ids(s) == [a.id, b.id]
    assert_index_ok(s)
    assert s.redo(1) is True and ids(s) == []
    assert s.clear_page(1) is False  # 空页不记操作


def test_clear_all() -> None:
    s = PageStore()
    s.add_stroke(1, pen((0.1, 0.1)))
    s.add_stroke(2, pen((0.2, 0.2)))
    s.clear_all()
    assert ids(s, 1) == [] and ids(s, 2) == []
    assert s.undo(1) is False and s.undo(2) is False
    assert not s.can_redo(1)


def test_pages_independent() -> None:
    s = PageStore()
    a, b, z = pen((0.1, 0.1)), pen((0.2, 0.2)), pen((0.3, 0.3))
    s.add_stroke(1, a)
    s.add_stroke(2, b)
    s.add_stroke(0, z)  # 单页退化键
    assert s.undo(2) is True
    assert ids(s, 1) == [a.id] and ids(s, 2) == [] and ids(s, 0) == [z.id]
    assert s.can_redo(2) and not s.can_redo(1)
    s.add_stroke(1, pen((0.4, 0.4)))
    assert s.can_redo(2), "别的页的新操作不应清掉本页重做栈"
    assert s.hit_test(2, 0.1, 0.1, 0.02) == []
    assert s.hit_test(1, 0.1, 0.1, 0.02) == [a.id]


def test_failure_sequence() -> None:
    """撤到空 -> 重做 -> 加擦除笔 -> 撤销，每步快照。"""
    s = PageStore()
    a, b = pen((0.1, 0.1), (0.2, 0.2)), pen((0.3, 0.3), (0.4, 0.4))
    s.add_stroke(1, a)
    s.add_stroke(1, b)
    assert ids(s) == [a.id, b.id]
    s.undo(1)
    s.undo(1)
    assert ids(s) == [] and not s.can_undo(1) and s.can_redo(1)
    assert_index_ok(s)
    assert s.redo(1) is True
    assert ids(s) == [a.id] and s.can_redo(1)
    assert_index_ok(s)
    e = erase((0.15, 0.15), (0.16, 0.16))
    s.add_stroke(1, e)
    assert ids(s) == [a.id, e.id] and not s.can_redo(1)
    assert [x.mode for x in s.strokes(1)] == ["pen", "erase"]
    assert_index_ok(s)
    assert s.undo(1) is True
    assert ids(s) == [a.id] and s.can_redo(1) and s.can_undo(1)
    assert_index_ok(s)
    assert s.redo(1) is True and ids(s) == [a.id, e.id]


def test_hit_test_hit_and_miss() -> None:
    s = PageStore()
    # 长段只有两个端点：中点命中证明用的是线段距离而非顶点距离
    a = pen((0.1, 0.5), (0.9, 0.5))
    s.add_stroke(1, a)
    assert s.hit_test(1, 0.5, 0.505, 0.01) == [a.id]
    assert s.hit_test(1, 0.5, 0.6, 0.01) == []
    assert s.hit_test(1, 0.95, 0.5, 0.01) == []
    dot = pen((0.3, 0.3))
    s.add_stroke(1, dot)
    assert s.hit_test(1, 0.305, 0.3, 0.01) == [dot.id]


def test_hit_test_radius_crosses_buckets() -> None:
    s = PageStore()
    cell = 1.0 / m.GRID_SIZE
    # 笔画只落在第 10 列格子里，查询点在第 7 列，半径跨越 3 个格子边界
    x_stroke = 10.5 * cell
    a = pen((x_stroke, 0.2), (x_stroke, 0.8))
    s.add_stroke(1, a)
    qx = 7.5 * cell
    r = x_stroke - qx + 0.001
    assert s.hit_test(1, qx, 0.5, r) == [a.id]
    assert s.hit_test(1, qx, 0.5, x_stroke - qx - 0.001) == []


def test_hit_test_ignores_erase() -> None:
    s = PageStore()
    e = erase((0.1, 0.5), (0.9, 0.5))
    s.add_stroke(1, e)
    assert s.hit_test(1, 0.5, 0.5, 0.05) == []
    a = pen((0.1, 0.5), (0.9, 0.5))
    s.add_stroke(1, a)
    assert s.hit_test(1, 0.5, 0.5, 0.05) == [a.id]


def test_index_consistent_across_undo_redo() -> None:
    s = PageStore()
    st = [pen((0.03 * i, 0.1), (0.9 - 0.03 * i, 0.9)) for i in range(10)]
    for x in st:
        s.add_stroke(1, x)
        assert_index_ok(s)
    s.add_stroke(1, erase((0.5, 0.5), (0.6, 0.6)))
    s.remove_strokes(1, [st[2].id, st[7].id])
    assert_index_ok(s)
    s.clear_page(1)
    assert_index_ok(s)
    for _ in range(14):
        s.undo(1)
        assert_index_ok(s)
    assert ids(s) == []
    for _ in range(14):
        s.redo(1)
        assert_index_ok(s)
    assert ids(s) == []
    s.undo(1)  # 撤销 clear
    hit = s.hit_test(1, st[2].points[0][0], 0.1, 0.005)
    assert st[2].id not in hit, "已删除的笔画不应被命中"


def main() -> int:
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"PASS {name}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
