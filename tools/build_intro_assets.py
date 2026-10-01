# -*- coding: utf-8 -*-
"""生成设置页「主界面」推广卡（「编辑主界面的新方式」）的两张配图。

用法::

    .venv\\Scripts\\python.exe tools\\build_intro_assets.py

**背景（2026-10-01）**：``resources/new_editor_maininterface_{light,dark}.png``
原本是两张**透明底**示意图，元素色是按"叠在相反色的底上"设计的 ——

    light 元素是**浅色**（面板 #DBDBDE 71%、右上块 #F6F6F7 不透明）
    dark  元素是**深色**（面板 #212124 71%、右上块 #4C4C4C 不透明）

透明底直接贴到卡片上，元素与卡片同色 → **整块看不见**（实机预览确认过）。
本脚本给它们补上底色，并交换文件名 —— 文件名即"适用于哪个主题"：

    dark.png  ← 深色卡片底 #2B2B2B + 浅色元素
    light.png ← 浅色卡片底 #FBFBFB + 深色元素

底色是 RinUI 里 ``cardColor`` 压平后的实测值（dark: 白 5.12% 叠在 #202020 上；
light: 白 70% 叠在 #F3F3F3 上）—— 与卡片同色，图贴在卡上就"没有边"。

⚠️ **输入是 `preview/_intro_src_new_editor_maininterface_*.png`（原始透明底那份）**，
不是 `resources/` 里的成品 —— 成品已有底色，再跑一次会把底再压一层、并又交换
一次文件名（图就毁了）。所以：

* 原始素材丢了 → 本脚本直接报错退出，**不会**去动 ``resources/``；
* 换新素材 → 把新的透明底图另存成那两个 ``_intro_src_*`` 名字，再跑一次。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "resources"
SRC = ROOT / "preview"

#: 目标文件名 → (底色, 原始素材文件名)。内容互换，见模块 docstring。
JOBS = [
    ("new_editor_maininterface_dark.png", (0x2B, 0x2B, 0x2B),
     "new_editor_maininterface_light"),
    ("new_editor_maininterface_light.png", (0xFB, 0xFB, 0xFB),
     "new_editor_maininterface_dark"),
]
SRC_PREFIX = "_intro_src_"


def main() -> int:
    missing = [
        SRC / f"{SRC_PREFIX}{source}.png"
        for _, _, source in JOBS
        if not (SRC / f"{SRC_PREFIX}{source}.png").exists()
    ]
    if missing:
        print("[FAIL] 缺少原始素材（透明底那份），无法生成：")
        for path in missing:
            print(f"        {path}")
        print("       把新的透明底图按这个文件名放进去再跑。")
        return 1

    # 两张图互为源与目标（内容要互换），所以先全部读进内存再写盘
    images = {}
    for target, bg, source in JOBS:
        image = Image.open(SRC / f"{SRC_PREFIX}{source}.png").convert("RGBA")
        images[target] = (bg, image)

    for target, (bg, image) in images.items():
        base = Image.new("RGBA", image.size, bg + (255,))
        out = Image.alpha_composite(base, image).convert("RGB")
        out.save(RES / target)
        print(f"[OK] {target} 底色 #{bg[0]:02X}{bg[1]:02X}{bg[2]:02X} "
              f"{out.size[0]}x{out.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
