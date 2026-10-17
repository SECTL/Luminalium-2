import QtQuick
import RinUI as Rin
import Luminalium
import ".."

/*!
    计时页（L1 的 ``#view-timer``：pivot + 起跑前的轮盘 / 到点 + 跑动态圆环 +
    时间到）。

    侧边栏版窗口把页面交给 ``NavigationView`` 加载，本页只读宿主窗口
    （``Window.window``，不是裸 ``window``）的引擎状态，写交互只走
    ``Backend.triggerAction("plugin:timer_l1:…")``。

    四个子层按 L1 的 CSS 版式锚定叠放（top 80 / bottom 100 / 左右 32 由
    ``TimerWindow.qml`` 的页容器给）：

    * 起跑前 —— pivot（倒计时 / 到点）+ 三滚轮 + 分隔线 + 常用时间
    * 跑动 / 暂停 —— 300 圆环（r140 / 描边 6）+ 64 时间 + 共 N 秒 + 快捷加时
    * 走完 —— 「时间到」
    * 底部控制层 —— ``TimerControlLayer``

    2026-10-17「RinUI 规范」一轮替换：本页的手搓控件全部换成 RinUI 自家的 ——

    ============================  ==============================================
    L1 / 上一版                   现在
    ============================  ==============================================
    文字 pivot + 自绘下划线        ``Rin.Segmented`` + ``Rin.SegmentedItem``
    裸 ``Text``                   ``Rin.Text``（字阶见下）
    描边胶囊（预设 / 加时）         ``Rin.Button``
    竖分隔线 ``Rectangle``        ``Rin.ToolSeparator``
    ============================  ==============================================

    字阶：标签类文字一律走 RinUI 字阶（``Rin.Typography``：Body 14 / Caption 12
    / Subtitle 20 / Title 28）；**显示级**数字（64 时间、56 滚轮、120 秒表）
    RinUI 字阶里没有对应档，保留 L1 原值并显式写 ``font.pixelSize`` ——
    实例赋值会盖掉 ``Rin.Text`` 按 typography 的绑定，这正是要的效果。

    ⚠️ ``Rin.Text`` 的 ``font.weight`` 也必须显式写：基类默认分支是
    ``return font.weight`` 的自指绑定，不写就等于把字重交给运气。
*/
Item {
    id: timerPage

    readonly property var host: Window.window

    // ------------------------------------------------------------ 起跑前
    Item {
        id: pickerLayer
        anchors.fill: parent
        visible: opacity > 0
        opacity: host ? (host.tmState === "picker" ? 1 : 0) : 0
        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        // pivot tabs（L1 .timer-pivot：gap 24，选中下划线 2px）→ RinUI 的
        // Segmented：互斥、键盘导航、选中底色与底部指示条都由它给
        Rin.Segmented {
            id: pivot
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 24

            currentIndex: host ? (host.targetTab ? 1 : 0) : 0
            onCurrentIndexChanged: {
                if (host)
                    host.targetTab = currentIndex === 1
                // 控件内部改属性会摘掉 QML 绑定 → 重装（同 TimerSettings 的
                // 开关 / 单选；幂等，值没变时不会二次触发）
                currentIndex = Qt.binding(function () {
                    return host ? (host.targetTab ? 1 : 0) : 0
                })
            }

            Rin.SegmentedItem {
                text: qsTr("倒计时")
            }
            Rin.SegmentedItem {
                text: qsTr("到点")
            }
        }

        // -------------------------------------------------------- 倒计时 tab
        Row {
            id: durationRow
            visible: host ? !host.targetTab : true
            anchors.top: pivot.bottom
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            height: 240
            spacing: 16

            // 三个滚轮（L1 .wheel-picker-container，flex 1）
            Item {
                width: (parent.width - 16 * 2 - 1) / 2
                height: parent.height

                Row {
                    anchors.centerIn: parent
                    spacing: 10

                    WheelColumn {
                        id: hourWheel
                        count: 24
                        onCurrentIndexChanged: if (host) host.pickH = currentIndex
                        unitText: qsTr("时")
                    }
                    Rin.Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.verticalCenterOffset: -10
                        text: ":"
                        // RinUI 字阶没有 40 这一档，显式给（显示级标点）
                        font.pixelSize: 40
                        color: Lumi.textPrimary
                        opacity: 0.5
                    }
                    WheelColumn {
                        id: minuteWheel
                        count: 60
                        onCurrentIndexChanged: if (host) host.pickM = currentIndex
                        unitText: qsTr("分")
                    }
                    Rin.Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.verticalCenterOffset: -10
                        text: ":"
                        font.pixelSize: 40
                        color: Lumi.textPrimary
                        opacity: 0.5
                    }
                    WheelColumn {
                        id: secondWheel
                        count: 60
                        onCurrentIndexChanged: if (host) host.pickS = currentIndex
                        unitText: qsTr("秒")
                    }
                }

                // 上下淡出（L1 mask-image：0% 透明 → 30% 实 → 70% 实 → 100% 透明）
                // ⚠️ 颜色必须取**页面实际底色**（``navPageBg``：appLayer 的
                // layerColor 盖在窗口基色上），用 surfaceBg 会差一档、留下亮边
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 72
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Lumi.navPageBg }
                        GradientStop { position: 1.0; color: Lumi.fade(Lumi.navPageBg, 0) }
                    }
                }
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 72
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Lumi.fade(Lumi.navPageBg, 0) }
                        GradientStop { position: 1.0; color: Lumi.navPageBg }
                    }
                }
            }

            // 竖分隔线（L1 .timer-setup-divider：1×200）
            Rin.ToolSeparator {
                orientation: Qt.Vertical
                width: 1
                height: 200
                anchors.verticalCenter: parent.verticalCenter
                // 基类写死了 2px padding，要精确尺寸必须一并归零
                padding: 0
                topPadding: 0
                bottomPadding: 0
            }

            // 常用时间（L1 .recent-durations：4 列，按钮圆角 10）
            Column {
                width: (parent.width - 16 * 2 - 1) / 2
                anchors.verticalCenter: parent.verticalCenter
                spacing: 12

                Rin.Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("常用时间")
                    typography: Rin.Typography.Body
                    color: Lumi.textSecondary
                }

                Grid {
                    anchors.horizontalCenter: parent.horizontalCenter
                    columns: 4
                    columnSpacing: 8
                    rowSpacing: 8

                    Repeater {
                        model: host ? host.presetSeconds : []

                        delegate: Rin.Button {
                            id: presetBtn
                            required property int modelData

                            width: 84
                            height: 32
                            // RinUI 字阶无此档，显式给（L1 .recent-item：圆角 10）
                            radius: 10
                            // 四边 padding 逐个清零：基类写的是 6/5/7，
                            // contentItem 会被挤成 40×32 而不是铺满 84×32
                            padding: 0
                            topPadding: 0
                            bottomPadding: 0
                            leftPadding: 0
                            rightPadding: 0
                            text: host ? host.fmtPreset(presetBtn.modelData) : ""

                            onClicked: {
                                // 预设 = 直接灌进三个滚轮（L1 同款）
                                var total = presetBtn.modelData
                                hourWheel.setIndex(Math.floor(total / 3600))
                                minuteWheel.setIndex(Math.floor((total % 3600) / 60))
                                secondWheel.setIndex(total % 60)
                            }
                        }
                    }
                }
            }
        }

        // -------------------------------------------------------- 到点 tab
        Item {
            id: targetRow
            visible: host ? host.targetTab : false
            anchors.top: pivot.bottom
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            width: targetWheels.width
            height: 240

            Row {
                id: targetWheels
                anchors.centerIn: parent
                spacing: 10

                WheelColumn {
                    id: targetHourWheel
                    count: 24
                    onCurrentIndexChanged: if (host) host.targetH = currentIndex
                    unitText: qsTr("时")
                }
                Rin.Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: -10
                    text: ":"
                    font.pixelSize: 40
                    color: Lumi.textPrimary
                    opacity: 0.5
                }
                WheelColumn {
                    id: targetMinuteWheel
                    count: 60
                    onCurrentIndexChanged: if (host) host.targetM = currentIndex
                    unitText: qsTr("分")
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 72
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Lumi.navPageBg }
                    GradientStop { position: 1.0; color: Lumi.fade(Lumi.navPageBg, 0) }
                }
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 72
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Lumi.fade(Lumi.navPageBg, 0) }
                    GradientStop { position: 1.0; color: Lumi.navPageBg }
                }
            }
        }

        // 到点提示（L1 updateTargetTimeInfo：随两个滚轮实时重算）
        Rin.Text {
            anchors.top: targetRow.bottom
            anchors.topMargin: 12
            anchors.horizontalCenter: parent.horizontalCenter
            visible: host ? host.targetTab : false
            text: {
                var host = timerPage.host
                if (!host)
                    return ""
                var target = new Date()
                target.setHours(host.targetH, host.targetM, 0, 0)
                var now = new Date()
                if (target <= now)
                    return qsTr("目标时间已过，将设为明天")
                return qsTr("将在 %1 后响铃").arg(
                    host.fmtDuration(Math.ceil((target - now) / 1000)))
            }
            typography: Rin.Typography.Body
            color: Lumi.textSecondary
        }
    }

    // ------------------------------------------------------------ 跑动 / 暂停
    Item {
        id: countdownLayer
        anchors.fill: parent
        visible: opacity > 0
        opacity: host ? (host.countdownActive ? 1 : 0) : 0
        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        Item {
            anchors.centerIn: parent
            width: 300
            height: 300

            // L1：viewBox 300 / r 140 / stroke 6。ProgressRing 的半径是
            // (size − strokeWidth) / 2，286 才等于 140。
            Rin.ProgressRing {
                objectName: "timerL1Ring"
                anchors.centerIn: parent
                size: 286
                strokeWidth: 6
                from: 0
                to: host ? Math.max(1, host.tmTotal) : 1
                value: host ? host.tmRemaining : 0
                backgroundColor: Lumi.fade(Lumi.textSecondary, 0.18)
                primaryColor: Lumi.accent
            }

            Column {
                anchors.centerIn: parent
                spacing: 12

                Rin.Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: host ? host.fmtClock(host.tmRemaining) : ""
                    // 等宽数字：末两秒跳字时字宽不抖
                    font.features: ({ "tnum": 1 })
                    // RinUI 字阶无 64 档，显式给（L1 .time-display）
                    font.pixelSize: 64
                    font.weight: Font.Bold
                    color: Lumi.textPrimary
                }

                Rin.Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: host ? qsTr("共 %1 秒").arg(Math.round(host.tmTotal / 1000)) : ""
                    typography: Rin.Typography.Body
                    color: Lumi.textSecondary
                }

                // 快捷加时（L1 .add-time-btn：高 28 / 圆角 14 / 12px）
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 8
                    visible: host ? host.quickAdds.length > 0 : false

                    Repeater {
                        model: host ? host.quickAdds : []

                        delegate: Rin.Button {
                            id: addChip
                            required property var modelData

                            // 量宽用的隐形尺子（同 PluginFilterChip / IconButton
                            // 的做法）：Rin.Button 把 implicitWidth 写死成
                            //「内容宽 + 26」，chip 要的是 +20
                            Rin.Text {
                                id: chipProbe
                                visible: false
                                typography: Rin.Typography.Body
                                text: "+" + addChip.modelData.value
                                      + (addChip.modelData.unit === "minute"
                                         ? qsTr("分") : qsTr("秒"))
                            }

                            width: Math.ceil(chipProbe.implicitWidth) + 20
                            height: 28
                            radius: 14
                            padding: 0
                            topPadding: 0
                            bottomPadding: 0
                            leftPadding: 0
                            rightPadding: 0
                            text: chipProbe.text

                            onClicked: Backend.triggerAction(
                                "plugin:timer_l1:add:" + addChip.modelData.seconds)
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ 时间到
    Item {
        id: bellLayer
        anchors.fill: parent
        visible: opacity > 0
        opacity: host ? (host.tmState === "finished" ? 1 : 0) : 0
        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        // L1 .time-up-text 是 32/700；RinUI 字阶里 Title（28/DemiBold）是
        // 最近的一档，按 RinUI 规范走字阶而不是抄 32
        Rin.Text {
            anchors.centerIn: parent
            text: qsTr("时间到")
            typography: Rin.Typography.Title
            color: Lumi.textPrimary
        }
    }

    // ------------------------------------------------------------ 控制层
    TimerControlLayer {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
    }

    Component.onCompleted: {
        // 起跑前的输入值存在宿主窗口上（关窗再开不丢），这里负责把轮盘对齐它
        if (!host)
            return
        hourWheel.setIndex(host.pickH)
        minuteWheel.setIndex(host.pickM)
        secondWheel.setIndex(host.pickS)
        targetHourWheel.setIndex(host.targetH)
        targetMinuteWheel.setIndex(host.targetM)
    }
}
