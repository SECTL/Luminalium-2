"""计时器的 WebView 宿主 —— 2026-10-17 用户指令「HTML 版计时器原汁原味搬过来」。

⚠️ 本模块是仓库两条硬规矩的**明文例外**，例外依据就是上面那条用户指令：

1. **网页前端**：``AGENTS.md`` 说「没有网页前端」，但计时器的 HTML 版
   （Lmn-copy ``plugins/builtins/timer/timer.html``）被要求原样保留，
   它只能跑在 QWebEngineView 里。本模块是把 HTML 跑起来的最小宿主，
   不是给项目引入通用 WebView 基建 —— 别的功能别学这里。
2. **Qt.FramelessWindowHint**：HTML 版计时器的标题栏是注入进页面的
   （``.title-bar``），原生标题栏必须摘掉，否则一页两个标题栏。
   这条例外只覆盖本模块的 ``TimerWebWindow``，QML 窗口的禁令不变。

移植自 Lmn-copy ``plugins/webview_runner.py``（217KB 的通用宿主）中计时器
实际用到的那部分：pywebview 兼容垫片（QWebChannel）、统一主题变量注入、
注入式标题栏（图标双击关闭 / 最小化 / 最大化 / 关闭）、WM_NCHITTEST 拖动
与无边框缩放、WM_NCCALCSIZE 去非客户区、迷你模式（340x400 右上角置顶
小窗）、页面后台保活（窗口只藏不销毁，藏起来的页面继续走表响铃）。
原项目里的 Linux 外挂进程模式、设置窗/引导窗专用分支、多主题包
（material-you 等 8 个本项目到不了的 ThemeId）没有带过来。

⚠️ 本模块的 QtWebEngine 导入发生在**模块级**，因此谁 import 它谁就拉起了
WebEngine —— ``plugin.py`` 故意在第一次开窗时才 import 本模块（已验证：
Qt 6.9 / Windows 上 QApplication 创建之后再初始化 WebEngine 可行，
tools 目录外的那段探针脚本跑出过 LOAD_FINISHED ok=True）。不要在
``register()`` 或模块顶层 import 本模块，否则全体用户启动白付
WebEngine 的初始化成本。
"""

from __future__ import annotations

import ctypes
import json
import logging
import sys
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QFile, QIODevice, QObject, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineScript,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ 主题


def _get_windows_dark_mode() -> bool:
    """读注册表拿 Windows 应用深浅色（Auto 模式用）。"""
    if sys.platform != "win32":
        return False
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
        return False


def resolve_theme_dark(theme_mode: str) -> bool:
    mode = str(theme_mode or "").strip().lower()
    if mode == "dark":
        return True
    if mode == "light":
        return False
    if mode == "auto":
        return _get_windows_dark_mode()
    return False


#: 统一主题变量表 —— 只留 ``default`` 一套（Luminalium 2 没有 ThemeId 概念，
#: 永远走 default；其余 8 套主题在本项目不可能被选中，没带过来）。
#: 变量值与 Lmn-copy ``_get_unified_theme_js`` 的 default 逐项一致。
_THEMES: Dict[str, Dict[str, Dict[str, str]]] = {
    "default": {
        "light": {
            "--bg-body": "transparent",
            "--bg-app": "#f7f8f9",
            "--bg-surface": "#ffffff",
            "--bg-color": "#ffffff",
            "--sidebar-bg": "#ffffff",
            "--border-color": "rgba(0,0,0,0.08)",
            "--text-primary": "#1a1c1e",
            "--text-secondary": "#5e6368",
            "--accent-blue": "#3275F5",
            "--divider": "rgba(0,0,0,0.08)",
            "--card-bg": "rgba(0,0,0,0.03)",
            "--card-border": "rgba(0,0,0,0.02)",
            "--item-hover": "rgba(0,0,0,0.05)",
            "--shadow-color": "rgba(0,0,0,0.06)",
            "--shadow-main": "0 4px 12px var(--shadow-color)",
            "--logo-glow": "rgba(50,117,245,0.1)",
            "--hyperos-g1": "#e0f2fe",
            "--hyperos-g2": "#fef9c3",
            "--hyperos-g3": "#fce7f3",
            "--hyperos-g4": "#d1fae5",
            "--hyperos-g5": "#ffffff",
            "--font-stack": '"Google Sans Flex","MiSans VF","Segoe UI",system-ui,-apple-system,sans-serif',
            "--font-weight-override": "400",
            "--overlay-toolbar-bg": "#FFFFFF",
            "--overlay-toolbar-border": "rgba(0,0,0,0.08)",
            "--overlay-toolbar-line": "rgba(0,0,0,0.08)",
            "--overlay-toolbar-shadow": "rgba(0,0,0,0.15)",
            "--overlay-toolbar-fg": "#191919",
            "--overlay-button-hover": "rgba(0,0,0,0.06)",
            "--overlay-button-active": "rgba(0,0,0,0.12)",
            "--overlay-status-bg": "rgba(0,0,0,0.25)",
            "--overlay-status-fg": "#FFFFFF",
            "--overlay-status-sep": "rgba(255,255,255,0.3)",
            "--overlay-popup-bg": "#FFFFFF",
            "--overlay-popup-border": "rgba(0,0,0,0.12)",
            "--overlay-popup-fg": "#191919",
            "--overlay-page-bg": "#FFFFFF",
            "--overlay-page-border": "rgba(0,0,0,0.08)",
            "--overlay-page-fg": "#191919",
            "--overlay-page-hint": "rgba(0,0,0,0.5)",
            "--overlay-page-hover": "rgba(0,0,0,0.05)",
            "--overlay-page-shadow": "rgba(0,0,0,0.15)",
            "--overlay-reload-mask": "rgba(0,0,0,0.43)",
            "--overlay-reload-card": "rgba(30,30,30,0.86)",
            "--overlay-reload-text": "rgba(255,255,255,0.92)",
            "--overlay-dev-watermark": "rgba(255,255,255,0.47)",
            "--text-inverse": "#FFFFFF",
            "--ring-bg": "rgba(0,0,0,0.05)",
            "--dialog-overlay": "rgba(0,0,0,0.4)",
            "--dialog-icon-bg": "#F2F7FF",
        },
        "dark": {
            "--bg-app": "#151515",
            "--bg-surface": "#1E1E1E",
            "--bg-color": "#1E1E1E",
            "--sidebar-bg": "#1E1E1E",
            "--border-color": "rgba(255,255,255,0.08)",
            "--text-primary": "#E5E5E5",
            "--text-secondary": "#909090",
            "--accent-blue": "#4A85F6",
            "--divider": "rgba(255,255,255,0.08)",
            "--card-bg": "rgba(255,255,255,0.03)",
            "--card-border": "rgba(255,255,255,0.02)",
            "--item-hover": "rgba(255,255,255,0.05)",
            "--shadow-color": "rgba(0,0,0,0.3)",
            "--shadow-main": "0 8px 32px var(--shadow-color)",
            "--logo-glow": "rgba(255,255,255,0.15)",
            "--hyperos-g1": "#1e293b",
            "--hyperos-g2": "#334155",
            "--hyperos-g3": "#1e1b4b",
            "--hyperos-g4": "#064e3b",
            "--hyperos-g5": "#0f172a",
            "--overlay-toolbar-bg": "#202020",
            "--overlay-toolbar-border": "rgba(255,255,255,0.08)",
            "--overlay-toolbar-line": "rgba(255,255,255,0.15)",
            "--overlay-toolbar-shadow": "rgba(0,0,0,0.31)",
            "--overlay-toolbar-fg": "#FFFFFF",
            "--overlay-button-hover": "rgba(255,255,255,0.08)",
            "--overlay-button-active": "rgba(255,255,255,0.15)",
            "--overlay-status-bg": "rgba(0,0,0,0.25)",
            "--overlay-status-fg": "#FFFFFF",
            "--overlay-status-sep": "rgba(255,255,255,0.3)",
            "--overlay-popup-bg": "#202020",
            "--overlay-popup-border": "rgba(255,255,255,0.18)",
            "--overlay-popup-fg": "#FFFFFF",
            "--overlay-page-bg": "#202020",
            "--overlay-page-border": "rgba(255,255,255,0.08)",
            "--overlay-page-fg": "#191919",
            "--overlay-page-hint": "rgba(255,255,255,0.6)",
            "--overlay-page-hover": "rgba(255,255,255,0.08)",
            "--overlay-page-shadow": "rgba(0,0,0,0.31)",
            "--overlay-reload-mask": "rgba(0,0,0,0.43)",
            "--overlay-reload-card": "rgba(30,30,30,0.86)",
            "--overlay-reload-text": "rgba(255,255,255,0.92)",
            "--overlay-dev-watermark": "rgba(255,255,255,0.47)",
            "--text-inverse": "#FFFFFF",
            "--ring-bg": "rgba(255,255,255,0.1)",
            "--dialog-overlay": "rgba(0,0,0,0.6)",
            "--dialog-icon-bg": "rgba(255,255,255,0.05)",
        },
    },
}

#: 主题 JS 的应用逻辑，与 Lmn-copy 的尾段逐字符一致（f-string 解成占位符
#: 拼接，避免 {} 转义失真）。读 window.initialSettings，把 default 主题的
#: CSS 变量铺到 :root，并打 data-theme / data-theme-variant / data-theme-id。
_THEME_TAIL = r"""(function(){var TD=__TD__;var SCENE=__SCENE__;function DFS(l){if(l==='zh-TW'||l==='ja-JP')return '\"Google Sans Flex\",\"MiSans Japanese VF\",\"MiSans TC VF\",\"Segoe UI\",system-ui,-apple-system,sans-serif';if(l==='ug-CN')return '\"Google Sans Flex\",\"Segoe UI\",\"MiSans VF\",system-ui,-apple-system,sans-serif';return '\"Google Sans Flex\",\"MiSans VF\",\"Segoe UI\",system-ui,-apple-system,sans-serif';}function GFS(s,l,sc){var f=s.Fonts;if(!f||!f.CustomFont)return '';var p=f.Profiles;if(!p||typeof p!=='object')return '';var lp=p[l];if(!lp||typeof lp!=='object')return '';var v=lp[sc];if(typeof v==='string'&&v.trim())return v.trim();return '';}function GFW(s,l,sc){var f=s.Fonts;if(!f||!f.CustomFont)return '';var w=f.Weights;if(!w||typeof w!=='object')return '';var lw=w[l];if(!lw||typeof lw!=='object')return '';var v=lw[sc];if(typeof v==='string'&&v.trim())return v.trim();if(sc==='overlay'){var v2=lw['web'];if(typeof v2==='string'&&v2.trim())return v2.trim();}return '';}function AT(){var r=document.documentElement;if(!r)return;var s=window.initialSettings||{};var a=s.Appearance||{};var d=a.ResolvedIsDark;var tid=a.ThemeId||'default';var v=d?'dark':'light';var b=TD['default'].light;for(var k in b)r.style.setProperty(k,b[k]);if(d){var db=TD['default'].dark;for(var k in db)r.style.setProperty(k,db[k]);}if(tid!=='default'&&TD[tid]&&TD[tid][v]){var t=TD[tid][v];for(var k in t)r.style.setProperty(k,t[k]);}r.style.setProperty('--accent-color','var(--accent-blue)');r.style.setProperty('--overlay-dialog-mask',d?'rgba(0,0,0,0.35)':'rgba(0,0,0,0.2)');r.style.setProperty('--overlay-dialog-shadow',d?'0 16px 40px rgba(0,0,0,0.45)':'0 12px 30px rgba(0,0,0,0.18)');r.style.setProperty('--overlay-dialog-bg','var(--overlay-popup-bg)');r.style.setProperty('--overlay-dialog-border','var(--overlay-popup-border)');r.style.setProperty('--overlay-dialog-title','var(--text-primary)');r.style.setProperty('--overlay-dialog-text','var(--text-secondary)');r.style.setProperty('--overlay-control-bg','var(--card-bg)');r.style.setProperty('--overlay-control-hover','var(--item-hover)');r.style.setProperty('--overlay-control-active','var(--overlay-button-active)');r.style.setProperty('--overlay-text-primary','var(--text-primary)');r.style.setProperty('--overlay-text-secondary','var(--text-secondary)');r.style.setProperty('--overlay-popup-shadow','none');r.style.setProperty('--overlay-thumb-bg',d?'var(--accent-blue)':'#FFFFFF');r.style.setProperty('--overlay-thumb-icon',d?'var(--bg-app)':'var(--accent-blue)');var lang=(s.General&&s.General.Language)||'zh-CN';var sel=GFS(s,lang,SCENE);var dfs=DFS(lang);var fs=sel?('\"'+sel.replace(/\"/g,'\\\"')+'\", '+dfs):dfs;r.style.setProperty('--font-stack',fs);var fw=GFW(s,lang,SCENE);if(fw){r.style.setProperty('--font-weight-override',fw);}else{r.style.removeProperty('--font-weight-override');}r.setAttribute('data-theme',d?'dark':'light');r.setAttribute('data-theme-variant',v);r.setAttribute('data-theme-id',tid);}if(document.documentElement){AT();}else{document.addEventListener('DOMContentLoaded',AT);}window.__applyUnifiedTheme=AT;})();"""


def build_theme_js() -> str:
    theme_json = json.dumps(_THEMES, ensure_ascii=False, separators=(",", ":"))
    scene_js = json.dumps("web")
    return _THEME_TAIL.replace("__TD__", theme_json).replace("__SCENE__", scene_js)


# ------------------------------------------------------------------ 垫片

_QWEBCHANNEL_JS_CACHE: Optional[str] = None


def _get_qwebchannel_js() -> str:
    """qwebchannel.js（Qt 资源里自带）+ pywebview 兼容垫片。

    timer.html 按 pywebview 的约定调 ``window.pywebview.api.*``（每个方法
    返回 Promise）；垫片用 Proxy 把调用转发到 QWebChannel 的 ``api`` 对象，
    并把回调包装成 Promise。与 Lmn-copy 同款，HTML 零修改的前提就是它。
    """
    global _QWEBCHANNEL_JS_CACHE
    if _QWEBCHANNEL_JS_CACHE is not None:
        return _QWEBCHANNEL_JS_CACHE

    js = ""
    f = QFile(":/qtwebchannel/qwebchannel.js")
    if f.open(QIODevice.OpenModeFlag.ReadOnly):
        try:
            js = f.readAll().data().decode("utf-8")
        except Exception:
            js = ""
        f.close()

    shim_js = """
    new QWebChannel(qt.webChannelTransport, function(channel) {
        window.pywebview = {
            api: new Proxy(channel.objects.api, {
                get: function(target, prop) {
                    return function(...args) {
                        return new Promise((resolve, reject) => {
                            target[prop](...args, function(result) {
                                resolve(result);
                            });
                        });
                    }
                }
            })
        };
        window.dispatchEvent(new Event('pywebviewready'));
    });
    """
    _QWEBCHANNEL_JS_CACHE = js + shim_js
    return _QWEBCHANNEL_JS_CACHE


# ------------------------------------------------------------------ Win32

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36
_DWM_COLOR_DEFAULT = 0xFFFFFFFF


def apply_window_theme(hwnd: int, is_dark: bool) -> None:
    """DWM 深色模式 + 边框/标题配色（无边框窗口也吃 immersive dark）。"""
    if not hwnd or sys.platform != "win32":
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        uxtheme = ctypes.windll.uxtheme
        user32 = ctypes.windll.user32
        val = ctypes.c_int(1 if is_dark else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
        )
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            _DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1,
            ctypes.byref(val),
            ctypes.sizeof(val),
        )
        if is_dark:
            border = ctypes.c_int(0x00202020)
            caption = ctypes.c_int(0x00202020)
            text = ctypes.c_int(0x00FFFFFF)
        else:
            border = ctypes.c_int(_DWM_COLOR_DEFAULT)
            caption = ctypes.c_int(_DWM_COLOR_DEFAULT)
            text = ctypes.c_int(_DWM_COLOR_DEFAULT)
        dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border)
        )
        dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption)
        )
        dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_TEXT_COLOR, ctypes.byref(text), ctypes.sizeof(text)
        )
        theme = "DarkMode_Explorer" if is_dark else "Explorer"
        uxtheme.SetWindowTheme(hwnd, ctypes.c_wchar_p(theme), None)
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0020
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except Exception:
        pass


def _remove_window_border(hwnd: int) -> None:
    """摘掉 Windows 硬塞给无边框窗口的残留边框样式（GWL_STYLE）。"""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
        style &= ~0x00800000  # WS_BORDER
        style &= ~0x00400000  # WS_DLGFRAME
        style &= ~0x00040000  # WS_SIZEBOX? 保留缩放交给 NCHITTEST —— 原版摘的是
        # WS_BORDER/WS_DLGFRAME/WS_THICKFRAME 三件（WS_THICKFRAME=0x00040000），
        # 摘了缩放框仍能缩放是因为 NCHITTEST 自己回了边缘热区。
        user32.SetWindowLongW(hwnd, -16, style)
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0020
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except Exception:
        pass


def remove_window_border_delayed(widget) -> None:
    """等窗口句柄完全落地后再摘边框（show 之前调用）。"""
    if sys.platform != "win32":
        return

    def _do_remove():
        try:
            hwnd = widget.winId()
            if hwnd:
                _remove_window_border(hwnd)
        except Exception:
            pass

    QTimer.singleShot(0, _do_remove)


# ------------------------------------------------------------------ 桥接


class TimerApi(QObject):
    """timer.html 的 ``window.pywebview.api`` 落地对象。

    方法集合 = HTML 实际调用全集（get_settings / get_version /
    get_timer_state / start_timer / pause_timer / resume_timer / stop_timer
    / finish_timer / add_time / update_timer / set_running / set_title /
    on_cancel / set_mini_mode / set_maximized / set_fullscreen /
    start_window_drag）外加注入标题栏要用的四个（minimize_window /
    toggle_maximize / close_window / get_window_title / get_window_icon_path）。
    """

    def __init__(
        self,
        timer_manager,
        settings_provider: Callable[[], Dict[str, Any]],
        version_provider: Callable[[], Dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self._window: Optional[TimerWebWindow] = None
        self._timer_manager = timer_manager
        self._settings_provider = settings_provider
        self._version_provider = version_provider

    def set_window(self, window: "TimerWebWindow") -> None:
        self._window = window

    def settings_snapshot(self) -> Dict[str, Any]:
        """窗口侧（非桥接）取当前设置快照，失败给空 dict。"""
        try:
            return self._settings_provider()
        except Exception:
            return {}

    # ---- 设置 / 版本 ----

    @Slot(result="QVariant")
    def get_settings(self):
        try:
            return self._settings_provider()
        except Exception:
            log.exception("get_settings 失败")
            return {}

    @Slot(result="QVariant")
    def get_version(self):
        try:
            return self._version_provider()
        except Exception:
            log.exception("get_version 失败")
            return {}

    # ---- 计时器状态（转发给后台引擎，语义与 Lmn-copy 一致）----

    @Slot(result="QVariant")
    def get_timer_state(self):
        m = self._timer_manager
        return {
            "remaining": int(m.remaining_seconds),
            "total": int(m.total_seconds),
            "is_running": bool(m.is_running),
        }

    @Slot(int)
    def start_timer(self, seconds):
        self._timer_manager.start(int(seconds))

    @Slot()
    def pause_timer(self):
        self._timer_manager.pause()

    @Slot()
    def resume_timer(self):
        self._timer_manager.resume()

    @Slot()
    def stop_timer(self):
        self._timer_manager.stop()

    @Slot()
    def finish_timer(self):
        self._timer_manager.finish()

    @Slot(int)
    def add_time(self, seconds):
        self._timer_manager.add_time(int(seconds))

    @Slot(int)
    def update_timer(self, total_seconds):
        self._timer_manager.update_time(int(total_seconds))

    @Slot(bool)
    def set_running(self, running):
        # HTML 上报自己的跑表状态（原项目用来切托盘文案）；本项目的宿主
        # 只记录不消费，留着接口免得 HTML 调用落空。
        pass

    # ---- 窗口控制 ----

    @Slot(str)
    def set_title(self, title):
        if self._window is not None:
            self._window.setWindowTitle(title)
            self._window.sync_title_bar_text()

    @Slot()
    def on_cancel(self):
        # HTML 的关闭请求（标题栏叉 / 迷你模式叉 / 退出确认框）一律落成
        # 「藏起来」—— 托盘常驻应用，窗口只藏不销毁，藏起来的页面继续走表。
        if self._window is not None:
            self._window.hide()

    @Slot(bool)
    def set_mini_mode(self, enabled):
        if self._window is not None:
            self._window.set_mini_mode(enabled)

    @Slot()
    def start_window_drag(self):
        if self._window is None:
            return
        try:
            hwnd = int(self._window.winId())
            ctypes.windll.user32.ReleaseCapture()
            ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF012, 0)
        except Exception:
            pass

    @Slot()
    def minimize_window(self):
        if self._window is None:
            return
        try:
            hwnd = int(self._window.winId())
            ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF020, 0)
        except Exception:
            pass

    @Slot()
    def toggle_maximize(self):
        if self._window is None:
            return
        try:
            hwnd = int(self._window.winId())
            if self._window.isMaximized():
                ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF120, 0)
            else:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF030, 0)
        except Exception:
            pass

    @Slot()
    def close_window(self):
        if self._window is not None:
            self._window.hide()

    @Slot(result=str)
    def get_window_title(self):
        try:
            if self._window is not None:
                return self._window.windowTitle()
        except Exception:
            pass
        return ""

    @Slot(result=str)
    def get_window_icon_path(self):
        try:
            from ...paths import RESOURCES_DIR

            svg = RESOURCES_DIR / "logo.svg"
            if svg.is_file():
                return str(svg).replace("\\", "/")
        except Exception:
            pass
        return ""


# ------------------------------------------------------------------ 窗口

#: 注入的标题栏样式（无边框模式）—— 与 Lmn-copy ``_inject_custom_border``
#: 的 frameless 分支一致；设置窗「日志」按钮的样式段没带过来。
_BORDER_CSS = """\
html, body {
    height: 100%;
    margin: 0;
    padding: 0;
}
body {
    box-sizing: border-box;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: flex-start;
}
.title-bar {
    display: none;
}
:root[data-frameless="true"] .title-bar {
    display: flex;
    align-items: center;
    height: 32px;
    background: var(--bg-app);
    user-select: none;
    flex-shrink: 0;
    position: relative;
    z-index: 100;
}
:root[data-frameless="true"][data-maximized="true"] .title-bar {
    height: 40px;
    margin: -7px -7px 0 -7px;
    padding-right: 7px;
}
:root[data-frameless="true"][data-maximized="true"] body {
    padding: 7px 7px 7px 7px;
}
.title-bar-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-left: 12px;
    margin-right: 8px;
    color: var(--text-primary);
    opacity: 0.7;
    z-index: 1;
    cursor: pointer;
    position: relative;
    -webkit-app-region: no-drag;
}
.title-bar-icon img {
    width: 16px;
    height: 16px;
}
.title-bar-icon-close-toast {
    position: absolute;
    left: calc(100% + 10px);
    top: 50%;
    transform: translateY(-50%);
    white-space: nowrap;
    background: rgba(30, 30, 30, 0.92);
    color: #fff;
    font-size: 12px;
    padding: 5px 14px;
    border-radius: 6px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
    z-index: 200;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}
:root[data-theme="dark"] .title-bar-icon-close-toast {
    background: rgba(60, 60, 60, 0.94);
}
.title-bar-icon-close-toast.show {
    opacity: 1;
}
.title-bar-title {
    position: absolute;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 12px;
    color: var(--text-primary);
    opacity: 0.8;
    cursor: default;
    pointer-events: none;
}
.title-bar-controls {
    display: flex;
    margin-left: auto;
    height: 100%;
}
.title-bar-btn {
    width: 46px;
    height: 100%;
    border: none;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-primary);
    border-radius: 0;
    padding: 0;
    transition: background 0.1s;
    -webkit-app-region: no-drag;
}
.title-bar-btn:hover {
    background: rgba(0, 0, 0, 0.08);
}
:root[data-theme="dark"] .title-bar-btn:hover {
    background: rgba(255, 255, 255, 0.08);
}
.title-bar-btn .title-bar-icon-glyph {
    font-family: "Segoe MDL2 Assets", sans-serif;
    font-size: 10px;
    line-height: 1;
}
:root[data-os="win11"] .title-bar-btn .title-bar-icon-glyph {
    font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets", sans-serif;
}
.title-bar-close:hover {
    background: #C42B1C !important;
    color: #fff !important;
}
"""

#: 注入的标题栏 DOM（图标 + 双击关闭提示 + 居中标题 + 三个控制钮）。
_TITLE_BAR_HTML = (
    '<div class="title-bar" id="title-bar">'
    '<div class="title-bar-icon" id="title-bar-icon">'
    '<div class="title-bar-icon-close-toast" id="title-bar-icon-close-toast">再次点击以关闭窗口</div>'
    "</div>"
    '<div class="title-bar-title" id="title-bar-text"></div>'
    '<div class="title-bar-controls">'
    '<button class="title-bar-btn" id="btn-minimize" title="最小化" onclick="window.pywebview.api.minimize_window()">'
    '<span class="title-bar-icon-glyph"></span>'
    "</button>"
    '<button class="title-bar-btn" id="btn-maximize" title="最大化" onclick="window.pywebview.api.toggle_maximize()">'
    '<span class="title-bar-icon-glyph"></span>'
    "</button>"
    '<button class="title-bar-btn title-bar-close" id="btn-close" title="关闭" onclick="window.pywebview.api.close_window()">'
    '<span class="title-bar-icon-glyph"></span>'
    "</button>"
    "</div>"
    "</div>"
)

#: 标题栏行为脚本：填充标题与图标、图标单击提示再点关闭。与原项目一致。
_TITLE_BAR_JS = (
    "(function(){"
    "function loadTitleBarInfo(){"
    "try{"
    "window.pywebview.api.get_window_title().then(function(t){"
    "var el=document.getElementById('title-bar-text');"
    "if(el&&t)el.textContent=t;"
    "});"
    "window.pywebview.api.get_window_icon_path().then(function(p){"
    "var el=document.getElementById('title-bar-icon');"
    "if(el&&p){"
    "var img=document.createElement('img');"
    "img.src='file:///'+p;"
    "img.alt='';"
    "el.appendChild(img);"
    "}"
    "});"
    "}catch(e){}"
    "}"
    "if(window.pywebview&&window.pywebview.api){loadTitleBarInfo();}"
    "else{window.addEventListener('pywebviewready',loadTitleBarInfo);}"
    "var _iconCloseTimer=null;"
    "var _iconClosePending=false;"
    "var _iconCloseIcon=document.getElementById('title-bar-icon');"
    "var _iconCloseToast=document.getElementById('title-bar-icon-close-toast');"
    "if(_iconCloseIcon&&_iconCloseToast){"
    "_iconCloseIcon.addEventListener('click',function(e){"
    "e.stopPropagation();"
    "if(_iconClosePending){"
    "clearTimeout(_iconCloseTimer);"
    "_iconCloseTimer=null;"
    "_iconClosePending=false;"
    "_iconCloseToast.classList.remove('show');"
    "window.pywebview.api.close_window();"
    "}else{"
    "_iconClosePending=true;"
    "_iconCloseToast.classList.add('show');"
    "_iconCloseTimer=setTimeout(function(){"
    "_iconClosePending=false;"
    "_iconCloseToast.classList.remove('show');"
    "_iconCloseTimer=null;"
    "},3000);"
    "}"
    "});"
    "}"
    "})()"
)


def _is_win11() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        build, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
        winreg.CloseKey(key)
        return int(build) >= 22000
    except Exception:
        try:
            return sys.getwindowsversion().build >= 22000
        except Exception:
            return False


class TimerWebWindow(QWebEngineView):
    """计时器的 WebView 窗口（无边框、只藏不销毁、页面后台保活）。

    标题栏 / 拖动 / 缩放全部按 Lmn-copy 的方式实现：标题栏是注入进页面的
    DOM，拖动与边缘缩放靠 ``nativeEvent`` 拦 WM_NCHITTEST 回答。
    """

    def __init__(
        self,
        title: str,
        html_path: str,
        api: TimerApi,
        width: int,
        height: int,
        settings: Dict[str, Any],
    ):
        super().__init__()
        self.api = api
        self.api.set_window(self)
        self.setWindowTitle(title)

        self._mini_mode = False
        self._pre_mini_geometry = None
        self._pre_mini_was_maximized = False
        self._pre_mini_was_fullscreen = False
        self._is_fullscreen = False
        self._render_crash_count = 0
        self._max_reload_attempts = 3

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        remove_window_border_delayed(self)
        self.resize(width, height)
        self._center_on_screen()

        # 页面设置：本地 HTML 要读 file:// 资源（系统铃声 wav）与跑脚本
        page = QWebEnginePage(self)
        self.setPage(page)
        page_settings = page.settings()
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True
        )
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True
        )
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.AutoLoadImages, True
        )
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.PluginsEnabled, False
        )
        page_settings.setAttribute(
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True
        )

        self.channel = QWebChannel(self)
        self.channel.registerObject("api", api)
        page.setWebChannel(self.channel)

        # 注入：垫片（DocumentCreation，保证早于页面脚本）、初始设置、主题变量
        script = QWebEngineScript()
        script.setSourceCode(_get_qwebchannel_js())
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        page.scripts().insert(script)

        settings_script = QWebEngineScript()
        settings_script.setSourceCode(
            "window.initialSettings = "
            + json.dumps(settings, ensure_ascii=False)
            + ";"
        )
        settings_script.setInjectionPoint(
            QWebEngineScript.InjectionPoint.DocumentCreation
        )
        settings_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        page.scripts().insert(settings_script)

        theme_script = QWebEngineScript()
        theme_script.setSourceCode(build_theme_js())
        theme_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        theme_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        page.scripts().insert(theme_script)

        # 边框/标题栏样式（DocumentReady 时以 <style> 注入）
        os_tag = "win11" if _is_win11() else "win10"
        border_js = (
            "(function() {"
            "var style = document.createElement('style');"
            "style.textContent = "
            + json.dumps(_BORDER_CSS)
            + ";"
            "if (document.documentElement) {"
            "document.documentElement.appendChild(style);"
            "document.documentElement.setAttribute('data-frameless', 'true');"
            "document.documentElement.setAttribute('data-os', '"
            + os_tag
            + "');"
            "}"
            "})();"
        )
        border_script = QWebEngineScript()
        border_script.setSourceCode(border_js)
        border_script.setInjectionPoint(
            QWebEngineScript.InjectionPoint.DocumentReady
        )
        border_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        page.scripts().insert(border_script)

        self.loadFinished.connect(self._on_load_finished)
        self.windowTitleChanged.connect(lambda _t: self.sync_title_bar_text())
        self.renderProcessTerminated.connect(self._on_render_process_terminated)

        self._apply_page_background()
        self.load(QUrl.fromLocalFile(html_path))

    # ---- 主题 / 外观 ----

    def _effective_is_dark(self) -> bool:
        try:
            appearance = self.api.settings_snapshot().get("Appearance", {})
        except Exception:
            appearance = {}
        return bool(appearance.get("ResolvedIsDark", False))

    def _apply_page_background(self) -> None:
        if self._mini_mode:
            self.page().setBackgroundColor(Qt.transparent)
            return
        is_dark = self._effective_is_dark()
        self.page().setBackgroundColor(
            QColor(24, 24, 24) if is_dark else QColor(255, 255, 255)
        )

    def apply_settings(self, settings: Dict[str, Any]) -> None:
        """外部（主题 / 语言 / 音效开关变化）推新设置进来：重铺 CSS 变量。"""
        self._apply_page_background()
        apply_window_theme(int(self.winId()), self._effective_is_dark())
        try:
            self.page().runJavaScript(
                "try{"
                "window.initialSettings = "
                + json.dumps(settings, ensure_ascii=False)
                + ";"
                "if(window.__applyUnifiedTheme)window.__applyUnifiedTheme();"
                "}catch(e){}"
            )
        except Exception:
            pass

    def sync_title_bar_text(self) -> None:
        try:
            self.page().runJavaScript(
                "try{"
                "var el=document.getElementById('title-bar-text');"
                "if(el)el.textContent="
                + json.dumps(self.windowTitle(), ensure_ascii=False)
                + ";"
                "}catch(e){}"
            )
        except Exception:
            pass

    # ---- 加载 ----

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            log.warning("计时器页面加载失败（loadFinished ok=False）")
            return
        self._render_crash_count = 0
        self._apply_page_background()
        apply_window_theme(int(self.winId()), self._effective_is_dark())
        self._inject_title_bar_html()
        self._inject_title_bar_js()
        self._push_maximized_state()
        self.sync_title_bar_text()

    def _on_render_process_terminated(self, status, code) -> None:
        # 渲染进程崩了自动重载，最多 3 次（原项目同款兜底）
        self._render_crash_count += 1
        if self._render_crash_count <= self._max_reload_attempts:
            log.warning(
                "计时器渲染进程终止（%s/%s），重载", status, code
            )
            QTimer.singleShot(300, self.reload)

    def _inject_title_bar_html(self) -> None:
        js = (
            "(function(){"
            "var tb=document.getElementById('title-bar');"
            "if(!tb){"
            "var d=document.createElement('div');"
            "d.innerHTML="
            + json.dumps(_TITLE_BAR_HTML, ensure_ascii=False)
            + ";"
            "var el=d.firstChild;"
            "document.body.insertBefore(el,document.body.firstChild);"
            "}"
            "})()"
        )
        self.page().runJavaScript(js)

    def _inject_title_bar_js(self) -> None:
        self.page().runJavaScript(_TITLE_BAR_JS)

    def _set_custom_title_bar_visible(self, visible: bool) -> None:
        display = "flex" if visible else "none"
        try:
            self.page().runJavaScript(
                "(function(){"
                "var tb=document.getElementById('title-bar');"
                "if(tb)tb.style.display="
                + json.dumps(display)
                + ";"
                "})()"
            )
        except Exception:
            pass

    def _push_maximized_state(self) -> None:
        try:
            maximized = "true" if self.isMaximized() else "false"
            icon_text = json.dumps("" if self.isMaximized() else "")
            self.page().runJavaScript(
                "try{"
                "document.documentElement.setAttribute('data-maximized','"
                + maximized
                + "');"
                "var b=document.getElementById('btn-maximize');"
                "if(b){var s=b.querySelector('.title-bar-icon-glyph');"
                "if(s)s.textContent="
                + icon_text
                + ";}"
                "}catch(e){}"
            )
        except Exception:
            pass

    # ---- 窗口模式 ----

    def set_mini_mode(self, enabled: bool) -> None:
        """迷你模式：340x400 右上角置顶小窗（尺寸与位置同 Lmn-copy）。"""
        if self._mini_mode == enabled:
            return
        self._mini_mode = enabled
        if enabled:
            self._pre_mini_was_maximized = bool(self.isMaximized())
            self._pre_mini_was_fullscreen = bool(self.isFullScreen() or self._is_fullscreen)
            try:
                if self._pre_mini_was_maximized or self._pre_mini_was_fullscreen:
                    self._pre_mini_geometry = self.normalGeometry()
                else:
                    self._pre_mini_geometry = self.geometry()
            except Exception:
                self._pre_mini_geometry = None
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            remove_window_border_delayed(self)
            self.resize(340, 400)
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(geo.x() + geo.width() - 340 - 20, geo.y() + 20)
            self._set_custom_title_bar_visible(False)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            remove_window_border_delayed(self)
            restored = False
            geo = self._pre_mini_geometry
            if geo is not None:
                try:
                    if geo.width() > 0 and geo.height() > 0:
                        self.setGeometry(geo)
                        restored = True
                except Exception:
                    restored = False
            if self._pre_mini_was_maximized:
                self.showMaximized()
                restored = True
            elif self._pre_mini_was_fullscreen:
                self.set_fullscreen(True)
                restored = True
            elif not restored:
                self.resize(800, 600)
                self._center_on_screen()
            self._pre_mini_geometry = None
            self._pre_mini_was_maximized = False
            self._pre_mini_was_fullscreen = False
            self._set_custom_title_bar_visible(True)
        self._apply_page_background()
        self.show()

    def set_fullscreen(self, enabled: bool) -> None:
        # 无边框 + WM_NCCALCSIZE 清零的窗口，showFullScreen 能真正盖住任务栏
        self._is_fullscreen = bool(enabled)
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def set_maximized(self, enabled: bool) -> None:
        if enabled:
            if self._is_fullscreen:
                self.set_fullscreen(False)
            self.showMaximized()
        else:
            if self._is_fullscreen:
                self.set_fullscreen(False)
            else:
                self.showNormal()
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass
        self._push_maximized_state()

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    # ---- 关窗 = 藏起来（托盘常驻应用，窗口只藏不销毁）----

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        # 最大化 / 还原后同步标题栏高度与按钮图标
        try:
            self._push_maximized_state()
        except Exception:
            pass

    # ---- 拖动与缩放：拦 WM_NCHITTEST；WM_NCCALCSIZE 清零去非客户区 ----

    def nativeEvent(self, eventType, message):
        try:
            import ctypes.wintypes

            msg_ptr = int(message)
            if not msg_ptr:
                return super().nativeEvent(eventType, message)
            msg = ctypes.wintypes.MSG.from_address(msg_ptr)

            if msg.message == 0x0084:  # WM_NCHITTEST
                pos = self.mapFromGlobal(QCursor.pos())
                x, y = pos.x(), pos.y()
                w, h = self.width(), self.height()

                title_bar_h = 40 if self.isMaximized() else 32
                # 三个控制钮各 46px：右侧 138px 让给按钮（点击要进页面）
                btn_area_left = w - 138

                title_bar_visible = (
                    not self._mini_mode and not self._is_fullscreen
                )
                # 左侧图标区域交给页面（单击图标弹「再次点击关闭」提示）：
                # 12px 左边距 + 16px 图标 + 8px 右边距 ≈ 36px
                if title_bar_visible and y < title_bar_h and x < 36:
                    return True, 1  # HTCLIENT

                if title_bar_visible and y < title_bar_h and x < btn_area_left:
                    return True, 2  # HTCAPTION（拖动摇晃窗口）

                if (
                    not self.isMaximized()
                    and not self.isFullScreen()
                    and not self._is_fullscreen
                ):
                    border = 8
                    is_left = x < border
                    is_right = x > w - border
                    is_top = y < border
                    is_bottom = y > h - border
                    if is_top and is_left:
                        return True, 13
                    elif is_top and is_right:
                        return True, 14
                    elif is_bottom and is_left:
                        return True, 16
                    elif is_bottom and is_right:
                        return True, 17
                    elif is_left:
                        return True, 10
                    elif is_right:
                        return True, 11
                    elif is_top:
                        return True, 12
                    elif is_bottom:
                        return True, 15

            if msg.message == 0x0083:  # WM_NCCALCSIZE
                if msg.wParam:
                    # 无边框：客户区 = 整个窗口；最大化时钳到工作区，
                    # 否则内容会盖到任务栏底下。
                    class RECT(ctypes.Structure):
                        _fields_ = [
                            ("left", ctypes.c_long),
                            ("top", ctypes.c_long),
                            ("right", ctypes.c_long),
                            ("bottom", ctypes.c_long),
                        ]

                    class NCCALCSIZE_PARAMS(ctypes.Structure):
                        _fields_ = [
                            ("rgrc", RECT * 3),
                            ("lppos", ctypes.c_void_p),
                        ]

                    params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
                    monitor = ctypes.windll.user32.MonitorFromWindow(msg.hWnd, 1)
                    if monitor:
                        class MONITORINFO(ctypes.Structure):
                            _fields_ = [
                                ("cbSize", ctypes.c_uint),
                                ("rcMonitor", RECT),
                                ("rcWork", RECT),
                                ("dwFlags", ctypes.c_uint),
                            ]

                        mi = MONITORINFO()
                        mi.cbSize = ctypes.sizeof(MONITORINFO)
                        if ctypes.windll.user32.GetMonitorInfoW(
                            monitor, ctypes.byref(mi)
                        ):
                            new_w = params.rgrc[0].right - params.rgrc[0].left
                            new_h = params.rgrc[0].bottom - params.rgrc[0].top
                            mon_w = mi.rcMonitor.right - mi.rcMonitor.left
                            mon_h = mi.rcMonitor.bottom - mi.rcMonitor.top
                            if new_w >= mon_w and new_h >= mon_h:
                                params.rgrc[0].left = mi.rcWork.left
                                params.rgrc[0].top = mi.rcWork.top
                                params.rgrc[0].right = mi.rcWork.right
                                params.rgrc[0].bottom = mi.rcWork.bottom
                    return True, 0
        except Exception:
            pass
        return super().nativeEvent(eventType, message)
