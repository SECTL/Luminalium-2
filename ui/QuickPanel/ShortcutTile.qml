import QtQuick
import RinUI as Rin
import Luminalium

/*!
    快捷方式磁贴（纯视觉）。

    对齐 Class Widgets 2 ``TrayShortcuts.qml`` 的磁贴：圆角表面里居中一枚
    22px 图标，下面一行 Caption 文字（超长省略）。表面用 ``Rin.Clip`` ——
    圆角、可点、悬停自带高亮。

    **编辑态的手柄（拖拽 / 移除）不在这里**：``Clip`` 是 ``Button``，按下即被它
    吃掉，压在下面的拖拽 MouseArea 收不到事件。所以和 CW2 一样，由容器在磁贴
    **之上**依次叠 MouseArea 与「移除」按钮。

    ``Clip`` 覆写了 ``background`` / ``contentItem``，基类的 ``implicitWidth`` /
    ``implicitHeight`` 引用了被覆写掉的 ``row`` / ``text`` id，故宽高必须显式给。
*/
Item {
    id: root

    property string title: ""
    property string iconName: ""
    property bool editing: false

    signal clicked()

    Column {
        anchors.fill: parent
        spacing: 4

        Rin.Clip {
            id: face
            width: parent.width
            height: parent.height - label.implicitHeight - parent.spacing
            radius: Lumi.shortcutTileRadius
            padding: 0

            onClicked: {
                if (!root.editing) {
                    root.clicked()
                }
            }

            Rin.Icon {
                anchors.centerIn: parent
                icon: root.iconName
                size: Lumi.shortcutIconSize
                color: Lumi.textPrimary
            }
        }

        Rin.Text {
            id: label
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 1
            typography: Rin.Typography.Caption
            color: Lumi.textSecondary
            text: root.title
        }
    }
}
