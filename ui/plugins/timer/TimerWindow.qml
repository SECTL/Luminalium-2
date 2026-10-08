import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    计时器插件窗口（倒计时 / 正计时 / 时钟三页）。

    2026-10-06 计时器插件（用户指令「做一个计时器[包含倒计时、正计时、
    时钟等功能]」，功能语义参考 Lmn-copy 的 plugins/builtins/timer，
    本仓库按「没有网页前端」的规矩用 RinUI 原生重写）。

    ⚠️ **本窗口只是显示层**：倒计时 / 正计时的引擎、铃声、秒滴全在
    ``app/plugins/timer/plugin.py`` 的 Python 引擎里（窗口只藏不销毁，
    但用户会关掉窗口继续讲课 —— 表必须藏在窗口背后继续走）。Python 每
    100ms 把状态写进根属性（``mode`` / ``cdRemaining`` / ``swMs`` ……，
    值变才写），本文件全部绑定只读这些属性，**不在这里存任何引擎状态**；
    圆环重绘也挂在根属性的变化回调上（``onCdRemainingChanged`` 等）。

    交互通道：本窗口 → Python 只有 ``Backend.triggerAction("plugin:timer:…")``
    一条路，时长等参数编在动作后缀里（``plugin:timer:start:300000``），
    由插件的动作处理器解析。别给本窗口发明第二条反向通道（专用槽 /
    context property 都是插件约定明令不走的）。

    关窗路径照插件窗口标准：``onClosing`` 拦掉默认关闭转动作通道
    （窗口只藏不销毁，倒计时继续）。禁止 ``Qt.FramelessWindowHint``。

    倒计时的「就绪态」判据是 ``cdRemaining >= cdTotal``（引擎重置后两者
    相等；跑动 / 暂停时剩余小于总长）—— 刻意不另设状态位，少一处两边
    对不上的可能。

    2026-10-08 交互三连改（builtin-plugins-ux 计划 todo 2，GAP-4/6）：

    * **预设按钮 = 一键开始**，不再只填自选框。课堂高频操作要一步到位，
      点「5 分」直接 ``plugin:timer:start:300000`` 开跑；三个 SpinBox
      退位给「自定义时长」这一条路（配「开始」按钮）。
    * **走完态也显示「加时 1 分钟」**：引擎 ``add:`` 分支本就支持把走完
      的倒计时复活（``_cd_finished`` 翻回 False、剩余 += 加时），UI 之前
      用 ``visible: !cdFinished`` 把这条退路雪藏了，现在放开并换文案。
    * **就绪态回填**：四个状态属性的变化回调里把引擎的 ``cdTotal`` 分解
      回填三个自选框，只兜「停止后框与引擎脱节」；SpinBox 是手动编辑、
      不绑 cdTotal，回填只在就绪态做，不会打断用户正在输入的自定义
      时长。（只挂 ``onCdTotalChanged`` 会撞上推送顺序拿到陈旧剩余量，
      见下面 onCdRemainingChanged 一段的注释。）

    2026-10-08 标题带状态（builtin-plugins-ux 计划 todo 10，GAP-9）：
    倒计时跑动时窗口标题实时显示剩余时间（「计时器 · 剩 4:37」），走完
    变「计时器 · 时间到」—— 用户眼睛在别处（放映画面、另一个窗口）时，
    任务栏 / 标题栏就是唯一的进度来源。引擎 100ms 一推，但标题文本走
    ``fmtCountdown``（ceil 到秒），格式化结果每秒才变一次，不闪烁。
    绑定只读倒计时三态（``cdRunning`` / ``cdFinished`` / ``cdRemaining``），
    正计时跑动（``swRunning``）与时钟页不动标题；暂停也算「否则」，
    回到静态「计时器」。窗口 chrome 由 RinUI 接管，改 ``title`` 属性
    不涉及任何窗口 flag，安全。

    2026-10-08 隐藏常驻导航栏：本窗口无导航项，``Component.onCompleted``
    里把 ``navigationView.navigationBar.visible`` 置 false，空 rail 与
    ≡ 折叠按钮不再出现，内容区自动铺满（理由见该处注释）。
*/
Rin.FluentWindow {
    id: timerWindow

    // 标题随倒计时状态走（理由见头注释 2026-10-08 条目）：跑动带剩余
    // 时间、走完报「时间到」，其余态（就绪 / 暂停 / 正计时 / 时钟）静态
    title: cdRunning
           ? qsTr("计时器 · 剩 %1").arg(fmtCountdown(cdRemaining))
           : (cdFinished ? qsTr("计时器 · 时间到") : qsTr("计时器"))
    visible: false
    width: 460
    height: 640
    // 420 = 六个预设按钮（6×54 + 5×8 = 364）+ 页边距 40 的下限；
    // 再窄预设行会两端出界（RowLayout 居中裁切，2026-10-07 巡检补的地面）
    minimumWidth: 420
    minimumHeight: 560

    onClosing: function (event) {
        event.accepted = false
        Backend.triggerAction("plugin:timer:close")
    }

    // ------------------------------------------------ 引擎推送进来的状态
    // 只读。Python 侧 _push_state() 按值变化逐个写这些属性。
    property string mode: "countdown"
    property int cdTotal: 0
    property int cdRemaining: 0
    property bool cdRunning: false
    property bool cdFinished: false
    property int swMs: 0
    property bool swRunning: false

    // 回填挂在全部四个状态属性上而不是只挂 cdTotal：_push_state 按
    // mode→cdTotal→cdRemaining→cdRunning→cdFinished 的顺序逐个写，只挂
    // cdTotal 会在「剩余量还是上一拍的旧值」时判定，错过或误判就绪态
    // （2026-10-08 证据脚本实锤：9 分钟就绪态回填出了 0:00:01）。守卫
    // 会挡住中间态的误写，最后一拍写入时四个属性全是新值，必然收敛。
    onCdRemainingChanged: {
        ring.requestPaint()
        backfillBoxes()
    }
    onCdTotalChanged: {
        ring.requestPaint()
        backfillBoxes()
    }
    onCdRunningChanged: backfillBoxes()
    onCdFinishedChanged: {
        ring.requestPaint()
        backfillBoxes()
    }

    /*! 就绪态把引擎的 cdTotal 分解回填进三个自选框。
        只在就绪态动手：SpinBox 靠手动编辑（编辑不产生 cdTotal 变化），
        跑动 / 暂停 / 走完时绝不能动框 —— 那是用户可能正在输入的自定义
        时长。cdTotal 为 0（窗口刚建、引擎首推未到）时跳过，免得把
        minutesBox 的默认值 5 抹掉。 */
    function backfillBoxes() {
        if (timerWindow.cdTotal <= 0) return
        if (timerWindow.cdRunning || timerWindow.cdFinished
                || timerWindow.cdRemaining < timerWindow.cdTotal) return
        var total = Math.floor(timerWindow.cdTotal / 1000)
        hoursBox.value = Math.floor(total / 3600)
        minutesBox.value = Math.floor((total % 3600) / 60)
        secondsBox.value = total % 60
    }

    /*! 毫秒 → H:MM:SS（倒计时用 ceil：起跑显示 5:00、临终点到 0:00）。 */
    function fmtCountdown(ms) {
        var total = Math.max(0, Math.ceil(ms / 1000))
        var h = Math.floor(total / 3600)
        var m = Math.floor((total % 3600) / 60)
        var s = total % 60
        var mm = (m < 10 ? "0" : "") + m
        var ss = (s < 10 ? "0" : "") + s
        if (h > 0) return h + ":" + mm + ":" + ss
        return m + ":" + ss
    }

    /*! 毫秒 → H:MM:SS.cc（正计时用 floor + 百分秒，秒表的样子）。 */
    function fmtStopwatch(ms) {
        var total = Math.max(0, Math.floor(ms))
        var h = Math.floor(total / 3600000)
        var m = Math.floor((total % 3600000) / 60000)
        var s = Math.floor((total % 60000) / 1000)
        var cs = Math.floor((total % 1000) / 10)
        var mm = (m < 10 ? "0" : "") + m
        var ss = (s < 10 ? "0" : "") + s
        var cc = (cs < 10 ? "0" : "") + cs
        if (h > 0) return h + ":" + mm + ":" + ss + "." + cc
        return m + ":" + ss + "." + cc
    }

    Component.onCompleted: {
        // 窗口是懒创建的，建出来这一刻向引擎要一次全量状态。⚠️ 这一步此刻
        // 其实是空操作：onCompleted 触发时句柄还没挂上窗口（_create 未返回），
        // Python 侧 _push_state 会早退 —— 真正兜底的是 toggle/open 动作里
        // show() 之后的那次推送（见 plugin.py）；这里留着作双保险。
        // 双保险之外再补一次就绪态回填（理由见 backfillBoxes 注释）
        backfillBoxes()
        Backend.triggerAction("plugin:timer:sync")

        // FluentWindow 常驻一条 NavigationBar（左侧 rail + ≡ 折叠按钮），
        // 本窗口没有任何导航项，空 rail 和 ≡ 是纯干扰。NavigationBar 在
        // NavigationView 的 RowLayout 里，不可见即被布局跳过，内容区自动
        // 铺满；标题在 titleBarLeadingHost 里，不受影响。藏它而不改 RinUI
        // 包（AGENTS.md 铁律：site-packages 不许动）。
        navigationView.navigationBar.visible = false
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        // -------------------------------------------- 模式切换（Segmented）
        // currentIndex 与引擎推送的 mode 双向对齐：点它发动作，引擎回推新值；
        // 点击会打断绑定，onCurrentIndexChanged 里重装（老坑，见 AGENTS.md）。
        Rin.Segmented {
            id: modeBar
            objectName: "timerModeBar"

            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true

            currentIndex: {
                var modes = ["countdown", "stopwatch", "clock"]
                var i = modes.indexOf(timerWindow.mode)
                return i >= 0 ? i : 0
            }
            onCurrentIndexChanged: {
                var modes = ["countdown", "stopwatch", "clock"]
                var m = modes[currentIndex]
                if (m !== undefined && m !== timerWindow.mode) {
                    Backend.triggerAction("plugin:timer:mode:" + m)
                }
                currentIndex = Qt.binding(function () {
                    var modes = ["countdown", "stopwatch", "clock"]
                    var i = modes.indexOf(timerWindow.mode)
                    return i >= 0 ? i : 0
                })
            }

            Rin.SegmentedItem { text: qsTr("倒计时") }
            Rin.SegmentedItem { text: qsTr("正计时") }
            Rin.SegmentedItem { text: qsTr("时钟") }
        }

        // ================================================ 倒计时页
        ColumnLayout {
            visible: timerWindow.mode === "countdown"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            Item {
                // 圆环 + 中央剩余时间
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 250
                Layout.preferredHeight: 250

                Canvas {
                    id: ring
                    anchors.fill: parent
                    antialiasing: true

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        var cx = width / 2
                        var cy = height / 2
                        var lineWidth = 10
                        var r = Math.min(cx, cy) - lineWidth
                        ctx.lineWidth = lineWidth
                        ctx.lineCap = "round"
                        // 底环
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, Math.PI * 2)
                        ctx.strokeStyle = Qt.rgba(
                            Lumi.textSecondary.r, Lumi.textSecondary.g,
                            Lumi.textSecondary.b, 0.18).toString()
                        ctx.stroke()
                        // 进度环：按「剩余 / 总长」画（顺时针，从正上方起）
                        var fraction = timerWindow.cdTotal > 0
                                       ? timerWindow.cdRemaining / timerWindow.cdTotal : 0
                        fraction = Math.max(0, Math.min(1, fraction))
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, -Math.PI / 2,
                                -Math.PI / 2 + Math.PI * 2 * fraction)
                        ctx.strokeStyle = timerWindow.cdFinished
                                          ? "#E03E3E" : String(Lumi.accent)
                        ctx.stroke()
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 2

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: timerWindow.fmtCountdown(timerWindow.cdRemaining)
                        font.pixelSize: 42
                        font.family: "Consolas"
                        color: timerWindow.cdFinished ? "#E03E3E" : Lumi.textPrimary
                    }
                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: timerWindow.cdFinished
                        text: qsTr("时间到")
                        font.pixelSize: 14
                        color: "#E03E3E"
                    }
                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: !timerWindow.cdFinished && timerWindow.cdTotal > 0
                                 && !timerWindow.cdRunning
                                 && timerWindow.cdRemaining < timerWindow.cdTotal
                        text: qsTr("已暂停")
                        font.pixelSize: 14
                        color: Lumi.textSecondary
                    }
                }
            }

            // ---- 就绪态：自选时长 + 预设 + 开始
            ColumnLayout {
                visible: !timerWindow.cdRunning && !timerWindow.cdFinished
                         && timerWindow.cdRemaining >= timerWindow.cdTotal
                Layout.fillWidth: true
                spacing: 12

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10

                    ColumnLayout {
                        spacing: 4
                        Rin.SpinBox {
                            id: hoursBox
                            from: 0; to: 23; editable: true
                            Layout.preferredWidth: 92
                        }
                        Rin.Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("时")
                            color: Lumi.textSecondary
                            font.pixelSize: 12
                        }
                    }
                    ColumnLayout {
                        spacing: 4
                        Rin.SpinBox {
                            id: minutesBox
                            from: 0; to: 59; editable: true
                            value: 5
                            Layout.preferredWidth: 92
                        }
                        Rin.Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("分")
                            color: Lumi.textSecondary
                            font.pixelSize: 12
                        }
                    }
                    ColumnLayout {
                        spacing: 4
                        Rin.SpinBox {
                            id: secondsBox
                            from: 0; to: 59; editable: true
                            Layout.preferredWidth: 92
                        }
                        Rin.Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: qsTr("秒")
                            color: Lumi.textSecondary
                            font.pixelSize: 12
                        }
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 8

                    Repeater {
                        model: [1, 3, 5, 10, 15, 30]

                        delegate: Rin.Button {
                            required property int modelData
                            Layout.preferredWidth: 54
                            text: modelData + qsTr(" 分")
                            onClicked: {
                                // 预设 = 一键开始（时长编在动作后缀里，毫秒）；
                                // 自定义时长走上面的 SpinBox +「开始」按钮
                                Backend.triggerAction(
                                    "plugin:timer:start:" + modelData * 60000)
                            }
                        }
                    }
                }

                Rin.Button {
                    objectName: "timerStartButton"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 160
                    text: qsTr("开始")
                    highlighted: true
                    primaryColor: Lumi.accent
                    onClicked: {
                        var ms = hoursBox.value * 3600000
                                 + minutesBox.value * 60000
                                 + secondsBox.value * 1000
                        if (ms <= 0) return
                        Backend.triggerAction("plugin:timer:start:" + ms)
                    }
                }
            }

            // ---- 跑动 / 暂停 / 走完态：控制按钮
            RowLayout {
                visible: timerWindow.cdRunning
                         || (timerWindow.cdRemaining < timerWindow.cdTotal
                             && !timerWindow.cdFinished)
                         || timerWindow.cdFinished
                Layout.alignment: Qt.AlignHCenter
                spacing: 10

                Rin.Button {
                    objectName: "timerPauseResumeButton"
                    visible: !timerWindow.cdFinished
                             && timerWindow.cdRemaining > 0
                    text: timerWindow.cdRunning ? qsTr("暂停") : qsTr("继续")
                    Layout.preferredWidth: 104
                    onClicked: Backend.triggerAction(
                        timerWindow.cdRunning ? "plugin:timer:pause"
                                              : "plugin:timer:resume")
                }
                Rin.Button {
                    objectName: "timerAddOneMinute"
                    // 走完态也显示：引擎 add: 本就支持复活走完的倒计时
                    // （plugin.py 里 finished 翻回 False、剩余 += 加时），
                    // 走完换文案，把这条退路从 UI 雪藏里放出来
                    text: timerWindow.cdFinished ? qsTr("加时 1 分钟")
                                                 : qsTr("+1 分钟")
                    Layout.preferredWidth: 104
                    onClicked: Backend.triggerAction("plugin:timer:add:60000")
                }
                Rin.Button {
                    objectName: "timerResetButton"
                    text: timerWindow.cdFinished ? qsTr("知道了") : qsTr("停止")
                    Layout.preferredWidth: 104
                    highlighted: true
                    primaryColor: Lumi.accent
                    onClicked: Backend.triggerAction("plugin:timer:reset")
                }
            }
        }

        // ================================================ 正计时页
        ColumnLayout {
            visible: timerWindow.mode === "stopwatch"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Column {
                    anchors.centerIn: parent
                    spacing: 6

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: timerWindow.fmtStopwatch(timerWindow.swMs)
                        font.pixelSize: 46
                        font.family: "Consolas"
                        color: Lumi.textPrimary
                    }
                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: timerWindow.swRunning ? qsTr("计时中") : qsTr("已停止")
                        font.pixelSize: 13
                        color: Lumi.textSecondary
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 10

                Rin.Button {
                    objectName: "stopwatchToggle"
                    Layout.preferredWidth: 130
                    text: timerWindow.swRunning ? qsTr("暂停") : qsTr("开始")
                    highlighted: true
                    primaryColor: Lumi.accent
                    onClicked: Backend.triggerAction(
                        timerWindow.swRunning ? "plugin:timer:sw-pause"
                                              : "plugin:timer:sw-start")
                }
                Rin.Button {
                    objectName: "stopwatchReset"
                    Layout.preferredWidth: 130
                    text: qsTr("重置")
                    onClicked: Backend.triggerAction("plugin:timer:sw-reset")
                }
            }
        }

        // ================================================ 时钟页
        ColumnLayout {
            id: clockPage
            visible: timerWindow.mode === "clock"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            property string nowText: ""
            property string dateText: ""

            Timer {
                interval: 250
                running: timerWindow.mode === "clock" && timerWindow.visible
                repeat: true
                triggeredOnStart: true
                onTriggered: {
                    var now = new Date()
                    clockPage.nowText = Qt.formatTime(now, "HH:mm:ss")
                    clockPage.dateText = Qt.formatDate(now, "yyyy/MM/dd dddd")
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Column {
                    anchors.centerIn: parent
                    spacing: 8

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: clockPage.nowText
                        font.pixelSize: 46
                        font.family: "Consolas"
                        color: Lumi.textPrimary
                    }
                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: clockPage.dateText
                        font.pixelSize: 16
                        color: Lumi.textSecondary
                    }
                }
            }
        }
    }
}
