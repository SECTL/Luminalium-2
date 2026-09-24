import QtQuick
import RinUI as Rin
import Luminalium

/*!
    空状态占位：图标 + 标题 + 说明。

    RinUI 0.4.4.1 **没有** ``EmptyState``（Class Widgets 2 用的新版本才有），
    所以这里手绘一个。内容本身仍全部使用 RinUI 组件（``Rin.Icon`` /
    ``Rin.Text``），只是把三者码成一个居中列。

    注意 ``Column`` 是定位器，**子项不得使用 anchors**，因此图标外面套了一层
    显式尺寸的 ``Item`` 来承担居中。
*/
Item {
    id: root

    property string iconName: ""
    property string title: ""
    property string description: ""

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width, 260)
        spacing: 6

        Item {
            width: parent.width
            height: 34

            Rin.Icon {
                anchors.centerIn: parent
                icon: root.iconName
                size: 28
                color: Lumi.textTertiary
            }
        }

        Rin.Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            typography: Rin.Typography.Body
            color: Lumi.textSecondary
            text: root.title
            visible: root.title !== ""
        }

        Rin.Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            typography: Rin.Typography.Caption
            color: Lumi.textTertiary
            text: root.description
            visible: root.description !== ""
        }
    }
}
