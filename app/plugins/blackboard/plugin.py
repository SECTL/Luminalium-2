"""小黑板插件 —— 放映 / 讲课时的随手板书板。

2026-10-06 用户指令「做一个……小黑板」落地。窗口即一块可涂写的黑板
（粉笔色、三档笔宽、橡皮、撤销、清空），画布逻辑全在 QML 侧
（``Canvas`` + 笔画数组）：这是一只**普通自管窗口**，没有「重建销毁
QML 状态」的问题（``context.py`` 铁规 1 只约束挂进 dock 的驻留组件，
``rebuild_docks`` 不会碰插件窗口），所以笔画数据放 QML 侧是安全的；
Python 侧只负责注册（磁贴 / 控制条动作 / 窗口）与开关联动。

黑板色刻意**不跟随主题**（真黑板就该是深色板面，浅色主题下也一样），
粉笔色是配套的五支高饱和浅色。窗口标题栏照常由 RinUI 接管。

2026-10-08 板书导出 PNG（builtin-plugins-ux 计划 todo 5）：板书原本随
应用退出全丢，没有任何导出通道。落地方式 = 注册期建好
``data_dir()/exports/blackboard/``，把目录以 **file URL 根属性**
``exportDir`` 推给窗口（QML 侧 ``grabToImage`` 存图）。为什么用
「Python 推窗口根属性」而不是私开 context property / Backend 专用槽：
插件约定的反通道就这一条（计时器 ``_push_state`` 先例），私开接缝会
破坏插件的可卸载 / 可替换性；不弹系统文件对话框 —— 放映中弹对话框
就是教学事故，导出目录固定、文件名带时间戳，一键即成。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QUrl

from ...paths import UI_DIR, data_dir
from ... import i18n

log = logging.getLogger(__name__)

META = {
    "id": "blackboard",
    "name": "小黑板",
    "version": "1.0.0",
    "category": "subject",
    "icon": "./icon.png",
    "author": "Saskia",
}

#: 无设置项（板色 / 笔色是黑板的本体属性，不给配 —— 给了就是一块不是
#: 黑板的黑板）。保留键只为让「启用 / 禁用」语义照常成立。
DEFAULTS = {"enabled": True}

_window_handle: Optional[Any] = None

#: 板书导出目录（注册期建好；建目录失败时保持 None，QML 侧按钮维持禁用）。
_export_dir: Optional[Path] = None
#: 上次推给窗口的 exportDir 值（值没变不推，照 timer ``_last_pushed`` 先例）。
_last_pushed_dir: Optional[str] = None


def _push_export_dir() -> None:
    """把导出目录推给窗口根属性 ``exportDir``（file URL 字符串，带尾斜杠）。

    守卫与时序照计时器 ``_push_state`` 同款：句柄没注册 / 窗口没懒建
    出来就什么都不做；真正的兜底是 toggle / open 分支里 ``show()``
    返回**之后**的那次调用（首帧窗口已存在，属性一次到位）。
    """
    if _export_dir is None or _window_handle is None:
        return
    window = _window_handle.window
    if window is None:
        return
    # 尾斜杠让 QML 侧可以直接 ``exportDir + 文件名`` 拼接，不用关心分隔
    url = QUrl.fromLocalFile(str(_export_dir)).toString() + "/"
    global _last_pushed_dir
    if _last_pushed_dir == url:
        return
    try:
        window.setProperty("exportDir", url)
    except RuntimeError:  # 窗口正被销毁（理论不发生：只藏不销毁）
        return
    _last_pushed_dir = url


def _on_action(action: str) -> None:
    """``plugin:blackboard:`` 前缀动作：open / close / toggle。

    ⚠️ 只判 ``_window_handle is None``，**不判** ``.window``：窗口懒创建，
    首次 ``show()`` 前 ``.window`` 是 None，多查那一步会把唯一能触发创建
    的调用拦死（2026-10-07 计时器 / 小黑板「点了没反应」的根因，见
    ``timer/plugin.py`` 同款注释）。
    """
    if _window_handle is None:
        return
    if action == "plugin:blackboard:toggle":
        _window_handle.toggle()
        # show() 返回后窗口已建，补推一次导出目录（懒创建路径上首帧就拿到）
        _push_export_dir()
    elif action == "plugin:blackboard:open":
        _window_handle.show()
        _push_export_dir()
    elif action == "plugin:blackboard:close":
        _window_handle.hide()
    else:
        log.info("小黑板收到未知动作: %s", action)


def register(ctx) -> None:
    global _window_handle, _export_dir

    def tr(source: str) -> str:
        return i18n.tr("blackboard", source)

    # 导出目录在注册期建好（mkdir 幂等）：导出是「点一下立刻出文件」的
    # 高频课堂操作，不能等按下按钮那一刻才去碰文件系统；建目录失败在
    # register 期就 log，比按钮静默没反应好查得多。data_dir() 是函数
    # 调用（跟随 LUMINALIUM_DATA_DIR 覆盖），自检改环境变量即隔离。
    _export_dir = data_dir() / "exports" / "blackboard"
    try:
        _export_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log.exception("板书导出目录创建失败：%s", _export_dir)
        _export_dir = None

    # ⚠️ META["name"] 在这里才翻译（时序理由见 timer/plugin.py 同日注释）：
    # 模块 import 跑在翻译器安装之前，import 期的 i18n.tr 只能回中文原文。
    META["name"] = tr("小黑板")

    ctx.add_shortcut(
        "blackboard_panel", tr("小黑板"), "ic_fluent_board_20_regular",
        "plugin:blackboard:toggle",
    )
    ctx.add_action_handler("plugin:blackboard:", _on_action)
    ctx.add_dock_action(
        "plugin:blackboard:toggle", tr("小黑板"), "ic_fluent_board_20_regular",
        tooltip=tr("打开 / 收起小黑板"),
    )
    _window_handle = ctx.register_window(
        "blackboard", UI_DIR / "plugins" / "blackboard" / "BlackboardWindow.qml",
        label=tr("小黑板"),
    )
    log.info("小黑板插件已注册")
