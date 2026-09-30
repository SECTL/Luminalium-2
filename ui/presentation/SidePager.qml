import QtQuick
import RinUI as Rin
import Luminalium

/*!
    竖版两侧翻页 pill —— **横版翻页 pill（``PresentationDock`` 的 ``pager``
    区块）旋转 90° 的同款布局**，贴屏幕左右边缘、垂直居中。

    尺寸与排布**直接由横版转置**而来，不是另一套比例（2026-09-30 用户指令：
    「竖版的按照横版翻转的布局来，不要全抄 L1」—— L1 竖版那套 margin 8 /
    大小字页码弃用）::

        横版 180×62：4 + 圆钮44 + 8 + 页码68 + 8 + 圆钮44 + 4
        竖版  62×180：同一行账，方向朝下 —— 圆钮 / 图标 / 间距 / 页码区 /
                      沿轴留白全部与横版同档，配置直接共用
                      （``pager.width`` / ``pager.spacing`` /
                        ``pager.surface_padding_x``）

    即::

        ║                       ║
        ║  ┌─────┐              ║
        ║  │  ▲  │              ║
        ║  │26/41│              ║
        ║  │     │              ║
        ║  │  ▼  │              ║
        ║  └─────┘              ║
        ║                       ║

    设计语言与横版共用：

    * 全圆胶囊底板（``FlyoutSurface`` 的 ``vertical`` 模式：内容自上而下，
      圆角按短边钳制）+ CW2 同款渐变边框高光 + flyout 投影 —— 全部照旧；
    * 圆形翻页钮就是 ``IconButton`` 本尊（与横版同一枚）；
    * 页码**三行堆叠**：当前页 / 斜杠 / 总页数，斜杠用小一号的字
      （Caption）—— 2026-09-30 用户指令；横版仍是单行 ``26/41``；
      翻页时页码做透明度脉冲（``PagePulse``），横竖版同一套节奏；
    * chevron 图标直接用 Fluent 的上 / 下箭头（横版是左右箭头，转向即旋转）。

    点击行为与横版一致，走 ``Backend.previousSlide()`` / ``nextSlide()``
    （含限流与轻量页码刷新）。

    ``corner`` 由 Python 注入（middle_left / middle_right）；显隐由
    ``presentation.corners.<corner>.enabled`` 与 ``pager.enabled`` 决定。
    本组件**只有翻页一组**—— 竖条里塞工具 / 动作组是另一个命题（L1 也没做）。
*/
Item {
    id: pager

    property string corner: "middle_left"

    // ------------------------------------------------------------ 配置读取
    readonly property var cfg: Backend.presentationConfig
    readonly property var surfaceCfg: cfg.surface !== undefined ? cfg.surface : ({})
    readonly property var shadowCfg: surfaceCfg.shadow !== undefined ? surfaceCfg.shadow : ({})
    readonly property var buttonsCfg: cfg.buttons !== undefined ? cfg.buttons : ({})
    readonly property var pagerCfg: cfg.pager !== undefined ? cfg.pager : ({})
    readonly property var sideCfg: pagerCfg.side !== undefined ? pagerCfg.side : ({})

    /*! ``pager.enabled`` 与横版同一开关（设置页「页码切换」）。 */
    readonly property bool pagerEnabled: pagerCfg.enabled !== false

    // ---- 尺寸（横版 pill 的转置；默认值 = Lumi 里同档令牌）----
    readonly property int pillWidth: sideCfg.width !== undefined
        ? sideCfg.width : Lumi.dockSidePagerWidth
    readonly property int pillHeight: sideCfg.height !== undefined
        ? sideCfg.height : Lumi.dockSidePagerHeight
    /*! 沿轴留白（竖条即上下）= 横版翻页 pill 的 surface_padding_x（4）。 */
    readonly property int pillPadding: sideCfg.padding !== undefined
        ? sideCfg.padding : Lumi.dockSidePagerPadding
    /*! 横向（垂直于轴）留白 = 工具条档的 9（横版 pill 的上下也是这一档）。 */
    readonly property int crossPadding: surfaceCfg.padding_y !== undefined
        ? surfaceCfg.padding_y : Lumi.dockPaddingY
    /*! 圆钮直径与横版同档（buttons.hit_size）。 */
    readonly property int contentHeight: buttonsCfg.hit_size !== undefined
        ? buttonsCfg.hit_size : Lumi.dockHitSize
    /*! 圆钮与页码区之间的间距 = 横版的 pager.spacing（8）。 */
    readonly property int pagerSpacing: pagerCfg.spacing !== undefined
        ? pagerCfg.spacing : Lumi.dockPagerSpacing
    /*! 页码区高度 = 横版页码文本区的宽度 pager.width（68）—— 转置关系。 */
    readonly property int infoHeight: pagerCfg.width !== undefined
        ? pagerCfg.width : Lumi.dockPagerWidth

    readonly property int iconSize: buttonsCfg.icon_size !== undefined
        ? buttonsCfg.icon_size : Lumi.dockIconSize
    readonly property int hitSize: contentHeight

    // ---- 图标（chevron 朝上 / 朝下 = 横版左右箭头旋转 90° 的对应物）----
    readonly property string iconPrev: sideCfg.icon_prev !== undefined
        ? sideCfg.icon_prev : "ic_fluent_chevron_up_20_filled"
    readonly property string iconNext: sideCfg.icon_next !== undefined
        ? sideCfg.icon_next : "ic_fluent_chevron_down_20_filled"

    // ---- 底板 / 投影 / 高光（与横版同一套开关）----
    readonly property real surfaceRadius: surfaceCfg.radius !== undefined
        ? surfaceCfg.radius : Lumi.dockSurfaceRadius
    readonly property real surfaceOpacity: surfaceCfg.opacity !== undefined
        ? surfaceCfg.opacity : Lumi.dockSurfaceOpacity
    readonly property bool highlightEnabled: surfaceCfg.highlight !== undefined
        ? surfaceCfg.highlight === true : true
    readonly property bool shadowEnabled: shadowCfg.enabled !== undefined
        ? shadowCfg.enabled : true
    readonly property int shadowMarginCfg: shadowCfg.margin !== undefined
        ? shadowCfg.margin : Lumi.dockShadowMargin
    readonly property real shadowBlur: shadowCfg.blur !== undefined ? shadowCfg.blur : 18
    readonly property real shadowOffsetY: shadowCfg.offset_y !== undefined
        ? shadowCfg.offset_y : 6
    /*! 投影余量（Python 摆放时扣掉；竖条垂直居中时它上下对称，无需特殊处理）。 */
    readonly property int shadowMargin: bar.margin
    /*! 高光环是否真的在画（自检用；经 FlyoutSurface 透出，与横版同名同义）。 */
    readonly property bool highlightRingVisible: bar.highlightRingVisible

    /*! 本条表面（不含投影余量）的交互矩形，坐标相对本 Item。 */
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
        vertical: true
        // 横版的两个留白档原样转置：沿轴 4（横版的左右）、横向 9（横版的上下）
        paddingX: pager.crossPadding
        paddingY: pager.pillPadding
        contentSpacing: pager.pagerSpacing
        surfaceRadius: pager.surfaceRadius
        surfaceOpacity: pager.surfaceOpacity
        highlightEnabled: pager.highlightEnabled
        shadowEnabled: pager.shadowEnabled
        shadowMargin: pager.shadowMarginCfg
        shadowBlur: pager.shadowBlur
        shadowOffsetY: pager.shadowOffsetY

        // ================================================ 上一页（chevron 朝上）
        IconButton {
            visible: pager.pagerEnabled
            iconName: pager.iconPrev
            tooltip: qsTr("上一页")
            hitSize: pager.hitSize
            glyphSize: pager.iconSize
            onClicked: Backend.previousSlide()
        }

        // ==================================== 页码（三行：26 / 小斜杠 / 41）
        // 变化时走透明度脉冲（与横版同一套节奏，见 PagePulse.qml）
        PagePulse {
            page: Backend.slideIndex
            visible: pager.pagerEnabled
            width: pager.contentHeight
            height: pager.infoHeight

            Column {
                anchors.centerIn: parent
                spacing: 0

                Rin.Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    typography: Rin.Typography.BodyLarge
                    text: Backend.slideTotal > 0 ? Backend.slideIndex : "-"
                }

                Rin.Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    typography: Rin.Typography.Caption
                    text: "/"
                }

                Rin.Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    typography: Rin.Typography.BodyLarge
                    text: Backend.slideTotal > 0 ? Backend.slideTotal : "-"
                }
            }
        }

        // ================================================ 下一页（chevron 朝下）
        IconButton {
            visible: pager.pagerEnabled
            iconName: pager.iconNext
            tooltip: qsTr("下一页")
            hitSize: pager.hitSize
            glyphSize: pager.iconSize
            onClicked: Backend.nextSlide()
        }
    }
}
