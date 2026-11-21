"""多实例检测（2026-11-22，照 Luminalium 1 的 ``_handle_multi_instance`` 移植）。

**只检测、不弹窗**：这里负责「找同入口的其它进程 / 等它退出 / 杀掉它」，
「问用户怎么办」的界面在 ``ui/MultiInstanceDialog.qml``，装配与决策在
``app/application.py::_guard_multi_instance``。

判定「同一程序」的锚点是**入口文件**，不是窗口类名或互斥体：

* 打包后 —— ``sys.executable``（exe 绝对路径）；
* 源码运行 —— ``sys.argv[0]``（``main.py``）。⚠️ 不能拿本模块的 ``__file__``：
  那是 ``app/multi_instance.py``，永远匹配不上进程命令行里的 ``main.py``。

进程命令行里可能有相对路径，所以像 L1 一样先按该进程的 ``cwd()`` 解析成
绝对路径再比；拿不到 ``cwd()``（权限 / 进程已退）就跳过那一段。

**重启不是多开**：``_restart`` 拉起新进程时会带 ``LUMINALIUM_RESTART`` 和
``LUMINALIUM_RESTART_PID``。新进程检测到旧实例时先等它自己退（最多
``RESTART_WAIT_SECONDS``），超时才 kill —— 重启走的是「排班交接」，不该弹
「你多开了」的对话框。环境变量读完即 pop，避免再下一次重启一路继承。

``LUMINALIUM_DISABLE_MULTI_INSTANCE=1`` 整段跳过（测试 / 排查用）。
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Iterable, Optional

log = logging.getLogger("luminalium")

#: 整段检测的开关（L1 同名环境变量）
DISABLE_ENV = "LUMINALIUM_DISABLE_MULTI_INSTANCE"
#: 本进程是被 ``_restart`` 拉起来的新实例
RESTART_ENV = "LUMINALIUM_RESTART"
#: 拉起新实例的旧进程 PID（旧进程可能刚好是当前进程的父进程，扫描时会被跳过，
#: 所以重启路径要单独带上它）
RESTART_PID_ENV = "LUMINALIUM_RESTART_PID"

#: 重启交接时等旧实例自己退出的上限；超时才动手 kill
RESTART_WAIT_SECONDS = 3.0
#: 等进程消失的轮询步长
_WAIT_STEP_SECONDS = 0.1

#: L1 里那几个辅助进程不是主实例，扫到也不能算
_SKIP_ARGS = ("--webview-runner", "--memory-cleaner", "--watchdog")


def is_disabled() -> bool:
    value = str(os.environ.get(DISABLE_ENV, "")).strip().lower()
    return value in ("1", "true", "yes", "on")


def consume_restart_request() -> tuple[bool, Optional[int]]:
    """读出并清掉「本次是重启拉起」的标记。

    返回 ``(是否重启, 旧进程 PID)``。PID 只是补充线索：旧进程通常就是当前
    进程的父进程，扫描时会被主动跳过，所以重启等待列表要把它加回去。
    """
    flag = str(os.environ.pop(RESTART_ENV, "")).strip().lower()
    pid_text = os.environ.pop(RESTART_PID_ENV, "")
    restart_pid: Optional[int] = None
    try:
        if pid_text:
            restart_pid = int(pid_text)
    except (TypeError, ValueError):
        restart_pid = None
    return flag in ("1", "true", "yes", "on"), restart_pid


def _current_entry() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    entry = sys.argv[0] if sys.argv else "main.py"
    return os.path.abspath(entry)


def _normalize(path: str, cwd: Optional[str]) -> Optional[str]:
    if not path or path.startswith("-"):
        return None
    if os.path.isabs(path):
        return os.path.abspath(path)
    if not cwd:
        return None
    return os.path.abspath(os.path.join(cwd, path))


def find_existing_instances() -> list[int]:
    """返回同入口的其它进程 PID（不含当前进程与父进程）。

    ``psutil`` 缺失时静默返回空表 —— 宁可少一层保护，也不能让程序起不来。
    """
    if is_disabled():
        return []

    try:
        import psutil
    except ImportError:
        log.debug("未安装 psutil，跳过多实例检测")
        return []

    current_pid = os.getpid()
    parent_pid = os.getppid()
    current_entry = os.path.normcase(_current_entry())
    pids: list[int] = []

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            pid = proc.info.get("pid")
            if pid in (None, 0, current_pid, parent_pid):
                continue
            cmd = proc.info.get("cmdline") or []
            if any(arg in _SKIP_ARGS for arg in cmd):
                continue
            # ``uv run ...`` 之类的外层启动器不是主实例
            if cmd:
                launcher = os.path.basename(str(cmd[0])).lower()
                if launcher in ("uv", "uv.exe") and "run" in cmd:
                    continue

            try:
                cwd = proc.cwd()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                cwd = None

            for part in cmd:
                if not isinstance(part, str):
                    continue
                normalized = _normalize(part, cwd)
                if normalized and os.path.normcase(normalized) == current_entry:
                    pids.append(pid)
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue

    return pids


def wait_for_exit(pids: Iterable[int], timeout: float = RESTART_WAIT_SECONDS) -> list[int]:
    """等这些 PID 自己消失，返回超时后仍活着的那些。"""
    try:
        import psutil
    except ImportError:
        return []

    alive = list(pids)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alive = [pid for pid in alive if psutil.pid_exists(pid)]
        if not alive:
            return []
        time.sleep(_WAIT_STEP_SECONDS)
    return [pid for pid in alive if psutil.pid_exists(pid)]


def terminate_instances(pids: Iterable[int], settle_seconds: float = 0.5) -> None:
    """强杀这些 PID（L1 的行为：不先发礼貌信号，演示软件旁边没有优雅退出的余量）。

    ``settle_seconds`` 是杀完后的短暂等待，让文件句柄 / 单实例资源来得及释放，
    避免新实例立刻去读旧实例还在写的配置。
    """
    try:
        import psutil
    except ImportError:
        return

    killed = 0
    for pid in pids:
        try:
            psutil.Process(pid).kill()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        except Exception:  # pragma: no cover - psutil 的异常面比文档宽
            log.debug("结束旧实例 %s 失败", pid, exc_info=True)
    if killed:
        log.info("已结束 %d 个旧实例", killed)
        time.sleep(settle_seconds)
