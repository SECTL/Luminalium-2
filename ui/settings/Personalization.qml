import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    个性化：目前只有「强调色」一项。

    2026-10-01（第四轮）用户指令：「把外观那一块除了界面语言改到新的个性化」
    —— 原挂在「通用」页末尾的「外观」组里共三张卡（应用主题 / 强调色 / 界面语言），
    前两张整体搬到本页，「界面语言」留在「通用」页（它不是外观、是语言与区域）。

    ⚠️ 2026-10-06 用户指令：「把应用是跟随系统还是亮色暗色移到通用，个性化设置
    先只留强调色」—— 「应用主题」（跟随系统 / 浅色 / 深色）那张卡整体搬回
    ``settings/General/Index.qml``，本页只剩「强调色」。这么分的道理是：深浅
    **模式**是跟系统走的环境设定（属于「通用」那种整机级开关），而**强调色**
    才是纯粹的审美选择；两件事放一起时用户会以为它们是同一组。

    导航项插在「通用」之后、「主界面」之前（``Settings.qml`` 的 ``navigationItems``）。
    ⚠️ 别把强调色再塞回「通用」或「主界面」：它调的是**整个应用**的取色，
    跟「主界面（放映时那块控制条画布）」不是一回事 —— 这条从 2026-10-01 改名那次
    就定下来了，只是归属页从「通用」换成了这里。

    底色约定：深色主题下 ``#4CC2FF`` 那一档最贴近 Fluent 默认蓝（与
    ``default_config.json`` 的 ``app.accent`` 首值一致）。
*/
Rin.FluentPage {
    id: page

    /*! 可选的强调色。第一项与 default_config.json 的 app.accent 一致。 */
    readonly property var accentPresets: [
        "#4CC2FF", "#0078D4", "#5B5FC7", "#00B294",
        "#C239B3", "#E3008C", "#EF6950", "#107C10"
    ]

    title: qsTr("个性化")
    contentSpacing: 10

    // 2026-10-06：「应用主题」搬回「通用」页，本页只剩下面这一张卡。
    // 分组标题仍是「外观」—— 等将来这一页再收新卡时不用改标题。

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("外观")
    }

    Rin.SettingCard {
        objectName: "personalizationAccent"

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
}
