"""开发用：把「Figma 导出的设计稿 PNG」和「本项目的离屏渲染图」逐像素比一遍。

还原设计稿这类活儿光靠眼睛看不可靠 —— 眼睛会把「放大倍率不同」误判成「版式不对」。
这个脚本做三件**客观**的事：

1. **叠放图**：灰度打底，设计稿独有的像素染红、渲染图独有的染青。
   整片纯灰 = 一致；出现红/青边 = 那里错位了。
2. **逐项几何**：在设计空间（2984×1679 网格）里量出 logo / 标题 / 进度条 / 插画卡
   等特征的外接框，和设计稿做差。数值可以直接搬回 QML。
3. **放大对照**：把可疑区域从**两边**裁出来上下拼一张 —— 关键是两边都先归一到同一
   工作分辨率再裁，否则 3× 导出那侧天然清晰，会把「放大倍率差异」看成「渲染发糊」。

用法::

    .venv\\Scripts\\python.exe tools\\design_diff.py            # 深色
    .venv\\Scripts\\python.exe tools\\design_diff.py light      # 浅色
    .venv\\Scripts\\python.exe tools\\design_diff.py light --no-zoom

产出（都在 gitignore 掉的 ``preview/`` 下，不会进仓库）::

    diff_side_<variant>.png     设计稿在上 / 渲染在下
    diff_overlay_<variant>.png  红=设计稿独有  青=渲染独有
    zoom_<feature>_<variant>.png 逐区域放大对照

渲染图从哪来：先跑 ``tools/preview.py`` 出 ``preview/splash.png``；
浅色版先跑 ``LUMI_PREVIEW_THEME=light tools/preview.py`` 出 ``splash_light.png``。

⚠️ **适用范围**（2026-10-01 起）：启动画面已经不是设计稿的 1:1 还原了 —— 版式照
设计稿走，但圆角 / 描边 / 字阶 / 配色 / 阴影改用了 Fluent 2 令牌。所以：

* **逐项几何**仍然有效，且是主要用途：卡面内 logo / 标题 / 插画卡的位置必须与
  设计稿对齐（容差一两个设计单位）。
* **平均差异与叠放图要带着脑子看**：卡面底色（浅色 #FFFFFF → Fluent #F3F3F3）、
  圆角（92 → 8）、底部字号（折算 9.4 → Fluent caption 12）这些是**刻意**的差异，
  会稳定地刷出红/青边，不代表版式跑偏。
* 窗口比卡面四周各大一圈（给阴影留位），所以渲染图会先**裁出卡面**再归一到设计空间。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
DESIGN_DIR = Path(r"I:/AA.USERDATAFILE/Downloads")

#: 设计稿画布 = 唯一的坐标系。所有测量值都以它为单位。
DESIGN_W, DESIGN_H = 2984, 1679
#: 比较用的工作分辨率。取设计空间的一半：够细，又不至于跑几十秒。
WORK_W, WORK_H = DESIGN_W // 2, DESIGN_H // 2

#: 卡面在窗口里的位置 —— 必须与 ``ui/Luminalium/Lumi.qml`` 的
#: ``splashCardWidth`` / ``splashShadowMargin`` 对齐（窗口 = 卡面 + 四周阴影边距）。
CARD_W = 720.0
CARD_H = round(CARD_W * DESIGN_H / DESIGN_W)
SHADOW_MARGIN = 32

#: variant -> (设计稿 PNG, 渲染图 PNG)
VARIANTS = {
    "dark": (DESIGN_DIR / "启动画面 Dark.png", ROOT / "preview" / "splash.png"),
    "light": (DESIGN_DIR / "启动画面 Light.png", ROOT / "preview" / "splash_light.png"),
}

#: 放大对照的区域：(x0, y0, x1, y1, 放大倍数)，用**设计空间**坐标。
ZOOM_REGIONS = {
    "logo": (105, 95, 345, 335, 3),
    "wordmark": (130, 1150, 920, 1310, 2),
    "subtitle": (120, 1315, 800, 1415, 3),
    "progress": (120, 1435, 1340, 1500, 3),
    "labels": (120, 1505, 1340, 1580, 3),
    "artcorner": (1390, 80, 1700, 420, 3),
    "artbottom": (1390, 1380, 1760, 1600, 3),
    "cardedge": (0, 700, 60, 1000, 4),
}


# ============================================================ 像素工具

def load(path: Path) -> Image.Image:
    """读设计稿并归一到设计空间网格。"""
    im = Image.open(path).convert("RGBA")
    if im.size != (DESIGN_W, DESIGN_H):
        im = im.resize((DESIGN_W, DESIGN_H), Image.LANCZOS)
    return im


def load_render(path: Path) -> Image.Image:
    """读渲染图：先**裁出卡面**（窗口四周有阴影边距）再归一到设计空间网格。

    不裁的话，那一圈透明边距会把整个卡片挤小，所有几何项一起偏。
    """
    im = Image.open(path).convert("RGBA")
    win_w = CARD_W + 2 * SHADOW_MARGIN
    win_h = CARD_H + 2 * SHADOW_MARGIN
    sx, sy = im.width / win_w, im.height / win_h
    box = (round(SHADOW_MARGIN * sx), round(SHADOW_MARGIN * sy),
           round((SHADOW_MARGIN + CARD_W) * sx), round((SHADOW_MARGIN + CARD_H) * sy))
    return im.crop(box).resize((DESIGN_W, DESIGN_H), Image.LANCZOS)


def lum(c) -> float:
    return (c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000


def opaque(im: Image.Image, bg=(128, 128, 128)) -> Image.Image:
    """把 RGBA 压到不透明底上 —— 不然透明角的 alpha 差会把真实差异淹掉。"""
    canvas = Image.new("RGBA", im.size, bg + (255,))
    return Image.alpha_composite(canvas, im.convert("RGBA")).convert("RGB")


def ink_bbox(im: Image.Image, box, pred):
    """在 box（设计空间）内找满足 pred 的像素外接框，返回 (x, y, w, h)。"""
    x0, y0, x1, y1 = (int(v) for v in box)
    px = im.load()
    mx = my = 10 ** 9
    Mx = My = -10 ** 9
    for y in range(max(0, y0), min(y1, DESIGN_H)):
        for x in range(max(0, x0), min(x1, DESIGN_W)):
            if pred(px[x, y]):
                mx = min(mx, x)
                Mx = max(Mx, x)
                my = min(my, y)
                My = max(My, y)
    return None if Mx < mx else (float(mx), float(my), float(Mx - mx + 1), float(My - my + 1))


# ============================================================ 特征表
# 每个特征是「量什么」+「怎么判定是墨迹」。键名会出现在输出里，自己看得懂就行。
# ⚠️ 判定阈值别卡太紧：抗锯齿的斜坡会被算成墨迹，把外接框撑大 1~3 单位。
#    看到「Δh 突然多出好几单位但肉眼没差」多半就是这个，先用亮度剖面确认再改代码。

def _card_bg(im):
    """卡片底色取样点（左上角内侧，任何设计都不会在那儿放东西）。"""
    return lum(im.getpixel((20, 800)))


def _f_logo(im):
    return ink_bbox(im, (100, 90, 350, 340),
                    lambda c: c[2] > 120 and c[2] - c[0] > 25 and c[3] > 128)


def _f_wordmark(im):
    ref = _card_bg(im)
    return ink_bbox(im, (120, 1150, 950, 1315),
                    lambda c: abs(lum(c) - ref) > 60 and c[3] > 128)


def _f_subtitle(im):
    ref = _card_bg(im)
    return ink_bbox(im, (120, 1320, 900, 1412),
                    lambda c: abs(lum(c) - ref) > 22 and c[3] > 128)


#: 进度条阈值（2026-10-01 调过）：设计稿的槽是「白 28%」、填充是「纯白」，
#: 换走 Fluent 令牌后槽变成 ``DividerStrokeColorDefault``（白 8%）、填充变成
#: 强调色 —— 沿用旧阈值（40 / 150）会把槽整个漏掉、只剩填充，于是宽度量出来
#: 少掉 40%（看着像版式错，其实是配色变了）。
def _f_track(im):
    ref = _card_bg(im)
    return ink_bbox(im, (120, 1450, 1340, 1492),
                    lambda c: abs(lum(c) - ref) > 14 and c[3] > 128)


def _f_fill(im):
    ref = _card_bg(im)
    return ink_bbox(im, (120, 1450, 1340, 1492),
                    lambda c: abs(lum(c) - ref) > 90 and c[3] > 128)


def _f_label_left(im):
    ref = _card_bg(im)
    return ink_bbox(im, (120, 1515, 700, 1575),
                    lambda c: abs(lum(c) - ref) > 60 and c[3] > 128)


def _f_label_right(im):
    ref = _card_bg(im)
    return ink_bbox(im, (900, 1515, 1340, 1575),
                    lambda c: abs(lum(c) - ref) > 60 and c[3] > 128)


def _f_card(im):
    ref = _card_bg(im)
    return ink_bbox(im, (1400, 100, 2920, 1580),
                    lambda c: abs(lum(c) - ref) > 30 and c[3] > 128)


#: (显示名, 测量函数, 是否计入版式判定)。
#: 只有**形体**项（卡片 / logo / 标题轮廓 / 进度条轨道 / 插画卡）参与判定。
#: 文字项一律不计入：这一版的正文字号和字体都改走 Fluent 字阶了，墨迹框本来就
#: 和设计稿不一样大（而且版本号、百分比是动态的），拿来当「版式跑偏」是误报。
FEATURES = [
    ("logo", _f_logo, True),
    ("wordmark", _f_wordmark, True),
    ("subtitle", _f_subtitle, False),
    ("progress track", _f_track, True),
    ("progress fill", _f_fill, False),
    ("label left", _f_label_left, False),
    ("label right", _f_label_right, False),
    ("art card", _f_card, True),
]


# ============================================================ 三张图

def write_side(design: Image.Image, render: Image.Image, out: Path) -> None:
    d = opaque(design.resize((WORK_W, WORK_H), Image.LANCZOS))
    r = opaque(render.resize((WORK_W, WORK_H), Image.LANCZOS))
    canvas = Image.new("RGB", (WORK_W, WORK_H * 2 + 8), (24, 24, 24))
    canvas.paste(d, (0, 0))
    canvas.paste(r, (0, WORK_H + 8))
    canvas.save(out)


def write_overlay(design: Image.Image, render: Image.Image, out: Path) -> tuple[Image.Image, float]:
    d = opaque(design.resize((WORK_W, WORK_H), Image.LANCZOS))
    r = opaque(render.resize((WORK_W, WORK_H), Image.LANCZOS))
    diff = ImageChops.difference(d, r).convert("L")
    avg = sum(diff.histogram()[i] * i for i in range(256)) / (WORK_W * WORK_H)

    overlay = d.convert("L").convert("RGB").point(lambda v: 40 + v * 3 // 4)
    od, dd, rd = overlay.load(), d.load(), r.load()
    for y in range(WORK_H):
        for x in range(WORK_W):
            a, b = dd[x, y], rd[x, y]
            if max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) < 22:
                continue
            # 谁更亮谁「多画了东西」：设计稿更亮染红，渲染更亮染青
            la = a[0] * 299 + a[1] * 587 + a[2] * 114
            lb = b[0] * 299 + b[1] * 587 + b[2] * 114
            od[x, y] = (255, 60, 60) if la > lb else (60, 255, 255)
    overlay.save(out)
    return diff, avg


def report_bands(diff: Image.Image) -> None:
    major = diff.point(lambda v: 255 if v > 26 else 0)
    rows = [major.crop((0, y, WORK_W, y + 1)).histogram()[255] for y in range(WORK_H)]
    cols = [major.crop((x, 0, x + 1, WORK_H)).histogram()[255] for x in range(WORK_W)]

    def bands(series, span, label):
        out, run, start = [], 0, 0
        for i, v in enumerate(series):
            if v > span * 0.04:          # 该行/列有 >4% 的像素明显不同 → 算「有差异」
                if run == 0:
                    start = i
                run += 1
            else:
                if run >= 3:
                    out.append(f"    {label} [{start * 2}, {(i - 1) * 2}]  峰值 {max(series[start:i])}")
                run = 0
        if run >= 3:
            out.append(f"    {label} [{start * 2}, {(len(series) - 1) * 2}]  峰值 {max(series[start:])}")
        return out or ["    （无）"]

    print("  行方向有明显差异的带（设计空间坐标）：")
    print("\n".join(bands(rows, WORK_W, "y")))
    print("  列方向有明显差异的带：")
    print("\n".join(bands(cols, WORK_H, "x")))


def report_geometry(design: Image.Image, render: Image.Image) -> float:
    print(f"{'feature':16s} {'x':>8s} {'y':>8s} {'w':>8s} {'h':>8s}"
          f"   {'Δx':>6s} {'Δy':>6s} {'Δw':>6s} {'Δh':>6s}")
    print("-" * 78)
    worst = 0.0
    for name, fn, layout_item in FEATURES:
        a, b = fn(design), fn(render)
        if a is None or b is None:
            print(f"{name:16s}  测量失败 design={a} render={b}")
            continue
        d = [b[i] - a[i] for i in range(4)]
        # 文字项的墨迹框受字体/字号影响，只有形体项才算「版式」。
        if layout_item:
            worst = max(worst, max(abs(v) for v in d))
        note = "" if layout_item else "   ← 文字/动态项，差值不计入版式判定"
        print(f"{name:16s} {a[0]:8.1f} {a[1]:8.1f} {a[2]:8.1f} {a[3]:8.1f}"
              f"  {d[0]:+6.1f} {d[1]:+6.1f} {d[2]:+6.1f} {d[3]:+6.1f}{note}")
    print("-" * 78)
    print(f"最大绝对偏差 {worst:.1f} 设计单位（只算版式项）"
          f"  =  {worst / DESIGN_W * CARD_W:.2f} 逻辑像素 @ 卡面 {CARD_W:.0f} 宽")
    return worst


def write_zooms(design: Image.Image, render: Image.Image, variant: str) -> None:
    s = WORK_W / DESIGN_W
    d = design.resize((WORK_W, WORK_H), Image.LANCZOS)
    r = render.resize((WORK_W, WORK_H), Image.LANCZOS)
    for name, (x0, y0, x1, y1, z) in ZOOM_REGIONS.items():
        box = (int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s))
        a = d.crop(box)
        b = r.crop(box)
        size = (max(1, a.width * z), max(1, a.height * z))
        a = a.resize(size, Image.LANCZOS)
        b = b.resize(size, Image.LANCZOS)
        bg = Image.new("RGBA", (size[0], size[1] * 2 + 4), (128, 128, 128, 255))
        bg.alpha_composite(a, (0, 0))
        bg.alpha_composite(b, (0, size[1] + 4))
        bg.convert("RGB").save(ROOT / "preview" / f"zoom_{name}_{variant}.png")
    print(f"  放大对照 {len(ZOOM_REGIONS)} 张（preview/zoom_*_{variant}.png；上=设计稿 下=渲染）")


# ============================================================ 入口

def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    variant = args[0].lower() if args else "dark"
    if variant not in VARIANTS:
        print(f"未知 variant {variant!r}，可选：{', '.join(VARIANTS)}")
        return 2
    design_path, render_path = VARIANTS[variant]
    if not render_path.exists():
        print(f"找不到渲染图 {render_path}\n"
              f"先跑 tools/preview.py"
              f"{'（前置 LUMI_PREVIEW_THEME=light）' if variant == 'light' else ''}")
        return 2

    design, render = load(design_path), load_render(render_path)
    out = ROOT / "preview"

    print(f"=========== design diff ({variant}) ===========")
    print(f"设计稿 {design_path.name}  →  {render_path.relative_to(ROOT)}")
    print(f"工作分辨率 {WORK_W}x{WORK_H}（设计空间 / 2），差值单位 = 设计空间\n")

    write_side(design, render, out / f"diff_side_{variant}.png")
    diff, avg = write_overlay(design, render, out / f"diff_overlay_{variant}.png")
    print(f"平均差异 {avg:.2f} / 255     （< 2 就算还原得很稳；侧栏文字占大头）\n")

    report_bands(diff)
    print()
    report_geometry(design, render)
    if "--no-zoom" not in sys.argv:
        print()
        write_zooms(design, render, variant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
