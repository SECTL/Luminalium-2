import QtQuick
import RinUI as Rin
import Luminalium

/*!
    「退出放映」按钮，两种版式：

    * ``style: "danger"``（缺省，**Luminalium 1 的形态**）
      —— 就是 ``.tool-btn-danger``：38×38 **圆形**按钮、图标 **红色
      ``#D9485A``**、悬停浮现红 14%（``rgba(224,62,62,0.14)``）。
      L1 的退出键不是强调色实底方块，而是一枚和其他按钮同尺寸的危险色图标。
    * ``style: "accent"``（旧版式，留着备用）
      —— 强调色实底、**黑色**图标（``Lumi.onAccent``）、略宽于高（1.07）。

    两条分支各自渲染自己，外层只是个调度用的 ``Item``：
    这样两种版式都不必互相迁就属性（强调色版要 ``highlighted``，
    危险版要 ``flat`` + 自绘填充）。

    ⛔ 强调色分支里**不能覆写 ``background``**（基类有
    ``property alias radius: background.radius``）；危险分支直接用
    ``IconButton``，圆形与状态填充都在那边统一处理。
*/
Item {
    id: root

    property string style: "danger"
    property string iconName: "ic_fluent_power_20_regular"
    property string tooltip: ""
    property int buttonHeight: Lumi.dockHitSize
    /*! 仅 accent 版式用到的宽:高比（L1 danger 版是纯圆）。 */
    property real widthRatio: Lumi.dockExitWidthRatio
    property int glyphSize: Lumi.dockIconSize
    property color accent: Lumi.accent

    signal clicked()

    readonly property bool dangerStyle: style !== "accent"

    implicitWidth: Math.round(buttonHeight * (dangerStyle ? 1 : widthRatio))
    implicitHeight: buttonHeight
    width: implicitWidth
    height: implicitHeight

    // ======================================== L1 版式：危险色圆形图标按钮
    IconButton {
        anchors.fill: parent
        visible: root.dangerStyle
        iconName: root.iconName
        tooltip: root.tooltip
        hitSize: root.buttonHeight
        glyphSize: root.glyphSize
        glyphColor: Lumi.dockDangerIcon
        hoverFill: Lumi.dockDangerFill
        onClicked: root.clicked()
    }

    // ======================================== 旧版式：强调色实底方块
    Rin.Button {
        anchors.fill: parent
        visible: !root.dangerStyle
        padding: 0
        radius: Lumi.dockControlRadius
        highlighted: true
        primaryColor: root.accent

        contentItem: Item {
            // 兼容垫片：满足基类对 id `text` 的引用（font / disabled state）
            Text {
                id: text
                visible: false
            }

            Rin.Icon {
                anchors.centerIn: parent
                icon: root.iconName
                size: root.glyphSize
                color: Lumi.onAccent
            }
        }

        Rin.ToolTip {
            visible: root.tooltip !== "" && parent.hovered
            text: root.tooltip
            delay: 600
        }
    }
}
