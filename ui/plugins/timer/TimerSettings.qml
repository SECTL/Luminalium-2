import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    计时器插件的设置页（2026-10-06 计时器插件）。

    目前只有「提示音」一个开关：走 ``plugins_timer_alarm`` 设置键
    （``app/plugins/timer/plugin.py`` 的 ``register_setting`` 登记，
    side_effect 实时改引擎状态 —— 关掉开关连正在响的铃声一起停，不用
    重启）。「试听」按钮经动作通道让插件播一遍铃声（单次，不循环）。

    开关 ``onToggled`` 里用 ``Qt.binding`` 重装 ``checked`` 绑定：控件内部
    改属性会摘掉 QML 绑定，不重装则外部改值开关不跟 —— 历史坑，同款注释
    见 ``ui/settings/General/Index.qml`` 的开机自启开关。
*/
Rin.FluentPage {
    id: page

    title: qsTr("计时器")
    contentSpacing: 10

    Rin.SettingCard {
        objectName: "timerAlarmCard"

        Layout.fillWidth: true
        title: qsTr("提示音")
        description: qsTr("倒计时结束响起铃声并循环，最多 3 分钟；最后 3 秒逐秒提示")
        icon.name: "ic_fluent_speaker_2_20_regular"

        Rin.Switch {
            checked: Backend.settings.plugins_timer_alarm === true
            onToggled: {
                Backend.setSetting("plugins_timer_alarm", checked)
                // 重装绑定（理由见文件头注释）；幂等，写成功时照装不误。
                checked = Qt.binding(function () {
                    return Backend.settings.plugins_timer_alarm === true
                })
            }
        }
    }

    Rin.SettingCard {
        objectName: "timerAlarmPreviewCard"

        Layout.fillWidth: true
        title: qsTr("试听铃声")
        description: qsTr("播放一遍结束铃声（不循环）")
        icon.name: "ic_fluent_music_note_2_20_regular"

        Rin.Button {
            text: qsTr("播放")
            onClicked: Backend.triggerAction("plugin:timer:preview-alarm")
        }
    }
}
