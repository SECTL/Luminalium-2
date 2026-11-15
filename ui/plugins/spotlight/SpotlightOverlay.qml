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
    * 2026-10-08：胶囊 ``pill`` 把自身几何（窗口局部逻辑坐标）经
      ``plugin:spotlight:pill-rect:<x>,<y>,<w>,<h>`` 上报给插件 ——
      光斑跟着光标走，光标一靠近胶囊，胶囊就掉进镂空里被 SetWindowRgn
      一起裁掉（✕ 按钮失联的上线实锤）；Python 塑形时把这个矩形
      RGN_OR 补回，任何光斑位置下胶囊都可见可点。开场提示（hint）
      **刻意不**保留 —— 它只是提示，被裁可接受。
    * 2026-10-08：hint 文案补上「光斑外点击被遮住」「+ / − 全局生效」——
      遮罩吃点击但没有任何说明时，用户把这堵看不见的点击墙当成
      「电脑卡死」（设置页滑条下限同日注释同源）。第一次开聚光灯就必须
      让人知道这两条，否则放映中超链接 / 触发器全灭且无从归因。
    * 2026-10-09：胶囊几何上报加第 5 参「圆角半径」—— 保留矩形补回
      原来用直角 ``CreateRectRgn``，光斑（圆洞）扫过圆角胶囊时，胶囊
      四个角外的遮罩被一并补回，用户看到「胶囊被灯照到时四角有遮罩」。
      Python 侧对带半径的保留矩形改用 ``CreateRoundRectRgn``（塑形在
      ``app/windows.py`` 的 ``_build_region_with_hole``）。

    浓度直读 ``plugins_spotlight_dim`` 设置键（settingsChanged 会推重读，
    设置页拖滑条遮罩实时变深浅）。光斑位置 / 大小由 Python 轮询喂
    ``set_hole``，本文件完全感知不到。

    2026-10-18 plugin-audit F9/D-S5：top_center dock 让位。top_center
    只能手改 config 产生（编辑器三选项没有它），默认参数下 dock 视觉带
    y∈[20, 82]（margin_y 20 + bar_height 62×scale 1.0）完全盖住胶囊的
    y∈[18, 64]，且 TopWindow 恒在叠加窗口之上——点击也被 dock 截走，
    胶囊既看不见也点不着。dock 开着且放映中时胶囊让位到 dock 视觉底边
    之下 8px；配置不热载（重启生效），绑定实际静态。胶囊挪动后
    ``pill-rect`` 保留矩形随 y 变化自动上报（≤25ms 一拍），可点性不丢。
    零 Python 改动。
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

    /*! top_center dock 是否开着（手改 config 才可达，编辑器三选项没有
        它）。守卫写法先例 MainInterfaceEditor.qml 的 ``enabledCorners``；
        无 Backend 的宿主（preview 桩）按关处理。 */
    readonly property bool dockTopCenter: {
        if (typeof Backend === "undefined") return false
        var cfg = Backend.presentationConfig
        var corners = cfg && cfg.corners !== undefined ? cfg.corners : ({})
        var c = corners.top_center
        return c !== undefined && c.enabled === true
    }

    /*! top_center dock 的**视觉底边**（margin_y + bar_height × scale，
        默认 20 + 62×1.0 = 82；推导见 plugin-mech-spotlight.md §D-S5）。
        margin_* 的语义是视觉距离、dock 位置公式按它算（见
        windows.py::_position_dock），胶囊让位对齐同一把尺。 */
    readonly property real dockClearance: {
        if (typeof Backend === "undefined") return 82
        var cfg = Backend.presentationConfig
        var marginY = cfg && cfg.margin_y !== undefined ? Number(cfg.margin_y) : 20
        var barHeight = cfg && cfg.bar_height !== undefined ? Number(cfg.bar_height) : 62
        var scale = cfg && cfg.scale !== undefined ? Number(cfg.scale) : 1.0
        if (isNaN(marginY) || marginY < 0) marginY = 20
        if (isNaN(barHeight) || barHeight <= 0) barHeight = 62
        if (isNaN(scale) || scale <= 0) scale = 1.0
        return marginY + barHeight * scale
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, spotlightOverlay.dimAlpha)

        // ------------------------------------------------ 控制胶囊（顶部居中）
        Rectangle {
            id: pill
            objectName: "spotlightPill"

            anchors.horizontalCenter: parent.horizontalCenter
            // top_center dock 开着且放映中 → 让位到 dock 视觉底边之下 8px
            // （dock 带完全盖住设计位 y∈[18,64]，TopWindow 又恒在遮罩之上，
            // 不让位就是「既看不见也点不着」）；否则回设计位 18。dock 只在
            // 放映期可见（show_docks/hide_docks），非放映期开聚光灯不让位。
            y: (dockTopCenter && typeof Backend !== "undefined"
                && Backend.presentationActive) ? dockClearance + 8 : 18
            width: pillRow.width + 28
            height: 46
            radius: 23
            color: Qt.rgba(1, 1, 1, 0.13)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.26)

            // 上报自身几何给插件做「镂空保留矩形」（缘由见文件头注释）。
            // 父项就是填满窗口的遮罩矩形，x/y 即窗口局部逻辑坐标；几何只在
            // 窗口resize 时变，不需要节流。preview 等无 Backend 的宿主下静默跳过。
            // 2026-10-09 起第 5 参带圆角半径（胶囊 = 高度一半全圆角）：直角
            // 保留矩形会让光斑扫过胶囊时四角漏出直角遮罩残片
            function reportGeometry() {
                if (typeof Backend === "undefined")
                    return
                Backend.triggerAction("plugin:spotlight:pill-rect:"
                                      + Math.round(x) + "," + Math.round(y) + ","
                                      + Math.round(width) + "," + Math.round(height)
                                      + "," + Math.round(height / 2))
            }
            Component.onCompleted: reportGeometry()
            onXChanged: reportGeometry()
            onYChanged: reportGeometry()
            onWidthChanged: reportGeometry()
            onHeightChanged: reportGeometry()

            Row {
                id: pillRow
                anchors.centerIn: parent
                spacing: 4

                Repeater {
                    // 三个胶囊按钮：缩小 / 放大 / 关闭。遮罩窗口不抢焦点，
                    // MouseArea 的悬停与点击照常工作。✕ 排在**末位**——
                    // 主退出路径在三键中间（2026-10-18 plugin-audit F8），
                    // 与一切常见工具条（✕ 恒最右）相悖，肌肉记忆必落空
                    model: [
                        { icon: "ic_fluent_subtract_20_regular", action: "plugin:spotlight:smaller", tip: qsTr("缩小光斑") },
                        { icon: "ic_fluent_add_20_regular", action: "plugin:spotlight:bigger", tip: qsTr("放大光斑") },
                        { icon: "ic_fluent_dismiss_20_filled", action: "plugin:spotlight:close", tip: qsTr("退出聚光灯") },
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
                        // 场景内 tooltip（2026-10-18 plugin-audit F11）：Rin.ToolTip
                        // 是 Popup——独立弹层坐在普通带，遮罩是置顶带，tooltip
                        // 只在光斑洞里可见（「半个 tooltip」的破碎观感）；手动
                        // 绑 visible 又让 delay 失效（悬停即弹）。改成遮罩窗口
                        // 内的自绘气泡：与遮罩同带渲染永不被盖，400ms 悬停
                        // 计时器补上 delay 语义。
                        Timer {
                            id: tipDelay
                            interval: 400
                            running: btnArea.containsMouse
                        }
                        Rectangle {
                            id: btnTip
                            visible: btnArea.containsMouse && !tipDelay.running
                            anchors.top: parent.bottom
                            anchors.topMargin: 6
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: btnTipText.implicitWidth + 20
                            height: btnTipText.implicitHeight + 12
                            radius: 6
                            color: Qt.rgba(0.12, 0.12, 0.13, 0.96)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.10)
                            z: 10
                            Text {
                                id: btnTipText
                                anchors.centerIn: parent
                                text: pillButton.modelData.tip
                                font.pixelSize: 12
                                color: "#FFFFFF"
                            }
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
            text: qsTr("光斑跟随鼠标 · 光斑外点击被遮住 · 键盘 + / − 或胶囊按钮调大小 · 点 ✕ 退出")
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
