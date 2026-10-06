"""Luminalium 2 插件系统 —— 贡献点注册表（代码侧唯一事实来源）。

设计约定（2026-10-05 插件系统计划 Wave 1 任务 1）：

1. **绝不落盘**：注册表里的条目全部来自代码（内置贡献 + 插件 ``register()``
   调用），运行期聚合后即冻结，不写进 config/config.json，也不从配置读回。
   原因：配置层是「用户可改的值」，注册表是「存在哪些东西」，两者混写会
   让卸载插件后残留死条目。

2. **加载期只写、冻结后只读**：所有 ``add_*`` 只能在 ``freeze()`` 之前调用，
   冻结后再写直接抛 ``RuntimeError``。这把「谁先注册谁后注册」的顺序依赖
   从根上消灭 —— 消费端（bridge / windows / application）只在冻结后读，
   拿到的一定是全量聚合结果，不存在「读早了少一半条目」的窗口期。

3. **列表型贡献禁止注入 config 默认层**：shortcut_catalog / presentation.tools /
   presentation.actions / Settings.qml navigationItems 这些消费端都是**列表**，
   而 Config._deep_merge 对列表是**整体替换**（用户层有值就盖掉默认层整段）。
   若把插件贡献写进默认配置，用户一旦改过一次快捷方式，插件条目就会被
   用户层的旧列表整体顶掉，表现为「插件装了但磁贴不出现」。所以列表合并
   必须在读取侧做纯拼接（config 列表 + 注册表列表），绝不能走默认层。

4. **条目形状与消费端严格对齐**，读取时纯拼接、无需转换：
   - 快捷方式磁贴 ↔ ``config/default_config.json`` 的 ``quick_panel.shortcut_catalog``
   - 放映工具 / 动作 ↔ ``presentation.tools`` / ``presentation.actions``
   - 设置页 ↔ ``Settings.qml`` 的 ``navigationItems``（QML 侧键名是 ``page``，
     这里存 ``page_url`` 是为了和 config 里的 ``settings/<页>.qml`` 相对路径
     语义区分开，读取合并时由消费端做一次键名映射，拼接本身仍是无逻辑的）
   - 扁平设置键 ↔ ``bridge.py`` 的 ``SETTING_PATHS``（含 notify / side_effect）

5. **零依赖**：本模块不 import bridge / windows / application / config，
   只含纯数据结构，保证任何模块在任何时机都能安全 import 它。

6. **翻译约定（2026-10-05 插件系统 Wave 2 任务 15）**：插件文案分两类走
   两条路——
   - 插件 QML（``ui/plugins/<id>/``）里的静态文案直接 ``qsTr("中文原文")``，
     ``tools/update_translations.py`` 的 lupdate 会扫 ``ui/`` 整树自动收录；
   - 经 Python 喂给 QML 的动态字符串（设置导航标题、快捷磁贴 ``title``、
     编辑器组 ``display_name`` 等注册表条目的展示文案）用
     ``app.i18n.tr(context, source)`` 标注，译文手工维护进
     ``translations/luminalium_py_*.ts``（lupdate 不碰 Python 侧，AGENTS.md
     明令）。``context`` 建议用插件 id，避免与内置 context 撞名。
   两侧 ts 由 lrelease 合并成同一个 ``luminalium_<lang>.qm`` 加载。
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, Mapping

__all__ = [
    "add_shortcut",
    "add_action_handler",
    "add_dock_tool",
    "add_dock_action",
    "add_settings_page",
    "add_setting_path",
    "add_editor_group",
    "add_window_spec",
    "register_plugin_defaults",
    "freeze",
    "is_frozen",
    "shortcuts",
    "action_handlers",
    "dock_tools",
    "dock_actions",
    "settings_pages",
    "setting_paths",
    "editor_groups",
    "window_specs",
    "plugin_defaults",
]

_frozen = False

# —— 八个贡献点注册表（加载期只写，冻结后只读）——

# 快捷面板磁贴：id → {id, title, icon, iconSource?, action}
# 形状对齐 quick_panel.shortcut_catalog；action 语法见 config 注释，
# 插件动作统一走 "plugin:<plugin_id>:<动作名>" 前缀（由 _action_handlers 消费）。
_shortcuts: dict[str, dict[str, Any]] = {}

# 动作动词前缀 → callable：application.py 分发动作时先查注册表再回落内置分支，
# 插件的 "plugin:<id>:xxx" 动作在这里按动词段登记处理器。
_action_handlers: dict[str, Callable[..., Any]] = {}

# 放映控制条工具 / 动作：id → {id, label, icon, tooltip?}
# 形状对齐 presentation.tools / presentation.actions，读取时与 config 列表拼接。
_dock_tools: dict[str, dict[str, Any]] = {}
_dock_actions: dict[str, dict[str, Any]] = {}

# 设置页：id → {title, page_url, icon, position?}
# 对齐 Settings.qml navigationItems 的 {title, page, icon, position}（page ← page_url）。
_settings_pages: dict[str, dict[str, Any]] = {}

# 扁平设置键 → {path, notify, side_effect}
# 对齐 bridge.SETTING_PATHS 的合并目标形状，让 QML 用同一个键读写插件设置。
_setting_paths: dict[str, dict[str, Any]] = {}

# 编辑器分组：组名 → {dock_qml?, display_name, icon, inspector_items, traits}
# 主界面编辑器按组聚合可编辑组件，插件可新增自己的组。
_editor_groups: dict[str, dict[str, Any]] = {}

# 窗口规格：名 → {qml_path, options}
# windows.py 懒创建窗口时按规格建，插件窗口与内置窗口走同一条路径。
_window_specs: dict[str, dict[str, Any]] = {}

# 插件配置默认值：plugin_id → 扁平 dict（键即 "plugins.<id>.*" 下的相对路径）。
# 供 Config 注入钩子消费（钩子由 Wave 1 并行任务实现，接口以 plugin_defaults() 为准）。
_plugin_defaults: dict[str, dict[str, Any]] = {}


def _ensure_writable() -> None:
    if _frozen:
        raise RuntimeError(
            "插件注册表已冻结：所有注册必须在加载期（freeze() 之前）完成"
        )


def _put(table: dict[str, Any], kind: str, key: str, value: Any) -> None:
    """统一写入入口：先查冻结，再查重复 id。

    重复 id 抛 ValueError 而不是静默覆盖 —— 静默覆盖会让两个插件抢同一个
    id 时后写的赢、先写的凭空消失，排查极难；直接报错逼插件改名。
    """
    _ensure_writable()
    if key in table:
        raise ValueError(f"{kind} 注册重复 id: {key!r}")
    table[key] = value


def add_shortcut(entry: dict[str, Any]) -> None:
    """注册快捷面板磁贴，形状 {id, title, icon, iconSource?, action}。"""
    _put(_shortcuts, "shortcut", entry["id"], entry)


def add_action_handler(verb: str, handler: Callable[..., Any]) -> None:
    """注册动作动词前缀处理器（如 "plugin:_demo" → callable）。"""
    _put(_action_handlers, "action_handler", verb, handler)


def add_dock_tool(entry: dict[str, Any]) -> None:
    """注册放映控制条工具，形状 {id, label, icon, tooltip?}。"""
    _put(_dock_tools, "dock_tool", entry["id"], entry)


def add_dock_action(entry: dict[str, Any]) -> None:
    """注册放映控制条动作，形状 {id, label, icon, tooltip?}。"""
    _put(_dock_actions, "dock_action", entry["id"], entry)


def add_settings_page(entry: dict[str, Any]) -> None:
    """注册设置页，形状 {title, page_url, icon, position?}（须有 id 键）。"""
    _put(_settings_pages, "settings_page", entry["id"], entry)


def add_setting_path(key: str, spec: dict[str, Any]) -> None:
    """注册扁平设置键 → {path, notify, side_effect}，并入 bridge 读写链路。"""
    _put(_setting_paths, "setting_path", key, spec)


def add_editor_group(name: str, group: dict[str, Any]) -> None:
    """注册编辑器分组 → {dock_qml?, display_name, icon, inspector_items, traits}。"""
    _put(_editor_groups, "editor_group", name, group)


def add_window_spec(name: str, spec: dict[str, Any]) -> None:
    """注册窗口规格 → {qml_path, options}，供 WindowManager 懒创建。"""
    _put(_window_specs, "window_spec", name, spec)


def register_plugin_defaults(plugin_id: str, defaults: dict[str, Any]) -> None:
    """收集插件 ``plugins.<id>.*`` 的默认配置 dict（相对键 → 默认值）。

    只收集、不立即注入 —— 真正的注入由 Config 的默认值钩子做（Wave 1 并行
    任务），这样默认值聚合顺序与 Config 实例化时机解耦。同一插件重复注册
    同样按重复 id 报错（一个插件的默认值只能声明一次）。
    """
    _put(_plugin_defaults, "plugin_defaults", plugin_id, defaults)


def freeze() -> None:
    """冻结注册表：此后所有 add_* 抛 RuntimeError，访问器可以安全读取。"""
    global _frozen
    _frozen = True


def is_frozen() -> bool:
    return _frozen


def _ro(table: dict[str, Any]) -> Mapping[str, Any]:
    """返回浅层只读视图。

    拷贝一层再包 MappingProxyType：直接对活表包代理会漏（冻结前写入仍可见），
    拷一层保证消费端拿到的快照不受后续意外改动影响；值本身是 dict 不深拷，
    因为约定消费端只读、条目形状在注册时就已定型。
    """
    return MappingProxyType(dict(table))


def shortcuts() -> Mapping[str, dict[str, Any]]:
    return _ro(_shortcuts)


def action_handlers() -> Mapping[str, Callable[..., Any]]:
    return _ro(_action_handlers)


def dock_tools() -> Mapping[str, dict[str, Any]]:
    return _ro(_dock_tools)


def dock_actions() -> Mapping[str, dict[str, Any]]:
    return _ro(_dock_actions)


def settings_pages() -> Mapping[str, dict[str, Any]]:
    return _ro(_settings_pages)


def setting_paths() -> Mapping[str, dict[str, Any]]:
    return _ro(_setting_paths)


def editor_groups() -> Mapping[str, dict[str, Any]]:
    return _ro(_editor_groups)


def window_specs() -> Mapping[str, dict[str, Any]]:
    return _ro(_window_specs)


def plugin_defaults() -> dict[str, Any]:
    """聚合全部插件默认值，返回 ``{"plugins": {<id>: {...}, ...}}`` 形状。

    返回的是普通 dict 副本而非只读视图：Config 注入钩子要把它当普通配置
    段去 merge，只读代理会在 merge 路径上碍事。
    """
    return {"plugins": {pid: dict(d) for pid, d in _plugin_defaults.items()}}
