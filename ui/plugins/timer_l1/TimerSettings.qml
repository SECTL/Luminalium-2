import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    计时器（Luminalium 1）插件的设置页。

    对应 L1 设置页里「计时器」那一组的三项（``plugins/builtins/settings/
    settings.html``，2026-10-17 移植）：

    1. **计时器音效** ← ``Timer.EnableSoundEffects``
       控制倒计时结束与重置时播不播提示音（L1 用的是系统自带的
       ``Windows Notify Email.wav`` / ``Speech Off.wav``，路径在插件 Python 侧）。
    2. **计时器全屏行为** ← ``Window.TimerFullscreenBehavior``
       L1 是「全屏切换 / 最大化」二选一；窗口全屏按钮据此调
       ``showFullScreen()`` 还是 ``showMaximized()``（QML 侧直接读这个键）。
    3. **快捷加时** ← ``Timer.QuickAddPresets``
       最多四个按钮、每个「数值 + 秒/分」。L1 存的是对象列表，L2 的
       ``DEFAULTS`` 不许放列表（列表注入默认层会被用户层静默吞掉，见
       ``app/config.py`` 头注释），所以配置里落成紧凑字符串 ``"1m,15s"``
       —— 解析规则在 ``app/plugins/timer_l1/plugin.py``，本页只负责编辑。

    ⚠️ 开关 / 单选都走「控件内部改属性会摘掉 QML 绑定 → ``Qt.binding`` 重装」
    这一套（历史坑，同款注释见 ``ui/settings/General/Index.qml`` 的开机自启
    开关）。快捷加时是**本地编辑 → 序列化写回字符串**：列表型值不进配置，
    编辑过程中的增删只在窗口里，写完立刻落盘。
*/
Rin.FluentPage {
    id: page

    title: qsTr("计时器")
    contentSpacing: 10

    //: 本页编辑中的快捷加时（``[{value, unit}]``，unit 是 "minute" | "second"）。
    property var presets: []

    readonly property int maxPresets: 4

    Component.onCompleted: reload()

    /*! 从配置字符串重新读一次（进页面时 / 切语言重算标签都靠它）。 */
    function reload() {
        presets = parse(Backend.settings.plugins_timer_l1_quick_add)
    }

    /*! ``"1m,15s"`` → ``[{value, unit}]``。规则与 Python 侧 ``_parse_quick_add``
        一致：最多四项、数值 1~99、单位只认 s / m，坏 token 跳过。 */
    function parse(text) {
        var out = []
        if (typeof text !== "string")
            return out
        var tokens = text.replace("，", ",").split(",")
        for (var i = 0; i < tokens.length && out.length < maxPresets; i++) {
            var token = tokens[i].trim().toLowerCase()
            if (token.length < 2)
                continue
            var unitChar = token.charAt(token.length - 1)
            if (unitChar !== "s" && unitChar !== "m")
                continue
            var value = parseInt(token.slice(0, -1), 10)
            if (!(value >= 1 && value <= 99))
                continue
            out.push({ value: value, unit: unitChar === "m" ? "minute" : "second" })
        }
        return out
    }

    function dump(items) {
        var parts = []
        for (var i = 0; i < items.length; i++)
            parts.push(items[i].value + (items[i].unit === "minute" ? "m" : "s"))
        return parts.join(",")
    }

    function commit() {
        Backend.setSetting("plugins_timer_l1_quick_add", dump(presets))
    }

    function setValue(index, value) {
        var items = presets.slice()
        if (index < 0 || index >= items.length)
            return
        items[index] = { value: value, unit: items[index].unit }
        presets = items
        commit()
    }

    function setUnit(index, unit) {
        var items = presets.slice()
        if (index < 0 || index >= items.length || items[index].unit === unit)
            return
        items[index] = { value: items[index].value, unit: unit }
        presets = items
        commit()
    }

    function removeAt(index) {
        var items = presets.slice()
        if (index < 0 || index >= items.length)
            return
        items.splice(index, 1)
        presets = items
        commit()
    }

    function addPreset() {
        if (presets.length >= maxPresets)
            return
        var items = presets.slice()
        items.push({ value: 5, unit: "minute" })
        presets = items
        commit()
    }

    // ------------------------------------------------------------ 音效
    Rin.SettingCard {
        objectName: "timerL1SoundCard"

        Layout.fillWidth: true
        title: qsTr("计时器音效")
        description: qsTr("控制计时结束和重置时是否播放提示音")
        icon.name: "ic_fluent_speaker_2_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.plugins_timer_l1_sound_effects === true
            onToggled: {
                Backend.setSetting("plugins_timer_l1_sound_effects", checked)
                // 重装绑定（理由见文件头注释）；幂等，写成功时照装不误。
                checked = Qt.binding(function () {
                    return Backend.settings.plugins_timer_l1_sound_effects === true
                })
            }
        }
    }

    // ------------------------------------------------------------ 全屏行为
    Rin.SettingCard {
        objectName: "timerL1FullscreenCard"

        Layout.fillWidth: true
        title: qsTr("计时器全屏行为")
        description: qsTr("选择计时器进入全屏时是真正全屏，还是仅最大化窗口")
        icon.name: "ic_fluent_full_screen_maximize_20_regular"

        RowLayout {
            spacing: 16

            Rin.RadioButton {
                objectName: "timerL1FullscreenModeFullscreen"
                text: qsTr("全屏切换")
                checked: Backend.settings.plugins_timer_l1_fullscreen_behavior !== "maximize"
                onToggled: {
                    if (checked)
                        Backend.setSetting("plugins_timer_l1_fullscreen_behavior", "fullscreen")
                    checked = Qt.binding(function () {
                        return Backend.settings.plugins_timer_l1_fullscreen_behavior !== "maximize"
                    })
                }
            }
            Rin.RadioButton {
                objectName: "timerL1FullscreenModeMaximize"
                text: qsTr("最大化")
                checked: Backend.settings.plugins_timer_l1_fullscreen_behavior === "maximize"
                onToggled: {
                    if (checked)
                        Backend.setSetting("plugins_timer_l1_fullscreen_behavior", "maximize")
                    checked = Qt.binding(function () {
                        return Backend.settings.plugins_timer_l1_fullscreen_behavior === "maximize"
                    })
                }
            }
        }
    }

    // ------------------------------------------------------------ 快捷加时
    Rin.SettingCard {
        objectName: "timerL1QuickAddCard"

        Layout.fillWidth: true
        title: qsTr("快捷加时")
        description: qsTr("编辑计时器里的快捷加时按钮，最多四个，可选秒或分")
        icon.name: "ic_fluent_add_circle_20_regular"

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Repeater {
                    model: page.presets

                    delegate: RowLayout {
                        required property var modelData
                        required property int index

                        Layout.fillWidth: true
                        spacing: 8

                        Rin.SpinBox {
                            from: 1
                            to: 99
                            editable: true
                            value: modelData.value
                            Layout.preferredWidth: 96
                            onValueModified: page.setValue(index, value)
                        }

                        Rin.ComboBox {
                            Layout.preferredWidth: 96
                            model: [qsTr("秒"), qsTr("分")]
                            currentIndex: modelData.unit === "minute" ? 1 : 0
                            onActivated: page.setUnit(index, currentIndex === 1 ? "minute" : "second")
                        }

                        Rin.Button {
                            text: qsTr("移除")
                            onClicked: page.removeAt(index)
                        }

                        Item { Layout.fillWidth: true }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rin.Text {
                    text: qsTr("最多四个按钮")
                    typography: Rin.Typography.Caption
                    color: Lumi.textSecondary
                }

                Item { Layout.fillWidth: true }

                Rin.Button {
                    objectName: "timerL1QuickAddAdd"
                    text: qsTr("添加快捷加时")
                    enabled: page.presets.length < page.maxPresets
                    highlighted: true
                    primaryColor: Lumi.accent
                    onClicked: page.addPreset()
                }
            }
        }
    }
}
