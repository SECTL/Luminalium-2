import QtQuick
import RinUI as Rin
import Luminalium

/*!
    橡皮子模式的选单 —— 当前工具**已经是橡皮**时再点一下「橡皮」，在工具栏
    上方浮出的卡片（与 ``PenPaletteCard`` 同一个交互习惯：二次点击 = 打开这个
    工具的选项）。

    2026-10-07 用户指令：自建批注 —— 自建墨迹的橡皮有两个子模式
    （``presentation.ink.eraser_mode``）：

    * ``stroke`` = **整笔擦除**：碰到哪一笔就整笔删掉（适合改错字）；
    * ``pixel`` = **像素擦除**（默认）：只擦掉划过的那一截，与 PowerPoint 自带
      橡皮的手感最接近。

    只在 engine=self 下有意义（com 模式交给演示软件自己的橡皮），但卡片不因此
    藏起来 —— 「藏入口」比「点了没反应」更让人困惑，而模式值是持久配置，
    下次切回 self 引擎仍然作数。

    ## 版式（与 PenPaletteCard 同一套 Fluent 2 flyout 语言）

    Caption 小标题 + 两行整宽的选项行（主标签 + 说明 caption 上下排），
    选中行右沿一枚勾（``ic_fluent_checkmark_20_filled``），hover 行铺
    ``dockButtonHoverFill``。卡片本体 92% 实底、1px 描边、投影余量、
    ``reveal`` 进出场 —— 全部与 ``PenPaletteCard`` 同令牌、同节奏，
    理由见那边头注释（色板要读真实色、动画 Fluent 2 flyout enter）。

    2026-10-08 用户指令：自建批注 —— **像素擦除**模式下，选项行下面再出一段
    「粗细」档位行（1px 分隔线 + Caption + 一排圆形热区，视觉逐字照搬
    ``PenPaletteCard`` 的粗细段；档位 = ``presentation.ink.eraser_widths``）。
    像素擦除原先跟着笔宽走，擦一块大字标题要来回划好几趟。**整笔擦除模式下
    整段收起**（碰到哪笔删哪笔，粗细无从谈起）；卡片高度随显隐变化，
    ``implicitHeight`` / 摆位 / ``hitRectChanged`` 全是绑定驱动、自动跟上
    （与笔选单同一个机制，不用为本段另接一根线）。档位圆点用中性文本色
    （``Lumi.textPrimary``）—— 擦除没有颜色可言，不像笔点能跟着选色走。
    com 引擎下这一行照样显示、点了不生效（应用层忽略 ``eraser_width:``，
    与笔选单粗细行同一个决策：藏入口比点了没反应更让人困惑）。

    ## 与「区域塑形」的关系（改这块前必读）

    与笔选单同一条命：卡片浮在 dock Item 包围盒**之外**，顶层窗口被
    ``SetWindowRgn`` 裁过，区域外既不绘制也不参与命中 —— 所以本卡片必须被算进
    ``PresentationDock.interactiveRect``，出现时要靠 ``hitRectChanged`` 让
    Python 侧**立刻**重算区域；同样**不进** dock 的 ``implicitWidth/Height``
    （尺寸不动、纯靠绘制溢出，否则 ``_position_dock`` 会在「长大 / 归位」之间
    闪一帧）。详细论证见 ``PenPaletteCard.qml`` 头注释，这里不抄第二遍。

    ## 收起路径（2026-10-08 用户报告：自建批注）

    与笔选单逐字同 model：再点一次「橡皮」切换、换工具 / 退出放映自动收、
    点模式行 / 粗细档不收；卡开着时点画布空白，self 引擎下第一按被 InkLayer
    起笔钩子消费成收卡（之后的按下正常擦除），com 引擎 / 穿透态退化为
    「光标离开控制条即收」—— 都经 ``PresentationDock.closeToolCards()``。
    论证见 ``PenPaletteCard.qml`` 头注释「收起路径」一节，这里不抄第二遍。

    ## 选中态的读法

    ``selectedMode`` / ``selectedWidth`` 是各自唯一的选中依据（都由调用方给：
    子模式读配置 ``Backend.settings.presentation_ink_eraser_mode`` —— 持久偏好；
    粗细读后端会话态 ``Backend.eraserWidth`` —— 与笔宽同一个决策，不落配置，
    理由见 ``bridge.py`` SETTING_PATHS 旁的 ⚠️ 注释）。卡片自己不存状态。
    点模式行发 ``modePicked``、点粗细档发 ``widthPicked``，落盘 / 落层都是
    调用方的事。

    ## 自检相关的镜像属性

    * ``reveal``（0..1 的展开进度）：自检等它到 1 再读卡片几何（同笔选单的坑）；
    * 选项行上的 ``modeValue`` / ``modeSelected``、粗细档上的 ``widthValue`` /
      ``widthSelected``：选中勾 / 选中环的可见性 PySide 读不到（效果层），另挂一份。
*/
Item {
    id: root

    /*! 当前选中的子模式（``stroke`` / ``pixel``）。空串 = 没有任何一行点亮
        （配置被手改成陌生值时的兜底显示态）。 */
    property string selectedMode: "pixel"
    property string title: qsTr("橡皮")
    /*! 展开 / 收起（语义上的开关；动画进度见 ``reveal``）。 */
    property bool opened: false

    /*! 点了一行 —— 交给调用方去落 ``presentation.ink.eraser_mode``。 */
    signal modePicked(string mode)

    /*! 像素橡皮的粗细档（逻辑 px 数组，``presentation.ink.eraser_widths``）。
        空数组 = 不出「粗细」那一段（连同它上面的分隔线）—— 与笔选单同一条
        规矩（翻页 pill 也挂着宿主组件，那里不给档位）。2026-10-08 用户指令：
        自建批注。 */
    property var widths: []
    property string titleWidth: qsTr("粗细")
    /*! 当前选中的粗细（px）；0 = 没有任何一档点亮。与 ``selectedMode`` 同一个
        读法：卡片自己不存状态，由调用方给（后端会话值，没选过时是配置的
        ``eraser_default_width``）。 */
    property real selectedWidth: 0
    /*! 点了一档粗细 —— 交给调用方经 Backend 发 ``eraser_width:<px>``。 */
    signal widthPicked(real value)
    readonly property bool hasWidths: widths !== undefined && widths.length > 0
    readonly property bool hasWidthSelection: selectedWidth > 0
    /*! 「粗细」段只服务于像素擦除：整笔擦除碰到哪笔删哪笔，粗细无从谈起。 */
    readonly property bool widthRowVisible: selectedMode === "pixel" && hasWidths

    readonly property int shadowMargin: Lumi.dockPaletteShadowMargin
    readonly property int padding: Lumi.dockPalettePadding

    /*! 内容列宽（设计值）：够放下「主标签 + 说明」两行字，又不至于宽得像块
        横幅 —— 这是只有两行的小卡片，不是设置页。 */
    readonly property int contentWidth: 208
    /*! 选项行高：主标签（Body）+ 说明（Caption）+ 上下各 7px 呼吸位。 */
    readonly property int optionHeight: 48
    readonly property int optionSpacing: 4
    /*! 小标题与选项之间的间距（与 PenPaletteCard 的 ``titleGap`` 同档）。 */
    readonly property int titleGap: 8

    /*! 尺寸含投影余量（与 ``FlyoutSurface`` / ``PenPaletteCard`` 同一套约定：
        摆放方按 ``implicit*`` 摆，卡片本体在 ``shadowMargin`` 处）。 */
    implicitWidth: card.width + shadowMargin * 2
    implicitHeight: card.height + shadowMargin * 2

    /*! 卡片**本体**的尺寸（不含投影余量）—— 调用方按它算「贴着底板上沿往上摆」
        的落点（与笔选单同一个公式）。 */
    readonly property real cardWidth: card.width
    readonly property real cardHeight: card.height

    // ------------------------------------------------ 动画（Fluent 2 flyout）
    /*! 展开进度 0..1。``opened`` 是语义开关，``reveal`` 是它的动画影子 ——
        自检等 ``reveal`` 到位再读几何，别读半路值。 */
    property real reveal: 0
    onOpenedChanged: reveal = opened ? 1 : 0
    Behavior on reveal {
        NumberAnimation {
            // 与笔选单同一个节奏：展开淡入快、滑入慢一档，收起整体更快 ——
            // 退出要比进入干脆，这是 Fluent 2 的直觉。
            duration: opened ? Lumi.dockPaletteEnterDuration
                             : Lumi.dockPaletteFadeDuration
            easing.type: Easing.OutQuint
        }
    }
    opacity: reveal
    /*! 收起动画期间还得画着（不然淡出没了），归零后才真正藏起。 */
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
        objectName: "eraserModeCard"

        x: root.shadowMargin
        // Fluent 2 flyout enter：从「贴近触发点」的位置向外滑入（同笔选单）。
        y: root.shadowMargin + (1 - root.reveal) * Lumi.dockPaletteEnterOffset
        width: content.width + root.padding * 2
        height: content.height + root.padding * 2
        radius: Lumi.dockPaletteRadius
        // 92% 实底：底下透出放映画面会让说明文字读不清（同笔选单的理由）。
        color: Lumi.dockPaletteBg
        border.width: 1
        border.color: Lumi.dockPaletteBorder
    }

    /*! 吞掉落在卡片范围内的点击 —— 不吞的话会穿到底下的舞台（放映画面）上，
        用户点在自己的选单上却给幻灯片画了一笔。 */
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
            objectName: "eraserModeTitle"
            text: root.title
            // Caption = Fluent 2 的分段标题档（12px / 600）
            typography: Rin.Typography.Caption
            color: Lumi.dockPaletteLabel
        }

        Repeater {
            // 词表与配置（``presentation.ink.eraser_mode``）严格一致：
            // ``application._on_config_changed`` 只认 stroke / pixel。
            model: [
                {
                    "mode": "stroke",
                    "label": qsTr("整笔擦除"),
                    "hint": qsTr("碰到哪一笔就整笔删掉"),
                    "icon": "ic_fluent_ink_stroke_20_regular"
                },
                {
                    "mode": "pixel",
                    "label": qsTr("像素擦除"),
                    "hint": qsTr("只擦掉划过的那一截"),
                    "icon": "ic_fluent_eraser_segment_20_regular"
                }
            ]

            delegate: Rin.Clip {
                id: option
                objectName: "eraserModeOption"

                /*! 自检镜像：``modeValue`` = 这一行代表的子模式，
                    ``modeSelected`` = 它是不是当前选中的那行（选中勾的可见性
                    是效果层，PySide 读不到）。 */
                readonly property string modeValue: modelData.mode
                readonly property bool modeSelected: root.selectedMode === modelData.mode

                width: root.contentWidth
                height: root.optionHeight
                radius: Lumi.dockPalettePreviewRadius
                // hover 底 = 「这里能点」的唯一提示（Fluent 2 菜单行同款）；
                // 选中行不另铺底色 —— 选中由右沿的勾表达，叠底色会读成 hover。
                color: option.hovered ? Lumi.dockButtonHoverFill : "transparent"
                padding: 0
                hoverEnabled: true
                onClicked: root.modePicked(option.modeValue)

                Behavior on color {
                    ColorAnimation {
                        duration: Lumi.dockPaletteFadeDuration
                        easing.type: Easing.OutQuint
                    }
                }

                Rin.Icon {
                    id: optionIcon
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    name: modelData.icon
                    size: 20
                    color: Lumi.textPrimary
                }

                Column {
                    anchors.left: optionIcon.right
                    anchors.leftMargin: 10
                    anchors.right: optionCheck.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1

                    Rin.Text {
                        objectName: "eraserModeOptionLabel"
                        text: modelData.label
                        typography: Rin.Typography.Body
                        color: Lumi.textPrimary
                    }

                    Rin.Text {
                        objectName: "eraserModeOptionHint"
                        width: parent.width
                        text: modelData.hint
                        typography: Rin.Typography.Caption
                        color: Lumi.dockPaletteLabel
                        elide: Text.ElideRight
                    }
                }

                /*! 选中勾：Fluent 菜单的选中标记（行内右沿一枚勾）。
                    颜色用主题文本色而不是 accent —— 与笔选单的选中环同一个
                    读法（``Lumi.dockSwatchRingColor`` 也是 textPrimary）：
                    控制条上 accent 只留给「这会真去干一件事」的件。 */
                Rin.Icon {
                    id: optionCheck
                    objectName: "eraserModeOptionCheck"
                    visible: option.modeSelected
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    name: "ic_fluent_checkmark_20_filled"
                    size: 16
                    color: Lumi.textPrimary
                }
            }
        }

        // ========================================================== 粗细
        // 2026-10-08 用户指令：自建批注 —— 像素橡皮的粗细档，视觉与交互逐字照搬
        // PenPaletteCard 的粗细段（1px 分隔线 + Caption + 圆形热区排，选中环 /
        // hover 环 / 按下缩放同令牌）。整段只在像素模式下出（``widthRowVisible``）：
        // 整笔擦除碰到哪笔删哪笔，粗细无从谈起。显隐变了卡片高度跟着变，
        // 摆位与 hitRect 全是绑定驱动，不用另接线（见头注释）。
        Rectangle {
            objectName: "eraserWidthDivider"
            visible: root.widthRowVisible
            width: root.contentWidth
            height: 1
            color: Lumi.dockPaletteDivider
        }

        Column {
            visible: root.widthRowVisible
            spacing: root.titleGap

            Rin.Text {
                objectName: "eraserWidthTitle"
                text: root.titleWidth
                typography: Rin.Typography.Caption
                color: Lumi.dockPaletteLabel
            }

            Row {
                id: widthRow
                objectName: "eraserWidthRow"
                spacing: Lumi.dockSwatchSpacing

                Repeater {
                    model: root.widthRowVisible ? root.widths : []

                    delegate: Rin.Clip {
                        id: widthTile
                        objectName: "eraserWidthTile"

                        /*! 自检镜像（同选项行：环的可见性是效果层，PySide 读不到）。 */
                        readonly property real widthValue: Number(modelData)
                        readonly property bool widthSelected: root.hasWidthSelection
                            && Math.abs(widthValue - root.selectedWidth) < 0.01

                        width: Lumi.dockSwatchSize
                        height: width
                        radius: width / 2
                        color: "transparent"
                        padding: 0
                        hoverEnabled: true
                        onClicked: root.widthPicked(widthValue)

                        scale: widthTile.down ? 0.88 : 1.0
                        Behavior on scale {
                            NumberAnimation {
                                duration: Lumi.dockPaletteFadeDuration
                                easing.type: Easing.OutQuint
                            }
                        }

                        Rectangle {
                            objectName: "eraserWidthRing"
                            visible: widthTile.widthSelected
                            anchors.fill: parent
                            radius: width / 2
                            color: "transparent"
                            border.width: Lumi.dockSwatchRingWidth
                            border.color: Lumi.dockSwatchRingColor
                        }

                        Rectangle {
                            objectName: "eraserWidthHoverRing"
                            visible: widthTile.hovered && !widthTile.widthSelected
                            anchors.fill: parent
                            radius: width / 2
                            color: "transparent"
                            border.width: Lumi.dockSwatchHoverRingWidth
                            border.color: Lumi.dockSwatchHoverRing
                        }

                        /*! 档位圆点：直径 = 档位 + 4、封顶到热区减掉选中环占位
                            （与笔选单同一公式）。颜色用中性文本色 —— 擦除没有
                            颜色可言，不能像笔点那样跟着选色走。描边理由同笔点
                            （浅色档的浅灰点没有这一圈就与底色糊在一起）。 */
                        Rectangle {
                            objectName: "eraserWidthDot"
                            anchors.centerIn: parent
                            width: Math.min(widthTile.widthValue + 4,
                                            parent.width - (Lumi.dockSwatchRingWidth
                                                            + Lumi.dockSwatchRingGap) * 2 - 2)
                            height: width
                            radius: width / 2
                            color: Lumi.textPrimary
                            border.width: 1
                            border.color: Lumi.dockPaletteBorder
                        }
                    }
                }
            }
        }
    }
}
