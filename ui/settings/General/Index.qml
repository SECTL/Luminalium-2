import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 通用：常用开关的汇总页，细分项在左侧导航的子项里。 */
Rin.FluentPage {
    id: page

    title: qsTr("通用")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("主题")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("应用主题")
        description: qsTr("跟随系统时会随 Windows 的浅色 / 深色设置切换")
        icon.name: "ic_fluent_paint_brush_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: [qsTr("跟随系统"), qsTr("浅色"), qsTr("深色")]
            currentIndex: {
                const value = Backend.settings.theme
                if (value === "light") return 1
                if (value === "dark") return 2
                return 0
            }
            onActivated: Backend.setSetting("theme", ["auto", "light", "dark"][currentIndex])
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("启动与托盘")
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
        title: qsTr("日志级别")
        description: qsTr("排查问题时改成 DEBUG，日志写在 logs/luminalium.log")
        icon.name: "ic_fluent_document_text_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: ["DEBUG", "INFO", "WARNING", "ERROR"]
            currentIndex: Math.max(0, model.indexOf(Backend.settings.log_level))
            onActivated: Backend.setSetting("log_level", model[currentIndex])
        }
    }
}
