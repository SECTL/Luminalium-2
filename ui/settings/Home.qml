import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 设置首页：一眼看清应用状态与常用入口。 */
Rin.FluentPage {
    id: page

    title: qsTr("主页")
    contentSpacing: 10

    // ---------------------------------------------------------------- 状态
    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("当前状态")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("放映状态")
        description: Backend.presentationActive
            ? qsTr("正在放映 · %1").arg(Backend.describeSlideProgress())
            : qsTr("未检测到放映中的演示文稿")
        icon.name: Backend.presentationActive
            ? "ic_fluent_slide_play_20_filled"
            : "ic_fluent_slide_play_20_regular"

        Rin.Button {
            flat: true
            text: qsTr("重新检测")
            onClicked: Backend.requestReload()
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("主题")
        description: Backend.settings.theme !== undefined
            ? (Backend.settings.theme === "dark" ? qsTr("深色") : qsTr("浅色"))
            : qsTr("深色")
        icon.name: "ic_fluent_paint_brush_20_regular"
    }

    // ------------------------------------------------------------ 快捷入口
    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("快捷入口")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("快捷面板")
        description: qsTr("点击托盘图标即可在光标附近弹出")
        icon.name: "ic_fluent_apps_list_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.tray_enabled === true
            onToggled: Backend.setSetting("tray_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("放映控制条")
        description: qsTr("检测到放映时自动出现在屏幕角落")
        icon.name: "ic_fluent_slide_play_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_enabled === true
            onToggled: Backend.setSetting("presentation_enabled", checked)
        }
    }
}
