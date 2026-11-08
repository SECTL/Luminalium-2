import QtQuick
import RinUI as Rin

/*!
    小黑板「滑动清屏」弹层（2026-10-17 按 Lmn-copy 蓝本 ``Board.qml`` 的
    ``eraserPopup`` 重做）。

    版式照蓝本：236×60 卡片（与色板卡同款底色 / 描边 / radius 12），
    内部轨道 radius 22（白 8% 底），居中 14px「滑动清屏」随拖动进度淡出，
    40px 圆 thumb（深色底 + 清空图标）。拖到底触发 ``triggered()``（宿主
    接 clearPage + 关弹层），未到底松手弹簧回位（200ms OutCubic），
    按下时 thumb 缩 0.95。

    存在理由（蓝本同款交互）：清屏是破坏性最强的操作，滑动确认把误点的
    代价从「整板没了」降到「弹层缩回去」。单击胶囊上的清空钮仍是直接
    清屏（蓝本如此；本项目的 clearPage 进撤销栈、可整板恢复，安全）。

    进出场动画与笔选单同一套节奏（opacity + scale 0.92↔1.0、150ms OutCubic、
    收起 200ms 后隐藏；10ms openTimer 的理由见 ``PenPaletteCard`` 头注释的
    ``reveal`` 一节 —— 先让 ``visible = true`` 渲出第一帧再启动动画，
    同帧改两个属性动画会被吃掉）。
*/
Rectangle {
    id: root

    /*! 语义开关：true = 展开。 */
    property bool opened: false

    /*! 拖到底触发（宿主：clearPage + 关弹层）。 */
    signal triggered()

    onOpenedChanged: opened ? open() : close()

    function open() {
        closeTimer.stop()
        visible = true
        openTimer.start()
    }
    function close() {
        openTimer.stop()
        opacity = 0
        scale = 0.92
        closeTimer.start()
    }

    width: 236
    height: 60
    visible: false
    opacity: 0
    scale: 0.92
    radius: 12
    color: "#202020"
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.1)
    clip: true

    Behavior on opacity {
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
    }
    Behavior on scale {
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
    }

    Timer {
        id: openTimer
        interval: 10
        onTriggered: if (root.visible) { root.opacity = 1; root.scale = 1.0 }
    }
    Timer {
        id: closeTimer
        interval: 200
        onTriggered: root.visible = false
    }

    // 整卡吞输入（P2-8，与笔选单卡行为对齐）：此前只有 track（四边
    // 8px 内边距内）接事件，卡片边缘 8px 的点击会穿透到板面 InkLayer —— 在
    // 弹层上点一下却给黑板擦了一道。声明在 track **之前**：z 序在 track 之下，
    // track 内的滑动拖拽照常，只有边缘 8px 落进这层被吞掉。
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        hoverEnabled: true
    }

    Rectangle {
        id: track
        anchors.fill: parent
        anchors.margins: 8
        radius: 22
        color: Qt.rgba(1, 1, 1, 0.08)
        clip: true

        property real dragX: 2
        property bool dragging: false
        readonly property real maxX: width - thumb.width - 2

        Rin.Text {
            anchors.centerIn: parent
            text: qsTr("滑动清屏")
            color: Qt.rgba(1, 1, 1, 0.5)
            font.pixelSize: 14
            // 随拖动进度淡出（蓝本同款系数 1.5：拖到 2/3 处文字已全隐）
            opacity: 1 - Math.max(0, Math.min(1,
                track.dragX / Math.max(1, track.maxX) * 1.5))
        }

        Rectangle {
            id: thumb
            width: 40
            height: 40
            radius: 20
            anchors.verticalCenter: parent.verticalCenter
            x: track.dragX
            color: "#484848"
            scale: track.dragging ? 0.95 : 1.0

            Rin.Icon {
                anchors.centerIn: parent
                icon: "ic_fluent_delete_20_regular"
                size: 20
                color: "#FFFFFF"
            }

            // 松手回位的弹簧：只在非拖动态生效，拖动中 x 跟手
            Behavior on x {
                enabled: !track.dragging
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }
            Behavior on scale {
                NumberAnimation { duration: 100 }
            }
        }

        MouseArea {
            anchors.fill: parent
            preventStealing: true

            onPressed: function (m) {
                track.dragging = true
                // 点在 thumb 外：先把 thumb 吸到触点下（蓝本同款）
                var xInThumb = m.x - thumb.x
                if (xInThumb < 0 || xInThumb > thumb.width) {
                    track.dragX = Math.max(2, Math.min(track.maxX,
                        m.x - thumb.width / 2))
                }
            }
            onPositionChanged: function (m) {
                if (track.dragging) {
                    track.dragX = Math.max(2, Math.min(track.maxX,
                        m.x - thumb.width / 2))
                }
            }
            onReleased: {
                track.dragging = false
                if (track.dragX >= track.maxX - 4)
                    root.triggered()
                // 无论成没成功都回位（成功了弹层正在收起，回位动画在
                // 淡出掩护下完成，下次打开 thumb 已归位）
                track.dragX = 2
            }
            onCanceled: {
                track.dragging = false
                track.dragX = 2
            }
        }
    }
}
