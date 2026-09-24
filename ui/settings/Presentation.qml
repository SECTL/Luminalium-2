import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 放映控制条：开关、位置、外观细节。 */
Rin.FluentPage {
    id: page

    title: qsTr("放映控制")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("总开关")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("放映时显示控制条")
        description: qsTr("检测到 PowerPoint 进入放映状态后自动出现")
        icon.name: "ic_fluent_slide_play_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_enabled === true
            onToggled: Backend.setSetting("presentation_enabled", checked)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("位置")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("水平边距")
        description: qsTr("控制条距屏幕左右边缘的距离（像素）")
        icon.name: "ic_fluent_arrow_bidirectional_left_right_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 140
            from: 0
            to: 200
            value: Backend.settings.presentation_margin_x !== undefined
                ? Backend.settings.presentation_margin_x : 8
            onValueModified: Backend.setSetting("presentation_margin_x", value)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("垂直边距")
        description: qsTr("控制条距屏幕上下边缘的距离（像素）")
        icon.name: "ic_fluent_arrow_bidirectional_up_down_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 140
            from: 0
            to: 200
            value: Backend.settings.presentation_margin_y !== undefined
                ? Backend.settings.presentation_margin_y : 8
            onValueModified: Backend.setSetting("presentation_margin_y", value)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("目标显示器")
        description: qsTr("宽屏放映时把控制条钉在指定屏幕上")
        icon.name: "ic_fluent_desktop_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: [qsTr("跟随放映窗口"), qsTr("主显示器")]
            currentIndex: Backend.settings.presentation_screen_index === -1 ? 0 : 1
            onActivated: Backend.setSetting("presentation_screen_index", currentIndex === 0 ? -1 : 0)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("外观")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("投影")
        description: qsTr("底板下方的柔和投影；纯色背景下关掉更清爽")
        icon.name: "ic_fluent_layer_diagonal_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_shadow_enabled === true
            onToggled: Backend.setSetting("presentation_shadow_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("组分隔线")
        description: qsTr("在工具 / 动作 / 退出之间绘制细竖线")
        icon.name: "ic_fluent_line_vertical_1_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_divider_enabled === true
            onToggled: Backend.setSetting("presentation_divider_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("页码切换")
        description: qsTr("右下角独立的上一页 / 下一页 pill")
        icon.name: "ic_fluent_arrow_sort_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_pager_enabled === true
            onToggled: Backend.setSetting("presentation_pager_enabled", checked)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("检测")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("轮询间隔")
        description: qsTr("越短越跟手，但 CPU 占用略高")
        icon.name: "ic_fluent_timer_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 160
            from: 100
            to: 2000
            stepSize: 100
            value: Backend.settings.presentation_poll_interval_ms !== undefined
                ? Backend.settings.presentation_poll_interval_ms : 400
            onValueModified: Backend.setSetting("presentation_poll_interval_ms", value)
        }
    }
}
