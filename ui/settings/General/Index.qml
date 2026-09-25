import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    通用：托盘与快捷面板的行为开关。

    2026-09-25 导航重构后本页吸收了原「行为」子页的全部内容；
    主题 / 强调色 / 显示语言归「外观」页，日志级别归「调试」页。
    快捷面板的尺寸与区块开关仍在左侧子项「快捷面板」里。
*/
Rin.FluentPage {
    id: page

    title: qsTr("通用")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("托盘")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("常驻托盘")
        description: qsTr("关闭后不显示托盘图标，快捷面板只能靠命令行唤起")
        icon.name: "ic_fluent_apps_list_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.tray_enabled === true
            onToggled: Backend.setSetting("tray_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("启动时提示")
        description: qsTr("驻留托盘后弹一条气泡提示")
        icon.name: "ic_fluent_alert_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.tray_notify_on_start === true
            onToggled: Backend.setSetting("tray_notify_on_start", checked)
        }
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
