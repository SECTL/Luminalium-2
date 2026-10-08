"""QML 桥接层。

QML 只依赖这里暴露的属性与槽函数，不直接触碰配置、Win32 或 PowerPoint 细节。
新增功能时通常只需要：加一个 ``Slot`` + 在 QML 里连上按钮。

2026-10-05：设置系统改成「内建常量 + 动态注册」双轨。加一个设置项仍然是
「加一行」—— 内建项写进 ``SETTING_PATHS`` 常量（副作用按下面的两级表登记），
插件项走 :meth:`Backend.register_setting_path` 运行时注册。插件键命名约定
``plugins_<id>_<name>``：既不会撞内建键，也不会误中 ``presentation_`` 前缀
广播规则。``setSetting`` 的副作用不再是硬编码 if/elif，而是两级查找：
① 键级回调表（精确命中，可带 side_effect）② 前缀 / 集合规则表（按前缀发
整块配置变更信号）。未注册的键照旧被日志丢弃。

2026-10-05（插件系统 Wave 2 任务 5）：快捷面板磁贴目录改成**双来源** ——
config 的 ``quick_panel.shortcut_catalog`` 内建条目 ∪ ``app.plugins.registry``
的插件磁贴，在 :meth:`Backend._catalog` 这个唯一读取点做纯拼接（插件追加在
内建之后，同名 id 内建胜出并记 warning）。合并绝不写回 config：配置层只存
用户启用 / 排序的 id 列表（``quick_panel.shortcuts``），目录内容不落盘是
铁律 —— 列表若走 config 默认层会被用户层的旧列表整体顶掉（详见
``app/plugins/registry.py`` 头注释第 3 条）。

2026-10-05（插件系统 Wave 2 任务 6）：控制条 tools/actions 同样双来源 ——
``presentationConfig`` 返回**深拷贝**后的合并结果（内建数组在前，
``registry.dock_tools()`` / ``dock_actions()`` 的插件条目追加在后，id 冲突
内建胜出）。必须深拷贝的为什么：``Config.get("presentation")`` 返回的是配置
对象的**内部引用**，直接往里 append 会把插件贡献写进 config 内存态 —— 这既
违反「插件贡献不落盘也不进 config 内存态」的铁律，还会让每次读取重复追加
同一条目。拷贝后合并，配置层永远干净、每次读取都是全量重算。QML 零改动：
PresentationDock 的 Repeater 本就遍历这两个数组，插件贡献自动出现。
``selectTool`` 对 ``plugin:`` 前缀的工具 id 不进白名单、不调 ``ppt.set_tool``，
改按动作处理（emit ``actionTriggered``），由应用层的 ``plugin:`` 特权通道
分发给插件处理器 —— 插件工具与 COM / 按键注入零接触。

2026-10-05（插件系统 Wave 2 任务 7）：设置窗口左侧导航同样改成数据驱动 ——
原 ``ui/Settings.qml`` 里硬编码的 ``navigationItems`` 逐字搬进
``_BUILTIN_SETTINGS_NAV``，与 ``registry.settings_pages()`` 的插件设置页在
:meth:`Backend._get_settings_nav_items` 拼接（内建在前、插件在后）后作为
``settingsNavItems`` 属性喂给 QML。搬到 Python 的原因：QML 的静态列表属性
拼不了运行时数据，且动态条目的标题 ``qsTr`` 翻译不了（``qsTr`` 只认字面量），
必须走 ``app.i18n.tr``。条目形状、顺序、「关于 / 更新」钉底部的语义全部照旧。

2026-10-05（插件系统 Wave 3 任务 17）：设置窗口新增内建「插件」管理页 ——
``pluginItems`` 属性把 ``app.plugins.loader.loaded_plugins()`` 的加载清单
合成成 QML 可消费的列表（id / 标题 / 版本 / 启用态 / 调试标记 / 加载结果 /
跳过原因），``setPluginEnabled`` 槽写 ``plugins.<id>.enabled`` 配置（与
``setSetting`` 同一条「改内存 + 防抖落盘」路径）。**只改配置、不做任何
动态增删**：启用 / 禁用重启后生效是唯一语义 —— 注册表在加载期末冻结
（``registry.freeze()`` 后任何 ``add_*`` 抛 RuntimeError），窗口又全是
懒创建只藏不销毁，实时反注册与这两个架构前提直接打架，所以本进程内
永不触碰已加载的插件。架构原因同步写在 ``ui/settings/Plugins.qml``
头注释里。

2026-10-06（用户指令「给插件系统添加外部导入插件功能」）：管理页再加
外部插件的「导入 / 删除」。导入 = 用户经原生文件对话框选中插件文件夹 /
zip，由 ``app/plugins/external.py`` 校验后拷贝进用户插件目录 —— 校验
阶段就会执行插件顶层代码（META 无法静态读，见该文件头注释第 3 条），
本进程不做任何注册，重启后由 loader 扫描加载，与启用 / 禁用同语义。
删除 = 只删用户插件目录里的安装副本（用户手里的原始文件不动），并清掉
``plugins.<id>`` 配置子树防残留。结果统一经 ``pluginManageResult`` 信号
回 QML 显示。
"""

from __future__ import annotations

import copy
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication

from . import autostart
from . import i18n
from . import monitors
from . import update_checker
from .config import Config
from .paths import RESOURCES_DIR, UI_DIR
from .plugins import external, loader, registry
from .ppt_controller import PresentationState

log = logging.getLogger(__name__)

#: 设置窗口里可改的项：QML 用的扁平键 -> 配置里的点号路径。
#: 加新开关时**只在这里加一行**，QML 侧用 ``Backend.settings.<扁平键>`` 读、
#: ``Backend.setSetting("<扁平键>", 值)`` 写。
SETTING_PATHS: Dict[str, str] = {
    "theme": "app.theme",
    "accent": "app.accent",
    "language": "app.language",
    "log_level": "app.log_level",
    # ⚠️ ``autostart`` 是**特例**：它的本体是 Windows 注册表（见 ``app/autostart.py``），
    #    配置里的 ``app.autostart`` 只是给日志 / 排查看的一份影子。读写两边都走
    #    注册表 —— ``_get_settings`` 每次回读真实状态，``setSetting`` 也单独分叉
    #    （见 :meth:`Backend._apply_autostart`），不走下面通用的「改内存 + 延迟落盘」。
    "autostart": "app.autostart",
    # ⚠️ ``tray.enabled`` / ``tray.tooltip`` / ``tray.show_on_click`` /
    #    ``tray.notify_on_start`` **没有**登记在这里，配置里的 ``tray`` 段也已删除：
    #    2026-10-01（第二轮）用户指令「托盘整组连着相关的逻辑和代码一块删掉」。
    #    现在托盘是**恒定行为**（常驻 + 提示文字取 app.name + 左键开面板 + 启动不弹
    #    气泡，见 ``application.py::_boot_tray/_boot_ready`` 与 ``TrayIcon``），
    #    没有可配置的路。
    # ⚠️ ``quick_panel.hide_on_deactivate`` 同理删除：失焦收起是**默认行为**
    #    （``windows.py::_on_panel_active_changed`` 恒定生效）。
    "panel_shortcuts_locked": "quick_panel.shortcuts_locked",
    "panel_section_shortcuts": "quick_panel.sections.shortcuts",
    "panel_section_footer": "quick_panel.sections.footer",
    "presentation_poll_interval_ms": "presentation.poll_interval_ms",
    "presentation_margin_x": "presentation.margin_x",
    "presentation_margin_y": "presentation.margin_y",
    "presentation_bar_height": "presentation.bar_height",
    # 控制条组件的整体缩放倍率（设置 → 主界面 → 「缩放大小」）。0.5~2.0 的**小数**
    # （滑块按整数百分比走，写回时再除 100）—— 见 default_config.json 的 ``presentation.scale``。
    "presentation_scale": "presentation.scale",
    "presentation_buttons_show_labels": "presentation.buttons.show_labels",
    "presentation_pager_position": "presentation.pager.position",
    "presentation_screen_index": "presentation.screen_index",
    # 钉屏显示器的稳定 id（``QScreen.name()``）。空串 = 走 ``screen_index`` 的旧
    # 语义（-1 跟随 / >=0 索引）；非空时优先。2026-10-08 新增，见
    # ``app/monitors.py`` 与 ``default_config.json`` 的 ``//screen_name``。
    "presentation_screen_name": "presentation.screen_name",
    "presentation_shadow_enabled": "presentation.surface.shadow.enabled",
    "presentation_surface_opacity": "presentation.surface.opacity",
    # ⚠️ ``presentation.divider.enabled`` / ``presentation.pager.enabled`` **没有**
    #    登记在这里：这两个开关 2026-10-01 按用户指令从界面上删除了（配置键仍
    #    生效、默认 true，只是改成纯配置项 —— 想关就在 config/config.json 里写）。
    #    登记进来的话 QML 侧会多一份没人读的代理属性，反而看不出它已经没有界面。
    "presentation_exit_style": "presentation.exit.style",
    # 墨迹引擎（self = 自建墨迹 / com = PowerPoint·WPS 自带放映笔）。值变了由
    # ``application.py`` 挂在 ``Config.on_change`` 上的监听器即时改道（放映中
    # 切换也生效），这里只负责让 QML 能读写；设置页入口在计划 self-ink 第 9 项。
    "presentation_ink_engine": "presentation.ink.engine",
    # 橡皮子模式（stroke = 整笔 / pixel = 像素）与手掌擦除开关、阈值（毫米）。
    # 2026-10-07 自建批注（计划 self-ink 第 9 项）：控制条橡皮卡片写前一个，设置页
    # 「主界面 → 墨迹」写后两个；擦除行为本身由第 8 项在 InkLayer 侧消费。
    "presentation_ink_eraser_mode": "presentation.ink.eraser_mode",
    "presentation_ink_palm_erase": "presentation.ink.palm_erase",
    "presentation_ink_palm_threshold_mm": "presentation.ink.palm_threshold_mm",
    # ⚠️ ``presentation.pen.widths`` / ``default_width``（2026-10-07 自建批注的
    #    笔粗细档）与 ``presentation.ink.eraser_widths`` / ``eraser_default_width``
    #    （2026-10-08 的像素橡皮粗细档）刻意**不**登记：与 ``pen.palette`` 同一条
    #    链路 —— QML 经 ``presentationConfig`` 整块读，选中值是**会话状态**
    #    （``_pen_width`` / ``_eraser_width``，不落配置，与 ``_pen_color`` 同读法）。
    #    登记进来只会多一份没人写的代理属性（上面 ``presentation.divider.enabled``
    #    的反面教材）。
    # 只在调试窗口出现（隐藏入口：设置标题连点 10 次），普通用户看不到水印开关
    "dev_watermark": "app.dev_watermark",
    # 更新模式 / 更新通道（设置 → 更新 → 更新设置）。⚠️ ``update.`` 段里其余的键
    # （last_status / last_check_time）**没有**登记在这里：它们是程序自己写的
    # 检查记录，不给设置页当输入 —— 登记了反而会多出一组没人写的代理属性。
    "update_mode": "update.mode",
    "update_channel": "update.channel",
}

#: 值一变就需要 QML 重新取整块配置的键。
_BROADCAST_KEYS = {"panel_section_shortcuts", "panel_section_footer"}

#: 键级副作用回调的签名：``(config, 扁平键, 新值)``。config 在前是因为这类回调
#: 十有八九是「再连带改几个配置键」（比如翻页组件位置 → corners）；要发信号的
#: 场景走 ``notify`` 信号名，不必在回调里碰 Backend。
SettingSideEffect = Callable[["Config", str, Any], None]

#: 副作用第二级：前缀规则表。扁平键命中前缀即发对应的整块配置变更信号
#: （``(信号名, 是否带 str(值) 作为参数)``）。``presentation_`` 前缀：控制条
#: 外观 / 几何变了；改 ``presentation_screen_index`` 会换一块显示器，还没放映
#: 过时 ``presentationScreen`` 是按配置现算的，所以连 ``presentationScreenChanged``
#: 一起发，给它一个重取的理由。
_PREFIX_NOTIFY_RULES: Tuple[Tuple[str, Tuple[Tuple[str, bool], ...]], ...] = (
    (
        "presentation_",
        (("presentationConfigChanged", False), ("presentationScreenChanged", False)),
    ),
)

#: 键级副作用条目的结构：``signals`` 为 ``(信号名, 是否带值)`` 列表，
#: ``side_effect`` 为可选回调（见 ``SettingSideEffect``）。
_KeyEffect = Dict[str, Any]
#: 改完**必须重启才生效**的设置项（扁平键）。
#:
#: 改动这些项时走 :meth:`Backend._notify_restart_required`：① ``restartPending``
#: 翻 true → 设置窗口标题栏右侧亮出强调色「需要重启」按钮；② 发 ``restartSuggested``
#: → 设置窗口弹对话框问「现在重启吗」。
#:
#: 参考 ClassIsland（``ClassIsland/Views/SettingsWindowNew.axaml{,.cs}``）。那边是::
#:
#:     private void CommandBindingRestartApp_OnExecuted(...)
#:     {
#:         ViewModel.IsRequestedRestart = true;   // → 标题栏亮出「需要重启」按钮
#:         ShowRestartDialog();                   // → 弹框问「现在重启吗」
#:     }
#:
#: ⚠️ ClassIsland **自己并不会在设置变更时自动弹框** —— 它订阅了
#: ``SettingsService.Settings.PropertyChanged``，而 ``SettingsOnPropertyChanged``
#: 是**空方法**；也没有任何「哪些设置要重启」的清单或 ``[RequiresRestart]`` 标记。
#: 它只是把「需要重启」当成通用提示，靠用户自己去点标题栏那枚按钮。
#:
#: 所以这里做了两点适配：
#: ① 触发点从「用户点按钮」挪到 ``setSetting`` —— 用户的原话是「对需要重新启动
#:   才能应用的设置项**更改时**做出行动」，条件本来就是「某项设置变了」，
#:   由 QML 逐项去想起来发命令，迟早会有页面忘了发；
#: ② 清单由 Python 侧集中维护（就是下面这个 frozenset），而不是散在各页面里。
#:
#: **入选理由（``language``）**：翻译（``app/i18n.py::install_translators`` 装载
#: ``luminalium_*.qm``）与 UI 字体（``apply_ui_font``，``ja_JP`` 切 Yu Gothic UI）
#: 都在 ``application.py`` 里装配**一次**，之后没有任何重新装配的路径。
#:
#: ⚠️ **刻意没收 ``dev_watermark``**：它经 ``Backend.devWatermark``（``constant=True``）
#: 出给 QML，窗口构造时求值一次 → 改完确实是「老窗口不变、新窗口跟着变」的半吊子
#: 状态。但它只在隐藏的调试窗口里出现，每拨一次就弹一次框太吵（且重启与否都存在
#: 半生效的部分），所以留着不动，等真要给这个开关做热更新时再一起解决。
RESTART_REQUIRED_KEYS: frozenset = frozenset({
    "language",
})

#: 「翻页组件位置」的两种形态 -> 该形态下**启用**的角落。
#:
#: 改这一项会连带开关 ``corners`` 里对应的四个角：真实生效的仍是 ``corners``
#: （``windows.py::_load_docks`` 与编辑器预览都只读它），``pager.position``
#: 只是它的人话开关 —— 两种形态二选一，同时开会变成四个翻页栏。
PAGER_POSITION_CORNERS: Dict[str, tuple] = {
    "side": ("middle_left", "middle_right"),
    "bottom": ("bottom_left", "bottom_right"),
}

#: RinUI ``Position`` 枚举里 ``Bottom`` 的整数值（``utils/Position.qml``：
#: Top=0, Bottom=1）。经 QVariant 递到 QML 后是 JS number，
#: ``NavigationBar.qml`` 的 ``item.position === Position.Bottom`` 严格比较成立；
#: 不写 ``position`` 键的条目在 QML 侧读为 ``undefined``，按 NavigationBar 的
#: 判定落入普通区（不钉底）。
_RIN_POSITION_BOTTOM = 1

#: 设置窗口左侧导航的**内建**条目：``(ui/ 下相对页路径, 标题原文, 图标, position)``。
#:
#: 2026-10-05（插件系统 Wave 2 任务 7）从 ``ui/Settings.qml`` 的硬编码
#: ``navigationItems`` **逐字**搬来 —— 标题、图标、页面、顺序、「关于 / 更新」
#: 钉底部的语义全部照旧。搬到 Python 的原因见文件头注释。
#:
#: ⚠️ ``page`` 最终必须是 **file:/// 绝对 URL**：RinUI ``NavigationView`` 用
#: ``Qt.createComponent`` 加载页面，相对路径会以 RinUI 模块自身为基准而解析失败
#: （原 ``Settings.qml`` 头注释里记过的坑）。URL 在这里拼好成品，QML 侧零拼接。
#:
#: 条目的历史沿革（从被删的 QML 注释留档）：
#: - 「通用」：2026-10-01 原挂在它下面的子项「快捷面板」删除后成为叶子节点；
#:   同日第四轮「应用主题 / 强调色」搬去「个性化」，本页只留「快捷方式锁定」
#:   +「界面语言」两张卡。
#: - 「个性化」：2026-10-01（第四轮）新建，承接「应用主题」「强调色」两张卡；
#:   插在「通用」之后、「主界面」之前 —— 它调的是**整个应用**的取色，层级更高。
#: - 「主界面」：2026-10-01 由「外观」改名而来，原页的主题 / 强调色 / 界面语言
#:   三张卡挪走；本页专放主界面自己的设定（可视化编辑在独立的
#:   MainInterfaceEditor 窗口）。
_BUILTIN_SETTINGS_NAV: Tuple[Tuple[str, str, str, Optional[int]], ...] = (
    ("settings/Home.qml", "主页", "ic_fluent_home_20_regular", None),
    ("settings/General/Index.qml", "通用", "ic_fluent_settings_20_regular", None),
    (
        "settings/Personalization.qml",
        "个性化",
        "ic_fluent_paint_brush_20_regular",
        None,
    ),
    ("settings/MainInterface.qml", "主界面", "ic_fluent_window_20_regular", None),
    # 「插件」：2026-10-05（插件系统 Wave 3 任务 17）新增的管理页（启用 / 禁用
    # 开关，重启生效）。内建页而非插件贡献 —— 管理插件的界面本身不能依赖
    # 插件系统注册（禁用全部插件后管理入口不能跟着消失）。排在「主界面」之后、
    # 钉底部的「关于 / 更新」之前，属普通区。
    ("settings/Plugins.qml", "插件", "ic_fluent_puzzle_piece_20_regular", None),
    ("settings/About.qml", "关于", "ic_fluent_info_20_regular", _RIN_POSITION_BOTTOM),
    (
        "settings/Update.qml",
        "更新",
        "ic_fluent_arrow_sync_20_regular",
        _RIN_POSITION_BOTTOM,
    ),
)


class Backend(QObject):
    """面向 QML 的应用后端。"""

    #: 设置项写盘的合并窗口（ms）。滑块拖动 / SpinBox 连点会连续改值，
    #: 这段窗口内的多次改动只落一次盘。
    _SAVE_DEBOUNCE_MS = 400

    # ---- 通知类信号 ----
    presentationActiveChanged = Signal()
    slideChanged = Signal()
    #: 幻灯片缩略图表变了（某几张就绪 / 整场复位，见 ``thumbUrls``）
    slideThumbsChanged = Signal()
    activeToolChanged = Signal()
    #: 墨迹颜色变了（QML 侧的笔选单靠它回显选中的那一格）
    penColorChanged = Signal()
    #: 笔的粗细变了（笔选单「粗细」一行靠它回显选中的那一档；2026-10-07 自建批注）
    penWidthChanged = Signal()
    #: 像素橡皮的粗细变了（橡皮卡片「粗细」一行靠它回显；2026-10-08 自建批注）
    eraserWidthChanged = Signal()
    shortcutsChanged = Signal()
    presentationConfigChanged = Signal()
    #: 编辑器分组清单变了（注册表 ``editor_groups()`` 的列表视图）。
    #: 注册时机固定在窗口加载期（``windows.py::_register_builtin_groups``），
    #: 早于任何 QML 窗口创建，属性现算现读即可；Wave 3 loader 冻结后若出现
    #: 运行期注册，再由任务 11 补发这个信号。
    presentationGroupsChanged = Signal()
    presentationScreenChanged = Signal()
    #: 显示器名单变了（热插拔）。``monitorList`` 属性现算现读，只在插拔时
    #: 需要喊一声让下拉重取（2026-10-08「目标显示器」逐台列出）。
    monitorListChanged = Signal()
    quickPanelConfigChanged = Signal()
    settingsChanged = Signal()
    #: 设置窗口导航清单变了（插件设置页注册进 ``registry.settings_pages()``）。
    #: 注册时机固定在加载期（冻结前），早于任何 QML 窗口创建，属性现算现读即可；
    #: 若将来出现运行期注册，由注册方负责发这个信号。
    settingsNavItemsChanged = Signal()
    #: 插件管理页列表变了（``setPluginEnabled`` 改完 ``plugins.<id>.enabled``
    #: 之后发）。加载清单本身只在加载期产生一次，运行期唯一会变的就是
    #: 各项的 ``enabled``，所以只有这个槽会发它。
    pluginItemsChanged = Signal()
    #: 插件导入 / 删除的结果（``ok, 人话消息``）—— ``importPluginFolder`` /
    #: ``importPluginZip`` / ``removePlugin`` 统一经它回 QML 显示。
    pluginManageResult = Signal(bool, str)
    statusChanged = Signal()
    #: 启动画面的进度 / 阶段文字变了
    splashChanged = Signal()
    #: 检查更新的状态机动了（详见下方「检查更新」一节）。
    updateStatusChanged = Signal()
    updateWorkingChanged = Signal()

    # ---- 请求类信号（由窗口管理器 / 应用层响应）----
    panelHideRequested = Signal()
    shortcutTriggered = Signal(str)
    actionTriggered = Signal(str)
    #: 重启整个程序（快捷面板底栏的「重启」按钮）：由应用层拉起新进程后退出。
    #: 原 ``reloadRequested``（仅重读配置）已按 2026-10-02 用户指令改成重启 ——
    #: 用户语义里这个按钮就该是「重启程序」，只重读配置反而「点了没反应」。
    restartRequested = Signal()
    #: 改了一项「要重启才生效」的设置（见 ``RESTART_REQUIRED_KEYS``）→ 设置窗口
    #: 弹对话框问「现在重启吗」（ClassIsland 的 ``ShowRestartDialog()`` 同款）。
    #: ⚠️ 与 ``restartRequested`` 是两回事：那个是**真的去重启**，这个是**提示**。
    restartSuggested = Signal()
    #: ``restartPending`` 变了。
    restartPendingChanged = Signal()
    quitRequested = Signal()
    settingsRequested = Signal()
    settingsCloseRequested = Signal()
    #: 调试窗口（隐藏入口：设置窗口标题连点 10 次）
    debugWindowRequested = Signal()
    debugWindowCloseRequested = Signal()
    #: 主界面编辑器（入口：快捷面板的「主界面编辑器」快捷方式）
    editorRequested = Signal()
    editorCloseRequested = Signal()
    themeChangeRequested = Signal(str)
    accentChangeRequested = Signal(str)
    #: 启用 / 停用的角落集合变了（翻页组件位置切换）：控制条**换了一组组件**，
    #: 光挪位置不够，得按新的角落重建（``windows.py::rebuild_docks``）。
    docksRebuildRequested = Signal()

    def __init__(self, config: Config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config

        self._presentation_active = False
        self._slide_index = 0
        self._slide_total = 0
        #: 幻灯片缩略图缓存（``app/slide_thumbs.py``）。由 ``application.py`` 在
        #: 播完 COM 控制器之后接上（``attach_slide_thumbs``）—— 预览 / 自检这类
        #: 只造 Backend 的宿主没有它，此时 ``thumbUrls`` 是空表、请求静默忽略。
        self._slide_thumbs = None
        #: 默认工具是**鼠标指针**（``arrow``）。
        #:
        #: ⚠️ 2026-10-01 用户指令「顶层窗口的工具栏的 Segmented 默认工具不应该
        #: 是鼠标指针吗？」—— 这里原本是 ``pen``，与配置里 ``presentation.tools``
        #: 的排布意图（``arrow`` 放第一个，见该段注释）自相矛盾：控制条一出来
        #: 就高亮着「笔」，用户得先点一下指针才能正常放映，等于默认把放映
        #: 变成书写。默认必须是「什么都不做」的那个工具。
        self._active_tool = "arrow"
        #: 墨迹颜色（``#RRGGBB``）。空串 = 还没有选过 —— QML 侧据此决定
        #: 哪一格点亮（见 :meth:`setPenColor`）。
        self._pen_color = ""
        #: 笔的粗细（逻辑 px）。0 = 还没选过 —— QML 侧此时点亮配置里的
        #: ``presentation.pen.default_width``（见 :meth:`setPenWidth`）。
        self._pen_width = 0.0
        #: 像素橡皮的粗细（逻辑 px）。0 = 还没选过 —— QML 侧此时点亮配置里的
        #: ``presentation.ink.eraser_default_width``（见 :meth:`setEraserWidth`，
        #: 2026-10-08 自建批注）。与笔宽同为会话状态，不落配置。
        self._eraser_width = 0.0
        self._status_text = ""

        #: 有没有「改了但要重启才生效」的设置（见 ``RESTART_REQUIRED_KEYS``）。
        #: 一旦翻 true 就**不再复位**（ClassIsland 的 ``IsRequestedRestart`` 同样只
        #: 置位）：用户把值改回原样也当作改过 —— 判断「有没有绕过」的成本远高于
        #: 多显示一个按钮，而重启一次本来也没有副作用。
        self._restart_pending = False

        #: 启动画面进度（0..1）与阶段文字。由应用层按真实里程碑推进
        #: （见 ``application.py::LuminaliumApplication._boot_*``）。
        self._splash_progress = 0.0
        self._splash_stage = ""

        #: 已启用的快捷方式 id（顺序即显示顺序）
        self._shortcut_ids: List[str] = [
            str(item) for item in (config.get("quick_panel.shortcuts", []) or [])
        ]

        #: ``WindowManager`` 推来的**真实**放映显示器几何（顶层窗口铺在哪块屏）。
        #: None 表示还没有放映过，此时 :meth:`_get_presentation_screen` 自己按
        #: 配置索引兜底。见 ``syncPresentationScreen``。
        self._overlay_screen: Optional[Dict[str, Any]] = None

        #: 设置项的**延迟落盘**（见 :meth:`setSetting`）。
        #:
        #: ``Config.set(persist=True)`` 会把整份用户配置重写一遍 —— 滑块拖一次
        #: 会发几十个 ``moved``，逐个落盘就是几十次磁盘写。这里改成「先改内存、
        #: 停手 ``_SAVE_DEBOUNCE_MS`` 之后再写一次」。进程正常退出时
        #: ``application.quit()`` 还会补一次 ``config.save()``，不会丢。
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(self._SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._config.save)

        # 显示器热插拔：作废 ``app/monitors.py`` 的枚举缓存并喊一声，让
        # 「目标显示器」下拉重取名单。QGuiApplication 尚未建好（纯脚本宿主）
        # 时跳过 —— 那种宿主本来也读不到显示器。
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._on_monitors_changed)
            app.screenRemoved.connect(self._on_monitors_changed)

        #: 「关于」页两条**异步**链路的后台线程（取回声洞句子 / 采集诊断信息）。
        #: 只为「同一件事不并发第二次」而持有；线程本身是 daemon，退出即回收。
        self._echo_thread: Optional[threading.Thread] = None
        self._diagnostics_thread: Optional[threading.Thread] = None
        #: 检查更新的后台线程（同上，见 :meth:`requestCheckUpdate`）。
        self._update_thread: Optional[threading.Thread] = None

        # ------------------------------------------------ 检查更新的状态机
        #:
        #: 对齐 ClassIsland ``UpdateService`` 的两组状态：
        #:
        #: * ``_update_status`` —— 上次检查的结论，对应它的 ``UpdateStatus``：
        #:   ``uptodate`` / ``available``（+ 部署环节的 ``updatedownloaded`` /
        #:   ``updatedeployed``，部署未实现、预留）＋ 本项目自己的 ``unknown``
        #:   （本次运行还没查过）。ClassIsland 把它持久化在 Settings 里，
        #:   这里同样落 ``update.last_status``。
        #: * ``_update_working`` —— 正在干什么，对应 ``UpdateWorkingStatus``：
        #:   目前只有 ``idle`` / ``checking``（下载 ``downloading`` /
        #:   部署 ``extracting`` 随部署一起接入）。
        self._update_status = str(self._config.get("update.last_status", "")
                                  or update_checker.STATUS_UNKNOWN)
        self._update_working = "idle"
        self._update_latest_version = ""
        self._update_changelog = ""
        self._update_current_changelog = ""
        self._update_release_url = ""
        self._update_error = ""

        # ---- 设置项注册表（内建常量 + 动态注册）----
        #: 动态注册的「扁平键 -> 点号路径」（插件走 ``register_setting_path``）。
        #: 与 ``SETTING_PATHS`` 合成视图见 :meth:`_setting_paths` —— 内建优先，
        #: 动态注册同名键会被拒绝，防插件顶掉内建行为。
        self._dynamic_paths: Dict[str, str] = {}
        #: 副作用第一级：键级回调表（精确命中优先于前缀规则）。内建特例原样
        #: 登记在这里，行为与重构前的硬编码 if/elif 完全一致：
        #: - ``presentation_pager_position``：连带开关四个角落（两种形态二选一，
        #:   见 ``PAGER_POSITION_CORNERS`` 处的说明）—— 真实生效的是 ``corners``，
        #:   所以这一步不是「副作用」而是这个开关的本体；角落集合变了控制条得按
        #:   新角落重建（``docksRebuildRequested``）。
        #: - ``theme`` / ``accent``：各自带值发请求信号，由应用层真正换肤。
        self._key_effects: Dict[str, _KeyEffect] = {
            "presentation_pager_position": {
                "signals": [("docksRebuildRequested", False)],
                "side_effect": lambda config, key, value: self._apply_pager_position(
                    str(value)
                ),
            },
            "theme": {"signals": [("themeChangeRequested", True)], "side_effect": None},
            "accent": {"signals": [("accentChangeRequested", True)], "side_effect": None},
        }


    # ==================================================================== 常量

    @Property(str, constant=True)
    def appName(self) -> str:
        return str(self._config.get("app.name", "Luminalium 2"))

    @Property(str, constant=True)
    def appVersion(self) -> str:
        from . import __version__

        return __version__

    @Property(bool, notify=restartPendingChanged)
    def restartPending(self) -> bool:
        """有没有「改了但要重启才生效」的设置（见 ``RESTART_REQUIRED_KEYS``）。

        设置窗口靠它决定标题栏右侧那枚「需要重启」按钮显不显示
        （ClassIsland 的 ``ViewModel.IsRequestedRestart`` 同款）。
        """
        return self._restart_pending

    @Property(str, constant=True)
    def accent(self) -> str:
        return str(self._config.get("app.accent", "#4CC2FF"))

    @Property(str, constant=True)
    def uiDir(self) -> str:
        return str(UI_DIR)

    @Property(bool, constant=True)
    def devWatermark(self) -> bool:
        """开发中水印开关（``app.dev_watermark``）。

        给开发者看的开关：只在**调试窗口**里出现，而调试窗口本身没有可见入口
        （设置窗口标题连点 10 次，见 ``openDebugWindow``）。缺省开启。
        """
        return self._config.get("app.dev_watermark", True) is not False

    @Property(str, constant=True)
    def devCodename(self) -> str:
        return str(self._config.get("app.codename", "AwaSubaru"))

    @Property(str, constant=True)
    def appChannel(self) -> str:
        """发布渠道（``app.channel``）：设置页「关于」的徽章只显示 ``Dev`` /
        ``Release`` 这两档，正式包把配置改成 ``"Release"`` 即可。"""
        return str(self._config.get("app.channel", "Dev"))

    # ================================================================ 启动画面

    @Property(float, notify=splashChanged)
    def splashProgress(self) -> float:
        """启动进度，0..1。"""
        return self._splash_progress

    @Property(str, notify=splashChanged)
    def splashStage(self) -> str:
        """当前阶段的短说明（设计稿里是「创建托盘图标」那一类）。"""
        return self._splash_stage

    @Property(str, constant=True)
    def splashSubtitle(self) -> str:
        """版本行文案：``<版本号> // <开发代号>``（设计稿同款）。"""
        return f"{self.appVersion} // {self.devCodename}"

    @Slot(float, str)
    def setSplashStage(self, progress: float, stage: str) -> None:
        """推进启动画面（应用层每到一个真实里程碑调一次）。"""
        self._splash_progress = max(0.0, min(1.0, float(progress)))
        self._splash_stage = str(stage)
        self.splashChanged.emit()

    @Property(str, constant=True)
    def deviceId(self) -> str:
        """本机短 ID（水印第二行用）：主机名 + MAC 的 SHA1 前 8 位。

        只用于开发者分辨「这是哪台测试机」，不含任何可逆的个人信息。
        """
        import hashlib
        import platform
        import uuid

        raw = f"{platform.node()}|{uuid.getnode():x}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8].upper()

    @Slot(str, result=str)
    def resourceFile(self, name: str) -> str:
        """``resources/`` 下某个品牌资源（logo.svg / logo.ico / banner.png）的
        ``file:///`` URL。

        QML 的 ``Image.source`` 不吃相对路径（基准是 QML 文件所在目录），
        所以统一在这里拼绝对 URL。
        """
        return QUrl.fromLocalFile(str(RESOURCES_DIR / name)).toString()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        """把一段文本放进系统剪贴板（回声洞的「复制」与诊断的「复制全部」共用）。"""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(text))

    # ================================================================ 回声洞

    #: 取句结果：``(句子, 状态)``，状态 ∈ ``ok`` / ``empty``。
    #:
    #: 为什么是**信号**而不是 ``@Slot(result=str)``：取句可能要走一次本地
    #: HTTP（见 ``echo_cave.py``），在槽里同步等会把 UI 线程按住 —— 这正是
    #: L1 用 ``await fetch()`` 避免的事。改成后台线程取、取完发信号，界面
    #: 期间能正常画出「获取中...」。
    echoCaveResult = Signal(str, str)

    @Slot()
    def requestEchoCave(self) -> None:
        """请求一条回声洞句子（异步）。

        ⚠️ **重复点击直接忽略**：句子很短，一次取句通常几十毫秒就回来了；
        真放行并发请求的话，晚回来的那个会盖掉用户刚看到的那句（L1 用
        ``echoCaveAbort`` 取消前一次动画，这里更简单 —— 干脆不并发）。
        """
        if self._echo_thread is not None and self._echo_thread.is_alive():
            return
        self._echo_thread = threading.Thread(
            target=self._fetch_echo_cave, name="echo-cave", daemon=True
        )
        self._echo_thread.start()

    def _fetch_echo_cave(self) -> None:
        """后台线程体：取句 → 发信号（在 Qt 里跨线程发信号会被排队到主线程）。"""
        from .echo_cave import fetch_sentence

        try:
            sentence = fetch_sentence()
        except Exception:  # noqa: BLE001 - 取句失败不该把线程带崩
            log.exception("回声洞取句失败")
            sentence = ""
        self.echoCaveResult.emit(sentence, "ok" if sentence else "empty")

    # ================================================================ 诊断信息

    #: 诊断字段就绪：``QVariantList``，每项 ``{"key": ..., "value": ...}``。
    #:
    #: 同样走**信号**而不是同步返回：硬件查询里有 ``GlobalMemoryStatusEx``
    #: 与注册表遍历，虽然都不起子进程，但没有理由压在 UI 线程上；更重要的是
    #: 同步返回的话界面根本没机会画出「加载中...」——L1 那个加载态正是这么来的。
    diagnosticsReady = Signal("QVariantList")

    @Slot()
    def requestDiagnostics(self) -> None:
        """采集诊断信息（异步）。重复请求同样直接忽略。

        ⚠️ **活体字段在这里先取好再交给线程**：``QGuiApplication.primaryScreen()``
        不是线程安全的，不能在 worker 里调（见 :meth:`_live_diagnostic_fields`）。
        """
        if self._diagnostics_thread is not None and self._diagnostics_thread.is_alive():
            return
        extra = self._live_diagnostic_fields()
        self._diagnostics_thread = threading.Thread(
            target=self._collect_diagnostics, args=(extra,), name="diagnostics", daemon=True
        )
        self._diagnostics_thread.start()

    def _live_diagnostic_fields(self) -> Dict[str, str]:
        """只有活体对象才拿得到的字段（屏幕 / 放映状态 / 日志级别 / 版本号）。

        ⚠️ 必须在**主线程**调用：``QGuiApplication.primaryScreen()`` 不是线程安全的。

        键名照 ClassIsland 的诊断字段（``AppSubChannel`` 对应它的发布渠道），
        与 ``app/diagnostics.py::FIELD_ORDER`` 里的键一一对上。
        """
        screen = QGuiApplication.primaryScreen()
        screen_size = ""
        if screen is not None:
            geometry = screen.geometry()
            screen_size = f"{geometry.width()} × {geometry.height()}"

        presentation = "active" if self._presentation_active else "inactive"
        if self._presentation_active:
            presentation = f"active:{self._slide_index}/{self._slide_total}"

        return {
            "Screen": screen_size,
            "AppVersion": self.appVersion,
            "AppSubChannel": self.appChannel,
            "Presentation": presentation,
            "LogLevel": str(self._config.get("app.log_level", "INFO")),
        }

    def _collect_diagnostics(self, extra: Dict[str, str]) -> None:
        """后台线程体：采集 → 发信号（``extra`` 由主线程预先取好）。"""
        from .diagnostics import collect

        try:
            fields = [{"key": key, "value": value} for key, value in collect(extra)]
        except Exception:  # noqa: BLE001 - 采集失败也要给界面一个交代
            log.exception("诊断信息采集失败")
            fields = []
        self.diagnosticsReady.emit(fields)

    # ================================================================ 检查更新
    #:
    #: 界面是 ClassIsland 更新页的一比一复刻（``ui/settings/Update.qml``），
    #: 这组属性 / 槽就是那边 ViewModel + UpdateService 公开面拆出来的最小集。
    #: 与回声洞 / 诊断同一条异步约定：**网络在后台线程、结果走信号**，
    #: 界面期间能正常画出「正在检查更新…」。
    #:
    #: ⚠️ **下载 / 安装 / 部署刻意未实现**（2026-10-05 用户指令）：界面上
    #: 「下载并安装」等按钮先以占位方式出现，点了由 QML 侧亮提示条；
    #: 状态机里 ``updatedownloaded`` / ``updatedeployed`` 两档留给部署接入时。

    def _get_update_status(self) -> str:
        return self._update_status

    updateStatus = Property(str, _get_update_status, notify=updateStatusChanged)
    def _get_update_working(self) -> str:
        return self._update_working

    updateWorkingStatus = Property(str, _get_update_working, notify=updateWorkingChanged)

    def _get_update_latest_version(self) -> str:
        return self._update_latest_version

    updateLatestVersion = Property(
        str, _get_update_latest_version, notify=updateStatusChanged
    )

    def _get_update_changelog(self) -> str:
        return self._update_changelog

    updateChangelog = Property(str, _get_update_changelog, notify=updateStatusChanged)

    def _get_update_current_changelog(self) -> str:
        return self._update_current_changelog

    updateCurrentChangelog = Property(
        str, _get_update_current_changelog, notify=updateStatusChanged
    )

    def _get_update_release_url(self) -> str:
        return self._update_release_url

    updateReleaseUrl = Property(
        str, _get_update_release_url, notify=updateStatusChanged
    )

    def _get_update_error(self) -> str:
        return self._update_error

    updateError = Property(str, _get_update_error, notify=updateStatusChanged)

    def _get_update_last_check_time(self) -> str:
        """上次检查更新的本地时间（人读格式；从未查过返回空串）。"""
        text = str(self._config.get("update.last_check_time", "") or "")
        if not text:
            return ""
        try:
            return datetime.fromisoformat(text).strftime("%Y/%m/%d %H:%M")
        except ValueError:
            return text

    updateLastCheckTime = Property(
        str, _get_update_last_check_time, notify=updateStatusChanged
    )

    @Slot(bool)
    def requestCheckUpdate(self, force: bool = False) -> None:
        """检查更新（异步）。``force`` = 强制检查（见 ``update_checker.check``）。

        ⚠️ **检查期间再点直接忽略**：并发检查的两次结果互相覆盖没有意义，
        与回声洞 / 诊断「不并发」同一个理由。界面侧在检查中会把按钮藏起来，
        这里是兜底。
        """
        if self._update_thread is not None and self._update_thread.is_alive():
            return
        self._update_working = "checking"
        self.updateWorkingChanged.emit()
        self._update_thread = threading.Thread(
            target=self._run_update_check, args=(bool(force),), name="update-check",
            daemon=True,
        )
        self._update_thread.start()

    @Slot()
    def autoCheckUpdates(self) -> None:
        """按配置的更新模式自动检查一次（应用启动后由应用层调用）。

        对应 ClassIsland ``AppStartupBackground`` 的第一段：
        ``UpdateMode >= 1`` 就 ``CheckUpdateAsync()``。模式 2（自动下载）与
        3（自动安装）在部署接入之前与 1 等效 —— 只检查、只通知。
        """
        mode = int(self._config.get("update.mode", 1))
        if mode < 1:
            return
        if mode >= 2:
            log.info("更新模式为 %d：自动下载/安装尚未实现，本次仅检查并通知", mode)
        self.requestCheckUpdate(False)

    def _run_update_check(self, force: bool) -> None:
        """后台线程体：查 → 记录 → 发信号（排队回主线程）。"""
        result = update_checker.check(
            channel=str(self._config.get("update.channel", "stable")),
            current_version=self.appVersion,
            force=force,
        )
        self._update_status = result["status"]
        self._update_latest_version = result["latest_version"]
        self._update_changelog = result["changelog"]
        self._update_current_changelog = result["current_changelog"]
        self._update_release_url = result["release_url"]
        self._update_error = result["error"]
        # 检查记录持久化（ClassIsland 同样记 LastUpdateStatus /
        # LastCheckUpdateTime）：重启后设置页还能看到上一次的结论。
        # 这里一次检查只写一次盘，不值得套延迟落盘。
        self._config.set("update.last_status", self._update_status)
        self._config.set(
            "update.last_check_time", datetime.now().isoformat(timespec="minutes")
        )
        self._update_working = "idle"
        self.updateStatusChanged.emit()
        self.updateWorkingChanged.emit()

    @Slot()
    def clearUpdateError(self) -> None:
        """关掉错误 InfoBar（对应 ClassIsland 把 ``NetworkErrorException`` 置空）。"""
        if self._update_error:
            self._update_error = ""
            self.updateStatusChanged.emit()

    def _get_update_channels(self) -> list:
        """更新通道候选（``[{"id", "name", "description"}, ...]``）。

        ⚠️ 通道表**只有这一份**，就是 ``update_checker.CHANNELS`` —— 界面上的
        名称与说明直接由它派生，不在 QML 里另抄一份（否则两边文案迟早漂）。

        2026-10-05：这也顺手绕掉了一个跨语言坑。原先通道表是 QML 里的
        ``property var updateChannels: [...]``，经 ``Loader.setProperty``
        推给「更新设置」Tab；QML 的 ``var`` 属性期望 ``QJSValue``，直接塞
        JS ``Array`` 过去会被包成**空 QJSValue**，子项遍历 ``.length`` 得 0 →
        通道下拉空、说明行标题与描述双空（自检实测）。改成由 Python 侧发
        ``QVariantList``，QML 拿到的就是原生数组。
        """
        return [
            {
                "id": key,
                "name": update_checker.CHANNEL_NAMES.get(key, key),
                "description": desc,
            }
            for key, desc in update_checker.CHANNELS.items()
        ]

    updateChannels = Property("QVariantList", _get_update_channels, constant=True)

    # ================================================================ 放映状态

    def _get_presentation_active(self) -> bool:
        return self._presentation_active

    presentationActive = Property(
        bool, _get_presentation_active, notify=presentationActiveChanged
    )

    def _get_slide_index(self) -> int:
        return self._slide_index

    slideIndex = Property(int, _get_slide_index, notify=slideChanged)

    def _get_slide_total(self) -> int:
        return self._slide_total

    slideTotal = Property(int, _get_slide_total, notify=slideChanged)

    # ---------------------------------------------------------- 幻灯片缩略图
    #: 页码快速跳转面板上那几十张「幻灯片画面」。**索引 = 页码 - 1**，空串 =
    #: 还没就绪（卡片显示空底 + 页码，这是正常的加载态）。
    #:
    #: ⚠️ 走 ``QVariantList`` 而不是逐张发信号：QML 里 ``var`` 属性收 JS 数组会
    #: 被包成空 QJSValue（见 memory 里那条），而列表整份重发只是几十个字符串，
    #: 比「41 条信号各接一次」简单得多。真正的产出链路在 ``app/slide_thumbs.py``。
    def _get_thumb_urls(self) -> List[str]:
        cache = self._slide_thumbs
        return list(cache.urls) if cache is not None else []

    thumbUrls = Property("QVariantList", _get_thumb_urls, notify=slideThumbsChanged)

    def attach_slide_thumbs(self, cache) -> None:
        """接上缩略图缓存（由 ``application.py`` 装配，见 ``slide_thumbs.py``）。"""
        self._slide_thumbs = cache
        if cache is not None:
            cache.urlsChanged.connect(self.slideThumbsChanged)
            self.slideThumbsChanged.emit()

    @Slot(int, int)
    def requestThumbnails(self, start: int, end: int) -> None:
        """要 ``[start, end]``（1-based 闭区间）这几页的缩略图。

        由 ``PageJumpPanel`` 在**展开时**（当前页 ±5）与**滚动时**（可见范围 ±3）
        调 —— 就是 Luminalium 1 的 ``requestThumbnailsForRange``，只换了个入口。
        没在放映 / 缓存没接上时静默忽略。
        """
        cache = self._slide_thumbs
        if cache is None:
            return
        cache.request(int(start), int(end))

    def _get_active_tool(self) -> str:
        return self._active_tool

    activeTool = Property(str, _get_active_tool, notify=activeToolChanged)

    def _get_pen_color(self) -> str:
        return self._pen_color

    #: 当前墨迹颜色（``#RRGGBB``，空串 = 还没选过）。
    #:
    #: ⚠️ 必须是 ``@Property`` 而不是 ``@Slot``：QML 侧把后端的 ``@Slot`` 当
    #: **属性**读**永远不报错**，拿到的是函数的形参个数（0）—— 症状是静默走
    #: 降级分支，这个坑本项目在 ``licenseText`` 上踩过一次。
    penColor = Property(str, _get_pen_color, notify=penColorChanged)

    def _get_pen_width(self) -> float:
        return self._pen_width

    #: 当前笔的粗细（逻辑 px，0 = 还没选过）。与 ``penColor`` 同一条理由必须是 Property。
    penWidth = Property(float, _get_pen_width, notify=penWidthChanged)

    def _get_eraser_width(self) -> float:
        return self._eraser_width

    #: 当前像素橡皮的粗细（逻辑 px，0 = 还没选过；2026-10-08 自建批注）。
    #: 与 ``penWidth`` 同一条理由必须是 Property。
    eraserWidth = Property(float, _get_eraser_width, notify=eraserWidthChanged)

    def _get_status_text(self) -> str:
        return self._status_text

    statusText = Property(str, _get_status_text, notify=statusChanged)

    def apply_state(self, state: PresentationState) -> None:
        """由 :class:`PptController` 调用。"""
        if state.active != self._presentation_active:
            self._presentation_active = state.active
            self.presentationActiveChanged.emit()

        if (state.slide_index, state.slide_total) != (
            self._slide_index,
            self._slide_total,
        ):
            self._slide_index = state.slide_index
            self._slide_total = state.slide_total
            self.slideChanged.emit()

        # 缩略图缓存跟着「放映开始 / 结束 / 页数变化」走。放在这里而不是
        # ``windows.py``：每个状态快照都会经过这个方法，缓存的新场 / 清场
        # 只需要一个入口（见 ``slide_thumbs.SlideThumbCache.set_show``）。
        cache = self._slide_thumbs
        if cache is not None:
            cache.set_show(bool(state.active), int(state.slide_total))

    def set_status_text(self, text: str) -> None:
        if text != self._status_text:
            self._status_text = text
            self.statusChanged.emit()

    # ================================================================== 配置块

    def _get_presentation_config(self) -> Dict[str, Any]:
        """``presentation`` 配置的**深拷贝** + 插件控制条贡献的读取侧合并。

        合并规则（2026-10-05 插件系统 Wave 2 任务 6，理由见文件头注释）：

        * ``tools`` / ``actions`` = config 内建数组在前，registry 的
          ``dock_tools()`` / ``dock_actions()`` 插件条目追加在后；
        * id 冲突时**内建胜出**并记 warning（与磁贴目录同款让位规则）；
        * 先 ``deepcopy`` 再合并 —— ``Config.get`` 返回的是内部引用，直接
          append 会污染配置内存态（铁律：插件贡献不落盘也不进 config
          内存态）；每次读取重新合并，天然不会重复追加。
        """
        merged = copy.deepcopy(self._config.get("presentation", {}) or {})
        for key, extra in (
            ("tools", registry.dock_tools()),
            ("actions", registry.dock_actions()),
        ):
            entries = list(merged.get(key, []) or [])
            builtin_ids = {str(item.get("id")) for item in entries}
            for entry in extra.values():
                entry_id = str(entry.get("id"))
                if entry_id in builtin_ids:
                    log.warning("插件控制条贡献 id 与内建冲突，内建胜出: %s", entry_id)
                    continue
                entries.append(dict(entry))
            merged[key] = entries
        return merged

    presentationConfig = Property(
        "QVariantMap",
        _get_presentation_config,
        notify=presentationConfigChanged,
    )

    def _get_presentation_groups(self) -> List[Dict[str, Any]]:
        """编辑器分组注册表的 QML 列表视图（2026-10-05 插件系统 Wave 2 任务 9）。

        把 ``registry.editor_groups()`` 的 ``{组名: 条目}`` 拍平成
        ``[{name, display_name, icon, dock_qml?, traits, inspector_items}, ...]``，
        主界面编辑器的组件名 / 图标 / 语义判定全部从这里读 —— 组名硬编码
        if 链已随本任务移除，注册表是唯一事实来源。

        每条深拷一层（traits / inspector_items 也拷）：注册表返回的只读视图
        只是浅快照，直接递给 QML 等于共享引用；编辑器只读，但桥接侧不给
        消费方留下「改列表项会污染注册表」的机会。
        """
        view: List[Dict[str, Any]] = []
        for name, entry in registry.editor_groups().items():
            item = {
                "name": name,
                "display_name": str(entry.get("display_name", name)),
                "icon": str(entry.get("icon", "")),
                "traits": copy.deepcopy(entry.get("traits") or {}),
                "inspector_items": copy.deepcopy(entry.get("inspector_items") or []),
            }
            dock_qml = entry.get("dock_qml")
            if dock_qml:
                item["dock_qml"] = str(dock_qml)
            view.append(item)
        return view

    presentationGroups = Property(
        "QVariantList",
        _get_presentation_groups,
        notify=presentationGroupsChanged,
    )

    # ------------------------------------------------- 放映显示器几何（画布基准）

    def _get_presentation_screen(self) -> Dict[str, Any]:
        """放映所在显示器的**逻辑**几何 —— 主界面编辑器画布的坐标基准。

        优先用 :meth:`syncPresentationScreen` 推来的真实结果（放映窗口在哪块屏
        就报哪块）；还没放映过时退回「钉屏名称 → 配置索引 → 主屏」，与
        ``windows.py::_presentation_screen`` 的兜底分支同源（2026-10-08 起
        多了 ``presentation.screen_name`` 这一跳，见 ``app/monitors.py``）。

        ⚠️ 不能用 QML 的 ``Screen`` attached property 代替：那说的是**本窗口**
        所在显示器。双屏时编辑器在主屏、放映在副屏，画布比例会整个错掉。
        """
        if self._overlay_screen is not None:
            return dict(self._overlay_screen)
        try:
            screens = QGuiApplication.screens()
        except Exception:  # pragma: no cover - QApplication 尚未建好
            screens = []
        screen = monitors.resolve_screen(
            str(self._config.get("presentation.screen_name", "") or ""),
            int(self._config.get("presentation.screen_index", -1)),
            screens,
        )
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:  # pragma: no cover - 极端情况（无显示器）
            return {"width": 1920, "height": 1080, "name": "",
                    "scale": 1.0, "source": "fallback"}
        geometry = screen.geometry()
        return {
            "width": geometry.width(),
            "height": geometry.height(),
            "name": screen.name(),
            "scale": float(screen.devicePixelRatio()),
            "source": "config",
        }

    presentationScreen = Property(
        "QVariantMap", _get_presentation_screen, notify=presentationScreenChanged
    )

    # ------------------------------------------------- 显示器名单（目标显示器下拉）

    def _get_monitor_list(self) -> List[Dict[str, Any]]:
        """当前接入的显示器名单（``app/monitors.py::enumerate_monitors``）。

        每项 ``{name, label, primary}``：``name`` 是钉屏用的稳定 id，
        ``label`` 是厂商+型号（读不到 EDID 时为空串，由 QML 翻成「显示器 N」）。
        """
        return monitors.enumerate_monitors()

    monitorList = Property(
        "QVariantList", _get_monitor_list, notify=monitorListChanged
    )

    def _on_monitors_changed(self, _screen) -> None:
        """显示器热插拔：作废枚举缓存并通知 QML 重取名单。"""
        monitors.invalidate()
        self.monitorListChanged.emit()

    @Slot(int, int, str, float)
    def syncPresentationScreen(
        self, width: int, height: int, name: str, scale: float
    ) -> None:
        """由 ``WindowManager.show_docks()`` 调用：顶层窗口定位完，把真实屏幕推过来。

        顶层窗口铺在哪块屏是按**放映窗口的物理显示器**判定的（见
        ``windows.py::_presentation_screen``），Bridge 侧复现不了，所以只能推。
        """
        info = {
            "width": int(width),
            "height": int(height),
            "name": str(name),
            "scale": float(scale),
            "source": "overlay",
        }
        if info == self._overlay_screen:
            return
        self._overlay_screen = info
        self.presentationScreenChanged.emit()

    def _get_quick_panel_config(self) -> Dict[str, Any]:
        return self._config.get("quick_panel", {}) or {}

    quickPanelConfig = Property(
        "QVariantMap",
        _get_quick_panel_config,
        notify=quickPanelConfigChanged,
    )

    # ============================================================ 快捷方式清单

    def _catalog(self) -> List[Dict[str, Any]]:
        """全部可用的快捷方式：config 内建目录 ∪ registry 插件磁贴（读取侧纯拼接）。

        合并规则（2026-10-05 插件系统 Wave 2 任务 5）：

        * 插件条目追加在内建之后 —— 面板「+」浮层里插件磁贴自然排在后面；
        * id 冲突时**内建胜出**并记 warning（插件让位，防插件顶掉内建行为）；
        * 合并是纯读取侧拼接，**绝不写回 config**（铁律，见文件头注释）。

        合并必须发生在这一处：``_resolve_shortcuts`` 会静默丢弃目录外的 id，
        在别处合并的插件条目到不了面板。``setShortcutEnabled`` /
        ``activateShortcut`` 的 id 校验走的也是这里，插件 id 天然被认。
        """
        merged = list(self._config.get("quick_panel.shortcut_catalog", []) or [])
        builtin_ids = {str(item.get("id")) for item in merged}
        for entry in registry.shortcuts().values():
            tile_id = str(entry.get("id"))
            if tile_id in builtin_ids:
                log.warning("插件磁贴 id 与内建冲突，内建胜出: %s", tile_id)
                continue
            merged.append(dict(entry))
        return merged

    def shortcut_action(self, shortcut_id: str) -> str:
        """按 id 在**合并后**的目录里查动作串；未命中返回空串。

        应用层（``application.py::_on_shortcut``）专用：目录双来源之后，
        应用层不能再只翻 config，否则插件磁贴的动作永远查不到。
        """
        for item in self._catalog():
            if str(item.get("id")) == shortcut_id:
                return str(item.get("action", ""))
        return ""

    def _resolve_shortcuts(self, ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """把 id 列表解析成目录里的完整条目；未知 id 直接丢弃。"""
        wanted = self._shortcut_ids if ids is None else ids
        by_id = {str(item.get("id")): item for item in self._catalog()}
        return [by_id[item_id] for item_id in wanted if item_id in by_id]

    def _get_shortcut_items(self) -> List[Dict[str, Any]]:
        return self._resolve_shortcuts()

    shortcutItems = Property(
        "QVariantList", _get_shortcut_items, notify=shortcutsChanged
    )

    def _get_available_shortcut_items(self) -> List[Dict[str, Any]]:
        enabled = set(self._shortcut_ids)
        return [item for item in self._catalog() if str(item.get("id")) not in enabled]

    availableShortcutItems = Property(
        "QVariantList", _get_available_shortcut_items, notify=shortcutsChanged
    )

    def _persist_shortcuts(self) -> None:
        self._config.set("quick_panel.shortcuts", list(self._shortcut_ids))
        self.shortcutsChanged.emit()

    @Slot(str, bool)
    def setShortcutEnabled(self, shortcut_id: str, enabled: bool) -> None:
        """快捷方式的启用开关；面板上的「添加 / 移除」都走这里。"""
        exists = any(str(item.get("id")) == shortcut_id for item in self._catalog())
        if not exists:
            log.info("未知快捷方式: %s", shortcut_id)
            return
        if enabled:
            if shortcut_id in self._shortcut_ids:
                return
            self._shortcut_ids.append(shortcut_id)
        else:
            if shortcut_id not in self._shortcut_ids:
                return
            self._shortcut_ids.remove(shortcut_id)
        self._persist_shortcuts()

    @Slot(str, int)
    def moveShortcut(self, shortcut_id: str, index: int) -> None:
        """把快捷方式拖到新位置（``index`` 来自网格的 visualIndex）。"""
        if shortcut_id not in self._shortcut_ids:
            return
        target = max(0, min(int(index), len(self._shortcut_ids) - 1))
        current = self._shortcut_ids.index(shortcut_id)
        if current == target:
            return
        self._shortcut_ids.pop(current)
        self._shortcut_ids.insert(target, shortcut_id)
        self._persist_shortcuts()

    # ================================================================== 设置

    def _setting_paths(self) -> Dict[str, str]:
        """内建 ``SETTING_PATHS`` ∪ 动态注册的合成视图（内建优先）。"""
        return {**self._dynamic_paths, **SETTING_PATHS}

    def register_setting_path(
        self,
        key: str,
        path: str,
        notify: Optional[str] = None,
        side_effect: Optional[SettingSideEffect] = None,
    ) -> bool:
        """动态注册一个设置项（插件用）。

        :param key: 扁平键（QML 侧 ``Backend.settings.<key>`` 读、
            ``Backend.setSetting("<key>", 值)`` 写）。插件键命名约定
            ``plugins_<id>_<name>``，避免撞内建键与 ``presentation_`` 前缀广播。
        :param path: 配置里的点号路径（如 ``plugins._t.volume``）。
        :param notify: 值变更时额外发的信号名字符串（无参，如
            ``"presentationConfigChanged"``）；None 则只发 ``settingsChanged``。
        :param side_effect: 可选回调 ``(config, key, value)``，在改完内存、
            排好延迟落盘之后、发信号之前调用。
        :return: 注册是否成功（与内建键冲突或参数为空会被拒绝并记日志）。
        """
        if not key or not path:
            log.warning("动态注册设置项被拒绝（键或路径为空）: %r -> %r", key, path)
            return False
        if key in SETTING_PATHS:
            log.warning("动态注册与内建设置项冲突，已忽略: %s", key)
            return False
        self._dynamic_paths[key] = path
        if notify is not None or side_effect is not None:
            self._key_effects[key] = {
                "signals": [(notify, False)] if notify else [],
                "side_effect": side_effect,
            }
        log.info("动态注册设置项: %s -> %s", key, path)
        return True

    def _get_settings(self) -> Dict[str, Any]:
        values = {
            key: self._config.get(path)
            for key, path in self._setting_paths().items()
        }
        # 「开机自启」的真相在**注册表**里，不在配置里：用户可能在「任务管理器 →
        # 启动」里禁用它，也可能手动删过那个注册表值 —— 配置里那份影子会骗人。
        # 所以每次都回读一次实际状态（注册表读取是微秒级的，代价可以忽略）。
        values["autostart"] = autostart.is_enabled()
        return values

    settings = Property("QVariantMap", _get_settings, notify=settingsChanged)

    def _get_settings_config(self) -> Dict[str, Any]:
        return self._config.get("settings", {}) or {}

    settingsConfig = Property(
        "QVariantMap", _get_settings_config, notify=settingsChanged
    )

    def _get_settings_nav_items(self) -> List[Dict[str, Any]]:
        """设置窗口左侧导航的数据源（2026-10-05 插件系统 Wave 2 任务 7）。

        = 内建条目（``_BUILTIN_SETTINGS_NAV``，原 QML 硬编码列表逐字搬入）
        ∪ 插件设置页（``registry.settings_pages()``）追加在后。

        * 标题经 ``app.i18n.tr`` 标注：内建项的 context 沿用原 QML 侧的
          ``Settings``（译文已同步进 ``translations/luminalium_py_*.ts``，
          Python 侧 ts 手工维护、lupdate 不碰）；插件条目注册时应自带
          翻译好的 ``title``（约定：插件自己的 ``tr(<插件 id>, ...)``），
          这里原样透传。
        * ``page`` 全部是 **file:/// 绝对 URL**（原因见
          ``_BUILTIN_SETTINGS_NAV`` 的注释）；插件侧给的 ``page_url`` 键名
          在这里映射成 QML 侧的 ``page``（两键名的语义区分见
          ``app/plugins/registry.py`` 头注释第 4 条）。
        * ``position`` 是 RinUI ``Position`` 枚举的**整数值**（经 QVariant
          到 QML 后与 ``Rin.Position.Bottom`` 严格相等）；普通条目不写这个
          键，QML 侧读为 ``undefined``，落入普通区。「关于 / 更新」钉底部
          的语义由表里的 ``_RIN_POSITION_BOTTOM`` 原样保留。
        * 每次读取现算（注册表在加载期冻结，读到的必是全量），且合并结果
          **绝不写回 config**（列表型贡献注入默认层会被用户层整体顶掉 ——
          铁律，见文件头注释与 ``app/plugins/registry.py`` 头注释第 3 条）。
        """
        items: List[Dict[str, Any]] = []
        for rel, title_source, icon, position in _BUILTIN_SETTINGS_NAV:
            item: Dict[str, Any] = {
                "title": i18n.tr("Settings", title_source),
                "page": "file:///" + (UI_DIR / rel).as_posix(),
                "icon": icon,
            }
            if position is not None:
                item["position"] = position
            items.append(item)
        for entry in registry.settings_pages().values():
            plugin_item: Dict[str, Any] = {
                "title": str(entry.get("title", "")),
                "page": str(entry.get("page_url", "")),
                "icon": str(entry.get("icon", "")),
            }
            if "position" in entry:
                plugin_item["position"] = entry["position"]
            items.append(plugin_item)
        return items

    settingsNavItems = Property(
        "QVariantList",
        _get_settings_nav_items,
        notify=settingsNavItemsChanged,
    )

    def _get_plugin_items(self) -> List[Dict[str, Any]]:
        """「插件」管理页的列表数据源（2026-10-05 插件系统 Wave 3 任务 17）。

        = ``loader.loaded_plugins()`` 的加载清单逐项合成 QML 消费的形状：

        * ``id`` / ``debug`` / ``loaded`` / ``reason``：照清单原样透传
          （``reason`` 为跳过原因，未跳过是 None）；
        * ``title``：``META.name``，插件没声明就回落 id（管理页总得有个
          能给人看的名字）；``version``：``META.version``，可空；
        * ``enabled``：**从正式 Config 现读** ``plugins.<id>.enabled``
          （默认 true），不照抄清单里那份 —— 清单是加载时刻的快照，而
          这个属性在 ``setPluginEnabled`` 之后还要被重读，读快照就永远
          看不到新值。

        清单为空（未跑加载 / 无插件）时返回空列表，QML 侧显示空态。
        """
        items: List[Dict[str, Any]] = []
        for entry in loader.loaded_plugins():
            pid = str(entry.get("id", ""))
            meta = entry.get("meta") or {}
            items.append(
                {
                    "id": pid,
                    "title": str(meta.get("name") or pid),
                    "version": meta.get("version"),
                    "enabled": bool(
                        self._config.get(f"plugins.{pid}.enabled", True)
                    ),
                    "debug": bool(entry.get("debug", False)),
                    "external": bool(entry.get("external", False)),
                    "loaded": bool(entry.get("loaded", False)),
                    "reason": entry.get("reason"),
                }
            )
        return items

    pluginItems = Property(
        "QVariantList",
        _get_plugin_items,
        notify=pluginItemsChanged,
    )

    @Slot(str, bool)
    def setPluginEnabled(self, plugin_id: str, enabled: bool) -> None:
        """改一个插件的启用开关（``plugins.<id>.enabled``），**重启后生效**。

        与 ``setSetting`` 同一条「改内存 + 防抖落盘」路径（配置落盘语义：
        与默认层不同才写进 ``config.json``，恢复默认 true 后该键消失；
        注意调试插件的默认值不走阶段一注入，其 ``enabled=true`` 恢复后
        仍会落一条 ``true``，属预期）。本进程内**不做任何动态增删** ——
        注册表冻结 + 窗口懒创建只藏不销毁，实时反注册与这两个架构前提
        冲突（详见文件头注释与 ``ui/settings/Plugins.qml`` 头注释）。
        """
        plugin_id = str(plugin_id).strip()
        if not plugin_id:
            log.warning("setPluginEnabled 被拒绝（插件 id 为空）")
            return
        enabled = bool(enabled)
        path = f"plugins.{plugin_id}.enabled"
        if bool(self._config.get(path, True)) == enabled:
            return
        self._config.set(path, enabled, persist=False)
        self._save_timer.start()
        log.info("插件 %s 启用开关改为 %s（重启后生效）", plugin_id, enabled)
        self.pluginItemsChanged.emit()

    # ------------------------------------------------ 外部插件的导入 / 删除

    def _import_plugin_from_dialog(self, pick) -> None:
        """导入插件的公共尾段：弹对话框 → 校验安装 → 结果信号回 QML。

        ``pick`` 是 ``QFileDialog`` 的静态调用（返回 ``(路径, 过滤器)`` 或
        ``(空串, _)``），对话框本体是模态原生窗口；用户取消就安静返回，
        不发结果信号（发一条「已取消」反而像出了错）。
        """
        from PySide6.QtWidgets import QFileDialog

        path, _filter = pick()
        if not path:
            return
        ok, message = external.install_from_path(path)
        log.info("插件导入结果: ok=%s 消息=%s", ok, message)
        self.pluginManageResult.emit(ok, message)

    @Slot()
    def importPluginFolder(self) -> None:
        """弹原生目录选择框导入插件文件夹（``plugin.py`` 直在其下）。"""
        from PySide6.QtWidgets import QFileDialog

        self._import_plugin_from_dialog(
            lambda: (
                QFileDialog.getExistingDirectory(
                    None,
                    i18n.tr("Plugins", "选择插件文件夹"),
                    str(external.user_plugins_dir()),
                    QFileDialog.Option.ShowDirsOnly,
                ),
                "",
            ),
        )

    @Slot()
    def importPluginZip(self) -> None:
        """弹原生文件选择框导入 .zip 插件包。"""
        from PySide6.QtWidgets import QFileDialog

        self._import_plugin_from_dialog(
            lambda: QFileDialog.getOpenFileName(
                None,
                i18n.tr("Plugins", "选择插件包"),
                "",
                i18n.tr("Plugins", "插件包 (*.zip);;所有文件 (*)"),
            ),
        )

    @Slot(str)
    def removePlugin(self, plugin_id: str) -> None:
        """删除一个外部插件的安装副本，并清掉它的 ``plugins.<id>`` 配置。

        只动用户插件目录里的**安装副本**（用户导入时的原始文件不动）。
        配置子树照删：插件都没了，``plugins.<id>.enabled`` 留着就是死条目
        （注册表头注释第 1 条骂的正是这种残留）。加载清单是启动时刻的
        快照，本进程内它仍显示在列表里、贡献也仍生效 —— 与启用 / 禁用
        一样重启后才是新世界。
        """
        plugin_id = str(plugin_id).strip()
        if not plugin_id:
            log.warning("removePlugin 被拒绝（插件 id 为空）")
            return
        ok, message = external.uninstall(plugin_id)
        if ok:
            self._config.remove(f"plugins.{plugin_id}")
            self.pluginItemsChanged.emit()
        log.info("插件删除结果: ok=%s 消息=%s", ok, message)
        self.pluginManageResult.emit(ok, message)

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        """改一项设置。类型按默认值对齐，避免 QML 把 int 传成字符串。"""
        path = self._setting_paths().get(key)
        if path is None:
            log.info("未知设置项: %s", key)
            return

        # 开机自启：**本体是注册表**，单独走一条路。通用的「改内存 + 延迟落盘」
        # 会把「写注册表失败」这件事吞掉 —— 那正是「关了却没关掉」的来源。
        if key == "autostart":
            self._apply_autostart(bool(value))
            return

        current = self._config.get(path)
        if isinstance(current, bool):
            value = bool(value)
        elif isinstance(current, int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return
        elif isinstance(current, float):
            try:
                value = float(value)
            except (TypeError, ValueError):
                return

        if current == value:
            return
        # 只改内存 + 排一次延迟落盘（理由见 ``_save_timer`` 处的注释）。
        self._config.set(path, value, persist=False)
        self._save_timer.start()
        log.info("设置 %s = %r", path, value)

        # 副作用两级查找（注册表驱动，不再是硬编码 if/elif）：
        # ① 键级回调表（精确命中，side_effect 先于信号 —— 翻页位置得先把
        #    corners 改完再喊重建）；② 前缀 / 集合规则表。
        effect = self._key_effects.get(key)
        if effect is not None:
            side_effect: Optional[SettingSideEffect] = effect.get("side_effect")
            if side_effect is not None:
                side_effect(self._config, key, value)
            for signal_name, pass_value in effect["signals"]:
                self._emit_setting_signal(signal_name, value, pass_value)
        if key in _BROADCAST_KEYS:
            self.quickPanelConfigChanged.emit()
        # 「改了要重启才生效」的项：亮出设置窗口那枚「需要重启」按钮，并弹一次
        # 询问框（见 ``RESTART_REQUIRED_KEYS`` 处的说明）。
        if key in RESTART_REQUIRED_KEYS:
            self._notify_restart_required(key)
        for prefix, signal_specs in _PREFIX_NOTIFY_RULES:
            if key.startswith(prefix):
                for signal_name, pass_value in signal_specs:
                    self._emit_setting_signal(signal_name, value, pass_value)
                break
        self.settingsChanged.emit()

    def _emit_setting_signal(self, signal_name: str, value: Any, pass_value: bool) -> None:
        """按名字发设置类信号；``pass_value`` 为真时带 ``str(值)`` 作为参数。

        按名字查是为了让注册表（内建键级表 / 前缀规则 / 动态注册）不用持有
        Backend 就能声明「改完发什么」；名字打错时记警告而不是静默吞掉。
        """
        signal = getattr(self, signal_name, None)
        if signal is None:
            log.warning("注册的通知信号不存在: %s", signal_name)
            return
        if pass_value:
            signal.emit(str(value))
        else:
            signal.emit()

    def _notify_restart_required(self, key: str) -> None:
        """某项「改了要重启才生效」的设置刚被改动 → 亮按钮 + 弹询问框。

        参考 ClassIsland ``SettingsWindowNew.axaml.cs``：::

            private void CommandBindingRestartApp_OnExecuted(...)
            {
                ViewModel.IsRequestedRestart = true;
                ShowRestartDialog();
            }

        也就是「置位 + 立刻弹框」两件事。用户选「取消」后框关掉，但那枚
        「需要重启」按钮留着（``restartPending`` 不复位），随时可以再点。
        """
        log.info("设置 %s 需要重启才生效", key)
        if not self._restart_pending:
            self._restart_pending = True
            self.restartPendingChanged.emit()
        # ⚠️ 询问框**每次都弹**（哪怕 ``restartPending`` 早就是 true）：
        # 与 ClassIsland 一致 —— 用户刚改完就该被问一次，而不是只有第一次改才问。
        self.restartSuggested.emit()

    def _apply_pager_position(self, position: str) -> None:
        """把「翻页组件位置」落到 ``corners`` 那四个角的开关上。

        ``side`` → 启用 ``middle_left`` / ``middle_right``（竖版两侧中间）、
        关掉底部两只；``bottom`` → 反过来。

        ⚠️ 真实生效的是 ``corners``（``windows.py::_load_docks`` 与编辑器预览
        都只读它），``pager.position`` 只是它的人话开关 —— 两边必须一起改，
        否则「设置里选了横版、屏幕上还是竖版」。
        """
        enabled = PAGER_POSITION_CORNERS.get(position)
        if enabled is None:
            log.info("未知翻页组件位置: %s", position)
            return
        for corners in PAGER_POSITION_CORNERS.values():
            for corner in corners:
                self._config.set(
                    f"presentation.corners.{corner}.enabled", corner in enabled
                )

    def _apply_autostart(self, enabled: bool) -> None:
        """开关开机自启：写注册表 → **回读真实状态** → 同步影子配置 → 广播。

        ⚠️ 回读是关键，不是多余的稳妥：``set_enabled`` 返回成功只说明注册表调用
        没抛异常，不代表最终状态就是想要的（组策略 / 杀软可能半途拦下）。所以以
        ``is_enabled()`` 的回读结果为准 —— 真实状态与用户点的那个不一致时，写进
        影子配置的是**真实状态**，QML 侧的开关跟着弹回去，而不是停在用户点的那
        一格骗人。这就是「关闭也必须有效无误」的落点。
        """
        ok = autostart.set_enabled(enabled)
        actual = autostart.is_enabled()
        self._config.set("app.autostart", actual, persist=False)
        self._save_timer.start()
        if not ok or actual != enabled:
            log.warning("开机自启未能按预期设置：期望 %s，实际 %s", enabled, actual)
        self.settingsChanged.emit()

    @Slot()
    def refreshSettings(self) -> None:
        """让 QML 重新取一遍 ``settings``（``settings`` 里含实时状态，如注册表）。

        入口是 ``windows.py::show_settings`` —— 每次打开设置窗口都刷一次，这样
        「在任务管理器里禁用了开机自启、再打开设置」看到的就是关着的那一格。
        """
        self.settingsChanged.emit()

    @Slot()
    def closeSettings(self) -> None:
        self.settingsCloseRequested.emit()

    @Slot()
    def openDebugWindow(self) -> None:
        """打开调试窗口。

        入口是**隐藏**的：在设置窗口左上角的标题文本上连点 10 次
        （``Settings.qml`` 的 ``debugTitleHotspot``）。调试项不再占用
        设置导航栏的位置。
        """
        self.debugWindowRequested.emit()

    @Slot()
    def closeDebugWindow(self) -> None:
        self.debugWindowCloseRequested.emit()

    @Slot()
    def openMainEditor(self) -> None:
        """打开主界面编辑器窗口。

        与调试窗口不同，这个是**正经入口**：快捷面板的「主界面编辑器」快捷方式
        （``shortcut_catalog`` 里 ``action: "open_editor"``）会派发到这里。
        """
        self.editorRequested.emit()

    @Slot()
    def closeMainEditor(self) -> None:
        self.editorCloseRequested.emit()

    def reload_from_config(self) -> None:
        self._shortcut_ids = [
            str(item) for item in (self._config.get("quick_panel.shortcuts", []) or [])
        ]
        self.shortcutsChanged.emit()
        self.settingsChanged.emit()
        self.presentationConfigChanged.emit()
        self.presentationScreenChanged.emit()
        self.quickPanelConfigChanged.emit()

    # ============================================================ 放映控制槽

    @Slot(str)
    def selectTool(self, tool: str) -> None:
        """切换放映指针：``pen`` / ``eraser`` / ``arrow``；``plugin:`` 前缀走动作通道。"""
        # ``plugin:`` 前缀的工具 id 来自插件（registry.add_dock_tool，2026-10-05
        # 任务 6）：不进白名单校验、不调 ``ppt.set_tool``（与 COM 零接触），改按
        # 动作处理 —— 经 ``actionTriggered`` 走应用层 ``_on_action`` 的 ``plugin:``
        # 特权通道，由动词注册表分发给插件处理器。
        if tool.startswith("plugin:"):
            self.actionTriggered.emit(tool)
            return
        if tool not in ("pen", "eraser", "arrow"):
            return
        if tool != self._active_tool:
            self._active_tool = tool
            self.activeToolChanged.emit()
        self.actionTriggered.emit(f"tool:{tool}")

    @Slot(str)
    def setPenColor(self, color: str) -> None:
        """选墨迹颜色（笔选单里点一格）。

        ``color`` 是 ``#RRGGBB``（可带 alpha，``#AARRGGBB`` 也认，取后六位）。
        先落进本对象（QML 靠它回显选中格），再经 ``actionTriggered`` 交给
        应用层：墨迹引擎为 self（默认）时落到自建墨迹的 InkLayer，为 com 时
        才调 PowerPoint 的 ``View.PointerColor``（见 ``application.py::_on_action``）。

        ⚠️ 非法串**直接丢弃**且不改状态：选单里的格子全来自配置，正常不会
        走到这儿，但这里是 QML 能直接调到的公开槽，别让它把 ``penColor``
        写成半截的垃圾值（回显会跟着错）。
        """
        value = str(color or "").strip().lstrip("#").upper()
        if len(value) == 8:  # #AARRGGBB → 取 RGB
            value = value[2:]
        if len(value) != 6 or any(c not in "0123456789ABCDEF" for c in value):
            log.warning("忽略非法的墨迹颜色: %r", color)
            return
        hex_color = "#" + value
        if hex_color != self._pen_color:
            self._pen_color = hex_color
            self.penColorChanged.emit()
        self.actionTriggered.emit(f"pen_color:{hex_color}")

    @Slot(float)
    def setPenWidth(self, width: float) -> None:
        """选笔的粗细（笔选单「粗细」一行点一档，2026-10-07 自建批注）。

        与 :meth:`setPenColor` 同一条路：先落进本对象（QML 回显选中档），再发
        ``pen_width:<px>`` 交给应用层 —— self 引擎落到 InkLayer.penWidth，com
        引擎忽略（PowerPoint 的放映笔没有粗细接口）。

        ⚠️ 非正数 / 非数字直接丢弃：这是 QML 能直接调到的公开槽，别让一个 0
        把笔画成看不见的线。
        """
        try:
            value = float(width)
        except (TypeError, ValueError):
            log.warning("忽略非法的笔粗细: %r", width)
            return
        if not (value > 0) or value != value:
            log.warning("忽略非法的笔粗细: %r", width)
            return
        if value != self._pen_width:
            self._pen_width = value
            self.penWidthChanged.emit()
        self.actionTriggered.emit(f"pen_width:{value:g}")

    @Slot(float)
    def setEraserWidth(self, width: float) -> None:
        """选像素橡皮的粗细（橡皮卡片「粗细」一行点一档，2026-10-08 自建批注）。

        与 :meth:`setPenWidth` 同一条路：先落进本对象（QML 回显选中档），再发
        ``eraser_width:<px>`` 交给应用层 —— self 引擎落到 InkLayer.eraserWidth，
        com 引擎忽略（橡皮交给演示软件自己，没有粗细接口）。

        ⚠️ 非正数 / 非数字直接丢弃（同 setPenWidth 的防线：这是 QML 能直接
        调到的公开槽，别让一个 0 把橡皮变成擦不动的空气）。
        """
        try:
            value = float(width)
        except (TypeError, ValueError):
            log.warning("忽略非法的橡皮粗细: %r", width)
            return
        if not (value > 0) or value != value:
            log.warning("忽略非法的橡皮粗细: %r", width)
            return
        if value != self._eraser_width:
            self._eraser_width = value
            self.eraserWidthChanged.emit()
        self.actionTriggered.emit(f"eraser_width:{value:g}")

    @Slot(str)
    def triggerAction(self, action_id: str) -> None:
        """面板上的通用动作（清屏等），由应用层分发到 PowerPoint 控制器。"""
        self.actionTriggered.emit(action_id)

    @Slot()
    def nextSlide(self) -> None:
        self.actionTriggered.emit("pager:next")

    @Slot()
    def previousSlide(self) -> None:
        self.actionTriggered.emit("pager:previous")

    @Slot(int)
    def gotoSlide(self, page: int) -> None:
        """跳到指定页（控制条上「点页码展开快速切页面板」里点了一格）。

        ``page`` 是 **1-based** 的页码 —— 与 ``slideIndex`` 同一个口径，
        PowerPoint 的 ``View.GotoSlide`` 本来就是 1-based，中间不要再换算一次。

        这里只挡掉 ``< 1``：面板里的格子全是从 ``slideTotal`` 铺出来的，正常
        不会越界，但这是 QML 能直接调到的公开槽，一个手滑的 0 会让 COM 那侧
        抛异常（越界上限交给 COM 自己判 —— 它失败也只是这一次跳页不生效，
        不会伤到别的状态）。"""
        try:
            target = int(page)
        except (TypeError, ValueError):
            log.warning("忽略非法的跳转页码: %r", page)
            return
        if target < 1:
            log.warning("忽略越界的跳转页码: %r", page)
            return
        self.actionTriggered.emit(f"pager:goto:{target}")

    @Slot()
    def exitPresentation(self) -> None:
        self.actionTriggered.emit("exit_presentation")

    # ================================================================ 面板交互

    @Slot(str, result=bool)
    def activateShortcut(self, shortcut_id: str) -> bool:
        """触发快捷方式。

        返回是否被受理 —— 面板用它决定要不要顺手收起（CW2 的
        ``executeShortcut`` 也是这个约定）。
        """
        known = any(str(item.get("id")) == shortcut_id for item in self._catalog())
        if not known:
            log.info("未注册的快捷方式: %s", shortcut_id)
            return False
        self.shortcutTriggered.emit(shortcut_id)
        return True

    @Slot()
    def requestSettings(self) -> None:
        self.settingsRequested.emit()

    @Slot()
    def requestRestart(self) -> None:
        self.restartRequested.emit()

    @Slot()
    def requestQuit(self) -> None:
        self.quitRequested.emit()

    @Slot()
    def hidePanel(self) -> None:
        self.panelHideRequested.emit()

    # ------------------------------------------------------------------ 工具
