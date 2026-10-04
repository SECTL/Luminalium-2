import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import RinUI as Rin
import Luminalium

/*!
    错误 / 崩溃报告窗口（2026-10-04 用户指令：「新增一个 Error handler，分为错误
    报告和崩溃报告」）。

    一张窗口承接**两档**报告 —— 版式完全相同，只有文案 / 表情 / 主按钮跟着
    ``ErrorHandler.isCrash`` 变（数据全在 ``app/error_handler.py``）：

    ==========  ==================  ==================  ==========
    档位         标题                主按钮               表情
    ==========  ==================  ==================  ==========
    崩溃报告     Luminalium 崩溃报告   重新启动             崩溃表情
    错误报告     Luminalium 错误报告   忽略                 错误表情
    ==========  ==================  ==================  ==========

    ## 版式：照 Class Widgets 2 重做（2026-10-05）

    用户指令：「参考一下 Class Widgets 2 的和 ClassIsland 2 的设计吧，感觉现有的
    还是有点敷衍」。CW2 的崩溃报告窗**同样**是 PySide6 + QML + RinUI（与我们同一套
    设计系统），所以直接对着它的 ``src/qml/ClassWidgets/Windows/ProblemReport.qml``
    改，比自己拍脑袋强：

        ┌ 标题栏（应用名 + 拖动）───────────────────────────┐
        │ [表情] 大标题                                      │
        │        说明：发生了什么 + 你可以做什么               │
        │                                                    │
        │ [i] 操作系统        [i] 应用版本                    │ ← 环境网格（田字格）
        │ [i] 发生时间        [i] 来源                       │
        │                                                    │
        │ ⌄ 查看详细信息                                      │ ← 折叠开关
        │   ┌──────────────────────────────────────┐         │
        │   │ 堆栈（等宽、可滚）           [复制]  │         │ ← 展开后才出现
        │   └──────────────────────────────────────┘         │
        ├────────────────────────────────────────────────────┤
        │ [提交 Issue] [复制]              [主操作 ⌄]         │ ← 页脚
        └────────────────────────────────────────────────────┘

    **关键差别是技术细节默认折叠。** 原来一上来就把整段 traceback 糊在脸上，看着像
    调试输出而不是给用户看的对话框 —— 这正是「敷衍」的来源。现在默认只给「发生了什么
    + 环境四格」，堆栈收在「查看详细信息」后面。

    ⚠️ 与 CW2 的一处**有意偏离**：CW2 把环境网格也收进 details 里；我们让它常显。
    因为 CW2 的面板高度跟着 ``implicitHeight`` 自己长，收起时不会有空白；而我们这边
    ``Rin.Window`` 吃的是写死的高度（见下），全收起来的话下半屏就是一片空白。

    （ClassIsland 2 是 Avalonia + FluentAvalonia，``ClassIsland.Core/Controls/
    CommonTaskDialogs.cs`` 只封了「标题 + 正文 + 确定」的最简形态，能给的结构信息
    有限 —— 所以骨架抄 CW2，ClassIsland 只当「就该用系统对话框的样子」的印证。）

    ## 尺寸

    宽度照 CW2 的 ``min(700, max(320, Screen.width - 96))`` 思路，按窗口**所在**那块
    屏夹一刀（``Screen`` 需要 ``import QtQuick.Window``，多屏时跟着走）。

    **高度分两档**（收起 / 展开），跟着「查看详细信息」切换；两档都 ``minimum`` =
    ``maximum`` = ``height`` 钉死 —— 对话框不该能拖大拖小。CW2 是让面板跟着
    ``implicitHeight`` 自己长（还有展开动画），我们这边显式给值更可控。

    ## 页脚

    Fluent 的 ContentDialog 是「正文 + 底部按钮条」：按钮条**顶着窗口下缘**、与正文
    之间隔一条 1px 分隔线，而不是飘在正文流里（原来按钮行就是 ``ColumnLayout`` 的
    最后一子项，跟堆栈框共用 16 间距）。

    ## 关闭按钮 = 忽略

    ``onClosing`` 拦下关闭、转发给 ``ErrorHandler.dismiss()``（同快捷面板：常驻
    窗口只隐藏不销毁，下次报告直接复用）。⚠️ 必须在 QML 侧拦：Python 槽接
    ``closing(QQuickCloseEvent*)`` 会因类型无法转换而抛 TypeError。
*/
Rin.Window {
    id: root

    // 宽度**上限**，实际按窗口所在屏幕的可用尺寸夹一刀。
    // ⚠️ ``Screen`` 需要 ``import QtQuick.Window``（上面已加）。
    readonly property int windowWidth: Math.max(
        520, Math.min(1280, Screen.width - 120))
    // 高度两档：收起（标题 + 说明 + 环境网格）/ 展开（+ 堆栈框）。
    readonly property int windowHeightCollapsed: Math.max(
        340, Math.min(380, Screen.height - 140))
    readonly property int windowHeightExpanded: Math.max(
        520, Math.min(600, Screen.height - 140))
    /*! 「查看详细信息」是否展开。堆栈默认收起（见头注释）。每次换报告都复位 ——
        否则上一次展开的状态会带到下一次，而用户多半只关心当前这一次。 */
    property bool detailsExpanded: false
    readonly property int windowHeight: detailsExpanded
        ? windowHeightExpanded : windowHeightCollapsed

    title: ErrorHandler.windowTitle
    visible: false
    width: windowWidth
    height: windowHeight
    minimumWidth: windowWidth
    maximumWidth: windowWidth
    minimumHeight: windowHeight
    maximumHeight: windowHeight

    // 报告窗只需要关闭键（参考图里也只有它）
    minimizeVisible: false
    maximizeVisible: false

    // 换了一份新报告就把「详细信息」收回去（数据全在 ErrorHandler 里，它一变就是新报告）
    Connections {
        target: ErrorHandler
        function onReportChanged() {
            root.detailsExpanded = false
        }
    }

    onClosing: function (event) {
        event.accepted = false
        ErrorHandler.dismiss()
    }

    // 环境网格的一格：图标 + （标签 / 值）两行 —— 照 CW2 的 ``EnvironmentItem``。
    // 值一律 ``elide``：来源可能是很长的线程名，不能把格子撑破。
    component EnvironmentItem: RowLayout {
        id: environmentItem

        property string iconName: ""
        property string label: ""
        property string value: ""

        spacing: 10
        Layout.fillWidth: true
        Layout.minimumWidth: 0

        Rin.Icon {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 16
            Layout.preferredHeight: 16
            icon: environmentItem.iconName
            size: 16
            color: Lumi.textSecondary
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignVCenter
            spacing: 0

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Caption
                color: Lumi.textTertiary
                text: environmentItem.label
                elide: Text.ElideRight
            }

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                color: Lumi.textPrimary
                text: environmentItem.value
                elide: Text.ElideRight
            }
        }
    }

    // 两段式：正文（撑满剩余高度）+ 贴着下缘的页脚，中间靠间距分开 —— 见头注释
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================================================== 正文
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 24
            Layout.bottomMargin: 12
            spacing: 16

            // ================================================== 头部
            // 表情 + 大标题 + 说明。说明照 CW2 那种「发生了什么 + 你可以做什么」
            // 两句式（文案在 ``ErrorHandler.subtitle``）。
            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                Image {
                    objectName: "errorReportEmoji"
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 48
                    Layout.preferredHeight: 48
                    source: ErrorHandler.emojiSource
                    sourceSize: Qt.size(48, 48)
                    fillMode: Image.PreserveAspectFit
                    // ⚠️ 刻意**不用** ``asynchronous``：这是一张 162×162 的本地小图，
                    // 同步解码的代价可以忽略；而异步那一版在「窗口从未被暴露」的
                    // 离屏预览里会一直停在空白（``tools/preview.py`` 抓出来没有表情）。
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 4

                    Rin.Text {
                        objectName: "errorReportHeading"
                        Layout.fillWidth: true
                        typography: Rin.Typography.Title
                        text: ErrorHandler.heading
                    }

                    Rin.Text {
                        objectName: "errorReportSubtitle"
                        Layout.fillWidth: true
                        typography: Rin.Typography.Body
                        color: Lumi.textSecondary
                        text: ErrorHandler.subtitle
                    }
                }
            }

            // ============================================ 运行环境（田字格）
            // 照 CW2 的 2×2 网格。以前这些信息只躺在「复制」出来的正文里，界面上
            // 看不见 —— 用户要报障还得先复制一遍才知道自己是什么版本。
            GridLayout {
                objectName: "errorReportEnvironment"
                Layout.fillWidth: true
                // 列数跟着实际宽度走：窄（≈700，CW2 的档）排 2 列两行，宽了就摊成
                // 一行四列 —— 否则 1280 宽下两列各占 600，格子空得晃眼。
                columns: Math.max(2, Math.min(4, Math.floor(width / 260)))
                columnSpacing: 16
                rowSpacing: 10

                EnvironmentItem {
                    iconName: "ic_fluent_desktop_20_regular"
                    label: qsTr("操作系统")
                    value: ErrorHandler.osName
                }
                EnvironmentItem {
                    iconName: "ic_fluent_apps_20_regular"
                    label: qsTr("应用版本")
                    value: ErrorHandler.appVersion
                }
                EnvironmentItem {
                    iconName: "ic_fluent_timer_20_regular"
                    label: qsTr("发生时间")
                    value: ErrorHandler.timestampText
                }
                EnvironmentItem {
                    iconName: "ic_fluent_info_20_regular"
                    label: qsTr("来源")
                    value: ErrorHandler.sourceText
                }
            }

            // ============================================ 查看详细信息（开关）
            // 堆栈**默认收起** —— 见头注释：一上来就糊整段 traceback 是「敷衍」的
            // 根源。flat 按钮 + chevron，与 CW2 一致。
            Rin.Button {
                objectName: "errorReportDetailsToggle"
                Layout.alignment: Qt.AlignLeft
                flat: true
                text: root.detailsExpanded
                    ? qsTr("收起详细信息") : qsTr("查看详细信息")
                icon.name: root.detailsExpanded
                    ? "ic_fluent_chevron_up_20_filled"
                    : "ic_fluent_chevron_down_20_filled"
                onClicked: root.detailsExpanded = !root.detailsExpanded
            }

            // ================================================== 堆栈
            // 收起时整块不占位（``visible`` false 的 Layout 子项不参与分配）。
            // 框本身是自绘的（``Rin.ScrollableTextArea`` 底子是 QtQuick Controls 的
            // TextArea，而它那个背景**只在高对比度模式下才可见** —— 常态下是一条
            // 没有边框的裸文本），所以套一层带描边的圆角矩形当卡片。
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: root.detailsExpanded
                Layout.minimumHeight: root.detailsExpanded ? 150 : 0
                visible: root.detailsExpanded
                clip: true

                Rectangle {
                    objectName: "errorReportTracebackBox"
                    anchors.fill: parent
                    radius: 6
                    color: Lumi.tileBg
                    border.width: 1
                    border.color: Lumi.hairline
                    clip: true

                    /*! ⚠️ ``Rin.ScrollableTextArea`` 而不是 ``Rin.TextArea``：后者不会滚。
                        另外它的 ``implicitHeight`` 求值失败（内层写了个不存在的
                        ``defaultHeight``），在 Layout 里**必须**给 ``anchors.fill``
                        或显式高度 —— 这里用 ``anchors.fill`` 直接铺满卡片。
                        字体走 ``font.family``（``ScrollView`` 会把它传给内容项）。 */
                    Rin.ScrollableTextArea {
                        objectName: "errorReportTraceback"
                        anchors.fill: parent
                        anchors.margins: 8
                        readOnly: true
                        color: Lumi.textPrimary
                        font.family: "Consolas"
                        font.pixelSize: 12
                        text: ErrorHandler.tracebackText
                    }
                }
            }

        } // ← 正文结束

        // ================================================== 页脚
        // 对话框的按钮条：**顶着窗口下缘**，与正文之间隔一条 1px 分隔线 —— 不再像
        // 原来那样当正文的最后一行（跟堆栈框共用 16 间距，看着就是普通窗口）。
        // 72 = 按钮 32 + 上下各 20 内边距。
        Item {
            objectName: "errorReportFooter"
            Layout.fillWidth: true
            Layout.preferredHeight: 72

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Lumi.hairline
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 8

                ReportButton {
                    objectName: "errorReportSubmit"
                    iconName: "ic_fluent_bug_20_regular"
                    label: qsTr("提交 Issue")
                    onClicked: ErrorHandler.submitIssue()
                }

                ReportButton {
                    objectName: "errorReportCopy"
                    iconName: "ic_fluent_copy_20_regular"
                    label: qsTr("复制")
                    onClicked: ErrorHandler.copyReport()
                }

                Item { Layout.fillWidth: true }

                SplitActionButton {
                    objectName: "errorReportSplit"
                    text: ErrorHandler.primaryAction === "restart"
                        ? qsTr("重新启动") : qsTr("忽略")
                    iconName: ErrorHandler.primaryAction === "restart"
                        ? "ic_fluent_arrow_clockwise_20_regular"
                        : "ic_fluent_dismiss_20_regular"
                    onPrimaryClicked: ErrorHandler.runAction(ErrorHandler.primaryAction)
                    onActionTriggered: function (action) {
                        ErrorHandler.runAction(action)
                    }
                }
            }
        }
    }
}
