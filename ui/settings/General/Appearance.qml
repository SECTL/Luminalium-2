import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 外观：主题模式与强调色。 */
Rin.FluentPage {
    id: page

    /*! 可选的强调色。第一项与 default_config.json 的 app.accent 一致。 */
    readonly property var accentPresets: [
        "#4CC2FF", "#0078D4", "#5B5FC7", "#00B294",
        "#C239B3", "#E3008C", "#EF6950", "#107C10"
    ]

    title: qsTr("外观")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("主题模式")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("应用主题")
        description: qsTr("影响所有窗口与控件的取色")
        icon.name: "ic_fluent_dark_theme_20_regular"

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
        text: qsTr("强调色")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("强调色")
        description: qsTr("按钮、开关、选中态统一使用这个颜色")
        icon.name: "ic_fluent_color_20_regular"

        // 色板没有对应的 RinUI 组件，用 Rin.Clip 画成圆形色块
        // （Clip = 圆角可点表面，悬停自带高亮；这里把圆角拉满成圆）。
        Repeater {
            model: page.accentPresets

            delegate: Rin.Clip {
                required property var modelData

                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                Layout.alignment: Qt.AlignVCenter
                radius: width / 2
                padding: 0
                color: modelData
                border.width: Backend.settings.accent === modelData ? 2 : 0
                border.color: Lumi.textPrimary

                onClicked: Backend.setSetting("accent", modelData)

                Rin.Icon {
                    anchors.centerIn: parent
                    visible: Backend.settings.accent === modelData
                    icon: "ic_fluent_checkmark_20_filled"
                    size: 14
                    color: "#FFFFFF"
                }
            }
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("显示语言")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("界面语言")
        description: qsTr("切换后需要重新加载应用")
        icon.name: "ic_fluent_local_language_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: ["zh_CN", "en_US"]
            currentIndex: Math.max(0, model.indexOf(Backend.settings.language))
            onActivated: Backend.setSetting("language", model[currentIndex])
        }
    }
}
