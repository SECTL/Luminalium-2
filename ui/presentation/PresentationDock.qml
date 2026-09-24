import QtQuick
import RinUI as Rin
import Luminalium

/*!
    放映悬浮控制条（Design: "Flyout Base"），**恒横向**。

    **整条是「区块（section）」的顺序拼装**，区块顺序固定为::

        tools → actions → pager → exit

    相邻的两个「可见区块」之间插一条竖向分隔线。
    某一区块在这个角落没被启用时，它连同它前后的分隔线一起消失。

    于是参考稿里的两块底板就是同一套规则的两种结果::

        groups = ["tools", "actions", "exit"]  →  [笔|橡皮] │ [清屏] [⋯] │ [⏻]
        groups = ["pager"]                     →  [ ◀  26/41  ▶ ]   （独立小 pill）

    **工具栏与翻页栏是两套独立的条**：``bottom_center`` 是工具栏
    （tools/actions/exit），``bottom_left`` 与 ``bottom_right`` 各是一只翻页
    pill —— 同一套组件渲染三份，只是 ``groups`` 不同。

    **关于「圆」**：参考稿里的白色圆圈是**图标占位**，不是设计元素 ——
    真实界面就是一枚图标（``IconButton`` = ``Rin.Button { flat: true }``），
    不画描边圆环。同理稿里那 4 个圆圈、3 个分段项是为示意排版而画，
    本项目没有那么多功能，**不硬塞占位按钮**。

    尺寸比例全部对照参考稿实测（条高 H=187）：内容高 0.647H、图标 0.331H、
    沿轴内边距 0.267H、横向内边距 0.176H、底板圆角 0.134H。
    详见 ``ui/Luminalium/Lumi.qml`` 里的对照表。

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
    readonly property var segmentCfg: cfg.segment !== undefined ? cfg.segment : ({})
    readonly property var buttonsCfg: cfg.buttons !== undefined ? cfg.buttons : ({})
    readonly property var dividerCfg: cfg.divider !== undefined ? cfg.divider : ({})
    readonly property var overflowCfg: cfg.overflow !== undefined ? cfg.overflow : ({})
    readonly property var pagerCfg: cfg.pager !== undefined ? cfg.pager : ({})
    readonly property var exitCfg: cfg.exit !== undefined ? cfg.exit : ({})
    readonly property var toolsCfg: cfg.tools !== undefined ? cfg.tools : []
    readonly property var actionsCfg: cfg.actions !== undefined ? cfg.actions : []

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

    /*! 内容行高度：底板扣掉上下 padding —— 分段、图标按钮、退出键共用这一档。 */
    readonly property int contentHeight: barHeight - surfacePaddingY * 2

    readonly property int iconSize: buttonsCfg.icon_size !== undefined
        ? buttonsCfg.icon_size : Lumi.dockIconSize
    readonly property int hitSize: buttonsCfg.hit_size !== undefined
        ? buttonsCfg.hit_size : Lumi.dockHitSize
    readonly property int buttonSpacing: buttonsCfg.spacing !== undefined
        ? buttonsCfg.spacing : 10

    // 分段项**缺省是正方形**（= 内容高）：项里只有一枚图标，做宽只会显得空。
    readonly property int segmentItemWidth: segmentCfg.item_width !== undefined
        ? segmentCfg.item_width : contentHeight
    readonly property int indicatorWidth: segmentCfg.indicator_width !== undefined
        ? segmentCfg.indicator_width : iconSize
    readonly property int indicatorHeight: segmentCfg.indicator_height !== undefined
        ? segmentCfg.indicator_height : 3

    readonly property int dividerWidth: dividerCfg.width !== undefined ? dividerCfg.width : 1
    readonly property int dividerHeight: dividerCfg.height !== undefined ? dividerCfg.height : 20
    readonly property int dividerGap: dividerCfg.gap !== undefined ? dividerCfg.gap : 14

    readonly property int pagerWidth: pagerCfg.width !== undefined ? pagerCfg.width : 48
    readonly property int pagerSpacing: pagerCfg.spacing !== undefined ? pagerCfg.spacing : 14
    readonly property int pagerPillPaddingX: pagerCfg.surface_padding_x !== undefined
        ? pagerCfg.surface_padding_x : Lumi.dockPagerPaddingX

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
        ? overflowCfg.icon : "ic_fluent_more_horizontal_20_regular"
    readonly property string overflowTooltip: overflowCfg.tooltip !== undefined
        ? overflowCfg.tooltip : qsTr("更多操作")
    readonly property string pagerIconPrev: pagerCfg.icon_prev !== undefined
        ? pagerCfg.icon_prev : "ic_fluent_chevron_left_20_regular"
    readonly property string pagerIconNext: pagerCfg.icon_next !== undefined
        ? pagerCfg.icon_next : "ic_fluent_chevron_right_20_regular"
    readonly property string exitIcon: exitCfg.icon !== undefined
        ? exitCfg.icon : "ic_fluent_power_20_regular"
    readonly property string exitLabel: exitCfg.label !== undefined
        ? exitCfg.label : qsTr("退出放映")
    readonly property color exitAccent: exitCfg.accent !== undefined
        ? exitCfg.accent : Lumi.accent

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

    /*! 只剩翻页一块时，底板退化成参考稿里那只「留白很足的小 pill」。 */
    readonly property bool pagerOnly: presentCount === 1 && present("pager")

    /*! 沿轴向内边距（横条即左右）。参考稿实测 0.267H（pill 更大）。 */
    readonly property int effPaddingAlong: pagerOnly ? pagerPillPaddingX : surfacePaddingX
    /*! 横向（垂直于轴）内边距：参考稿实测 0.176H，与沿轴**不是同一档**。 */
    readonly property int effPaddingCross: surfacePaddingY

    // ------------------------------------------------------- 工具 ↔ 选中项
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

    // ------------------------------------------------------------- 控制条本体
    // 根节点是 Item（不再是独立窗口）：所有角落的控制条都挂在
    // TopWindow.qml（全屏「顶层窗口」）的容器里，由 Python 定位。
    // 窗口级属性（置顶 / 无边框 / 点击穿透）由顶层窗口统一负责。

    /*! 本条表面（不含投影余量）的交互矩形，坐标相对本 Item。
        顶层窗口用它计算「鼠标何时落在工具栏上」（其余区域点击穿透）。 */
    readonly property rect interactiveRect: Qt.rect(
        bar.margin, bar.margin,
        Math.max(width - bar.margin * 2, 0),
        Math.max(height - bar.margin * 2, 0)
    )

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
        shadowEnabled: dock.shadowEnabled
        shadowMargin: dock.shadowMargin
        shadowBlur: dock.shadowBlur
        shadowOffsetY: dock.shadowOffsetY

        // ==================================================== 1. 工具分段
        ToolSegment {
            id: toolSegment
            visible: dock.present("tools")
            itemHeight: dock.contentHeight
            // 绑定：给出初值，并在后端切换工具（快捷键等）时自动跟随。
            // 用户点击会写 currentIndex 从而打断绑定，之后由下面的
            // Connections 继续同步。
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
                    itemWidth: dock.segmentItemWidth
                    itemHeight: dock.contentHeight
                    indicatorWidth: dock.indicatorWidth
                    indicatorHeight: dock.indicatorHeight
                    glyphSize: dock.iconSize
                    tooltip: modelData.label !== undefined ? modelData.label : ""
                    icon.name: modelData.icon !== undefined ? modelData.icon : ""
                }
            }
        }

        // ==================================== 分隔线（分段 → 动作）
        SectionDivider {
            visible: dock.dividerBefore("actions")
            dividerWidth: dock.dividerWidth
            dividerHeight: dock.dividerHeight
            dividerGap: dock.dividerGap
            rowHeight: dock.contentHeight
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
                    hitSize: dock.hitSize
                    glyphSize: dock.iconSize
                    onClicked: Backend.triggerAction(modelData.id)
                }
            }

            IconButton {
                visible: dock.overflowEnabled
                iconName: dock.overflowIcon
                tooltip: dock.overflowTooltip
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

            Item {
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
            iconName: dock.exitIcon
            tooltip: dock.exitLabel
            accent: dock.exitAccent
            buttonHeight: dock.contentHeight
            widthRatio: Lumi.dockExitWidthRatio
            glyphSize: dock.iconSize
            onClicked: Backend.exitPresentation()
        }
    }

    // 绑定被打断后，继续同步后端发起的工具切换
    Connections {
        target: Backend

        function onActiveToolChanged() {
            var index = dock.toolIndex(Backend.activeTool)
            if (toolSegment.currentIndex !== index) {
                toolSegment.currentIndex = index
            }
        }
    }
}
