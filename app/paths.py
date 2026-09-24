"""路径解析：项目根目录、UI 资源目录、用户数据目录。

默认采用「便携模式」——运行时数据写在项目内的 ``config/`` 与 ``logs/``，
这样应用不依赖系统盘剩余空间，也方便整包拷贝。
可通过环境变量 ``LUMINALIUM_DATA_DIR`` 覆盖数据目录。
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Luminalium2"
APP_DIR_NAME = "Luminalium 2"

# app/paths.py -> app/ -> <root>
ROOT_DIR = Path(__file__).resolve().parent.parent

UI_DIR = ROOT_DIR / "ui"
QML_DIR = UI_DIR
ASSETS_DIR = ROOT_DIR / "assets"
# 品牌资源（logo.svg / logo.ico / banner.png）由仓库根目录的 resources/ 承载，
# QML 侧通过 ``Backend.resourceFile("<文件名>")`` 取 file:/// URL。
RESOURCES_DIR = ROOT_DIR / "resources"
CONFIG_DIR = ROOT_DIR / "config"
LOG_DIR = ROOT_DIR / "logs"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "default_config.json"
USER_CONFIG_FILE = CONFIG_DIR / "config.json"


def data_dir() -> Path:
    """返回运行时可写数据目录。"""
    override = os.environ.get("LUMINALIUM_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        path = ROOT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_runtime_dirs() -> None:
    """确保配置文件与日志目录存在。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
