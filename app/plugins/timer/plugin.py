"""计时器插件（倒计时 / 正计时 / 时钟）—— Luminalium 2 第一个正式插件。

2026-10-06 用户指令「做一个计时器[包含倒计时、正计时、时钟等功能]」落地。
功能语义参考了 Lmn-copy 项目的 ``plugins/builtins/timer``（开始 / 暂停 /
继续 / 停止 / 加时 / 结束铃声 / 末 3 秒秒滴），但该项目是 WebView(HTML)
形态，本项目按 ``AGENTS.md``「没有网页前端」的规矩用 RinUI 原生 QML 重写，
只保留功能契约与铃声资产（``assets/alarm.wav`` 即原项目 ``3s.wav``；
``assets/tick.wav`` 是本仓库生成的 0.14s / 880Hz 秒滴）。

架构要点（为什么这样写，别改回去）：

* **倒计时引擎在 Python，不在 QML**。窗口是懒创建、只藏不销毁的，但用户
  会把窗口关掉继续讲课 —— 倒计时必须藏在窗口背后继续走、走完了照响。
  这也是 ``context.py`` 铁规 1（驻留组件的状态放 Python 侧）的窗口版。
  引擎用 ``time.monotonic()`` 逐拍累计（QTimer 只当节拍器），不靠间隔数
  数，定时器漂移 / 挂起不会让表走慢。
* **QML 只做显示**。Python 引擎每拍把状态（模式 / 剩余 / 跑没跑 / 走完没）
  经 ``QQuickWindow.setProperty`` 推给窗口根属性，QML 纯绑定渲染 ——
  窗口还没建（懒创建）时推空操作，窗口藏起来时照推（代价是几个属性写）。
* **QML → Python 的通道只有动作**。窗口上的开始 / 暂停 / 预设时长按钮全走
  ``Backend.triggerAction("plugin:timer:...")``，参数（时长毫秒数）编进
  动作后缀由处理器解析 —— 这是 ``docs/plugin-development.md`` 动作动词
  一节「处理器拿到完整动作串自己解析后缀」的正用；插件不碰 Backend 的
  专用槽，也不私开 context property。

窗口 / 磁贴 / 控制条 / 设置页四路入口都注册：快捷面板磁贴与放映控制条
动作是 ``plugin:timer:toggle``，设置页管「提示音」开关（经 side_effect
实时改引擎，不用重启）。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ...paths import UI_DIR
from ... import i18n

log = logging.getLogger(__name__)

META = {
    "id": "timer",
    "name": "计时器",
    "version": "1.0.0",
}

#: ``plugins.timer.*`` 的默认值（dict 型贡献，经阶段一注入默认层，不落盘）。
DEFAULTS = {"alarm": True}

#: 倒计时走完之后铃声最长响多久（秒）—— 循环铃声必须有个上限，否则用户
#: 关了窗口又忘了这回事，铃声能一路响到天荒地老。
_ALARM_MAX_SECONDS = 180

#: 末尾多少秒开始秒滴（对齐参考实现的「3、2、1」倒数提示）。
_TICK_LAST_SECONDS = 3

_ASSETS = Path(__file__).resolve().parent / "assets"
_ALARM_WAV = _ASSETS / "alarm.wav"
_TICK_WAV = _ASSETS / "tick.wav"

# ---------------------------------------------------------------- 引擎状态

#: ``register`` 期捕获的窗口句柄（PluginContext 不留公共 Backend 访问器，
#: 插件需要的引用都在注册期自己存好）。
_window_handle: Optional[Any] = None
_tick_timer: Optional[Any] = None

_mode = "countdown"           # countdown | stopwatch | clock
# 倒计时
_cd_total_ms = 5 * 60 * 1000
_cd_remaining_ms = _cd_total_ms
_cd_running = False
_cd_finished = False
_cd_last_beep_second: Optional[int] = None
# 正计时
_sw_ms = 0
_sw_running = False

_alarm_enabled = True
_alarm_playing = False
_alarm_started_at = 0.0

_last_stamp = 0.0
#: 上次推给窗口的属性快照 —— 值没变就不写（setProperty 会打断 QML 侧绑定，
#: 也会触发绑定重求值，100ms 一拍没必要全量推）。
_last_pushed: Dict[str, Any] = {}


# ---------------------------------------------------------------- 声音

def _play(path: Path, loop: bool) -> None:
    """异步播放 wav（不阻塞主线程）。winsound 是 Windows 独占 stdlib，本项目
    本来就是 Win32 专用的（``ppt_controller`` / ``windows.py`` 满篇 user32）。"""
    try:
        import winsound

        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        if loop:
            flags |= winsound.SND_LOOP
        winsound.PlaySound(str(path), flags)
    except Exception:
        log.warning("播放 %s 失败", path.name, exc_info=True)


def _stop_sound() -> None:
    try:
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:  # pragma: no cover - winsound 理论上不会炸
        pass


def _start_alarm() -> None:
    global _alarm_playing, _alarm_started_at
    if not _alarm_enabled:
        return
    _alarm_playing = True
    _alarm_started_at = time.monotonic()
    _play(_ALARM_WAV, loop=True)


def _stop_alarm() -> None:
    global _alarm_playing
    _alarm_playing = False
    _stop_sound()


# ---------------------------------------------------------------- 引擎推进

def _tick() -> None:
    """引擎节拍（100ms）：推进倒计时 / 正计时、管秒滴与铃声、推状态。

    一拍只有两次浮点加减和一次属性对比，空转代价可忽略 —— 刻意**不停表**：
    启停定时器的状态机比永远转着的空拍更容易写出「忘了重启」的悬案。
    """
    global _last_stamp, _cd_remaining_ms, _cd_running, _cd_finished
    global _cd_last_beep_second, _sw_ms

    now = time.monotonic()
    dt_ms = max(0.0, (now - _last_stamp) * 1000.0)
    _last_stamp = now

    if _cd_running:
        _cd_remaining_ms -= dt_ms
        whole = int(max(0.0, _cd_remaining_ms) / 1000.0) + 1
        if 0 < whole <= _TICK_LAST_SECONDS and whole != _cd_last_beep_second:
            # 进入末 3 秒：每个整秒滴一声（whole 是「还剩多少个整秒含当前」）
            _cd_last_beep_second = whole
            if _alarm_enabled:
                _play(_TICK_WAV, loop=False)
        if _cd_remaining_ms <= 0:
            _cd_remaining_ms = 0.0
            _cd_running = False
            _cd_finished = True
            _start_alarm()
            log.info("倒计时结束，铃声已起（最长 %ds，重置 / 切页 / 关提示音即停）", _ALARM_MAX_SECONDS)
    if _sw_running:
        _sw_ms += dt_ms

    if _alarm_playing and (now - _alarm_started_at) > _ALARM_MAX_SECONDS:
        _stop_alarm()

    _push_state()


def _push_state() -> None:
    """把引擎状态推给窗口根属性（值没变不推；窗口没建就什么都不做）。"""
    if _window_handle is None:
        return
    window = _window_handle.window
    if window is None:
        return
    state: Dict[str, Any] = {
        "mode": _mode,
        "cdTotal": int(_cd_total_ms),
        "cdRemaining": int(round(max(0.0, _cd_remaining_ms))),
        "cdRunning": bool(_cd_running),
        "cdFinished": bool(_cd_finished),
        "swMs": int(_sw_ms),
        "swRunning": bool(_sw_running),
    }
    for key, value in state.items():
        if _last_pushed.get(key) != value:
            try:
                window.setProperty(key, value)
            except RuntimeError:  # pragma: no cover - 窗口正被销毁
                return
            _last_pushed[key] = value


# ---------------------------------------------------------------- 动作处理


def _on_action(action: str) -> None:
    """``plugin:timer:`` 前缀动作的处理器：后缀分发，参数编在动作串里。

    ⚠️ 入口只判 ``_window_handle is None``（注册没成功），**不能**再判
    ``.window is None``：窗口是懒创建的，第一次 ``show()`` 之前 ``.window``
    就是 None —— 那道守卫会把唯一能触发创建的调用拦在门外，磁贴 / 控制条
    就永远「点了没反应」（2026-10-07 实锤的上线 bug，聚光灯能用恰是它的
    处理器不做这道检查）。``toggle()/show()/hide()`` 自己处理懒创建。
    """
    global _mode, _cd_total_ms, _cd_remaining_ms, _cd_running, _cd_finished
    global _cd_last_beep_second, _sw_ms, _sw_running

    prefix = "plugin:timer:"
    if action == prefix + "toggle":
        if _window_handle is not None:
            _window_handle.toggle()
            _push_state()
        return
    if action == prefix + "open":
        if _window_handle is not None:
            _window_handle.show()
            _push_state()
        return
    if action == prefix + "close":
        if _window_handle is not None:
            _window_handle.hide()
        return
    if action == prefix + "sync":
        # 窗口 Component.onCompleted 里要一次全量状态。⚠️ 这一步在懒创建
        # 路径上通常是空操作：onCompleted 触发时 ``_create()`` 还没返回，
        # 句柄的 ``.window`` 仍是 None，``_push_state`` 直接早退。真正的
        # 兜底是 toggle / open 分支里 show() 返回**之后**的那次
        # ``_push_state()``（窗口已存在，首帧就能拿到真实状态）——
        # 2026-10-07 插件巡检修的「首帧闪 0:00」就是这个时序。
        _push_state()
        return
    if action == prefix + "preview-alarm":
        # 设置页「试听」：单次播放，不进循环。PlaySound 进程内独占，新
        # 播放本来就会顶掉正在响的循环铃声 —— 先显式停掉，免得
        # ``_alarm_playing`` 揣着旧时间戳假装铃声还在响。
        _stop_alarm()
        _play(_ALARM_WAV, loop=False)
        return
    if action.startswith(prefix + "mode:"):
        mode = action[len(prefix + "mode:"):]
        if mode in ("countdown", "stopwatch", "clock") and mode != _mode:
            _mode = mode
            _stop_alarm()  # 换页 = 换心情，铃声不该跟着人跑
            _push_state()
        return

    # ---- 倒计时 ----
    if action.startswith(prefix + "start:"):
        # 时长编在动作后缀里（毫秒）；窗口的预设按钮与自选框都走这条
        try:
            total = int(action.rsplit(":", 1)[1])
        except ValueError:
            log.warning("倒计时时长解析失败: %s", action)
            return
        total = max(1000, min(total, 24 * 3600 * 1000))
        _stop_alarm()
        _cd_total_ms = total
        _cd_remaining_ms = total
        _cd_running = True
        _cd_finished = False
        _cd_last_beep_second = None
        _mode = "countdown"
    elif action == prefix + "pause":
        _cd_running = False
    elif action == prefix + "resume":
        if not _cd_finished and _cd_remaining_ms > 0:
            _cd_running = True
            _cd_last_beep_second = None
    elif action.startswith(prefix + "add:"):
        # 走完之后加时 = 复活倒计时；跑动中加时 = 顺延
        try:
            extra = int(action.rsplit(":", 1)[1])
        except ValueError:
            return
        extra = max(0, min(extra, 60 * 60 * 1000))
        _stop_alarm()
        _cd_total_ms += extra
        _cd_remaining_ms += extra
        _cd_finished = False
        _cd_last_beep_second = None
    elif action == prefix + "reset":
        _stop_alarm()
        _cd_running = False
        _cd_finished = False
        _cd_remaining_ms = _cd_total_ms
        _cd_last_beep_second = None

    # ---- 正计时 ----
    elif action == prefix + "sw-start":
        _sw_running = True
    elif action == prefix + "sw-pause":
        _sw_running = False
    elif action == prefix + "sw-reset":
        _sw_running = False
        _sw_ms = 0
    else:
        log.info("计时器收到未知动作: %s", action)
        return
    _push_state()


def _on_alarm_setting(config, key, value) -> None:
    """「提示音」设置的 side_effect：实时改引擎；关掉时连响着的铃声一起停。"""
    global _alarm_enabled
    _alarm_enabled = bool(value)
    if not _alarm_enabled:
        _stop_alarm()


# ---------------------------------------------------------------- 注册

def register(ctx) -> None:
    """两处入口 + 控制条动作 + 设置页 + 提示音设置键 + 自管窗口。"""
    global _window_handle, _tick_timer, _last_stamp, _alarm_enabled

    def tr(source: str) -> str:
        return i18n.tr("timer", source)

    # ⚠️ META["name"] 在这里才翻译（2026-10-07 插件巡检）：模块 import 发生在
    # 阶段一 collect_defaults（Config() 构造之前），那时翻译器一个都没装，
    # i18n.tr 只能回中文原文 —— 英文/日文界面上插件管理页的名称会永远是
    # 中文。register 跑在 install_translators 之后，这里重写才是真译文。
    META["name"] = tr("计时器")

    # ① 快捷面板磁贴
    ctx.add_shortcut(
        "timer_panel", tr("计时器"), "ic_fluent_timer_20_regular",
        "plugin:timer:toggle",
    )
    # ② 动作处理器（窗口按钮全走这条通道）
    ctx.add_action_handler("plugin:timer:", _on_action)
    # ③ 放映控制条动作（讲课中途开计时器是高频操作）
    ctx.add_dock_action(
        "plugin:timer:toggle", tr("计时器"), "ic_fluent_timer_20_regular",
        tooltip=tr("打开 / 收起计时器"),
    )
    # ④ 设置页
    ctx.add_settings_page(
        "timer_page", tr("计时器"), "TimerSettings.qml",
        "ic_fluent_clock_alarm_20_regular",
    )
    # ⑤ 设置键：提示音（side_effect 实时生效）。初始值走
    # ``backend._config`` 内部引用（loader 读启用态同款通道；ctx 刻意不
    # 给公共读取器，插件与宿主的通道收束在 ctx 的 8 个 API 上）。
    _alarm_enabled = bool(ctx._backend._config.get("plugins.timer.alarm", True))
    ctx.register_setting(
        "plugins_timer_alarm", "plugins.timer.alarm",
        side_effect=_on_alarm_setting,
    )
    # ⑥ 自管窗口（懒创建；引擎先跑起来，窗口第一次 show 就能拿到当前状态）
    _window_handle = ctx.register_window(
        "timer", UI_DIR / "plugins" / "timer" / "TimerWindow.qml",
        label=tr("计时器"),
    )

    _last_stamp = time.monotonic()
    from PySide6.QtCore import QTimer

    _tick_timer = QTimer()
    _tick_timer.setInterval(100)
    _tick_timer.timeout.connect(_tick)
    _tick_timer.start()
    log.info("计时器插件已注册（提示音 %s）", "开" if _alarm_enabled else "关")
