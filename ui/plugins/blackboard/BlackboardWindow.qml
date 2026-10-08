import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    小黑板插件窗口 —— 可涂写的板书板。

    2026-10-06 小黑板插件（用户指令）。画布 = ``Canvas`` + 笔画数组：
    每一笔是 ``{color, width, points[]}``，画完的笔进 ``strokes``，
    撤销 / 重做 / 清空整幅重画；落笔过程中走**增量画**（只画最新一段，
    ``dirtyAll=false``），整幅重画只在撤销 / 重做 / 清空 / 尺寸变化时发生 ——
    否则一笔长线画到几千个点时每帧全量重绘会肉眼可见地掉帧。
    单点笔画合法（单击成点，2026-10-07 巡检补的，原来单击会被当空笔丢弃）；
    MouseArea 必须处理 ``onCanceled``（捕获被抢时收尾，防 liveStroke 悬挂）。

    2026-10-08 撤销/重做真栈（builtin-plugins-ux 计划 todo 4）：
    ``undoStack`` / ``redoStack`` 存 ``strokes`` 的**快照**（浅拷贝数组），
    上限 50 条丢最旧（一节课几十上百笔，内存不能无界膨胀）；清空也进栈
    —— 误触「清空」一撤销整板回来，可撤销优于确认弹窗（弹窗打断讲课）。
    快照只存引用是安全的：``strokes`` 的全部写入路径都是「slice + 整体
    重赋」，落进数组的笔画对象落定后永不再改（加点只发生在它还是
    ``liveStroke`` 的时候），快照不会被后续操作污染。

    ⚠️ 笔画数据放 QML 侧是**安全的**：这是普通自管窗口，只藏不销毁，
    ``WindowManager.rebuild_docks`` 不会碰它（``context.py`` 铁规 1 只
    约束挂进 dock 的驻留组件）。若哪天要把黑板搬进控制条驻留，这些
    状态必须整体搬去 Python。

    黑板色刻意不随主题（真黑板就是深色板面）；粉笔色是配套的五支。
    关窗路径照插件窗口标准（``onClosing`` → 动作通道 → 句柄 hide），
    禁止 ``Qt.FramelessWindowHint``。

    2026-10-08 板书导出（builtin-plugins-ux 计划 todo 5）：工具栏「导出」
    把画布抓成 PNG 存进 Python 推来的 ``exportDir``（file URL 根属性，
    注册期推送，见 plugin.py 头注释）。抓图前先 ``dirtyAll + requestPaint``
    是因为增量画管线下画布缓冲可能只有最新一段 —— 不整幅重画一次，
    抓到的可能是残缺缓冲。提示走 Text + Timer 淡出（SpotlightOverlay
    开场提示同款），不弹系统对话框：放映中弹对话框是教学事故。

    2026-10-08 快捷键（builtin-plugins-ux 计划 todo 9），全部窗口作用域
    （默认 context，别加宽 —— 黑板藏起来时按 E 不能动它的模式）：
        Ctrl+Z  撤销      Ctrl+Y  重做
        E       切橡皮    B       回到粉笔
    粉笔侧光标用 Cross（瞄准落点），橡皮用 SizeAll 而不是 PointingHand：
    手型光标的语义是「这里有个可点的链接」，不是「擦」；SizeAll 的
    四向箭头读作「大面积挪动/擦除」，与宽笔触的橡皮语义对得上。
*/
Rin.FluentWindow {
    id: boardWindow

    title: qsTr("小黑板")
    visible: false
    width: 760
    height: 540
    // ⚠️ 最小宽度别低于工具栏的自然宽度 + 两侧页边距（12×2）—— RowLayout 不会把
    // 固定宽的色点压小，窄了直接把右端裁没（2026-10-07 巡检补的地面）。
    // 实测轨迹：2026-10-07 约 610 / 下限 660；2026-10-08 加「重做」「导出」
    // 两个按钮后离屏脚本（.omo/evidence/task-4-builtin-plugins-ux.py）实测
    // 自然宽度 720 → 720+24=744，下限取 760（与默认宽度一致，留少许余量）
    minimumWidth: 760
    minimumHeight: 340

    onClosing: function (event) {
        event.accepted = false
        Backend.triggerAction("plugin:blackboard:close")
    }

    // ------------------------------------------------ 快捷键
    // 窗口作用域（Shortcut 默认 context）——黑板藏起来时这些键必须失效，
    // 不然用户在本子外按个 E 就把模式翻了。不做成可配置键位：讲课场景
    // 要的是肌肉记忆，四个键写死够用（todo 9 指令明确不加可配置）。
    Shortcut {
        sequence: "Ctrl+Z"
        onActivated: boardWindow.undo()
    }
    Shortcut {
        sequence: "Ctrl+Y"
        onActivated: boardWindow.redo()
    }
    Shortcut {
        sequence: "E"
        onActivated: boardWindow.eraserOn = true
    }
    Shortcut {
        sequence: "B"
        onActivated: boardWindow.eraserOn = false
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
    /*! 整幅重画开关：撤销 / 重做 / 清空 / 尺寸变化置位，下一帧 onPaint 全量重画。 */
    property bool dirtyAll: true
    /*! 撤销 / 重做栈：元素是 ``strokes`` 落定前的快照（浅拷贝数组）。
        只存引用不深拷贝是安全的 —— ``strokes`` 的写入全部是 slice+整体重赋，
        落定后的笔画对象不再被改（不变量见文件头注释，改动写入路径时必须保住它）。 */
    property var undoStack: []
    property var redoStack: []
    /*! 栈上限：超出丢最旧，防长会话内存膨胀。 */
    readonly property int historyLimit: 50

    /*! 板书导出目录（file URL 字符串带尾斜杠，Python 注册期推来；
        空串 = 还没推送 / 目录不可用，导出按钮保持禁用）。 */
    property string exportDir: ""

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
            pushHistory()
            var s = strokes.slice()
            s.push(liveStroke)
            strokes = s
        }
        liveStroke = null
    }

    /*! 把当前 ``strokes`` 的快照推进 ``stack``，返回截断后的新数组。
        ``var`` 数组属性原地 push/pop 不发变更信号（按钮 enabled 绑定不刷新），
        必须整体重赋，所以这里返回新数组而不是原地改。 */
    function _pushSnapshot(stack) {
        var next = stack.slice()
        next.push(strokes.slice())
        if (next.length > historyLimit) next.shift()
        return next
    }

    /*! 落定类操作（落笔完成 / 清空）动手前统一走这里：当前状态进撤销栈、
        重做链作废（新编辑之后 redo 到的东西已不属于这条时间线）。
        undo / redo **不走**这里 —— 它们各自把当前状态推进对面的栈；若走
        pushHistory，刚推进撤销栈的当前态会被立刻弹回，撤销成空操作。 */
    function pushHistory() {
        undoStack = _pushSnapshot(undoStack)
        redoStack = []
    }

    function undo() {
        if (undoStack.length === 0) return
        redoStack = _pushSnapshot(redoStack)
        strokes = undoStack[undoStack.length - 1]
        undoStack = undoStack.slice(0, undoStack.length - 1)
        dirtyAll = true
        boardCanvas.requestPaint()
    }

    function redo() {
        if (redoStack.length === 0) return
        undoStack = _pushSnapshot(undoStack)
        strokes = redoStack[redoStack.length - 1]
        redoStack = redoStack.slice(0, redoStack.length - 1)
        dirtyAll = true
        boardCanvas.requestPaint()
    }

    function clearAll() {
        // 先留快照再清 —— 清空可撤销（讲课误触一撤销整板回来，
        // 可撤销优于确认弹窗：弹窗在课上是打断）
        pushHistory()
        strokes = []
        liveStroke = null
        dirtyAll = true
        boardCanvas.requestPaint()
    }

    // ------------------------------------------------ 板书导出 PNG
    /*! 导出文件名时间戳 ``yyyyMMdd-HHmmss``（Windows 文件名禁冒号）。 */
    function _exportTimestamp() {
        var d = new Date()
        function pad(n) { return (n < 10 ? "0" : "") + n }
        return String(d.getFullYear())
            + pad(d.getMonth() + 1) + pad(d.getDate()) + "-"
            + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds())
    }

    /*! 一键导出板书 PNG 到 ``exportDir``。
        抓的是 Canvas 当前尺寸 = 纯板面内容（工具栏不在内）。
        失败不炸：``saveToFile`` 返回 false 时只把提示换成「导出失败」。 */
    function exportBoard() {
        if (exportDir === "" || strokes.length === 0) return
        // 先整幅重画再抓：增量画管线下缓冲可能只有最新一段（头注释）
        dirtyAll = true
        boardCanvas.requestPaint()
        boardCanvas.grabToImage(function (result) {
            var ok = result.saveToFile(
                exportDir + "板书-" + _exportTimestamp() + ".png")
            showExportHint(ok ? qsTr("已导出") : qsTr("导出失败"))
        })
    }

    /*! 2 秒淡出的结果提示（SpotlightOverlay 开场提示同款写法）。 */
    function showExportHint(msg) {
        exportHintText.text = msg
        exportHintTimer.restart()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // ============================================ 工具栏
        RowLayout {
            // objectName 供离屏验收脚本量自然宽度（minimumWidth 护栏）
            objectName: "blackboardToolbar"
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
                // 绑定撤销栈而非 strokes：清空之后 strokes 已空但恰恰这时
                // 最要点撤销（2026-10-08 真栈改造的动机场景）
                enabled: boardWindow.undoStack.length > 0
                text: qsTr("撤销")
                onClicked: boardWindow.undo()
            }
            Rin.Button {
                objectName: "blackboardRedoButton"
                enabled: boardWindow.redoStack.length > 0
                text: qsTr("重做")
                onClicked: boardWindow.redo()
            }
            Rin.Button {
                objectName: "blackboardClearButton"
                enabled: boardWindow.strokes.length > 0
                text: qsTr("清空")
                onClicked: boardWindow.clearAll()
            }
            Rin.Button {
                objectName: "blackboardExportButton"
                enabled: boardWindow.strokes.length > 0 && boardWindow.exportDir !== ""
                text: qsTr("导出")
                onClicked: boardWindow.exportBoard()
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
                // 粉笔 = 十字（瞄准落点）；橡皮 = SizeAll 四向箭头（理由见文件头注释，
                // PointingHand 的手型语义是「点链接」而不是「擦」）
                cursorShape: boardWindow.eraserOn ? Qt.SizeAllCursor : Qt.CrossCursor

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

    // ------------------------------------------------ 「已导出」提示
    // 叠在板面下缘（画布延伸到窗口底部，深色板面上白字才看得清）；
    // 透明度绑 Timer.running，时间到自然淡出（SpotlightOverlay 同款）
    Rin.Text {
        id: exportHintText
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 20
        font.pixelSize: 13
        color: Qt.rgba(1, 1, 1, 0.85)

        opacity: exportHintTimer.running ? 1 : 0
        Behavior on opacity {
            NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
        }

        Timer {
            id: exportHintTimer
            interval: 2000
        }
    }
}
