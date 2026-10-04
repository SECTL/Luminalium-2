import QtQuick
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import RinUI as Rin
import Luminalium

/*!
    Fluent 2 的 **Split Button**（拆分按钮）：一枚强调色实底按钮，右端再切出一段
    带 chevron 的「展开」区，点它弹出菜单。

        [  ⟳  重新启动   │   ⌄  ]
        └──── 主操作 ────┘└ 展开 ┘

    报告窗右下角用的就是它（用户 2026-10-04 指令：「把右下角的按钮换为 Split
    Button（崩溃则为重新启动为主要，错误则以忽略为主要，展开的内容可以是退出
    程序，重新启动，忽略）」）。

    ## 为什么不是 ``Rin.DropDownButton``

    RinUI 那个是「整颗按钮都能点开菜单」（``onClicked`` 里只有 ``menu.open()``），
    而 Split Button 的关键是**两个命中区、两种行为**：左半执行主操作、右半才开
    菜单。所以这里自绘。

    ## 为什么底板要过一层 ``OpacityMask``

    两个分段的高亮是**方形**的（贴在中间那条分隔线上，不能是圆角，否则缝里会
    透出底色），但最左 / 最右两个外角必须跟着底板的圆角走。让底板把自己（连同
    子项）渲染进一层纹理、再用一枚同尺寸同圆角的矩形当遮罩裁一刀，方形高亮就
    自然被外角吃掉 —— 与 RinUI 自己画按钮底纹（``components/BasicInput/
    Button.qml`` 的 ``layer.effect``）是同一个做法。
*/

Item {
    id: root

    /*! 主操作段的文案与图标。 */
    property string text: ""
    property string iconName: ""
    /*! 按钮高度（Fluent 控件标准 32）。 */
    property int buttonHeight: 32
    /*! 右端「展开」段的宽度。 */
    property int chevronWidth: 32

    /*! 实底填充色 —— 默认强调色（主按钮）。 */
    property color fillColor: Lumi.accent
    /*! 文字 / 图标色 —— 压在强调色上的那一支（与 RinUI 的高亮按钮同源）。 */
    property color contentColor: Rin.Theme.currentTheme
        ? Rin.Theme.currentTheme.colors.textOnAccentColor : "#000000"
    property color hoverFill: Qt.rgba(1, 1, 1, 0.10)
    property color pressFill: Qt.rgba(0, 0, 0, 0.06)
    property color dividerColor: Qt.rgba(0, 0, 0, 0.18)

    /*! 主操作段被点击。 */
    signal primaryClicked()
    /*! 菜单项被点击（``quit`` / ``restart`` / ``ignore``）。 */
    signal actionTriggered(string action)

    implicitWidth: primaryLabel.implicitWidth + 24 + 1 + chevronWidth
    implicitHeight: buttonHeight
    width: implicitWidth
    height: implicitHeight

    // ================================================================ 底板
    Rectangle {
        id: surface
        anchors.fill: parent
        radius: Lumi.controlRadius
        color: root.fillColor

        layer.enabled: true
        layer.smooth: false
        layer.mipmap: false
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: surface.width
                height: surface.height
                radius: surface.radius
            }
        }

        Row {
            anchors.fill: parent
            spacing: 0

            // ---------------------------------------------------- 主操作段
            Item {
                id: primarySegment
                height: parent.height
                width: root.implicitWidth - root.chevronWidth - 1

                Rectangle {
                    anchors.fill: parent
                    color: primaryArea.pressed ? root.pressFill
                        : primaryArea.containsMouse ? root.hoverFill : "transparent"
                    Behavior on color { ColorAnimation { duration: Lumi.durationFast } }
                }

                RowLayout {
                    id: primaryLabel
                    anchors.centerIn: parent
                    spacing: 8

                    Rin.Icon {
                        Layout.alignment: Qt.AlignVCenter
                        visible: root.iconName !== ""
                        icon: root.iconName
                        size: 16
                        color: root.contentColor
                    }

                    Rin.Text {
                        Layout.alignment: Qt.AlignVCenter
                        text: root.text
                        typography: Rin.Typography.Body
                        color: root.contentColor
                        wrapMode: Text.NoWrap
                    }
                }

                MouseArea {
                    id: primaryArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.primaryClicked()
                }
            }

            // ------------------------------------------------------ 分隔线
            Rectangle {
                width: 1
                height: parent.height - 14
                anchors.verticalCenter: parent.verticalCenter
                color: root.dividerColor
            }

            // ---------------------------------------------------- 展开段
            Item {
                id: chevronSegment
                height: parent.height
                width: root.chevronWidth

                Rectangle {
                    anchors.fill: parent
                    color: chevronArea.pressed ? root.pressFill
                        : chevronArea.containsMouse ? root.hoverFill : "transparent"
                    Behavior on color { ColorAnimation { duration: Lumi.durationFast } }
                }

                Rin.Icon {
                    anchors.centerIn: parent
                    icon: "ic_fluent_chevron_down_20_filled"
                    size: 12
                    color: root.contentColor
                }

                MouseArea {
                    id: chevronArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: menu.open()
                }
            }
        }
    }

    // ================================================================ 菜单
    /*! 菜单的**定位锚**：与菜单等宽、右缘贴着按钮右缘。

        ``Rin.Menu`` 的弹出位置是按 ``parent`` 居中的（``posX = (parent.width −
        width) / 2``）。直接把按钮当 parent 的话，180 宽的菜单在按钮窄的时候
        （错误档的「忽略」只有 109 宽）会往右戳出窗口 —— 而 Popup 画在窗口的
        overlay 里，戳出去的那截会被窗口边缘**裁掉**（右下角那一圈圆角会缺一
        块）。换成这块与菜单同宽的锚，居中就等价于右对齐。 */
    Item {
        id: menuAnchor
        x: root.width - menu.width
        y: 0
        width: menu.width
        height: root.height
    }

    // 按钮贴在窗口右下角，所以菜单往**上**弹（``Rin.Position.Top``）。
    // 菜单项写死三条（用户指定）：退出程序 / 重新启动 / 忽略。
    Rin.Menu {
        id: menu
        objectName: "splitActionMenu"
        parent: menuAnchor
        position: Rin.Position.Top
        width: 180

        Rin.MenuItem {
            text: qsTr("退出程序")
            icon.name: "ic_fluent_arrow_exit_20_regular"
            onTriggered: root.actionTriggered("quit")
        }
        Rin.MenuItem {
            text: qsTr("重新启动")
            icon.name: "ic_fluent_arrow_clockwise_20_regular"
            onTriggered: root.actionTriggered("restart")
        }
        Rin.MenuItem {
            text: qsTr("忽略")
            icon.name: "ic_fluent_dismiss_20_regular"
            onTriggered: root.actionTriggered("ignore")
        }
    }
}
