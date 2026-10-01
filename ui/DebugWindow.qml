import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    调试窗口（开发者专用，**不对外露出入口**）。

    原先调试项是设置窗口导航栏最底部的一项（``settings/Debug.qml``），
    2026-09-30 按用户要求改成**独立窗口**：调试内容从设置导航里摘出去，
    入口换成「在设置窗口左上角的标题文本上连点 10 次」（见
    ``Settings.qml`` 的 ``debugTitleHotspot``）。这样普通用户翻设置
    永远看不到它，而开发者不用记命令行参数。

    为什么不用 ``Rin.FluentWindow``：那个组件自带左侧 ``NavigationView``
    （为设置这种多页结构准备的）。调试窗口是**单页**的，套一层只有一项的
    导航栏纯属浪费 —— 用它的基类 ``Rin.FluentWindowBase``，正文直接落在
    标题栏下方的内容区（``default property content`` → ``contentArea``）。

    窗口只隐藏不销毁：与设置窗口同一套约定（桌面常驻应用里重建一个
    Fluent 窗口的开销不值得），关闭走 ``Backend.closeDebugWindow()``。
*/
Rin.FluentWindowBase {
    id: debugWindow

    title: qsTr("调试")
    visible: false
    // 高度贴着正文（三张卡片 + 分组标题 + 上下 24 留白 ≈ 418），不留大片空白；
    // 以后加诊断项超出可视区时 Flickable 接管滚动
    width: 620
    height: 470
    minimumWidth: 520
    minimumHeight: 320

    onClosing: function (event) {
        event.accepted = false
        Backend.closeDebugWindow()
    }

    /*! 原生边框交给 RinUI 管 —— 与 ``Settings.qml`` 同一处理，别再往 ``flags``
        里塞 ``FramelessWindowHint``：窗口已由 Python 侧
        （``WindowManager._attach_to_rinui``）补登记进 RinUI，``WM_NCCALCSIZE``
        会被处理掉原生标题栏，而 ``WS_CAPTION`` 是系统阴影 / 圆角 / Snap 的前提。 */

    // ============================================================ 正文
    // 内容不多，但留一层 Flickable：以后往下加诊断项时不必再改结构
    // （滚轮可用；刻意不挂 ScrollBar —— 见项目约定「优先 RinUI 组件」，
    // 且这里内容高度稳定在可视区内，滚动条平时根本不会出现）。
    Flickable {
        anchors.fill: parent
        clip: true
        contentHeight: content.implicitHeight + 48

        ColumnLayout {
            id: content
            x: 28
            y: 24
            width: parent.width - 56
            spacing: 10

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
                // 措辞收短：原来后面还挂着「排查控制条不出现时先看这里」，
                // 620 宽的调试窗口里要折成两行（控制条不出现的问题看日志更直接）。
                description: qsTr("越短越跟手，CPU 占用略高")
                icon.name: "ic_fluent_timer_20_regular"

                // 滑块而不是 SpinBox：这一项是「试出来的」—— 拖到不卡为止，
                // 不需要精确到 1ms，档位 100ms。
                SettingSlider {
                    primaryColor: Lumi.accent
                    from: 100
                    to: 2000
                    stepSize: 100
                    suffix: " ms"
                    value: Backend.settings.presentation_poll_interval_ms !== undefined
                        ? Backend.settings.presentation_poll_interval_ms : 400
                    onMoved: Backend.setSetting("presentation_poll_interval_ms",
                                                Math.round(value))
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
    }
}
