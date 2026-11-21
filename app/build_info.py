"""构建标识（commit 短号）—— 开发水印第二行的唯一来源。

2026-11-15（用户指令「开发中水印加上 commit 号」）：水印要能一眼看出「这是哪次
提交编出来的」，第二行从三段扩成四段：版本号 / 开发代号 / commit 短号 / 设备ID。

为什么读取分两条路、而且**不调 git 可执行文件**：
* 源码跑（``RESOURCE_ROOT`` = 仓库根）：直接解析 ``.git/HEAD`` 那条引用链。
  启动期起子进程太重，用户机器也未必装了 git；而且这样开发中随手 commit 后
  重启即变，不需要重新生成任何文件。
* 打包跑（PyInstaller）：exe 里没有 ``.git``，由 ``Luminalium.spec`` 在构建时
  把 HEAD 短号写进 ``build_info.json`` 随包分发，运行时读 ``RESOURCE_ROOT`` 下
  那一份。CI（直接调 PyInstaller）与本地 ``build.py`` 都走 spec，注入点只此一处。

读不到（源码包分发 / 浅克隆缺 refs / 构建文件丢了）一律返回空串：QML 侧把整段
省掉，绝不显示 "unknown" 之类的假值 —— 水印是给开发者定位版本用的，错号比没号糟。

短号固定截 7 位（``git rev-parse --short`` 的默认长度），水印第二行长度稳定。
``LUMINALIUM_COMMIT`` 可显式覆盖（排查「这个包到底是哪次 commit」时用）；构建期
没有这个变量时 ``GITHUB_SHA`` 自动兜底（CI 默认注入）。
"""

from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import paths

#: 短号长度；也是水印里显示的长度。
SHORT_LEN = 7
#: 打包时由 ``Luminalium.spec`` 生成、落在 ``_MEIPASS`` 根目录的文件名。
BUILD_INFO_FILE = "build_info.json"

_HEX = re.compile(r"[0-9a-fA-F]{7,40}")
_GIT_FILE_HEADER = re.compile(r"gitdir:\s*(.+)", re.IGNORECASE)


def _short(value: str) -> str:
    """把 40 位 sha / 脏字符串归一成 7 位短号；不是 hex 就返回空串。"""
    text = str(value).strip()
    return text[:SHORT_LEN].lower() if _HEX.fullmatch(text) else ""


def _git_dir(repo_root: Path) -> Optional[Path]:
    """``.git`` 可能是目录（普通仓库）或一行文件（worktree / submodule）。"""
    dot = repo_root / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        try:
            match = _GIT_FILE_HEADER.search(dot.read_text(encoding="utf-8"))
        except OSError:
            return None
        if match:
            path = Path(match.group(1).strip())
            return path if path.is_absolute() else (repo_root / path).resolve()
    return None


def _from_git(repo_root: Path) -> str:
    """沿 ``HEAD -> ref -> sha`` 解析；refs 打过包就回退 ``packed-refs``。"""
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        return ""
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not head.lower().startswith("ref:"):
        return _short(head)  # detached HEAD：直接就是 sha

    ref = head.split(":", 1)[1].strip()
    # worktree 的 refs 存在公共 git 目录里（``commondir``），HEAD 仍在本目录。
    common = git_dir
    try:
        common_name = (git_dir / "commondir").read_text(encoding="utf-8").strip()
    except OSError:
        common_name = ""
    if common_name:
        path = Path(common_name)
        common = path if path.is_absolute() else (git_dir / path).resolve()

    try:
        return _short((common / ref).read_text(encoding="utf-8").strip())
    except OSError:
        pass
    try:
        for line in (common / "packed-refs").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line[0] in "#^":
                continue
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return _short(sha)
    except OSError:
        pass
    return ""


def _from_build_info() -> str:
    """打包环境：读 spec 在构建时写进 ``_MEIPASS`` 的那份短号。"""
    try:
        data = json.loads(
            (paths.RESOURCE_ROOT / BUILD_INFO_FILE).read_text(encoding="utf-8")
        )
    except (OSError, ValueError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return _short(data.get("commit", ""))


def build_commit(repo_root: Optional[Path] = None) -> str:
    """**构建期**用（``Luminalium.spec``）：显式变量 > 仓库当前 HEAD。

    两档环境变量分开的原因：``LUMINALIUM_COMMIT`` 是人为指定的覆盖，
    ``GITHUB_SHA`` 是 CI 自带、恰好等于 checkout 出来的 HEAD，优先级更低。
    """
    explicit = _short(
        os.environ.get("LUMINALIUM_COMMIT", "") or os.environ.get("GITHUB_SHA", "")
    )
    return explicit or _from_git(repo_root or paths.RESOURCE_ROOT)


@lru_cache(maxsize=1)
def commit_hash() -> str:
    """**运行期**用：一次进程内只解析一次（``Backend.commitHash`` 是 constant）。"""
    explicit = _short(os.environ.get("LUMINALIUM_COMMIT", ""))
    if explicit:
        return explicit
    if not getattr(sys, "frozen", False):
        live = _from_git(paths.RESOURCE_ROOT)
        if live:
            return live
    return _from_build_info()
