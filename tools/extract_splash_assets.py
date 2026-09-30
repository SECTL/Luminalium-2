"""把 Figma 导出的「启动画面」SVG 拆成运行时要用的素材（可重跑）。

产物（都在 ``resources/splash/``，这些是**生成物**，改设计稿就重跑本脚本）::

    art.png             插画位图（1717×1640，设计稿原始像素，不裁 —— 圆角裁切交给 QML）
    logo.svg            品牌标记（184×184，配色取设计稿，不是仓库根目录那份旧配色）
    wordmark_dark.svg   标题「Luminalium」的矢量轮廓，白色（深色主题用）
    wordmark_light.svg  同上，黑色（浅色主题用）

**为什么标题搬轮廓而不是用字体重排**：设计稿用的是一款带尾钩 ``l``/``i`` 的无衬线体，
本机与常见免费字体里都没有匹配款（逐字母墨迹宽度指纹差 > 8%）。用轮廓能保证 100% 一致。
版本行是动态文本没法这么做，退而求其次用 Candara。

**为什么不用现成的 SVG 库**：导出的 SVG 里正文已全部转成 ``<path>`` 轮廓，读不出字号；
而挑 path 得靠包围盒，所以这里自带一个完整的 path 解析器（曲线采样 16 段，
二次曲线升阶成三次），按真实几何求包围盒。

用法::

    .venv\\Scripts\\python.exe tools\\extract_splash_assets.py "I:/…/启动画面 Dark.svg"
"""

from __future__ import annotations

import base64
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "resources" / "splash"

# 设计稿画布（所有坐标的设计空间）
CANVAS = (2984.0, 1679.0)

# 各元素的包围盒 —— 与 SVG 里读到的数值一致。设计稿改了要同步这里。
BOX_LOGO = (131.0, 121.0, 184.0, 184.0)
BOX_TITLE = (147.3, 1176.5, 727.7, 113.7)

TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


# ============================================================ SVG path 包围盒

def _cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
    )


def path_bbox(d: str) -> tuple[float, float, float, float] | None:
    """按真实几何求 (x0, y0, x1, y1)。曲线采样 16 段，二次曲线升阶成三次。"""
    toks: list[object] = []
    for m in TOKEN.finditer(d):
        toks.append(m.group(1) if m.group(1) else float(m.group(2)))

    xs: list[float] = []
    ys: list[float] = []

    def add(p):
        xs.append(p[0])
        ys.append(p[1])

    i = 0
    cmd = ""
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_ctrl = None
    while i < len(toks):
        t = toks[i]
        if isinstance(t, str):
            cmd = t
            i += 1
        rel = cmd.islower()
        c = cmd.upper()

        def take(n=2):
            nonlocal i
            vals = toks[i : i + n]
            i += n
            return [float(v) for v in vals]

        if c in "ML":
            pts = []
            while i < len(toks) and not isinstance(toks[i], str):
                pts += take(2)
            for k in range(0, len(pts), 2):
                p = (pts[k], pts[k + 1])
                if rel:
                    p = (cur[0] + p[0], cur[1] + p[1])
                cur = p
                add(p)
                if c == "M" and k == 0:
                    start = p
            if c == "M":
                cmd = "l" if rel else "L"
            prev_ctrl = None
        elif c in "HV":
            while i < len(toks) and not isinstance(toks[i], str):
                v = take(1)[0]
                if c == "H":
                    cur = (cur[0] + v if rel else v, cur[1])
                else:
                    cur = (cur[0], cur[1] + v if rel else v)
                add(cur)
            prev_ctrl = None
        elif c in "CS":
            pts = []
            while i < len(toks) and not isinstance(toks[i], str):
                pts += take(6)
            for k in range(0, len(pts), 6):
                c1 = (pts[k], pts[k + 1])
                c2 = (pts[k + 2], pts[k + 3])
                end = (pts[k + 4], pts[k + 5])
                if c == "S":
                    c1 = ((2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
                          if prev_ctrl else cur)
                if rel:
                    c1 = (cur[0] + c1[0], cur[1] + c1[1])
                    c2 = (cur[0] + c2[0], cur[1] + c2[1])
                    end = (cur[0] + end[0], cur[1] + end[1])
                for s in range(17):
                    add(_cubic(cur, c1, c2, end, s / 16))
                prev_ctrl = c2
                cur = end
        elif c in "QT":
            pts = []
            while i < len(toks) and not isinstance(toks[i], str):
                pts += take(4)
            for k in range(0, len(pts), 4):
                q = (pts[k], pts[k + 1])
                end = (pts[k + 2], pts[k + 3])
                if c == "T":
                    q = ((2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
                         if prev_ctrl else cur)
                if rel:
                    q = (cur[0] + q[0], cur[1] + q[1])
                    end = (cur[0] + end[0], cur[1] + end[1])
                c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
                c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
                for s in range(17):
                    add(_cubic(cur, c1, c2, end, s / 16))
                prev_ctrl = q
                cur = end
        elif c == "A":
            pts = []
            while i < len(toks) and not isinstance(toks[i], str):
                pts += take(7)
            for k in range(0, len(pts), 7):
                end = (pts[k + 5], pts[k + 6])
                if rel:
                    end = (cur[0] + end[0], cur[1] + end[1])
                add(end)
                cur = end
            prev_ctrl = None
        elif c == "Z":
            cur = start
            add(cur)
            prev_ctrl = None
        else:
            i += 1

    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


# ============================================================ 从 SVG 里挑元素

def paths_of(svg_text: str) -> list[tuple[str, dict[str, str]]]:
    found: list[tuple[str, dict[str, str]]] = []
    for m in re.finditer(r"<path\b([^>]*?)/>", svg_text, re.S):
        attrs = dict(re.findall(r'([\w:.-]+)\s*=\s*"([^"]*)"', m.group(1)))
        if "d" in attrs:
            found.append((attrs["d"], attrs))
    return found


def pick(paths, want_bbox, tol=2.0):
    """按包围盒（x0, y0, x1, y1）认领一条 path。"""
    for d, attrs in paths:
        b = path_bbox(d)
        if b and all(abs(b[i] - want_bbox[i]) <= tol for i in range(4)):
            return d, attrs
    return None, None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = pathlib.Path(sys.argv[1])
    text = src.read_text(encoding="utf-8")

    # ---- 插画位图 ----
    img = re.search(r'xlink:href="data:image/png;base64,([A-Za-z0-9+/=]+)"', text)
    assert img, "SVG 里没有内嵌位图"
    OUT.mkdir(parents=True, exist_ok=True)
    art = OUT / "art.png"
    art.write_bytes(base64.b64decode(img.group(1)))
    print(f"{'art.png':<18} {art.stat().st_size:>8} bytes")

    # 抹掉 base64，后面按 path 找就不会被它干扰
    text = re.sub(r'xlink:href="data:image/png;base64,[^"]*"', 'xlink:href=""', text)
    paths = paths_of(text)

    # ---- 标题轮廓 ----
    tx, ty, tw, th = BOX_TITLE
    title_d, _ = pick(paths, (tx, ty, tx + tw, ty + th))
    assert title_d, "没找到标题轮廓"
    for name, fill in (("wordmark_dark.svg", "#FFFFFF"), ("wordmark_light.svg", "#000000")):
        svg = (
            f'<svg width="{tw:g}" height="{th:g}" viewBox="{tx:g} {ty:g} {tw:g} {th:g}" '
            f'fill="none" xmlns="http://www.w3.org/2000/svg">\n'
            f'<path d="{title_d}" fill="{fill}"/>\n</svg>\n'
        )
        p = OUT / name
        p.write_text(svg, encoding="utf-8")
        print(f"{name:<18} {p.stat().st_size:>8} bytes")

    # ---- 品牌标记（按设计稿配色重写一份，别动仓库根目录那份旧 logo.svg）----
    d_circle, _ = pick(paths, (131.0, 121.0, 315.0, 305.0))
    d_ring, _ = pick(paths, (141.1, 131.1, 304.9, 294.9))
    star = [d for d, _a in paths
            if (b := path_bbox(d)) and abs(b[0] - 152.5) < 2 and abs(b[1] - 142.7) < 2]
    assert d_circle and d_ring and len(star) == 2, "标记元素不全"
    # 星形在 SVG 里出现两次：一条是填充（短），一条是描边轮廓（长，evenodd）
    d_star_fill, d_star_edge = sorted(star, key=len)

    grad = re.search(r'<linearGradient id="paint1[^"]*"[^>]*>(.*?)</linearGradient>', text, re.S)
    stops = re.findall(r'stop-color="([^"]*)"', grad.group(1)) if grad else ["#4781CE", "#658ED5"]
    gx1, gy1, gx2, gy2 = (re.findall(r'(?:x1|y1|x2|y2)="([-\d.]+)"', grad.group(0))
                          if grad else ["125.244", "103.146", "318.902", "299.439"])

    x, y, w, h = BOX_LOGO
    svg = (
        f'<svg width="{w:g}" height="{h:g}" viewBox="{x:g} {y:g} {w:g} {h:g}" '
        f'fill="none" xmlns="http://www.w3.org/2000/svg">\n'
        f'<defs><linearGradient id="g" x1="{gx1}" y1="{gy1}" x2="{gx2}" y2="{gy2}" '
        f'gradientUnits="userSpaceOnUse">'
        f'<stop stop-color="{stops[0]}"/><stop offset="1" stop-color="{stops[1]}"/>'
        f"</linearGradient></defs>\n"
        f'<path d="{d_circle}" fill="url(#g)"/>\n'
        f'<path d="{d_ring}" fill="white" fill-opacity="0.32"/>\n'
        f'<path d="{d_star_fill}" fill="white" fill-opacity="0.15"/>\n'
        f'<path fill-rule="evenodd" clip-rule="evenodd" d="{d_star_edge}" '
        f'fill="white" fill-opacity="0.51"/>\n</svg>\n'
    )
    p = OUT / "logo.svg"
    p.write_text(svg, encoding="utf-8")
    print(f"{'logo.svg':<18} {p.stat().st_size:>8} bytes")

    print(f"\n设计空间 {CANVAS[0]:g}×{CANVAS[1]:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
