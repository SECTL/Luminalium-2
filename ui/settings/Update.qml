import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*! 检查更新：目前只展示当前版本与更新渠道的占位说明。 */
Rin.FluentPage {
    id: page

    title: qsTr("检查更新")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("当前版本")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("已安装 %1").arg(Backend.appVersion)
        description: qsTr("更新渠道尚未接入；接入后这里会显示可用版本与更新日志")
        icon.name: "ic_fluent_arrow_sync_20_regular"

        Rin.Button {
            flat: true
            text: qsTr("检查更新")
            onClicked: Backend.requestSummary()
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("更新渠道")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("稳定版")
        description: qsTr("经过验证的发布版本（默认）")
        icon.name: "ic_fluent_shield_checkmark_20_regular"
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("预览版")
        description: qsTr("抢先体验新功能，可能有未打磨的地方")
        icon.name: "ic_fluent_beaker_20_regular"
        clickable: false

        Rin.Button {
            flat: true
            text: qsTr("敬请期待")
            enabled: false
        }
    }
}
