import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    计时器插件的设置页。

    2026-10-17 计时器换成 HTML 原版（Lmn-copy 移植，见
    ``app/plugins/timer/plugin.py`` 头注释）后本页保留：「提示音」开关
    走 ``plugins_timer_alarm`` 设置键，side_effect 实时合成进喂给页面的
    ``Timer.EnableSoundEffects``（不用重启）；「试听」经动作通道让
    Python 用 winsound 播一遍页面同款系统提示音（页面藏着也能听到）。

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
        description: qsTr("倒计时结束与重置时播放提示音（Windows 系统音）")
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
        description: qsTr("播放一遍结束提示音（单次）")
        icon.name: "ic_fluent_music_note_2_20_regular"

        Rin.Button {
            text: qsTr("播放")
            onClicked: Backend.triggerAction("plugin:timer:preview-alarm")
        }
    }
}
