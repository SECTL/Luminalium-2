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

    ⚠️ **放大镜不进分段**（2026-10-06 用户指令：「放大镜不应当以 Segmented
    内排版」）。它是条上**紧跟着分段**的一枚独立圆钮（``dockZoomButton``），
    状态挂在**独立的** ``Backend.zoomActive`` 布尔上，**不占** ``activeTool``。
    为什么强调「不占」：放大镜不是 PowerPoint 的指针类型
    （``PpSlideShowPointerType`` 里没有这一项），它**不改变指针** ——
    用着放大镜的时候笔照样是笔。

    ⚠️⚠️ 早先把它塞进 ``activeTool``（取值 ``"zoom"``）试过，代价极大：
    ``ToolSegment.currentIndex`` 的绑定读 ``toolIndex(Backend.activeTool)``，
    「分段里没有这一页」会被翻译成「指针那一页」，于是点一下放大镜 → 工具被切回
    指针 → ``onActiveToolChanged`` 顺手把刚弹的面板收掉。**全程零报错**，
    只是面板「刚出来就没了」。

    ⚠️ **别再为它改这一行绑定**（试过三种写法，全留副作用）：绑定里自引用
    ``currentIndex`` = binding loop（Qt 静默作废整条绑定、属性落回默认 0）；
    块语法 + ``lastToolIndex`` 回退 = 分段项点不动。``activeTool`` 只取那三个
    指针类型之后，这里**原样就成立**。详见 ``ToolSegment`` 那处注释。

    * 两个高亮会并存，这是有意的：分段说的是「演示软件的指针是什么」，
      放大镜那枚说的是「视图是不是放大着」。

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
    readonly property var zoomCfg: cfg.zoom !== undefined ? cfg.zoom : ({})

    // ---- 尺寸（默认值就是 Lumi 里按实测比例定的那一档）----
    readonly property int barHeight: cfg.bar_height !== undefined ? cfg.bar_height : 56

    /*! 竖版（2026-10-07 用户指令：「为什么默认用户只会用横版」）。

        两侧布局（左 / 右 / 双组）且 ``pager.position == "side"`` 时，工具栏与
        翻页合并进 ``middle_left`` / ``middle_right``（贴屏幕左右、垂直居中），
        整条**转置成竖排** —— 与 ``SidePager`` 的转置账同源：横版的高（``bar_height``）
        变成竖版的宽，内容自上而下排。

        ⚠️ 朝向**由角落的垂直对齐推**（``middle`` = 竖），不看角名前缀 —— 与
        ``windows.py::_resolve_dock_qml`` 同一条口径。 */
    readonly property bool isVertical: corner.indexOf("middle") === 0

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

    /*! 底板**宽度**（设计单位）：横版由内容撑开（读 ``bar``），竖版恒等于
        ``bar_height``（转置 —— 与 ``SidePager`` 的 62 宽同源）。 */
    readonly property int barWidth: isVertical ? barHeight : bar.implicitWidth

    /*! 内容行高度：底板扣掉上下 padding —— 图标按钮、退出键共用这一档。
        ⚠️ 竖版由**宽度**算（转置）。 */
    readonly property int contentHeight: isVertical
        ? barWidth - (surfacePaddingX * 2)
        : barHeight - surfacePaddingY * 2

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
    /*! 分段当前选中页的下标（自检用；没启用工具组时为 -1）。

        为什么要挂一份：``toolSegment.currentIndex`` 挂在 ``ToolSegment`` 里，
        Python 侧够不着那个实例（``_find_named`` 只能按 ``objectName`` 找，而
        ``ToolSegment`` 没给名字），所以镜像到根Item 上。
        自检拿它盯「切到放大镜时分段选中页不动」—— 那个 bug（2026-10-06）就是
        这里被悄悄拉回 0，进而把工具切回指针。 */
    readonly property int segmentCurrentIndex: present("tools")
        ? toolSegment.currentIndex : -1

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
    /*! 条上**放大镜入口**那枚独立圆钮的图标 / 名称 / 提示。
        ⚠️ 别和面板里七枚按钮的 ``zoom.icon_*`` / ``tooltip_*`` 混了 —— 那是
        另一组（放大 / 缩小 / 复位 / 四向移位），见``ZoomPanel`` 实例上的绑定。 */
    readonly property bool zoomEnabled: zoomCfg.enabled !== false
    readonly property string zoomIcon: zoomCfg.icon !== undefined
        ? zoomCfg.icon : "ic_fluent_search_20_filled"
    readonly property string zoomLabel: zoomCfg.label !== undefined
        ? zoomCfg.label : qsTr("放大镜")
    readonly property string zoomTooltip: zoomCfg.tooltip !== undefined
        ? zoomCfg.tooltip : qsTr("放大镜")
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
    /*! ``presentation.tools`` 里 id 为 ``toolId`` 的下标，**找不到返回 -1**。

        ⚠️ 返回 ``-1`` 而不是回落 0（2026-10-06）。回落 0 等于把「不认识的工具」
        翻译成「指针」—— 而 ``currentIndex`` 的绑定会照单全收写进去，触发
        ``onCurrentIndexChanged`` 把工具真切回指针。

        放大镜曾经就是这么栽的（那时它还占着 ``activeTool``）：症状是点一下放大镜，
        面板刚弹出来就被收掉，**全程零报错**。现在放大镜改用独立的
        ``Backend.zoomActive``、不再占 ``activeTool``，这条路已经走不到了 ——
        但 ``-1`` 仍留着当安全值（配置被改坏时不至于静默切错工具）。 */
    function toolIndex(toolId) {
        for (var i = 0; i < toolsCfg.length; i++) {
            if (toolsCfg[i].id === toolId) {
                return i
            }
        }
        return -1
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

    /*! 快速切页面板展开着没有 —— 与 ``paletteOpened`` 同一个用途（``interactiveRect``
        / 区域塑形），另外 Python 侧还靠它决定「光标移出控制条了要不要收面板」
        （见 ``windows.py::_watch_overlay``）。 */
    readonly property bool jumpPanelOpened: jumpPanel.opened

    /*! 放大镜选单展开着没有（``interactiveRect`` / 区域塑形用）。

        ⚠️ 它**不参与** Python 侧那个「光标移出控制条就收面板」
        （``windows.py::_dismiss_jump_panels`` 只认 ``jumpPanelOpened``）：
        那是**工具自己的选项**，与笔的色板同一类 —— 用户要按好几下缩放 / 移位，
        中途光标飘出去就收起来会很难用。退路是「再点一下放大镜」或切工具。 */
    readonly property bool zoomPanelOpened: zoomPanel.opened

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

    /*! 放大镜选单要对齐的那枚圆钮（缓存实例）。

        ⚠️ **必须有这一层缓存，不能在绑定里直接查表**：``FlyoutSurface.contentItemByName``
        要读 ``inner.data``，而 ``QQuickItem::data`` 在 QML 里是 **non-bindable** ——
        直接写在绑定表达式里，每次求值都会刷一串
        ``depends on non-bindable properties: QQuickFlow::data`` 警告，而且
        ``showLabels`` / 工具数变化导致圆钮挪位置时**绑定追不到**，面板会错位。

        缓存实例之后，绑定读的是 ``zoomPanelAnchor`` 这个**可绑定**属性 + 圆钮自己的
        ``x`` / ``width``（也都是可绑定），依赖链恢复干净。刷新时机：条尺寸变化
        （``bar.width/height``，含 ``showLabels`` 切换与工具数变化）。 */
    property Item zoomPanelAnchor: null

    function _refreshZoomPanelAnchor() {
        zoomPanelAnchor = bar.contentItemByName("dockZoomButton")
    }

    Connections {
        target: bar
        function onWidthChanged() { dock._refreshZoomPanelAnchor() }
        function onHeightChanged() { dock._refreshZoomPanelAnchor() }
    }

    Component.onCompleted: _refreshZoomPanelAnchor()

    /*! 浮出卡片（笔选单 / 放大镜选单）的横向落点。

        返回的是**根 Item 坐标**（面板这个 Item 自己的 ``x``）。

        两块浮出层的锚**不一样**，这是有意的（2026-10-06 用户指令「要改成
        对齐圆钮」）：

        * 不传 ``anchor``（笔选单）→ 卡片左沿对齐**底板左沿**。笔在分段第一页，
          那个位置本来就在条的最左边，两者差一个 ``segmentPaddingX``，肉眼看
          是一回事。
        * 传 ``anchor``（放大镜）→ 卡片**中心线**对准那枚圆钮的中心线。圆钮在
          条的中间（紧跟分段之后），还按左沿对齐的话面板会明显偏在它左边
          （实测偏 100px 出头），看着像「不知道从哪冒出来的」。

        算式全在**设计单位**里做完，最后乘一次 ``scaleFactor`` —— 面板自己
        带 ``scale`` 变换（``transformOrigin: TopLeft``），所以「先设计单位
        对齐、再整体缩放」和「先缩放、再屏幕对齐」等价，前者好写也好读。

        ⚠️ 别用 ``anchor.mapToItem(dock, …)``：那个方法内部读的是 C++ 字段，
        **绑定引擎捕获不到**，于是 ``showLabels`` 一开、条变宽、圆钮挪位置，
        面板不会跟着动。显式读 ``bar.x`` / ``anchor.x`` / ``anchor.width``
        才是真的建立依赖。

        ⚠️ ``anchor`` 传的是**实例**（由调用方经 ``zoomPanelAnchor`` 缓存后给出），
        不是名字 —— 「按名字查表」会读 ``inner.data``（non-bindable，见
        ``zoomPanelAnchor`` 的说明）。

        卡片比条还宽、而条又贴着屏幕右 / 下角时会溢出屏幕 —— 这时整块往左收
        （可用宽度从父级拿：父级是铺满整屏的容器）。 */
    function flyoutX(panel, anchor) {
        var s = dock.scaleFactor
        var want
        if (anchor && anchor.visible && anchor.width > 0) {
            // 圆钮中心相对**底板**的横坐标（设计单位）＝ 底板内边距 + 圆钮在
            // ``Flow`` 里的 x + 半个圆钮。``bar.x`` 是底板在 dock 内的偏移
            // （另加 ``bar.margin`` 那份投影余量由下面 panel 的 margin 抵掉，
            // 与旧算式等价）。
            var innerX = bar.x + bar.paddingX
            var anchorCenter = innerX + anchor.x + anchor.width / 2
            // ⚠️ 扣的是 ``panel.shadowMargin + panel.cardWidth / 2``，**不是**
            //    ``panel.width``（后者含两侧 shadowMargin）—— 用它会多扣一个
            //    shadowMargin，面板偏左 20px（实测 200→84 而非 200→104）。
            want = anchorCenter - (panel.shadowMargin + panel.cardWidth / 2) * s
        } else {
            want = (bar.margin - panel.shadowMargin) * s
        }
        var limit = dock.parent ? dock.parent.width - dock.x : 0
        if (limit > 0 && want + panel.width * s > limit) {
            want = limit - panel.width * s
        }
        return want
    }

    /*! 按下分页时选的是谁 —— ``clicked`` 落地时 TabBar 早把 ``currentIndex``
        换好了，那时再读 ``Backend.activeTool`` 分不清「切工具」和「再点一次」。 */
    property string toolBeforePress: ""

    function noteToolPress() {
        toolBeforePress = Backend.activeTool
    }

    /*! 收起全部浮出层（笔选单 / 放大镜选单 / 快速切页面板）。 */
    function closeFlyouts() {
        penPalette.opened = false
        zoomPanel.opened = false
        jumpPanel.opened = false
    }

    /*! 分段里点了一页。

        ⚠️ **切工具必须在这里做，不能只靠 ``ToolSegment.onCurrentIndexChanged``**
        （2026-10-06）。那一层只在 ``currentIndex`` **真的变化**时才发；于是
        「点已经选中的那一页」什么都不会发生 —— 用着放大镜时点分段里的「指针」
        就是这种情况（放大镜占着 ``activeTool``，而分段那页仍停在指针），
        结果点了没反应、放大镜面板也不收。 */
    function activateTool(toolId) {
        var was = toolBeforePress
        toolBeforePress = ""
        // 先把工具切过去 —— 这一步不能省：``ToolSegment`` 那一层的
        // ``currentIndex`` 变化只在换页时才发（见上面那段话）。
        if (Backend.activeTool !== toolId) {
            Backend.selectTool(toolId)
        }
        // ⚠️ **关放大镜要在这里显式做，不能只靠 ``onActiveToolChanged``**
        // （2026-10-06）。同一类问题：点分段里**已经选中**的那一页时，
        // ``selectTool`` 根本不会被调（上面那个 ``if`` 不成立），那条信号也就不发 ——
        // 实测「切到别的工具 → 放大镜整个关掉」红在这里，``zoomActive`` 卡在 True。
        // 分段里的工具与放大镜是**互斥工位**，所以不分「有没有真换工具」，一律关。
        if (Backend.zoomActive) {
            Backend.setZoomActive(false)
        }
        // 分段里**带选单的工具**只剩笔（色板）：第一次点它是**切工具**，已经
        // 切过去了再点一下才弹选单（见上面那段 2026-10-01 的说明）。
        // 放大镜也带选单，但它是条上那枚**独立**的圆钮 —— 走 ``activateZoom``，
        // 不进这条「二次点击」的路。
        if (toolId !== "pen" || was !== toolId) {
            // 这一下是「切工具」（或点了别的），浮出层都跟着收起来 ——
            // 用户已经在做别的事了，面板再飘着就是挡路
            closeFlyouts()
            return
        }
        penPalette.opened = !penPalette.opened
    }

    /*! 放大镜入口（条上紧跟着工具分段的那枚独立圆钮）。

        点一下 = **开放大镜 + 直接弹出选单**；再点一下 = 收起选单（放大镜仍开着，
        退出靠再点一下或点别的工具）。

        与笔「二次点击才弹选单」不同：那是分段里的习惯 —— 第一下的语义是
        「切到这一页」。独立的按钮没有「当前分页」那层语义，「打开」就是点它，
        要求点两下才出东西反而像坏了。

        ⚠️ 走的是 :meth:`Backend.setZoomActive`（独立的 ``zoomActive`` 布尔），
        **不是** ``selectTool`` —— 放大镜不是指针类型，不该挤占 ``activeTool``
        （见 ``bridge.py`` 里那个槽的注释：早先挤占的结果是分段把工具切回指针、
        面板刚弹就被收掉）。

        ⚠️ 顺序：先 ``setZoomActive`` 再开面板 —— 它会发 ``zoomActiveChanged``，
        那条处理器里有「关掉放大镜就收起面板」的逻辑（见文件末尾的
        ``Connections``），反过来的话刚开的面板会被自己关掉。 */
    function activateZoom() {
        if (!Backend.zoomActive) {
            closeFlyouts()
            Backend.setZoomActive(true)
            zoomPanel.opened = true
            return
        }
        // ⚠️ 三态（2026-10-06）：开着的时候要分「面板开着」和「面板已收」——
        // 前者再点是**收面板**（放大镜还留着，图照样放大着），后者再点才是
        // **退出放大镜**。写成 `zoomPanel.opened = !zoomPanel.opened` 的话，
        // 第三态永远是「又打开」，圆钮亮着就再也灭不掉了。
        if (zoomPanel.opened) {
            zoomPanel.opened = false
            return
        }
        Backend.setZoomActive(false)
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
        // 快速切页面板是同一回事：它浮在条**上方**（条在屏幕下部），尺寸随页数
        // 变，必须整块包进来 —— 否则格子点不动（穿透到 PowerPoint 就变成在幻灯片
        // 上乱画一笔），而且那块会被 ``SetWindowRgn`` 整个裁掉、连画都画不出来。
        if (jumpPanelOpened && jumpPanel.visible) {
            left = Math.min(left, jumpPanel.x)
            right = Math.max(right, jumpPanel.x + jumpPanel.width * s)
            top = Math.min(top, jumpPanel.y)
            bottom = Math.max(bottom, jumpPanel.y + jumpPanel.height * s)
        }
        // 放大镜选单是同一回事（浮在条**上方**、尺寸固定），只是它不往下长。
        if (zoomPanelOpened && zoomPanel.visible) {
            left = Math.min(left, zoomPanel.x)
            right = Math.max(right, zoomPanel.x + zoomPanel.width * s)
            top = Math.min(top, zoomPanel.y)
        }
        return Qt.rect(left, top, Math.max(right - left, 0), Math.max(bottom - top, 0))
    }

    /*! 命中矩形变了（笔选单开合）。Python 侧连这个信号去重算窗口区域。 */
    signal hitRectChanged()

    onInteractiveRectChanged: hitRectChanged()

    /*! 根 Item 的尺寸 = **缩放后**的屏幕像素（Python 摆位 / 区域塑形 / 编辑器预览
        都读它，见 ``scaleFactor`` 的说明）。
        ⚠️ 竖版宽恒 ``barHeight``、高由内容撑开（``bar.implicitHeight``）——
        ``FlyoutSurface`` 的 ``vertical`` 模式负责算。 */
    implicitWidth: Math.round((isVertical ? barHeight : bar.implicitWidth) * scaleFactor)
    implicitHeight: Math.round((isVertical ? bar.implicitHeight : bar.implicitHeight)
                               * scaleFactor)
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
        // 竖版（两侧合并布局）：内容自上而下一列排（与 SidePager 同一种转置）
        vertical: dock.isVertical
        // ⚠️ 竖版把两档 padding **转置**：``FlyoutSurface`` 的 ``paddingX`` 是横向
        //    （垂直于竖条的轴）、``paddingY`` 是纵向（沿竖条的轴）—— 与横版正好
        //    互换，所以这里按 ``isVertical`` 换一下，别让竖条沿轴留白变成 9。
        paddingX: dock.isVertical ? dock.effPaddingCross : dock.effPaddingAlong
        paddingY: dock.isVertical ? dock.effPaddingAlong : dock.effPaddingCross
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

            // ⚠️ ``currentIndex`` 是**绑定**，所以「工具切到放大镜」这条路径**绕不开**
            //    它 —— 不只是底部那个 ``onActiveToolChanged`` 处理器。
            //
            //    放大镜不在 ``tools`` 里，``toolIndex("zoom")`` 返回 ``-1``。这里的
            //    写法有两个坑，都踩过：
            //
            //    * 直接绑 ``toolIndex(...)``（早先的写法）→ 写入 0 → 下面那个
            //      ``onCurrentIndexChanged`` 把工具真切回「指针」，再由
            //      ``onActiveToolChanged`` 顺手收掉放大镜面板。症状：点一下圆钮，
            //      面板刚弹出来就没了（2026-10-06 排查了半天才定位到这一行）。
            //    * 写成 ``index >= 0 ? index : currentIndex`` —— **也不行**：
            //      绑定里读自己就是 binding loop，Qt 会把这整条绑定作废，
            //      ``currentIndex`` 落回 TabBar 的默认值 0，走回第一条路
            //      （而且**一条警告都不打**，QML 侧看起来一切正常）。
            //
            //    正解是用 ``lastToolIndex`` 把「上一次有效的那一页」显式记下来：
            //    绑定读它（单向，不成环），``onCurrentIndexChanged`` 里写它。
            // ⚠️ 这里就是原来那一行，**一行都没改**（2026-10-06）。放大镜曾经短暂挤进
            //    ``activeTool``，为了不让 ``toolIndex("zoom")`` 回落0把工具切回指针，
            //    试过好几种「保护」写法（自引用绑定 / ``lastToolIndex`` 回退）——
            //    **全都留下了副作用**（自引用那条binding loop 被 Qt 静默作废，
            //    块语法那条直接让分段项点不动）。
            //
            //    正解在数据那边：放大镜**不占** ``activeTool``，改用独立的
            //    ``Backend.zoomActive``（见 ``bridge.py::setZoomActive``）。于是
            //    ``activeTool`` 永远只取 pen / eraser / arrow，``toolIndex``
            //    必然查得到，这一行原样就成立 —— **别再加保护**。
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
                    // 选单正开着时给那一页描一圈（见 ``expanded``）。放大镜也
                    // 带一块选单，但它是条上那枚独立的圆钮，**不在这里**描
                    // （2026-10-06 指令：放大镜不进 Segmented）。
                    expanded: dock.paletteOpened && modelData.id === "pen"
                    // 按下时就记住「选的是谁」（见 ``noteToolPress``），
                    // 抬起后 ``clicked`` 里才判得出是切工具还是再点一次。
                    onPressed: dock.noteToolPress()
                    onClicked: dock.activateTool(modelData.id)
                }
            }
        }

        // ============================================ 1b. 放大镜（独立圆钮）
        // ⚠️ **不进**上面那个分段（2026-10-06 用户指令：「放大镜不应当以
        //    Segmented 内排版」）。它不是 PowerPoint 的指针类型，跟分段里那三页
        //    **不互斥** —— 用着放大镜的时候笔照样是笔。放在紧跟着分段的位置，
        //    读起来仍是「工具这一簇」的一员。
        //
        //    它右侧同样没有分隔线（理由同分段：它也是一枚圆钮，紧跟着再来一条
        //    竖线就成了「双层边」）。
        //
        //    ⚠️ 它的 ``id`` 外层读不到（``FlyoutSurface`` 用 ``default property
        //    alias contentData: inner.data`` 把这里的子项收进了另一个作用域），
        //    所以选单那边按 ``objectName`` 找它 —— 见 ``flyoutX``。
        IconButton {
            objectName: "dockZoomButton"
            visible: dock.present("tools") && dock.zoomEnabled
            iconName: dock.zoomIcon
            tooltip: dock.zoomTooltip
            label: dock.zoomLabel
            showLabel: dock.showLabels
            hitSize: dock.hitSize
            glyphSize: dock.iconSize
            // 选中态 = 放大镜开着（独立的 ``zoomActive``，**不是** ``activeTool``）。
            // ⚠️ 它可能和分段里那一页**同时**亮着，这是有意的（见头注释：分段说
            // 「指针是什么」，这枚说「视图放大着没有」）—— 别去「修」它。
            active: Backend.zoomActive
            onClicked: dock.activateZoom()
        }

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
            vertical: dock.isVertical
        }

        // ==================================================== 3. 翻页组
        // ⚠️ 这一段**不接** ``showLabels``：翻页 pill 保持「小、聚拢」的形态，
        //    见上面 ``showLabels`` 的说明。
        Flow {
            visible: dock.present("pager")
            spacing: dock.pagerSpacing

            IconButton {
                objectName: "dockPagerPrev"
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
                //
                // ⚠️ 圆角用 ``Lumi.dockPagerHitRadius``（短边一半 = 胶囊），**不是**
                //    ``Lumi.dockJumpItemRadius``(8) —— 那是快速切页面板里**卡片**的
                //    圆角，与这里不是同一族（2026-10-06 用户实锤「翻页组件的
                //    hover 不行」）。8 会把 68×44 画成一块大圆角方块：既不跟两侧
                //    44 正圆钮同形，方块本身又比圆更像「容器」，视觉重量凭空高一档。
                //    横竖两版必须同值，见 ``Lumi.qml`` 里那枚令牌的说明。
                Rectangle {
                    objectName: "dockPagerHitSurface"
                    anchors.fill: parent
                    radius: Lumi.dockPagerHitRadius
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
                objectName: "dockPagerNext"
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
            vertical: dock.isVertical
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
        // 这时整块往左收（算式见 ``flyoutX``）。
        x: dock.flyoutX(penPalette)

        onColorPicked: function (value) {
            // ⚠️ 必须转字符串：``color`` 直接喂给 ``@Slot(str)`` 过不了类型转换。
            Backend.setPenColor(value.toString())
        }
    }

    // ================================================ 放大镜选单（浮出层）
    // 条上那枚独立的放大镜圆钮（``dockZoomButton``）点一下就弹（``activateZoom``）
    // —— 它不在分段里，没有「二次点击才弹选单」那层语义。
    // 声明在 ``bar`` **之后** → 绘制、命中都在控制条之上。
    //
    // ⚠️ 与笔选单同一条约定：**不进** dock 的 ``implicitWidth/Height`` ——
    //    dock 一改尺寸 ``_position_dock`` 就要重摆，条会闪一帧；代价是
    //    ``interactiveRect`` 必须自己把它包进来（上面那段就是）。
    //
    // 面板里七枚按钮发的是 ``op`` 字符串，真正的缩放 / 移位由 Python 侧按
    // 软件族去按放映软件自己的键（见 ``ZoomPanel`` 头注释）。
    ZoomPanel {
        id: zoomPanel
        objectName: "zoomPanel"

        // 图标与提示全部来自配置 ``presentation.zoom``（与色板同一条「文案
        // 同源」约定：换配置就全对，不用改 QML）。
        titleZoom: dock.zoomCfg.label_zoom !== undefined
            ? dock.zoomCfg.label_zoom : qsTr("缩放")
        titlePan: dock.zoomCfg.label_pan !== undefined
            ? dock.zoomCfg.label_pan : qsTr("移位")
        iconIn: dock.zoomCfg.icon_in !== undefined
            ? dock.zoomCfg.icon_in : "ic_fluent_zoom_in_20_filled"
        iconOut: dock.zoomCfg.icon_out !== undefined
            ? dock.zoomCfg.icon_out : "ic_fluent_zoom_out_20_filled"
        iconReset: dock.zoomCfg.icon_reset !== undefined
            ? dock.zoomCfg.icon_reset : "ic_fluent_arrow_reset_20_filled"
        iconUp: dock.zoomCfg.icon_up !== undefined
            ? dock.zoomCfg.icon_up : "ic_fluent_arrow_up_20_filled"
        iconDown: dock.zoomCfg.icon_down !== undefined
            ? dock.zoomCfg.icon_down : "ic_fluent_arrow_down_20_filled"
        iconLeft: dock.zoomCfg.icon_left !== undefined
            ? dock.zoomCfg.icon_left : "ic_fluent_arrow_left_20_filled"
        iconRight: dock.zoomCfg.icon_right !== undefined
            ? dock.zoomCfg.icon_right : "ic_fluent_arrow_right_20_filled"
        tooltipIn: dock.zoomCfg.tooltip_in !== undefined
            ? dock.zoomCfg.tooltip_in : qsTr("放大")
        tooltipOut: dock.zoomCfg.tooltip_out !== undefined
            ? dock.zoomCfg.tooltip_out : qsTr("缩小")
        tooltipReset: dock.zoomCfg.tooltip_reset !== undefined
            ? dock.zoomCfg.tooltip_reset : qsTr("恢复原始大小")
        tooltipUp: dock.zoomCfg.tooltip_up !== undefined
            ? dock.zoomCfg.tooltip_up : qsTr("向上移位")
        tooltipDown: dock.zoomCfg.tooltip_down !== undefined
            ? dock.zoomCfg.tooltip_down : qsTr("向下移位")
        tooltipLeft: dock.zoomCfg.tooltip_left !== undefined
            ? dock.zoomCfg.tooltip_left : qsTr("向左移位")
        tooltipRight: dock.zoomCfg.tooltip_right !== undefined
            ? dock.zoomCfg.tooltip_right : qsTr("向右移位")
        glyphSize: dock.iconSize

        // 与底板同倍率缩放 —— 整块面板跟着组件一起放大 / 缩小。
        // ``transformOrigin: TopLeft``：下面算的 x/y 是**根 Item 坐标**（未缩放
        // 的定位），缩放围绕左上角做，落点才不跟着漂。
        scale: dock.scaleFactor
        transformOrigin: Item.TopLeft

        // 贴着工具栏底板上沿往上摆（与笔选单同一条算式，见 ``penPalette``）。
        y: (bar.y + bar.margin - Lumi.dockPaletteGap
            - zoomPanel.shadowMargin - zoomPanel.cardHeight) * dock.scaleFactor
        // ⚠️ 横向对齐**那枚圆钮自己**（2026-10-06 用户指令「要改成对齐圆钮」），
        //    不跟笔选单共用「贴底板左沿」那条 —— 圆钮在条的中间，照旧的话面板
        //    会偏在它左边 100px 出头。传的是**缓存的实例**（``zoomPanelAnchor``），
        //    不能在绑定里现查 —— 理由见那个属性的说明。
        x: dock.flyoutX(zoomPanel, dock.zoomPanelAnchor)

        onZoomRequested: function (op) {
            Backend.zoomSlide(op)
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
    // 放大镜另有一条 ``onZoomActiveChanged`` —— 它不在 ``activeTool`` 那条链上。
    Connections {
        target: Backend

        function onActiveToolChanged() {
            var id = Backend.activeTool
            var index = dock.toolIndex(id)
            // ``>= 0`` 兜底：配置里的 ``tools`` 万一被改坏（空数组 / id 写错），
            // ``-1`` 写进去会让分段自己把工具切回 ``toolIdAt(-1)``（空串，处理器
            // 会忽略），但没必要让选中页变成一个非法值。
            if (index >= 0 && toolSegment.currentIndex !== index) {
                toolSegment.currentIndex = index
            }
            // 选单属于各自的工位：换成指针 / 橡皮就收起来（否则它会跟着
            // 挂在条上方，而那时已经没有「那个工具的选项」可言了）。
            if (id !== "pen") {
                penPalette.opened = false
            }
            // 换工具（指针 / 笔 / 橡皮）就是离开放大镜这个工位 —— 收面板并关掉
            // 放大镜。⚠️ 要**显式关**：放大镜的状态在``zoomActive`` 上，不再随
            // ``activeTool`` 走，只收面板会让那枚圆钮还亮着（看着像还开着）。
            //
            // ⚠️ 这条**不是**唯一路径，``activateTool`` 里也有一份 —— 那边的才
            // 管得住「点分段里已经选中的那一页」（此时 selectTool 不会被调、
            // 这条处理器根本不发，2026-10-06 实测卡在 zoomActive=True）。
            // 这里是给「别的代码直接调 setSetting / selectTool 换工具」兜底。
            if (zoomPanel.opened || Backend.zoomActive) {
                zoomPanel.opened = false
                Backend.setZoomActive(false)
            }
        }

        // 放大镜被关掉（点它自己、或换工具）→ 收起选单。反过来**不开**面板 ——
        // 「开着放大镜但面板收着」是合法状态（用户只调了缩放，面板挡路）。
        function onZoomActiveChanged() {
            if (!Backend.zoomActive) {
                zoomPanel.opened = false
            }
        }

        // 退出放映 → 收起浮出层（笔选单 / 放大镜选单 / 快速切页面板）：下一次
        // 放映进来时不该看到上次遗留的一块卡片。
        function onPresentationActiveChanged() {
            if (!Backend.presentationActive) {
                dock.closeFlyouts()
            }
        }
    }
}
