"""Nightly 预发布：算版本号、生成发布说明、写 exe 版本资源、改 ``app/__init__.py``。

被 ``.github/workflows/nightly.yml`` 调用，也可以在本机干跑核对输出::

    python .github/scripts/nightly_release.py --dry-run

一次运行做四件事
----------------

1. **算版本号** —— 读 ``app/__init__.py`` 的基准版本（如 ``26.0.707.1``），
   拼成 ``26.0.707.1-nightly.20261005``（日期取**东八区**，因为 cron 跑在
   UTC，北京时间才是「今天」）；
2. **写回版本号** —— 原地改写 ``app/__init__.py`` 的 ``__version__``，这样打包
   出来的 exe 里，设置页与诊断信息报的都是这个 nightly 版本号（``app/bridge.py``
   / ``app/error_handler.py`` 都从 ``__version__`` 取），用户上报时能对上号；
3. **生成发布说明** —— ``dist/RELEASE_NOTES.md``：顶部贴头图、列出**本版本与
   上一个 nightly 之间**的提交（按 Conventional Commits 分组）、说清这是测试版、
   给出遇到问题时的处置与**带上诊断信息**的上报指引；
4. **写 exe 版本资源** —— ``dist/version_info.txt``（PyInstaller 的
   ``VSVersionInfo`` 格式），交给 ``Luminalium.spec``，让 exe 的「属性 → 详细信息」
   里也能看到 nightly 版本号。

GitHub Actions 侧还会把 ``version`` / ``tag`` / ``commit_count`` / ``should_publish``
等写进 ``$GITHUB_OUTPUT``（本机干跑时这一步自动跳过）。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ------------------------------------------------------------------ 常量

#: 仓库根目录（本脚本在 ``<root>/.github/scripts/`` 下）。
ROOT = Path(__file__).resolve().parents[2]

#: 版本号的唯一真源。``pyproject.toml`` 里那份是另一套发布口径，这里不碰。
INIT_FILE = ROOT / "app" / "__init__.py"

#: 产物目录（与 PyInstaller 的 ``--distpath dist/...`` 并列，不进 git）。
DIST_DIR = ROOT / "dist"

#: 头图在仓库里的**相对路径**（用户指定）。
BANNER_PATH = "docs/NewVersionUpdate-Banner.png"

#: 时区：cron 跑在 UTC，日期按东八区算才是「今天」。
CST = timezone(timedelta(hours=8))

#: 找不到上一个 nightly 时的兜底：列出全部历史，但最多这么多条。
MAX_COMMITS = 200

#: nightly 的 tag 前缀。用 ``nightly-YYYYMMDD`` 而不是版本号，好处是排序即时间序，
#: 找「上一个 nightly」只要 ``git tag --sort=-v:refname`` 取第一条。
TAG_PREFIX = "nightly-"

#: Conventional Commits 的分组口径（顺序即输出顺序）。
_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("新功能", ("feat", "feature")),
    ("问题修复", ("fix", "bugfix")),
    ("性能优化", ("perf",)),
    ("重构", ("refactor",)),
    ("样式与体验", ("style", "ui")),
    ("文档", ("docs",)),
    ("构建 / CI / 杂项", ("build", "ci", "chore", "test")),
)
#: 认不出来的提交丢这里。
_OTHER_GROUP = "其它"

_COMMIT_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)"
    r"(?:\((?P<scope>[^)]*)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<desc>.+)$"
)


# ------------------------------------------------------------------ 小工具


def _run_git(*args: str, check: bool = True) -> str:
    """跑一条 git 命令，返回 stdout（去掉尾部空白）。"""
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 失败（{result.returncode}）：{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _read_base_version() -> str:
    """从 ``app/__init__.py`` 读基准版本，并剥掉可能残留的 nightly 后缀。

    本地反复干跑时 ``__version__`` 会已经被改过一次，不剥的话版本号会越接越长
    （``26.0.707.1-nightly.20261004-nightly.20261005``）。
    """
    text = INIT_FILE.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise SystemExit(f"在 {INIT_FILE} 里找不到 __version__")
    return re.sub(r"-nightly\..*$", "", match.group(1)).strip()


def _write_version(new_version: str) -> None:
    """把 ``__version__`` 原地改成 ``new_version``（保留文件其余部分不动）。"""
    text = INIT_FILE.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'^(__version__\s*=\s*)"[^"]+"',
        lambda m: f'{m.group(1)}"{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit(f"改写 {INIT_FILE} 的 __version__ 失败")
    INIT_FILE.write_text(new_text, encoding="utf-8")


def _numeric_version(base: str) -> Tuple[int, int, int, int]:
    """把 ``26.0.707.1`` 拆成 Windows 版本资源要的四段整数。

    ``filevers`` 只吃四个 int，nightly 后缀塞不进去（那边另有字符串字段）。
    段数不足补 0，超过四段截断；非数字段一律当 0（防御性，正常不会遇到）。
    """
    parts: List[int] = []
    for chunk in base.split("."):
        digits = re.match(r"\d+", chunk)
        parts.append(int(digits.group(0)) if digits else 0)
        if len(parts) == 4:
            break
    while len(parts) < 4:
        parts.append(0)
    return parts[0], parts[1], parts[2], parts[3]


def _previous_nightly_tag(current_tag: str) -> Optional[str]:
    """最近一个 nightly tag；没有（或只剩当前这个）就返回 ``None``。"""
    output = _run_git("tag", "-l", f"{TAG_PREFIX}*", "--sort=-v:refname")
    for line in output.splitlines():
        tag = line.strip()
        if tag and tag != current_tag:
            return tag
    return None


def _collect_commits(prev_tag: Optional[str], head: str) -> List[Tuple[str, str]]:
    """收集 ``prev_tag..head``（无 prev_tag 则全部历史）的提交。

    返回 ``[(short_sha, subject), ...]``，**新→旧**。合并提交直接跳过 —— 它们
    对读更新说明的人没有信息量。
    """
    rev_range = f"{prev_tag}..{head}" if prev_tag else head
    # %h 短哈希 / %s 主题；用 NUL 分隔字段、用 0x1e 分隔记录，主题里的换行不会串行。
    output = _run_git(
        "log", rev_range, "--no-merges", "--pretty=format:%h%x1f%s%x1e"
    )
    commits: List[Tuple[str, str]] = []
    for record in output.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x1f")
        if len(parts) != 2:
            continue
        commits.append((parts[0].strip(), parts[1].strip()))
    return commits


def _group_commits(commits: Sequence[Tuple[str, str]]) -> Dict[str, List[str]]:
    """按 Conventional Commits 类型分组，返回 ``{组名: [markdown 行, ...]}``。

    认不出类型的进「其它」；``!``（breaking change）在行尾标一个 ``[破坏性变更]``。
    """
    buckets: Dict[str, List[str]] = {name: [] for name, _ in _GROUPS}
    buckets[_OTHER_GROUP] = []

    for sha, subject in commits:
        match = _COMMIT_RE.match(subject)
        if match is None:
            buckets[_OTHER_GROUP].append(f"- `{sha}` {subject}")
            continue

        kind = match.group("type").lower()
        scope = (match.group("scope") or "").strip()
        desc = match.group("desc").strip()
        breaking = " **[破坏性变更]**" if match.group("breaking") else ""

        target = _OTHER_GROUP
        for name, kinds in _GROUPS:
            if kind in kinds:
                target = name
                break

        prefix = f"**{scope}:** " if scope else ""
        buckets[target].append(f"- `{sha}` {prefix}{desc}{breaking}")

    return {name: lines for name, lines in buckets.items() if lines}


# ------------------------------------------------------------------ 发布说明


def _banner_url(repo: str, ref: str) -> str:
    """头图的绝对 URL。

    刻意用 ``raw.githubusercontent.com`` 的绝对地址、并把 ``ref`` 钉在**本次提交
    的 SHA** 上：发布说明里的相对路径在 release 页面能否解析并不稳，钉 SHA 则
    任何一次构建都指得准（哪怕头图后来被换掉，旧 nightly 也还是当时那张）。
    """
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{BANNER_PATH}"


def _build_notes(
    *,
    repo: str,
    ref: str,
    nightly_version: str,
    base_version: str,
    prev_tag: Optional[str],
    head_short: str,
    commits: Sequence[Tuple[str, str]],
    truncated: int,
    built_at: datetime,
) -> str:
    """拼出发布说明正文。"""
    issues_url = f"https://github.com/{repo}/issues/new"
    releases_url = f"https://github.com/{repo}/releases"
    stable_url = f"https://github.com/{repo}/releases/latest"

    if prev_tag:
        range_text = f"`{prev_tag}` → `{head_short}`（{len(commits)} 次提交）"
        compare_url = f"https://github.com/{repo}/compare/{prev_tag}...{ref}"
    else:
        range_text = f"首次 nightly 构建，列出仓库全部历史（{len(commits)} 次提交）"
        compare_url = f"https://github.com/{repo}/commits/{ref}"

    lines: List[str] = []
    lines.append(f"![Luminalium 2 更新横幅]({_banner_url(repo, ref)})")
    lines.append("")
    lines.append(f"# Luminalium 2 {nightly_version}")
    lines.append("")
    lines.append(
        "> **这是每夜自动构建的测试版本（Nightly / 预发布），不是稳定版。**"
    )
    lines.append(
        "> 它由 `master` 的最新提交自动打包，没有经过完整的回归验证，"
        "功能与行为都可能随时变动。"
    )
    lines.append("> **请不要把它用在正式演示、课堂投屏等不能出岔子的场合。**")
    lines.append("")
    lines.append(f"- **版本号**：`{nightly_version}`")
    lines.append(f"- **基准版本**：`{base_version}`")
    lines.append(f"- **构建时间**：{built_at.strftime('%Y-%m-%d %H:%M')} (UTC+8)")
    lines.append(f"- **提交范围**：{range_text}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 本次更新内容")
    lines.append("")

    if commits:
        grouped = _group_commits(commits)
        for name, entries in grouped.items():
            lines.append(f"### {name}")
            lines.append("")
            lines.extend(entries)
            lines.append("")
        if truncated:
            lines.append(f"> 另有更早的 {truncated} 次提交未在此列出。")
            lines.append("")
    else:
        lines.append("自上一个 nightly 以来没有新的提交，本次仅为重新构建。")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 遇到问题了怎么办")
    lines.append("")
    lines.append("测试版本出问题是正常的，不用忍，按下面的顺序来：")
    lines.append("")
    lines.append("1. **先重启一次程序** —— 多数偶发问题重启后就好了；")
    lines.append(
        f"2. **需要稳定使用就先回退** —— 到 [Releases]({stable_url}) "
        "下载最新的正式版覆盖安装即可；"
    )
    lines.append(
        "3. **能复现就上报** —— 带着诊断信息提 Issue，"
        "这样我们才定位得动（见下一节）。"
    )
    lines.append("")
    lines.append("## 上报问题（请附上诊断信息）")
    lines.append("")
    lines.append("没有诊断信息的问题单，多数只能停在「我这复现不了」。")
    lines.append("")
    lines.append("**第一步：取诊断信息（两种方式，任选）**")
    lines.append("")
    lines.append(
        "- 右键点击系统**托盘图标** → **「诊断信息（写入日志）」**，"
        "程序会把诊断信息写进 exe 同级的 `logs/luminalium.log`；"
    )
    lines.append(
        "- 如果程序弹出了**「错误报告 / 崩溃报告」**窗口，"
        "直接点窗口里的 **「复制」**（正文含环境信息 + 堆栈），"
        "或点 **「提交 Issue」** 让浏览器带上预填内容。"
    )
    lines.append("")
    lines.append("**第二步：提 Issue**")
    lines.append("")
    lines.append(f"到 {issues_url} 新建 Issue，并把下面这些一并贴上：")
    lines.append("")
    lines.append("- **诊断信息全文**（含 `AppVersion` / `SystemOsVersion` / `Python` / "
                 "`PySide6` / `Qt` / `LogFile` 等字段）—— 关键是把 `AppVersion` 带上，"
                 "好确认是不是这个 nightly 引入的；")
    lines.append("- **`logs/luminalium.log`** 里出错前后的相关片段；")
    lines.append("- **复现步骤**：点了什么、期望看到什么、实际看到什么；")
    lines.append("- 如果只在**特定的 PPT 文件 / 特定的 Office 版本 / 特定的系统版本**下出现，"
                 "也请注明。")
    lines.append("")
    lines.append(f"完整变更对比：{compare_url}")
    lines.append("")
    lines.append(
        "<!-- 本说明由 .github/scripts/nightly_release.py 自动生成，请勿手工编辑 -->"
    )
    lines.append("")
    return "\n".join(lines)


def _write_version_info(version: str, base_version: str) -> Path:
    """写 PyInstaller 的 Windows 版本资源文件，返回路径。"""
    filevers = _numeric_version(base_version)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    path = DIST_DIR / "version_info.txt"
    path.write_text(
        "# UTF-8\n"
        "# 由 .github/scripts/nightly_release.py 生成，勿手工编辑。\n"
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers={filevers!r},\n"
        f"    prodvers={filevers!r},\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable(\n"
        "        '040904B0',\n"
        "        [\n"
        "          StringStruct('CompanyName', 'SECTL'),\n"
        "          StringStruct('FileDescription', 'Luminalium 2 (Nightly)'),\n"
        f"          StringStruct('FileVersion', '{version}'),\n"
        "          StringStruct('InternalName', 'Luminalium2'),\n"
        "          StringStruct('LegalCopyright', 'MIT License'),\n"
        "          StringStruct('OriginalFilename', 'Luminalium2.exe'),\n"
        "          StringStruct('ProductName', 'Luminalium 2'),\n"
        f"          StringStruct('ProductVersion', '{version}'),\n"
        "        ]\n"
        "      )\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n",
        encoding="utf-8",
    )
    return path


# ------------------------------------------------------------------ 输出


def _set_output(key: str, value: str) -> None:
    """写一行到 ``$GITHUB_OUTPUT``（本机干跑时没有这个变量，安静跳过）。"""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


# ------------------------------------------------------------------ 主流程


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="生成 Luminalium 2 的 nightly 预发布")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只算不写：不改 app/__init__.py、不落盘产物，把结果打到 stdout",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="自上个 nightly 以来没有新提交时也照常发布",
    )
    args = parser.parse_args(argv)

    # 环境变量优先（workflow 用 env 传），命令行参数可覆盖。
    force = args.force or os.environ.get("FORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        # 本机干跑：从 origin 里推。
        remote = _run_git("remote", "get-url", "origin", check=False)
        match = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/.]+)", remote)
        repo = match.group("slug") if match else "SECTL/Luminalium-2"

    head = os.environ.get("GITHUB_SHA", "").strip() or _run_git("rev-parse", "HEAD")
    head_short = _run_git("rev-parse", "--short", head)

    built_at = datetime.now(CST)
    base_version = _read_base_version()
    nightly_version = f"{base_version}-nightly.{built_at.strftime('%Y%m%d')}"
    tag = f"{TAG_PREFIX}{built_at.strftime('%Y%m%d')}"

    prev_tag = _previous_nightly_tag(tag)
    commits = _collect_commits(prev_tag, head)

    truncated = 0
    if len(commits) > MAX_COMMITS:
        truncated = len(commits) - MAX_COMMITS
        commits = commits[:MAX_COMMITS]

    # 上个 nightly 之后一个提交都没有 → 默认不发，免得刷屏；--force 可覆盖。
    should_publish = bool(commits) or prev_tag is None or force

    notes = _build_notes(
        repo=repo,
        ref=head,
        nightly_version=nightly_version,
        base_version=base_version,
        prev_tag=prev_tag,
        head_short=head_short,
        commits=commits,
        truncated=truncated,
        built_at=built_at,
    )

    if args.dry_run:
        print(f"repo            = {repo}")
        print(f"head            = {head} ({head_short})")
        print(f"base version    = {base_version}")
        print(f"nightly version = {nightly_version}")
        print(f"tag             = {tag}")
        print(f"previous tag    = {prev_tag or '(无，首次构建)'}")
        print(f"commit count    = {len(commits)}")
        print(f"should publish  = {should_publish} (force={force})")
        print("-" * 60)
        print(notes)
        return 0

    _write_version(nightly_version)
    version_info = _write_version_info(nightly_version, base_version)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    notes_path = DIST_DIR / "RELEASE_NOTES.md"
    notes_path.write_text(notes, encoding="utf-8")

    _set_output("version", nightly_version)
    _set_output("base_version", base_version)
    _set_output("tag", tag)
    _set_output("prev_tag", prev_tag or "")
    _set_output("commit_count", str(len(commits)))
    _set_output("should_publish", "true" if should_publish else "false")
    _set_output("version_file", str(version_info))
    _set_output("notes_file", str(notes_path))

    print(f"nightly 版本   : {nightly_version}")
    print(f"tag            : {tag}")
    print(f"上一个 nightly : {prev_tag or '(无)'}")
    print(f"提交数         : {len(commits)}")
    print(f"是否发布       : {should_publish}")
    print(f"发布说明       : {notes_path}")
    print(f"版本资源       : {version_info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
