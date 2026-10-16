"""InkLayer 渲染核心自检（计划 self-ink 第 4 项）。

2026-10-07 用户指令：自建批注。仓库没有 pytest，按 tools/ink_*_selftest.py 的惯例直接运行：
    $env:PYTHONIOENCODING='utf-8'; .venv/Scripts/python.exe tools/ink_layer_selftest.py

为什么不用 QT_QPA_PLATFORM=offscreen：offscreen 平台下场景图可能退回 software 适配层，
那一层不画自定义 QSGGeometryNode（湿墨迹整个消失），测到的就不是真机的 D3D11 路径。
所以这里开一只真实的无边框 Tool 窗口，用 grabWindow 取帧。
等待一律 processEvents + 小步 sleep：QTest.qWait 攥着 GIL（AGENTS.md）。
任何断言失败，退出码为 1；输出同时写到 .omo/evidence/self-ink/t4-frame-counts.txt。
"""

from __future__ import annotations

import faulthandler
import math
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / ".omo" / "evidence" / "self-ink"

from PySide6.QtCore import QRect, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

W, H = 800, 600
N = 5000
DARK = (0x1E, 0x1E, 0x1E)
INK = "#FFC000"

QML = """
import QtQuick
import QtQuick.Window
import Luminalium.Ink 1.0

Window {
    width: %d; height: %d
    visible: false
    color: "#1E1E1E"
    flags: Qt.Tool | Qt.FramelessWindowHint
    InkLayer { objectName: "inkLayer"; anchors.fill: parent }
}
""" % (W, H)

_lines: list[str] = []
_fails: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    _lines.append(msg)


def check(cond: bool, msg: str) -> None:
    log(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _fails.append(msg)


def raw(img: QImage) -> bytes:
    return bytes(img.constBits())[: img.sizeInBytes()]


def count_ink(img: QImage, bg: tuple[int, int, int], step: int = 2) -> int:
    buf, bpl, n = raw(img), img.bytesPerLine(), 0
    br, bgc, bb = bg
    for y in range(0, img.height(), step):
        row = y * bpl
        for x in range(0, img.width(), step):
            i = row + 4 * x
            if abs(buf[i] - br) + abs(buf[i + 1] - bgc) + abs(buf[i + 2] - bb) > 120:
                n += 1
    return n


def diff_count(a: QImage, b: QImage, thresh: int = 64) -> int:
    ba, bb = raw(a), raw(b)
    n = 0
    for i in range(0, min(len(ba), len(bb)), 4):
        if max(abs(ba[i] - bb[i]), abs(ba[i + 1] - bb[i + 1]), abs(ba[i + 2] - bb[i + 2])) > thresh:
            n += 1
    return n


def path_pt(i: int, n: int = N, scale: float = 1.0) -> tuple[float, float]:
    t = i / (n - 1)
    return ((60 + 680 * t) * scale, (300 + 150 * math.sin(t * 4 * math.pi)) * scale)


SAMPLES = list(range(0, N, 125))


def dense(corners: list[tuple[float, float]], step: float = 1.0) -> list[tuple[float, float, float]]:
    out = [(corners[0][0], corners[0][1], 1.0)]
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        k = max(1, int(math.hypot(bx - ax, by - ay) / step))
        out += [(ax + (bx - ax) * j / k, ay + (by - ay) * j / k, 1.0) for j in range(1, k + 1)]
    return out


class Harness:
    def __init__(self, app: QGuiApplication, win, layer) -> None:
        self.app, self.win, self.layer = app, win, layer
        self.frames = 0
        self.ink_events = 0
        win.frameSwapped.connect(self._on_frame)
        layer.inkChanged.connect(self._on_ink)

    def _on_frame(self) -> None:
        self.frames += 1

    def _on_ink(self) -> None:
        self.ink_events += 1

    @property
    def dpr(self) -> float:
        return self.win.effectiveDevicePixelRatio()

    def pump(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while True:
            self.app.processEvents()
            if time.monotonic() >= end:
                break
            time.sleep(0.005)

    def grab(self) -> QImage:
        self.pump(0.05)
        return self.win.grabWindow().convertToFormat(QImage.Format.Format_RGBA8888)

    def diff_at(self, img: QImage, x: float, y: float, bg: tuple[int, int, int]) -> int:
        d = self.dpr
        px = img.pixelColor(min(img.width() - 1, round(x * d)), min(img.height() - 1, round(y * d)))
        return abs(px.red() - bg[0]) + abs(px.green() - bg[1]) + abs(px.blue() - bg[2])

    def ink_at(self, img: QImage, x: float, y: float, bg=DARK) -> bool:
        return self.diff_at(img, x, y, bg) > 120

    def bg_at(self, img: QImage, x: float, y: float, bg=DARK) -> bool:
        return self.diff_at(img, x, y, bg) < 24

    def dry_alpha(self, x: float, y: float) -> int:
        d = self.dpr
        return self.layer._image.pixelColor(int(x * d), int(y * d)).alpha()

    def samples_inked(self, img: QImage, scale: float = 1.0) -> list[int]:
        return [i for i in SAMPLES if not self.ink_at(img, *path_pt(i, scale=scale))]


def test_long_stroke(h: Harness) -> None:
    L = h.layer
    L.setProperty("tool", "pen")
    L.setProperty("penWidth", 6.0)
    L.setProperty("penColor", QColor(INK))
    check(L.property("tool") == "pen" and L.property("penWidth") == 6.0, "属性 tool/penWidth 可读写")
    pts = [path_pt(i) for i in range(N)]
    req0, f0, ev0 = L._update_requests, h.frames, h.ink_events
    t0 = time.perf_counter()
    L.beginStroke(pts[0][0], pts[0][1], 1.0)
    batches = 0
    for k in range(1, N, 50):
        L.extendStroke([[x, y, 1.0] for x, y in pts[k:k + 50]])
        batches += 1
        h.app.processEvents()
    feed = time.perf_counter() - t0
    log(f"2 喂入 {N} 点 / {batches} 批，用时 {feed * 1000:.0f} ms；期间 update 请求 {L._update_requests - req0}，实际出帧 {h.frames - f0}")
    check(L._pts is not None and len(L._pts) == N, f"2 进行中笔画累计 {N} 点")
    wet = h.grab()
    vc = L._wet_geom.vertexCount() if L._wet_geom is not None else -1
    log(f"3 湿网格顶点 {vc}（{vc * 12 / 1024:.0f} KiB）")
    check(vc > 0, "3 书写中湿几何非空")
    miss = h.samples_inked(wet)
    check(not miss, f"3 书写中（湿）沿路径 {len(SAMPLES)} 个采样点都有墨，缺 {miss[:5]}")
    L.endStroke()
    dry = h.grab()
    check(L._shown_wet == b"" and L._wet_geom.vertexCount() <= 3 and L._shown_wet == b"", "4 抬笔后湿几何清空")
    miss = h.samples_inked(dry)
    check(not miss, f"4 抬笔后（干）沿路径采样点都有墨，缺 {miss[:5]}")
    amiss = [i for i in SAMPLES if h.dry_alpha(*pts[i]) < 200]
    check(not amiss, f"4 干图 QImage 沿路径持有墨迹，缺 {amiss[:5]}")
    strokes = L.store.strokes(0)
    check(len(strokes) == 1 and len(strokes[0].points) == N and strokes[0].mode == "pen", "4 PageStore 记下 1 笔 5000 点 pen")
    xs = [p[0] for p in strokes[0].points]
    ys = [p[1] for p in strokes[0].points]
    check(0 <= min(xs) and max(xs) <= 1 and 0 <= min(ys) and max(ys) <= 1 and abs(xs[0] - 60 / W) < 1e-9 and abs(ys[0] - 300 / H) < 1e-9,
          "2 点按 item 宽高归一化存储")
    check(h.ink_events - ev0 == 1, "inkChanged 抬笔发一次")
    changed, inkpx = diff_count(wet, dry), count_ink(dry, DARK, 1)
    ratio = changed / max(inkpx, 1)
    log(f"干湿衔接：通道差 >64 的像素 {changed} / 墨迹像素 {inkpx} = {ratio:.4%}")
    check(ratio < 0.02, "干湿衔接差异像素 < 2%")
    wet.save(str(EVIDENCE / "t4-seam-wet.png"))
    dry.save(str(EVIDENCE / "t4-seam-dry.png"))


def test_cancel(h: Harness) -> None:
    L = h.layer
    n0, ev0 = len(L.store.strokes(0)), h.ink_events
    L.beginStroke(100, 100, 1.0)
    L.extendStroke([[125, 110, 1.0], [150, 120, 1.0]])
    h.grab()
    L.cancelStroke()
    img = h.grab()
    check(L._shown_wet == b"" and L._wet_geom.vertexCount() <= 3 and len(L.store.strokes(0)) == n0 and h.ink_events == ev0,
          "cancelStroke 丢弃进行中笔画、不入账、不发 inkChanged")
    check(h.bg_at(img, 150, 120), "cancelStroke 后画面无残留")


def test_erase_undo(h: Harness) -> None:
    L = h.layer
    L.setProperty("tool", "eraser")
    L.setProperty("penWidth", 40.0)
    L.beginStroke(400, 100, 1.0)
    L.extendStroke([[400, 100 + 2 * i, 1.0] for i in range(1, 201)])
    pre = h.grab()
    check(h.bg_at(pre, 400, 300), "5 擦除进行中预览已削除")
    L.endStroke()
    img = h.grab()
    s = L.store.strokes(0)
    check(len(s) == 2 and s[-1].mode == "erase", "5 eraser 产生 mode=erase 笔画")
    erased = [p for p in (path_pt(i) for i in range(N)) if 392 <= p[0] <= 408]
    check(bool(erased) and all(h.bg_at(img, x, y) for x, y in erased), f"5 擦除带内 {len(erased)} 个路径点全部清空")
    kept = [path_pt(i) for i in SAMPLES if abs(path_pt(i)[0] - 400) > 40]
    check(all(h.ink_at(img, x, y) for x, y in kept), "5 擦除带外墨迹保留")
    check(h.dry_alpha(400, 300) == 0, "5 干图被擦处 alpha=0")
    check(L.undo() is True, "5 undo 擦除返回 True")
    img = h.grab()
    check(all(h.ink_at(img, x, y) for x, y in erased[::4]), "5 undo 后被擦墨迹复原")
    check(h.dry_alpha(400, 300) > 200, "5 undo 后干图复原")
    check(L.redo() is True, "5 redo 擦除返回 True")
    img = h.grab()
    check(all(h.bg_at(img, x, y) for x, y in erased), "5 redo 后再次清空")
    check(L.undo() is True, "5 再 undo 回到只有墨迹")
    h.grab()
    L.setProperty("tool", "pen")
    L.setProperty("penWidth", 6.0)


def test_idle(h: Harness) -> None:
    L = h.layer
    h.pump(0.3)
    req0, f0, t0 = L._update_requests, h.frames, time.monotonic()
    h.pump(3.0)
    dt, req, fr = time.monotonic() - t0, L._update_requests - req0, h.frames - f0
    log(f"6 空闲 {dt:.2f} s：update 请求 {req} 次，实际出帧 {fr}（累计 _update_requests={L._update_requests}）")
    check(req == 0, "6 空闲 3 s 内 update() 请求 0 次")
    check(fr == 0, "6 空闲 3 s 内实际出帧 0")


def test_pages(h: Harness) -> None:
    L = h.layer
    L.setPage(1)
    img = h.grab()
    check(L.currentPage == 1 and count_ink(img, DARK) == 0 and L.store.strokes(1) == [], "7 setPage(1) 新页为空")
    L.setPage(0)
    img = h.grab()
    check(L.currentPage == 0 and not h.samples_inked(img), "7 setPage(0) 墨迹回来")


def test_clear_undo_redo(h: Harness) -> None:
    L = h.layer
    ev0 = h.ink_events
    check(L.clearPage() is True, "8 clearPage 有墨时返回 True")
    img = h.grab()
    check(count_ink(img, DARK) == 0 and h.ink_events == ev0 + 1, "8 clearPage 后画面空、inkChanged +1")
    check(L.undo() is True, "8 undo 清屏返回 True")
    check(not h.samples_inked(h.grab()), "8 undo 清屏后墨迹回来")
    check(L.redo() is True, "8 redo 清屏返回 True")
    check(count_ink(h.grab(), DARK) == 0, "8 redo 后再次清空")
    check(L.redo() is False, "8 重做栈空时 redo 返回 False")
    check(L.undo() is True and not h.samples_inked(h.grab()), "8 再 undo 墨迹回来")
    L.setPage(1)
    check(L.clearPage() is False and L.undo() is False and L.redo() is False, "8 空页 clearPage/undo/redo 均返回 False")
    L.setPage(0)
    h.grab()


def test_resize(h: Harness) -> None:
    L = h.layer
    h.win.resize(1000, 750)
    h.pump(0.3)
    img = h.grab()
    check(L.width() == 1000 and L.height() == 750, "尺寸变化：层跟随到 1000x750")
    check(not h.samples_inked(img, scale=1.25), "尺寸变化：重烘后墨迹按归一化坐标对齐")
    h.win.resize(W, H)
    h.pump(0.3)
    check(not h.samples_inked(h.grab()), "尺寸复原：墨迹回到原位")


def render_previews(h: Harness) -> None:
    L = h.layer
    L.clearAll()
    L.setProperty("tool", "pen")

    def stroke(points, color: str, width: float, finish: bool = True) -> None:
        L.setProperty("penColor", QColor(color))
        L.setProperty("penWidth", float(width))
        x, y, w = points[0]
        L.beginStroke(x, y, w)
        if len(points) > 1:
            L.extendStroke([list(p) for p in points[1:]])
        if finish:
            L.endStroke()

    for row, (width, color) in enumerate([(2, "#E81123"), (4, "#0078D4"), (8, "#10A37F"), (16, "#FFC000")]):
        y0 = 40 + row * 55
        stroke(dense([(40 + i * 40, y0 + (0 if i % 2 == 0 else 35)) for i in range(9)]), color, width)
    spiral = []
    for i in range(1500):
        t = i / 1499
        a, r = t * 6 * math.pi, 10 + 110 * t
        spiral.append((600 + r * math.cos(a), 160 + r * math.sin(a), 0.25 + 1.75 * math.sin(math.pi * t)))
    stroke(spiral, "#FF4FA3", 12)
    eight = []
    for i in range(800):
        a = i / 799 * 2 * math.pi
        eight.append((200 + 110 * math.sin(a), 340 + 55 * math.sin(2 * a), 1.0))
    stroke(eight, "#8E44AD", 6)
    for x, width in ((440, 4), (490, 10), (550, 20), (625, 30)):
        stroke([(x, 340, 1.0)], "#0078D4", width)
    L.setProperty("tool", "eraser")
    stroke(dense([(60, 30), (380, 250)]), "#000000", 14)
    L.setProperty("tool", "pen")
    wave = lambda y0: [(60 + t, y0 + 25 * math.sin(t / 40), 1.0) for t in range(0, 680)]  # noqa: E731
    stroke(wave(450), "#00B7C3", 10)
    stroke(wave(530), "#00B7C3", 10, finish=False)  # 故意留作湿墨迹，和上面那条干墨迹对照
    d = h.dpr
    crops = {
        "zoom-dots": (QRect(int(400 * d), int(300 * d), int(260 * d), int(80 * d)), 4),
        "zoom-zigzag": (QRect(int(30 * d), int(30 * d), int(220 * d), int(140 * d)), 3),
        "zoom-waves": (QRect(int(50 * d), int(410 * d), int(260 * d), int(160 * d)), 3),
    }
    for name, bg in (("dark", "#1E1E1E"), ("light", "#F5F5F5")):
        h.win.setProperty("color", QColor(bg))
        img = h.grab()
        ok = img.save(str(EVIDENCE / f"t4-render-{name}.png"))
        for cname, (rect, k) in crops.items():
            sub = img.copy(rect)
            ok &= sub.scaled(sub.width() * k, sub.height() * k, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation).save(str(EVIDENCE / f"t4-render-{name}-{cname}.png"))
        check(ok, f"预览图 t4-render-{name}*.png 已保存")
    L.cancelStroke()
    h.win.setProperty("color", QColor("#1E1E1E"))


def finish() -> int:
    ok = not _fails
    log(f"== 结果：{'全部通过' if ok else f'{len(_fails)} 项失败'}")
    head = f"# t4 InkLayer 自检 {time.strftime('%Y-%m-%d %H:%M:%S')}\n# 命令：.venv/Scripts/python.exe tools/ink_layer_selftest.py\n"
    (EVIDENCE / "t4-frame-counts.txt").write_text(head + "\n".join(_lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


def main() -> int:
    faulthandler.enable()
    faulthandler.dump_traceback_later(300, exit=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication(sys.argv)
    from app.ink import register_qml_types

    register_qml_types()
    register_qml_types()  # 幂等
    qml_path = Path(tempfile.gettempdir()) / "ink_layer_selftest.qml"
    qml_path.write_text(QML, encoding="utf-8")
    engine = QQmlApplicationEngine()
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    roots = engine.rootObjects()
    check(bool(roots), "1 注册类型后 QML 载入含 InkLayer 的窗口")
    if not roots:
        return finish()
    win = roots[0]
    layer = win.findChild(QQuickItem, "inkLayer")
    check(layer is not None and type(layer).__name__ == "InkLayer", "1 按 objectName 找到 InkLayer")
    if layer is None:
        return finish()
    h = Harness(app, win, layer)
    win.setPosition(60, 60)
    win.show()
    deadline = time.monotonic() + 5
    while not win.isExposed() and time.monotonic() < deadline:
        h.pump(0.02)
    h.pump(0.3)
    log(f"窗口 {win.width()}x{win.height()} dpr={h.dpr} api={win.rendererInterface().graphicsApi()} 层 {layer.width()}x{layer.height()}")
    check(layer.width() == W and layer.height() == H, "1 InkLayer 尺寸 800x600")
    for step in (test_long_stroke, test_cancel, test_erase_undo, test_idle, test_pages,
                 test_clear_undo_redo, test_resize, render_previews):
        try:
            step(h)
        except Exception as exc:  # 自检入口：任何异常都记为失败并继续后面的项
            log(traceback.format_exc())
            check(False, f"{step.__name__} 抛异常 {exc!r}")
    win.hide()
    faulthandler.cancel_dump_traceback_later()
    return finish()


if __name__ == "__main__":
    sys.exit(main())
