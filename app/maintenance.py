"""维护模式（2026-11-22 用户指令：「按照 ClassIsland 制作此程序的维护模式窗口，
本程序没有的功能不要做」）。

## 它是什么

ClassIsland 的「恢复」窗口（``Views/RecoveryWindow.axaml`` +
``Views/RecoveryPages/HomePage.axaml``）在**主程序起不来 / 配置被改坏**时提供
一条自救通道：不加载插件与主界面，只开一张 450×600 的小窗，列出「继续使用
（正常 / 安全 / 诊断）」「打开日志目录」「清理与重置」这几组操作。

本文件是那条通道的**装配**。窗口本体在 ``ui/MaintenanceWindow.qml``，
按钮落到 ``Backend`` 的维护槽（文件操作也在桥里，见 ``app/bridge.py``）。

## 为什么是独立装配、而不是主装配的一个开关

* 主装配（``LuminaliumApplication``）从第一行起就假定「本次要拉起托盘、
  放映探测、控制条、插件」；建到一半再回头拆，比单开一条路更容易漏。
* 维护模式要能**在主路径坏掉时仍进得去**：所以它不 ``import application``，
  公共的日志 / RinUI 外观在 ``app/startup.py``（那边只依赖 logging / RinUI /
  paths）。这条约束比「少写几行代码」重要 —— 加依赖前先想清楚。
* 但它**仍然走** ``WindowManager.register_window``：懒创建、RinUI 三清单接管、
  失败 frameless 兜底、定位、显隐这一整套是铁律（见 ``app/windows.py`` 头注释），
  维护窗口没有理由自建一条。为此 ``WindowManager`` 允许 ``ppt=None`` ——
  构造函数只把它存着，维护模式永远不调 ``load_windows`` / ``show_docks``。

## 不做什么（用户明令：本程序没有的功能不要做）

ClassIsland 那张窗里还有「恢复备份」「回滚到之前的版本」「重置全部配置（档案 /
组件 / 自动化）」「重置全部信息（含课表档案）」—— L2 **没有**备份机制、没有
版本管理器、没有档案与组件，这些一律不做，别照着抄一个空壳按钮。

对应到本程序的「重置」只有三层真实存在的东西：

* 设置 = ``config/config.json``（用户差分，默认值在 ``default_config.json``）；
* 续播记忆 = ``page_memory.json``；
* 外部插件 = 数据根下的 ``plugins/``（内建插件在包里，删不到也不该删）；
* 运行期缓存 = ``cache/``（缩略图等，可随时删）。
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow

from . import __version__, i18n, launch, multi_instance, rinui_patch
from .bridge import Backend
from .config import Config
from .paths import APP_NAME, UI_DIR, ensure_runtime_dirs
from .startup import apply_backdrop_effect, configure_rinui, setup_logging
from .tray import build_app_icon
from .windows import WindowManager

log = logging.getLogger("luminalium")

#: 窗口在 ``WindowManager._registered_windows`` 里的名字（也是日志里的称呼）
WINDOW_NAME = "maintenance"


class MaintenanceApplication:
    """维护模式的精简装配：一张窗、一个 Backend，别的什么都没有。"""

    def __init__(self, argv: list[str]) -> None:
        # 维护模式不注入插件默认值（``extra_defaults``）：它不加载插件，
        # 默认层多出来的那部分只会让「重置后配置长什么样」更难推理。
        self.config = Config()
        setup_logging(str(self.config.get("app.log_level", "INFO")))
        log.info("Luminalium 2 v%s 启动（维护模式）", __version__)

        # 本进程是 ``launch.relaunch`` 拉起来的，环境里留着「重启交接」标记。
        # 这里**读掉它**（顺带得到一个日志线索），同时**跳过**多实例检测：
        # 维护模式本来就是排障通道，再弹一层「你多开了」只会把用户挡在门外。
        restart, restart_pid = multi_instance.consume_restart_request()
        if restart:
            log.info("维护模式由重启拉起（旧进程 PID=%s）", restart_pid)

        ensure_runtime_dirs()
        self.qt_app = QApplication(argv)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationDisplayName(str(self.config.get("app.name", APP_NAME)))
        # 关闭窗口走 QML 的 ``onClosing`` → ``Backend.quitMaintenance``，
        # 不靠 lastWindowClosed（对话框 / 菜单弹出时它也会跟着计数）。
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setWindowIcon(build_app_icon())

        # i18n / 字体：时序与主装配一致（必须在任何 QML 加载之前）。
        language = str(self.config.get("app.language", i18n.SOURCE_LANGUAGE))
        i18n.apply_locale(language)
        i18n.install_translators(self.qt_app, language)
        i18n.apply_ui_font(self.qt_app, language)
        rinui_patch.apply()

        # 维护窗口不做墨迹，但 QML 侧 ``import Luminalium``（设计令牌单例）
        # 会带上 AuroraFlow / GlassLogo 一类组件 —— 它们不碰 Ink 类型，
        # 所以这里**不需要** ``register_qml_types``。

        self.backend = Backend(self.config, self.qt_app)

        self.rinui = RinUIWindow()
        # RinUI 的 Win32 接管组件（WinEventFilter）只在 ``load()`` 里创建。维护
        # 模式不 load 任何根 QML（不建快捷面板），但自管窗口仍然需要它才能拿到
        # DWM 阴影 / 圆角 / resize 边框 / Snap —— 否则 ``_attach_to_rinui`` 第一
        # 行就撞 ``NoneType.windows``。按同一入口补一次，窗口名单先置空表。
        self.rinui.windows = []
        configure_rinui(self.rinui, self.config)
        self.rinui._window_handle_setup()
        self.rinui.engine.rootContext().setContextProperty("Backend", self.backend)
        # 维护模式没有 ``load()``（不建快捷面板），材质值先记进 RinUI，
        # 等窗口被接管时 ``_attach_to_rinui`` 会重放它。
        apply_backdrop_effect(self.rinui, self.config)

        # ppt=None：本装配永不调 load_windows / show_docks（见模块头注释）。
        self.windows = WindowManager(
            self.rinui.engine,
            self.config,
            self.backend,
            None,
            tray=None,
            rinui=self.rinui,
        )
        self._handle = self.windows.register_window(
            WINDOW_NAME,
            UI_DIR / "MaintenanceWindow.qml",
            label="维护模式窗口",
        )

        self.backend.maintenanceRestartRequested.connect(self._relaunch_normal)
        self.backend.maintenanceQuitRequested.connect(self.quit)

        self._handle.show()

    # ------------------------------------------------------------------ 动作

    def _relaunch_normal(self, safe: bool, diagnostic: bool) -> None:
        """「继续使用」：拉一个**正常**进程，再退出自己。

        失败就把窗口留着（用户还能去「打开日志目录」看看怎么回事），
        而不是把维护模式一起关掉 —— 那样用户手里就什么都不剩了。
        """
        extra = []
        if safe:
            extra.append(launch.SAFE_FLAG)
        if diagnostic:
            extra.append(launch.DIAGNOSTIC_FLAG)
        log.info("退出维护模式并正常启动%s", f"（{' '.join(extra)}）" if extra else "")
        if not launch.relaunch(extra):
            return
        self.quit()

    def quit(self) -> None:
        """退出维护模式。

        ⚠️ **绝不** ``config.save()``。维护模式里刚做过的「重置应用设置」删掉了
        ``config.json``，而本进程的 ``Config._data`` 还是**重置前**读进来的那一份；
        收尾时存一次盘等于把用户刚清掉的配置原样写回去 —— 静默失效，日志里连
        个响都没有（``_diff`` 只会如实算出「用户层比默认层多了这些键」）。
        """
        log.info("退出维护模式")
        self.windows.shutdown()
        self.qt_app.quit()

    def run(self) -> int:
        return self.qt_app.exec()


def run_maintenance(argv: Optional[list[str]] = None) -> int:
    """入口（``application.main`` 在参数命中 ``--maintenance`` 时调它）。"""
    app = MaintenanceApplication(list(argv or []))
    return app.run()
