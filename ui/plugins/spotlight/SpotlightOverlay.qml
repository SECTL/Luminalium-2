import QtQuick
import QtQuick.Window
import RinUI as Rin
import Luminalium

/*!
    聚光灯遮罩 —— 全屏压暗 + 顶部控制胶囊。

    2026-10-06 聚光灯插件。本窗口是 ``app/windows.py`` 的**叠加窗口**家族
    （与放映顶层窗口 TopWindow 同族，Python 侧 ``RegisteredOverlay`` 懒创建）：

    * 透明窗口，QML 只画「半透明黑遮罩 + 控制胶囊」；**光斑本身不是 QML
      画的** —— Python 按 ``SetWindowRgn`` 把窗口区域塑形成「整屏 − 圆形」，
      圆内既不绘制也不命中，真实画面从洞里透出来。别想着在 QML 里再画
      一个圆，那只会叠在洞上。
    * 窗口 **不带** ``WS_EX_TRANSPARENT``（遮罩要吃点击，胶囊才可点），
      只带 ``WS_EX_NOACTIVATE``（Python 侧补）—— 点胶囊不抢前台焦点，
      放映窗口的方向键 / 滚轮照常工作。
    * flags 这里声明 FramelessWindowHint 是**必须的**：这不是 RinUI 接管的
      FluentWindow，AGENTS.md「禁 Frameless」那条约束的是被接管的窗口。

    浓度直读 ``plugins_spotlight_dim`` 设置键（settingsChanged 会推重读，
    设置页拖滑条遮罩实时变深浅）。光斑位置 / 大小由 Python 轮询喂
    ``set_hole``，本文件完全感知不到。
*/
Window {
    id: spotlightOverlay

    objectName: "SpotlightOverlay"
    title: qsTr("聚光灯")
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        | Qt.WindowDoesNotAcceptFocus

    /*! 遮罩浓度（5%~85%）。设置键名义 0–85（%），下限钳到 5 —— 全透明的
        遮罩**照样吃掉**光斑之外的所有点击（窗口命中按区域算，与像素
        alpha 无关），一块看不见还挡点击的全屏窗就是「电脑卡死」的假象
        （2026-10-07 插件巡检补的地面；设置页滑条同步从 5 起）。 */
    readonly property real dimAlpha: {
        var raw = typeof Backend !== "undefined"
                  ? Number(Backend.settings.plugins_spotlight_dim) : 60
        if (isNaN(raw)) raw = 60
        return Math.max(5, Math.min(85, raw)) / 100.0
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, spotlightOverlay.dimAlpha)

        // ------------------------------------------------ 控制胶囊（顶部居中）
        Rectangle {
            id: pill
            objectName: "spotlightPill"

            anchors.horizontalCenter: parent.horizontalCenter
            y: 18
            width: pillRow.width + 28
            height: 46
            radius: 23
            color: Qt.rgba(1, 1, 1, 0.13)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.26)

            Row {
                id: pillRow
                anchors.centerIn: parent
                spacing: 4

                Repeater {
                    // 三个胶囊按钮：缩小 / 关闭 / 放大。遮罩窗口不抢焦点，
                    // MouseArea 的悬停与点击照常工作
                    model: [
                        { icon: "ic_fluent_subtract_20_regular", action: "plugin:spotlight:smaller", tip: qsTr("缩小光斑") },
                        { icon: "ic_fluent_dismiss_20_filled", action: "plugin:spotlight:close", tip: qsTr("退出聚光灯") },
                        { icon: "ic_fluent_add_20_regular", action: "plugin:spotlight:bigger", tip: qsTr("放大光斑") },
                    ]

                    delegate: Item {
                        id: pillButton
                        required property var modelData

                        width: 38
                        height: 38

                        Rectangle {
                            anchors.fill: parent
                            radius: 19
                            color: btnArea.containsMouse
                                   ? Qt.rgba(1, 1, 1, 0.16) : "transparent"
                        }
                        Rin.Icon {
                            anchors.centerIn: parent
                            icon: pillButton.modelData.icon
                            size: 20
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: btnArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Backend.triggerAction(pillButton.modelData.action)
                        }
                        Rin.ToolTip {
                            visible: btnArea.containsMouse
                            text: pillButton.modelData.tip
                            delay: 400
                        }
                    }
                }
            }
        }

        // ------------------------------------------------ 开场提示（4 秒淡出）
        Rin.Text {
            id: hint
            anchors.horizontalCenter: parent.horizontalCenter
            y: pill.y + pill.height + 10
            text: qsTr("光斑跟随鼠标 · 键盘 + / − 或胶囊按钮调大小 · 点 ✕ 退出")
            font.pixelSize: 13
            color: Qt.rgba(1, 1, 1, 0.82)

            opacity: hintTimer.running ? 1 : 0
            Behavior on opacity {
                NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
            }

            // 遮罩每次显隐都重开一次计时：running 绑定 visible，藏了就停
            Timer {
                id: hintTimer
                interval: 4000
                running: spotlightOverlay.visible
            }
        }
    }
}
