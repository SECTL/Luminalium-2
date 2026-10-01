import QtQuick
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

    // ------------------------------------------------------------ 配置读取
    readonly property var cfg: Backend.presentationConfig
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
    /*! 钳制后的**实际**圆角（胶囊时为 高/2）。自检读这个值。 */
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
    readonly property int shadowMargin: shadowCfg.margin !== undefined
        ? shadowCfg.margin : Lumi.dockShadowMargin
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

    /*! 按下分页时选的是谁 —— ``clicked`` 落地时 TabBar 早把 ``currentIndex``
        换好了，那时再读 ``Backend.activeTool`` 分不清「切工具」和「再点一次」。 */
    property string toolBeforePress: ""

    function noteToolPress() {
        toolBeforePress = Backend.activeTool
    }

    function activateTool(toolId) {
        var was = toolBeforePress
        toolBeforePress = ""
        if (toolId !== "pen" || was !== "pen") {
            // 这一下是「切工具」（或点了别的），选单跟着收起来
            penPalette.opened = false
            return
        }
        penPalette.opened = !penPalette.opened
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
        // 控制条底板表面：围在投影余量内侧
        var left = bar.x + bar.margin
        var right = bar.x + bar.implicitWidth - bar.margin
        var top = bar.y + bar.margin
        var bottom = bar.y + bar.implicitHeight - bar.margin
        if (paletteOpened && penPalette.visible) {
            left = Math.min(left, penPalette.x)
            right = Math.max(right, penPalette.x + penPalette.width)
            top = Math.min(top, penPalette.y)
        }
        return Qt.rect(left, top, Math.max(right - left, 0), Math.max(bottom - top, 0))
    }

    /*! 命中矩形变了（笔选单开合）。Python 侧连这个信号去重算窗口区域。 */
    signal hitRectChanged()

    onInteractiveRectChanged: hitRectChanged()

    implicitWidth: bar.implicitWidth
    implicitHeight: bar.implicitHeight
    width: implicitWidth
    height: implicitHeight

    FlyoutSurface {
        id: bar
        anchors.fill: parent
        paddingX: dock.effPaddingAlong
        paddingY: dock.effPaddingCross
        surfaceRadius: dock.surfaceRadius
        surfaceOpacity: dock.surfaceOpacity
        highlightEnabled: dock.highlightEnabled
        shadowEnabled: dock.shadowEnabled
        shadowMargin: dock.shadowMargin
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
                    // 选单正开着时给「笔」描一圈（见 ``expanded``）
                    expanded: dock.paletteOpened && modelData.id === "pen"
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

            // 页码变化走透明度脉冲（与竖版同一套节奏，见 PagePulse.qml）
            PagePulse {
                page: Backend.slideIndex
                width: dock.pagerWidth
                height: dock.contentHeight

                Rin.Text {
                    anchors.centerIn: parent
                    typography: Rin.Typography.BodyLarge
                    text: Backend.slideTotal > 0
                        ? Backend.slideIndex + "/" + Backend.slideTotal
                        : "-/-"
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

        // 贴着工具栏底板上沿往上摆：卡片**本体**（不含投影余量）的底边距底板上
        // 沿 ``Lumi.dockPaletteGap``。卡片自己的坐标含 shadowMargin，所以两边都
        // 要各扣/加一次。
        y: bar.y + bar.margin - Lumi.dockPaletteGap
           - penPalette.shadowMargin - penPalette.cardHeight
        // 左沿与底板的左沿对齐；卡片比条还宽，贴右下的角落会溢出屏幕 ——
        // 这时整块往左收（可用宽度从父级拿：父级是铺满整屏的容器）。
        x: {
            var want = bar.margin - penPalette.shadowMargin
            var limit = dock.parent ? dock.parent.width - dock.x : 0
            if (limit > 0 && want + penPalette.width > limit) {
                want = limit - penPalette.width
            }
            return want
        }

        onColorPicked: function (value) {
            // ⚠️ 必须转字符串：``color`` 直接喂给 ``@Slot(str)`` 过不了类型转换。
            Backend.setPenColor(value.toString())
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
            // 挂在条上方，而那时已经没有「笔的选项」可言了）。
            if (Backend.activeTool !== "pen") {
                penPalette.opened = false
            }
        }

        // 退出放映 → 收起选单：下一次放映进来时不该看到上次遗留的一块卡片。
        function onPresentationActiveChanged() {
            if (!Backend.presentationActive) {
                penPalette.opened = false
            }
        }
    }
}
