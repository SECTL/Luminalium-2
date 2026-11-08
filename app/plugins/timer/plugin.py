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
* 铃声由 HTML 自己播（Windows 系统音，``Timer.EnableSoundEffects`` 控制）
  —— 设置页「提示音」开关经 ``plugins.timer.alarm`` 落进
  ``EnableSoundEffects`` 喂给页面；「试听」走动作通道在 Python 侧
  用 winsound 播同一个系统音（页面藏着时也能听到）。
  2026-10-18（plugin-audit F2/F9/F15）补 Python 权威收口：页面
  ``setInterval`` 藏窗后会被 Chromium 节流，铃声不能押在它身上 ——
  订阅 ``TimerManager.finished``（见 ``_on_timer_finished``），藏窗时
  show/raise + 推 JS 走页面同一条收尾分支，JS 不可用才回落 winsound
  （同一条配置门控）。

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
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ... import __version__, i18n
from .timer_manager import TimerManager

log = logging.getLogger(__name__)

META = {
    "id": "timer",
    "name": "计时器",
    "version": "1.0.0",
    "category": "utility",
}

#: ``plugins.timer.*`` 默认值（dict 型贡献，注入默认层不落盘）。
#: ``alarm`` = HTML 侧的 ``Timer.EnableSoundEffects``（走完 / 重置提示音）。
DEFAULTS = {"alarm": True}

_WEB_DIR = Path(__file__).resolve().parent / "web"
_TIMER_HTML = _WEB_DIR / "timer.html"

# 默认铃声资产 = Windows 自带系统音（Media 子目录），两支共用一套推导：
# 到点铃声（页面到点 / 设置页试听 / 到点回落三处同源）与重置提示音。
# 2026-10-19 todo T8/F12：旧版三处把系统盘写死（C:\Windows\Media），
# 改过系统盘盘符的机器整批静音，现一律按 %SystemRoot% 推导。
_ALARM_SOUND_FILE = "Windows Notify Email.wav"
_BELL_OFF_SOUND_FILE = "Speech Off.wav"


def _alarm_sound_path(name: str = _ALARM_SOUND_FILE) -> str:
    """默认音文件路径：%SystemRoot% 推导 Media 子目录（todo T8/F12）。

    %SystemRoot% 缺失时回落 ``C:\\Windows`` 字面兜底 —— 行为等价旧版，
    可感知的 failure 面不崩；环境变量非空才走推导值。
    """
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return os.path.join(root, "Media", name)


def _alarm_sound_file_url(name: str = _ALARM_SOUND_FILE) -> str:
    """同源路径的 file:// URL（页面 Audio 只吃 URL）；异常给空串。

    空串在页面侧走跳过分支（不落回写死盘符），到点铃声的权威回落
    仍在 Python（_alarm_sound_fallback），页面静默不崩。
    """
    try:
        return Path(_alarm_sound_path(name)).as_uri()
    except (ValueError, OSError):
        return ""


# ---------------------------------------------------------------- 模块状态

#: 窗口与桥接（懒创建，只藏不销毁；webengine 模块同样懒 import）
_window: Optional[Any] = None
_api: Optional[Any] = None
_timer_manager: Optional[TimerManager] = None
_backend: Optional[Any] = None
#: 注册时注入的只读配置读口（ctx.config_get，2026-10-19 D11/D-F11）：
#: _build_settings/_build_version 是模块级函数、没有 ctx 在手，经这里
#: 的函数引用走公共口，私有配置直读链就此清零。
_config_get: Optional[Any] = None
#: WindowManager（放映置顶带公共通道用，register 时接线；preview 桩可能没有）
_windows: Optional[Any] = None
_sound_enabled = True
#: 到点双发防抖闩：页面 finish_timer 与 worker 自然到点可能几乎同时各发
#: 一次 finished，latch 保证露面/铃声收口恰做一次；新一轮起表复位
_finished_latch = False
#: finished / state_changed 订阅只接一次（_timer_manager 是单例，但接线
#: 跟着懒创建走，防重复 connect）
_alarm_subscribed = False


# ---------------------------------------------------------------- 设置合成


def _resolve_is_dark(theme_mode: str) -> bool:
    """app.theme（auto/light/dark）→ HTML 要的 ResolvedIsDark。

    Windows 应用深浅色注册表读法的唯一实现（F24，2026-10-19 todo 24）：
    webview.py 的旧副本（_get_windows_dark_mode/resolve_theme_dark）已删——
    同一段 winreg 读法曾抄三份，auto 判定改一处漏两处的坑；新调用方
    一律用这一个。
    """
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
    Timer.EnableSoundEffects（提示音开关）、Timer.AlarmSoundUrl /
    Timer.BellOffSoundUrl（默认音 file:// URL，%SystemRoot% 推导，
    2026-10-19 todo T8）。QuickAddPresets 不给 ——
    HTML 有内置默认值，Lmn-copy 的默认配置里也没有这一项。
    """
    def _get(path: str, default: Any) -> Any:
        return _config_get(path, default) if _config_get is not None else default

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
        "Timer": {
            "EnableSoundEffects": bool(_sound_enabled),
            "AlarmSoundUrl": _alarm_sound_file_url(_ALARM_SOUND_FILE),
            "BellOffSoundUrl": _alarm_sound_file_url(_BELL_OFF_SOUND_FILE),
        },
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
    if _config_get is not None:
        codename = str(_config_get("app.codename", ""))
    return {
        "version": __version__,
        "code_name": codename,
        "device_uuid": _device_uuid(),
    }


# ---------------------------------------------------------------- 窗口


def _ensure_window():
    """懒创建 WebView 窗口（第一次开窗时才拉起 WebEngine）。"""
    global _window, _api, _timer_manager, _alarm_subscribed
    if _window is not None:
        return _window

    from .webview import TimerApi, TimerWebWindow  # 懒 import，见头注释

    if _timer_manager is None:
        _timer_manager = TimerManager()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(_timer_manager.shutdown)

    # 到点告警 Python 权威（2026-10-18 plugin-audit F2/F9/F15，见
    # _on_timer_finished）：finished 此前无人订阅，铃声押在被节流的页面
    # setInterval 上。接线跟懒创建走，只接一次。
    if not _alarm_subscribed:
        _alarm_subscribed = True
        _timer_manager.finished.connect(_on_timer_finished)
        _timer_manager.state_changed.connect(_on_timer_run_state_changed)

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
    _sync_topmost_band()


def _sync_topmost_band() -> None:
    """把窗口纳入放映置顶带（2026-10-18，plugin-audit GAP-1）。

    本插件的窗口是 AGENTS.md 明文豁免 register_window 的自建窗口，
    WindowManager 的放映置顶机制只扫登记表 —— 不主动 adopt 的话，放映
    中开计时器会被全屏放映画面整个盖死（含迷你窗），翻页把置顶带重排
    后也没有恢复通路。adopt 幂等：注册初值 / 放映状态边沿 / 每次开窗各
    调一次都安全；普通期它只登记成员不推顶（窗口在迷你模式下的常驻
    置顶来自它自己的 StaysOnTopHint，不经这道门），放映退出的对称回落
    由 WindowManager 统一做。
    """
    window = _window
    manager = _windows
    if window is None or manager is None:
        return
    try:
        manager.adopt_topmost_window(window)
    except Exception:
        log.warning("计时器窗口接入放映置顶带失败", exc_info=True)


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
            _alarm_sound_path(),
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )
    except Exception:
        log.exception("试听铃声播放失败")


# ---------------------------------------------------------------- 到点告警


def _on_timer_run_state_changed(running: bool) -> None:
    """新一轮起表（is_running → True）解除到点闩 —— 双发防抖的复位点。"""
    global _finished_latch
    if running:
        _finished_latch = False


def _alarm_sound_fallback() -> None:
    """JS 通道不可用时的到点铃声回落，声音沿 ``Timer.EnableSoundEffects`` 门控。

    页面自己的铃声走 ``playSystemAudio``（同一条配置门控）；只有 JS 推
    不动（窗口没建出来 / 页面未加载 / 渲染进程崩）才落到这里。与设置页
    「试听」用同一个系统音（同走 ``_alarm_sound_path`` 推导，
    2026-10-19 todo T8 收口）。
    """
    if not _sound_enabled:
        return
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.PlaySound(
            _alarm_sound_path(),
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )
    except Exception:
        log.exception("到点回落铃声播放失败")


def _on_timer_finished() -> None:
    """到点（TimerManager.finished，Python 权威）—— 无论藏否必响必露面。

    2026-10-18（plugin-audit F2/F9/F15）：铃声此前完全押在页面的
    ``setInterval`` 上，窗口藏 5 分钟后 Chromium 强化节流最坏 1 次/分钟，
    铃声晚响甚至到重开窗口才响；``TimerManager.finished`` 明明是权威
    信号却无人订阅。现在 Python 收口：

    * 窗口可见 → 交由页面自己的 ``finishCountdown``（UI+铃声，页面已按
      ``Timer.EnableSoundEffects`` 门控），不重复 show、不重复推；
    * 窗口藏着 → ``show/raise`` 露面 + 推 JS 走同一条页面收尾分支
      （页面 ``finishCountdown`` 已加幂等守卫，与页面自己的到点检测、
      与这条推送都不会双响），迷你模式被藏的窗口同样露面（统一 F9 的
      「迷你弹、普通不弹」不一致 —— 收尾形态都由页面分支决定）；
    * JS 不可用 → 回落 winsound（:meth:`_alarm_sound_fallback`）。
    """
    global _finished_latch
    if _finished_latch:
        return
    _finished_latch = True

    window = _window
    if window is None:
        # 没建过窗口（引擎被外部驱动等）：没有页面可露可推，只保铃声
        _alarm_sound_fallback()
        return
    try:
        if window.isVisible():
            return
        window.show()
        window.raise_()
    except Exception:
        log.warning("到点露面失败，回落 winsound", exc_info=True)
        _alarm_sound_fallback()
        return

    # 推 JS 统一走页面收尾分支；页面正常时 finishCountdown 同步执行完、
    # 回调立即回 —— 2 秒没回说明 JS 通道不可用（页面未加载 / 渲染进程
    # 已崩），回落 winsound
    js_fired = [False]

    def _js_done(_result) -> None:
        js_fired[0] = True

    try:
        window.page().runJavaScript(
            "try{ if (typeof finishCountdown === 'function') finishCountdown(); }catch(e){}",
            _js_done,
        )
    except Exception:
        log.warning("到点推送页面收尾失败，回落 winsound", exc_info=True)
        _alarm_sound_fallback()
        return

    def _verify_js_reached_page() -> None:
        if not js_fired[0]:
            log.warning("到点推送页面无回应，回落 winsound")
            _alarm_sound_fallback()

    QTimer.singleShot(2000, _verify_js_reached_page)


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
    global _backend, _sound_enabled, _windows, _config_get

    def tr(source: str) -> str:
        return i18n.tr("timer", source)

    # ⚠️ META["name"] 在这里才翻译（register 跑在翻译器安装之后，
    # 模块顶层 tr 只能回中文 —— 2026-10-07 插件巡检实锤）。
    META["name"] = tr("计时器")

    _backend = ctx._backend
    _config_get = ctx.config_get
    _sound_enabled = bool(ctx.config_get("plugins.timer.alarm", True))

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

    # ⑦ 放映置顶带（见 _sync_topmost_band 注释）：接线 + 注册时读初值
    # 同步（放映中插件才被加载的场合，边沿信号不会再来第二次）。此刻
    # 窗口必然还没建（懒创建），首调是幂等空转，只为把「当前是否放映」
    # 的判断挂上。
    try:
        _windows = ctx._windows
    except Exception:
        _windows = None
    if _windows is not None:
        try:
            _backend.presentationActiveChanged.connect(_sync_topmost_band)
            _sync_topmost_band()
        except Exception:
            log.warning("订阅放映状态失败，放映中开计时器可能被放映画面盖住",
                        exc_info=True)

    log.info("计时器插件已注册（HTML 版，提示音 %s）", "开" if _sound_enabled else "关")
