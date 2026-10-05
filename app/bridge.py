"""QML 桥接层。

QML 只依赖这里暴露的属性与槽函数，不直接触碰配置、Win32 或 PowerPoint 细节。
新增功能时通常只需要：加一个 ``Slot`` + 在 QML 里连上按钮。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication

from . import autostart
from . import update_checker
from .config import Config
from .paths import RESOURCES_DIR, UI_DIR
from .ppt_controller import PresentationState

log = logging.getLogger(__name__)

#: 设置窗口里可改的项：QML 用的扁平键 -> 配置里的点号路径。
#: 加新开关时**只在这里加一行**，QML 侧用 ``Backend.settings.<扁平键>`` 读、
#: ``Backend.setSetting("<扁平键>", 值)`` 写。
SETTING_PATHS: Dict[str, str] = {
    "theme": "app.theme",
    "accent": "app.accent",
    "language": "app.language",
    "log_level": "app.log_level",
    # ⚠️ ``autostart`` 是**特例**：它的本体是 Windows 注册表（见 ``app/autostart.py``），
    #    配置里的 ``app.autostart`` 只是给日志 / 排查看的一份影子。读写两边都走
    #    注册表 —— ``_get_settings`` 每次回读真实状态，``setSetting`` 也单独分叉
    #    （见 :meth:`Backend._apply_autostart`），不走下面通用的「改内存 + 延迟落盘」。
    "autostart": "app.autostart",
    # ⚠️ ``tray.enabled`` / ``tray.tooltip`` / ``tray.show_on_click`` /
    #    ``tray.notify_on_start`` **没有**登记在这里，配置里的 ``tray`` 段也已删除：
    #    2026-10-01（第二轮）用户指令「托盘整组连着相关的逻辑和代码一块删掉」。
    #    现在托盘是**恒定行为**（常驻 + 提示文字取 app.name + 左键开面板 + 启动不弹
    #    气泡，见 ``application.py::_boot_tray/_boot_ready`` 与 ``TrayIcon``），
    #    没有可配置的路。
    # ⚠️ ``quick_panel.hide_on_deactivate`` 同理删除：失焦收起是**默认行为**
    #    （``windows.py::_on_panel_active_changed`` 恒定生效）。
    "panel_shortcuts_locked": "quick_panel.shortcuts_locked",
    "panel_section_shortcuts": "quick_panel.sections.shortcuts",
    "panel_section_footer": "quick_panel.sections.footer",
    "presentation_poll_interval_ms": "presentation.poll_interval_ms",
    "presentation_margin_x": "presentation.margin_x",
    "presentation_margin_y": "presentation.margin_y",
    "presentation_bar_height": "presentation.bar_height",
    # 控制条组件的整体缩放倍率（设置 → 主界面 → 「缩放大小」）。0.5~2.0 的**小数**
    # （滑块按整数百分比走，写回时再除 100）—— 见 default_config.json 的 ``presentation.scale``。
    "presentation_scale": "presentation.scale",
    "presentation_buttons_show_labels": "presentation.buttons.show_labels",
    "presentation_pager_position": "presentation.pager.position",
    "presentation_screen_index": "presentation.screen_index",
    "presentation_shadow_enabled": "presentation.surface.shadow.enabled",
    "presentation_surface_opacity": "presentation.surface.opacity",
    # ⚠️ ``presentation.divider.enabled`` / ``presentation.pager.enabled`` **没有**
    #    登记在这里：这两个开关 2026-10-01 按用户指令从界面上删除了（配置键仍
    #    生效、默认 true，只是改成纯配置项 —— 想关就在 config/config.json 里写）。
    #    登记进来的话 QML 侧会多一份没人读的代理属性，反而看不出它已经没有界面。
    "presentation_exit_style": "presentation.exit.style",
    # 只在调试窗口出现（隐藏入口：设置标题连点 10 次），普通用户看不到水印开关
    "dev_watermark": "app.dev_watermark",
    # 更新模式 / 更新通道（设置 → 更新 → 更新设置）。⚠️ ``update.`` 段里其余的键
    # （last_status / last_check_time）**没有**登记在这里：它们是程序自己写的
    # 检查记录，不给设置页当输入 —— 登记了反而会多出一组没人写的代理属性。
    "update_mode": "update.mode",
    "update_channel": "update.channel",
}

#: 值一变就需要 QML 重新取整块配置的键。
_BROADCAST_KEYS = {"panel_section_shortcuts", "panel_section_footer"}

#: 改完**必须重启才生效**的设置项（扁平键）。
#:
#: 改动这些项时走 :meth:`Backend._notify_restart_required`：① ``restartPending``
#: 翻 true → 设置窗口标题栏右侧亮出强调色「需要重启」按钮；② 发 ``restartSuggested``
#: → 设置窗口弹对话框问「现在重启吗」。
#:
#: 参考 ClassIsland（``ClassIsland/Views/SettingsWindowNew.axaml{,.cs}``）。那边是::
#:
#:     private void CommandBindingRestartApp_OnExecuted(...)
#:     {
#:         ViewModel.IsRequestedRestart = true;   // → 标题栏亮出「需要重启」按钮
#:         ShowRestartDialog();                   // → 弹框问「现在重启吗」
#:     }
#:
#: ⚠️ ClassIsland **自己并不会在设置变更时自动弹框** —— 它订阅了
#: ``SettingsService.Settings.PropertyChanged``，而 ``SettingsOnPropertyChanged``
#: 是**空方法**；也没有任何「哪些设置要重启」的清单或 ``[RequiresRestart]`` 标记。
#: 它只是把「需要重启」当成通用提示，靠用户自己去点标题栏那枚按钮。
#:
#: 所以这里做了两点适配：
#: ① 触发点从「用户点按钮」挪到 ``setSetting`` —— 用户的原话是「对需要重新启动
#:   才能应用的设置项**更改时**做出行动」，条件本来就是「某项设置变了」，
#:   由 QML 逐项去想起来发命令，迟早会有页面忘了发；
#: ② 清单由 Python 侧集中维护（就是下面这个 frozenset），而不是散在各页面里。
#:
#: **入选理由（``language``）**：翻译（``app/i18n.py::install_translators`` 装载
#: ``luminalium_*.qm``）与 UI 字体（``apply_ui_font``，``ja_JP`` 切 Yu Gothic UI）
#: 都在 ``application.py`` 里装配**一次**，之后没有任何重新装配的路径。
#:
#: ⚠️ **刻意没收 ``dev_watermark``**：它经 ``Backend.devWatermark``（``constant=True``）
#: 出给 QML，窗口构造时求值一次 → 改完确实是「老窗口不变、新窗口跟着变」的半吊子
#: 状态。但它只在隐藏的调试窗口里出现，每拨一次就弹一次框太吵（且重启与否都存在
#: 半生效的部分），所以留着不动，等真要给这个开关做热更新时再一起解决。
RESTART_REQUIRED_KEYS: frozenset = frozenset({
    "language",
})

#: 「翻页组件位置」的两种形态 -> 该形态下**启用**的角落。
#:
#: 改这一项会连带开关 ``corners`` 里对应的四个角：真实生效的仍是 ``corners``
#: （``windows.py::_load_docks`` 与编辑器预览都只读它），``pager.position``
#: 只是它的人话开关 —— 两种形态二选一，同时开会变成四个翻页栏。
PAGER_POSITION_CORNERS: Dict[str, tuple] = {
    "side": ("middle_left", "middle_right"),
    "bottom": ("bottom_left", "bottom_right"),
}


class Backend(QObject):
    """面向 QML 的应用后端。"""

    #: 设置项写盘的合并窗口（ms）。滑块拖动 / SpinBox 连点会连续改值，
    #: 这段窗口内的多次改动只落一次盘。
    _SAVE_DEBOUNCE_MS = 400

    # ---- 通知类信号 ----
    presentationActiveChanged = Signal()
    slideChanged = Signal()
    activeToolChanged = Signal()
    #: 墨迹颜色变了（QML 侧的笔选单靠它回显选中的那一格）
    penColorChanged = Signal()
    shortcutsChanged = Signal()
    presentationConfigChanged = Signal()
    presentationScreenChanged = Signal()
    quickPanelConfigChanged = Signal()
    settingsChanged = Signal()
    statusChanged = Signal()
    #: 启动画面的进度 / 阶段文字变了
    splashChanged = Signal()
    #: 检查更新的状态机动了（详见下方「检查更新」一节）。
    updateStatusChanged = Signal()
    updateWorkingChanged = Signal()

    # ---- 请求类信号（由窗口管理器 / 应用层响应）----
    panelHideRequested = Signal()
    shortcutTriggered = Signal(str)
    actionTriggered = Signal(str)
    #: 重启整个程序（快捷面板底栏的「重启」按钮）：由应用层拉起新进程后退出。
    #: 原 ``reloadRequested``（仅重读配置）已按 2026-10-02 用户指令改成重启 ——
    #: 用户语义里这个按钮就该是「重启程序」，只重读配置反而「点了没反应」。
    restartRequested = Signal()
    #: 改了一项「要重启才生效」的设置（见 ``RESTART_REQUIRED_KEYS``）→ 设置窗口
    #: 弹对话框问「现在重启吗」（ClassIsland 的 ``ShowRestartDialog()`` 同款）。
    #: ⚠️ 与 ``restartRequested`` 是两回事：那个是**真的去重启**，这个是**提示**。
    restartSuggested = Signal()
    #: ``restartPending`` 变了。
    restartPendingChanged = Signal()
    quitRequested = Signal()
    settingsRequested = Signal()
    settingsCloseRequested = Signal()
    #: 调试窗口（隐藏入口：设置窗口标题连点 10 次）
    debugWindowRequested = Signal()
    debugWindowCloseRequested = Signal()
    #: 主界面编辑器（入口：快捷面板的「主界面编辑器」快捷方式）
    editorRequested = Signal()
    editorCloseRequested = Signal()
    themeChangeRequested = Signal(str)
    accentChangeRequested = Signal(str)
    #: 启用 / 停用的角落集合变了（翻页组件位置切换）：控制条**换了一组组件**，
    #: 光挪位置不够，得按新的角落重建（``windows.py::rebuild_docks``）。
    docksRebuildRequested = Signal()

    def __init__(self, config: Config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config

        self._presentation_active = False
        self._slide_index = 0
        self._slide_total = 0
        #: 默认工具是**鼠标指针**（``arrow``）。
        #:
        #: ⚠️ 2026-10-01 用户指令「顶层窗口的工具栏的 Segmented 默认工具不应该
        #: 是鼠标指针吗？」—— 这里原本是 ``pen``，与配置里 ``presentation.tools``
        #: 的排布意图（``arrow`` 放第一个，见该段注释）自相矛盾：控制条一出来
        #: 就高亮着「笔」，用户得先点一下指针才能正常放映，等于默认把放映
        #: 变成书写。默认必须是「什么都不做」的那个工具。
        self._active_tool = "arrow"
        #: 墨迹颜色（``#RRGGBB``）。空串 = 还没有选过 —— QML 侧据此决定
        #: 哪一格点亮（见 :meth:`setPenColor`）。
        self._pen_color = ""
        self._status_text = ""

        #: 有没有「改了但要重启才生效」的设置（见 ``RESTART_REQUIRED_KEYS``）。
        #: 一旦翻 true 就**不再复位**（ClassIsland 的 ``IsRequestedRestart`` 同样只
        #: 置位）：用户把值改回原样也当作改过 —— 判断「有没有绕过」的成本远高于
        #: 多显示一个按钮，而重启一次本来也没有副作用。
        self._restart_pending = False

        #: 启动画面进度（0..1）与阶段文字。由应用层按真实里程碑推进
        #: （见 ``application.py::LuminaliumApplication._boot_*``）。
        self._splash_progress = 0.0
        self._splash_stage = ""

        #: 已启用的快捷方式 id（顺序即显示顺序）
        self._shortcut_ids: List[str] = [
            str(item) for item in (config.get("quick_panel.shortcuts", []) or [])
        ]

        #: ``WindowManager`` 推来的**真实**放映显示器几何（顶层窗口铺在哪块屏）。
        #: None 表示还没有放映过，此时 :meth:`_get_presentation_screen` 自己按
        #: 配置索引兜底。见 ``syncPresentationScreen``。
        self._overlay_screen: Optional[Dict[str, Any]] = None

        #: 设置项的**延迟落盘**（见 :meth:`setSetting`）。
        #:
        #: ``Config.set(persist=True)`` 会把整份用户配置重写一遍 —— 滑块拖一次
        #: 会发几十个 ``moved``，逐个落盘就是几十次磁盘写。这里改成「先改内存、
        #: 停手 ``_SAVE_DEBOUNCE_MS`` 之后再写一次」。进程正常退出时
        #: ``application.quit()`` 还会补一次 ``config.save()``，不会丢。
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(self._SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._config.save)

        #: 「关于」页两条**异步**链路的后台线程（取回声洞句子 / 采集诊断信息）。
        #: 只为「同一件事不并发第二次」而持有；线程本身是 daemon，退出即回收。
        self._echo_thread: Optional[threading.Thread] = None
        self._diagnostics_thread: Optional[threading.Thread] = None
        #: 检查更新的后台线程（同上，见 :meth:`requestCheckUpdate`）。
        self._update_thread: Optional[threading.Thread] = None

        # ------------------------------------------------ 检查更新的状态机
        #:
        #: 对齐 ClassIsland ``UpdateService`` 的两组状态：
        #:
        #: * ``_update_status`` —— 上次检查的结论，对应它的 ``UpdateStatus``：
        #:   ``uptodate`` / ``available``（+ 部署环节的 ``updatedownloaded`` /
        #:   ``updatedeployed``，部署未实现、预留）＋ 本项目自己的 ``unknown``
        #:   （本次运行还没查过）。ClassIsland 把它持久化在 Settings 里，
        #:   这里同样落 ``update.last_status``。
        #: * ``_update_working`` —— 正在干什么，对应 ``UpdateWorkingStatus``：
        #:   目前只有 ``idle`` / ``checking``（下载 ``downloading`` /
        #:   部署 ``extracting`` 随部署一起接入）。
        self._update_status = str(self._config.get("update.last_status", "")
                                  or update_checker.STATUS_UNKNOWN)
        self._update_working = "idle"
        self._update_latest_version = ""
        self._update_changelog = ""
        self._update_current_changelog = ""
        self._update_release_url = ""
        self._update_error = ""


    # ==================================================================== 常量

    @Property(str, constant=True)
    def appName(self) -> str:
        return str(self._config.get("app.name", "Luminalium 2"))

    @Property(str, constant=True)
    def appVersion(self) -> str:
        from . import __version__

        return __version__

    @Property(bool, notify=restartPendingChanged)
    def restartPending(self) -> bool:
        """有没有「改了但要重启才生效」的设置（见 ``RESTART_REQUIRED_KEYS``）。

        设置窗口靠它决定标题栏右侧那枚「需要重启」按钮显不显示
        （ClassIsland 的 ``ViewModel.IsRequestedRestart`` 同款）。
        """
        return self._restart_pending

    @Property(str, constant=True)
    def accent(self) -> str:
        return str(self._config.get("app.accent", "#4CC2FF"))

    @Property(str, constant=True)
    def uiDir(self) -> str:
        return str(UI_DIR)

    @Property(bool, constant=True)
    def devWatermark(self) -> bool:
        """开发中水印开关（``app.dev_watermark``）。

        给开发者看的开关：只在**调试窗口**里出现，而调试窗口本身没有可见入口
        （设置窗口标题连点 10 次，见 ``openDebugWindow``）。缺省开启。
        """
        return self._config.get("app.dev_watermark", True) is not False

    @Property(str, constant=True)
    def devCodename(self) -> str:
        return str(self._config.get("app.codename", "AwaSubaru"))

    @Property(str, constant=True)
    def appChannel(self) -> str:
        """发布渠道（``app.channel``）：设置页「关于」的徽章只显示 ``Dev`` /
        ``Release`` 这两档，正式包把配置改成 ``"Release"`` 即可。"""
        return str(self._config.get("app.channel", "Dev"))

    # ================================================================ 启动画面

    @Property(float, notify=splashChanged)
    def splashProgress(self) -> float:
        """启动进度，0..1。"""
        return self._splash_progress

    @Property(str, notify=splashChanged)
    def splashStage(self) -> str:
        """当前阶段的短说明（设计稿里是「创建托盘图标」那一类）。"""
        return self._splash_stage

    @Property(str, constant=True)
    def splashSubtitle(self) -> str:
        """版本行文案：``<版本号> // <开发代号>``（设计稿同款）。"""
        return f"{self.appVersion} // {self.devCodename}"

    @Slot(float, str)
    def setSplashStage(self, progress: float, stage: str) -> None:
        """推进启动画面（应用层每到一个真实里程碑调一次）。"""
        self._splash_progress = max(0.0, min(1.0, float(progress)))
        self._splash_stage = str(stage)
        self.splashChanged.emit()

    @Property(str, constant=True)
    def deviceId(self) -> str:
        """本机短 ID（水印第二行用）：主机名 + MAC 的 SHA1 前 8 位。

        只用于开发者分辨「这是哪台测试机」，不含任何可逆的个人信息。
        """
        import hashlib
        import platform
        import uuid

        raw = f"{platform.node()}|{uuid.getnode():x}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8].upper()

    @Slot(str, result=str)
    def resourceFile(self, name: str) -> str:
        """``resources/`` 下某个品牌资源（logo.svg / logo.ico / banner.png）的
        ``file:///`` URL。

        QML 的 ``Image.source`` 不吃相对路径（基准是 QML 文件所在目录），
        所以统一在这里拼绝对 URL。
        """
        return QUrl.fromLocalFile(str(RESOURCES_DIR / name)).toString()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        """把一段文本放进系统剪贴板（回声洞的「复制」与诊断的「复制全部」共用）。"""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(text))

    # ================================================================ 回声洞

    #: 取句结果：``(句子, 状态)``，状态 ∈ ``ok`` / ``empty``。
    #:
    #: 为什么是**信号**而不是 ``@Slot(result=str)``：取句可能要走一次本地
    #: HTTP（见 ``echo_cave.py``），在槽里同步等会把 UI 线程按住 —— 这正是
    #: L1 用 ``await fetch()`` 避免的事。改成后台线程取、取完发信号，界面
    #: 期间能正常画出「获取中...」。
    echoCaveResult = Signal(str, str)

    @Slot()
    def requestEchoCave(self) -> None:
        """请求一条回声洞句子（异步）。

        ⚠️ **重复点击直接忽略**：句子很短，一次取句通常几十毫秒就回来了；
        真放行并发请求的话，晚回来的那个会盖掉用户刚看到的那句（L1 用
        ``echoCaveAbort`` 取消前一次动画，这里更简单 —— 干脆不并发）。
        """
        if self._echo_thread is not None and self._echo_thread.is_alive():
            return
        self._echo_thread = threading.Thread(
            target=self._fetch_echo_cave, name="echo-cave", daemon=True
        )
        self._echo_thread.start()

    def _fetch_echo_cave(self) -> None:
        """后台线程体：取句 → 发信号（在 Qt 里跨线程发信号会被排队到主线程）。"""
        from .echo_cave import fetch_sentence

        try:
            sentence = fetch_sentence()
        except Exception:  # noqa: BLE001 - 取句失败不该把线程带崩
            log.exception("回声洞取句失败")
            sentence = ""
        self.echoCaveResult.emit(sentence, "ok" if sentence else "empty")

    # ================================================================ 诊断信息

    #: 诊断字段就绪：``QVariantList``，每项 ``{"key": ..., "value": ...}``。
    #:
    #: 同样走**信号**而不是同步返回：硬件查询里有 ``GlobalMemoryStatusEx``
    #: 与注册表遍历，虽然都不起子进程，但没有理由压在 UI 线程上；更重要的是
    #: 同步返回的话界面根本没机会画出「加载中...」——L1 那个加载态正是这么来的。
    diagnosticsReady = Signal("QVariantList")

    @Slot()
    def requestDiagnostics(self) -> None:
        """采集诊断信息（异步）。重复请求同样直接忽略。

        ⚠️ **活体字段在这里先取好再交给线程**：``QGuiApplication.primaryScreen()``
        不是线程安全的，不能在 worker 里调（见 :meth:`_live_diagnostic_fields`）。
        """
        if self._diagnostics_thread is not None and self._diagnostics_thread.is_alive():
            return
        extra = self._live_diagnostic_fields()
        self._diagnostics_thread = threading.Thread(
            target=self._collect_diagnostics, args=(extra,), name="diagnostics", daemon=True
        )
        self._diagnostics_thread.start()

    def _live_diagnostic_fields(self) -> Dict[str, str]:
        """只有活体对象才拿得到的字段（屏幕 / 放映状态 / 日志级别 / 版本号）。

        ⚠️ 必须在**主线程**调用：``QGuiApplication.primaryScreen()`` 不是线程安全的。

        键名照 ClassIsland 的诊断字段（``AppSubChannel`` 对应它的发布渠道），
        与 ``app/diagnostics.py::FIELD_ORDER`` 里的键一一对上。
        """
        screen = QGuiApplication.primaryScreen()
        screen_size = ""
        if screen is not None:
            geometry = screen.geometry()
            screen_size = f"{geometry.width()} × {geometry.height()}"

        presentation = "active" if self._presentation_active else "inactive"
        if self._presentation_active:
            presentation = f"active:{self._slide_index}/{self._slide_total}"

        return {
            "Screen": screen_size,
            "AppVersion": self.appVersion,
            "AppSubChannel": self.appChannel,
            "Presentation": presentation,
            "LogLevel": str(self._config.get("app.log_level", "INFO")),
        }

    def _collect_diagnostics(self, extra: Dict[str, str]) -> None:
        """后台线程体：采集 → 发信号（``extra`` 由主线程预先取好）。"""
        from .diagnostics import collect

        try:
            fields = [{"key": key, "value": value} for key, value in collect(extra)]
        except Exception:  # noqa: BLE001 - 采集失败也要给界面一个交代
            log.exception("诊断信息采集失败")
            fields = []
        self.diagnosticsReady.emit(fields)

    # ================================================================ 检查更新
    #:
    #: 界面是 ClassIsland 更新页的一比一复刻（``ui/settings/Update.qml``），
    #: 这组属性 / 槽就是那边 ViewModel + UpdateService 公开面拆出来的最小集。
    #: 与回声洞 / 诊断同一条异步约定：**网络在后台线程、结果走信号**，
    #: 界面期间能正常画出「正在检查更新…」。
    #:
    #: ⚠️ **下载 / 安装 / 部署刻意未实现**（2026-10-05 用户指令）：界面上
    #: 「下载并安装」等按钮先以占位方式出现，点了由 QML 侧亮提示条；
    #: 状态机里 ``updatedownloaded`` / ``updatedeployed`` 两档留给部署接入时。

    def _get_update_status(self) -> str:
        return self._update_status

    updateStatus = Property(str, _get_update_status, notify=updateStatusChanged)
    def _get_update_working(self) -> str:
        return self._update_working

    updateWorkingStatus = Property(str, _get_update_working, notify=updateWorkingChanged)

    def _get_update_latest_version(self) -> str:
        return self._update_latest_version

    updateLatestVersion = Property(
        str, _get_update_latest_version, notify=updateStatusChanged
    )

    def _get_update_changelog(self) -> str:
        return self._update_changelog

    updateChangelog = Property(str, _get_update_changelog, notify=updateStatusChanged)

    def _get_update_current_changelog(self) -> str:
        return self._update_current_changelog

    updateCurrentChangelog = Property(
        str, _get_update_current_changelog, notify=updateStatusChanged
    )

    def _get_update_release_url(self) -> str:
        return self._update_release_url

    updateReleaseUrl = Property(
        str, _get_update_release_url, notify=updateStatusChanged
    )

    def _get_update_error(self) -> str:
        return self._update_error

    updateError = Property(str, _get_update_error, notify=updateStatusChanged)

    def _get_update_last_check_time(self) -> str:
        """上次检查更新的本地时间（人读格式；从未查过返回空串）。"""
        text = str(self._config.get("update.last_check_time", "") or "")
        if not text:
            return ""
        try:
            return datetime.fromisoformat(text).strftime("%Y/%m/%d %H:%M")
        except ValueError:
            return text

    updateLastCheckTime = Property(
        str, _get_update_last_check_time, notify=updateStatusChanged
    )

    @Slot(bool)
    def requestCheckUpdate(self, force: bool = False) -> None:
        """检查更新（异步）。``force`` = 强制检查（见 ``update_checker.check``）。

        ⚠️ **检查期间再点直接忽略**：并发检查的两次结果互相覆盖没有意义，
        与回声洞 / 诊断「不并发」同一个理由。界面侧在检查中会把按钮藏起来，
        这里是兜底。
        """
        if self._update_thread is not None and self._update_thread.is_alive():
            return
        self._update_working = "checking"
        self.updateWorkingChanged.emit()
        self._update_thread = threading.Thread(
            target=self._run_update_check, args=(bool(force),), name="update-check",
            daemon=True,
        )
        self._update_thread.start()

    @Slot()
    def autoCheckUpdates(self) -> None:
        """按配置的更新模式自动检查一次（应用启动后由应用层调用）。

        对应 ClassIsland ``AppStartupBackground`` 的第一段：
        ``UpdateMode >= 1`` 就 ``CheckUpdateAsync()``。模式 2（自动下载）与
        3（自动安装）在部署接入之前与 1 等效 —— 只检查、只通知。
        """
        mode = int(self._config.get("update.mode", 1))
        if mode < 1:
            return
        if mode >= 2:
            log.info("更新模式为 %d：自动下载/安装尚未实现，本次仅检查并通知", mode)
        self.requestCheckUpdate(False)

    def _run_update_check(self, force: bool) -> None:
        """后台线程体：查 → 记录 → 发信号（排队回主线程）。"""
        result = update_checker.check(
            channel=str(self._config.get("update.channel", "stable")),
            current_version=self.appVersion,
            force=force,
        )
        self._update_status = result["status"]
        self._update_latest_version = result["latest_version"]
        self._update_changelog = result["changelog"]
        self._update_current_changelog = result["current_changelog"]
        self._update_release_url = result["release_url"]
        self._update_error = result["error"]
        # 检查记录持久化（ClassIsland 同样记 LastUpdateStatus /
        # LastCheckUpdateTime）：重启后设置页还能看到上一次的结论。
        # 这里一次检查只写一次盘，不值得套延迟落盘。
        self._config.set("update.last_status", self._update_status)
        self._config.set(
            "update.last_check_time", datetime.now().isoformat(timespec="minutes")
        )
        self._update_working = "idle"
        self.updateStatusChanged.emit()
        self.updateWorkingChanged.emit()

    @Slot()
    def clearUpdateError(self) -> None:
        """关掉错误 InfoBar（对应 ClassIsland 把 ``NetworkErrorException`` 置空）。"""
        if self._update_error:
            self._update_error = ""
            self.updateStatusChanged.emit()

    def _get_update_channels(self) -> list:
        """更新通道候选（``[{"id", "name", "description"}, ...]``）。

        ⚠️ 通道表**只有这一份**，就是 ``update_checker.CHANNELS`` —— 界面上的
        名称与说明直接由它派生，不在 QML 里另抄一份（否则两边文案迟早漂）。

        2026-10-05：这也顺手绕掉了一个跨语言坑。原先通道表是 QML 里的
        ``property var updateChannels: [...]``，经 ``Loader.setProperty``
        推给「更新设置」Tab；QML 的 ``var`` 属性期望 ``QJSValue``，直接塞
        JS ``Array`` 过去会被包成**空 QJSValue**，子项遍历 ``.length`` 得 0 →
        通道下拉空、说明行标题与描述双空（自检实测）。改成由 Python 侧发
        ``QVariantList``，QML 拿到的就是原生数组。
        """
        return [
            {
                "id": key,
                "name": update_checker.CHANNEL_NAMES.get(key, key),
                "description": desc,
            }
            for key, desc in update_checker.CHANNELS.items()
        ]

    updateChannels = Property("QVariantList", _get_update_channels, constant=True)

    # ================================================================ 放映状态

    def _get_presentation_active(self) -> bool:
        return self._presentation_active

    presentationActive = Property(
        bool, _get_presentation_active, notify=presentationActiveChanged
    )

    def _get_slide_index(self) -> int:
        return self._slide_index

    slideIndex = Property(int, _get_slide_index, notify=slideChanged)

    def _get_slide_total(self) -> int:
        return self._slide_total

    slideTotal = Property(int, _get_slide_total, notify=slideChanged)

    def _get_active_tool(self) -> str:
        return self._active_tool

    activeTool = Property(str, _get_active_tool, notify=activeToolChanged)

    def _get_pen_color(self) -> str:
        return self._pen_color

    #: 当前墨迹颜色（``#RRGGBB``，空串 = 还没选过）。
    #:
    #: ⚠️ 必须是 ``@Property`` 而不是 ``@Slot``：QML 侧把后端的 ``@Slot`` 当
    #: **属性**读**永远不报错**，拿到的是函数的形参个数（0）—— 症状是静默走
    #: 降级分支，这个坑本项目在 ``licenseText`` 上踩过一次。
    penColor = Property(str, _get_pen_color, notify=penColorChanged)

    def _get_status_text(self) -> str:
        return self._status_text

    statusText = Property(str, _get_status_text, notify=statusChanged)

    def apply_state(self, state: PresentationState) -> None:
        """由 :class:`PptController` 调用。"""
        if state.active != self._presentation_active:
            self._presentation_active = state.active
            self.presentationActiveChanged.emit()

        if (state.slide_index, state.slide_total) != (
            self._slide_index,
            self._slide_total,
        ):
            self._slide_index = state.slide_index
            self._slide_total = state.slide_total
            self.slideChanged.emit()

    def set_status_text(self, text: str) -> None:
        if text != self._status_text:
            self._status_text = text
            self.statusChanged.emit()

    # ================================================================== 配置块

    def _get_presentation_config(self) -> Dict[str, Any]:
        return self._config.get("presentation", {}) or {}

    presentationConfig = Property(
        "QVariantMap",
        _get_presentation_config,
        notify=presentationConfigChanged,
    )

    # ------------------------------------------------- 放映显示器几何（画布基准）

    def _get_presentation_screen(self) -> Dict[str, Any]:
        """放映所在显示器的**逻辑**几何 —— 主界面编辑器画布的坐标基准。

        优先用 :meth:`syncPresentationScreen` 推来的真实结果（放映窗口在哪块屏
        就报哪块）；还没放映过时退回「配置索引 → 主屏」，与
        ``windows.py::_presentation_screen`` 的兜底分支同源。

        ⚠️ 不能用 QML 的 ``Screen`` attached property 代替：那说的是**本窗口**
        所在显示器。双屏时编辑器在主屏、放映在副屏，画布比例会整个错掉。
        """
        if self._overlay_screen is not None:
            return dict(self._overlay_screen)
        try:
            screens = QGuiApplication.screens()
        except Exception:  # pragma: no cover - QApplication 尚未建好
            screens = []
        index = int(self._config.get("presentation.screen_index", -1))
        screen = screens[index] if 0 <= index < len(screens) else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:  # pragma: no cover - 极端情况（无显示器）
            return {"width": 1920, "height": 1080, "name": "",
                    "scale": 1.0, "source": "fallback"}
        geometry = screen.geometry()
        return {
            "width": geometry.width(),
            "height": geometry.height(),
            "name": screen.name(),
            "scale": float(screen.devicePixelRatio()),
            "source": "config",
        }

    presentationScreen = Property(
        "QVariantMap", _get_presentation_screen, notify=presentationScreenChanged
    )

    @Slot(int, int, str, float)
    def syncPresentationScreen(
        self, width: int, height: int, name: str, scale: float
    ) -> None:
        """由 ``WindowManager.show_docks()`` 调用：顶层窗口定位完，把真实屏幕推过来。

        顶层窗口铺在哪块屏是按**放映窗口的物理显示器**判定的（见
        ``windows.py::_presentation_screen``），Bridge 侧复现不了，所以只能推。
        """
        info = {
            "width": int(width),
            "height": int(height),
            "name": str(name),
            "scale": float(scale),
            "source": "overlay",
        }
        if info == self._overlay_screen:
            return
        self._overlay_screen = info
        self.presentationScreenChanged.emit()

    def _get_quick_panel_config(self) -> Dict[str, Any]:
        return self._config.get("quick_panel", {}) or {}

    quickPanelConfig = Property(
        "QVariantMap",
        _get_quick_panel_config,
        notify=quickPanelConfigChanged,
    )

    # ============================================================ 快捷方式清单

    def _catalog(self) -> List[Dict[str, Any]]:
        """全部可用的快捷方式（``shortcut_catalog``）。"""
        return list(self._config.get("quick_panel.shortcut_catalog", []) or [])

    def _resolve_shortcuts(self, ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """把 id 列表解析成目录里的完整条目；未知 id 直接丢弃。"""
        wanted = self._shortcut_ids if ids is None else ids
        by_id = {str(item.get("id")): item for item in self._catalog()}
        return [by_id[item_id] for item_id in wanted if item_id in by_id]

    def _get_shortcut_items(self) -> List[Dict[str, Any]]:
        return self._resolve_shortcuts()

    shortcutItems = Property(
        "QVariantList", _get_shortcut_items, notify=shortcutsChanged
    )

    def _get_available_shortcut_items(self) -> List[Dict[str, Any]]:
        enabled = set(self._shortcut_ids)
        return [item for item in self._catalog() if str(item.get("id")) not in enabled]

    availableShortcutItems = Property(
        "QVariantList", _get_available_shortcut_items, notify=shortcutsChanged
    )

    def _persist_shortcuts(self) -> None:
        self._config.set("quick_panel.shortcuts", list(self._shortcut_ids))
        self.shortcutsChanged.emit()

    @Slot(str, bool)
    def setShortcutEnabled(self, shortcut_id: str, enabled: bool) -> None:
        """快捷方式的启用开关；面板上的「添加 / 移除」都走这里。"""
        exists = any(str(item.get("id")) == shortcut_id for item in self._catalog())
        if not exists:
            log.info("未知快捷方式: %s", shortcut_id)
            return
        if enabled:
            if shortcut_id in self._shortcut_ids:
                return
            self._shortcut_ids.append(shortcut_id)
        else:
            if shortcut_id not in self._shortcut_ids:
                return
            self._shortcut_ids.remove(shortcut_id)
        self._persist_shortcuts()

    @Slot(str, int)
    def moveShortcut(self, shortcut_id: str, index: int) -> None:
        """把快捷方式拖到新位置（``index`` 来自网格的 visualIndex）。"""
        if shortcut_id not in self._shortcut_ids:
            return
        target = max(0, min(int(index), len(self._shortcut_ids) - 1))
        current = self._shortcut_ids.index(shortcut_id)
        if current == target:
            return
        self._shortcut_ids.pop(current)
        self._shortcut_ids.insert(target, shortcut_id)
        self._persist_shortcuts()

    # ================================================================== 设置

    def _get_settings(self) -> Dict[str, Any]:
        values = {key: self._config.get(path) for key, path in SETTING_PATHS.items()}
        # 「开机自启」的真相在**注册表**里，不在配置里：用户可能在「任务管理器 →
        # 启动」里禁用它，也可能手动删过那个注册表值 —— 配置里那份影子会骗人。
        # 所以每次都回读一次实际状态（注册表读取是微秒级的，代价可以忽略）。
        values["autostart"] = autostart.is_enabled()
        return values

    settings = Property("QVariantMap", _get_settings, notify=settingsChanged)

    def _get_settings_config(self) -> Dict[str, Any]:
        return self._config.get("settings", {}) or {}

    settingsConfig = Property(
        "QVariantMap", _get_settings_config, notify=settingsChanged
    )

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        """改一项设置。类型按默认值对齐，避免 QML 把 int 传成字符串。"""
        path = SETTING_PATHS.get(key)
        if path is None:
            log.info("未知设置项: %s", key)
            return

        # 开机自启：**本体是注册表**，单独走一条路。通用的「改内存 + 延迟落盘」
        # 会把「写注册表失败」这件事吞掉 —— 那正是「关了却没关掉」的来源。
        if key == "autostart":
            self._apply_autostart(bool(value))
            return

        current = self._config.get(path)
        if isinstance(current, bool):
            value = bool(value)
        elif isinstance(current, int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return
        elif isinstance(current, float):
            try:
                value = float(value)
            except (TypeError, ValueError):
                return

        if current == value:
            return
        # 只改内存 + 排一次延迟落盘（理由见 ``_save_timer`` 处的注释）。
        self._config.set(path, value, persist=False)
        self._save_timer.start()
        log.info("设置 %s = %r", path, value)

        # 翻页组件位置：连带开关四个角落（两种形态二选一，见常量处的说明）。
        # 真实生效的是 ``corners``，所以这一步不是「副作用」而是这个开关的本体。
        if key == "presentation_pager_position":
            self._apply_pager_position(str(value))
            self.docksRebuildRequested.emit()

        if key == "theme":
            self.themeChangeRequested.emit(str(value))
        elif key == "accent":
            self.accentChangeRequested.emit(str(value))
        if key in _BROADCAST_KEYS:
            self.quickPanelConfigChanged.emit()

        # 「改了要重启才生效」的项：亮出设置窗口那枚「需要重启」按钮，并弹一次
        # 询问框（见 ``RESTART_REQUIRED_KEYS`` 处的说明）。
        if key in RESTART_REQUIRED_KEYS:
            self._notify_restart_required(key)
        if key.startswith("presentation_"):
            self.presentationConfigChanged.emit()
            # 改 ``presentation_screen_index`` 会换一块显示器；还没放映过时
            # ``presentationScreen`` 是按配置现算的，得给它一个重取的理由。
            self.presentationScreenChanged.emit()
        self.settingsChanged.emit()

    def _notify_restart_required(self, key: str) -> None:
        """某项「改了要重启才生效」的设置刚被改动 → 亮按钮 + 弹询问框。

        参考 ClassIsland ``SettingsWindowNew.axaml.cs``：::

            private void CommandBindingRestartApp_OnExecuted(...)
            {
                ViewModel.IsRequestedRestart = true;
                ShowRestartDialog();
            }

        也就是「置位 + 立刻弹框」两件事。用户选「取消」后框关掉，但那枚
        「需要重启」按钮留着（``restartPending`` 不复位），随时可以再点。
        """
        log.info("设置 %s 需要重启才生效", key)
        if not self._restart_pending:
            self._restart_pending = True
            self.restartPendingChanged.emit()
        # ⚠️ 询问框**每次都弹**（哪怕 ``restartPending`` 早就是 true）：
        # 与 ClassIsland 一致 —— 用户刚改完就该被问一次，而不是只有第一次改才问。
        self.restartSuggested.emit()

    def _apply_pager_position(self, position: str) -> None:
        """把「翻页组件位置」落到 ``corners`` 那四个角的开关上。

        ``side`` → 启用 ``middle_left`` / ``middle_right``（竖版两侧中间）、
        关掉底部两只；``bottom`` → 反过来。

        ⚠️ 真实生效的是 ``corners``（``windows.py::_load_docks`` 与编辑器预览
        都只读它），``pager.position`` 只是它的人话开关 —— 两边必须一起改，
        否则「设置里选了横版、屏幕上还是竖版」。
        """
        enabled = PAGER_POSITION_CORNERS.get(position)
        if enabled is None:
            log.info("未知翻页组件位置: %s", position)
            return
        for corners in PAGER_POSITION_CORNERS.values():
            for corner in corners:
                self._config.set(
                    f"presentation.corners.{corner}.enabled", corner in enabled
                )

    def _apply_autostart(self, enabled: bool) -> None:
        """开关开机自启：写注册表 → **回读真实状态** → 同步影子配置 → 广播。

        ⚠️ 回读是关键，不是多余的稳妥：``set_enabled`` 返回成功只说明注册表调用
        没抛异常，不代表最终状态就是想要的（组策略 / 杀软可能半途拦下）。所以以
        ``is_enabled()`` 的回读结果为准 —— 真实状态与用户点的那个不一致时，写进
        影子配置的是**真实状态**，QML 侧的开关跟着弹回去，而不是停在用户点的那
        一格骗人。这就是「关闭也必须有效无误」的落点。
        """
        ok = autostart.set_enabled(enabled)
        actual = autostart.is_enabled()
        self._config.set("app.autostart", actual, persist=False)
        self._save_timer.start()
        if not ok or actual != enabled:
            log.warning("开机自启未能按预期设置：期望 %s，实际 %s", enabled, actual)
        self.settingsChanged.emit()

    @Slot()
    def refreshSettings(self) -> None:
        """让 QML 重新取一遍 ``settings``（``settings`` 里含实时状态，如注册表）。

        入口是 ``windows.py::show_settings`` —— 每次打开设置窗口都刷一次，这样
        「在任务管理器里禁用了开机自启、再打开设置」看到的就是关着的那一格。
        """
        self.settingsChanged.emit()

    @Slot()
    def closeSettings(self) -> None:
        self.settingsCloseRequested.emit()

    @Slot()
    def openDebugWindow(self) -> None:
        """打开调试窗口。

        入口是**隐藏**的：在设置窗口左上角的标题文本上连点 10 次
        （``Settings.qml`` 的 ``debugTitleHotspot``）。调试项不再占用
        设置导航栏的位置。
        """
        self.debugWindowRequested.emit()

    @Slot()
    def closeDebugWindow(self) -> None:
        self.debugWindowCloseRequested.emit()

    @Slot()
    def openMainEditor(self) -> None:
        """打开主界面编辑器窗口。

        与调试窗口不同，这个是**正经入口**：快捷面板的「主界面编辑器」快捷方式
        （``shortcut_catalog`` 里 ``action: "open_editor"``）会派发到这里。
        """
        self.editorRequested.emit()

    @Slot()
    def closeMainEditor(self) -> None:
        self.editorCloseRequested.emit()

    def reload_from_config(self) -> None:
        self._shortcut_ids = [
            str(item) for item in (self._config.get("quick_panel.shortcuts", []) or [])
        ]
        self.shortcutsChanged.emit()
        self.settingsChanged.emit()
        self.presentationConfigChanged.emit()
        self.presentationScreenChanged.emit()
        self.quickPanelConfigChanged.emit()

    # ============================================================ 放映控制槽

    @Slot(str)
    def selectTool(self, tool: str) -> None:
        """切换放映指针：``pen`` / ``eraser`` / ``arrow``。"""
        if tool not in ("pen", "eraser", "arrow"):
            return
        if tool != self._active_tool:
            self._active_tool = tool
            self.activeToolChanged.emit()
        self.actionTriggered.emit(f"tool:{tool}")

    @Slot(str)
    def setPenColor(self, color: str) -> None:
        """选墨迹颜色（笔选单里点一格）。

        ``color`` 是 ``#RRGGBB``（可带 alpha，``#AARRGGBB`` 也认，取后六位）。
        先落进本对象（QML 靠它回显选中格），再经 ``actionTriggered`` 交给
        应用层调 PowerPoint 的 ``View.PointerColor``。

        ⚠️ 非法串**直接丢弃**且不改状态：选单里的格子全来自配置，正常不会
        走到这儿，但这里是 QML 能直接调到的公开槽，别让它把 ``penColor``
        写成半截的垃圾值（回显会跟着错）。
        """
        value = str(color or "").strip().lstrip("#").upper()
        if len(value) == 8:  # #AARRGGBB → 取 RGB
            value = value[2:]
        if len(value) != 6 or any(c not in "0123456789ABCDEF" for c in value):
            log.warning("忽略非法的墨迹颜色: %r", color)
            return
        hex_color = "#" + value
        if hex_color != self._pen_color:
            self._pen_color = hex_color
            self.penColorChanged.emit()
        self.actionTriggered.emit(f"pen_color:{hex_color}")

    @Slot(str)
    def triggerAction(self, action_id: str) -> None:
        """面板上的通用动作（清屏等），由应用层分发到 PowerPoint 控制器。"""
        self.actionTriggered.emit(action_id)

    @Slot()
    def nextSlide(self) -> None:
        self.actionTriggered.emit("pager:next")

    @Slot()
    def previousSlide(self) -> None:
        self.actionTriggered.emit("pager:previous")

    @Slot(int)
    def gotoSlide(self, page: int) -> None:
        """跳到指定页（控制条上「点页码展开快速切页面板」里点了一格）。

        ``page`` 是 **1-based** 的页码 —— 与 ``slideIndex`` 同一个口径，
        PowerPoint 的 ``View.GotoSlide`` 本来就是 1-based，中间不要再换算一次。

        这里只挡掉 ``< 1``：面板里的格子全是从 ``slideTotal`` 铺出来的，正常
        不会越界，但这是 QML 能直接调到的公开槽，一个手滑的 0 会让 COM 那侧
        抛异常（越界上限交给 COM 自己判 —— 它失败也只是这一次跳页不生效，
        不会伤到别的状态）。"""
        try:
            target = int(page)
        except (TypeError, ValueError):
            log.warning("忽略非法的跳转页码: %r", page)
            return
        if target < 1:
            log.warning("忽略越界的跳转页码: %r", page)
            return
        self.actionTriggered.emit(f"pager:goto:{target}")

    @Slot()
    def exitPresentation(self) -> None:
        self.actionTriggered.emit("exit_presentation")

    # ================================================================ 面板交互

    @Slot(str, result=bool)
    def activateShortcut(self, shortcut_id: str) -> bool:
        """触发快捷方式。

        返回是否被受理 —— 面板用它决定要不要顺手收起（CW2 的
        ``executeShortcut`` 也是这个约定）。
        """
        known = any(str(item.get("id")) == shortcut_id for item in self._catalog())
        if not known:
            log.info("未注册的快捷方式: %s", shortcut_id)
            return False
        self.shortcutTriggered.emit(shortcut_id)
        return True

    @Slot()
    def requestSettings(self) -> None:
        self.settingsRequested.emit()

    @Slot()
    def requestRestart(self) -> None:
        self.restartRequested.emit()

    @Slot()
    def requestQuit(self) -> None:
        self.quitRequested.emit()

    @Slot()
    def hidePanel(self) -> None:
        self.panelHideRequested.emit()

    # ------------------------------------------------------------------ 工具
