import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium
import Luminalium.Ink 1.0

/*!
    小黑板插件窗口 —— 可涂写的板书板。

    2026-10-08 用户指令：「小黑板不好用，照搬叠加层的自建批注」—— 板面从
    QML ``Canvas`` + JS 笔画数组整体换成自建墨迹层 ``InkLayer``
    （``import Luminalium.Ink 1.0``，与放映叠加层 ``InkOverlay.qml`` 同一块）。
    换层白得的能力：笔画平滑滤波、压感/速度宽度、像素橡皮真擦除
    （``CompositionMode_Clear``，透出下面的板色矩形 —— 旧实现的「板色涂抹
    假装擦除」hack 成为历史）、PageStore 真操作栈（落笔 / 整笔擦除 /
    像素擦除 / 清屏全进栈，撤销重做是模型级回放而不是 QML 快照切换）、
    增量烘焙（空闲零帧，没有定时器也没有整幅重画）。

    旧的 QML 快照撤销栈（2026-10-08 早上加的 undoStack/redoStack）整体作废：
    ``PageStore.can_undo/can_redo`` 经 ``InkLayer.canUndo/canRedo``（notify=
    inkChanged）暴露给按钮 enabled；清空可撤销 —— ``model.py`` 的
    ``_ClearOp`` 落进撤销栈，``store.undo()`` 会把整板笔画原样放回
    （revert 分支 ``self.strokes = list(saved)``）。

    板面结构：容器 Item（``blackboardBoard``，导出抓图的目标）里先铺板色
    Rectangle 再放铺满的 InkLayer。InkLayer 自身透明、只画墨，板色必须
    由下层矩形提供 —— 像素橡皮清掉墨迹后透出来的就是它，导出 PNG 里
    板色也靠它（InkLayer 的抓图底色是透明的）。

    黑板色刻意不随主题（真黑板就是深色板面）；粉笔色是配套的五支。
    关窗路径照插件窗口标准（``onClosing`` → 动作通道 → 句柄 hide），
    禁止 ``Qt.FramelessWindowHint``。窗口懒创建、只藏不销毁，InkLayer
    实例与笔画随窗口存续，最小化/隐藏不丢板书（与 Canvas 时代一致）。

    2026-10-08 板书导出（builtin-plugins-ux 计划 todo 5，InkLayer 化后
    调整）：工具栏「导出」把**板面容器**（板色矩形 + 墨迹层整棵子树）
    抓成 PNG 存进 Python 推来的 ``exportDir``（file URL 根属性，注册期
    推送，见 plugin.py 头注释）。启用条件只看 ``exportDir !== ""``：
    PageStore 没有「本页是否有墨」的 QML 接口，清空操作也会把 canUndo
    顶成 true，拿不到干净的「有墨」判据 —— 空板导出一张纯板色 PNG
    无害，比维护一个近似状态诚实。提示走 Text + Timer 淡出
    （SpotlightOverlay 开场提示同款），不弹系统对话框：放映中弹对话框
    是教学事故。

    快捷键（builtin-plugins-ux 计划 todo 9），全部窗口作用域
    （默认 context，别加宽 —— 黑板藏起来时按 E 不能动它的模式）：
        Ctrl+Z  撤销      Ctrl+Y  重做
        E       切橡皮    B       回到粉笔
    粉笔侧光标用 Cross（瞄准落点），橡皮用 SizeAll 而不是 PointingHand：
    手型光标的语义是「这里有个可点的链接」，不是「擦」；SizeAll 的
    四向箭头读作「大面积挪动/擦除」，与宽笔触的橡皮语义对得上。
    MouseArea 没了之后光标由板面上的 HoverHandler 提供（Qt6 的
    HoverHandler 支持 cursorShape；InkLayer 只管笔画不管光标）。

    2026-10-08 隐藏常驻导航栏：本窗口无导航项，``Component.onCompleted``
    里把 ``navigationView.navigationBar.visible`` 置 false，空 rail 与
    ≡ 折叠按钮不再出现，内容区自动铺满（理由见该处注释）。
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

    Component.onCompleted: {
        // FluentWindow 常驻一条 NavigationBar（左侧 rail + ≡ 折叠按钮），
        // 本窗口没有任何导航项，空 rail 和 ≡ 是纯干扰。NavigationBar 在
        // NavigationView 的 RowLayout 里，不可见即被布局跳过，内容区自动
        // 铺满；标题在 titleBarLeadingHost 里，不受影响。藏它而不改 RinUI
        // 包（AGENTS.md 铁律：site-packages 不许动）。
        navigationView.navigationBar.visible = false
    }

    // ------------------------------------------------ 快捷键
    // 窗口作用域（Shortcut 默认 context）——黑板藏起来时这些键必须失效，
    // 不然用户在本子外按个 E 就把模式翻了。不做成可配置键位：讲课场景
    // 要的是肌肉记忆，四个键写死够用（todo 9 指令明确不加可配置）。
    Shortcut {
        sequence: "Ctrl+Z"
        onActivated: inkLayer.undo()
    }
    Shortcut {
        sequence: "Ctrl+Y"
        onActivated: inkLayer.redo()
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

    property int sizeIndex: 1
    property int chalkIndex: 0
    property bool eraserOn: false

    /*! 板书导出目录（file URL 字符串带尾斜杠，Python 注册期推来；
        空串 = 还没推送 / 目录不可用，导出按钮保持禁用）。 */
    property string exportDir: ""

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
        抓的是板面容器整棵子树（板色矩形 + InkLayer 的自定义场景图节点）：
        ``grabToImage`` 离屏渲染 item 子树，自定义 SG 节点照常进图 ——
        抓 InkLayer 本身会丢板色（层的底色是透明的），抓窗口又会带上
        工具栏，所以容器是唯一正确目标。空板也照导（理由见文件头注释）。
        失败不炸：``saveToFile`` 返回 false 时只把提示换成「导出失败」。 */
    function exportBoard() {
        if (exportDir === "") return
        boardContainer.grabToImage(function (result) {
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
                                   ? Lumi.textSecondary
                                   : boardWindow.chalkColors[boardWindow.chalkIndex]
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
                // 绑层的真操作栈（PageStore），清空也进栈 —— 清空之后恰恰
                // 是最要点撤销的时刻，绑「有没有墨」就点不动了
                enabled: inkLayer.canUndo
                text: qsTr("撤销")
                onClicked: inkLayer.undo()
            }
            Rin.Button {
                objectName: "blackboardRedoButton"
                enabled: inkLayer.canRedo
                text: qsTr("重做")
                onClicked: inkLayer.redo()
            }
            Rin.Button {
                objectName: "blackboardClearButton"
                // 清空走 store.clear_page（_ClearOp 进撤销栈，可整板恢复），
                // enabled 与撤销同源：有东西可撤销时板上才有东西可清
                enabled: inkLayer.canUndo
                text: qsTr("清空")
                onClicked: inkLayer.clearPage()
            }
            Rin.Button {
                objectName: "blackboardExportButton"
                // 启用只看导出目录有没有推来：空板导出一张纯板色 PNG 无害
                // （PageStore 没有「本页有墨」的 QML 判据，理由见文件头注释）
                enabled: boardWindow.exportDir !== ""
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
        // 容器 = 板色矩形 + 铺满的 InkLayer；导出抓图以它为目标（工具栏不进图）
        Item {
            id: boardContainer
            objectName: "blackboardBoard"

            Layout.fillWidth: true
            Layout.fillHeight: true

            Rectangle {
                anchors.fill: parent
                color: boardWindow.boardColor
            }

            InkLayer {
                id: inkLayer
                objectName: "blackboardInkLayer"
                anchors.fill: parent

                tool: boardWindow.eraserOn ? "eraser" : "pen"
                penColor: boardWindow.chalkColors[boardWindow.chalkIndex]
                penWidth: boardWindow.brushSizes[boardWindow.sizeIndex]
                // 沿用旧橡皮「同档 × 6」的手感：橡皮的本职是快速抹掉一片
                eraserWidth: boardWindow.brushSizes[boardWindow.sizeIndex] * 6
                // 手掌擦除参数用 InkLayer 默认（20mm / enabled），不接线配置：
                // 黑板是窗口内嵌板面，手掌擦除是放映叠加层的场景需求
            }

            // InkLayer 只管笔画不管光标；MouseArea 没了之后光标由它提供
            // （粉笔 = 十字瞄准落点，橡皮 = SizeAll 四向箭头，理由见文件头注释）
            HoverHandler {
                cursorShape: boardWindow.eraserOn ? Qt.SizeAllCursor : Qt.CrossCursor
            }
        }
    }

    // ------------------------------------------------ 「已导出」提示
    // 叠在板面下缘（板面延伸到窗口底部，深色板面上白字才看得清）；
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
