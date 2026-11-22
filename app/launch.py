"""启动参数与「拉起一个新进程」。

两个东西放在一起是有原因的：**参数是谁拼的、进程是谁拉起的，必须同一处**
—— 否则「重启并进入维护模式」很容易只改了一半（拉起的进程没带标记，
用户点完菜单什么都没发生，日志里也看不出破绽）。

2026-11-22 从 ``application.py::_restart`` 抽出。动机：维护模式
（``app/maintenance.py``）要从**另一套装配**里做同一件事 —— 从维护模式点
「继续使用」= 拉一个**正常**进程再退出自己。把命令行拼接留在
``LuminaliumApplication`` 的方法里，维护模式就只能复制一份，而复制出来的
那半份迟早会和这边走岔。

命令行怎么拼（逐字沿用原来的两支）：

* 打包后（``sys.frozen``）：直接再跑 ``sys.executable``；
* 源码运行：``sys.executable + 脚本绝对路径``。``sys.argv[0]`` 就是入口脚本，
  解析成绝对路径保证与启动时的工作目录无关。

⚠️ 重启交接的两个环境变量（``multi_instance.RESTART_ENV`` /
``RESTART_PID_ENV``）也在这里设：新进程检测到旧实例时只做交接等待，
不弹「你多开了」的询问框。维护模式那条路同样需要 —— 从维护模式回到正常
模式时，维护进程此刻还活着。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

from . import multi_instance

log = logging.getLogger(__name__)

#: 启动即进入维护模式（设置标题栏「更多」→「重新启动并进入维护模式」）。
MAINTENANCE_FLAG = "--maintenance"
#: 不加载插件（维护模式「以安全模式继续使用」）。
SAFE_FLAG = "--safe"
#: 日志级别拉到 DEBUG（维护模式「以诊断模式继续使用」）。
DIAGNOSTIC_FLAG = "--diagnostic"


def _has(argv: Iterable[str], flag: str) -> bool:
    """参数表里有没有这个开关（大小写不敏感，容忍 ``--flag`` 前后的空白）。

    ⚠️ 必须**精确**比对整段参数，不能用 ``in`` 子串判断：源码运行时参数表里
    第二项是脚本绝对路径，路径里出现 ``--safe`` 这种字样（有人真把仓库放在
    叫 ``--safe`` 的目录下）就会误判。
    """
    needle = flag.lower()
    return any(str(arg).strip().lower() == needle for arg in argv)


def maintenance_requested(argv: Iterable[str]) -> bool:
    return _has(argv, MAINTENANCE_FLAG)


def safe_mode_requested(argv: Iterable[str]) -> bool:
    return _has(argv, SAFE_FLAG)


def diagnostic_requested(argv: Iterable[str]) -> bool:
    return _has(argv, DIAGNOSTIC_FLAG)


def build_command(extra_args: Sequence[str] = ()) -> tuple[list[str], str]:
    """返回 ``(命令行, 工作目录)``。见模块头注释的两支。"""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
        cwd = str(Path(sys.executable).parent)
    else:
        script = Path(sys.argv[0] if sys.argv else "main.py").resolve()
        cmd = [sys.executable, str(script)]
        cwd = str(script.parent)
    return cmd + [str(arg) for arg in extra_args], cwd


def relaunch(extra_args: Sequence[str] = ()) -> bool:
    """拉起一个**分离的**新进程（与当前控制台 / 父进程解绑）；成功返回 True。

    失败只记日志并返回 False —— 调用方据此**保持当前进程活着**：拉不起来
    还退掉，用户手里就什么都不剩了。
    """
    cmd, cwd = build_command(extra_args)
    # DETACHED_PROCESS：脱离控制台（GUI 程序本来也没有）；窗口控制在
    # DWM/Win32 侧，不需要继承任何句柄。close_fds 兜底防句柄泄漏。
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    env = os.environ.copy()
    env[multi_instance.RESTART_ENV] = "1"
    env[multi_instance.RESTART_PID_ENV] = str(os.getpid())
    try:
        subprocess.Popen(
            cmd,
            cwd=cwd,
            close_fds=True,
            creationflags=creationflags,
            env=env,
        )
    except OSError:
        log.exception("无法拉起新进程 %r，保持当前实例运行", cmd)
        return False
    log.info("已拉起新进程: %s", cmd)
    return True
