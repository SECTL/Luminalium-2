"""i18n：按 ``app.language`` 加载翻译、设定默认 QLocale 与应用字体。

约定
----

* 源语言 = 简体中文（QML 里 ``qsTr("中文")`` 的原文就是中文），所以
  ``zh_CN`` 不装翻译器、界面即原文；其它语言从 ``translations/`` 里找
  ``luminalium_<语言>.qm``（QML 与 Python 侧的 .ts 由 lrelease 合并成
  同一个 .qm）。
* 翻译**重启后生效**（与设置页「切换后需要重新加载应用」的文案一致）：
  翻译器必须在引擎加载任何 QML 之前装好，运行中途换语言对已创建的
  组件不生效。
* ``apply_locale`` 把 Qt 的**默认 QLocale** 设成配置里的 UI 语言。除了
  影响数字/日期的本地化格式，它还是 RinUI 字体补丁（``app/rinui_patch.py``）
  的语言信号 —— 补丁在 QML 单例里读 ``Qt.locale().name()`` 判断要不要把
  默认字体切成 Yu Gothic UI，因此**必须先于任何 QML 加载**调用。
* ``apply_ui_font`` 管 ``Rin.Text``/``Rin.TextField`` **之外**的控件：
  RinUI 的按钮、菜单、托盘等没有显式指定字体，走 QApplication 默认字体
  （Windows 上随系统语言）。UI 语言为日语时显式设成 Yu Gothic UI，与
  RinUI 补丁的行为一致；其它语言不动、跟随系统。
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .paths import TRANSLATIONS_DIR

log = logging.getLogger("luminalium")

#: 源语言：QML 字符串原文就是它，不需要翻译文件。
SOURCE_LANGUAGE = "zh_CN"

#: 下拉里有、但还没有翻译文件的语言：安静跳过（界面保持中文原文），
#: 不刷 warning —— 这是「暂未翻译」的已知状态，不是故障（见
#: ``config/default_config.json`` 的 ``//language`` 注释）。
#: 目前四种语言（zh_CN 源语言 / en_US / ja_JP）都已齐翻译，此集合留空备用。
UNTRANSLATED: set[str] = set()

#: 已安装的翻译器。必须持有引用 —— QTranslator 被回收后翻译会整体失效。
_translators: list[QTranslator] = []


def apply_locale(language: str) -> None:
    """把 Qt 默认 QLocale 设成配置里的 UI 语言。

    ⚠️ 必须在任何 QML 加载之前调用（RinUI 字体补丁依赖它）。
    """
    QLocale.setDefault(QLocale(language))
    log.info("默认 QLocale: %s", QLocale().name())


def install_translators(qt_app: QApplication, language: str) -> None:
    """装载 ``translations/luminalium_<language>.qm``（源语言则跳过）。"""
    if language in ("", SOURCE_LANGUAGE):
        return
    qm = TRANSLATIONS_DIR / f"luminalium_{language}.qm"
    if not qm.exists():
        if language in UNTRANSLATED:
            log.info("语言 %s 暂无翻译文件，界面保持中文原文", language)
        else:
            log.warning("翻译文件不存在: %s（界面保持中文原文）", qm)
        return
    translator = QTranslator(qt_app)
    if not translator.load(str(qm)):
        log.warning("翻译加载失败: %s（界面保持中文原文）", qm)
        return
    qt_app.installTranslator(translator)
    _translators.append(translator)
    log.info("已加载翻译: %s", qm.name)


def tr(context: str, source: str) -> str:
    """Python 侧可见文案的翻译查询；查不到就回原文。

    ``context`` 必须与 .ts 里的 ``<name>`` 一致（Python 侧目前用
    ``Splash`` / ``Tray`` / ``Overflow`` / ``App``，见
    ``translations/luminalium_py_*.ts``）。
    """
    for translator in _translators:
        hit = translator.translate(context, source)
        if hit:
            return hit
    return source


def apply_ui_font(qt_app: QApplication, language: str) -> None:
    """日语 UI 时把应用默认字体设成 Yu Gothic UI（其余语言跟随系统）。

    只影响没有显式指定字体的控件（按钮 / 菜单 / 托盘等）；``Rin.Text``
    与 ``Rin.TextField`` 的字体由 RinUI 补丁在 QML 侧解决。
    """
    if not language.startswith("ja"):
        return
    qt_app.setFont(QFont("Yu Gothic UI"))
    log.info("UI 字体: Yu Gothic UI（语言 %s）", language)
