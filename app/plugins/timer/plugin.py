"""计时器插件（HTML 原版移植）—— 2026-10-17 用户指令「把 Lmn-copy 的计时器
原汁原味搬过来，替换现有实现」。

本插件经历过两代：

* 2026-10-06 初代：参考 Lmn-copy 的功能语义，用 RinUI 原生 QML 重写
  （那时守「没有网页前端」的规矩，只拿走了功能契约与铃声资产）。
* 2026-10-17 本代：用户明确要求 HTML 版**原样**回来，QML 版废弃删除
  （``ui/plugins/timer/TimerWindow.qml``、``assets/*.wav`` 已移除）。
  ``web/timer.html`` 是 Lmn-copy ``plugins/builtins/timer/timer.html``
  的逐字节副本，一个字符都没改 —— 它只能跑在 QWebEngineView 里，
  宿主在 ``webview.py``（两条硬规矩的明文例外，理由写在那里的头注释）。

架构（与 Lmn-copy 同构）：

* HTML 页面是自己的引擎：窗口开着时倒计时 / 秒表 / 时钟全在页面里跑，
  经 pywebview 垫片调 Python 的 ``TimerApi`` 同步状态。
* Python 侧的 ``TimerManager``（``timer_manager.py``，原版逐行移植）是
  权威状态源：窗口藏起来（本应用窗口只藏不销毁）后页面其实还在跑，
  重开窗口时 ``get_timer_state`` 从这里恢复。
* 铃声由 HTML 自己播（Windows 系统音，``Timer.EnableSoundEffects`` 控制），
  Python 不再 winsound —— 设置页「提示音」开关经 ``plugins.timer.alarm``
  落进 ``EnableSoundEffects`` 喂给页面；「试听」走动作通道在 Python 侧
  用 winsound 播同一个系统音（页面藏着时也能听到）。

入口与设置键的 id 与初代完全一致（``timer_panel`` 磁贴、
``plugin:timer:toggle`` 动作、``timer_page`` 设置页、
``plugins_timer_alarm`` 设置键），老用户的配置与面板布局不受影响。

⚠️ WebEngine 懒加载：``webview.py`` 的 QtWebEngine 是模块级导入，所以
本模块只在第一次开窗时才 import 它（``_ensure_window`` 里）。register
阶段 import 会让全体用户白付 WebEngine 初始化成本（已验证 Qt 6.9 允许
在 QApplication 创建之后再初始化 WebEngine）。
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QApplication

from ... import __version__, i18n
from .timer_manager import TimerManager

log = logging.getLogger(__name__)

META = {
    "id": "timer",
    "name": "计时器",
    "version": "1.0.0",
    "category": "utility",
    # 管理页行首图标（``META.icon``，见 docs/plugin-development.md）
    "icon": "ic_fluent_timer_20_regular",
}

#: ``plugins.timer.*`` 默认值（dict 型贡献，注入默认层不落盘）。
#: ``alarm`` = HTML 侧的 ``Timer.EnableSoundEffects``（走完 / 重置提示音）。
DEFAULTS = {"alarm": True}

_WEB_DIR = Path(__file__).resolve().parent / "web"
_TIMER_HTML = _WEB_DIR / "timer.html"

# ---------------------------------------------------------------- 模块状态

#: 窗口与桥接（懒创建，只藏不销毁；webengine 模块同样懒 import）
_window: Optional[Any] = None
_api: Optional[Any] = None
_timer_manager: Optional[TimerManager] = None
_backend: Optional[Any] = None
_sound_enabled = True


# ---------------------------------------------------------------- 设置合成


def _resolve_is_dark(theme_mode: str) -> bool:
    """app.theme（auto/light/dark）→ HTML 要的 ResolvedIsDark。"""
    mode = theme_mode.strip().lower()
    if mode == "dark":
        return True
    if mode == "light":
        return False
    # auto：读 Windows 应用深浅色
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return int(value) == 0
        except Exception:
            pass
    return False


def _build_settings() -> Dict[str, Any]:
    """把 Luminalium 2 的配置合成 Lmn-copy settings.json 的形状喂给 HTML。

    HTML 读：General.Language（zh-CN 式）、Appearance.ThemeMode
    （Light/Dark/Auto 首字母大写式）、Appearance.ThemeId（恒 default）、
    Appearance.ResolvedIsDark、Fonts.CustomFont（恒 False 走内置字体栈）、
    Window.TimerFullscreenBehavior（恒 fullscreen）、
    Timer.EnableSoundEffects（提示音开关）。QuickAddPresets 不给 ——
    HTML 有内置默认值，Lmn-copy 的默认配置里也没有这一项。
    """
    cfg = _backend._config if _backend is not None else None

    def _get(path: str, default: Any) -> Any:
        try:
            return cfg.get(path, default) if cfg is not None else default
        except Exception:
            return default

    theme_raw = str(_get("app.theme", "dark"))
    theme_mode = {"dark": "Dark", "light": "Light"}.get(
        theme_raw.strip().lower(), "Auto"
    )
    language = str(_get("app.language", "zh_CN")).replace("_", "-")
    return {
        "General": {"Language": language},
        "Appearance": {
            "ThemeMode": theme_mode,
            "ThemeId": "default",
            "ResolvedIsDark": _resolve_is_dark(theme_raw),
        },
        "Fonts": {"CustomFont": False},
        "Window": {"TimerFullscreenBehavior": "fullscreen"},
        "Timer": {"EnableSoundEffects": bool(_sound_enabled)},
    }


def _device_uuid() -> str:
    """开发版水印用的设备短码：Windows MachineGuid 的 md5 前 8 位。"""
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return hashlib.md5(str(guid).encode()).hexdigest()[:8]
        except Exception:
            pass
    return "00000000"


def _build_version() -> Dict[str, Any]:
    codename = ""
    try:
        if _backend is not None:
            codename = str(_backend._config.get("app.codename", ""))
    except Exception:
        pass
    return {
        "version": __version__,
        "code_name": codename,
        "device_uuid": _device_uuid(),
    }


# ---------------------------------------------------------------- 窗口


def _ensure_window():
    """懒创建 WebView 窗口（第一次开窗时才拉起 WebEngine）。"""
    global _window, _api, _timer_manager
    if _window is not None:
        return _window

    from .webview import TimerApi, TimerWebWindow  # 懒 import，见头注释

    if _timer_manager is None:
        _timer_manager = TimerManager()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(_timer_manager.shutdown)

    _api = TimerApi(_timer_manager, _build_settings, _build_version)

    screen = QApplication.primaryScreen()
    screen_geo = screen.geometry() if screen is not None else None
    if screen_geo is not None:
        # 窗口尺寸公式与 Lmn-copy 一致：随屏幕取比例并封顶
        width_val = int(
            min(max(600, screen_geo.width() * 0.35), screen_geo.width() * 0.5)
        )
        height_val = int(
            min(max(500, screen_geo.height() * 0.45), screen_geo.height() * 0.6)
        )
        width = int(min(width_val + 350, screen_geo.width()))
        height = int(min(height_val + 150, screen_geo.height()))
    else:
        width, height = 950, 650

    _window = TimerWebWindow(
        i18n.tr("timer", "计时器"),
        str(_TIMER_HTML),
        _api,
        width,
        height,
        _build_settings(),
    )
    return _window


def _open_window() -> None:
    window = _ensure_window()
    # 藏着期间可能换过主题 / 语言 / 开关，重推一遍设置再亮相
    window.apply_settings(_build_settings())
    if window.isMinimized():
        window.showNormal()
    window.show()
    window.raise_()
    window.activateWindow()


def _close_window() -> None:
    if _window is not None:
        _window.hide()


def _toggle_window() -> None:
    if _window is not None and _window.isVisible():
        _close_window()
    else:
        _open_window()


def _preview_alarm() -> None:
    """「试听铃声」：播 HTML 走完时用的同一个系统音（单次，异步）。"""
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.PlaySound(
            r"C:\Windows\Media\Windows Notify Email.wav",
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )
    except Exception:
        log.exception("试听铃声播放失败")


# ---------------------------------------------------------------- 动作分发


def _on_action(action: str) -> None:
    prefix = "plugin:timer:"
    if action == prefix + "toggle":
        _toggle_window()
    elif action == prefix + "open":
        _open_window()
    elif action == prefix + "close":
        _close_window()
    elif action == prefix + "preview-alarm":
        _preview_alarm()
    else:
        log.info("计时器收到未知动作: %s", action)


def _on_alarm_setting(config, key, value) -> None:
    """「提示音」开关的 side_effect：实时合成进下次喂给 HTML 的设置，
    窗口开着就立刻推过去。"""
    global _sound_enabled
    _sound_enabled = bool(value)
    if _window is not None:
        _window.apply_settings(_build_settings())


def _on_settings_changed() -> None:
    """主题 / 语言变化时跟进（settingsChanged 是宽信号，推一遍设置成本很低）。"""
    if _window is not None:
        _window.apply_settings(_build_settings())


# ---------------------------------------------------------------- 注册


def register(ctx) -> None:
    """磁贴 + 控制条动作 + 设置页 + 提示音设置键；窗口在动作触发时才建。"""
    global _backend, _sound_enabled

    def tr(source: str) -> str:
        return i18n.tr("timer", source)

    # ⚠️ META["name"] 在这里才翻译（register 跑在翻译器安装之后，
    # 模块顶层 tr 只能回中文 —— 2026-10-07 插件巡检实锤）。
    META["name"] = tr("计时器")

    _backend = ctx._backend
    try:
        _sound_enabled = bool(ctx._backend._config.get("plugins.timer.alarm", True))
    except Exception:
        _sound_enabled = True

    # ① 快捷面板磁贴
    ctx.add_shortcut(
        "timer_panel", tr("计时器"), "ic_fluent_timer_20_regular",
        "plugin:timer:toggle",
    )
    # ② 动作处理器（开关窗 / 试听都走这条通道）
    ctx.add_action_handler("plugin:timer:", _on_action)
    # ③ 放映控制条动作（讲课中途开计时器是高频操作）
    ctx.add_dock_action(
        "plugin:timer:toggle", tr("计时器"), "ic_fluent_timer_20_regular",
        tooltip=tr("打开 / 收起计时器"),
    )
    # ④ 设置页（提示音开关 + 试听）
    ctx.add_settings_page(
        "timer_page", tr("计时器"), "TimerSettings.qml",
        "ic_fluent_clock_alarm_20_regular",
    )
    # ⑤ 设置键：提示音（side_effect 实时喂给页面，不用重启）
    ctx.register_setting(
        "plugins_timer_alarm", "plugins.timer.alarm",
        side_effect=_on_alarm_setting,
    )
    # ⑥ 主题 / 语言跟进
    try:
        ctx._backend.settingsChanged.connect(_on_settings_changed)
    except Exception:
        pass

    log.info("计时器插件已注册（HTML 版，提示音 %s）", "开" if _sound_enabled else "关")
