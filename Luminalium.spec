# -*- mode: python ; coding: utf-8 -*-
"""Luminalium 2 的 PyInstaller 打包配置。

``app/paths.py`` 里写明了两套路径语义，这份 spec 要正好对上：

* **只读资源**（``ui/`` / ``config/default_config.json`` / ``resources/`` /
  ``translations/``，以及 RinUI 自己的 QML 组件）解压到 ``sys._MEIPASS``，
  所以它们必须落在包根目录、**保持原来的相对位置**；
* **可写用户数据**（``config/config.json`` / ``logs/``）由 ``app/paths.py``
  自己算到 exe 同级目录，**不进包**。

``ui/`` 之外的三样都靠 ``_MEIPASS/<目录名>`` 定位（见 ``app/paths.py`` 的
``RESOURCE_ROOT``），所以这里用 ``(源, 目标目录)`` 逐个钉死，别指望自动发现。

单文件 / 目录版由环境变量切换
------------------------------

CI 里两种都要出，但 PyInstaller 一次只能产一种，所以用 ``LUMINALIUM_ONEFILE``
切换 ``EXE`` 的形态：

* ``LUMINALIUM_ONEFILE=1`` → 单文件 exe（``EXE`` 直接吃 binaries/datas）；
* 不设 / 其它值 → 目录版（``EXE`` + ``COLLECT``）。

命令行::

    set LUMINALIUM_ONEFILE=1
    python -m PyInstaller --noconfirm --clean Luminalium.spec

exe 的版本资源（属性 → 详细信息）由 ``LUMINALIUM_VERSION_FILE`` 传入，文件由
``.github/scripts/nightly_release.py`` 生成；本地构建不传也能出包，只是没有版本资源。
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

#: ``SPECPATH`` 是 PyInstaller 注入的全局变量 = 本 spec 所在目录 = 仓库根。
ROOT = Path(SPECPATH)

#: ``1/true/yes/on`` → 单文件；其余 → 目录版。
ONEFILE = os.environ.get("LUMINALIUM_ONEFILE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

#: 版本资源文件（可选）。缺失就传 None，PyInstaller 会跳过。
_version_file = os.environ.get("LUMINALIUM_VERSION_FILE", "").strip()
version = _version_file if _version_file and Path(_version_file).is_file() else None

# ------------------------------------------------------------------ 资源

datas = [
    # QML 界面（含 ui/Luminalium 模块目录与 qmldir）
    (str(ROOT / "ui"), "ui"),
    # 翻译（luminalium_<语言>.qm；.ts 源文件一起带上也无妨，体积可忽略）
    (str(ROOT / "translations"), "translations"),
    # 品牌资源（logo.ico / banner.png / 表情图 / WARNING.png …），
    # QML 侧通过 Backend.resourceFile() 取
    (str(ROOT / "resources"), "resources"),
    # 默认配置。⚠️ 只带 default_config.json —— config/config.json 是用户数据，
    # 属于 exe 同级目录，打进包里会被 _MEIPASS 的只读语义坑到。
    (str(ROOT / "config" / "default_config.json"), "config"),
]

# RinUI 的 QML 组件 / 主题 / 图标 / 语言文件。RinUI.core.config 的 RINUI_PATH
# 会解析到 _MEIPASS，Qt 引擎靠它找到 ``RinUI/qmldir``，所以目标目录必须是
# ``RinUI/...``（collect_data_files 默认就是这样）。
datas += collect_data_files("RinUI")

# 正式插件的资产（2026-10-06 计时器插件）：app/plugins/<id>/ 下的数据文件
# PyInstaller 不会自动带，必须显式列。目标路径要和插件运行时的取法对齐 ——
# plugin.py 用 ``Path(__file__).parent / "assets"``，冻结后 __file__ 落在
# ``_MEIPASS/app/plugins/<id>/``，所以第二段保持同样的相对结构。
datas += [
    (str(ROOT / "app" / "plugins" / "timer" / "assets"),
     os.path.join("app", "plugins", "timer", "assets")),
]

# ------------------------------------------------------------------ 隐藏导入

# pywin32 的 COM 子模块是**运行时按名字**加载的（PPT 控制器走 win32com），
# 静态分析看不到，必须显式列出来，否则打包后放映控制整块失效。
hiddenimports = [
    "pythoncom",
    "pywintypes",
    "win32api",
    "win32con",
    "win32gui",
    "win32process",
    "win32event",
    "win32com",
    "win32com.client",
    "win32com.shell",
    "win32com.shell.shellcon",
    # 正式插件是 loader 用 importlib 按 ``app.plugins.<id>.plugin`` **动态**
    # 导入的（app/plugins/__init__.py 的 PLUGINS 表只是 id 字符串），静态分析
    # 看不到这层引用 —— 不列出来打包后所有正式插件都会「导入失败」跳过。
    # 新增正式插件时这里要同步加一行。
    "app.plugins.timer.plugin",
    "app.plugins.blackboard.plugin",
    "app.plugins.spotlight.plugin",
    # 自建墨迹包（2026-10-07）：application.py / 工具脚本都是在函数体里
    # 延迟导入（``from .ink import register_qml_types``），PyInstaller 的静态
    # 分析可能扫不到这层引用；漏带的话打包后 QML 里 ``import Luminalium.Ink``
    # 直接报模块未安装、整个批注层加载失败，所以显式列出。
    "app.ink",
    "app.ink.layer",
    "app.ink.model",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # tkinter 与本应用无关（PySide6 应用常见误带），排掉能省一截体积。
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

#: 两种形态共用的 EXE 参数。
_exe_kwargs = dict(
    name="Luminalium2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 应用：不弹控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "resources" / "logo.ico"),
    version=version,
)

if ONEFILE:
    # 单文件：binaries / datas 全部塞进 exe，运行时解压到 _MEIPASS。
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        **_exe_kwargs,
    )
else:
    # 目录版：exe 只带脚本，依赖摊在 dist/Luminalium2/ 里，启动更快。
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **_exe_kwargs,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="Luminalium2",
    )
