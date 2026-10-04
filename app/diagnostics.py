"""诊断信息采集。

**字段口径照 ClassIsland**（``Services/DiagnosticService.cs`` 的
``GetDiagnosticInfo()``）：英文 PascalCase 键 + ``Key: Value`` 逐行，**不翻译**。
这份文本的用途是贴进 issue / 求助帖，键名保持语言中立才能被不同语言的维护者
一眼检索到 —— ClassIsland 的界面是中文，诊断键却同样是英文，正是这个道理。
所以本模块只回稳定英文键，QML 侧也**不再**把键名映射成中文（旧版有
``diagnosticLabel``，已按用户指令去掉）。

硬件那几项（CPU / 显卡 / 内存 / 显示器）ClassIsland 没有（它交给 Sentry），
是本应用需要的，沿用它同一套命名与排布；应用侧还补了 Python / Qt 运行时，
排查 PySide6 应用时这几行往往比系统信息更关键。

移植自 Luminalium 1 的 ``plugins/builtins/settings/diagnostic_info.py``，但把
**子进程查询换成了注册表 / ctypes**：L1 那版靠 ``wmic`` 取 CPU / 显卡 / 内存，
而 Windows 11 24H2 起 ``wmic`` 默认已移除，那几条会一律退化成空。注册表、
``GlobalMemoryStatusEx`` 与 ``GetProcessMemoryInfo`` 都不起进程、毫秒级返回，
且不受系统裁剪影响。

⚠️ 采集结果含**本机路径**（应用包根目录 / 应用根目录 / 运行目录 / 日志文件）。
ClassIsland 与 L1 同样采集这些字段 —— 排查打包与权限问题时它们往往是关键证据。
界面侧会提示「分享前请检查」。

**刻意不采集**的两类字段，别当成漏了：

* ``UserTraceId`` / ``AppLoadedPlugin`` / ``AppIsAssetsTrimmed`` —— 分别是
  Sentry 链路 ID、插件清单、资源裁剪开关，本应用没有对应概念；
* ``DiagnosticFirstLaunchTime`` / ``DiagnosticStartupCount`` /
  ``DiagnosticMemoryKill*`` —— 需要一份跨启动持久化的统计账本，本应用还没有
  （L1 只有 ``ByMemoryKillCount`` 一项，来源是它的内存看门狗）。
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import sys
from typing import Dict, List, Optional, Tuple

from .paths import DATA_DIR, LOG_DIR, RESOURCE_ROOT

log = logging.getLogger(__name__)

#: 采集结果的字段顺序。分组与 ClassIsland 同源（系统 → 硬件 → 应用 → 运行时），
#: 键名在 ClassIsland 有对应项时**逐字沿用**（``SystemOsVersion`` /
#: ``SystemDeviceName`` / ``AppCurrentDirectory`` …），没有对应项的按同一风格补。
FIELD_ORDER: Tuple[str, ...] = (
    # —— 系统 ——
    "SystemOsVersion",
    "SystemOsArch",
    "SystemDeviceName",
    "SystemDeviceVendor",
    # —— 硬件（ClassIsland 无对应项）——
    "CPU",
    "GPU",
    "RAM",
    "Screen",
    # —— 应用 ——
    "AppPackageRoot",
    "AppRoot",
    "AppCurrentDirectory",
    "AppExecutingEntrance",
    "AppCurrentMemoryUsage",
    "AppVersion",
    "AppSubChannel",
    # —— 运行时（ClassIsland 无对应项）——
    "Python",
    "PySide6",
    "Qt",
    "PyWin32",
    "Presentation",
    "LogLevel",
    "LogFile",
)

#: 采集不到的字段统一回**空串**，由界面侧渲染成 ``Unknown``。
#:
#: ⚠️ 这里刻意不写中文「未知」：这个模块拿不到 Qt 的翻译器，硬编码中文会让
#: 英文 / 日文界面里冒出三个汉字。空串是语言中立的，且复制出去的那份文本
#: 也走界面侧同一个格式化函数（``About.qml::plainText``），口径一致。
UNKNOWN = ""


# ------------------------------------------------------------------ 通用助手


def _reg_local(subkey: str, name: str) -> str:
    """读 ``HKEY_LOCAL_MACHINE`` 下的一个字符串值；读不到返回空串。

    诊断是**尽力而为**：注册表被策略锁住、键不存在、类型不是字符串 —— 一律
    安静地返回空串，由调用方决定退回什么。绝不往外抛。
    """
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as key:
            return str(winreg.QueryValueEx(key, name)[0] or "").strip()
    except Exception:  # noqa: BLE001 - 诊断辅助，拿不到就算了
        return ""


def _read_first_line(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _format_size(size: int) -> str:
    """``234.5 MB`` 这种形态（1024 进制，保留一位小数）。"""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


# ------------------------------------------------------------------ 系统


def _os_version() -> str:
    """``Windows 11 24H2 (10.0.26300)`` 这种形态。

    注册表的 ``ProductName`` 在 Win11 上仍写 ``Windows 10``（老毛病），所以
    **以内部版本号为准**：``build >= 22000`` 判为 11。非 Windows 退回
    ``platform.release()``。

    对应 ClassIsland 的 ``SystemOsVersion``（那边取
    ``RuntimeInformation.OSDescription``，形态相近）。
    """
    if sys.platform != "win32":
        return f"{platform.release() or UNKNOWN} ({platform.version()})"

    current_version = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    try:
        build = int(_reg_local(current_version, "CurrentBuild"))
    except (TypeError, ValueError):
        build = 0
    edition = "Windows 11" if build >= 22000 else "Windows 10"
    display = _reg_local(current_version, "DisplayVersion")
    suffix = f" {display}" if display else ""
    return f"{edition}{suffix} ({platform.version()})"


def _os_arch() -> str:
    """``X64`` / ``X86`` / ``Arm64`` —— 与 ClassIsland 的 ``SystemOsArch`` 同义。

    ClassIsland 那边是 ``RuntimeInformation.OSArchitecture.ToString()``，枚举
    取值就是这几个；``platform.machine()`` 报的是 ``AMD64`` / ``aarch64`` 这类
    平台名，这里归一到同一套写法，好让两边的诊断文本能对着看。
    """
    machine = (platform.machine() or "").lower()
    return {
        "amd64": "X64",
        "x86_64": "X64",
        "x64": "X64",
        "x86": "X86",
        "i386": "X86",
        "i686": "X86",
        "arm64": "Arm64",
        "aarch64": "Arm64",
        "arm": "Arm",
    }.get(machine, platform.machine() or UNKNOWN)


def _device_vendor() -> str:
    """``SystemDeviceVendor`` —— ClassIsland 取 ``Win32_ComputerSystemProduct.Vendor``。"""
    bios = r"HARDWARE\DESCRIPTION\System\BIOS"
    return _reg_local(bios, "SystemManufacturer") or _read_first_line(
        "/sys/devices/virtual/dmi/id/sys_vendor"
    ) or UNKNOWN


def _device_model() -> str:
    """``SystemDeviceName`` —— ClassIsland 取 ``Win32_ComputerSystemProduct.Name``。"""
    bios = r"HARDWARE\DESCRIPTION\System\BIOS"
    return _reg_local(bios, "SystemProductName") or _read_first_line(
        "/sys/devices/virtual/dmi/id/product_name"
    ) or UNKNOWN


# ------------------------------------------------------------------ 硬件


def _cpu() -> str:
    value = _reg_local(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
    if value:
        return value
    if sys.platform == "linux":
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine() or UNKNOWN


def _gpu() -> str:
    """显卡名。

    路径是 Windows「显示适配器」设备类（``{4d36e968-...}``），实例键下的
    ``DriverDesc`` 就是驱动报告的名字。一台机器可能有 ``0000`` / ``0001``
    多个适配器，**全部收进来** —— 核显 + 独显时这一行往往是关键信息。
    """
    if sys.platform != "win32":
        return UNKNOWN

    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    names: List[str] = []
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as class_key:
            index = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(class_key, index)
                except OSError:
                    break
                index += 1
                if not sub_name.isdigit():
                    continue
                desc = _reg_local(f"{base}\\{sub_name}", "DriverDesc")
                if desc and desc not in names:
                    names.append(desc)
    except Exception:  # noqa: BLE001
        return UNKNOWN
    return ", ".join(names) if names else UNKNOWN


def _ram() -> str:
    """物理内存总量，``15.9 GB`` 这种形态。"""
    if sys.platform == "win32":
        try:
            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return f"{status.ullTotalPhys / (1024 ** 3):.1f} GB"
        except Exception:  # noqa: BLE001
            pass

    if sys.platform == "linux":
        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal"):
                        kib = int(line.split(":", 1)[1].strip().split()[0])
                        return f"{kib / (1024 ** 2):.1f} GB"
        except (OSError, ValueError, IndexError):
            pass
    return UNKNOWN


def _memory_usage_bytes() -> int:
    """本进程的**工作集**字节数（拿不到回 0）。"""
    if sys.platform == "win32":
        try:
            class _ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            # ⚠️ 两个坑，都踩过：
            #
            # 1. **函数名**：kernel32 在现代 Windows 上导出的是 ``K32GetProcessMemoryInfo``，
            #    不带 ``K32`` 前缀的 ``GetProcessMemoryInfo`` 在这里**根本不存在**
            #    （老文档里的写法是 psapi.dll 时代的）。所以要按
            #    ``K32...`` → ``psapi.dll`` 的顺序找。
            # 2. **``GetCurrentProcess`` 的 ``restype``**：ctypes 默认把返回值当 C
            #    ``int``（32 位），而 ``HANDLE`` 在 64 位下是 64 位 —— 伪句柄 ``-1``
            #    会被截成 ``0x00000000FFFFFFFF``，调用必然失败（字段恒为空）。
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_info = getattr(kernel32, "K32GetProcessMemoryInfo", None)
            if get_info is None:
                try:
                    get_info = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
                except Exception:  # noqa: BLE001
                    get_info = None
            if get_info is None:
                return 0

            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            get_info.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(_ProcessMemoryCounters),
                ctypes.c_ulong,
            ]
            get_info.restype = ctypes.c_int

            counters = _ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(_ProcessMemoryCounters)
            if get_info(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            ):
                return int(counters.WorkingSetSize)
        except Exception:  # noqa: BLE001
            pass
        return 0

    # Linux / macOS：VmRSS 最省事，取不到再退回 ru_maxrss。
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS"):
                    return int(line.split(":", 1)[1].strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except Exception:  # noqa: BLE001
        return 0


def _memory_usage() -> str:
    """``123.4 MB(129400832 Bytes)`` —— 与 ClassIsland 的 ``AppCurrentMemoryUsage``
    同格式（那边是 ``FormatSize(n) + $"({n} Bytes)"``，括号前不留空格）。"""
    size = _memory_usage_bytes()
    if size <= 0:
        return UNKNOWN
    return f"{_format_size(size)}({size} Bytes)"


# ------------------------------------------------------------------ 应用 / 运行时


def _executing_entrance() -> str:
    """``AppExecutingEntrance`` —— 正在跑的那个可执行文件。

    ClassIsland 取 ``AppBase.ExecutingEntrance``（打包后是 exe 路径）。本应用
    打包后 ``sys.executable`` 同样是 exe 本身；开发环境则是解释器路径，
    配合 ``AppRoot`` 足以还原「到底是谁在跑这份代码」。
    """
    return sys.executable or UNKNOWN


def _pyside_version() -> str:
    try:
        from PySide6 import __version__ as version

        return str(version)
    except Exception:  # noqa: BLE001
        return UNKNOWN


def _qt_version() -> str:
    try:
        from PySide6.QtCore import qVersion

        return str(qVersion())
    except Exception:  # noqa: BLE001
        return UNKNOWN


def _pywin32_version() -> str:
    """pywin32 的版本号；没装回 ``none``（比 ``yes`` / ``no`` 信息量大）。

    ⚠️ **不要**用 ``importlib.metadata.version("pywin32")``：它会遍历
    ``sys.path`` 的每一个条目去找 ``*.dist-info``，在本应用的 sys.path 下实测
    **耗时 8 秒**（应用里 sys.path 比裸解释器长得多）—— 那 8 秒会原样变成诊断
    对话框里的「加载中...」，踩过。改成从 ``win32api`` 的实际位置往上找
    ``pywin32-<版本>.dist-info``：只列一个目录，毫秒级。
    """
    try:
        import win32api
    except Exception:  # noqa: BLE001 - 没装 pywin32 就是这条路
        return "none"

    try:
        from pathlib import Path

        root = Path(win32api.__file__).resolve().parent
        # 布局通常是 site-packages/win32/win32api.pyd → dist-info 在再上一层。
        for base in (root, root.parent):
            for dist in sorted(base.glob("pywin32-*.dist-info")):
                return dist.name[len("pywin32-"):-len(".dist-info")]
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


# ------------------------------------------------------------------ 入口


def collect(extra: Optional[Dict[str, str]] = None) -> List[Tuple[str, str]]:
    """采集全部诊断字段，返回 ``[(key, value), ...]``（顺序同 ``FIELD_ORDER``）。

    ``extra`` 用来塞**必须问活体对象**的字段（屏幕尺寸 / 放映状态 / 日志级别 /
    版本号），由 ``bridge.Backend`` 提供 —— 这个模块刻意不 import Qt，好在没有
    QApplication 的场合（打包脚本、单测）也能跑。

    字段取不到时给**空串**而不是 ``None``：QML 侧统一把空串渲染成 ``Unknown``。
    """
    values: Dict[str, str] = {
        "SystemOsVersion": _os_version(),
        "SystemOsArch": _os_arch(),
        "SystemDeviceName": _device_model(),
        "SystemDeviceVendor": _device_vendor(),
        "CPU": _cpu(),
        "GPU": _gpu(),
        "RAM": _ram(),
        "AppPackageRoot": str(RESOURCE_ROOT),
        "AppRoot": str(DATA_DIR),
        "AppCurrentDirectory": os.getcwd(),
        "AppExecutingEntrance": _executing_entrance(),
        "AppCurrentMemoryUsage": _memory_usage(),
        "Python": platform.python_version(),
        "PySide6": _pyside_version(),
        "Qt": _qt_version(),
        "PyWin32": _pywin32_version(),
        "LogFile": str(LOG_DIR / "luminalium.log"),
    }
    values.update({str(k): str(v) for k, v in (extra or {}).items()})
    return [(key, values.get(key, "")) for key in FIELD_ORDER]
