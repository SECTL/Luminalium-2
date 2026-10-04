"""错误处理：**崩溃报告** 与 **错误报告**。

两档报告共用同一张窗口（``ui/ErrorReport/ErrorReportWindow.qml``），只有文案 /
表情 / 主按钮不同 —— 由 :attr:`ErrorHandler.isCrash` 决定：

    · **崩溃报告**（``crash``）—— 不可继续的致命错误（未捕获异常）。主按钮
      「重新启动」，副标题「Luminalium 遇到了一个不可让程序再继续运行下去的
      问题。」；
    · **错误报告**（``error``）—— 可继续的非致命错误。主按钮「忽略」，副标题
      「Luminalium 遇到了一个问题。虽然你可以继续运行程序，但是最好反馈一下
      为好。」。

两档展开菜单都是同一套：**退出程序 / 重新启动 / 忽略**。

## 钩子装在哪

* :data:`sys.excepthook` —— **主线程**的未捕获异常。PySide6 对「槽函数里抛出的
  异常」的处理是打印 traceback 之后**继续跑**（不 abort），所以这条路径拿到的是
  「事件循环还活着」的崩溃 —— 报告窗正是在这个前提下才有意义（用户能点）。
* :data:`threading.excepthook` —— **后台线程**的未捕获异常（回声洞取句线程、
  放映探测线程…）。同样记一份崩溃报告，但**不**抢窗口：后台线程常常只是某个
  功能坏了，把它升级成「程序崩溃了！」会吓人。这里按**错误报告**处理。

⚠️ 真正**在事件循环之前**挂掉的（导入期 / 建窗口期）走不到这里 —— 那时 Qt 还没
起来，弹不出任何窗口。那一段由 ``main.py`` 的 ``_crash.log`` 兜底。

## 为什么窗口请求要延后一拍

主线程的 excepthook 是在「某个槽正在执行」的栈里被调用的，此时同步去
``QQmlComponent.create()`` 建窗口属于在异常处理里做重活 —— 一旦它自己也抛，
就变成异常套异常。所以 :meth:`_request_window` 在主线程上用
``QTimer.singleShot(0, ...)`` 把「请窗口管理器弹窗」推回事件循环的下一拍；
后台线程则直接发信号（跨线程会自动排队到主线程执行）。
"""

from __future__ import annotations

import logging
import platform
import sys
import threading
import traceback
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QObject,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QGuiApplication

from .i18n import tr
from .paths import RESOURCES_DIR

log = logging.getLogger("luminalium")


def _t(source: str) -> str:
    """Python 侧文案翻译（context 固定为 ``ErrorHandler``）。

    词条在 ``translations/luminalium_py_<lang>.ts`` 里**手工维护**（与
    Splash / Tray / Overflow / App 同一套约定），查不到就回中文原文 ——
    所以 zh_CN 下看到的就是下面这些字面量本身。
    """
    return tr("ErrorHandler", source)

#: 资源目录里的两张表情图（用户素材：``resources/``）
EMOJI_CRASH = "crash_handler_emoji_crashed.png"
EMOJI_ERROR = "crash_handler_emoji_error.png"

#: 「提交 Issue」打开的地址（本仓库的 new issue 页，正文/标题预填）
ISSUE_REPO_URL = "https://github.com/SECTL/Luminalium-2/issues/new"

#: 报告种类
KIND_CRASH = "crash"
KIND_ERROR = "error"

#: 预填进 issue URL 的正文上限（URL 不是拿来传大文件的地方，超长的部分砍掉，
#: 完整正文仍在「复制」那一份里）
_ISSUE_BODY_LIMIT = 6000


class ErrorHandler(QObject):
    """错误 / 崩溃报告的采集与呈现（QML 侧作为 ``ErrorHandler`` 上下文属性）。"""

    #: 报告数据变了 —— QML 重读下面那批只读属性
    reportChanged = Signal()
    #: 请求显示报告窗口（应用层连到 ``WindowManager.show_error_report``）
    reportRequested = Signal()
    #: 「忽略」—— 收起报告窗口，程序继续跑
    dismissRequested = Signal()
    #: 「重新启动」—— 应用层拉起新进程后退出
    restartRequested = Signal()
    #: 「退出程序」
    quitRequested = Signal()

    def __init__(self, config: Optional[Any] = None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config

        self._kind = KIND_ERROR
        self._summary = ""
        self._traceback = ""
        self._timestamp = ""
        self._source = ""
        self._has_report = False

    # ================================================================ 安装钩子

    def install(self) -> None:
        """接管主线程与后台线程的未捕获异常。

        ``sys.excepthook`` 会被**整体替换** —— 应用层不要再另装一个，需要额外
        处理的话在本类的 ``_excepthook`` 里加分支。
        """
        sys.excepthook = self._excepthook
        threading.excepthook = self._thread_excepthook
        log.info("错误处理器已安装（sys.excepthook / threading.excepthook）")

    def _excepthook(self, exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            # Ctrl+C 不是崩溃，交回默认处理（打断事件循环）
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        self.report_exception(exc_type, exc_value, exc_tb, fatal=True,
                              source=_t("主线程"))

    def _thread_excepthook(self, args) -> None:
        if issubclass(args.exc_type, SystemExit):
            return
        name = getattr(getattr(args, "thread", None), "name", "") or _t("后台线程")
        # 后台线程的异常按**错误报告**记（见模块头：它多半只是某个功能坏了，
        # 不该按「程序崩溃了」吓用户）
        self.report_exception(
            args.exc_type, args.exc_value, args.exc_traceback, fatal=False,
            source=_t("线程 {name}").format(name=name),
        )

    # ================================================================ 采集

    def report_exception(
        self,
        exc_type,
        exc_value,
        exc_tb,
        *,
        fatal: bool = True,
        source: str = "",
    ) -> None:
        """把一次异常记成报告（``fatal=True`` → 崩溃报告）。"""
        try:
            text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        except Exception:  # pragma: no cover - 格式化本身出问题就别再炸一次
            text = f"{exc_type!r}: {exc_value!r}"
        summary = f"{getattr(exc_type, '__name__', 'Exception')}: {exc_value}"
        self._capture(
            kind=KIND_CRASH if fatal else KIND_ERROR,
            summary=summary,
            traceback_text=text,
            source=source,
        )

    @Slot(str, str)
    def reportError(self, summary: str, details: str = "") -> None:
        """手动上报一条**非致命**错误（QML / 其它模块都可用）。"""
        self._capture(
            kind=KIND_ERROR,
            summary=str(summary),
            traceback_text=str(details) or str(summary),
            source="",
        )

    def _capture(self, *, kind: str, summary: str, traceback_text: str, source: str = "") -> None:
        self._kind = KIND_CRASH if kind == KIND_CRASH else KIND_ERROR
        self._summary = summary
        self._traceback = traceback_text
        self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._source = source
        self._has_report = True

        level = logging.CRITICAL if self._kind == KIND_CRASH else logging.ERROR
        log.log(
            level,
            "捕获%s：%s%s",
            "崩溃" if self._kind == KIND_CRASH else "错误",
            summary,
            f"（{source}）" if source else "",
        )
        self.reportChanged.emit()
        self._request_window()

    def _request_window(self) -> None:
        """请求弹出报告窗（主线程延后一拍，见模块头）。"""
        app = QCoreApplication.instance()
        if app is not None and threading.current_thread() is threading.main_thread():
            QTimer.singleShot(0, self.reportRequested.emit)
        else:
            # 后台线程：信号会自动排队到主线程的接收者
            self.reportRequested.emit()

    # ================================================================ 只读属性

    @Property(bool, notify=reportChanged)
    def hasReport(self) -> bool:
        """是否已经采集到一份报告（窗口没内容时不必显示）。"""
        return self._has_report

    @Property(bool, notify=reportChanged)
    def isCrash(self) -> bool:
        """本次是崩溃报告（``True``）还是错误报告（``False``）。"""
        return self._kind == KIND_CRASH

    @Property(str, notify=reportChanged)
    def windowTitle(self) -> str:
        kind = _t("崩溃报告") if self.isCrash else _t("错误报告")
        return f"{self._app_name} {kind}"

    @Property(str, notify=reportChanged)
    def heading(self) -> str:
        return _t("程序崩溃了！") if self.isCrash else _t("程序出现了一个错误！")

    @Property(str, notify=reportChanged)
    def subtitle(self) -> str:
        """正文说明。

        照 Class Widgets 2 的 ``ProblemReport.qml`` 那种写法：**先说清发生了什么，
        再给出下一步**（CW2 是「很抱歉…你的数据已自动保存…可以尝试重启」）。
        ⚠️ 别写我们做不到保证的话 —— CW2 那句「数据已自动保存」是它真有自动保存
        才敢写；这里只说「可以做什么」，不替程序打包票。
        """
        if self.isCrash:
            return _t(
                "{app_name} 遇到了一个自己无法恢复的问题，不得不停下来。"
                "你可以尝试重新启动；如果它反复出现，请把下面的详细信息反馈给我们。"
            ).format(app_name=self._app_name)
        return _t(
            "{app_name} 遇到了一个问题。程序还可以继续运行，"
            "但最好把下面的详细信息反馈给我们，方便我们修掉它。"
        ).format(app_name=self._app_name)

    # ------------------------------------------------ 环境信息（详情面板的网格）
    # 2026-10-05 照 Class Widgets 2 的「运行环境」田字格做的：四格带图标，
    # 让用户不用读堆栈也能一眼报出「什么系统 / 什么版本 / 什么时候 / 从哪来」。
    # 之前这些只躺在 ``reportBody`` 的文本里，界面上看不见。

    @Property(str, notify=reportChanged)
    def osName(self) -> str:
        return f"{platform.system()} {platform.version()}".strip() or _t("未知")

    @Property(str, notify=reportChanged)
    def appVersion(self) -> str:
        return self._app_version

    @Property(str, notify=reportChanged)
    def timestampText(self) -> str:
        return self._timestamp or _t("未知")

    @Property(str, notify=reportChanged)
    def sourceText(self) -> str:
        """异常来源（后台线程名 / 空 = 主线程）。"""
        return self._source or _t("未知")

    @Property(str, notify=reportChanged)
    def emojiSource(self) -> str:
        name = EMOJI_CRASH if self.isCrash else EMOJI_ERROR
        return QUrl.fromLocalFile(str(RESOURCES_DIR / name)).toString()

    @Property(str, notify=reportChanged)
    def tracebackText(self) -> str:
        return self._traceback

    @Property(str, notify=reportChanged)
    def primaryAction(self) -> str:
        """主按钮对应的动作 id：崩溃 = ``restart``，错误 = ``ignore``。"""
        return "restart" if self.isCrash else "ignore"

    @Property(str, notify=reportChanged)
    def reportBody(self) -> str:
        """「复制」/「提交 Issue」用的完整正文（环境信息 + 摘要 + 堆栈）。"""
        lines = [
            f"## {_t('环境信息')}",
            f"- {_t('应用版本')}: {self._app_version}",
            f"- {_t('报告类型')}: {_t('崩溃报告') if self.isCrash else _t('错误报告')}",
            f"- {_t('发生时间')}: {self._timestamp or _t('未知')}",
            f"- {_t('来源')}: {self._source or _t('未知')}",
            f"- {_t('操作系统')}: {platform.platform()}",
            f"- Python: {platform.python_version()}",
            "",
            f"## {_t('摘要')}",
            self._summary or _t("(无)"),
            "",
            f"## {_t('堆栈')}",
            "```",
            self._traceback.rstrip("\n"),
            "```",
            "",
        ]
        return "\n".join(lines)

    @Property(str, notify=reportChanged)
    def issueUrl(self) -> str:
        """预填标题 / 正文的 GitHub new-issue 地址。"""
        label = _t("崩溃报告") if self.isCrash else _t("错误报告")
        title = f"[{label}] {self._summary}"[:120]
        body = self.reportBody[:_ISSUE_BODY_LIMIT]
        return f"{ISSUE_REPO_URL}?title={quote(title)}&body={quote(body)}"

    # ================================================================ 动作

    @Slot()
    def submitIssue(self) -> None:
        """在系统浏览器里打开预填好的 new issue 页。"""
        url = QUrl(self.issueUrl)
        if not QDesktopServices.openUrl(url):
            log.warning("打开 Issue 页面失败: %s", url.toString())

    @Slot()
    def copyReport(self) -> None:
        """把完整报告正文放进剪贴板。"""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.reportBody)

    @Slot(str)
    def runAction(self, action: str) -> None:
        """分发报告窗上的动作：``quit`` / ``restart`` / 其它（= 忽略）。"""
        action = str(action)
        if action == "quit":
            self.quitRequested.emit()
        elif action == "restart":
            self.restartRequested.emit()
        else:
            self.dismissRequested.emit()

    @Slot()
    def dismiss(self) -> None:
        """「忽略」（也用于标题栏关闭按钮）。"""
        self.dismissRequested.emit()

    # ============================================================ 调试入口

    @Slot()
    def simulateError(self) -> None:
        """调试窗口的「手动报错」：弹一张**非致命**的错误报告。

        内容是编的（程序并没有真的出错），用途是核对错误报告窗的版式、表情图
        与主按钮（「忽略」）。
        """
        self.reportError(
            _t("RuntimeError: 这是一条手动触发的错误报告"),
            _t("这条报告来自调试窗口的「手动报错」，程序本身并没有出错。\n"
               "用途：核对错误报告窗的版式、表情图与主按钮（忽略）。"),
        )

    @Slot()
    def simulateCrash(self) -> None:
        """调试窗口的「手动崩溃」：制造一次**真实的**未捕获异常。

        走的是完整链路 —— 与真崩溃同一条：``sys.excepthook`` → 记报告 →
        弹崩溃报告窗。所以这条路径顺带把「钩子装没装、装得对不对」也验掉了。

        ⚠️ 异常**不真的抛出去**：本槽是 QML 调过来的，抛出去要穿过 QML 引擎的
        调用栈（PySide6 自己能兜住，但没必要冒这个险）。改成把 ``sys.exc_info()``
        直接交给 ``sys.excepthook`` —— 与 PySide6 在槽里捕获到未处理异常之后的
        动作**逐字一致**（实测 PySide6 6.11：打印 traceback → 调 excepthook →
        继续跑）。
        """
        try:
            raise RuntimeError("手动触发的崩溃（来自调试窗口）")
        except RuntimeError:
            if getattr(sys.excepthook, "__self__", None) is self:
                sys.excepthook(*sys.exc_info())
            else:
                # 钩子没装上（例如在预览工具里跑）：直接出报告，别让按钮点了没反应
                self.report_exception(*sys.exc_info(), fatal=True, source="调试窗口")

    # ================================================================ 内部

    @property
    def _app_name(self) -> str:
        if self._config is not None:
            try:
                return str(self._config.get("app.name", "Luminalium 2"))
            except Exception:  # pragma: no cover - 配置未就绪
                pass
        return "Luminalium 2"

    @property
    def _app_version(self) -> str:
        try:
            from . import __version__

            return __version__
        except Exception:  # pragma: no cover
            return "unknown"
