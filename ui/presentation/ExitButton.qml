import QtQuick
import RinUI as Rin
import Luminalium

/*!
    「退出放映」按钮。**就是圆**（直径 = 内容高 = 38），与其他工具栏按钮
    同款形态，区别只在配色：

    * ``style: "default"``（**缺省**）—— 普通透明圆钮 + 主题色电源图标，
      悬停浮现与其他按钮相同的淡填充。强调色实底版式已按用户要求取消
      （2026-09-25），退出键不再搞特殊。
    * ``style: "danger"`` —— Luminalium 1 的 ``.tool-btn-danger``：透明
      圆钮 + 红色电源图标 ``#D9485A``、悬停浮现红 14%。

    两种版式都是 ``IconButton``（见该组件的 contentItem 覆写契约注释），
    这里只是个配色的调度壳。

    自检读 ``fillColor`` / ``iconColor`` —— 两种版式**尺寸完全一样**，
    只能靠颜色区分，所以把解析出来的颜色暴露出来给自检比对
    （default 的填充平时透明，悬停才浮现，所以 ``fillColor`` 报的是悬停档）。
*/
Item {
    id: root

    property string style: "default"
    property string iconName: "ic_fluent_power_20_regular"
    property string tooltip: ""
    /*! 按钮的名称文本（「退出放映」，由 ``PresentationDock`` 从 ``exit.label`` 传下来）。 */
    property string label: ""
    /*! 是否在图标旁显示 ``label``（跟着工具栏的「显示按钮文本」开关走）。 */
    property bool showLabel: false
    property int buttonHeight: Lumi.dockHitSize
    property int glyphSize: Lumi.dockIconSize

    signal clicked()

    readonly property bool dangerStyle: style === "danger"
    /*! 直径。 */
    readonly property int buttonSize: buttonHeight
    /*! 实底填充色（两种版式平时都是透明的，这里报的是**悬停档**）。 */
    readonly property color fillColor: dangerStyle
        ? Lumi.dockDangerFill : Lumi.dockButtonHoverFill
    readonly property color iconColor: dangerStyle
        ? Lumi.dockDangerIcon : Lumi.textPrimary

    /*! 尺寸由里面那枚 ``IconButton`` 说了算 —— 带名称文本时它会变宽，
        这里照着它的 implicit 尺寸走，别自己写死成 ``buttonSize``（那样文字会溢出）。 */
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    width: implicitWidth
    height: implicitHeight

    IconButton {
        id: button
        anchors.fill: parent
        iconName: root.iconName
        tooltip: root.tooltip
        label: root.label
        showLabel: root.showLabel
        hitSize: root.buttonSize
        glyphSize: root.glyphSize
        glyphColor: root.iconColor
        hoverFill: root.fillColor
        onClicked: root.clicked()
    }
}
