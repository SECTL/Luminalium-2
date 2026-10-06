"""插件系统验收夹具 ``_demo``（2026-10-05 插件系统计划 Wave 3 任务 12）。

⚠️ **本插件组（``_demo`` + ``_demo_dep``）是框架验收夹具**：存在的唯一目的是把
``PluginContext`` 的全部 8 个 API、通信总线与依赖声明各真用一遍，让 QA 脚本
（``.omo/evidence/task-12-demo-qa.py``）有东西可断言。**禁止在此实现任何真实
功能**（计时器 / 小黑板 / 聚焦一概不许），UI 全部占位级（一个标题一行字一个开关）。

门控：本插件**不进** ``app.plugins.PLUGINS``；``_`` 前缀目录由
``loader.load_plugins(..., include_debug=True)``（门控来源 ``app.debug`` 配置键，
默认关）时才追加加载。``DEFAULTS`` 只是形状演示 —— 调试插件的默认值**不走**
阶段一注入（``loader.py`` 头注释明令：调试夹具不该污染正式配置默认层），所以
debug 关闭时 ``plugins._demo.*`` 连默认值都不存在。

关窗链路（**插件窗口的标准关窗路径**，供未来插件参照）：
``DemoWindow.qml`` 的 ``onClosing`` → ``Backend.triggerAction("plugin:_demo:close")``
→ 任务 6 的 ``plugin:`` 特权通道 → 动词注册表最长前缀匹配 → 下面的
``_on_action`` → ``register_window`` 句柄 ``hide()``。这是唯一不依赖 Backend
专用槽（如 ``closeSettings``）的通用关窗通道。

文案约定：夹具文案直接写中文字面量（``add_shortcut`` / ``add_settings_page`` 的
``title`` 等）。正式插件应走 ``app.i18n.tr(<插件id>, ...)``（约定见
``app/plugins/registry.py`` 头注释第 6 条），夹具不翻。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ...paths import UI_DIR

log = logging.getLogger(__name__)

META = {"id": "_demo"}

#: 形状演示：正式插件的 ``plugins.<id>.*`` 默认值经它进配置默认层；
#: 调试夹具不走阶段一注入（见模块头注释），这份声明只给「DEFAULTS 常量
#: 存在且形状合法」一个可断言的实体。
DEFAULTS = {"flag": False, "note": "演示"}

#: ``register`` 期捕获的宿主引用。PluginContext 刻意不提供公共 Backend
#: 访问器（插件与宿主的通道收束到 8 个 API）；夹具要经 ``Backend.setSetting``
#: 写键供 smoke / QA 断言总线与动作链路，作为同仓库装配层代码走内部引用
#: （与 ``loader`` 读 ``backend._config`` 同级）。真实插件不该学这一招。
_backend: Optional[Any] = None
#: ``ctx.register_window`` 返回的句柄，动作处理器靠它显隐夹具窗口。
_window_handle: Optional[Any] = None


def _on_action(action: str) -> None:
    """``plugin:_demo:`` 前缀的动作处理器：按动作串后缀分发。"""
    if action == "plugin:_demo:open":
        if _window_handle is not None:
            _window_handle.show()
    elif action == "plugin:_demo:ping":
        # 写标志位供 smoke / QA 断言动作通道端到端（dock 动作与磁贴动作同源）。
        if _backend is not None:
            _backend.setSetting("plugins__demo_note", "ping")
    elif action == "plugin:_demo:close":
        if _window_handle is not None:
            _window_handle.hide()
    else:
        log.info("夹具收到未知动作: %s", action)


def _on_hello(payload: Any) -> None:
    """``_demo_dep:hello`` 的订阅处理器：把 payload 写进 ``plugins._demo.note``。

    供 smoke / QA 断言总线端到端与拓扑序（``_demo_dep`` 依赖 ``_demo``，
    它发布时本订阅必须已就绪）。
    """
    if _backend is not None:
        _backend.setSetting("plugins__demo_note", payload)


def register(ctx) -> None:
    """依次调用 PluginContext 全部 8 个 API（顺序即验收清单顺序）。"""
    global _backend, _window_handle
    _backend = ctx._backend

    # ① 快捷面板磁贴
    ctx.add_shortcut(
        "_demo_panel", "演示", "ic_fluent_beaker_20_regular", "plugin:_demo:open"
    )
    # ② 动作动词前缀处理器
    ctx.add_action_handler("plugin:_demo:", _on_action)
    # ③④ 放映控制条工具 / 动作
    ctx.add_dock_tool("plugin:_demo:tool", "演示工具", "ic_fluent_beaker_20_filled")
    ctx.add_dock_action("plugin:_demo:ping", "演示动作", "ic_fluent_beaker_20_filled")
    # ⑤ 设置页
    ctx.add_settings_page(
        "_demo_page", "演示插件", "DemoSettings.qml", "ic_fluent_beaker_20_regular"
    )
    # ⑥ 扁平设置键（QML 侧 Backend.settings.<key> 读写）
    ctx.register_setting("plugins__demo_flag", "plugins._demo.flag")
    ctx.register_setting("plugins__demo_note", "plugins._demo.note")
    # ⑦ 主界面编辑器分组（含一条检查器开关描述符）
    ctx.add_editor_group(
        "_demo_group",
        display_name="演示组件",
        icon="ic_fluent_beaker_20_filled",
        inspector_items=[
            {"key": "plugins__demo_flag", "kind": "switch", "title": "演示开关"}
        ],
    )
    # ⑧ 自管窗口（只注册不 show，显示时机由动作处理器决定）
    _window_handle = ctx.register_window(
        "demo", UI_DIR / "plugins" / "_demo" / "DemoWindow.qml", label="演示夹具窗口"
    )

    # 通信总线：订阅 _demo_dep 的问候（拓扑序保证它发布时本订阅已就绪）
    ctx.subscribe("_demo_dep:hello", _on_hello)
