import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    日志窗口。

    2026-11-21 用户指令：设置标题栏版本号右侧加「更多」按钮，菜单里的「日志」
    打开这个窗口。**只读** —— 这里不提供任何写日志 / 清日志的入口，它存在的
    意义是「用户遇到问题时不用去翻文件夹」。

    结构照 ``DebugWindow.qml``：``Rin.FluentWindowBase``（单页窗口，不需要
    设置那套左侧导航），关闭只隐藏不销毁，走 ``Backend.closeLogWindow()``。
    原生边框照旧交给 RinUI（见 ``Settings.qml`` 头注释），别在这里碰 ``flags``。

    正文取 ``Backend.readLogText()``（Python 侧只读文件尾部 256 KB，理由写在
    那个槽的注释里），每次窗口露出来时重读一次 —— 日志是 append 的，重读
    永远比增量拼接可靠，而这点开销只在开窗那一下。

    ⚠️ 滚动容器自己写 ``Flickable`` 而不是 ``Rin.ScrollView``：打开就要停在
    **最新一行**，而 ``ScrollView`` 不保证内容改完之后 ``contentItem.parent``
    还是那个 Flickable（实测它是内部实现细节，取到与否随 Qt 版本变）。自己的
    Flickable 有稳定的 ``contentY``，一行赋值就到底。
*/

Rin.FluentWindowBase {
    id: logWindow

    objectName: "logWindow"
    title: qsTr("日志")
    visible: false
    width: 900
    height: 640
    minimumWidth: 520
    minimumHeight: 320

    onClosing: function (event) {
        event.accepted = false
        Backend.closeLogWindow()
    }

    //: 正文。放属性上而不是直接绑 ``Backend.readLogText()``：那是个槽，
    //: 不会自己通知变化，重读时机由本窗口控制（露出时、点刷新时）。
    property string logText: ""

    //: 是否跟随尾部。每次重读 / 打开都置回 true，用户自己往上翻了就断开。
    property bool followTail: true

    function reload() {
        logText = Backend.readLogText()
        followTail = true
        // ⚠️ 大段文本的布局是**异步**的：``contentHeight`` 要等几帧才追上真实
        // 高度，同一次调用里算出来的 ``contentY`` 会停在倒数第二屏（实测差
        // 53px）。所以这里只补一次，真正的收敛靠下面 TextEdit 的
        // ``onContentHeightChanged`` —— 它每变一次就把尾巴再拽下来。
        Qt.callLater(scrollToBottom)
    }

    function scrollToBottom() {
        // ⚠️ 用 ``logTextEdit.contentHeight``（文本自己的高度）而不是
        // ``flick.contentHeight``：后者是绑定值，文本高度变了之后要等下一帧
        // 才更新，在 ``onContentHeightChanged`` 里读到的是**旧**值 —— 实测
        // 会永远停在倒数一行半（差 16px）。
        flick.contentY = Math.max(0, logTextEdit.contentHeight + 24 - flick.height)
    }

    onVisibleChanged: {
        if (visible)
            reload()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Caption
                color: Lumi.textSecondary
                elide: Text.ElideMiddle
                text: qsTr("logs/luminalium.log · 只读，显示最新的 256 KB")
            }

            Rin.Button {
                objectName: "logReloadButton"
                text: qsTr("刷新")
                icon.name: "ic_fluent_arrow_clockwise_20_regular"
                // flat：工具栏按钮不该是一块实色面板（RinUI 的 flat 平时背景
                // 透明、悬停才浮出 subtleSecondary）。实色版在这条深色工具条上
                // 会显成一块亮方块，跟下面的日志背板抢注意力。
                flat: true
                onClicked: logWindow.reload()
            }

            Rin.Button {
                objectName: "logOpenDirButton"
                text: qsTr("打开日志目录")
                icon.name: "ic_fluent_folder_open_20_regular"
                flat: true
                onClicked: Backend.openLogDir()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Lumi.controlRadius
            color: Lumi.panelCardBg
            border.width: 1
            border.color: Lumi.hairline
            clip: true

            Flickable {
                id: flick

                anchors.fill: parent
                anchors.margins: 1
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                contentWidth: width
                contentHeight: Math.max(height, logTextEdit.contentHeight + 24)

                // 用户自己往上翻过就别再把他拽回底部；滚回最下面重新跟随。
                onMovementEnded: logWindow.followTail =
                    contentY >= contentHeight - height - 4

                ScrollBar.vertical: Rin.ScrollBar {
                    policy: ScrollBar.AsNeeded
                }

                TextEdit {
                    id: logTextEdit

                    x: 12
                    y: 12
                    width: flick.width - 24
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.Wrap
                    text: logWindow.logText
                    color: Lumi.textPrimary
                    // Consolas 没有汉字，Qt 会逐字回退到系统中文 -- 日志里那句话
                    // 和缩进的时间戳对齐就行，不需要等宽覆盖全部字符。
                    font.family: "Consolas"
                    font.pixelSize: 12
                    selectionColor: Lumi.accent
                    selectedTextColor: Lumi.textOnAccent

                    // 布局追上真实高度时把尾巴再拽下来一次（reload 里的
                    // callLater 只能补第一拍，见那边注释）。补两拍：Flickable
                    // 的 contentHeight 绑定比 TextEdit 晚一帧，第一拍设的
                    // contentY 会被它按旧高度夹住（差一行，16px）。
                    onContentHeightChanged: {
                        if (logWindow.followTail) {
                            logWindow.scrollToBottom()
                            Qt.callLater(logWindow.scrollToBottom)
                        }
                    }
                }
            }

            // 空文件（还没写过日志）时给一句解释，别让整块面板空着。
            Rin.Text {
                anchors.centerIn: parent
                visible: logWindow.logText === ""
                typography: Rin.Typography.Body
                color: Lumi.textSecondary
                text: qsTr("暂无日志内容")
            }
        }
    }
}
