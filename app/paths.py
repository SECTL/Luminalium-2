"""路径解析：项目根目录、UI 资源目录、用户数据目录。

默认采用「便携模式」——运行时数据写在项目内的 ``config/`` 与 ``logs/``，
这样应用不依赖系统盘剩余空间，也方便整包拷贝。
可通过环境变量 ``LUMINALIUM_DATA_DIR`` 覆盖数据目录。

打包（PyInstaller 单文件）语义：
    * **只读资源**（``ui/``、``config/default_config.json``、``resources/``、
      RinUI 的 QML 组件）随 exe 解压到 ``sys._MEIPASS``，启动即删不可写；
    * **可写用户数据**（``config/config.json``、``logs/``）落在 exe **同级**
      目录，保证改动跨启动持久化，不散落到系统临时目录。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Luminalium2"
APP_DIR_NAME = "Luminalium 2"

# 只读资源根：开发环境 = 项目根；打包后 = PyInstaller 解压临时目录（sys._MEIPASS）。
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    RESOURCE_ROOT = Path(sys._MEIPASS)
else:
    RESOURCE_ROOT = Path(__file__).resolve().parent.parent

# 可写数据根：便携模式默认与 exe 同级（开发环境 = 项目根），这样单文件打包后
# 用户配置与日志仍能持久化，而不是写进每次启动都换位置的临时解压目录。
def _default_data_root() -> Path:
    if getattr(sys, "frozen", False):
        # exe 所在目录（单文件模式 sys.executable 即 exe 本身）。
        return Path(sys.executable).resolve().parent
    return RESOURCE_ROOT


# 兼容旧名：ROOT_DIR 历史上既是资源根也是数据根，拆分后保留只读语义。
ROOT_DIR = RESOURCE_ROOT

UI_DIR = RESOURCE_ROOT / "ui"
QML_DIR = UI_DIR
ASSETS_DIR = RESOURCE_ROOT / "assets"
# 品牌资源（logo.svg / logo.ico / banner.png）由仓库根目录的 resources/ 承载，
# QML 侧通过 ``Backend.resourceFile("<文件名>")`` 取 file:/// URL。
RESOURCES_DIR = RESOURCE_ROOT / "resources"
# 翻译文件（luminalium_<语言>.ts/.qm）。只读资源，随包分发（见 Luminalium.spec）。
TRANSLATIONS_DIR = RESOURCE_ROOT / "translations"

# 用户数据目录（可写）。默认值在导入时解析一次，保证后续引用一致。
DATA_DIR = _default_data_root()

CONFIG_DIR = DATA_DIR / "config"
LOG_DIR = DATA_DIR / "logs"
# 运行期缓存（可随时删）在数据根下 —— 出问题时用户能直接翻到这个文件夹，
# 而且「只清自己写的、不碰别人的临时文件」这条清理逻辑简单得多。
CACHE_DIR_NAME = "cache"


def cache_dir() -> Path:
    """运行期缓存根目录。**跟随 ``data_dir()`` 的 ``LUMINALIUM_DATA_DIR`` 覆盖**。

    ⚠️ 这里是**函数**而不是模块级常量，与 ``CONFIG_DIR`` / ``LOG_DIR`` 那套不同：
    缩略图缓存是这个应用里**唯一会主动整目录删文件**的地方（换一场放映清一次），
    而 ``LUMINALIUM_DATA_DIR`` 正是给「自检 / 探针别碰用户真实数据」准备的。
    常量写法在导入那一刻就把路径钉死了，覆盖就失效 —— 那样跑一轮自检就会去删
    用户数据目录里的东西。
    """
    return data_dir() / CACHE_DIR_NAME


def slide_thumb_dir() -> Path:
    """放映页缩略图目录（见 ``app/slide_thumbs.py``）。"""
    return cache_dir() / "slide_thumbs"

DEFAULT_CONFIG_FILE = RESOURCE_ROOT / "config" / "default_config.json"
USER_CONFIG_FILE = CONFIG_DIR / "config.json"


def data_dir() -> Path:
    """返回运行时可写数据目录。

    优先级：环境变量 ``LUMINALIUM_DATA_DIR`` > exe 同级目录（打包）/ 项目根（开发）。
    """
    override = os.environ.get("LUMINALIUM_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        path = DATA_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_runtime_dirs() -> None:
    """确保配置文件与日志目录存在。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
