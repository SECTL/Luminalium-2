import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 行为：托盘交互与快捷面板的弹出规则。 */
Rin.FluentPage {
    id: page

    title: qsTr("行为")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("托盘")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("左键打开快捷面板")
        description: qsTr("关闭后左键不再唤出面板，只能走右键菜单")
        icon.name: "ic_fluent_cursor_click_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.tray_show_on_click === true
            onToggled: Backend.setSetting("tray_show_on_click", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("托盘提示文字")
        description: qsTr("鼠标悬停在托盘图标上时显示")
        icon.name: "ic_fluent_text_bulleted_list_20_regular"

        Rin.TextField {
            Layout.preferredWidth: 220
            text: Backend.settings.tray_tooltip !== undefined ? Backend.settings.tray_tooltip : ""
            onEditingFinished: Backend.setSetting("tray_tooltip", text)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("快捷面板")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("失去焦点时收起")
        description: qsTr("点击别处自动隐藏，和系统托盘菜单一致")
        icon.name: "ic_fluent_eye_tracking_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.panel_hide_on_deactivate === true
            onToggled: Backend.setSetting("panel_hide_on_deactivate", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("快捷方式锁定")
        description: qsTr("锁定后面板上的「编辑」按钮消失，防止误改")
        icon.name: "ic_fluent_lock_closed_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.panel_shortcuts_locked === true
            onToggled: Backend.setSetting("panel_shortcuts_locked", checked)
        }
    }
}
