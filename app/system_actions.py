"""系统层小动作：往桌面 / 开始菜单扔一个 ``.lnk``。

2026-11-21 用户指令：设置标题栏版本号右侧加「更多」按钮，菜单里有
「创建桌面快捷方式 / 创建开始菜单快捷方式」。这里只做**这一件事** ——
「打开日志目录 / 打开应用目录」由 bridge 用 ``QDesktopServices`` 直接开，
不值得为此多一层。

为什么单开文件而不是在 bridge 里写两行：

* 目标路径分**源码运行**与**打包运行**两支。源码运行要指向
  ``pythonw.exe + main.py``，写错成 ``python.exe`` 就在用户桌面上留一个
  黑框控制台快捷方式（本机实测：双击后先弹黑窗再出面板）；
* 快捷方式的名字要跟 ``app.name`` 走，不能写死 —— 用户改过应用名之后，
  桌面上那枚图标得叫同一个名字，否则看起来像两个程序。

COM 走 pywin32（``WScript.Shell`` 的 ``CreateShortCut``）——
``.lnk`` 是二进制壳链接，手写字节格式没有任何好处；pywin32 本来就在
``requirements.txt`` 里（PPT 控件也用），且 ``Luminalium.spec`` 的
``hiddenimports`` 已带 ``win32com.client``，打包版不会缺。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from . import i18n
from .paths import RESOURCE_ROOT, RESOURCES_DIR

log = logging.getLogger(__name__)

#: 目标快捷方式的名字（``.lnk`` 后缀由 Windows 自己补，路径里带上更保险）。
_LINK_SUFFIX = ".lnk"

#: 菜单项传进来的两种目标。
DESKTOP = "desktop"
START_MENU = "start_menu"
_TARGETS = (DESKTOP, START_MENU)


def _launch_target() -> tuple[Path, str, Path]:
    """返回 ``(可执行文件, 参数字符串, 工作目录)``。

    打包版：直接跑 exe 自身，参数为空；
    源码版：优先 ``pythonw.exe``（无控制台）跑仓库根的 ``main.py``。

    ⚠️ 参数里含空格时必须自带双引号 —— ``WScript.Shell.Shortcut.Arguments``
    是**原样拼接**到命令行上的，不会替我们转义。项目根在本机就是
    ``G:\\Dev\\Luminalium-2``（无空格），但别人的克隆路径不保证。
    """
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return exe, "", exe.parent

    interpreter = Path(sys.executable).resolve()
    windowed = interpreter.with_name("pythonw.exe")
    if windowed.is_file():
        interpreter = windowed
    script = RESOURCE_ROOT / "main.py"
    return interpreter, f'"{script}"', script.parent


def _target_dir(kind: str) -> Path:
    """桌面 / 开始菜单（当前用户）目录。

    ⚠️ 用环境变量而不是 ``WScript.Shell.SpecialFolders``：后者要 COM 已初始化，
    而这里在拿目录之前不该先付 COM 的代价；``APPDATA`` / ``USERPROFILE`` 在
    正常桌面会话里恒定存在，取不到就按失败处理（比悄悄落到别处强）。
    """
    if kind == DESKTOP:
        home = Path.home()
        # OneDrive 重定向过的桌面上 ``Path.home()/"Desktop"`` 可能不存在，
        # 但那是用户自己的映射，落在这儿仍然是「桌面上看得见」的位置吗？
        # 不是 —— 所以优先认 ``OneDrive`` 同名目录。
        candidates = [home / "OneDrive" / "Desktop", home / "Desktop"]
    else:
        appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        candidates = [appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"]

    for path in candidates:
        if path.is_dir():
            return path
    raise FileNotFoundError(str(candidates[0]))


def create_shortcut(kind: str, display_name: str) -> tuple[bool, str]:
    """创建（或覆盖）一枚快捷方式，返回 ``(成功?, 给人看的消息)``。

    已存在同名 ``.lnk`` 时直接覆盖：用户连点两次菜单不该得到两枚一样的图标，
    而「目标换了（比如从源码版换成打包版）」时覆盖才是对的语义。
    """
    if kind not in _TARGETS:
        return False, i18n.tr("MoreMenu", "未知的快捷方式类型")

    try:
        folder = _target_dir(kind)
    except FileNotFoundError as exc:
        log.warning("快捷方式目标目录不存在: %s", exc)
        return False, i18n.tr("MoreMenu", "找不到目标文件夹")

    link_path = folder / f"{display_name}{_LINK_SUFFIX}"
    exe, args, workdir = _launch_target()
    icon = RESOURCES_DIR / "logo.ico"

    try:
        import pythoncom
        import win32com.client

        # 主线程可能已被 Qt 初始化过 COM（S_FALSE），成对 Uninitialize 即可。
        pythoncom.CoInitialize()
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(link_path))
            shortcut.TargetPath = str(exe)
            if args:
                shortcut.Arguments = args
            shortcut.WorkingDirectory = str(workdir)
            shortcut.Description = display_name
            if icon.is_file():
                shortcut.IconLocation = f"{icon},0"
            shortcut.Save()
        finally:
            pythoncom.CoUninitialize()
    except Exception:  # noqa: BLE001 - COM 的异常族很杂，统一按失败上报
        log.exception("创建快捷方式失败: %s -> %s", kind, link_path)
        return False, i18n.tr("MoreMenu", "创建快捷方式失败，详情见日志")

    log.info("已创建快捷方式: %s", link_path)
    if kind == DESKTOP:
        return True, i18n.tr("MoreMenu", "已在桌面创建快捷方式")
    return True, i18n.tr("MoreMenu", "已在开始菜单创建快捷方式")
