import QtQuick
import QtQuick.Controls.Basic
import RinUI as Rin
import Luminalium

/*!
    计时器（Luminalium 1）插件窗口（侧边栏版）。

    2026-10-17 用户指令链：先移植 L1 的计时器并保留原有排版 → 版式换成
    ``Rin.FluentWindowBase`` 自绘侧栏（同编辑器那一款，无导航栏）→ 最后改成
    **RinUI 的侧边栏**：窗口回到 ``Rin.FluentWindow``，三页交给
    ``NavigationView`` 管，内容就是刚做的三个页面（秒表 / 计时 / 时钟，在
    ``pages/`` 下）。

    两版侧栏的差别（为什么值得换）：自绘那版什么都得自己摆（图标、悬停填充、
    选中色、切页淡入），且窗口标题与页面标题各有一份；NavigationView 这套是
    RinUI 的原生导航 —— ☰ 折叠 / 展开、当前项高亮、页面栈与入场动画、标题都
    由它负责，本文件只剩「状态 + 同步」。

    2026-10-17 第二轮（用户指令「用 RinUI 组件和 RinUI 规范逐个替换组件，
    做到排版一致、语言革新」）：窗口里所有自绘控件也全部换成 RinUI 自家的
    （``Rin.ToolButton`` / ``Rin.Button`` / ``Rin.Text`` / ``Rin.Segmented``
    / ``Rin.ToolSeparator`` / ``Rin.ProgressRing``）。**版式与尺寸一律不动**
    （仍照 L1 的骨架），换的只是「用什么组件画」：悬停 / 按压 / 禁用三态、
    颜色过渡、字阶全部交给 RinUI 主题。逐项对照表见 ``pages/TimerPage.qml``
    与 ``TimerControlLayer.qml`` 的头注释。

    尺寸仍照 L1 的骨架：外留白 12 / 卡片圆角 16 / 页区 top 80 bottom 100
    左右 32 / 滚轮行高 80 字号 56 / 圆环 300（r140 描边 6）/ 剩余时间 64 /
    控制层 gap 32 / 侧钮 44 / 主钮 72 / 长按环 92 / 秒表与时钟 120。

    ⚠️ **本窗口只是状态层 + 窗口层**：引擎在 ``app/plugins/timer_l1/plugin.py``
    （窗口只藏不销毁，但用户会关掉窗口继续讲课 —— 表必须藏在窗口背后继续走）。
    Python 每 33ms 把状态写进根属性（``page`` / ``tmState`` / ``tmRemaining`` /
    ``swMs`` ……，值变才写）。页面（``pages/*.qml``）通过 ``Window.window`` 读这
    些属性 —— 页面会被塞进 Loader 宿主，裸 ``window`` 标识符靠不住，
    ``AGENTS.md`` 有这条。

    ⚠️ **侧栏与引擎状态的双向同步**在这里做（唯一的环风险点）：
    * 引擎推 ``page`` → ``onPageChanged`` 里 ``navigationView.push(url)``；
    * 用户点侧栏 → ``currentPageChanged`` 里发 ``page:<key>`` 动作。
    两边都只在「真的不一样」时才动，所以不会互相顶。

    交互通道：页面 / 本窗口 → Python 只有 ``Backend.triggerAction("plugin:timer_l1:…")``
    一条路。关窗路径照插件窗口标准（``onClosing`` 拦掉默认关闭，只藏不销毁），
    禁止 ``Qt.FramelessWindowHint``。

    未搬（见 ``MEMORY-qml-pitfalls`` / 每日记录）：时钟页农历干支、迷你模式的
    三档宽度自适应、页面切换的 blur 过渡。
*/
Rin.FluentWindow {
    id: win

    title: qsTr("计时器（Luminalium 1）")
    visible: false
    // 标题交给左侧导航栏那一份（与设置窗口同一取舍），自绘标题栏里再画一次
    // 窗口标题会出现两遍
    titleEnabled: false
    // L1 按屏幕算出来的窗口约 1022×650，这里取整用等价默认值
    width: 1020
    height: 650
    minimumWidth: miniMode ? 300 : 880
    minimumHeight: miniMode ? 340 : 560
    // 低于 640 才把侧栏收成图标条（沿用设置窗口那档），否则默认最小宽 880
    // 一缩就折叠
    navigationView.navMinimumExpandWidth: 640

    onClosing: function (event) {
        event.accepted = false
        Backend.triggerAction("plugin:timer_l1:close")
    }

    // ================================================================ 引擎状态（只读）
    property string page: "stopwatch"        // stopwatch | timer | clock
    property string tmState: "picker"        // picker | running | paused | finished
    property int tmTotal: 300000             // ms
    property int tmRemaining: 300000         // ms
    property int swMs: 0
    property bool swRunning: false
    property var quickAdds: []

    // ================================================================ 窗口本地状态
    /*! 计时页第二个 tab（到点）。 */
    property bool targetTab: false
    /*! 全屏倒计时层是否显示。 */
    property bool countdownFullscreen: false
    /*! 迷你模式（L1 的浮动小窗）。 */
    property bool miniMode: false

    property real normalWidth: 1020
    property real normalHeight: 650

    // 起跑前的输入值（滚盘当前值；跟着窗口活着，关窗再开不丢）
    property int pickH: 0
    property int pickM: 5                    // L1 默认 00:05:00
    property int pickS: 0
    property int targetH: 0
    property int targetM: 0

    /*! 倒计时正在跑 / 暂停 —— 侧钮浮不浮现看它。 */
    readonly property bool countdownActive:
        page === "timer" && (tmState === "running" || tmState === "paused")

    readonly property var presetSeconds: [60, 900, 1800, 2400, 2700, 3600, 5400, 7200]

    // 三个页面（NavigationView 按 URL 加载）
    readonly property url pageStopwatch: Qt.resolvedUrl("pages/StopwatchPage.qml")
    readonly property url pageTimer: Qt.resolvedUrl("pages/TimerPage.qml")
    readonly property url pageClock: Qt.resolvedUrl("pages/ClockPage.qml")

    // 侧栏条目。顺序照 L1 的 sidebar：计时 / 秒表 / 时钟
    navigationItems: [
        // Fluent 图标集里没有 stopwatch 字形，timer_2 是最接近的一支
        { title: qsTr("计时"), page: win.pageTimer, icon: "ic_fluent_timer_20_regular" },
        { title: qsTr("秒表"), page: win.pageStopwatch, icon: "ic_fluent_timer_2_20_regular" },
        { title: qsTr("时钟"), page: win.pageClock, icon: "ic_fluent_clock_20_regular" }
    ]

    // 初始页交给 ``defaultPage``：NavigationView 自己初始化时会推它，栈深度
    // 与我们的外部推送一致，不会撞车。
    //
    // ⚠️ 2026-10-17 踩过的两种错法都记在这里，别再改回去：
    // ① 不设 ``defaultPage`` → RinUI 改推 ``navigationItems[0]``（计时页），
    //    与引擎默认页（秒表）不一致；
    // ② 在 ``Component.onCompleted`` 里再主动 ``push`` 一次 → 那一推落在
    //    RinUI 首推之后、把栈加深，随后它的栈清理又把页面弹回去（症状：seed
    //    灌了 ``page=timer``，抓图却停在秒表页，且 600ms 后才翻）。
    defaultPage: urlForPage(page)

    Component.onCompleted: {
        // 懒创建：建出来这一刻向引擎要一次全量状态。⚠️ 此刻通常还是空操作
        // （onCompleted 触发时句柄还没挂上窗口），兜底是 toggle/open 里 show()
        // 之后的那次推送 —— 留着作双保险。
        Backend.triggerAction("plugin:timer_l1:sync")
    }

    // 倒计时走完：退全屏、退迷你（L1 finishCountdown 就是这两件）
    onTmStateChanged: {
        if (tmState !== "finished")
            return
        if (countdownFullscreen)
            setCountdownFullscreen(false)
        if (miniMode)
            setMiniMode(false)
    }

    // ================================================================ 侧栏 ↔ 引擎

    /*! 当前 ``page`` → NavigationView 的页面 URL。 */
    function urlForPage(key) {
        if (key === "timer")
            return win.pageTimer
        if (key === "clock")
            return win.pageClock
        return win.pageStopwatch
    }

    /*! 引擎换了页 → 让 NavigationView 跟着切（真的不一样才推）。 */
    function syncNavigation() {
        var target = urlForPage(win.page)
        if (String(navigationView.currentPage) !== String(target))
            navigationView.push(target)
    }

    onPageChanged: syncNavigation()

    /*! 用户点了侧栏 → 告诉引擎。 */
    Connections {
        target: navigationView

        function onCurrentPageChanged() {
            var current = String(navigationView.currentPage)
            var key = current === String(win.pageTimer) ? "timer"
                    : current === String(win.pageClock) ? "clock"
                    : "stopwatch"
            if (key !== win.page)
                Backend.triggerAction("plugin:timer_l1:page:" + key)
        }
    }

    // ================================================================ 格式化

    /*! ms → MM:SS（L1 常态版式；分钟不折进小时，90 分钟就是 90:00）。 */
    function fmtClock(ms) {
        var total = Math.max(0, Math.ceil(ms / 1000))
        var m = Math.floor(total / 60)
        var s = total % 60
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }

    /*! ms → H:MM:SS（L1 全屏版式）。 */
    function fmtFull(ms) {
        var total = Math.max(0, Math.ceil(ms / 1000))
        var h = Math.floor(total / 3600)
        var m = Math.floor((total % 3600) / 60)
        var s = total % 60
        return h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }

    /*! ms → MM:SS.cc（秒表，百分秒）。 */
    function fmtStopwatch(ms) {
        var total = Math.max(0, Math.floor(ms))
        var m = Math.floor(total / 60000)
        var s = Math.floor((total % 60000) / 1000)
        var cs = Math.floor((total % 1000) / 10)
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
                + "." + (cs < 10 ? "0" : "") + cs
    }

    /*! 秒 → HH:MM:SS（预设按钮标签，L1 的 formatPresetLabel）。 */
    function fmtPreset(sec) {
        var h = Math.floor(sec / 3600)
        var m = Math.floor((sec % 3600) / 60)
        var s = sec % 60
        return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m
                + ":" + (s < 10 ? "0" : "") + s
    }

    /*! 秒 → 「1小时 5分 0秒」（到点页提示，L1 的 formatDurationText）。 */
    function fmtDuration(sec) {
        var h = Math.floor(sec / 3600)
        var m = Math.floor((sec % 3600) / 60)
        var s = sec % 60
        if (h > 0) return h + qsTr("小时") + " " + m + qsTr("分") + " " + s + qsTr("秒")
        if (m > 0) return m + qsTr("分") + " " + s + qsTr("秒")
        return s + qsTr("秒")
    }

    /*! 到点 tab 的目标时刻 → 剩余秒数。已过则算明天（L1 同款）。 */
    function targetSeconds() {
        var now = new Date()
        var target = new Date()
        target.setHours(targetH, targetM, 0, 0)
        if (target <= now)
            target.setDate(target.getDate() + 1)
        return Math.max(1, Math.ceil((target - now) / 1000))
    }

    function durationSeconds() {
        return pickH * 3600 + pickM * 60 + pickS
    }

    function startCountdown() {
        var seconds = targetTab ? targetSeconds() : durationSeconds()
        if (seconds <= 0)
            return
        Backend.triggerAction("plugin:timer_l1:start:" + seconds)
    }

    /*! 主按钮这一刻该干什么（L1 mainBtn click 的分支）。 */
    function mainAction() {
        if (page === "stopwatch") {
            Backend.triggerAction("plugin:timer_l1:sw-toggle")
            return
        }
        if (page !== "timer")
            return
        if (tmState === "picker")
            startCountdown()
        else if (tmState === "running")
            Backend.triggerAction("plugin:timer_l1:pause")
        else if (tmState === "paused")
            Backend.triggerAction("plugin:timer_l1:resume")
        else if (tmState === "finished")
            Backend.triggerAction("plugin:timer_l1:reset")
    }

    /*! 长按（2 秒）能重置吗 —— L1 只允许「暂停中的计时」与「动过的秒表」。 */
    function canLongPressReset() {
        if (page === "timer")
            return tmState === "paused"
        if (page === "stopwatch")
            return swRunning || swMs > 0
        return false
    }

    function longPressReset() {
        if (page === "timer")
            Backend.triggerAction("plugin:timer_l1:reset")
        else if (page === "stopwatch")
            Backend.triggerAction("plugin:timer_l1:sw-reset")
    }

    /*! 全屏 / 最大化：按 L1 的「计时器全屏行为」设置项走（fullscreen | maximize）。 */
    function setCountdownFullscreen(on) {
        countdownFullscreen = on
        if (on) {
            if (Backend.settings.plugins_timer_l1_fullscreen_behavior === "maximize")
                win.showMaximized()
            else
                win.showFullScreen()
        } else {
            win.showNormal()
        }
    }

    /*! 迷你模式：存下原尺寸再缩到 L1 的 320×380；退出时还原。 */
    function setMiniMode(on) {
        if (on === miniMode)
            return
        if (on) {
            normalWidth = win.width
            normalHeight = win.height
            miniMode = true
            win.width = 320
            win.height = 380
        } else {
            win.width = normalWidth
            win.height = normalHeight
            miniMode = false
        }
    }

    // ================================================================ 迷你模式
    // L1 body.mini-mode：窗口 320×380，只剩圆环（186）+ 时间（42）+ 单位行 +
    // 快捷加时 + 播放 / 回满两颗 42 圆钮。标题栏用 RinUI 原生那一条（窗口边框 /
    // 阴影 / 圆角全归它管），不在窗口里再自绘一条迷你标题栏。
    // ⚠️ 必须是**不透明**的底色：侧边栏版的窗口里 NavigationView 与当前页
    // 都还在背后，透明的盖片会让它们透上来（2026-10-17 实测：迷你窗里看到两重
    // 圆环和两份 02:22）。底色取 ``navPageBg``（页面实际底色）而不是 surfaceBg
    // —— 两者差一档，迷你窗会与主窗口的页面底色不一致。
    Rectangle {
        id: miniLayout
        anchors.fill: parent
        visible: win.miniMode
        color: Lumi.navPageBg

        // 回到常规窗口（L1 迷你标题栏上那枚「恢复窗口」）
        Rin.ToolButton {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: 10
            anchors.topMargin: 8
            width: 24
            height: 24
            radius: 6
            flat: true
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0

            icon.name: "ic_fluent_arrow_maximize_20_regular"
            size: 14
            color: Lumi.textSecondary

            onClicked: win.setMiniMode(false)
        }

        Column {
            anchors.centerIn: parent
            spacing: 10

            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 186
                height: 186

                // L1 mini：圆环 186、描边加粗、半径 ≈ 83
                Rin.ProgressRing {
                    anchors.centerIn: parent
                    size: 176
                    strokeWidth: 10
                    from: 0
                    to: Math.max(1, win.tmTotal)
                    value: win.tmRemaining
                    backgroundColor: Lumi.fade(Lumi.textSecondary, 0.18)
                    primaryColor: Lumi.accent
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 2

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: win.fmtClock(win.tmRemaining)
                        font.features: ({ "tnum": 1 })
                        font.pixelSize: 42
                        font.weight: Font.Bold
                        color: Lumi.textPrimary
                    }
                    // L1 mini-unit：「总计 N 分钟」
                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: win.tmTotal > 0
                        text: qsTr("总计 %1 分钟").arg(Math.ceil(win.tmTotal / 60000))
                        typography: Rin.Typography.Body
                        color: Lumi.textSecondary
                    }
                }
            }

            // 快捷加时（L1 mini 里更小一号：高 24 / 11px）
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 6
                visible: win.quickAdds.length > 0

                Repeater {
                    model: win.quickAdds

                    delegate: Rin.Button {
                        id: miniChip
                        required property var modelData

                        // 量宽用的隐形尺子（同 TimerPage 的加时 chip）：
                        // Rin.Button 的 implicitWidth 写死成「内容宽 + 26」，
                        // mini chip 要的是 +16
                        Rin.Text {
                            id: miniChipProbe
                            visible: false
                            typography: Rin.Typography.Body
                            text: "+" + miniChip.modelData.value
                                  + (miniChip.modelData.unit === "minute"
                                     ? qsTr("分") : qsTr("秒"))
                        }

                        width: Math.ceil(miniChipProbe.implicitWidth) + 16
                        height: 24
                        radius: 12
                        padding: 0
                        topPadding: 0
                        bottomPadding: 0
                        leftPadding: 0
                        rightPadding: 0
                        text: miniChipProbe.text

                        onClicked: Backend.triggerAction(
                            "plugin:timer_l1:add:" + miniChip.modelData.seconds)
                    }
                }
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 14

                // 回满（L1 mini-btn-secondary）：回满并停在暂停，迷你窗口里
                // 没有轮盘可回，不能走主窗口那个 reset
                Rin.ToolButton {
                    width: 42
                    height: 42
                    radius: 21
                    padding: 0
                    topPadding: 0
                    bottomPadding: 0
                    leftPadding: 0
                    rightPadding: 0

                    icon.name: "ic_fluent_arrow_counterclockwise_20_regular"
                    size: 20
                    color: Lumi.textPrimary

                    onClicked: Backend.triggerAction("plugin:timer_l1:rewind")
                }

                // 播放 / 暂停（L1 mini-btn-primary）
                Rin.ToolButton {
                    width: 42
                    height: 42
                    radius: 21
                    padding: 0
                    topPadding: 0
                    bottomPadding: 0
                    leftPadding: 0
                    rightPadding: 0

                    icon.name: win.tmState === "running"
                                  ? "ic_fluent_pause_20_filled"
                                  : "ic_fluent_play_20_filled"
                    // 图标色走 ToolButton 的 color 别名（不是 icon.color，
                    // 那个被 IconWidget 自己的同名属性遮蔽，永远不生效）
                    color: Lumi.accent
                    size: 24

                    onClicked: Backend.triggerAction(
                        win.tmState === "running"
                            ? "plugin:timer_l1:pause"
                            : "plugin:timer_l1:resume")
                }
            }
        }
    }

    // ================================================================ 全屏倒计时
    // L1 .countdown-fullscreen：整窗黑底、只剩一串 15vw 的大字（末 5 秒转红），
    // 底部一枚「退出全屏」。侧栏 / 圆环 / 按钮全藏。
    Rectangle {
        id: fullscreenLayer
        anchors.fill: parent
        color: "#000000"
        visible: win.countdownFullscreen
        z: 100

        Rin.Text {
            anchors.centerIn: parent
            text: win.fmtFull(win.tmRemaining)
            font.features: ({ "tnum": 1 })
            // 15vw：跟着窗口宽走，RinUI 字阶里没有这一档
            font.pixelSize: win.width * 0.15
            font.weight: Font.DemiBold
            color: win.tmRemaining <= 5000 ? "#FF3B30" : "#FFFFFF"
        }

        Rin.Button {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 32
            text: qsTr("退出全屏")
            onClicked: win.setCountdownFullscreen(false)
        }
    }
}
