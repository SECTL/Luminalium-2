import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 快捷面板：尺寸、弹出偏移与区块开关。 */
Rin.FluentPage {
    id: page

    title: qsTr("快捷面板")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("尺寸与位置")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("面板宽度")
        description: qsTr("默认 375，和 Class Widgets 2 的托盘面板同宽")
        icon.name: "ic_fluent_arrow_bidirectional_left_right_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 150
            from: 300
            to: 640
            stepSize: 5
            value: Backend.settings.panel_width !== undefined ? Backend.settings.panel_width : 375
            onValueModified: Backend.setSetting("panel_width", value)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("面板高度")
        description: qsTr("内容超出后快捷方式网格自己滚动，面板本身不滚动")
        icon.name: "ic_fluent_arrow_bidirectional_up_down_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 150
            from: 360
            to: 900
            stepSize: 10
            value: Backend.settings.panel_height !== undefined ? Backend.settings.panel_height : 520
            onValueModified: Backend.setSetting("panel_height", value)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("弹出偏移")
        description: qsTr("面板顶边相对光标下移的距离；下方放不下会自动翻到光标上方")
        icon.name: "ic_fluent_arrow_move_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 150
            from: 0
            to: 200
            stepSize: 2
            value: Backend.settings.panel_offset_y !== undefined ? Backend.settings.panel_offset_y : 30
            onValueModified: Backend.setSetting("panel_offset_y", value)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("显示内容")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("快捷方式")
        description: qsTr("3 列磁贴网格；在面板里点「编辑」可增删与拖拽排序")
        icon.name: "ic_fluent_apps_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.panel_section_shortcuts === true
            onToggled: Backend.setSetting("panel_section_shortcuts", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("放映状态")
        description: qsTr("卡片内一行放映检测摘要（放映中 / 页码）")
        icon.name: "ic_fluent_slide_play_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.panel_section_status === true
            onToggled: Backend.setSetting("panel_section_status", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("底部工具栏")
        description: qsTr("重新加载 / 退出")
        icon.name: "ic_fluent_navigation_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.panel_section_footer === true
            onToggled: Backend.setSetting("panel_section_footer", checked)
        }
    }
}
