import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    通用：托盘、快捷面板与全局外观开关。

    2026-09-25 导航重构后本页吸收了原「行为」子页的全部内容；
    2026-10-01 又吸收了原「外观」页的三张卡（主题模式 / 强调色 / 界面语言）——
    用户指令「把『外观』改成『主界面』」，而这三项是**全局外观设定**、不属于
    「主界面」这个概念，所以随改名一起并进来；原「外观」页改名为
    ``settings/MainInterface.qml`` 并留空。日志级别归调试窗口。
*/
Rin.FluentPage {
    id: page

    /*! 可选的强调色。第一项与 default_config.json 的 app.accent 一致。 */
    readonly property var accentPresets: [
        "#4CC2FF", "#0078D4", "#5B5FC7", "#00B294",
        "#C239B3", "#E3008C", "#EF6950", "#107C10"
    ]

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

    // ============================================================ 外观
    // 2026-10-01 从原「外观」页整体搬来（原页改名「主界面」并留空）。
    // 这三项是**全局**取色与文案语言，跟「主界面」不是一回事：

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("外观")
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
