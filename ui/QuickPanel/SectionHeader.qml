import QtQuick
import RinUI as Rin
import Luminalium

/*!
    小节标题行：左标题 + 右侧操作按钮。

    对齐 Class Widgets 2 ``TrayShortcuts.qml`` 的标题行结构
    （``Text { BodyStrong }`` + 弹簧 + 若干 ``ToolButton { flat: true }``）：
    编辑模式下的「+」与常驻的「编辑 / 完成」切换按钮。

    定位器 ``Row`` 的子项不得使用 anchors，故按钮高度由自身隐式尺寸决定。
*/
Item {
    id: root

    property string title: ""
    property bool editing: false
    property bool showEdit: true
    property bool showAdd: false
    property bool addEnabled: true

    signal editToggled()
    signal addRequested()

    implicitHeight: Math.max(titleLabel.implicitHeight, actions.implicitHeight)

    Rin.Text {
        id: titleLabel
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        typography: Rin.Typography.BodyStrong
        text: root.title
    }

    Row {
        id: actions
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        IconButton {
            visible: root.editing && root.showAdd
            enabled: root.addEnabled
            iconName: "ic_fluent_add_20_regular"
            tooltip: qsTr("添加")
            onClicked: root.addRequested()
        }

        IconButton {
            visible: root.showEdit
            iconName: root.editing
                ? "ic_fluent_checkmark_20_regular"
                : "ic_fluent_edit_20_regular"
            tooltip: root.editing ? qsTr("完成") : qsTr("编辑")
            onClicked: root.editToggled()
        }
    }
}
