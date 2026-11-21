import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import RinUI as Rin
import Luminalium

/*!
    多实例询问窗（2026-11-22，照 Luminalium 1 的
    ``ppt_assistant/ui/dialog.html`` 里 ``code == "multi_instance"`` 那一档重做）。

    ## 2026-11-22 用户纠正：「你这也不是 RinUI 窗口啊，而且也不是标准 rinui 组件」

    第一版根项是 ``Rin.Window``，命令入口、警告卡全是自绘 ``Rectangle``，被否。
    原因有两层，两个都改了：

    1. **窗口没被 RinUI 接管**。这张窗在 ``WindowManager`` 建出来之前就由
       ``QQmlComponent`` 现建，没走 ``_attach_to_rinui``。RinUI 不接管时
       ``WS_CAPTION`` 会变成**真的原生标题栏**压在自绘标题栏上，看着就是一只
       普通 Windows 窗口。现在启动顺序已把检测挪到 ``WindowManager`` 之后，
       建完窗口立刻 ``_attach_to_rinui``（见
       ``application.py::_ask_multi_instance``）。
    2. **组件换成 RinUI 标准件**：根项 ``Rin.FluentWindowBase``（调试 / 日志
       窗口用的是同一套）；操作入口是 ``Rin.SettingCard`` 分角圆角卡组
       （第四轮曾收进底栏，第五轮按用户要求改回）；警告用 ``Rin.Dialog`` +
       ``Rin.DialogButtonBox``，正文 ``Rin.Text`` —— 与设置页「需要重启」框
       完全同一套标准写法。选 ``FluentWindowBase`` 还因为它底子是
       ``ApplicationWindow``，``QQC2.Overlay.overlay`` 才存在，
       ``Rin.Dialog`` 才能居中显示。

    正文里没有自绘 Rectangle；底栏是一个纯装饰 Rectangle（``windowBg`` 底色
    + 下圆角），不描边、直接铺满窗口下部，与日志窗口径一致，按钮和操作项
    仍是 RinUI 组件。

    ## 2026-11-22 第二次反馈：「但是现在也不好看啊 你参考下 classisland」

    版式按 ClassIsland / WinUI ContentDialog 的形态收了一遍：窗口从 738×577
    缩到 640×460（第三轮又调到 720×400，见下）；标题从 ``Title`` 降到
    ``Subtitle``；两个命令入口拼成**一张连续的分组卡片**（上卡圆上两角、
    下卡圆下两角，中间共用一条边），不再是两张飘着的设置卡（第四轮已整体
    收进底栏，见下）；底栏去掉那条
    孤立的分隔线（第三轮又改成分色底栏，见下）。

    ## 2026-11-22 第三轮（用户澄清：说明改实色正文，图标和大标题删掉，
    下方仿 RinUI Dialog 做宽按钮和色差背景）

    删掉左上角图标与「检测到程序已在运行」大标题，两段说明改成
    ``textPrimary`` 实色正文；底部按 ``DialogButtonBox`` 仿一块**亮一档的
    底栏**（``backgroundAcrylicColor`` + 顶部 hairline + 24 内边距），
    只放一个「取消」并让它**横向铺满**底栏。窗口 720×400（宽度按用户要求
    拉到 720，高度收回到贴着内容，避免卡片和底栏之间空一大块）。

    ## 2026-11-22 第四轮：「你就不能高仿一下dialog 吗」

    照着 ``Dialog.qml`` / ``DialogButtonBox.qml`` 逐条对了一遍：

    - 窗口底：``surfaceBg``（backgroundAcrylicColor）+ ``surfaceBorder`` +
      ``windowRadius`` —— 和 Dialog 的卡片底同一组令牌；
    - 底栏：独立的圆角卡片，``windowBg``（backgroundColor，比正文**暗**一档）
      + 1px 描边 + ``windowRadius`` + 24 内边距；
    - 操作全部收进底栏，做成 DialogButtonBox 的**等宽按钮**
      （第五轮又改回正文卡组，见下）；
    - 正文内边距同步成 Dialog 的 24；窗口高度先收到 300，第五轮卡组回来后
      提到 420。

    之前那版底栏用了 ``surfaceBg``，等于把 Dialog 的明暗关系反了过来（底栏
    比正文亮），所以怎么调都不像 —— 这是根因。

    ## 2026-11-22 第五轮：「改回卡组啊」+「取消占一半宽，破开 RinUI 默认描边」

    操作项恢复成正文里的分角圆角 ``SettingCard`` 卡组（第四轮曾整体收进
    底栏，用户否了）；底栏只留「取消」，右对齐、占可用宽度一半（与
    DialogButtonBox 单按钮规则一致）。窗口底与底栏都不再画 1px 描边，
    底栏用 ``windowBg`` 直接**铺满窗口下部**，只保留下圆角与窗口对齐 ——
    否则底栏外侧会多出一圈 RinUI 默认描边。

    ## 交互

    检测逻辑在 ``app/multi_instance.py``，装配在
    ``app/application.py::_guard_multi_instance``。本文件**不引用任何 Python
    上下文属性**，只发三个信号，由应用层接：

    * ``restartRequested`` —— 结束旧实例 + 启动本实例；
    * ``continueRequested`` —— 保留旧实例、强制启动（先过一道警告）；
    * ``cancelRequested`` —— 退出本次启动（含点关闭按钮）。

    ## 两阶段

    主页面是「说明 + 两个命令入口」；点「仍然启动」不直接放行，再弹一层
    ``Rin.Dialog`` 警告（L1 的 ``#multi-warning-modal`` 同构）。

    ⚠️ 关闭按钮要**先置 ``decided`` 再发信号**，否则 Python 侧 ``hide()`` 时
    会再触发一次 ``onClosing``，把流程绕回去。
*/
Rin.FluentWindowBase {
    id: root

    objectName: "multiInstanceDialog"

    signal restartRequested()
    signal continueRequested()
    signal cancelRequested()

    /*! 已经做出决定：之后不再接关闭事件里的「取消」。 */
    property bool decided: false
    /*! 「不建议多开」警告框是否展开（预览脚本靠它出第二张图）。 */
    property bool warningVisible: false

    title: qsTr("Luminalium 2 已在运行")
    visible: false

    readonly property int dialogWidth: Math.max(640, Math.min(720, Screen.width - 120))
    readonly property int dialogHeight: Math.max(360, Math.min(420, Screen.height - 140))
    width: dialogWidth
    height: dialogHeight
    minimumWidth: dialogWidth
    maximumWidth: dialogWidth
    minimumHeight: dialogHeight
    maximumHeight: dialogHeight

    // 询问窗只需要关闭键，别给用户拖大拖小的余地。
    minimizeVisible: false
    maximizeVisible: false

    /*! 高仿 ``Rin.Dialog`` 的卡片底：正文用 acrylic（``surfaceBg``），描边和
        圆角也取 Dialog 用的那组主题令牌。窗口自带的 Fluent 背景是更暗的
        ``backgroundColor``，不覆盖的话正文永远比 Dialog 暗一档。

        2026-11-22 用户指令：「尽量破开 RinUI 默认的那一层描边」—— 窗口底的
        1px 描边不要了，否则它会在底栏外侧再画一圈，底栏永远铺不到最下面。 */
    background: Rectangle {
        anchors.fill: parent
        z: -1
        color: Lumi.surfaceBg
        border.width: 0
        radius: Lumi.windowRadius
        clip: true
    }

    onClosing: function (event) {
        if (root.decided) {
            event.accepted = true
            return
        }
        event.accepted = false
        root.decided = true
        root.cancelRequested()
    }

    // warningVisible 是给预览 / 外部驱动的开关；Dialog 自己的 open/close 会改
    // visible，不能双向绑定，只能单向转发。
    onWarningVisibleChanged: {
        if (root.warningVisible)
            warningDialog.open()
        else
            warningDialog.close()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================================================== 正文
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 24
            Layout.bottomMargin: 16
            spacing: 12

            // 2026-11-22 第三轮（用户澄清）：图标和大标题删掉，说明段落改成
            // 实色正文（textPrimary，不再是次要灰）—— 对话框不要「引导页」
            // 那套层级，直接说事。
            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                color: Lumi.textPrimary
                text: qsTr("Luminalium 2 的另一个实例已经在后台运行。你可以在系统托盘区域点击图标打开「设置」进行配置。")
            }

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                color: Lumi.textPrimary
                text: qsTr("如果程序没有故障或设置错误，Luminalium 2 的主界面只会在放映时显示。\n\n如果仍然找不到旧实例，可能是出现了问题，可以尝试重新启动实例，或仍然启动新实例。")
            }

            /*! 2026-11-22 第五轮「改回卡组啊」：操作项恢复成正文里的分组
                卡片（上一轮曾整体收进底栏，用户否了）。上卡只圆上面两角、
                下卡只圆下面两角、中间共用一条边，视觉上是一组连续操作项。 */
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                Rin.SettingCard {
                    objectName: "multiInstanceRestart"

                    Layout.fillWidth: true
                    clickable: true
                    topLeftRadius: 8
                    topRightRadius: 8
                    bottomLeftRadius: 0
                    bottomRightRadius: 0
                    icon.name: "ic_fluent_arrow_sync_20_regular"
                    title: qsTr("重新启动实例")
                    description: qsTr("结束旧实例并启动此新实例")
                    onClicked: {
                        root.decided = true
                        root.restartRequested()
                    }
                }

                Rin.SettingCard {
                    objectName: "multiInstanceContinue"

                    Layout.fillWidth: true
                    clickable: true
                    topLeftRadius: 0
                    topRightRadius: 0
                    bottomLeftRadius: 8
                    bottomRightRadius: 8
                    icon.name: "ic_fluent_play_20_regular"
                    title: qsTr("仍然启动")
                    description: qsTr("保留旧实例并强制启动新实例")
                    onClicked: root.warningVisible = true
                }
            }

            Item { Layout.fillHeight: true }
        }

        // ================================================== 底栏
        // 高仿 ``DialogButtonBox``：底色用窗口基色 ``windowBg``（比正文 acrylic
        // 暗一档），24 内边距，不描边。之前那块「亮一档的平铺色带」正好把
        // Dialog 的明暗关系反了过来，所以怎么调都不像。
        Item {
            id: footer
            Layout.fillWidth: true
            Layout.leftMargin: 0
            Layout.rightMargin: 0
            Layout.preferredHeight: 80

            /*! 内容区被 RinUI 的 ``Utils.windowDragArea``（5px）左右下三边
                内缩，背景只画在 Item 里就会在窗口边留一圈没盖住的底色，四个
                角也会和窗口圆角错位。往这三边各撑出这么多，正好顶到窗口边
                —— 与 ``MainInterfaceEditor`` 的 ``edgeBleed`` 同一做法。 */
            readonly property real edgeBleed: Rin.Utils.windowDragArea

            Rectangle {
                anchors.fill: parent
                anchors.leftMargin: -footer.edgeBleed
                anchors.rightMargin: -footer.edgeBleed
                anchors.bottomMargin: -footer.edgeBleed
                color: Lumi.windowBg
                // 只留下面两个圆角与窗口对齐，上面两个角是直角、也不描边
                // —— 那块「卡片里的卡片」的描边就是用户说的 RinUI 默认那层线。
                topLeftRadius: 0
                topRightRadius: 0
                bottomLeftRadius: Lumi.windowRadius
                bottomRightRadius: Lumi.windowRadius
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 8

                Item { Layout.fillWidth: true }

                // 取消占底栏可用宽度的一半、右对齐 —— DialogButtonBox 对单个
                // 按钮的处理就是「preferredWidth = availableWidth / 2」。
                Rin.Button {
                    objectName: "multiInstanceCancel"

                    Layout.preferredWidth: parent.width / 2
                    text: qsTr("取消")
                    onClicked: {
                        root.decided = true
                        root.cancelRequested()
                    }
                }
            }
        }

        // ================================================== 「不建议多开」警告
        // RinUI 标准对话框：标题、底色、阴影、底栏全由组件负责，窗口内居中。
        // ⚠️ 必须声明在 Item 的 data 里（Popup 不是 QQuickItem，不能进
        // ``FluentWindowBase`` 的 ``content`` 别名 —— 那个别名要求 QQuickItem）。
        Rin.Dialog {
            id: warningDialog

            objectName: "multiInstanceWarningDialog"
            title: qsTr("不建议多开实例")
            modal: true

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                color: Lumi.textPrimary
                text: qsTr("同时运行多个实例，可能会导致：资源占用翻倍、数据冲突或丢失、功能异常或崩溃等。\n\n因此，开发者不推荐多开实例。若你在生产环境中强行使用此类功能，开发者不对该行为产生的后果承担任何责任。")
            }

            footer: Rin.DialogButtonBox {
                id: warningButtons

                Rin.Button {
                    Layout.fillWidth: true
                    Layout.preferredWidth: warningButtons.availableWidth / 2
                    text: qsTr("返回")
                    onClicked: root.warningVisible = false
                }

                Rin.Button {
                    id: warningContinueButton

                    Layout.fillWidth: true
                    Layout.preferredWidth: warningButtons.availableWidth / 2
                    text: qsTr("仍然启动")
                    onClicked: {
                        root.warningVisible = false
                        root.decided = true
                        root.continueRequested()
                    }
                }
            }

            onClosed: {
                if (root.warningVisible)
                    root.warningVisible = false
            }

            onOpened: {
                // ``DialogButtonBox`` 建子项时会按 role 覆盖 highlighted
                // （与设置页重启框同一处理，2026-10-04 实测）。
                warningContinueButton.highlighted = true
            }
        }
    }
}
