"""全局旁白 / 配音语言（2026-10-17 用户指令）。

一句话：这是**对外暴露的配音语种配置**，主程序里任何要出声旁白的模块、
以及日后插件里的旁白 / 配音场景，都从这里取「该用哪一档配音」，不要各自
去读配置、各自维护一份语种表。

配置
    键 ``narration.language``（QML / 插件侧见扁平键 ``narration_language``），
    取值只有三档：``zh_CN``（中配）/ ``en_US``（英配）/ ``ja_JP``（日配）。
    **默认 ``zh_CN``**。它与界面语言 ``app.language`` 是**两个独立维度**：
    界面语言换的是 UI 文案与字体（``app/i18n.py``），配音语言换的是声音；
    把界面切成 English 而旁白仍用中文是合法组合，所以刻意不复用同一个键。

读取（唯一入口）
    * 主程序：``from . import narration`` → ``narration.language(config)``；
    * 插件：``ctx.narration_language()``（``PluginContext`` 的只读包装，
      插件拿不到 config，也不需要拿）；
    * QML：``Backend.narrationLanguage``（归一后的值，改配置会跟着变）。

回退（读失败怎么办）
    ``language()`` 一律返回**三档之一**，绝不把脏值透给调用方：
    键缺失 / 空串 / 非字符串 / 不在三档内 → 回退 ``DEFAULT_LANGUAGE``（``zh_CN``）。
    后三种会记一条 warning（缺失是正常情况：老版本 config.json 里没有这个键，
    默认层会兜住，属于预期路径，不吵）。

试听素材
    ``resources/narration_testaudio_<BCP47>.mp3`` 三条，映射见 :data:`SAMPLES`。
    ⚠️ 文件名用的是**连字符**（``zh-CN``）而配置值用**下划线**（``zh_CN``）——
    素材是既有的、不改名，映射在这里显式写死，别拿 code 拼文件名。
    素材缺失时 :func:`sample_path` 返回 None、:func:`sample_available` 为假，
    设置页那颗试听按钮自己变灰（**不补占位音频、不假装能播**）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .paths import RESOURCES_DIR

log = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "SAMPLES",
    "SampleNotFound",
    "language",
    "normalize",
    "play_sample",
    "preview_languages",
    "sample_available",
    "sample_path",
    "stop_sample",
]

#: 读不到 / 读到脏值时的落点。选 ``zh_CN`` 的理由：源语言、素材齐全、
#: 与 ``app.language`` 的默认值一致 —— 用户什么都还没配的时候，界面和
#: 声音都该是母语。
DEFAULT_LANGUAGE = "zh_CN"

#: 三档配音语言：``(code, 显示名)``。显示名用**各自语言的母语名**，与
#: 「界面语言」下拉同一套惯例（看不懂当前界面语言的人也认得出自己的语种）。
LANGUAGES: Tuple[Tuple[str, str], ...] = (
    ("zh_CN", "简体中文"),
    ("en_US", "English"),
    ("ja_JP", "日本語"),
)

#: 配音语言 -> 试听素材文件名（``resources/`` 下）。**唯一**的映射表：
#: 设置页的试听按钮、日后插件的配音示例都从这里取，别再各写一遍。
SAMPLES: Dict[str, str] = {
    "zh_CN": "narration_testaudio_zh-CN.mp3",
    "en_US": "narration_testaudio_en-US.mp3",
    "ja_JP": "narration_testaudio_ja-JP.mp3",
}

_CODES = tuple(code for code, _ in LANGUAGES)


class SampleNotFound(FileNotFoundError):
    """试听素材不在 ``resources/`` 里（打包漏带 / 素材被删）。"""


# ---------------------------------------------------------------- 读取与归一


def normalize(code: Any) -> Optional[str]:
    """把任意值收敛成三档之一；认不出来返回 None（**不**在这里回退默认值，
    调用方要靠这个区分「用户真选了 zh_CN」和「值是脏的」）。"""
    if not isinstance(code, str):
        return None
    value = code.strip().replace("-", "_")
    if value in _CODES:
        return value
    # 大小写宽容一点：配置文件是人手改的，``EN_us`` 这类写法不该变成静默失效。
    for candidate in _CODES:
        if candidate.lower() == value.lower():
            return candidate
    return None


def language(config: Any) -> str:
    """从配置读配音语言 —— **主程序和插件都走这里**，不要自己读键。

    ``config`` 是 ``app.config.Config``（含 ``.get(点号路径, 默认值)``）。
    任何异常（config 为 None、读不出、值不合法）都收敛成 ``DEFAULT_LANGUAGE``：
    配音是「说不出来就不好用」的功能，宁可回退也不要抛异常把调用方带崩。
    """
    if config is None:
        return DEFAULT_LANGUAGE
    try:
        raw = config.get("narration.language", DEFAULT_LANGUAGE)
    except Exception:  # noqa: BLE001 - 见 docstring「回退」一节
        log.warning("读取旁白语言失败，回退 %s", DEFAULT_LANGUAGE, exc_info=True)
        return DEFAULT_LANGUAGE
    normalized = normalize(raw)
    if normalized is not None:
        return normalized
    if raw in ("", None):
        # 老配置 / 首次运行没有这个键：默认层会兜住，属于正常路径。
        return DEFAULT_LANGUAGE
    log.warning("旁白语言取值非法: %r（可选 %s），回退 %s",
                raw, "/".join(_CODES), DEFAULT_LANGUAGE)
    return DEFAULT_LANGUAGE


# ---------------------------------------------------------------- 素材与播放


def sample_path(code: Any) -> Optional[Path]:
    """试听素材的绝对路径；语种非法或文件不存在都返回 None。"""
    normalized = normalize(code)
    if normalized is None:
        return None
    filename = SAMPLES.get(normalized)
    if not filename:
        return None
    path = RESOURCES_DIR / filename
    return path if path.is_file() else None


def sample_available(code: Any) -> bool:
    """这个语种有没有可播的示例音频（设置页据此禁用试听按钮）。"""
    return sample_path(code) is not None


def preview_languages() -> List[Dict[str, Any]]:
    """设置页下拉用的条目列表：``[{code, name, sampleAvailable}, ...]``。

    从 Python 出而不是在 QML 里硬编码：选项与素材的对应关系只有一份
    （:data:`SAMPLES`），加一档配音只需要改这个模块。
    """
    return [
        {"code": code, "name": name, "sampleAvailable": sample_available(code)}
        for code, name in LANGUAGES
    ]


#: 播放器的模块级单例。**必须**持有引用：``QMediaPlayer`` / ``QAudioOutput``
#: 一旦被 GC 回收，声音当场断（这是 QtMultimedia 最常见的「播一秒就停」来源）。
_player: Any = None
_audio: Any = None
_current_code: Optional[str] = None
#: 播放状态回调 ``(code, playing)``（bridge 拿来发信号给 QML 切图标）。
_state_callback: Optional[Callable[[str, bool], None]] = None

#: QtMultimedia 是否可用。缺包时**只**让试听失效，不影响整个设置页 / 应用 ——
#: 配音语言本身是配置项，读写在没有多媒体后端的环境里照样成立。
_MULTIMEDIA_OK = True


def _ensure_player() -> bool:
    global _player, _audio, _MULTIMEDIA_OK
    if _player is not None:
        return True
    if not _MULTIMEDIA_OK:
        return False
    try:
        from PySide6.QtCore import QUrl  # noqa: F401 - 仅探测可用性
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    except Exception:  # noqa: BLE001 - ImportError / 缺插件都算「没有多媒体」
        _MULTIMEDIA_OK = False
        log.warning("QtMultimedia 不可用，配音试听被禁用（配音语言配置本身不受影响）")
        return False
    _player = QMediaPlayer()
    _audio = QAudioOutput()
    _player.setAudioOutput(_audio)
    _audio.setVolume(1.0)
    _player.playbackStateChanged.connect(_on_playback_state)
    return True


def _on_playback_state(state: Any) -> None:
    """把 Qt 的播放状态翻成 ``(code, playing)`` 交给回调。

    ⚠️ 只认 ``PlayingState``：``StoppedState`` 与 ``PausedState`` 一律算「没在放」
    —— QML 那颗按钮只有两态（试听 / 停止），中间态没有必要暴露。
    """
    from PySide6.QtMultimedia import QMediaPlayer

    playing = state == QMediaPlayer.PlaybackState.PlayingState
    callback = _state_callback
    if callback is not None and _current_code is not None:
        try:
            callback(_current_code, playing)
        except Exception:  # noqa: BLE001 - 回调是 UI 侧，出问题不该断声音
            log.exception("配音试听状态回调异常")


def play_sample(code: Any, on_state: Optional[Callable[[str, bool], None]] = None) -> bool:
    """播放某个语种的示例音频，成功启动返回 True。

    失败（语种非法 / 素材缺失 / 没有多媒体后端）一律返回 False 且**不抛**：
    试听是锦上添花，不该让设置页报错。调用方（QML）拿返回值决定要不要提示。
    """
    global _current_code, _state_callback

    path = sample_path(code)
    if path is None:
        log.info("配音试听素材不存在: %r", code)
        return False
    if not _ensure_player():
        return False

    from PySide6.QtCore import QUrl

    _current_code = normalize(code)
    _state_callback = on_state
    _player.stop()
    _player.setSource(QUrl.fromLocalFile(str(path)))
    _player.play()
    return True


def stop_sample() -> None:
    """停止试听（用户再点一次那颗按钮）。"""
    global _current_code
    if _player is not None:
        _player.stop()
    _current_code = None
