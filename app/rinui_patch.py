"""RinUI 补丁：UI 语言为日语时，默认 UI 字体用 Yu Gothic UI 而非微软雅黑。

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
        ? (Qt.locale().name.startsWith("ja") ? "Yu Gothic UI" : "Microsoft YaHei")
        : Qt.application.font.family

* zh_CN / en_US 等非日语环境行为与原版**完全一致**（微软雅黑）；
* 打过补丁的文件带 ``[Luminalium ja patch]`` 标记，重复启动不会重写；
* RinUI 升级后文件变了、匹配不上时打不上去 —— 只告警不崩，字体退回
  微软雅黑；
* 打包（PyInstaller）时 ``collect_data_files("RinUI")`` 收的是 venv 里
  **已打补丁**的文件，会随包分发；frozen 运行时本身不再改写（``_MEIPASS``
  是临时解压目录，改了也留不住）。
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

log = logging.getLogger("luminalium")

#: 补丁标记：写过补丁的文件里能搜到这行注释。
_PATCH_MARKER = "[Luminalium ja patch]"

#: 原版 ``fontFamily``（RinUI 0.4.4，themes/utils.qml）。允许换行与缩进有出入，
#: 用正则匹配而不是全文比对 —— 升级到相近版本时不至于一改就失配。
_ORIGINAL_RE = re.compile(
    r'property string fontFamily: Qt\.platform\.os === "windows"\s*'
    r'\? "Microsoft YaHei" : Qt\.application\.font\.family'
)

#: 补丁后的 ``fontFamily``。日语（默认 QLocale 为 ja_*）→ Yu Gothic UI。
#: ⚠️ QML 里 ``Locale.name`` 是**属性**不是函数（``.name()`` 会抛 TypeError，
#: 把整个表达式算成 undefined → 字体空串），所以是 ``Qt.locale().name``。
_PATCHED = (
    'property string fontFamily: Qt.platform.os === "windows"\n'
    '        ? (Qt.locale().name.startsWith("ja") ? "Yu Gothic UI" : "Microsoft YaHei")\n'
    "        : Qt.application.font.family"
)


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

    if _PATCH_MARKER in text:
        log.info("RinUI 字体补丁：已应用过（%s）", utils_qml)
        return

    if not _ORIGINAL_RE.search(text):
        log.warning(
            "RinUI 字体补丁：%s 里找不到原版 fontFamily 写法"
            "（RinUI 版本变了？），跳过 —— UI 字体保持微软雅黑",
            utils_qml,
        )
        return

    patched = _ORIGINAL_RE.sub(
        "// %s app/rinui_patch.py 启动时改写：\n    %s" % (_PATCH_MARKER, _PATCHED),
        text,
        count=1,
    )
    try:
        utils_qml.write_text(patched, encoding="utf-8")
    except OSError:
        log.warning("RinUI 字体补丁：写入失败 %s，跳过", utils_qml, exc_info=True)
        return
    log.info("RinUI 字体补丁：已应用（%s）→ 日语时使用 Yu Gothic UI", utils_qml)
