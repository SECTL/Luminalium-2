"""本地打包脚本：PyInstaller 构建 Luminalium 2。

2026-10-08 用户指令：写一个打包脚本放在项目根目录。

为什么要这个脚本而不是直接敲 PyInstaller：
1. 与 CI（.github/workflows/nightly.yml）的构建方式严格对齐 —— 同样的
   ``--noconfirm --clean``、同样的 dist/onefile 与 dist/onedir 分目录，
   本地产物和 Nightly 产物结构一致，排查「我这能跑 CI 不能跑」类问题时
   少一个变量。
2. PyInstaller 不在 requirements.txt 里（它只是构建期工具，不进运行时依赖），
   本脚本负责按需安装（>=6.10，与 CI 同一约束），免得每次换环境都手工补。
3. GBK 控制台坑（见 .memory/topics/rinui-gbk-crash.md）：统一用 ``-X utf8``
   起 Python，避免构建日志里的中文把 GBK 控制台弄崩。

用法：
    .venv\\Scripts\\python.exe build.py            # 目录版（dist/onedir，启动快，默认）
    .venv\\Scripts\\python.exe build.py --onefile  # 单文件版（dist/onefile，便于分发）
    .venv\\Scripts\\python.exe build.py --both     # 两个都打（与 CI 一致）

spec 的 ONEFILE 开关通过环境变量 LUMINALIUM_ONEFILE 传递（spec 注释原话：
PyInstaller 一次只能产一种）。版本资源文件（LUMINALIUM_VERSION_FILE）是 CI
注入的可选项，本地不生成，spec 会自动跳过。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SPEC = ROOT / "Luminalium.spec"


def _run(cmd: list[str], env: dict[str, str]) -> int:
    # 构建日志要实时滚，出问题能看到停在哪一步
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    return proc.returncode


def _ensure_pyinstaller(env: dict[str, str]) -> None:
    probe = subprocess.run(
        [str(VENV_PYTHON), "-X", "utf8", "-c", "import PyInstaller"],
        cwd=ROOT, env=env, capture_output=True,
    )
    if probe.returncode == 0:
        return
    print("PyInstaller 未安装，按 CI 约束安装 pyinstaller>=6.10 ...")
    code = _run(
        [str(VENV_PYTHON), "-X", "utf8", "-m", "pip", "install", "pyinstaller>=6.10"],
        env,
    )
    if code != 0:
        sys.exit("PyInstaller 安装失败，构建中止")


def _build(onefile: bool) -> int:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"  # 子进程输出的中文在重定向下不炸
    # spec 读 LUMINALIUM_ONEFILE 决定形态；目录版要确保清掉这个变量
    if onefile:
        env["LUMINALIUM_ONEFILE"] = "1"
    else:
        env.pop("LUMINALIUM_ONEFILE", None)

    kind = "onefile" if onefile else "onedir"
    code = _run(
        [
            str(VENV_PYTHON), "-X", "utf8", "-m", "PyInstaller",
            "--noconfirm", "--clean",
            "--distpath", f"dist/{kind}",
            "--workpath", f"build/{kind}",
            str(SPEC),
        ],
        env,
    )
    if code == 0:
        artifact = (
            ROOT / "dist" / "onefile" / "Luminalium2.exe"
            if onefile
            else ROOT / "dist" / "onedir" / "Luminalium2"
        )
        print(f"\n构建完成: {artifact}")
    return code


def main() -> int:
    args = set(sys.argv[1:])
    if not VENV_PYTHON.is_file():
        sys.exit(f"找不到 venv 解释器: {VENV_PYTHON}（先在仓库根目录建 .venv）")
    if not SPEC.is_file():
        sys.exit(f"找不到 {SPEC}")

    _ensure_pyinstaller(dict(os.environ))

    if "--both" in args:
        targets = (True, False)
    elif "--onefile" in args:
        targets = (True,)
    else:
        targets = (False,)

    for onefile in targets:
        code = _build(onefile)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
