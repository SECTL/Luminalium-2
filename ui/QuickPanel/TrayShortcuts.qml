import QtQuick
import QtQuick.Layouts
import QtQml.Models
import RinUI as Rin
import Luminalium

/*!
    快捷方式区。

    结构对齐 Class Widgets 2 的 ``Components/TrayShortcuts.qml``：

    * 标题行：``快捷方式`` + 右侧「编辑 / 完成」与「+」两个扁平图标按钮；
    * 空状态：没有启用任何快捷方式时给出引导文案；
    * 主体：**3 列** ``GridView``，单元格高 84，磁贴比单元格小 6；
    * 编辑态：磁贴上方叠一层拖拽 ``MouseArea``（拖到别的格子上即换位）与
      左上角「移除」按钮。顺序不能反 —— ``Clip`` 是 ``Button``，会把按下事件
      吃掉，所以手柄必须叠在磁贴**之上**。

    数据来自 ``Backend.shortcutItems``（已启用的，按配置顺序），
    编辑结果通过 ``Backend.setShortcutEnabled`` / ``Backend.moveShortcut`` 回写配置。
*/
ColumnLayout {
    id: root

    property bool locked: false
    property bool editing: false

    signal shortcutTriggered()
    signal addRequested()

    spacing: Lumi.panelSectionSpacing

    Component.onCompleted: {
        if (visualModel.count === 0 && !root.locked) {
            root.editing = true
        }
    }

    SectionHeader {
        Layout.fillWidth: true
        title: qsTr("快捷方式")
        editing: root.editing
        showEdit: !root.locked
        showAdd: true
        addEnabled: Backend.availableShortcutItems.length > 0
        onEditToggled: root.editing = !root.editing
        onAddRequested: root.addRequested()
    }

    EmptyState {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: visualModel.count === 0
        iconName: "ic_fluent_apps_20_regular"
        title: qsTr("还没有快捷方式")
        description: qsTr("点标题栏的「+」添加。")
    }

    GridView {
        id: grid
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: Math.min(contentHeight, Lumi.shortcutGridMaxHeight)
        clip: true
        interactive: contentHeight > height
        visible: visualModel.count > 0
        cellWidth: width / 3
        cellHeight: Lumi.shortcutCellHeight
        model: visualModel

        // 不挂 ScrollBar：`ScrollBar.vertical` 附着属性来自 QtQuick.Controls，
        // 而本项目约定不导入它（会与 RinUI 的同名类型打架）。滚轮 / 拖拽照样能滚。

        delegate: Item {
            id: cell

            required property var modelData
            property int visualIndex: DelegateModel.itemsIndex

            width: grid.cellWidth - Lumi.shortcutCellGap
            height: grid.cellHeight - Lumi.shortcutCellGap

            Item {
                id: tile
                width: cell.width
                height: cell.height
                z: dragArea.drag.active ? 1 : 0
                Drag.active: dragArea.drag.active
                Drag.source: cell
                Drag.hotSpot.x: width / 2
                Drag.hotSpot.y: height / 2

                // 拖拽时挂到 GridView 的内容层，避免被 cell 裁切
                states: State {
                    when: dragArea.drag.active
                    ParentChange {
                        target: tile
                        parent: grid.contentItem
                    }
                }

                ShortcutTile {
                    anchors.fill: parent
                    title: cell.modelData.title !== undefined ? cell.modelData.title : ""
                    iconName: cell.modelData.icon !== undefined ? cell.modelData.icon : ""
                    editing: root.editing
                    onClicked: {
                        if (Backend.activateShortcut(cell.modelData.id)) {
                            root.shortcutTriggered()
                        }
                    }
                }

                // 编辑态手柄：拖拽
                MouseArea {
                    id: dragArea
                    anchors.fill: parent
                    enabled: root.editing && !root.locked
                    drag.target: tile
                    onReleased: Backend.moveShortcut(cell.modelData.id, cell.visualIndex)
                }

                // 编辑态手柄：移除（必须叠在 dragArea 之后才收得到点击）
                IconButton {
                    visible: root.editing
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.margins: -6
                    iconName: "ic_fluent_subtract_20_regular"
                    tooltip: qsTr("移除")
                    buttonSize: 24
                    iconSize: 14
                    onClicked: Backend.setShortcutEnabled(cell.modelData.id, false)
                }
            }

            DropArea {
                anchors.fill: parent
                onEntered: function (drag) {
                    if (drag.source && drag.source !== cell
                            && drag.source.visualIndex !== cell.visualIndex) {
                        visualModel.items.move(drag.source.visualIndex, cell.visualIndex)
                    }
                }
            }
        }

        move: Transition {
            NumberAnimation { properties: "x,y"; duration: 160; easing.type: Easing.OutCubic }
        }

        moveDisplaced: Transition {
            NumberAnimation { properties: "x,y"; duration: 160; easing.type: Easing.OutCubic }
        }
    }

    DelegateModel {
        id: visualModel
        model: Backend.shortcutItems
    }
}
