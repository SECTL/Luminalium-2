import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    小黑板插件窗口 —— 可涂写的板书板。

    2026-10-06 小黑板插件（用户指令）。画布 = ``Canvas`` + 笔画数组：
    每一笔是 ``{color, width, points[]}``，画完的笔进 ``strokes``，
    撤销 / 清空整幅重画；落笔过程中走**增量画**（只画最新一段，
    ``dirtyAll=false``），整幅重画只在撤销 / 清空 / 尺寸变化时发生 ——
    否则一笔长线画到几千个点时每帧全量重绘会肉眼可见地掉帧。
    单点笔画合法（单击成点，2026-10-07 巡检补的，原来单击会被当空笔丢弃）；
    MouseArea 必须处理 ``onCanceled``（捕获被抢时收尾，防 liveStroke 悬挂）。

    ⚠️ 笔画数据放 QML 侧是**安全的**：这是普通自管窗口，只藏不销毁，
    ``WindowManager.rebuild_docks`` 不会碰它（``context.py`` 铁规 1 只
    约束挂进 dock 的驻留组件）。若哪天要把黑板搬进控制条驻留，这些
    状态必须整体搬去 Python。

    黑板色刻意不随主题（真黑板就是深色板面）；粉笔色是配套的五支。
    关窗路径照插件窗口标准（``onClosing`` → 动作通道 → 句柄 hide），
    禁止 ``Qt.FramelessWindowHint``。
*/
Rin.FluentWindow {
    id: boardWindow

    title: qsTr("小黑板")
    visible: false
    width: 760
    height: 540
    // ⚠️ 最小宽度别低于工具栏的自然宽度（约 610：五粉笔色 + 三档笔宽 +
    // 橡皮/撤销/清空 + 模式标签，见下方 RowLayout）—— RowLayout 不会把
    // 固定宽的色点压小，窄了直接把右端裁没（2026-10-07 巡检补的地面）
    minimumWidth: 660
    minimumHeight: 340

    onClosing: function (event) {
        event.accepted = false
        Backend.triggerAction("plugin:blackboard:close")
    }

    // ------------------------------------------------ 板面与笔的常量
    // 黑板色 / 粉笔色是黑板的本体属性，刻意不做成设置项（见 plugin.py 注释）
    readonly property color boardColor: "#2A3C34"
    readonly property var chalkColors: [
        "#F3F3EE", // 白（主笔）
        "#F7D858", // 黄
        "#F28B82", // 红
        "#81B4E3", // 蓝
        "#9CDF9C", // 绿
    ]
    readonly property var brushSizes: [3, 6, 12]
    readonly property color inkColor: eraserOn ? boardColor : chalkColors[chalkIndex]

    /*! 当前笔宽档位下标；橡皮用「同档 × 6」的宽度，擦起来才痛快。 */
    property int sizeIndex: 1
    property int chalkIndex: 0
    property bool eraserOn: false
    readonly property real brushWidth: brushSizes[sizeIndex] * (eraserOn ? 6 : 1)

    // ------------------------------------------------ 笔画状态
    /*! 已落定的笔画：``[{color, width, points:[{x,y}...]}]``。 */
    property var strokes: []
    /*! 正在画的一笔（落笔期间；松手后挪进 strokes）。 */
    property var liveStroke: null
    /*! 整幅重画开关：撤销 / 清空 / 尺寸变化置位，下一帧 onPaint 全量重画。 */
    property bool dirtyAll: true

    function beginStroke(x, y) {
        liveStroke = {
            color: String(inkColor),
            width: brushWidth,
            points: [{ x: x, y: y }],
        }
    }

    function extendStroke(x, y) {
        if (liveStroke === null) return
        var pts = liveStroke.points
        var last = pts[pts.length - 1]
        var dx = x - last.x
        var dy = y - last.y
        // 抖动抑制：挪动不足 2px 不记点也不重画（笔尖悬停抖动会画出毛刺）
        if (dx * dx + dy * dy < 4) return
        pts.push({ x: x, y: y })
        boardCanvas.requestPaint()
    }

    function endStroke() {
        if (liveStroke === null) return
        // 单点也算一笔（单击成点）：圆头渲染成一个粉笔点，落笔即有反馈
        if (liveStroke.points.length >= 1) {
            var s = strokes.slice()
            s.push(liveStroke)
            strokes = s
        }
        liveStroke = null
    }

    function undo() {
        if (strokes.length === 0) return
        strokes = strokes.slice(0, strokes.length - 1)
        dirtyAll = true
        boardCanvas.requestPaint()
    }

    function clearAll() {
        strokes = []
        liveStroke = null
        dirtyAll = true
        boardCanvas.requestPaint()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // ============================================ 工具栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            // 粉笔色（圆点；选中 = accent 描边圈）
            Repeater {
                model: boardWindow.chalkColors

                delegate: Item {
                    required property int index
                    required property var modelData

                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 30

                    Rectangle {
                        anchors.centerIn: parent
                        width: 22
                        height: 22
                        radius: 11
                        color: modelData
                        border.width: !boardWindow.eraserOn
                                      && boardWindow.chalkIndex === index ? 2 : 1
                        border.color: !boardWindow.eraserOn
                                      && boardWindow.chalkIndex === index
                                      ? Lumi.accent : Lumi.hairline
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            boardWindow.chalkIndex = index
                            boardWindow.eraserOn = false
                        }
                    }
                }
            }

            Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 24; color: Lumi.hairline }

            // 笔宽（同款圆点，点内圆径随档位变）
            Repeater {
                model: boardWindow.brushSizes

                delegate: Item {
                    required property int index
                    required property var modelData

                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 30

                    Rectangle {
                        anchors.centerIn: parent
                        width: 26
                        height: 26
                        radius: 13
                        color: "transparent"
                        border.width: boardWindow.sizeIndex === index ? 2 : 0
                        border.color: Lumi.accent

                        Rectangle {
                            anchors.centerIn: parent
                            width: Math.min(14, 4 + index * 5)
                            height: width
                            radius: width / 2
                            color: boardWindow.eraserOn
                                   ? Lumi.textSecondary : boardWindow.inkColor
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: boardWindow.sizeIndex = index
                    }
                }
            }

            Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 24; color: Lumi.hairline }

            Rin.Button {
                objectName: "blackboardEraserButton"
                text: qsTr("橡皮")
                highlighted: boardWindow.eraserOn
                primaryColor: Lumi.accent
                onClicked: boardWindow.eraserOn = !boardWindow.eraserOn
            }
            Rin.Button {
                objectName: "blackboardUndoButton"
                enabled: boardWindow.strokes.length > 0
                text: qsTr("撤销")
                onClicked: boardWindow.undo()
            }
            Rin.Button {
                objectName: "blackboardClearButton"
                enabled: boardWindow.strokes.length > 0
                text: qsTr("清空")
                onClicked: boardWindow.clearAll()
            }

            Item { Layout.fillWidth: true }

            Rin.Text {
                text: boardWindow.eraserOn ? qsTr("橡皮模式") : qsTr("粉笔模式")
                color: Lumi.textSecondary
                font.pixelSize: 12
            }
        }

        // ============================================ 板面
        Canvas {
            id: boardCanvas
            objectName: "blackboardCanvas"

            Layout.fillWidth: true
            Layout.fillHeight: true

            onPaint: {
                var ctx = getContext("2d")
                if (boardWindow.dirtyAll) {
                    ctx.reset()
                    ctx.fillStyle = String(boardWindow.boardColor)
                    ctx.fillRect(0, 0, width, height)
                    var all = boardWindow.strokes
                    for (var i = 0; i < all.length; i++) {
                        drawStroke(ctx, all[i])
                    }
                    if (boardWindow.liveStroke !== null) {
                        drawStroke(ctx, boardWindow.liveStroke)
                    }
                    boardWindow.dirtyAll = false
                } else if (boardWindow.liveStroke !== null) {
                    // 增量：只画正在画的一笔的最新一段（省掉全量重绘的掉帧）；
                    // 还没挪出第二个点时先画点（按住不动也有笔尖反馈）
                    var pts = boardWindow.liveStroke.points
                    if (pts.length >= 2) {
                        drawSegment(ctx, boardWindow.liveStroke,
                                    pts[pts.length - 2], pts[pts.length - 1])
                    } else {
                        drawDot(ctx, boardWindow.liveStroke, pts[0])
                    }
                }
            }

            /*! 一整笔（起点到终点连线段序列）；单点笔画渲染成圆点。 */
            function drawStroke(ctx, stroke) {
                if (stroke.points.length === 1) {
                    drawDot(ctx, stroke, stroke.points[0])
                    return
                }
                for (var i = 1; i < stroke.points.length; i++) {
                    drawSegment(ctx, stroke, stroke.points[i - 1], stroke.points[i])
                }
            }

            /*! 一个粉笔点（单击成点；半径 = 笔宽一半，与圆头线帽同宽）。 */
            function drawDot(ctx, stroke, pt) {
                ctx.beginPath()
                ctx.arc(pt.x, pt.y, stroke.width / 2, 0, Math.PI * 2)
                ctx.fillStyle = stroke.color
                ctx.fill()
            }

            /*! 一段线（圆头线帽让粉笔道有笔画感）。 */
            function drawSegment(ctx, stroke, from, to) {
                ctx.beginPath()
                ctx.lineWidth = stroke.width
                ctx.lineCap = "round"
                ctx.lineJoin = "round"
                ctx.strokeStyle = stroke.color
                ctx.moveTo(from.x, from.y)
                ctx.lineTo(to.x, to.y)
                ctx.stroke()
            }

            // 尺寸变了画布缓冲会被清掉，必须整幅重画
            onWidthChanged: {
                boardWindow.dirtyAll = true
                requestPaint()
            }
            onHeightChanged: {
                boardWindow.dirtyAll = true
                requestPaint()
            }

            MouseArea {
                id: penArea
                anchors.fill: parent
                hoverEnabled: false
                preventStealing: true
                cursorShape: boardWindow.eraserOn ? Qt.PointingHandCursor : Qt.CrossCursor

                onPressed: function (mouse) {
                    // ⚠️ 别在这里动 dirtyAll：若刚 resize 完还没来得及重画，
                    // 把它翻成 false 会丢掉整幅内容
                    boardWindow.beginStroke(mouse.x, mouse.y)
                    boardCanvas.requestPaint()
                }
                onPositionChanged: function (mouse) {
                    boardWindow.extendStroke(mouse.x, mouse.y)
                }
                onReleased: function (mouse) {
                    boardWindow.endStroke()
                }
                onCanceled: boardWindow.endStroke()
                // ⚠️ 鼠标捕获被系统抢走（弹窗 / 手势接管）时 MouseArea 收不到
                // released —— 不收尾的话 liveStroke 悬挂，下一次落笔会被
                // beginStroke 直接顶掉，那一笔就无声无息丢了
            }
        }
    }
}
