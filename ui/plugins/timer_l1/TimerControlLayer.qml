import QtQuick
import RinUI as Rin
import Luminalium

/*!
    底部控制层（L1 的 ``.control-layer``）：44 全屏钮 + 72 主钮（外框 92，带
    2 秒长按重置环）+ 44 迷你钮，间距 32，底部留 24。

    单独拆成组件是因为 L2 的侧边栏版窗口（``Rin.FluentWindow`` + NavigationView）
    把页面交给导航栈加载，**三页各带一份控制层**：导航栏本身负责切页，窗口级再挂
    一条会浮在侧栏内容之上、展开态还要跟侧栏宽度打架。放在页里则天然落在内容区
    底部 —— 与 L1 的 main-container 内定位等价。

    ⚠️ 状态不在这里存：全部读宿主窗口（``Window.window``，不是裸 ``window`` ——
    页面会被塞进 Loader 宿主，见 ``AGENTS.md``）。交互仍然只有一条出口：
    ``Backend.triggerAction("plugin:timer_l1:…")``。

    2026-10-17「RinUI 规范」替换：自绘的圆钮（``Rectangle`` + ``MouseArea`` +
    手搓 hover/press）全部换成 **``Rin.ToolButton``**，L1 的
    ``.side-btn`` / ``.play-btn`` 在 RinUI 里的对应物就是它：

    * 悬停 / 按下 / 禁用三态、颜色过渡、焦点指示全走 RinUI 基类，不再自己画；
    * 字形大小用 ``size``（ToolButton 的别名，指向 IconWidget.size）——
      ⚠️ 不是 ``icon.width``：``Rin.Button`` 默认 contentItem 里的 IconWidget
      只把 ``width/height`` 当盒子用，**字形大小由 ``size``（默认 16）决定**，
      调盒子不改字形（``ui/presentation/IconButton.qml`` 头注释里有同一段）；
    * 主钮的图标色 ``Lumi.accent``（L1 的 ``.play-btn`` 就是中性底 + 强调色
      图标），底子是 RinUI 的 ``controlColor`` 填充 —— L1 的 ``--bg-surface``
      + 分隔线描边在 Fluent 语言里就是这一档；
    * 四边 padding **逐个清零**：基类写的是 ``padding: 6`` + ``topPadding: 5``
      + ``bottomPadding: 7``，只写 ``padding: 0`` 盖不住后两个（Qt 里它们是
      独立属性），contentItem 会被挤成 40×32、图标偏 1px；
    * 长按不再挂 ``MouseArea``：直接用 Button 原生的
      ``onPressed`` / ``onReleased`` / ``onClicked``（长按触发过的那次点击
      要吃掉，与 L1 同款）。进度环仍是 ``Canvas`` —— RinUI 没有「绕按钮一圈」
      的进度组件，且它得画在按钮**之上**（声明顺序即图层顺序）。
*/
Item {
    id: controlLayer
    objectName: "timerL1ControlLayer"

    implicitWidth: 420
    implicitHeight: 92

    //: 宿主窗口（``TimerWindow.qml`` 的根）；引擎状态与动作入口都在它身上
    readonly property var host: Window.window

    // 时钟页没有控制层（L1 把 mainBtn 整只隐藏，侧钮也只在倒计时激活时浮现）
    readonly property bool active: host ? host.page !== "clock" : false
    readonly property bool countdownActive: host ? host.countdownActive : false

    visible: active

    Row {
        anchors.centerIn: parent
        spacing: 32

        // 全屏（只在倒计时激活时浮现；不显示也占位，主钮才居中）
        Rin.ToolButton {
            width: 44
            height: 44
            radius: 22
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0

            // ⚠️ 隐藏靠 opacity 而不是 enabled：Rin.Button 的 disabled 状态里
            // 有一条 PropertyChanges { opacity: 0.65 }，会**盖掉**绑定把按钮
            // 按 65% 亮度留在屏幕上（2026-10-17 实测：起跑前 / 时间到两态
            // 侧钮隐约可见）。也不能用 visible: false —— Row 会跳过不可见子项，
            // 主钮就不再居中。所以按钮恒 enabled，点击处设防。
            opacity: controlLayer.countdownActive ? 1 : 0
            // 不另挂 Behavior on opacity：基类自带一条（appearanceSpeed）

            icon.name: "ic_fluent_full_screen_maximize_20_regular"
            size: 20
            color: Lumi.textPrimary

            onClicked: {
                if (!controlLayer.countdownActive)
                    return
                if (controlLayer.host)
                    controlLayer.host.setCountdownFullscreen(true)
            }
        }

        // 主按钮 + 长按环
        Item {
            id: mainButton
            width: 92
            height: 92
            anchors.verticalCenter: parent.verticalCenter

            property bool longPressing: false
            property bool longPressFired: false
            property real longPressProgress: 0
            property real longPressStart: 0

            Rin.ToolButton {
                anchors.centerIn: parent
                width: 72
                height: 72
                radius: 36
                padding: 0
                topPadding: 0
                bottomPadding: 0
                leftPadding: 0
                rightPadding: 0

                icon.name: {
                    var host = controlLayer.host
                    if (!host)
                        return "ic_fluent_play_20_filled"
                    if (host.page === "stopwatch")
                        return host.swRunning
                               ? "ic_fluent_pause_20_filled"
                               : "ic_fluent_play_20_filled"
                    if (host.tmState === "running")
                        return "ic_fluent_pause_20_filled"
                    if (host.tmState === "finished")
                        return "ic_fluent_arrow_counterclockwise_20_regular"
                    return "ic_fluent_play_20_filled"
                }
                // ⚠️ 图标色走 ToolButton 自己的 ``color`` 别名，**不是**
                // ``icon.color``：ToolButton 的 contentItem 里那句
                // ``icon.color ? …`` 解析到的是 IconWidget 自己的字符串属性
                // ``icon``（同名遮蔽），永远 falsy → 图标回落主题 textColor
                // （2026-10-17 实测：浅色主题下播放键是黑的）。
                color: Lumi.accent
                size: 28

                onPressed: {
                    mainButton.longPressFired = false
                    if (controlLayer.host && controlLayer.host.canLongPressReset())
                        mainButton.startLongPress()
                }
                onReleased: mainButton.stopLongPress()
                onCanceled: mainButton.stopLongPress()

                onClicked: {
                    // 长按已经触发过就别再当成一次点击（L1 同款）
                    if (mainButton.longPressFired) {
                        mainButton.longPressFired = false
                        return
                    }
                    if (controlLayer.host)
                        controlLayer.host.mainAction()
                }
            }

            // 长按进度环：画在按钮之上（后声明 = 上层）
            Canvas {
                id: longPressRing
                anchors.fill: parent
                visible: mainButton.longPressProgress > 0.001
                antialiasing: true

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    var cx = width / 2
                    var cy = height / 2
                    var r = cx - 3
                    ctx.lineWidth = 4
                    ctx.lineCap = "round"
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, -Math.PI / 2,
                            -Math.PI / 2
                            + Math.PI * 2 * mainButton.longPressProgress)
                    ctx.strokeStyle = String(Lumi.accent)
                    ctx.stroke()
                }

                Connections {
                    target: mainButton
                    function onLongPressProgressChanged() {
                        longPressRing.requestPaint()
                    }
                }
            }

            Timer {
                id: longPressTimer
                interval: 2000
                onTriggered: {
                    mainButton.longPressFired = true
                    if (controlLayer.host)
                        controlLayer.host.longPressReset()
                    mainButton.stopLongPress()
                }
            }

            Timer {
                id: longPressTicker
                interval: 30
                repeat: true
                onTriggered: {
                    mainButton.longPressProgress =
                        Math.min(1, (Date.now() - mainButton.longPressStart) / 2000)
                }
            }

            function startLongPress() {
                mainButton.longPressStart = Date.now()
                mainButton.longPressFired = false
                mainButton.longPressing = true
                mainButton.longPressProgress = 0.0001
                longPressTimer.start()
                longPressTicker.start()
            }

            function stopLongPress() {
                longPressTimer.stop()
                longPressTicker.stop()
                mainButton.longPressing = false
                mainButton.longPressProgress = 0
            }
        }

        // 迷你模式
        Rin.ToolButton {
            width: 44
            height: 44
            radius: 22
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0

            // 同全屏钮：隐藏靠 opacity，不禁用（disabled 状态会按 0.65 亮度
            // 把按钮留在屏幕上），点击处设防
            opacity: controlLayer.countdownActive ? 1 : 0

            icon.name: "ic_fluent_picture_in_picture_enter_20_regular"
            size: 20
            color: Lumi.textPrimary

            onClicked: {
                if (!controlLayer.countdownActive)
                    return
                if (controlLayer.host)
                    controlLayer.host.setMiniMode(true)
            }
        }
    }
}
