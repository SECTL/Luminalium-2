import QtQuick
import RinUI as Rin
import Luminalium

/*!
    控制条「更多」的收折网格（2026-11-22 用户指令：「『更多』按钮行为改为显示
    『已收折的项目』列表，此列表以网格形式显示被收折的按钮」）。

    这里**不再是** ``QMenu``：控制条窗口带 ``Qt.WindowDoesNotAcceptFocus``，
    QML ``Popup`` 会另开一个抢焦点的真窗口，而原生菜单又完全脱离 QML 的
    主题 / 尺寸 / 缩放体系（历史 QSS 还得手工照抄 ``Lumi`` 的色值）。于是改成本
    窗口里的一张普通浮层卡片 —— 与 ``ZoomPanel`` / ``PenPaletteCard`` 同一套
    摆法与区域塑形约定，主题、缩放、动画自动跟着走。

    ## 谁是「已收折的项目」

    ``actions`` 由 ``PresentationDock`` 过滤 ``presentation.actions`` 得到：
    只有**插件贡献**的动作才会进来（``_collapsed`` 标记，见
    ``bridge.py::_get_presentation_config``）。内建动作（清屏等）永远平铺在
    控制条上，既不会被收折，也不会出现在这个勾选体系里。哪些插件动作收折，
    由主界面编辑器 → 选中工具栏 →「已收折的项目」决定，写进
    ``presentation.overflow.collapsed``。

    ## 与「区域塑形」的关系（改这块前必读）

    与 ``ZoomPanel`` 同一条约定：卡片浮在 dock Item 的包围盒之外，必须被算进
    ``PresentationDock.interactiveRect``，出现 / 收起时区域要立刻重算
    （``hitRectChanged``），否则那块既画不出来（被 ``SetWindowRgn`` 裁掉）
    也点不动（点击穿透到放映画面）。

    外部点击由 Python 侧 ``WindowManager._dismiss_popup_panels`` 按光标位置
    收起（QML 收不到穿透区域的事件），所以这里不需要自己的「点外部关闭」。
*/
Item {
    id: root

    /*! 展开 / 收起（语义上的开关；动画进度见 ``reveal``）。 */
    property bool opened: false

    /*! 进出场动画开关（离屏抓图要稳定终态，关掉后 ``reveal`` 直接落地）。 */
    property bool animate: true

    /*! 收折的动作条目：``{id, label, icon, tooltip}``。
        顺序即控制条 ``presentation.actions`` 里的顺序。 */
    property var actions: []

    /*! 网格列数（来自配置 ``presentation.overflow.columns``）。 */
    property int columns: 4

    /*! 小标题。 */
    property string title: qsTr("已收折的项目")

    /*! 圆钮直径 / 间距 / 图标大小：与 ``ZoomPanel`` 同档。 */
    property int buttonSize: Lumi.dockZoomButtonSize
    property int buttonSpacing: Lumi.dockZoomButtonSpacing
    property int glyphSize: Lumi.dockIconSize

    /*! 点了一枚收折按钮 —— ``actionId`` 直接交给 ``Backend.triggerAction``。 */
    signal actionTriggered(string actionId)

    readonly property int shadowMargin: Lumi.dockPaletteShadowMargin
    readonly property int padding: Lumi.dockPalettePadding
    readonly property int titleGap: 8

    readonly property int actualColumns: Math.max(
        1, Math.min(columns, actions.length))
    readonly property int rows: actions.length === 0
        ? 0 : Math.ceil(actions.length / actualColumns)
    /*! 网格本体宽度：末行不满时也按整列算，卡片不会随行尾忽宽忽窄。 */
    readonly property real gridWidth: actualColumns * buttonSize
        + (actualColumns - 1) * buttonSpacing
    readonly property real gridHeight: rows === 0
        ? 0 : rows * buttonSize + (rows - 1) * buttonSpacing
    /*! 内容宽度取「网格」与「标题」的较大者，单项目时标题不会溢出卡片。 */
    readonly property real contentWidth: Math.max(
        gridWidth, Math.ceil(titleText.implicitWidth))

    implicitWidth: card.width + shadowMargin * 2
    implicitHeight: card.height + shadowMargin * 2
    readonly property real cardWidth: card.width
    readonly property real cardHeight: card.height

    // ------------------------------------------------ 动画（Fluent 2 flyout）
    property real reveal: 0
    onOpenedChanged: reveal = opened ? 1 : 0
    Behavior on reveal {
        enabled: root.animate
        NumberAnimation {
            duration: opened ? Lumi.dockPaletteEnterDuration
                             : Lumi.dockPaletteFadeDuration
            easing.type: Easing.OutQuint
        }
    }
    opacity: reveal
    visible: reveal > 0.001 && actions.length > 0

    /*! 打开状态下条目被移空（插件卸载 / 编辑器改配置）时自动收起，
        避免留下一个空卡片。 */
    onActionsChanged: if (actions.length === 0) opened = false

    /*! 投影必须先于底板声明，否则会盖在底板上面。 */
    Rin.Shadow {
        source: card
        style: "flyout"
        radius: 18
        verticalOffset: 6
    }

    Rectangle {
        id: card
        objectName: "overflowPanelCard"

        x: root.shadowMargin
        // 与 ZoomPanel 同一条入场方向：从贴近触发点的位置向上滑入。
        y: root.shadowMargin + (1 - root.reveal) * Lumi.dockPaletteEnterOffset
        width: content.width + root.padding * 2
        height: content.height + root.padding * 2
        radius: Lumi.dockPaletteRadius
        color: Lumi.dockPaletteBg
        border.width: 1
        border.color: Lumi.dockPaletteBorder

        readonly property color surfaceBorderColor: border.color
        readonly property real effectiveRadius: radius
    }

    /*! 吞掉落在卡片范围内的点击，别穿到底下的放映画面。 */
    MouseArea {
        anchors.fill: card
        acceptedButtons: Qt.AllButtons
    }

    Column {
        id: content

        x: card.x + root.padding
        y: card.y + root.padding
        width: root.contentWidth
        spacing: root.titleGap

        Rin.Text {
            id: titleText
            objectName: "overflowPanelTitle"
            // ⚠️ 必须显式给宽度：``Rin.Text`` 带 ``wrapMode: WordWrap``，
            // 放进 ``Column`` 且不写 width 时实测拿到 0 宽（2026-11-22 预览
            // 抓图确认标题整行不显示），而 ``implicitWidth`` 仍是正常值。
            width: root.contentWidth
            text: root.title
            typography: Rin.Typography.Caption
            color: Lumi.dockPaletteLabel
        }

        /*! ⚠️ ``Grid`` 是定位器，子项不能用 anchors（见 PresentationDock
            头注释）；按钮尺寸全靠 ``IconButton.hitSize`` 撑。 */
        Grid {
            objectName: "overflowPanelGrid"
            columns: root.actualColumns
            rowSpacing: root.buttonSpacing
            columnSpacing: root.buttonSpacing

            Repeater {
                model: root.actions

                delegate: IconButton {
                    required property var modelData
                    objectName: "overflowItem_" + modelData.id
                    iconName: modelData.icon
                        ? String(modelData.icon)
                        : "ic_fluent_apps_20_filled"
                    tooltip: modelData.tooltip
                        ? String(modelData.tooltip)
                        : String(modelData.label !== undefined
                                 ? modelData.label : modelData.id)
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.actionTriggered(String(modelData.id))
                }
            }
        }
    }
}
