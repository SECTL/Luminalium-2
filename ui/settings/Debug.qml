import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    调试：开发者用的诊断项，普通用户不需要碰。

    收录「看起来不适宜直接给用户看」的设置：日志级别、放映检测轮询
    间隔、开发中水印开关。导航里钉在底部，图标是只小虫子。
*/
Rin.FluentPage {
    id: page

    title: qsTr("调试")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("诊断")
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

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("放映检测轮询间隔")
        description: qsTr("越短越跟手，但 CPU 占用略高；排查控制条不出现时先看这里")
        icon.name: "ic_fluent_timer_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 160
            from: 100
            to: 2000
            stepSize: 100
            value: Backend.settings.presentation_poll_interval_ms !== undefined
                ? Backend.settings.presentation_poll_interval_ms : 400
            onValueModified: Backend.setSetting("presentation_poll_interval_ms", value)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("开发专用")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("开发中水印")
        description: qsTr("每个窗口左下角的「开发中版本」角标；改动在重启后生效")
        icon.name: "ic_fluent_bug_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            // 缺省开启（缺键 / undefined 都算 true），只有显式 false 才关
            checked: Backend.settings.dev_watermark !== false
            onToggled: Backend.setSetting("dev_watermark", checked)
        }
    }
}
