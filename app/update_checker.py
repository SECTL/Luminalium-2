"""检查更新机制（GitHub Releases 源）。

对应 ClassIsland 的 ``Services/AppUpdating/UpdateService.cs`` 里「检查更新」
那一段（``CheckUpdateAsync``）：拿远端最新版本号 → 与当前版本比较 →
有新版就再取一份详情（版本号 + 更新日志）。区别只在**更新源**：

* ClassIsland 用自己的发行服务器（Phainon DistributionCenter）；
* 本项目托管在 GitHub，天然的分发源就是 **GitHub Releases**。

通道（channel）语义也对齐：

* ``stable``  —— 只看正式发布（GitHub 的 release 且非 prerelease）；
* ``preview`` —— 连预发布一起看（prerelease 也算候选）。

⚠️ 这个模块只负责「查」，不碰 Qt：检查在后台线程里跑，结果经
``bridge.Backend.requestCheckUpdate`` 的信号回 UI 线程 —— 与
``echo_cave`` / ``diagnostics`` 同一条约定。**下载与部署环节刻意未实现**
（2026-10-05 用户指令「目前先不要实现更新部署」）：状态机里预留了
ClassIsland 的 ``UpdateDownloaded`` / ``UpdateDeployed`` 两档，接部署时
从这里往下续。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request

log = logging.getLogger(__name__)

#: 本项目的 GitHub 仓库（与「关于」页 / 主页的 ``repoUrl`` 同一份口径）。
REPO = "SECTL/Luminalium-2"

#: GitHub Releases 列表接口。一次拿 30 条（API 默认值）足够：检查只需要
#: 「最新的一条」，外加「当前版本对应的旧发布」（给「查看更新日志」用）。
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"

#: 单次请求超时（秒）。GitHub 在墙内的可达性起伏很大，给宽一点，
#: 但也不能让「正在检查更新…」挂到天荒地老。
REQUEST_TIMEOUT = 12.0

#: 更新通道 -> 该通道下可接受的发布。键会出现在配置 ``update.channel`` 与
#: 设置页「更新通道」下拉里，别乱改。
CHANNELS: dict[str, str] = {
    "stable": "正式发布的版本，经过完整测试。",
    "preview": "包含最新的功能与修复，但可能不稳定。",
}

#: 检查结果状态。前两档与 ClassIsland 的 ``UpdateStatus`` 同名段对齐；
#: ``unknown`` = 本次运行还没检查过。
STATUS_UP_TO_DATE = "uptodate"
STATUS_AVAILABLE = "available"
STATUS_UNKNOWN = "unknown"


def parse_version(text: str) -> tuple[int, ...] | None:
    """把 ``v26.0.707.1`` 这类版本号拆成可比较的整数元组。

    版本号格式见 ``app/__init__.py``（年份.中版本.小版本.状态），逐段按整数比。
    解析不了（tag 是 ``nightly`` 之类）返回 None，调用方当作「不可比」跳过。
    """
    match = re.match(r"^[vV]?(\d+(?:\.\d+)*)$", str(text or "").strip())
    if match is None:
        return None
    try:
        return tuple(int(part) for part in match.group(1).split("."))
    except ValueError:  # pragma: no cover - 正则已保证全是数字
        return None


def _fetch_releases() -> list[dict]:
    """拉取 Releases 列表（新版在前，GitHub 固定如此）。

    ⚠️ GitHub API 要求带 ``User-Agent``，不带直接 403。
    ⚠️ 这里**故意走系统代理**（默认 opener）：GitHub 是本项目唯一可能需要
    代理才够得着的远端 —— 与 ``echo_cave`` 的 localhost 直连正好相反。
    """
    request = urllib.request.Request(
        RELEASES_URL,
        headers={
            "User-Agent": "Luminalium2-UpdateChecker",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, list) else []


def _release_matches_channel(release: dict, channel: str) -> bool:
    """通道过滤：stable 排除 prerelease 与 draft；preview 只排除 draft。"""
    if release.get("draft"):
        return False
    if channel == "preview":
        return True
    return not release.get("prerelease", False)


def check(channel: str, current_version: str, force: bool = False) -> dict:
    """检查一次更新。

    返回统一形状的结果 dict（Qt 侧原样转发给 QML）::

        {
            "status":           "uptodate" | "available" | "error",
            "latest_version":   str,   # 远端最新版本号（无新版时为空）
            "changelog":        str,   # 最新一版的更新日志（Markdown 原文）
            "release_url":      str,   # 该次发布的网页地址
            "current_changelog": str,  # 当前版本自己的更新日志（无则空）
            "error":            str,   # 失败原因（status=error 时才有）
        }

    ``force`` 对应 ClassIsland 的「强制检查更新」（``CheckUpdateAsync(isForce)``）：
    即使远端版本**不比当前新**也报 ``available`` —— 用来把同一个版本强制
    重新装一遍（排障用）。
    """
    result: dict = {
        "status": STATUS_UP_TO_DATE,
        "latest_version": "",
        "changelog": "",
        "release_url": "",
        "current_changelog": "",
        "error": "",
    }

    try:
        releases = _fetch_releases()
    except Exception as exc:  # noqa: BLE001 - 网络失败是常态，交给界面亮错误条
        log.warning("检查更新失败: %s", exc)
        result["status"] = "error"
        result["error"] = str(exc)
        return result

    candidates = [
        release for release in releases
        if _release_matches_channel(release, channel)
    ]
    if not candidates:
        # 仓库还没发过这个通道的版：当作已是最新（与 ClassIsland 的
        # 「通道不存在时回落默认通道」同一种「查不到就算了」的处理）。
        return result

    latest = candidates[0]
    latest_tag = str(latest.get("tag_name") or "")
    latest_version = parse_version(latest_tag)
    current = parse_version(current_version)

    # 当前版本自己的发布（「查看更新日志」按钮看的就是它）。
    for release in candidates:
        if parse_version(str(release.get("tag_name") or "")) == current:
            result["current_changelog"] = str(release.get("body") or "")
            break

    is_newer = (
        latest_version is not None
        and current is not None
        and latest_version > current
    )
    if not is_newer and not force:
        return result

    result["status"] = STATUS_AVAILABLE
    result["latest_version"] = latest_tag
    result["changelog"] = str(latest.get("body") or "")
    result["release_url"] = str(latest.get("html_url") or "")
    return result
