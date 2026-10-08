import QtQuick
import QtQuick.Window
import RinUI as Rin
import Luminalium

/*!
    放映悬浮控制条，**恒横向**。

    形态与尺寸照 **Luminalium 1**（``ppt_assistant/ui/overlay.html``）：
    全圆胶囊底板、圆形图标按钮、选中即圆底填充、翻页 pill 紧凑。
    逐个值的对照表在 ``ui/Luminalium/Lumi.qml`` 上方的注释里。

    **整条是「区块（section）」的顺序拼装**，区块顺序固定为::

        tools → actions → pager → exit

    分隔线只插在 **动作 → 翻页 → 退出** 之间 —— 工具分段右侧没有：分段
    自带胶囊容器，紧跟着再来一条竖线会显得「双层边」。
    某一区块在这个角落没被启用时，它连同它前后的分隔线一起消失::

        groups = ["tools", "actions", "exit"]  →  [↑][笔][橡皮] │ [清屏][⋯] │ [⏻]
        groups = ["pager"]                     →  [ ‹  26/41  › ]  （独立小 pill）

    **工具栏与翻页栏是两套独立的条**：``bottom_center`` 是工具栏
    （tools/actions/exit），``bottom_left`` 与 ``bottom_right`` 各是一只翻页
    pill —— 同一套组件渲染三份，只是 ``groups`` 不同。
    注意两边的横向内边距**不是同一档**：工具栏 9、翻页 pill 只有 4
    （L1 的圆钮自带 4px 外边距，几乎贴着 pill 边缘）。

    **工具组是「圆的分段控件」**（``ToolSegment``，基类 RinUI 的
    ``Segmented``）：胶囊容器 + 每页一枚圆形图标，选中的那页浮现圆钮、
    没有下划线。组内互斥与 ``currentIndex`` 由 ``TabBar`` 基类提供，
    ``currentIndex ↔ Backend.activeTool`` 由本组件双向同步（后端换工具
    —— 快捷键 / 托盘 —— 时选中页自动跟随）。

    **「显示按钮文本」**（``presentation.buttons.show_labels``，入口在主界面编辑器 →
    选中工具栏 → 设置项）：打开后工具栏的按钮从「直径 44 的圆」变成「图标 + 名称」的
    胶囊，整条按文字实际宽度撑宽；**翻页 pill 不参与** —— 它本来就是「小、聚拢」的
    形态，加文字会把它拉成一条长条（见 ``showLabels`` 的说明）。

    ``corner`` 由 Python 注入（bottom_left / bottom_right / ...），
    每组显隐由 ``corners.<corner>.groups`` 决定。

    注意：``Flow`` 是定位器，其子项**不能使用 anchors**；
    需要居中的内容一律包一层 ``Item`` 后再用 anchors。
*/
Item {
    id: dock

    property string corner: "bottom_left"

    /*! 挂在屏幕**右侧**（``bottom_right``）—— 快速切页面板跟着它右对齐，
        于是「面板从条的这一侧长出去」的观感两个角落一致。 */
    readonly property bool cornerIsRight: corner.indexOf("right") >= 0

    // ------------------------------------------------------------ 配置读取
    readonly property var cfg: Backend.presentationConfig

    /*! **组件整体缩放倍率**（``presentation.scale``，入口：设置 → 主界面 →
        「缩放大小」滑块，50%~200%）。1.0 = 设计原档。

        画法是一个 ``scale`` 变换打在底板上 —— 于是投影、渐变高光、图标、页码
        文字**一起**等比缩放，不用逐项乘。代价是「内部」尺寸（``contentHeight`` /
        ``hitSize`` / ``pillRadius`` …）仍活在**设计单位**里，而 ``width`` /
        ``height`` / ``shadowMargin`` / ``interactiveRect`` 这几个**对外**的量
        要换算成屏幕像素：Python 摆位（``windows.py::_position_dock``）与区域
        塑形、编辑器预览的命中测试读的都是后者，换算好了那三处**一行都不用改**。

        ⚠️ 别把倍率乘进下面那些尺寸令牌（``barHeight`` / ``hitSize`` …）：那是
        「设计单位」，再乘一遍就是**双重缩放**，条会变成设计值的平方倍。 */
    readonly property real scaleFactor: {
        var value = cfg.scale !== undefined ? Number(cfg.scale) : 1.0
        if (!(value > 0))
            return 1.0
        // 手改配置兜底：滑块只给 0.5~2.0，越界值钳到 0.25~4.0，别让一个手滑的
        // 0 把控制条缩没（也挡住负数）。
        return Math.max(0.25, Math.min(4.0, value))
    }

    readonly property var cornerCfg: {
        var corners = cfg.corners !== undefined ? cfg.corners : ({})
        return corners[corner] !== undefined ? corners[corner] : ({})
    }
    readonly property var groups: cornerCfg.groups !== undefined ? cornerCfg.groups : []

    readonly property var surfaceCfg: cfg.surface !== undefined ? cfg.surface : ({})
    readonly property var shadowCfg: surfaceCfg.shadow !== undefined ? surfaceCfg.shadow : ({})
    /*! CW2 小组件同款渐变边框高光（工具栏与翻页 pill 共用）。 */
    readonly property bool highlightEnabled: surfaceCfg.highlight !== undefined
        ? surfaceCfg.highlight === true : true
    /*! 高光环是否真的在画（自检用；经 FlyoutSurface 透出）。 */
    readonly property bool highlightRingVisible: bar.highlightRingVisible
    readonly property var buttonsCfg: cfg.buttons !== undefined ? cfg.buttons : ({})
    readonly property var dividerCfg: cfg.divider !== undefined ? cfg.divider : ({})
    readonly property var segmentCfg: cfg.segment !== undefined ? cfg.segment : ({})
    readonly property var overflowCfg: cfg.overflow !== undefined ? cfg.overflow : ({})
    readonly property var pagerCfg: cfg.pager !== undefined ? cfg.pager : ({})
    readonly property var exitCfg: cfg.exit !== undefined ? cfg.exit : ({})
    readonly property var toolsCfg: cfg.tools !== undefined ? cfg.tools : []
    readonly property var actionsCfg: cfg.actions !== undefined ? cfg.actions : []
    readonly property var penCfg: cfg.pen !== undefined ? cfg.pen : ({})
    readonly property var inkCfg: cfg.ink !== undefined ? cfg.ink : ({})
    // ---- 尺寸（默认值就是 Lumi 里按实测比例定的那一档）----
    readonly property int barHeight: cfg.bar_height !== undefined ? cfg.bar_height : 56
    readonly property int surfacePaddingX: surfaceCfg.padding_x !== undefined
        ? surfaceCfg.padding_x : Lumi.dockPaddingX
    readonly property int surfacePaddingY: surfaceCfg.padding_y !== undefined
        ? surfaceCfg.padding_y : Lumi.dockPaddingY
    readonly property real surfaceRadius: surfaceCfg.radius !== undefined
        ? surfaceCfg.radius : Lumi.dockSurfaceRadius
    readonly property real surfaceOpacity: surfaceCfg.opacity !== undefined
        ? surfaceCfg.opacity : Lumi.dockSurfaceOpacity
    /*! 钳制后的**实际**圆角（胶囊时为 高/2）。自检读这个值。
        ⚠️ **设计单位**（缩放变换之前）—— 屏幕上量到的半径还要乘 ``scaleFactor``。 */
    readonly property real pillRadius: bar.effectiveRadius

    /*! 内容行高度：底板扣掉上下 padding —— 图标按钮、退出键共用这一档。 */
    readonly property int contentHeight: barHeight - surfacePaddingY * 2

    /*! **显示按钮文本**（``presentation.buttons.show_labels``，入口在主界面编辑器 →
        选中工具栏 → 设置项）：按钮从「直径 44 的圆」变成「图标 + 名称」的胶囊，
        整条按文字宽度自然变宽。

        ⚠️ **只作用于工具栏那几块**（工具 / 动作 / 溢出 / 退出），翻页 pill **不参与**
        —— 它本来就是「小、聚拢」的形态（沿轴留白只有 4），加文字会把它拉成一条
        长条，与「翻页栏更紧凑」的设计初衷正好相反。见配置里的 ``show_labels`` 注释。 */
    readonly property bool showLabels: buttonsCfg.show_labels === true

    readonly property int iconSize: buttonsCfg.icon_size !== undefined
        ? buttonsCfg.icon_size : Lumi.dockIconSize
    readonly property int hitSize: buttonsCfg.hit_size !== undefined
        ? buttonsCfg.hit_size : Lumi.dockHitSize
    readonly property int buttonSpacing: buttonsCfg.spacing !== undefined
        ? buttonsCfg.spacing : Lumi.dockButtonSpacing

    readonly property int dividerWidth: dividerCfg.width !== undefined ? dividerCfg.width : 1
    readonly property int dividerHeight: dividerCfg.height !== undefined ? dividerCfg.height : 20
    readonly property int dividerGap: dividerCfg.gap !== undefined ? dividerCfg.gap : 14

    readonly property int pagerWidth: pagerCfg.width !== undefined ? pagerCfg.width : 48
    readonly property int pagerSpacing: pagerCfg.spacing !== undefined ? pagerCfg.spacing : 14
    readonly property int pagerPillPaddingX: pagerCfg.surface_padding_x !== undefined
        ? pagerCfg.surface_padding_x : Lumi.dockPagerPaddingX

    // ---- 页码快速跳转（点页码展开的面板，``presentation/PageJumpPanel.qml``）----
    // 出处是 Luminalium 1 的「点按翻页」扩展。⚠️ 形态在 2026-10-06 **返工过一遍**：
    // 第一版做成「5 列页码网格 + 贴着控制条」，用户对着 L1 说「不像」，于是改成
    // L1 的样子 —— **一整条贴窗口边的侧栏**（单列 16:9 缩略图、页码压右下角、
    // 当前页 2px accent 描边）。取舍与 L1 原值列在 ``PageJumpPanel.qml`` 头注释里。
    readonly property var jumpCfg: pagerCfg.jump !== undefined ? pagerCfg.jump : ({})
    /*! 面板的总开关（``presentation.pager.jump.enabled``）。关掉后页码区不再
        可点、也不再给 hover 提示 —— 「点不动」和「看着能点但没反应」是两回事。 */
    readonly property bool jumpEnabled: jumpCfg.enabled !== false

    // ---- 分段控件（工具组）----
    readonly property int segmentPaddingX: segmentCfg.padding_x !== undefined
        ? segmentCfg.padding_x : Lumi.dockSegmentPadding
    readonly property int segmentSpacing: segmentCfg.spacing !== undefined
        ? segmentCfg.spacing : Lumi.dockSegmentSpacing
    /*! 分段胶囊的**实际**圆角（= 高/2，钳制后）。自检读这个值。 */
    readonly property real segmentPillRadius: present("tools")
        ? toolSegment.effectiveRadius : 0
    /*! 当前分页数（自检用；没启用工具组时为 0）。 */
    readonly property int segmentItemCount: present("tools") ? toolsCfg.length : 0
    /*! ``TabBar.count`` —— Repeater 的项**真的进了**容器的 contentModel
        （配置长度只能证明 model 有几条，这条才证明接线成立）。 */
    readonly property int segmentPageCount: present("tools") ? toolSegment.count : 0

    // ---- 开关 ----
    readonly property bool shadowEnabled: shadowCfg.enabled !== undefined
        ? shadowCfg.enabled : true
    /*! 投影余量（**设计单位**）—— 传给 ``FlyoutSurface`` 用，别外传。 */
    readonly property int shadowMarginBase: shadowCfg.margin !== undefined
        ? shadowCfg.margin : Lumi.dockShadowMargin
    /*! 投影余量（**屏幕像素**）—— Python 摆位与编辑器预览读的是这个：
        ``windows.py::_position_dock`` 用它把 ``margin_x/margin_y``（视觉距离）
        换算成 Item 坐标。跟着 ``scaleFactor`` 走，否则缩放后贴边距离会漂。 */
    readonly property int shadowMargin: Math.round(shadowMarginBase * scaleFactor)
    readonly property real shadowBlur: shadowCfg.blur !== undefined ? shadowCfg.blur : 18
    readonly property real shadowOffsetY: shadowCfg.offset_y !== undefined
        ? shadowCfg.offset_y : 6
    readonly property bool overflowEnabled: overflowCfg.enabled !== undefined
        ? overflowCfg.enabled : true

    // ---- 图标 ----
    readonly property string overflowIcon: overflowCfg.icon !== undefined
        ? overflowCfg.icon : "ic_fluent_more_horizontal_20_filled"
    readonly property string overflowTooltip: overflowCfg.tooltip !== undefined
        ? overflowCfg.tooltip : qsTr("更多操作")
    readonly property string pagerIconPrev: pagerCfg.icon_prev !== undefined
        ? pagerCfg.icon_prev : "ic_fluent_chevron_left_20_filled"
    readonly property string pagerIconNext: pagerCfg.icon_next !== undefined
        ? pagerCfg.icon_next : "ic_fluent_chevron_right_20_filled"
    readonly property string exitIcon: exitCfg.icon !== undefined
        ? exitCfg.icon : "ic_fluent_power_20_filled"
    readonly property string exitLabel: exitCfg.label !== undefined
        ? exitCfg.label : qsTr("退出放映")
    /*! ``default``（缺省）= 与其他按钮同款的透明圆钮 + 主题色图标；
        ``danger`` = L1 的 .tool-btn-danger（红色图标透明圆钮）。
        强调色实底版式已取消（2026-09-25）。 */
    readonly property string exitStyle: exitCfg.style !== undefined
        ? exitCfg.style : "default"
    /*! 两种版式**尺寸相同**（都是直径 = 内容高的圆），自检靠这两个颜色区分。 */
    readonly property color exitFillColor: exitStyle === "danger"
        ? Lumi.dockDangerFill : Lumi.dockButtonHoverFill
    readonly property color exitIconColor: exitStyle === "danger"
        ? Lumi.dockDangerIcon : Lumi.textPrimary

    // ============================================================ 区块编排
    /*! 区块顺序固定；``corners.<corner>.groups`` 只需是它的子集。 */
    readonly property var sectionOrder: ["tools", "actions", "pager", "exit"]

    /*! 这一区块在当前角落是否呈现。 */
    function present(id) {
        if (groups.indexOf(id) < 0) {
            return false
        }
        if (id === "pager") {
            return pagerCfg.enabled !== false
        }
        if (id === "exit") {
            return exitCfg.enabled !== false
        }
        return true
    }

    readonly property int presentCount: {
        var n = 0
        for (var i = 0; i < sectionOrder.length; i++) {
            if (present(sectionOrder[i])) {
                n++
            }
        }
        return n
    }

    readonly property bool dividerEnabled: dividerCfg.enabled !== false && presentCount > 1

    /*! 这一块之前是否还有别的可见块 —— 有才画分隔线。 */
    function dividerBefore(id) {
        if (!dividerEnabled || !present(id)) {
            return false
        }
        for (var i = 0; i < sectionOrder.length; i++) {
            var s = sectionOrder[i]
            if (s === id) {
                return false
            }
            if (present(s)) {
                return true
            }
        }
        return false
    }

    /*! 只剩翻页一块时，底板退化成「留白很紧的小 pill」（L1 的 .flipper）。 */
    readonly property bool pagerOnly: presentCount === 1 && present("pager")

    /*! 沿轴向内边距（横条即左右）。工具条 9、翻页 pill 只有 4（两档）。 */
    readonly property int effPaddingAlong: pagerOnly ? pagerPillPaddingX : surfacePaddingX
    /*! 横向（垂直于轴）内边距 —— 与工具条那一档共用（上下都是 9）。 */
    readonly property int effPaddingCross: surfacePaddingY

    // ------------------------------------------------------- 工具 ↔ 选中页
    /*! ``presentation.tools`` 里 id 为 ``toolId`` 的下标，找不到回落 0。 */
    function toolIndex(toolId) {
        for (var i = 0; i < toolsCfg.length; i++) {
            if (toolsCfg[i].id === toolId) {
                return i
            }
        }
        return 0
    }

    function toolIdAt(index) {
        return (index >= 0 && index < toolsCfg.length) ? toolsCfg[index].id : ""
    }

    // ----------------------------------------------------------- 笔的选单
    // 2026-10-01 用户指令：「当目前工具已经是笔的时候弹出如图的选单」——
    // 第一下点「笔」是**切工具**，已经切过去了再点一下才弹选单（与 Figma /
    // PowerPoint 自己的工具按钮同一种习惯：二次点击 = 打开这个工具的选项）。
    /*! 色板（``presentation.pen.palette``，缺省 30 色）。
        ⚠️ 只有**带工具组的**控制条才给色板：翻页 pill 也挂着本组件，给了就是
        白建 30 个色点（它们永远不可见）。空数组 → ``Repeater`` 一个项都不建。 */
    readonly property var penPaletteColors: present("tools") && penCfg.palette !== undefined
        ? penCfg.palette : []
    readonly property int penPaletteColumns: penCfg.columns !== undefined
        ? penCfg.columns : 10
    /*! 还没选过颜色时预点亮的那一格（只是选单的初始焦点，不会写进 PowerPoint）。 */
    readonly property color penDefaultColor: penCfg.default !== undefined
        ? penCfg.default : "transparent"
    /*! 选单该点亮哪一格：后端记着的墨迹色；没选过时用配置的默认色。
        ⚠️ 它只反映「用户在我们这儿选过的色」—— 用户若在 PowerPoint 自带的
        UI 里改笔色，这里不会跟着变（那要跨线程回读 COM 快照，见
        ``ppt_controller._refresh_snapshot`` 里 pen_color 的节流读取）。 */
    readonly property color penSelectedColor: Backend.penColor !== ""
        ? Backend.penColor : penDefaultColor
    /*! 选单展开着没有（``interactiveRect`` 与真机区域塑形都看它）。 */
    readonly property bool paletteOpened: penPalette.opened

    // ---- 笔的粗细档（2026-10-07 用户指令：自建批注）----
    // 与色板同一条链路：档位从 ``presentation.pen.widths`` 整块读（不登记
    // SETTING_PATHS，理由见 bridge.py 对应注释），选中值是后端会话状态
    // （``Backend.penWidth``，不落配置 —— 与笔色同一个读法）。
    /*! 粗细档（``presentation.pen.widths``）。与色板同一条规矩：只有带工具组
        的控制条才给 —— 翻页 pill 也挂着本组件，给了就是白建。空数组 →
        卡片里「粗细」整段（连同分隔线）不出。 */
    readonly property var penPaletteWidths: present("tools") && penCfg.widths !== undefined
        ? penCfg.widths : []
    /*! 还没选过粗细时预点亮的那一档（``presentation.pen.default_width``，
        **存的是值不是下标**，见配置注释）。 */
    readonly property real penDefaultWidth: penCfg.default_width !== undefined
        ? Number(penCfg.default_width) : 0
    /*! 选单该点亮哪一档：后端记着的粗细；没选过时用配置的默认档。
        com 引擎下这一行照样显示，但点了应用层忽略（PowerPoint 的放映笔
        没有粗细接口 —— 见 ``application.py::_on_action`` 的 ``pen_width:`` 分支）。 */
    readonly property real penSelectedWidth: Backend.penWidth > 0
        ? Backend.penWidth : penDefaultWidth

    // ---- 橡皮子模式卡片（2026-10-07 用户指令：自建批注）----
    // 与笔选单同一个交互习惯：工具已经是橡皮时再点一下「橡皮」→ 浮出
    // 「整笔擦除 / 像素擦除」两行。选中值直接读写配置
    // （``presentation_ink_eraser_mode``，持久 —— 与笔色/粗细的会话态不同：
    // 子模式是用户偏好，重启后不该悄悄退回默认）。
    /*! 橡皮子模式卡片展开着没有（``interactiveRect`` 与真机区域塑形都看它）。 */
    readonly property bool eraserPaletteOpened: eraserPalette.opened

    // ---- 像素橡皮的粗细档（2026-10-08 用户指令：自建批注）----
    // 与笔的粗细档同一条链路：档位从 ``presentation.ink.eraser_widths`` 整块读
    // （不登记 SETTING_PATHS，理由见 bridge.py 对应注释），选中值是后端会话
    // 状态（``Backend.eraserWidth``，不落配置 —— 与笔色/粗细同一个读法）。
    // 整笔擦除模式下卡片里整段不出（EraserModeCard 自己按 selectedMode 藏）。
    /*! 粗细档（``presentation.ink.eraser_widths``）。与笔同一条规矩：只有带
        工具组的控制条才给 —— 翻页 pill 也挂着本组件，给了就是白建。 */
    readonly property var eraserPaletteWidths: present("tools") && inkCfg.eraser_widths !== undefined
        ? inkCfg.eraser_widths : []
    /*! 还没选过橡皮粗细时预点亮的那一档（``presentation.ink.eraser_default_width``，
        **存的是值不是下标**，见配置注释）。 */
    readonly property real eraserDefaultWidth: inkCfg.eraser_default_width !== undefined
        ? Number(inkCfg.eraser_default_width) : 0
    /*! 卡片该点亮哪一档：后端记着的粗细；没选过时用配置的默认档。
        com 引擎下这一行照样显示，但点了应用层忽略（见
        ``application.py::_on_action`` 的 ``eraser_width:`` 分支）。 */
    readonly property real eraserSelectedWidth: Backend.eraserWidth > 0
        ? Backend.eraserWidth : eraserDefaultWidth

    /*! 快速切页面板展开着没有 —— 与 ``paletteOpened`` 同一个用途（``interactiveRect``
        / 区域塑形），另外 Python 侧还靠它决定「光标移出控制条了要不要收面板」
        （见 ``windows.py::_watch_overlay``）。 */
    readonly property bool jumpPanelOpened: jumpPanel.opened

    /*! 可用宽度（**屏幕逻辑像素**）= 所在**窗口**的宽 —— 遮罩层是铺满放映窗口的
        整屏窗口，所以窗口尺寸就是面板能横着占的地方。

        ⚠️ 别改成 ``parent.width``：``TopWindow`` 的 ``containerItem`` 是
        ``anchors.fill: parent``，而那个 ``Qt.Tool`` 透明窗口的 contentItem 尺寸
        **实测不可靠**（0 / 陈旧值 / 建窗口那一刻的默认值，取决于读的时机）——
        拿它算可用空间，面板会被静默压成单列。竖版同款（见 ``SidePager``）。 */
    readonly property real availableWidth: {
        var win = Window.window
        if (win) {
            return win.width
        }
        return parent ? parent.width : 0
    }

    /*! 可用高度（**屏幕逻辑像素**）= 所在**窗口**的高。

        与 ``availableWidth`` 同一个用途、同一条告诫（别改成 ``parent.height``）。
        快速切页面板贴窗口边铺满整高之后，它取代了原来那条「从条往上还剩多少」
        的算式 —— 面板高度现在由**窗口**决定，与条在哪、多高都无关。 */
    readonly property real availableHeight: {
        var win = Window.window
        if (win) {
            return win.height
        }
        return parent ? parent.height : 0
    }

    /*! 点页码区：开 / 关面板。总页数为 0（没读到页码）时不动 —— 空面板没有意义，
        而「点了一下弹出一块空白」比「点不动」更像坏了。 */
    function toggleJumpPanel() {
        if (!present("pager") || !jumpEnabled || Backend.slideTotal <= 0) {
            return
        }
        jumpPanel.opened = !jumpPanel.opened
    }

    /*! 收起切页面板。给 Python 侧的「点外部收起」调 —— 面板外的点击在区域塑形
        模式下是系统级穿透的，QML 里收不到（见 ``PageJumpPanel`` 头注释）。 */
    function closeJumpPanel() {
        jumpPanel.opened = false
    }

    /*! 收起两张工具卡（笔色板 / 橡皮子模式卡）。给 Python 侧的「点空白收起」
        调 —— 2026-10-08 用户报告（自建批注）：卡开着时点画布空白不收起。
        卡外的点击要么落在墨迹窗口（self 引擎笔/橡皮态，由 InkLayer 的起笔钩子
        把第一按消费成收卡），要么系统级穿透（com 引擎 / 区域塑形之外，由
        ``windows._dismiss_tool_cards_on_leave`` 按光标位置代判）—— 两条路上
        QML 自己都收不到这个点击，只能由 Python 代为调用（与 ``closeJumpPanel``
        同一个通道）。 */
    function closeToolCards() {
        penPalette.opened = false
        eraserPalette.opened = false
    }

    /*! 按下分页时选的是谁 —— ``clicked`` 落地时 TabBar 早把 ``currentIndex``
        换好了，那时再读 ``Backend.activeTool`` 分不清「切工具」和「再点一次」。 */
    property string toolBeforePress: ""

    function noteToolPress() {
        toolBeforePress = Backend.activeTool
    }

    function activateTool(toolId) {
        var was = toolBeforePress
        toolBeforePress = ""
        // 有「二次点击选项卡」的工具：笔（色板/粗细）与橡皮（子模式）。
        // 第一下点 = 切工具，已经切过去了再点一下才弹卡片（2026-10-07 起
        // 橡皮也加入这个习惯，见 EraserModeCard.qml 头注释）。
        if ((toolId !== "pen" && toolId !== "eraser") || was !== toolId) {
            // 这一下是「切工具」（或点了别的），所有浮出层都跟着收起来 ——
            // 用户已经在做别的事了，面板再飘着就是挡路
            penPalette.opened = false
            eraserPalette.opened = false
            jumpPanel.opened = false
            return
        }
        if (toolId === "pen") {
            penPalette.opened = !penPalette.opened
        } else {
            eraserPalette.opened = !eraserPalette.opened
        }
    }

    // ------------------------------------------------------------- 控制条本体
    // 根节点是 Item（不再是独立窗口）：所有角落的控制条都挂在
    // TopWindow.qml（全屏「顶层窗口」）的容器里，由 Python 定位。
    // 窗口级属性（置顶 / 无边框 / 点击穿透）由顶层窗口统一负责。

    /*! 本条表面（不含投影余量）的交互矩形，坐标相对本 Item。
        顶层窗口用它计算「鼠标何时落在工具栏上」（其余区域点击穿透）。

        ⚠️ 它是**动态**的：笔选单展开时，卡片浮在工具栏**上方**（dock Item 的
        包围盒之外），必须一并包进来 —— 否则那块区域既画不出来（``SetWindowRgn``
        裁掉）也点不动（点击直接穿透到 PowerPoint，在幻灯片上乱画一笔）。
        变化时会发 ``hitRectChanged``，Python 侧（``windows.py``）据此**立刻**
        重算窗口区域，不用等 800ms 一拍的 ``_assert_topmost``。 */
    readonly property rect interactiveRect: {
        // 控制条底板表面：围在投影余量内侧。全部换算到**根 Item 坐标**
        // （= 屏幕像素）—— 底板自己活在设计单位里（``scaleFactor`` 变换之前），
        // 而读它的 Python 摆位 / 区域塑形要的是屏幕上真实占多大。
        var s = scaleFactor
        var left = (bar.x + bar.margin) * s
        var right = (bar.x + bar.implicitWidth - bar.margin) * s
        var top = (bar.y + bar.margin) * s
        var bottom = (bar.y + bar.implicitHeight - bar.margin) * s
        if (paletteOpened && penPalette.visible) {
            // 选单也跟着 ``scaleFactor`` 缩放（见 ``penPalette`` 的 scale）：
            // 它的 x/y 已经是根 Item 坐标，宽高要乘倍率。
            left = Math.min(left, penPalette.x)
            right = Math.max(right, penPalette.x + penPalette.width * s)
            top = Math.min(top, penPalette.y)
        }
        // 橡皮子模式卡片与笔选单同一条命（2026-10-07 自建批注）：浮在 dock
        // 包围盒之外，不包进来就既不画也点不动。
        if (eraserPaletteOpened && eraserPalette.visible) {
            left = Math.min(left, eraserPalette.x)
            right = Math.max(right, eraserPalette.x + eraserPalette.width * s)
            top = Math.min(top, eraserPalette.y)
        }
        // 快速切页面板是同一回事：它浮在条**上方**（条在屏幕下部），尺寸随页数
        // 变，必须整块包进来 —— 否则格子点不动（穿透到 PowerPoint 就变成在幻灯片
        // 上乱画一笔），而且那块会被 ``SetWindowRgn`` 整个裁掉、连画都画不出来。
        if (jumpPanelOpened && jumpPanel.visible) {
            left = Math.min(left, jumpPanel.x)
            right = Math.max(right, jumpPanel.x + jumpPanel.width * s)
            top = Math.min(top, jumpPanel.y)
            bottom = Math.max(bottom, jumpPanel.y + jumpPanel.height * s)
        }
        return Qt.rect(left, top, Math.max(right - left, 0), Math.max(bottom - top, 0))
    }

    /*! 命中矩形变了（笔选单开合）。Python 侧连这个信号去重算窗口区域。 */
    signal hitRectChanged()

    onInteractiveRectChanged: hitRectChanged()

    /*! 根 Item 的尺寸 = **缩放后**的屏幕像素（Python 摆位 / 区域塑形 / 编辑器预览
        都读它，见 ``scaleFactor`` 的说明）。 */
    implicitWidth: Math.round(bar.implicitWidth * scaleFactor)
    implicitHeight: Math.round(bar.implicitHeight * scaleFactor)
    width: implicitWidth
    height: implicitHeight

    FlyoutSurface {
        id: bar
        // ⚠️ **不能用 ``anchors.fill: parent``**：根 Item 已经是**缩放后**的尺寸，
        //    再铺满就等于把缩放算了两遍。底板保持设计尺寸，缩放交给下面这个
        //    ``scale`` 变换 —— ``transformOrigin: TopLeft`` 让底板左上角钉在根
        //    Item 的 0 点，两边坐标原点重合。
        width: implicitWidth
        height: implicitHeight
        scale: dock.scaleFactor
        transformOrigin: Item.TopLeft
        paddingX: dock.effPaddingAlong
        paddingY: dock.effPaddingCross
        surfaceRadius: dock.surfaceRadius
        surfaceOpacity: dock.surfaceOpacity
        highlightEnabled: dock.highlightEnabled
        shadowEnabled: dock.shadowEnabled
        shadowMargin: dock.shadowMarginBase
        shadowBlur: dock.shadowBlur
        shadowOffsetY: dock.shadowOffsetY

        // ==================================================== 1. 工具分段
        // 圆的分段控件（基类 Rin.Segmented = TabBar）：组内互斥与 currentIndex
        // 都由基类提供。绑定 ``currentIndex: dock.toolIndex(...)`` 给出初值并
        // 跟随后端切换；用户点击会写 currentIndex 打断绑定，由底部 Connections
        // 继续同步（标准 TabBar 用法）。
        ToolSegment {
            id: toolSegment
            visible: dock.present("tools")
            itemHeight: dock.contentHeight
            edgePadding: dock.segmentPaddingX
            itemSpacing: dock.segmentSpacing

            currentIndex: dock.toolIndex(Backend.activeTool)

            onCurrentIndexChanged: {
                var id = dock.toolIdAt(currentIndex)
                if (id !== "" && Backend.activeTool !== id) {
                    Backend.selectTool(id)
                }
            }

            Repeater {
                model: dock.toolsCfg

                delegate: ToolSegmentItem {
                    // 名字带 id，自检与调试找得到具体是哪一个工具（「指针 / 笔 /
                    // 橡皮」三个项长得一模一样）
                    objectName: "dockTool_" + (modelData.id !== undefined
                                               ? modelData.id : "?")
                    itemHeight: dock.contentHeight
                    glyphSize: dock.iconSize
                    tooltip: modelData.label !== undefined ? modelData.label : ""
                    icon.name: modelData.icon !== undefined ? modelData.icon : ""
                    label: modelData.label !== undefined ? modelData.label : ""
                    showLabel: dock.showLabels
                    // 选单正开着时给对应工具描一圈（见 ``expanded``）：
                    // 笔 ↔ 色板卡，橡皮 ↔ 子模式卡（2026-10-07 自建批注）。
                    expanded: (dock.paletteOpened && modelData.id === "pen")
                        || (dock.eraserPaletteOpened && modelData.id === "eraser")
                    // 按下时就记住「选的是谁」（见 ``noteToolPress``），
                    // 抬起后 ``clicked`` 里才判得出是切工具还是再点一次。
                    onPressed: dock.noteToolPress()
                    onClicked: dock.activateTool(modelData.id)
                }
            }
        }

        // （工具分段右侧**没有分隔线**：分段自带胶囊容器，紧跟着再来一条竖线
        //  会显得「双层边」。分隔线只画在 动作 → 翻页 → 退出 之间。）

        // ==================================== 2. 动作按钮 + 溢出「⋯」
        Flow {
            visible: dock.present("actions")
            spacing: dock.buttonSpacing

            Repeater {
                model: dock.actionsCfg

                delegate: IconButton {
                    iconName: modelData.icon !== undefined ? modelData.icon : ""
                    tooltip: modelData.tooltip !== undefined ? modelData.tooltip : ""
                    // 名称文本取 ``label``（「清屏」），**不是** ``tooltip``
                    //（「清屏（擦除本页全部墨迹）」）—— 条上要的是短名
                    label: modelData.label !== undefined ? modelData.label : ""
                    showLabel: dock.showLabels
                    hitSize: dock.hitSize
                    glyphSize: dock.iconSize
                    onClicked: Backend.triggerAction(modelData.id)
                }
            }

            IconButton {
                visible: dock.overflowEnabled
                iconName: dock.overflowIcon
                tooltip: dock.overflowTooltip
                label: dock.overflowTooltip
                showLabel: dock.showLabels
                hitSize: dock.hitSize
                glyphSize: dock.iconSize
                onClicked: Backend.triggerAction("overflow")
            }
        }

        // ==================================== 分隔线（动作 → 翻页）
        SectionDivider {
            visible: dock.dividerBefore("pager")
            dividerWidth: dock.dividerWidth
            dividerHeight: dock.dividerHeight
            dividerGap: dock.dividerGap
            rowHeight: dock.contentHeight
        }

        // ==================================================== 3. 翻页组
        // ⚠️ 这一段**不接** ``showLabels``：翻页 pill 保持「小、聚拢」的形态，
        //    见上面 ``showLabels`` 的说明。
        Flow {
            visible: dock.present("pager")
            spacing: dock.pagerSpacing

            IconButton {
                iconName: dock.pagerIconPrev
                tooltip: qsTr("上一页")
                hitSize: dock.hitSize
                glyphSize: dock.iconSize
                onClicked: Backend.previousSlide()
            }

            // 页码区 —— 除了显示，**还是快速切页面板的触发点**（L1 的点按翻页）。
            // 包一层 Item 是因为 ``Flow`` 的子项不能用 anchors（见头注释），
            // 而这个热区里要有「hover 底 + 脉冲文字 + 点击」三层。
            Item {
                id: pagerHit
                objectName: "dockPagerHit"
                width: dock.pagerWidth
                height: dock.contentHeight

                // hover 底：这是「这里能点」的唯一提示 —— 页码区平时看着只是一个
                // 数字，不给反馈没人会去点它。开了面板时也保持点亮，等于「面板是
                // 从这里长出来的」这条视觉连线。
                Rectangle {
                    objectName: "dockPagerHitSurface"
                    anchors.fill: parent
                    radius: Lumi.dockJumpItemRadius
                    color: pagerHitArea.containsMouse || dock.jumpPanelOpened
                        ? Lumi.dockJumpItemHover : "transparent"
                    Behavior on color {
                        ColorAnimation {
                            duration: Lumi.dockJumpFadeDuration
                            easing.type: Easing.OutQuint
                        }
                    }
                }

                // 页码变化走透明度脉冲（与竖版同一套节奏，见 PagePulse.qml）
                PagePulse {
                    anchors.fill: parent
                    page: Backend.slideIndex

                    Rin.Text {
                        anchors.centerIn: parent
                        typography: Rin.Typography.BodyLarge
                        text: Backend.slideTotal > 0
                            ? Backend.slideIndex + "/" + Backend.slideTotal
                            : "-/-"
                    }
                }

                MouseArea {
                    id: pagerHitArea
                    anchors.fill: parent
                    enabled: dock.jumpEnabled
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: dock.toggleJumpPanel()
                }
            }

            IconButton {
                iconName: dock.pagerIconNext
                tooltip: qsTr("下一页")
                hitSize: dock.hitSize
                glyphSize: dock.iconSize
                onClicked: Backend.nextSlide()
            }
        }

        // ==================================== 分隔线（翻页 → 退出）
        SectionDivider {
            visible: dock.dividerBefore("exit")
            dividerWidth: dock.dividerWidth
            dividerHeight: dock.dividerHeight
            dividerGap: dock.dividerGap
            rowHeight: dock.contentHeight
        }

        // ==================================================== 4. 退出放映
        ExitButton {
            visible: dock.present("exit")
            style: dock.exitStyle
            iconName: dock.exitIcon
            tooltip: dock.exitLabel
            label: dock.exitLabel
            showLabel: dock.showLabels
            buttonHeight: dock.contentHeight
            glyphSize: dock.iconSize
            onClicked: Backend.exitPresentation()
        }
    }

    // ==================================================== 笔的选单（浮出层）
    // 声明在 ``bar`` **之后** → 绘制、命中都在控制条之上。
    //
    // ⚠️ 它**不进** dock 的 ``implicitWidth/Height``（见组件头注释）：dock 一
    //    改尺寸，``windows.py::_position_dock`` 就要重摆，条会在「长大 / 归位」
    //    之间闪一帧。尺寸不动、纯靠绘制溢出，是这个交互最省事的形态 ——
    //    代价是 ``interactiveRect`` 必须自己把它包进来（上面那段就是）。
    PenPaletteCard {
        id: penPalette
        objectName: "penPalette"

        opened: false
        palette: dock.penPaletteColors
        columns: dock.penPaletteColumns
        selectedColor: dock.penSelectedColor
        // 粗细档（2026-10-07 自建批注）：空数组时卡片里整段不出（翻页 pill 那档）。
        widths: dock.penPaletteWidths
        selectedWidth: dock.penSelectedWidth

        // 与底板同倍率缩放 —— 整块选单跟着组件一起放大 / 缩小。
        // ``transformOrigin: TopLeft``：下面算的 x/y 是**根 Item 坐标**（未缩放
        // 的定位），缩放围绕左上角做，落点才不跟着漂。
        scale: dock.scaleFactor
        transformOrigin: Item.TopLeft

        // 贴着工具栏底板上沿往上摆：卡片**本体**（不含投影余量）的底边距底板上
        // 沿 ``Lumi.dockPaletteGap``。卡片自己的坐标含 shadowMargin，所以两边都
        // 要各扣/加一次。⚠️ 整条式子乘 ``scaleFactor``：底板的可见上沿在
        // ``bar.margin * scaleFactor`` 处（底板被缩放变换过），落点要跟着走。
        y: (bar.y + bar.margin - Lumi.dockPaletteGap
            - penPalette.shadowMargin - penPalette.cardHeight) * dock.scaleFactor
        // 左沿与底板的左沿对齐；卡片比条还宽，贴右下的角落会溢出屏幕 ——
        // 这时整块往左收（可用宽度从父级拿：父级是铺满整屏的容器）。
        x: {
            var s = dock.scaleFactor
            var want = (bar.margin - penPalette.shadowMargin) * s
            var limit = dock.parent ? dock.parent.width - dock.x : 0
            if (limit > 0 && want + penPalette.width * s > limit) {
                want = limit - penPalette.width * s
            }
            return want
        }

        onColorPicked: function (value) {
            // ⚠️ 必须转字符串：``color`` 直接喂给 ``@Slot(str)`` 过不了类型转换。
            Backend.setPenColor(value.toString())
        }

        onWidthPicked: function (value) {
            // 与颜色同一条路：先落 Backend（QML 回显选中档），再发
            // ``pen_width:<px>`` 给应用层 —— self 引擎落到 InkLayer.penWidth，
            // com 引擎忽略（见 ``application.py::_on_action``）。
            Backend.setPenWidth(value)
        }
    }

    // ======================================== 橡皮子模式卡片（浮出层）
    // 2026-10-07 用户指令：自建批注。与笔选单同一套约定（**不进** dock 的
    // ``implicitWidth/Height``、摆位公式、缩放、hitRect 机制全镜像），
    // 论证见 ``PenPaletteCard.qml`` / ``EraserModeCard.qml`` 头注释。
    EraserModeCard {
        id: eraserPalette
        objectName: "eraserPalette"

        opened: false
        // 配置是唯一事实源（持久偏好，不是会话态）：写了之后
        // ``application._on_config_changed`` 会实时推给在场的 InkLayer；
        // 陌生值兜底按 pixel 显示（与 InkLayer 的默认值一致）。
        selectedMode: Backend.settings.presentation_ink_eraser_mode === "stroke"
            ? "stroke" : "pixel"
        // 像素橡皮的粗细档（2026-10-08 自建批注）：空数组时卡片里整段不出
        // （翻页 pill 那档）；整笔擦除模式下卡片自己把这段藏起来。
        widths: dock.eraserPaletteWidths
        selectedWidth: dock.eraserSelectedWidth

        // 与底板同倍率缩放（同笔选单：x/y 是根 Item 坐标，缩放围绕左上角）。
        scale: dock.scaleFactor
        transformOrigin: Item.TopLeft

        // 摆位公式与笔选单逐字一致：贴着工具栏底板上沿往上摆、左沿与底板
        // 左沿对齐、屏幕右沿放不下时整块往左收。卡片小（两行），左对齐与
        // 笔选单摆在同一垂线上，用户认得「这是同一个位置的选项卡」。
        y: (bar.y + bar.margin - Lumi.dockPaletteGap
            - eraserPalette.shadowMargin - eraserPalette.cardHeight) * dock.scaleFactor
        x: {
            var s = dock.scaleFactor
            var want = (bar.margin - eraserPalette.shadowMargin) * s
            var limit = dock.parent ? dock.parent.width - dock.x : 0
            if (limit > 0 && want + eraserPalette.width * s > limit) {
                want = limit - eraserPalette.width * s
            }
            return want
        }

        onModePicked: function (mode) {
            // 落配置（持久）；层在不在场由应用层操心（``_on_config_changed``
            // 推在场的层，建窗时 ``_apply_ink_config`` 补）。卡片保持展开 ——
            // 与笔选单「点完颜色不收」同一个手感，用户可能接着换回来对比。
            Backend.setSetting("presentation_ink_eraser_mode", mode)
        }

        onWidthPicked: function (value) {
            // 与笔的粗细同一条路：先落 Backend（QML 回显选中档），再发
            // ``eraser_width:<px>`` 给应用层 —— self 引擎落到 InkLayer.eraserWidth，
            // com 引擎忽略（见 ``application.py::_on_action``）。
            Backend.setEraserWidth(value)
        }
    }

    // ============================================ 快速切页面板（点页码展开）
    // 声明在 ``bar`` 之后 → 绘制、命中都在控制条之上。
    //
    // ⚠️ 与笔选单同一条约定：**不进** dock 的 ``implicitWidth/Height`` ——
    //    dock 一改尺寸，``windows.py::_position_dock`` 就要重摆，条会在
    //    「长大 / 归位」之间闪一帧。尺寸不动、纯靠绘制溢出，代价是
    //    ``interactiveRect`` 必须自己把它包进来（上面那段就是）。
    PageJumpPanel {
        id: jumpPanel
        objectName: "pageJumpPanel"

        // 本角落**没有翻页组**时不铺卡片：那个角落根本没有页码区（没有触发点），
        // 面板实例只是跟着组件一起被建出来而已 —— 白建几十张卡片纯属浪费。
        // 底中那条工具栏就是这一档（它的 groups 是 tools/actions/exit）。
        total: dock.present("pager") ? Backend.slideTotal : 0
        current: Backend.slideIndex
        opened: false
        /*! 面板贴**窗口**的哪条边（L1 形态，见 ``PageJumpPanel.qml`` 头注释）。
            横版条在屏幕下部：左下角的条 → 面板贴左边，右下角 → 贴右边；
            底中的条取不到「哪一侧」，按左处理（L1 的判据是点击在屏幕左右哪半，
            条居中时两边等价）。 */
        side: dock.cornerIsRight ? "right" : "left"

        // 与底板同倍率缩放 —— 整块面板跟着组件一起放大 / 缩小。
        // ``transformOrigin: TopLeft``：下面算的 x/y 是**根 Item 坐标**（未缩放的
        // 定位），缩放围绕左上角做，落点才不跟着漂。
        scale: dock.scaleFactor
        transformOrigin: Item.TopLeft

        /*! 横向：贴**窗口**的左右边（``Lumi.dockJumpEdge``）。
            ⚠️ 面板 Item 的宽是**滑行路径的并集**（比卡片多一条 ``enterDistance``，
                见组件头注释），所以贴左边时要再往左让出一整条。
                式子是**屏幕逻辑像素**，而 ``want`` 要的是 dock 内部坐标 ——
                先把 ``dock.x``（本 dock 在窗口里的原点）扣掉。 */
        x: (dock.cornerIsRight
            ? dock.availableWidth
              - (Lumi.dockJumpEdge + jumpPanel.cardWidth) * dock.scaleFactor
            : (Lumi.dockJumpEdge - jumpPanel.enterDistance) * dock.scaleFactor)
            - dock.x

        /*! 纵向：L1 是 ``top: 24px`` —— 面板自己铺满整高，上下各让 24。
            与条的位置**无关**（这正是这次返工的重点：面板不再从条旁边长出来）。 */
        y: Lumi.dockJumpInset * dock.scaleFactor - dock.y

        /*! 可用高度（**设计单位**）= 窗口高减去上下那两条 24。
            与页数无关（L1 的面板高度由窗口决定），页数少时由组件自己收短。 */
        maxHeight: Math.max(dock.availableHeight / dock.scaleFactor
                            - Lumi.dockJumpInset * 2, 0)
        // 可用宽度 = 遮罩整宽换算回设计单位（面板只需别顶出窗口）
        maxWidth: Math.max(dock.availableWidth / dock.scaleFactor, 0)

        onPagePicked: function (page) {
            Backend.gotoSlide(page)
            // 跳完就收 —— 面板的使命结束了，留着反而挡住刚跳过去的那一页
            jumpPanel.opened = false
        }
    }

    // 用户点击后 currentIndex 的绑定被打断；后端发起的工具切换
    // （快捷键 / 托盘菜单）由这里继续同步到选中页。
    Connections {
        target: Backend

        function onActiveToolChanged() {
            var index = dock.toolIndex(Backend.activeTool)
            if (toolSegment.currentIndex !== index) {
                toolSegment.currentIndex = index
            }
            // 选单属于「笔」这个工位：换成指针 / 橡皮就收起来（否则它会跟着
            // 挂在条上方，而那时已经没有「笔的选项」可言了）。橡皮子模式卡片
            // 同理（2026-10-07 自建批注）—— 它属于「橡皮」这个工位。
            if (Backend.activeTool !== "pen") {
                penPalette.opened = false
            }
            if (Backend.activeTool !== "eraser") {
                eraserPalette.opened = false
            }
        }

        // 退出放映 → 收起浮出层（笔选单 / 橡皮子模式卡片 / 快速切页面板）：
        // 下一次放映进来时不该看到上次遗留的一块卡片。
        function onPresentationActiveChanged() {
            if (!Backend.presentationActive) {
                penPalette.opened = false
                eraserPalette.opened = false
                jumpPanel.opened = false
            }
        }
    }
}
