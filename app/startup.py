"""正常启动与维护模式**共用**的那一小段装配：日志、RinUI 外观。

2026-11-22 从 ``application.py`` 抽出。动机不是「文件太长了」，而是
**维护模式不能依赖正常装配**：维护模式存在的意义就是「主路径起不来时仍能
进去修」，如果它 ``import application`` 才能拿到 ``setup_logging``，那主路径
里任何一个导入错误都会把自救通道一起带走。所以这里只留最轻的依赖
（logging / RinUI / paths），两套装配各自导入它。

⚠️ 新增内容前先问一句：维护模式真的需要它吗？需要才放这里。
"""

from __future__ import annotations

import logging
import logging.handlers
import sys

from RinUI import BackdropEffect, Theme
from RinUI.core.config import RINUI_PATH, is_win10, is_win11

from .paths import LOG_DIR, UI_DIR, ensure_runtime_dirs

log = logging.getLogger("luminalium")


def setup_logging(level: str = "INFO") -> None:
    ensure_runtime_dirs()
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "luminalium.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # 只在**真终端**上再挂一份 stdout 日志。
    #
    # 为什么必须判断：Windows 管道的缓冲区写满（一般 64KB）时，写入方会被**阻塞**，
    # 而不是丢弃。从 VS Code 的「调试控制台」这类没有人持续读取的管道启动时，
    # 后台探测线程只要在 log 调用上撞到满缓冲区，就会被永远按在那里 ——
    # 现象是「线程 isRunning=True 但一个探测周期都不完成、日志静默、控制条不出现」。
    # 日志文件本身不受影响（先写文件再写 stdout），所以这里直接跳过最安全。
    if sys.stdout is not None and sys.stdout.isatty():
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)
    else:
        log.info(
            "标准输出不是终端（管道 / 调试控制台），已跳过控制台日志以免写满管道"
            "阻塞后台探测线程；日志见 %s", LOG_DIR / "luminalium.log",
        )


def configure_rinui(rinui, config) -> None:
    """把主题 / 强调色套到 RinUI 实例上（装配段与维护模式共用）。

    维护模式要开自己的引擎，但窗口外观必须与主程序**逐字一致** ——
    复制一份是必然走岔的写法，所以留在这里当唯一一处。

    ⚠️ **背景材质不在这里**（见 :func:`apply_backdrop_effect`）：它必须排在
    ``rinui.load()`` **之后**，否则那时窗口名单还是空的，材质一次都落不到
    面板上。

    ⚠️ 这里替 ``RinUIWindow.load()`` 补两件事：模块导入路径与 ``ThemeManager``
    上下文属性。RinUI 只在 ``load()`` 里做这两步，而**维护模式根本没有
    ``load()``**（它不建快捷面板）—— 不补的话 ``import RinUI`` 直接报
    「module "RinUI" is not installed」，窗口连创建都创建不出来。
    主装配这边是重复设置（``load()`` 里会再判一次 ``if not in import_paths``），
    幂等，无副作用。
    """
    import_paths = rinui.engine.importPathList()
    if str(RINUI_PATH) not in import_paths:
        rinui.engine.addImportPath(str(RINUI_PATH))
    rinui.engine.rootContext().setContextProperty("ThemeManager", rinui.theme_manager)
    rinui.engine.addImportPath(str(UI_DIR))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent", "#4CC2FF")))

    theme_name = str(config.get("app.theme", "dark")).lower()
    rinui.setTheme({"dark": Theme.Dark, "light": Theme.Light}.get(theme_name, Theme.Auto))


def apply_backdrop_effect(rinui, config) -> None:
    """按配置铺背景材质 —— 必须在 ``rinui.load()`` **之后**调用。

    （维护模式没有 ``load()`` 这一步：它把材质值记在 RinUI 里，等自管窗口
    接管时 ``_attach_to_rinui`` 会重放当前值。）
    """
    # 默认 "auto" = **按平台选**，与 RinUI 自带策略一致：
    # Win11 → Mica / Win10 → Acrylic / 其余 → none。
    #
    # ⚠️ 这里以前默认 "none"，并且**无条件**调用 setBackdropEffect() ——
    # 等于把 RinUI 自己的平台判断整个覆盖掉。后果是 Win11 上永远铺实色
    # 主题背景（colors.backgroundColor = #202020），窗口一次都不会透明，
    # 看起来就像「RinUI 的 Mica 没生效」。实测（build 26300）只要把值放成
    # mica，DWMWA_SYSTEMBACKDROP_TYPE 立刻变 2、客户区 alpha 从 255 掉到 77，
    # DWM 确实在合成 —— 所以问题从来不在 RinUI 那侧，而在这行覆盖。
    #
    # 显式写 none 仍然完全可用（窗口退回实色主题背景）。
    backdrop = str(config.get("app.backdrop", "auto")).lower()
    if backdrop == "auto":
        effect = (
            BackdropEffect.Mica
            if is_win11()
            else BackdropEffect.Acrylic
            if is_win10()
            else BackdropEffect.None_
        )
    else:
        effect = {
            "mica": BackdropEffect.Mica,
            "acrylic": BackdropEffect.Acrylic,
            "tabbed": BackdropEffect.Tabbed,
        }.get(backdrop, BackdropEffect.None_)
    rinui.setBackdropEffect(effect)
    log.info("背景材质: %s（配置 app.backdrop=%s）", effect.value, backdrop)
