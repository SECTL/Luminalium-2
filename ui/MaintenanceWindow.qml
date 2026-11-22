import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import RinUI as Rin
import Luminalium

/*!
    维护模式窗口（2026-11-22 用户指令：「按照 ClassIsland 制作此程序的维护模式
    窗口，本程序没有的功能不要做」）。

    ## 照的是哪一张窗

    ClassIsland 的「恢复」窗（``Views/RecoveryWindow.axaml`` 450×600 +
    ``Views/RecoveryPages/HomePage.axaml``）。版式逐条对过来：

    * 小窗、居中、不可最大化（``minimizeVisible/maximizeVisible: false``，与
      ``MultiInstanceDialog`` 同一处理）——维护模式不是主界面，别给用户
      「把它当工作台用」的暗示；
    * 正文第一行是 ``Subtitle`` 的「选择一个选项」，第二行一句「选择一个操作
      以继续。」（逐字照抄文案）；
    * 操作项是**连续分组卡片**（组内上卡只圆上两角、下卡只圆下角、中间共用
      一条边），每组之间空一行 —— 与 ``SettingsExpanderItem`` 的 cardContainer
      同一视觉，本项目的对应物是 ``Rin.SettingCard`` + 分角圆角；
    * 危险操作先弹 ``Rin.Dialog``，**要求在输入框里敲一遍确认文本**才放行
      （ClassIsland ``ContentDialogHelper.ShowConfirmationDialog`` 的
      ``requiredInput`` 同款）。没有这一步的话，「重置全部信息」点错一次就
      没法回头了。

    ## 只保留本程序真有的操作

    用户明令「本程序没有的功能不要做」，所以 ClassIsland 那边这几项**不做**：

    * 「恢复备份」—— L2 没有备份机制（``Config.save`` 不写 .bak）；
    * 「回滚到之前的版本」—— 没有版本管理器；
    * 「重置全部配置 / 全部信息」里针对档案、组件、自动化的部分 —— L2 没有
      档案、没有组件、没有自动化。

    留下来的是三层真实存在的数据（设置差分 / 续播记忆 / 外部插件）+ 缓存，
    见 ``app/bridge.py`` 的维护模式一节与 ``app/maintenance.py`` 头注释。

    ## 结果反馈

    ClassIsland 用 Toast。RinUI 的 ``Rin.Toast`` 是给 ``WindowManager`` 动态
    创建用的（``isDynamic``），放进固定窗口要自己接一堆进场动画时序；这里退成
    窗口顶部一条常驻结果条（``resultBar``）：操作完显示、6 秒后自己收起来。
    失败用红图标，成功用绿勾 —— 颜色取本项目既有的 danger 令牌，不另立一套。

    ## 交互出口

    * 「继续使用」三档 → ``Backend.maintenanceRestart(safe, diagnostic)``：
      应用层拉起一个**正常**进程后退出本进程（见 ``app/maintenance.py``）；
    * 关闭按钮 → ``Backend.quitMaintenance()``：维护模式直接退出，不回正常
      模式（ClassIsland 的 ``Closed`` 同样是「关了就没了」）。
*/

Rin.FluentWindowBase {
    id: root

    objectName: "maintenanceWindow"
    title: qsTr("维护模式")
    // 标题栏左侧那枚 16px 品牌图标（与设置窗口同一套取法）
    icon: Backend.resourceFile("logo.svg")
    visible: false

    /*! 尺寸固定、跟随屏幕夹取。520 宽比 ClassIsland 的 450 宽一点：中文描述
        比英文长，450 会频繁折成三行；高度留 700 让 8 个操作项尽量一屏放下，
        真放不下时由 ``ScrollView`` 兜底（ClassIsland 那张窗也是滚动的）。 */
    readonly property int windowWidth: Math.max(420, Math.min(520, Screen.width - 120))
    readonly property int windowHeight: Math.max(420, Math.min(740, Screen.height - 140))
    width: windowWidth
    height: windowHeight
    minimumWidth: windowWidth
    maximumWidth: windowWidth
    minimumHeight: windowHeight
    maximumHeight: windowHeight

    minimizeVisible: false
    maximizeVisible: false

    // 结果条的状态（``showResult`` 写，``resultTimer`` 清）
    property bool resultOk: true
    property string resultMessage: ""

    /// 当前确认框在做哪件事：``clear_temp`` / ``reset_settings`` / ``reset_all``
    property string pendingAction: ""

    onClosing: function (event) {
        // 维护模式关掉就是退出（不回正常模式）。这里只发请求，真正的收尾
        // （收窗口 / 退出事件循环）在 Python 侧 —— 与其它窗口同一套出口。
        event.accepted = false
        Backend.quitMaintenance()
    }

    // ============================================================ 动作

    function showResult(ok, message) {
        root.resultOk = ok
        root.resultMessage = message
        resultTimer.restart()
    }

    function askClearTemp() {
        root.pendingAction = "clear_temp"
        confirmDialog.title = qsTr("清除临时文件")
        confirmDialog.body = qsTr("此操作将删除所有缓存和临时文件，例如放映页缩略图，并且无法恢复。\n\n临时文件会在下次放映时重新生成，不影响任何设置。")
        confirmDialog.requiredText = ""
        confirmDialog.confirmLabel = qsTr("清除")
        confirmDialog.open()
    }

    function askResetSettings() {
        root.pendingAction = "reset_settings"
        confirmDialog.title = qsTr("重置应用设置")
        var confirmText = qsTr("我确认重置应用设置")
        confirmDialog.body = qsTr("此操作将把应用设置恢复为默认值，并且无法恢复。不影响已安装的插件与续播记忆。")
                                 + "\n\n"
                                 + qsTr("如果你确实希望继续，请在下方输入「%1」。").arg(confirmText)
        confirmDialog.requiredText = confirmText
        confirmDialog.confirmLabel = qsTr("重置")
        confirmDialog.open()
    }

    function askResetAll() {
        root.pendingAction = "reset_all"
        confirmDialog.title = qsTr("重置全部信息")
        var confirmText = qsTr("我确认重置全部信息")
        confirmDialog.body = qsTr("此操作将删除应用设置、续播记忆与已安装的外部插件，并清除临时文件，恢复到首次运行的状态，并且无法恢复。\n\n日志不会被删除。")
                                 + "\n\n"
                                 + qsTr("如果你确实希望继续，请在下方输入「%1」。").arg(confirmText)
        confirmDialog.requiredText = confirmText
        confirmDialog.confirmLabel = qsTr("重置")
        confirmDialog.open()
    }

    function runPendingAction() {
        var action = root.pendingAction
        root.pendingAction = ""
        confirmDialog.close()
        var result
        if (action === "clear_temp")
            result = Backend.maintenanceClearTemp()
        else if (action === "reset_settings")
            result = Backend.maintenanceResetSettings()
        else if (action === "reset_all")
            result = Backend.maintenanceResetAll()
        else
            return
        root.showResult(result.ok, result.message)
    }

    // ============================================================ 布局

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        /*! 结果条：贴顶、与卡片同宽。``preferredHeight`` 随可见性收成 0，
            否则空条会在标题上方留一块透明空隙（``visible: false`` 的项在
            Layout 里仍然占位 —— 这是 QML 布局的老坑）。 */
        Rin.Frame {
            id: resultBar

            objectName: "maintenanceResultBar"
            visible: root.resultMessage !== ""
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Layout.topMargin: 16
            Layout.preferredHeight: visible ? implicitHeight : 0
            implicitHeight: resultRow.implicitHeight + 24
            color: Lumi.tileBg
            border.width: 1
            border.color: Lumi.hairline
            radius: 8

            RowLayout {
                id: resultRow
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12

                Rin.Icon {
                    name: root.resultOk
                        ? "ic_fluent_checkmark_circle_20_regular"
                        : "ic_fluent_dismiss_circle_20_regular"
                    size: 18
                    color: root.resultOk ? Lumi.accent : Lumi.dockDangerIcon
                }

                Rin.Text {
                    objectName: "maintenanceResultText"
                    Layout.fillWidth: true
                    typography: Rin.Typography.Body
                    color: Lumi.textPrimary
                    text: root.resultMessage
                }
            }
        }

        /*! 滚动容器用裸 ``Flickable``：RinUI 0.4.4.1 的 ``qmldir`` 里虽然声明了
            ``ScrollViewer``，但 ``components/ScrollViewer.qml`` **根本不存在**
            （悬空条目，``Rin.ScrollViewer`` / ``Rin.ScrollView`` 都编译不过）。
            与 ``DebugWindow`` 同一条路：滚轮可用、不挂 ScrollBar。 */
        Flickable {
            id: scroller

            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: body.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: body

                // Flickable 不会把内容撑到视口宽 —— 不显式绑的话，卡片会按
                // 自己最窄的 implicitWidth 缩成一条细长条。
                width: scroller.width
                spacing: 6

                Rin.Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.topMargin: 24
                    typography: Rin.Typography.Subtitle
                    color: Lumi.textPrimary
                    text: qsTr("选择一个选项")
                }

                Rin.Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.topMargin: 2
                    Layout.bottomMargin: 10
                    typography: Rin.Typography.Body
                    color: Lumi.textSecondary
                    text: qsTr("选择一个操作以继续。")
                }

                // -------------------------------------------------- 组 1：继续
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    spacing: 0

                    Rin.SettingCard {
                        objectName: "maintenanceContinue"

                        Layout.fillWidth: true
                        clickable: true
                        topLeftRadius: 8
                        topRightRadius: 8
                        bottomLeftRadius: 0
                        bottomRightRadius: 0
                        icon.name: "ic_fluent_play_20_regular"
                        title: qsTr("继续使用 Luminalium 2")
                        description: qsTr("退出维护模式，正常启动应用。")
                        onClicked: Backend.maintenanceRestart(false, false)
                    }

                    Rin.SettingCard {
                        objectName: "maintenanceContinueSafe"

                        Layout.fillWidth: true
                        clickable: true
                        radius: 0
                        topLeftRadius: 0
                        topRightRadius: 0
                        bottomLeftRadius: 0
                        bottomRightRadius: 0
                        icon.name: "ic_fluent_shield_20_regular"
                        title: qsTr("以安全模式继续使用")
                        description: qsTr("禁用所有插件。")
                        onClicked: Backend.maintenanceRestart(true, false)
                    }

                    Rin.SettingCard {
                        objectName: "maintenanceContinueDiagnostic"

                        Layout.fillWidth: true
                        clickable: true
                        radius: 0
                        topLeftRadius: 0
                        topRightRadius: 0
                        bottomLeftRadius: 0
                        bottomRightRadius: 0
                        icon.name: "ic_fluent_bug_20_regular"
                        title: qsTr("以诊断模式继续使用")
                        description: qsTr("把日志级别提升到 DEBUG。")
                        onClicked: Backend.maintenanceRestart(false, true)
                    }

                    Rin.SettingCard {
                        objectName: "maintenanceOpenLogDir"

                        Layout.fillWidth: true
                        clickable: true
                        radius: 0
                        topLeftRadius: 0
                        topRightRadius: 0
                        bottomLeftRadius: 0
                        bottomRightRadius: 0
                        icon.name: "ic_fluent_folder_open_20_regular"
                        title: qsTr("打开日志目录")
                        description: qsTr("日志文件在 logs 目录下。")
                        onClicked: Backend.openLogDir()
                    }

                    Rin.SettingCard {
                        objectName: "maintenanceOpenAppDir"

                        Layout.fillWidth: true
                        clickable: true
                        radius: 0
                        topLeftRadius: 0
                        topRightRadius: 0
                        bottomLeftRadius: 8
                        bottomRightRadius: 8
                        icon.name: "ic_fluent_folder_20_regular"
                        title: qsTr("打开应用目录")
                        description: qsTr("配置与数据所在的位置。")
                        onClicked: Backend.openAppDir()
                    }
                }

                // -------------------------------------------------- 组 2：清理与重置
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.topMargin: 16
                    spacing: 0

                    Rin.SettingCard {
                        objectName: "maintenanceClearTemp"

                        Layout.fillWidth: true
                        clickable: true
                        topLeftRadius: 8
                        topRightRadius: 8
                        bottomLeftRadius: 0
                        bottomRightRadius: 0
                        icon.name: "ic_fluent_broom_20_regular"
                        title: qsTr("清除临时文件")
                        description: qsTr("删除所有缓存和临时文件。")
                        onClicked: root.askClearTemp()
                    }

                    Rin.SettingCard {
                        objectName: "maintenanceResetSettings"

                        Layout.fillWidth: true
                        clickable: true
                        radius: 0
                        topLeftRadius: 0
                        topRightRadius: 0
                        bottomLeftRadius: 0
                        bottomRightRadius: 0
                        icon.name: "ic_fluent_arrow_reset_20_regular"
                        title: qsTr("重置应用设置")
                        description: qsTr("恢复默认设置，不影响插件与记忆。")
                        onClicked: root.askResetSettings()
                    }

                    Rin.SettingCard {
                        objectName: "maintenanceResetAll"

                        Layout.fillWidth: true
                        clickable: true
                        radius: 0
                        topLeftRadius: 0
                        topRightRadius: 0
                        bottomLeftRadius: 8
                        bottomRightRadius: 8
                        icon.name: "ic_fluent_delete_20_regular"
                        title: qsTr("重置全部信息")
                        description: qsTr("恢复到首次运行的状态。")
                        onClicked: root.askResetAll()
                    }
                }

                Item { Layout.preferredHeight: 24 }
            }
        }

        // ============================================================ 结果条自动收起
        Timer {
            id: resultTimer
            interval: 6000
            onTriggered: root.resultMessage = ""
        }

        // ============================================================ 确认框
        /*! 危险操作的统一确认框（ClassIsland ``ContentDialogHelper
            .ShowConfirmationDialog`` 的本项目版）：

            * 正文之外，重置类操作还要求**在输入框里敲一遍** ``requiredText``
              才点亮主按钮 —— 拼错一个字都点不动；
            * 清除临时文件不需要输入（``requiredText`` 为空串），与 ClassIsland
              那一档一致（删缓存可重建，代价不对称）；
            * 文案逐条对应 ``app/bridge.py`` 那几个槽真正删掉的东西，别写成
              「重置全部配置」这种本程序不存在的层级。
        */
        Rin.Dialog {
            id: confirmDialog

            objectName: "maintenanceConfirmDialog"
            property string body: ""
            property string requiredText: ""
            property string confirmLabel: ""
            modal: true

            Rin.Text {
                objectName: "maintenanceConfirmBody"
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                color: Lumi.textPrimary
                text: confirmDialog.body
            }

            Rin.TextField {
                id: confirmInput

                objectName: "maintenanceConfirmInput"

                Layout.fillWidth: true
                Layout.preferredWidth: 320
                // 只有需要输入确认文本的操作才露这一格；清缓存那档直接两行字 + 按钮。
                visible: confirmDialog.requiredText !== ""
                placeholderText: qsTr("在此输入确认文本")
                onTextChanged: confirmButton.highlighted = confirmButton.enabled
            }

            footer: Rin.DialogButtonBox {
                id: confirmButtons

                Rin.Button {
                    objectName: "maintenanceConfirmCancel"

                    Layout.fillWidth: true
                    Layout.preferredWidth: confirmButtons.availableWidth / 2
                    text: qsTr("取消")
                    onClicked: confirmDialog.close()
                }

                Rin.Button {
                    id: confirmButton

                    objectName: "maintenanceConfirmOk"

                    Layout.fillWidth: true
                    Layout.preferredWidth: confirmButtons.availableWidth / 2
                    text: confirmDialog.confirmLabel
                    // 需要确认文本时：敲对了才放行。清除临时文件那档 requiredText
                    // 为空，恒亮。
                    enabled: confirmDialog.requiredText === ""
                             || confirmInput.text.trim() === confirmDialog.requiredText
                    onClicked: root.runPendingAction()
                }
            }

            // ``DialogButtonBox`` 建子项时会按 role 覆盖 highlighted（与设置页
            // 重启框同一处理，2026-10-04 实测），所以在这里补。
            onOpened: {
                confirmButton.highlighted = confirmButton.enabled
            }

            onClosed: {
                // 关掉对话框不保留上次敲的字：下一次打开必须重新确认。
                confirmInput.text = ""
            }
        }
    }
}
