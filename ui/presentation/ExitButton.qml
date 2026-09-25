import QtQuick
import RinUI as Rin
import Luminalium

/*!
    「退出放映」按钮。**两种版式都是圆**（直径 = 内容高 = 38），区别只在填充：

    * ``style: "accent"``（**缺省**）—— 强调色实底圆 + 深色图标（``Lumi.onAccent``）。
      用的是 ``Rin.Button { highlighted: true }``，悬停 / 按下的反馈由基类给
      （悬停淡到 0.875、按下 0.65）。注意这里的 ``radius`` alias 到
      ``background.radius``，所以**不能**再替换 ``background`` —— 换了别名就断。
      旧版式是「略宽于高的圆角方块（radius 5）」，现在按用户要求收成纯圆：
      宽 = 高 = ``buttonSize``、``radius = buttonSize / 2``。
    * ``style: "danger"`` —— Luminalium 1 的 ``.tool-btn-danger``：透明圆钮 +
      红色电源图标 ``#D9485A``、悬停浮现红 14%，形态与别的工具栏按钮一致。

    两条分支各自渲染自己，外层只是个调度用的 ``Item``：这样两种版式都不必
    互相迁就属性（强调色版要 ``highlighted``，危险版要 ``flat`` + 自绘填充）。

    自检读 ``fillColor`` / ``iconColor`` / ``buttonSize`` —— 两个版式现在**尺寸完全
    一样**，只能靠颜色区分，所以把解析出来的颜色暴露出来给自检比对。
*/
Item {
    id: root

    property string style: "accent"
    property string iconName: "ic_fluent_power_20_regular"
    property string tooltip: ""
    property int buttonHeight: Lumi.dockHitSize
    property int glyphSize: Lumi.dockIconSize
    property color accent: Lumi.accent

    signal clicked()

    readonly property bool dangerStyle: style === "danger"
    /*! 直径：两种版式共用（圆）。 */
    readonly property int buttonSize: buttonHeight
    /*! 实底填充色（danger 版平时是透明的，只有悬停才浮现红）。 */
    readonly property color fillColor: dangerStyle ? Lumi.dockDangerFill : root.accent
    readonly property color iconColor: dangerStyle ? Lumi.dockDangerIcon : Lumi.onAccent

    implicitWidth: buttonSize
    implicitHeight: buttonSize
    width: implicitWidth
    height: implicitHeight

    // ======================================== 缺省版式：强调色实底圆
    Rin.Button {
        anchors.fill: parent
        visible: !root.dangerStyle
        // 覆写 contentItem 的连带契约：基类的 implicit* 引用默认 contentItem 里的
        // ``row`` —— 不一起覆写的话，一旦有人问 implicitWidth 就是 ReferenceError。
        implicitWidth: root.buttonSize
        implicitHeight: root.buttonSize
        padding: 0
        // 圆形：radius 是 ``background.radius`` 的别名，这里没换 background，安全
        radius: Math.round(root.buttonSize / 2)
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
                color: root.iconColor
            }
        }

        Rin.ToolTip {
            visible: root.tooltip !== "" && parent.hovered
            text: root.tooltip
            delay: 600
        }
    }

    // ======================================== L1 版式：危险色图标圆钮
    IconButton {
        anchors.fill: parent
        visible: root.dangerStyle
        iconName: root.iconName
        tooltip: root.tooltip
        hitSize: root.buttonSize
        glyphSize: root.glyphSize
        glyphColor: root.iconColor
        hoverFill: root.fillColor
        onClicked: root.clicked()
    }
}
