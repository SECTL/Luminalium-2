import QtQuick
import RinUI as Rin
import Luminalium

/*!
    放大镜的选单 —— 条上那枚独立的放大镜圆钮（``dockZoomButton``，它**不在**
    工具分段里，见 ``PresentationDock`` 头注释）点一下，在工具栏上方浮出的卡片。

    2026-10-06 用户指令：「新增工具『放大镜』，打开之后在工具栏上方弹出放大镜
    选项和上下左右移位的选项，他们在一个面板之内。至于这个放大要调用演示软件
    的缩放功能」。于是这一块是**一张卡片里的两段**，不是两个浮出层::

        缩放                     ← Caption，secondary
        [−] [+] [复位]
        ─────────────────────    ← 1px hairline
        移位                     ← Caption，secondary
            [↑]
        [←] [↓] [→]

    两段内容**等宽**（都是 3 枚圆钮 + 2 个间距），左右沿自然齐平，不用另外
    对齐 —— ``dockZoomButtonSize`` / ``dockZoomButtonSpacing`` 的注释里写了
    这条算式。

    ## 缩放到底调的是谁

    ⚠️ **不是**我们自己在 QML 里放大一张图：``SlideShowView.Zoom`` 是**只读**
    的（Microsoft Learn 明写 Read-only），缩放到多少只能由放映软件自己决定。
    这里每一枚按钮只是发一个 ``op`` 字符串（``in`` / ``out`` / ``reset`` /
    ``up`` / ``down`` / ``left`` / ``right``），由 Python 侧按**软件族**去按
    放映软件自己的缩放键（PowerPoint 小键盘 + / -，WPS 演示 Ctrl+↑ / Ctrl+↓），
    再用 ``view.Zoom`` 读回校验。详见 ``app/ppt_controller.py`` 的
    ``KIND_ZOOM_KEYS`` 与 ``_cmd_zoom``。

    ⚠️ 移位发的是方向键，而**放映态下方向键本来就是翻页键** —— 所以 Python
    侧要先判画面放大着没有（``_zoom_state``）：判出来「还停在适应屏幕」时会
    **先补一档放大再发方向键**，判不出来就按用户意图直接发。面板这边照常出
    按钮，判据在控制层，不在 UI 层。

    （2026-10-06 修「移位按钮无效」：早先那条判据是「确认已放大才发，否则
    return」，而确认又要靠读回值变化 —— 读不到 / 不变就永远确认不了，于是
    点了完全没反应。）

    ## 与「区域塑形」的关系（改这块前必读）

    与笔选单（``PenPaletteCard``）**同一条约定**，这里复述一遍因为后果一样：
    卡片浮在工具栏上方、在 dock Item 的包围盒之外，所以它必须被算进
    ``PresentationDock.interactiveRect``，它一出现区域就要**立刻**重算
    （``hitRectChanged``）。否则那块既画不出来（被 ``SetWindowRgn`` 裁掉）也
    点不动（点击穿透到放映画面）。
*/
Item {
    id: root

    /*! 展开 / 收起（语义上的开关；动画进度见 ``reveal``）。 */
    property bool opened: false
    /*! 进出场动画的开关（默认开）。关掉后 ``reveal`` 直接落到终值 ——
        离屏抓图要的是**稳定终态**而不是动画中间态（与
        ``PageJumpPanel.animate`` 同一条理由：预览在屏幕外建窗口，
        ``Behavior`` 的时间轴在那种环境下推进不可靠）。 */
    property bool animate: true

    /*! 两段的小标题。 */
    property string titleZoom: qsTr("缩放")
    property string titlePan: qsTr("移位")

    /*! 七枚按钮的图标与提示（全部来自配置 ``presentation.zoom``，
        与笔的色板同一条「文案同源」约定）。 */
    property string iconIn: "ic_fluent_zoom_in_20_filled"
    property string iconOut: "ic_fluent_zoom_out_20_filled"
    property string iconReset: "ic_fluent_arrow_reset_20_filled"
    property string iconUp: "ic_fluent_arrow_up_20_filled"
    property string iconDown: "ic_fluent_arrow_down_20_filled"
    property string iconLeft: "ic_fluent_arrow_left_20_filled"
    property string iconRight: "ic_fluent_arrow_right_20_filled"
    property string tooltipIn: qsTr("放大")
    property string tooltipOut: qsTr("缩小")
    property string tooltipReset: qsTr("恢复原始大小")
    property string tooltipUp: qsTr("向上移位")
    property string tooltipDown: qsTr("向下移位")
    property string tooltipLeft: qsTr("向左移位")
    property string tooltipRight: qsTr("向右移位")

    /*! 圆钮直径（比控制条那档 44 收一档 —— 卡片只有 156 宽）。 */
    property int buttonSize: Lumi.dockZoomButtonSize
    /*! 圆钮之间的间距。 */
    property int buttonSpacing: Lumi.dockZoomButtonSpacing
    /*! 图标大小：跟控制条那一档（``buttons.icon_size``），整条工具栏的图标
        重量才一致。 */
    property int glyphSize: Lumi.dockIconSize

    /*! 点了一枚按钮 —— ``op`` 取 ``in`` / ``out`` / ``reset`` /
        ``up`` / ``down`` / ``left`` / ``right``。 */
    signal zoomRequested(string op)

    readonly property int shadowMargin: Lumi.dockPaletteShadowMargin
    readonly property int padding: Lumi.dockPalettePadding
    /*! 小标题与它下面那块内容之间的间距 / 两段之间的间距（与笔选单同档）。 */
    readonly property int titleGap: 8
    readonly property int sectionGap: Lumi.dockPaletteSectionGap

    /*! 两段共用的内容宽度：3 枚圆钮 + 2 个间距。缩放那一行与下面那个十字
        都是这个宽度，于是左右沿天然齐平。 */
    readonly property real rowWidth: buttonSize * 3 + buttonSpacing * 2

    /*! 尺寸含投影余量（与 ``PenPaletteCard`` 同一套约定：摆放方按 ``implicit*``
        摆，卡片本体在 ``shadowMargin`` 处）。 */
    implicitWidth: card.width + shadowMargin * 2
    implicitHeight: card.height + shadowMargin * 2

    /*! 卡片**本体**的尺寸（不含投影余量）—— 调用方按它算「贴着底板上沿往上摆」。 */
    readonly property real cardWidth: card.width
    readonly property real cardHeight: card.height

    // ------------------------------------------------ 动画（Fluent 2 flyout）
    /*! 展开进度 0..1（与笔选单同一个 ``reveal`` 约定：自检等它到位再读几何）。 */
    property real reveal: 0
    onOpenedChanged: reveal = opened ? 1 : 0
    Behavior on reveal {
        // 关掉动画时 ``reveal`` 直接落地（离屏抓图用，见 ``animate``）
        enabled: root.animate
        NumberAnimation {
            duration: opened ? Lumi.dockPaletteEnterDuration
                             : Lumi.dockPaletteFadeDuration
            easing.type: Easing.OutQuint
        }
    }
    opacity: reveal
    visible: reveal > 0.001

    /*! 投影**必须先于**底板声明，否则会盖在底板上面。 */
    Rin.Shadow {
        source: card
        style: "flyout"
        radius: 18
        verticalOffset: 6
    }

    Rectangle {
        id: card
        objectName: "zoomPanelCard"

        x: root.shadowMargin
        // Fluent 2 flyout enter：从「贴近触发点」的位置向外滑入（卡片在条
        // 上方 → 起点比终点低），reveal=1 时归位。
        y: root.shadowMargin + (1 - root.reveal) * Lumi.dockPaletteEnterOffset
        width: content.width + root.padding * 2
        height: content.height + root.padding * 2
        radius: Lumi.dockPaletteRadius
        color: Lumi.dockPaletteBg
        border.width: 1
        border.color: Lumi.dockPaletteBorder

        /*! 描边色经 ``border`` 分组属性拿不到（PySide 侧没有 ``QQuickPen*`` 的
            转换器），复制一份给自检读。 */
        readonly property color surfaceBorderColor: border.color
        readonly property real effectiveRadius: radius
    }

    /*! 吞掉落在卡片范围内的点击 —— 不吞的话会穿到底下的舞台（放映画面）上，
        用户点在自己的选单上却给放映软件发了一个手势。 */
    MouseArea {
        anchors.fill: card
        acceptedButtons: Qt.AllButtons
    }

    Column {
        id: content

        x: card.x + root.padding
        y: card.y + root.padding
        width: root.rowWidth
        spacing: root.sectionGap

        // ========================================================== 缩放
        Column {
            spacing: root.titleGap

            Rin.Text {
                objectName: "zoomPanelTitleZoom"
                text: root.titleZoom
                typography: Rin.Typography.Caption
                color: Lumi.dockPaletteLabel
            }

            Row {
                objectName: "zoomPanelZoomRow"
                spacing: root.buttonSpacing

                IconButton {
                    objectName: "zoomBtn_out"
                    iconName: root.iconOut
                    tooltip: root.tooltipOut
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("out")
                }
                IconButton {
                    objectName: "zoomBtn_in"
                    iconName: root.iconIn
                    tooltip: root.tooltipIn
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("in")
                }
                IconButton {
                    objectName: "zoomBtn_reset"
                    iconName: root.iconReset
                    tooltip: root.tooltipReset
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("reset")
                }
            }
        }

        // ========================================================== 分隔线
        Rectangle {
            objectName: "zoomPanelDivider"
            width: root.rowWidth
            height: 1
            color: Lumi.dockPaletteDivider
        }

        // ========================================================== 移位
        Column {
            spacing: root.titleGap

            Rin.Text {
                objectName: "zoomPanelTitlePan"
                text: root.titlePan
                typography: Rin.Typography.Caption
                color: Lumi.dockPaletteLabel
            }

            /*! 十字方向键：3 列网格，第一行的两端用两个占位 ``Item`` 把「↑」
                顶到正中 —— 方向键必须是这个形状才读得出来是「移位」，排成一
                行就只是四个箭头。

                ⚠️ ``Grid`` 是定位器，子项**不能用 anchors**（见
                ``PresentationDock`` 头注释），居中一律靠占位项撑。 */
            Grid {
                objectName: "zoomPanelPanGrid"
                columns: 3
                rowSpacing: root.buttonSpacing
                columnSpacing: root.buttonSpacing

                Item { width: root.buttonSize; height: root.buttonSize }
                IconButton {
                    objectName: "zoomBtn_up"
                    iconName: root.iconUp
                    tooltip: root.tooltipUp
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("up")
                }
                Item { width: root.buttonSize; height: root.buttonSize }

                IconButton {
                    objectName: "zoomBtn_left"
                    iconName: root.iconLeft
                    tooltip: root.tooltipLeft
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("left")
                }
                IconButton {
                    objectName: "zoomBtn_down"
                    iconName: root.iconDown
                    tooltip: root.tooltipDown
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("down")
                }
                IconButton {
                    objectName: "zoomBtn_right"
                    iconName: root.iconRight
                    tooltip: root.tooltipRight
                    hitSize: root.buttonSize
                    glyphSize: root.glyphSize
                    onClicked: root.zoomRequested("right")
                }
            }
        }
    }
}
