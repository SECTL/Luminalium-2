"""开机自启 —— Windows 注册表 ``Run`` 键。

「随系统启动」在 Windows 上的标准做法是往

    HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

写一个字符串值 —— 用户登录后由 ``explorer.exe`` 读这个键并执行。

几个刻意的选择：

* **HKCU 而不是 HKLM**：不需要管理员权限，且只对当前用户生效 —— 这正是
  一个桌面小工具该有的作用范围（写 HKLM 反而要提权，还会给所有用户装上）；
* **值名固定**（:data:`VALUE_NAME`）：关掉时靠它精确删除。改名会让旧值变成
  谁都不认领的幽灵启动项；
* **命令行指向真实可执行的入口**：打包后是 exe 本身，源码运行时是
  ``pythonw.exe main.py``（用 ``pythonw`` 而不是 ``python`` —— 否则每次开机
  都会先闪一个控制台黑框）。

⚠️ Windows 10/11 的「任务管理器 → 启动」并不会删除 ``Run`` 里的值，而是往

    HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\
        StartupApproved\\Run

写一个 12 字节的开关（首字节 ``0x02`` = 启用、``0x03`` = 禁用，后 8 字节是
禁用时刻的 FILETIME）。**只认 ``Run`` 键是不够的**：用户在任务管理器里把启动项
关掉之后，``Run`` 里的值还在，我们这边就会一直显示「已开启」，而系统根本不会
拉起它 —— 这正是「关了却没关掉」最容易出现的地方。所以读写两边都把
``StartupApproved`` 一起考虑：

* 读 —— 「``Run`` 里存在 **且** 没被 ``StartupApproved`` 禁用」才算开启；
* 开 —— 写 ``Run`` 值，并清掉可能残留的禁用标记（否则写了也白写）；
* 关 —— 删 ``Run`` 值，顺手把 ``StartupApproved`` 里那条一并清掉。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

#: 自启项所在的注册表路径（``HKEY_CURRENT_USER`` 下）。
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

#: 任务管理器「启动」页的开关所在路径（见模块 docstring）。
APPROVED_KEY_PATH = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
)

#: 注册表值名。**固定不变** —— 关掉时靠它精确删除，改名会留下删不掉的旧项。
VALUE_NAME = "Luminalium2"

#: ``StartupApproved`` 那 12 字节开关的首字节：``0x02`` = 启用、``0x03`` = 禁用。
_APPROVED_DISABLED = 0x03


def _winreg():
    """取 ``winreg`` 模块；非 Windows 或导入失败时返回 ``None``。

    单文件打包（PyInstaller）在 Windows 上一定带 ``winreg``；非 Windows 只是
    为了「导入本模块不炸」，调用方拿到 ``None`` 时按「不支持」处理。
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover - 正常 Windows 上不会发生
        return None
    return winreg


# ------------------------------------------------------------------ 命令行

def _entry_script() -> Path:
    """源码运行时的入口脚本。

    ⚠️ 以**资源根下的 ``main.py``** 为准（``paths.RESOURCE_ROOT`` = 开发时的项目
    根），而不是 ``sys.argv[0]``：``argv[0]`` 只说明「这一次是怎么被拉起来的」，
    用 ``tools/smoke.py`` 之类的外层脚本跑一遍，它就会指到那个脚本上 —— 照着写进
    注册表就成了一条「开机去跑测试脚本」的启动项（自检里真踩到过）。
    ``argv[0]`` 只在 ``main.py`` 不存在时兜底（非常规布局）。
    """
    from .paths import RESOURCE_ROOT

    canonical = (RESOURCE_ROOT / "main.py").resolve()
    if canonical.exists():
        return canonical
    argv0 = sys.argv[0] if sys.argv else ""
    candidate = Path(argv0)
    if candidate.suffix.lower() == ".py":
        try:
            return candidate.resolve()
        except OSError:  # pragma: no cover - 路径畸形时退回规范入口
            pass
    return canonical


def launch_command() -> str:
    """随系统启动时要执行的命令行（注册表里存的就是这一串）。"""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'

    interpreter = Path(sys.executable).resolve()
    # 源码运行：优先 pythonw.exe。注册表启动没有控制台宿主，用 python.exe
    # 会在每次开机时弹一个黑框，观感上像是出错了。
    pythonw = interpreter.with_name("pythonw.exe")
    if pythonw.exists():
        interpreter = pythonw
    return f'"{interpreter}" "{_entry_script()}"'


# ------------------------------------------------------------------ 读取

def _is_disabled_by_task_manager(winreg) -> bool:
    """任务管理器「启动」页是否把这个项禁用了（没有记录 = 没禁用）。"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, APPROVED_KEY_PATH, 0, winreg.KEY_READ
        ) as key:
            blob, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    except OSError:
        log.exception("读取 StartupApproved 失败，按未禁用处理")
        return False
    return bool(blob) and blob[0] == _APPROVED_DISABLED


def is_enabled() -> bool:
    """当前是否真的会随系统启动。

    读的是**注册表里的实际状态**，不是配置文件里的影子值 —— 用户可能在任务
    管理器里禁用、也可能手改过注册表，配置说了不算。
    """
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    except OSError:
        log.exception("读取开机自启注册表失败，按未开启处理")
        return False
    if not str(value).strip():
        # 空串会被系统当成一条要执行的命令，等于没有启动项。
        return False
    return not _is_disabled_by_task_manager(winreg)


# ------------------------------------------------------------------ 写入

def _delete_value(winreg, key, name: str) -> None:
    """删一个值；本来就没有时静默通过（关两次不该报错）。"""
    try:
        winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def _clear_approved(winreg) -> None:
    """清掉任务管理器留下的「已禁用」标记。

    只 ``OpenKey`` 不 ``CreateKeyEx``：键本来不存在就没必要为它建一个空壳。
    """
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, APPROVED_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            _delete_value(winreg, key, VALUE_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        log.exception("清理 StartupApproved 失败")


def set_enabled(enabled: bool) -> bool:
    """开关开机自启，返回操作是否**成功**。

    ⚠️ 返回 ``True`` 只代表注册表调用没抛异常，不代表最终状态就是想要的
    （组策略 / 杀软可能半途拦下）。调用方应当再 :func:`is_enabled` 回读一次，
    以回读结果为准 —— ``bridge.Backend._apply_autostart`` 就是这么做的。
    """
    winreg = _winreg()
    if winreg is None:
        log.warning("当前平台不支持开机自启（仅 Windows）")
        return False
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, VALUE_NAME, 0, winreg.REG_SZ, launch_command()
                )
            else:
                _delete_value(winreg, key, VALUE_NAME)
    except OSError:
        log.exception("写入开机自启注册表失败（enabled=%s）", enabled)
        return False

    # 无论开关，都要把任务管理器那条记录清掉：开着的时候它可能残留「已禁用」
    # （不清就白写），关掉之后它就成了没人认领的孤儿记录。
    _clear_approved(winreg)
    log.info("开机自启已%s：%s", "开启" if enabled else "关闭",
             launch_command() if enabled else VALUE_NAME)
    return True
