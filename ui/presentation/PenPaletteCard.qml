import QtQuick
import QtQuick.Shapes
import RinUI as Rin
import Luminalium

/*!
    笔的选单 —— 当前工具**已经是笔**时再点一下「笔」，在工具栏上方浮出的卡片。

    2026-10-01 用户指令：「顶层窗口的工具栏的 Segmented 默认工具不应该是鼠标指针
    吗？并且当目前工具已经是笔的时候弹出如图的选单 `@image`，图片的只供参考，
    实际的颜色列表要更多更丰富」。

    ## 版式（Fluent 2 flyout）

    两段内容 + 中间一条 1px 分隔线，各段带 ``Caption`` 小标题（12px / 600，
    Fluent 2 的分段标题档）::

        颜色                     ← Caption，secondary
        ● ● ● ● ● ● ● ● ● ●
        ● ● ● ● ● ● ● ● ● ●
        ● ● ● ● ● ● ● ● ● ●
        ─────────────────────    ← 1px hairline（分区线不比卡片描边扎眼）
        预览                     ← Caption，secondary
        ⌒⌒⌒⌒⌒⌒⌒⌒⌒⌒⌒           ← 次级底板（Subtle fill）上的波浪笔迹

    动效照 Fluent 2 的 flyout enter：**淡入 + 从触发点外侧滑入**
    （卡片在条上方 → 从贴近条的位置向上浮），``OutQuint``（decelerate）；
    收起反向、更快（accelerate 的直觉：退出比进入干脆）。

    ## 与「区域塑形」的关系（改这块前必读）

    顶层窗口被 ``SetWindowRgn`` 裁成「只有控制条几块」，**区域外既不绘制也不
    参与命中**。本卡片浮在工具栏**上方**、也就是 dock Item 的包围盒之外，所以：

    * 它必须被算进 ``PresentationDock.interactiveRect``（否则点色点会穿透到
      PowerPoint，变成在幻灯片上乱画一笔）；
    * 它一出现，区域要**立刻**重算 —— ``PresentationDock`` 会为此发
      ``hitRectChanged``，Python 侧（``windows.py``）接住后重算区域。
      只靠 800ms 一拍的 ``_assert_topmost`` 是不够的：那半秒里卡片既画不出来
      也点不动。

    ⚠️ 卡片**不进** dock 的 ``implicitWidth/Height``：dock 的尺寸一变，
    ``_position_dock`` 就要重摆，条会在「长大 / 归位」之间闪一帧。尺寸不动、
    纯靠绘制溢出，是这个交互最省事的形态。

    ## 选中态的读法

    ``selectedColor`` 是**唯一**的选中依据（由调用方给：后端记着的墨迹色，
    没选过时是配置里的 ``pen.default``）。色点自己不存状态 —— 于是「换一行
    配置就全对」。

    ## 自检相关的镜像属性

    * ``reveal``（0..1 的展开进度）：自检要等它到 1 再读卡片几何，否则会读到
      进出场动画**半路**的 y（这条坑项目在「手动档位」上踩过一次）；
    * 色点上的 ``swatchColor`` / ``swatchSelected``、预览的 ``strokeColor``：
      效果层（border / ShapePath）PySide 读不到，全部另挂一份。
*/
Item {
    id: root

    /*! 色板（十六进制串数组），顺序即从左到右、从上到下。 */
    property var palette: []
    /*! 色板每行几格。 */
    property int columns: 10
    property string titleColor: qsTr("颜色")
    property string titlePreview: qsTr("预览")
    /*! 当前选中的颜色；``transparent`` = 还没有选中任何一格（此时预览画一道
        中性线，也不点亮任何色点）。 */
    property color selectedColor: "transparent"
    /*! 展开 / 收起（语义上的开关；动画进度见 ``reveal``）。 */
    property bool opened: false

    /*! 点了一格色点 —— 交给调用方去落配置并驱动 PowerPoint。 */
    signal colorPicked(color value)

    readonly property int shadowMargin: Lumi.dockPaletteShadowMargin
    readonly property int padding: Lumi.dockPalettePadding
    readonly property int swatchSize: Lumi.dockSwatchSize
    readonly property int swatchSpacing: Lumi.dockSwatchSpacing
    readonly property int previewHeight: Lumi.dockPalettePreviewHeight
    /*! 小标题与它下面那块内容之间的间距。 */
    readonly property int titleGap: 8
    /*! 两段（颜色 / 预览）之间的间距。 */
    readonly property int sectionGap: Lumi.dockPaletteSectionGap

    /*! 预览笔迹的颜色：没选过色时退成一道中性线（否则 ``transparent`` 什么都
        看不见，用户会以为预览坏了）。 */
    readonly property color strokeColor: hasSelection
        ? selectedColor : Lumi.dockPaletteIdleStroke

    /*! 有没有选中任何一格。

        ⚠️ 判据是 **alpha > 0** 而不是 ``selectedColor === "transparent"``：
        QML 里 ``color`` 与字符串做 ``===`` 是**跨类型比较**，恒为 false ——
        于是「还没选过」会被漏判，预览会去画一个完全透明的笔迹（什么都看不见）。
        ``transparent`` 恰好就是 alpha=0，而任何真的选中的颜色 alpha 都是 1。 */
    readonly property bool hasSelection: selectedColor.a > 0

    /*! 色板的列宽 —— 预览那条波浪与它等宽，两段左对齐、右沿也齐。 */
    readonly property real gridWidth: columns * swatchSize
        + Math.max(columns - 1, 0) * swatchSpacing

    /*! 尺寸含投影余量（与 ``FlyoutSurface`` 同一套约定：
        摆放方按 ``implicit*`` 摆，卡片本体在 ``shadowMargin`` 处）。 */
    implicitWidth: card.width + shadowMargin * 2
    implicitHeight: card.height + shadowMargin * 2

    /*! 卡片**本体**的尺寸（不含投影余量）—— 调用方按它算「贴着底板上沿往上摆」
        的落点：``y = 底板上沿 - 间距 - shadowMargin - cardHeight``。 */
    readonly property real cardWidth: card.width
    readonly property real cardHeight: card.height

    // ------------------------------------------------ 动画（Fluent 2 flyout）
    /*! 展开进度 0..1。``opened`` 是语义开关，``reveal`` 是它的动画影子 ——
        自检等 ``reveal`` 到位再读几何，别读半路值。 */
    property real reveal: 0
    onOpenedChanged: reveal = opened ? 1 : 0
    Behavior on reveal {
        NumberAnimation {
            // 展开：淡入快、滑入慢一档（RinUI 自家 Flyout 也是这个分工）；
            // 收起整体更快 —— 退出要比进入干脆，这是 Fluent 2 的直觉。
            duration: opened ? Lumi.dockPaletteEnterDuration
                             : Lumi.dockPaletteFadeDuration
            easing.type: Easing.OutQuint
        }
    }
    opacity: reveal
    /*! 收起动画期间还得画着（不然淡出没了），归零后才真正藏起。 */
    visible: reveal > 0.001

    /*! 某一格是不是当前选中的那格。大小写不敏感（配置里可能写成小写），
        带 alpha 的写法（``#AARRGGBB``）取后六位。 */
    function isSelected(swatch) {
        if (!hasSelection || swatch === undefined) {
            return false
        }
        var want = String(swatch).toUpperCase().replace("#", "")
        var have = selectedColor.toString().toUpperCase().replace("#", "")
        return want.slice(-6) === have.slice(-6)
    }

    /*! 投影**必须先于**底板声明，否则会盖在底板上面。 */
    Rin.Shadow {
        source: card
        style: "flyout"
        radius: 18
        verticalOffset: 6
    }

    Rectangle {
        id: card
        objectName: "penPaletteCard"

        x: root.shadowMargin
        // Fluent 2 flyout enter：从「贴近触发点」的位置向外滑入。卡片在条
        // 上方 → 起点比终点低（往下偏），reveal=1 时归位。
        y: root.shadowMargin + (1 - root.reveal) * Lumi.dockPaletteEnterOffset
        // 宽度**直接由列宽算**（不靠内容撑）：卡片与下面那条预览波浪一定是
        // 同一个右沿。位置器的 ``implicitWidth`` 在这种纯显式尺寸的子项上
        // 不够直观，写死算出来的值反而好读。
        width: content.width + root.padding * 2
        height: content.height + root.padding * 2
        radius: Lumi.dockPaletteRadius
        // 92% 实底（不是控制条那档 65%）：色板要能读出**真实颜色**，
        // 底下透出放映画面会让每个色点都偏色。见 Lumi.dockPaletteBg。
        color: Lumi.dockPaletteBg
        border.width: 1
        border.color: Lumi.dockPaletteBorder

        /*! 描边色经 ``border`` 分组属性拿不到（PySide 侧没有 ``QQuickPen*`` 的
            转换器），复制一份给自检读。 */
        readonly property color surfaceBorderColor: border.color
        readonly property real effectiveRadius: radius
    }

    /*! 与工具栏底板同一道「渐变边框高光」—— 抽出的 ``SurfaceHighlight``，
        两块浮出层共用一个实现才像一家人。 */
    SurfaceHighlight {
        objectName: "penPaletteHighlight"
        source: card
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
        width: root.gridWidth
        spacing: root.sectionGap

        // ========================================================== 颜色
        Column {
            spacing: root.titleGap

            Rin.Text {
                objectName: "penPaletteTitleColor"
                text: root.titleColor
                // Caption = Fluent 2 的分段标题档（12px / 600）
                typography: Rin.Typography.Caption
                color: Lumi.dockPaletteLabel
            }

            Grid {
                id: grid
                objectName: "penPaletteGrid"
                columns: root.columns
                width: root.gridWidth
                rowSpacing: root.swatchSpacing
                columnSpacing: root.swatchSpacing

                Repeater {
                    model: root.palette

                    delegate: Rin.Clip {
                        id: tile
                        objectName: "penSwatchTile"

                        /*! 自检读的两份镜像：``Rin.Clip`` 的底色/描边经
                            ``background`` 拿不到（PySide 侧没有对应转换器）。 */
                        readonly property color swatchColor: modelData
                        readonly property bool swatchSelected: root.isSelected(modelData)

                        width: root.swatchSize
                        height: width
                        radius: width / 2
                        // 圆点自己画（见下面几块内容），按钮底层留空
                        color: "transparent"
                        padding: 0
                        hoverEnabled: true
                        onClicked: root.colorPicked(modelData)

                        // Fluent 2 的可点表面三态：hover 外圈、按下缩一点、
                        // 选中描环。没有 hover 态的色板划过去毫无反馈。
                        scale: tile.down ? 0.88 : 1.0
                        Behavior on scale {
                            NumberAnimation {
                                duration: Lumi.dockPaletteFadeDuration
                                easing.type: Easing.OutQuint
                            }
                        }

                        /*! 选中环：一圈描边贴着色点的**外沿**，色点缩进去
                            让出「环宽 + 空隙」。环色取主题文本色
                            （深色=白 / 浅色=黑），见 ``Lumi.dockSwatchRingColor``。 */
                        Rectangle {
                            objectName: "penSwatchRing"
                            visible: tile.swatchSelected
                            anchors.fill: parent
                            radius: width / 2
                            color: "transparent"
                            border.width: Lumi.dockSwatchRingWidth
                            border.color: Lumi.dockSwatchRingColor
                        }

                        /*! hover 环（1px，比选中环淡一档）。选中的那格不画 ——
                            它已经有更重的环，两圈叠一起反而含糊。 */
                        Rectangle {
                            objectName: "penSwatchHoverRing"
                            visible: tile.hovered && !tile.swatchSelected
                            anchors.fill: parent
                            radius: width / 2
                            color: "transparent"
                            border.width: Lumi.dockSwatchHoverRingWidth
                            border.color: Lumi.dockSwatchHoverRing
                        }

                        /*! 色点本体。选中时缩进去，把外圈让给环。
                            描边是**必须**的：卡片底色在深浅两档都接近中性，
                            纯白/纯黑的色点没有这一圈就与底色糊在一起。 */
                        Rectangle {
                            objectName: "penSwatchDot"
                            anchors.centerIn: parent
                            width: parent.width - (tile.swatchSelected
                                ? (Lumi.dockSwatchRingWidth + Lumi.dockSwatchRingGap) * 2 : 0)
                            height: width
                            radius: width / 2
                            color: tile.swatchColor
                            border.width: 1
                            border.color: Lumi.dockPaletteBorder

                            Behavior on width {
                                NumberAnimation {
                                    duration: Lumi.dockPaletteFadeDuration
                                    easing.type: Easing.OutQuint
                                }
                            }
                        }
                    }
                }
            }
        }

        // ========================================================== 分隔线
        Rectangle {
            objectName: "penPaletteDivider"
            width: root.gridWidth
            height: 1
            color: Lumi.dockPaletteDivider
        }

        // ========================================================== 预览
        Column {
            spacing: root.titleGap

            Rin.Text {
                objectName: "penPaletteTitlePreview"
                text: root.titlePreview
                typography: Rin.Typography.Caption
                color: Lumi.dockPaletteLabel
            }

            /*! 次级底板（Subtle fill）：波浪画在块上，「预览」才像一块独立的
                只读区域，而不是直接飘在卡片底色上。嵌套圆角比外层小一档。 */
            Rectangle {
                objectName: "penPalettePreviewSurface"
                width: root.gridWidth
                height: root.previewHeight
                radius: Lumi.dockPalettePreviewRadius
                color: Lumi.dockPalettePreviewFill

                /*! 一笔波浪 —— 用 ``Shape`` 画（不是贴图）：颜色要跟着选中的
                    那一格实时变，而且曲线在任何 DPR 下都得是干净的。

                    ``CurveRenderer``：默认的几何渲染器会把弧打散成折线（这里没有
                    弧，只有三次贝塞尔，但曲线段在默认渲染器下走的是同一条
                    折线化路径），直接用曲线渲染器最稳。 */
                Shape {
                    id: preview
                    objectName: "penPalettePreview"
                    x: Lumi.dockPalettePreviewPad
                    width: parent.width - Lumi.dockPalettePreviewPad * 2
                    height: parent.height - Lumi.dockPalettePreviewPad * 2
                    anchors.verticalCenter: parent.verticalCenter
                    preferredRendererType: Shape.CurveRenderer

                    /*! 镜像给自检读（``ShapePath`` 是 QObject 不是 Item，
                        Python 侧的 ``childItems()`` 够不着它）。 */
                    readonly property color strokeColor: root.strokeColor
                    readonly property real strokeWidth: Lumi.dockPalettePreviewStroke

                    ShapePath {
                        fillColor: "transparent"
                        strokeColor: preview.strokeColor
                        strokeWidth: preview.strokeWidth
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin

                        // 起笔在左下，先扬起来、再沉下去、最后挑上去 —— 与参考图
                        // 那一笔同形（两个三次贝塞尔接起来，中点在正中收口）。
                        startX: 0
                        startY: preview.height * 0.62

                        PathCubic {
                            control1X: preview.width * 0.18
                            control1Y: preview.height * 0.04
                            control2X: preview.width * 0.32
                            control2Y: preview.height * 0.04
                            x: preview.width * 0.5
                            y: preview.height * 0.5
                        }

                        PathCubic {
                            control1X: preview.width * 0.68
                            control1Y: preview.height * 0.96
                            control2X: preview.width * 0.82
                            control2Y: preview.height * 0.96
                            x: preview.width
                            y: preview.height * 0.38
                        }
                    }
                }
            }
        }
    }
}
