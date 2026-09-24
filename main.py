"""Luminalium 2 启动脚本。

用法::

    .venv\\Scripts\\python.exe main.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 保证以任意工作目录启动时都能 import app 包
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# RinUI 会把主题配置写到 <cwd>/RinUI/config/rin_ui.json，固定工作目录避免散落
os.chdir(ROOT)

from app.application import main  # noqa: E402  (需在 sys.path 调整之后导入)

if __name__ == "__main__":
    raise SystemExit(main())
