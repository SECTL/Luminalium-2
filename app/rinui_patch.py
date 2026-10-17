"""RinUI 补丁：按 UI 语言换默认 UI 字体（日语 Yu Gothic UI、韩语 Malgun Gothic 等）。

背景
----

RinUI 0.4.4 的 ``themes/utils.qml``（单例 ``Utils``）把 Windows 默认字体
写死成 ``"Microsoft YaHei"``::

    property string fontFamily: Qt.platform.os === "windows"
        ? "Microsoft YaHei" : Qt.application.font.family

``Rin.Text`` / ``Rin.TextField`` 都绑定 ``Utils.fontFamily``，而它是 QML
单例属性，Python 侧**没有**运行时改写的通道 —— 所以只能对已安装的
RinUI 包文件打补丁。

做法
----

``apply()`` 在**每次启动**时把 venv 里 ``RinUI/themes/utils.qml`` 的
``fontFamily`` 幂等地改写成按默认 QLocale 判断的版本（``app/i18n.py::
apply_locale`` 已把默认 QLocale 设成 ``app.language``）::

    property string fontFamily: Qt.platform.os === "windows"
        ? (Qt.locale().name.startsWith("ja") ? "Yu Gothic UI"
            : Qt.locale().name.startsWith("ko") ? "Malgun Gothic"
            : ... : "Microsoft YaHei")
        : Qt.application.font.family

* 语言 -> 字体的对照表**只有一份**，在 ``app/i18n.py::UI_FONTS``；这里
  按它生成 QML 表达式，另一侧 ``apply_ui_font`` 按它设 QApplication 字体。
  改字体只改那个 dict，别在这里另写一份。
* 表外语言（zh_CN / en_US 等）行为与原版**完全一致**（微软雅黑）；
* 打过补丁的文件带 ``[Luminalium font patch]`` 标记，重复启动不会重写；
  旧版标记 ``[Luminalium ja patch]``（2026-10-17 之前只认日语）也能被
  识别并**就地升级**成新版表达式，不用手工还原文件；
* RinUI 升级后文件变了、匹配不上时打不上去 —— 只告警不崩，字体退回
  微软雅黑；
* 打包（PyInstaller）时 ``collect_data_files("RinUI")`` 收的是 venv 里
  **已打补丁**的文件，会随包分发；frozen 运行时本身不再改写（``_MEIPASS``
  是临时解压目录，改了也留不住）。

⚠️ 2026-10-17 补的两道保险（当天真撞上「整个 QML 全挂」）：

* **原子写**（临时文件 + ``os.replace``）。原来直接 ``write_text``，多开
  一个进程（预览 / 探针 / 应用本身）同时启动就可能被读到一个写了一半的文件，
  而 ``utils.qml`` 是**所有** QML 的根导入 —— 表里少一个冒号，整个界面直接
  ``Type Utils unavailable``，报错还指在别处。
* **自愈**：标记在、表达式却不是当前这份（旧版本写坏 / 手改过）时**就地重写**。
  原来见到标记就 ``return``，于是一份写坏的文件永远修不回来 —— 再次启动、
  再打包，坏的一直跟着走。
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

from .i18n import UI_FONTS

log = logging.getLogger("luminalium")

#: 补丁标记：写过补丁的文件里能搜到这行注释。
_PATCH_MARKER = "[Luminalium font patch]"

#: 旧版补丁标记（2026-10-17 之前，只把日语换成 Yu Gothic UI）。带这个标记
#: 的文件要能升级成新版表达式，否则装过旧版的人永远停在日语-only 的版本上。
_LEGACY_MARKER = "[Luminalium ja patch]"

#: **任意** ``fontFamily`` 整块（原版 / 旧补丁 / 写坏的）。三种状态都靠它定位：
#: 匹配不到 = RinUI 换了写法（只告警，不硬改）。
#: 非贪婪到第一个 ``: Qt.application.font.family`` 为止；匹配不到就说明
#: RinUI 换了写法，别硬改（只告警）。
_ANY_FONT_RE = re.compile(
    r'property string fontFamily: Qt\.platform\.os === "windows".*?'
    r': Qt\.application\.font\.family',
    re.S,
)


def _font_family_expression() -> str:
    """按 ``UI_FONTS`` 生成 QML 侧的字体三元表达式。

    ⚠️ QML 里 ``Locale.name`` 是**属性**不是函数（``.name()`` 会抛 TypeError，
    把整个表达式算成 undefined → 字体空串），所以是 ``Qt.locale().name``。
    ``UI_FONTS`` 的键既可能是语言前缀（``ja``）也可能是完整代码（``zh_TW``），
    两者在 QLocale 的 ``name`` 上都是前缀，统一用 ``startsWith`` 判断。
    """
    # 三元链：第一项开括号，其后每一项都要带前导的 ``:``（QML 的 ?: 右结合，
    # 少一个冒号整条表达式就解析失败 → Utils.fontFamily 变成空串）。
    lines = []
    for i, (key, family) in enumerate(UI_FONTS.items()):
        indent = "        ? (" if i == 0 else "            : "
        lines.append(f'{indent}Qt.locale().name.startsWith("{key}") ? "{family}"')
    lines.append('            : "Microsoft YaHei")')
    body = "\n".join(lines)
    return (
        'property string fontFamily: Qt.platform.os === "windows"\n'
        f"{body}\n"
        "        : Qt.application.font.family"
    )


_PATCHED = _font_family_expression()


def _rinui_qml_dir() -> Path | None:
    """定位已安装 RinUI 包的目录（site-packages/RinUI）。"""
    try:
        import RinUI  # noqa: PLC0415 —— 启动期一次性定位，延迟导入避免循环

        return Path(RinUI.__file__).resolve().parent
    except Exception:  # pragma: no cover —— 没装 RinUI 时后面的引擎也起不来
        return None


def apply() -> None:
    """把字体补丁幂等地打到已安装的 RinUI 上（失败只告警，不阻塞启动）。"""
    if getattr(sys, "frozen", False):
        log.info("RinUI 字体补丁：打包运行，跳过（包内文件已带补丁）")
        return

    pkg = _rinui_qml_dir()
    if pkg is None:
        log.warning("RinUI 字体补丁：找不到已安装的 RinUI，跳过")
        return

    utils_qml = pkg / "themes" / "utils.qml"
    if not utils_qml.exists():
        log.warning("RinUI 字体补丁：不存在 %s，跳过", utils_qml)
        return

    try:
        text = utils_qml.read_text(encoding="utf-8")
    except OSError:
        log.warning("RinUI 字体补丁：读取失败 %s，跳过", utils_qml, exc_info=True)
        return

    # 已经是当前这份表达式 → 什么都不做（幂等）。
    if _PATCHED in text:
        log.info("RinUI 字体补丁：已应用过（%s）", utils_qml)
        return

    match = _ANY_FONT_RE.search(text)
    if match is None:
        log.warning(
            "RinUI 字体补丁：%s 里找不到 fontFamily 写法"
            "（RinUI 版本变了？），跳过 —— UI 字体保持微软雅黑",
            utils_qml,
        )
        return

    # 走到这里说明「要写」：区分是原版 / 旧补丁 / 写坏的（只影响日志与注释清理）
    if _LEGACY_MARKER in text:
        note = "旧版（只认日语）升级"
        # 旧版标记那行注释说「只认日语」，留着会骗人 —— 先删掉
        text = "\n".join(
            line for line in text.splitlines() if _LEGACY_MARKER not in line
        )
        # 删行会挪位置，重新定位一次
        match = _ANY_FONT_RE.search(text)
        if match is None:  # pragma: no cover —— 理论上不可能
            return
    elif _PATCH_MARKER in text:
        # 标记在、表达式却不是当前这份 = 之前写坏了或被人改过 → 自愈
        note = "表达式与当前版本不符，就地重写"
    else:
        note = "原版"

    patched = text[:match.start()] + (
        "// %s app/rinui_patch.py 启动时改写：\n    %s"
        % (_PATCH_MARKER, _PATCHED)
    ) + text[match.end():]

    # ⚠️ 原子写：utils.qml 是所有 QML 的根导入，被读到半截就等于「整个界面挂掉」。
    tmp = utils_qml.with_suffix(".qml.tmp")
    try:
        tmp.write_text(patched, encoding="utf-8")
        os.replace(tmp, utils_qml)
    except OSError:
        log.warning("RinUI 字体补丁：写入失败 %s，跳过", utils_qml, exc_info=True)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return
    fonts = " / ".join(f"{k}→{v}" for k, v in UI_FONTS.items())
    log.info("RinUI 字体补丁：已应用（%s，%s）→ %s", utils_qml, note, fonts)
