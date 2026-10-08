"""小黑板插件 —— 放映 / 讲课时的随手板书板。

2026-10-06 用户指令「做一个……小黑板」落地。窗口即一块可涂写的黑板
（粉笔色、三档笔宽、橡皮、撤销、清空），画布逻辑全在 QML 侧
（``Canvas`` + 笔画数组）：这是一只**普通自管窗口**，没有「重建销毁
QML 状态」的问题（``context.py`` 铁规 1 只约束挂进 dock 的驻留组件，
``rebuild_docks`` 不会碰插件窗口），所以笔画数据放 QML 侧是安全的；
Python 侧只负责注册（磁贴 / 控制条动作 / 窗口）与开关联动。

黑板色刻意**不跟随主题**（真黑板就该是深色板面，浅色主题下也一样），
粉笔色是配套的五支高饱和浅色。窗口标题栏照常由 RinUI 接管。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ...paths import UI_DIR
from ... import i18n

log = logging.getLogger(__name__)

META = {
    "id": "blackboard",
    "name": "小黑板",
    "version": "1.0.0",
}

#: 无设置项（板色 / 笔色是黑板的本体属性，不给配 —— 给了就是一块不是
#: 黑板的黑板）。保留键只为让「启用 / 禁用」语义照常成立。
DEFAULTS = {"enabled": True}

_window_handle: Optional[Any] = None


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
    elif action == "plugin:blackboard:open":
        _window_handle.show()
    elif action == "plugin:blackboard:close":
        _window_handle.hide()
    else:
        log.info("小黑板收到未知动作: %s", action)


def register(ctx) -> None:
    global _window_handle

    def tr(source: str) -> str:
        return i18n.tr("blackboard", source)

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
