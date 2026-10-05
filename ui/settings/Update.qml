import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    设置 → 更新：**一比一复刻 ClassIsland 的更新页**
    （``ClassIsland/Views/SettingPages/UpdateSettingsPage.axaml`` +
    ``UpdateSettingsPage.axaml.cs``，2026-10-05 用户指令「参阅 ClassIsland
    的排版，补全检查更新机制和界面，目前先不要实现更新部署，外观要一比一
    复刻」）。逐段对应关系：

    * **头部状态区**（axaml 顶部那个 ``Grid``）：48px 的状态大图标 + 24px
      Medium 的状态大字 + 副行，全部照抄 —— 图标随结论换
      （已是最新 = 对勾圆 / 有更新 = 下载 / 其余 = 同步），副行在「已是最新」
      时显示「上次检查更新时间：…」、有更新时换成「发现新版本：…」。
      唯一的小动作：ClassIsland 只在**下载**时让图标自转，这里把自转放宽到
      任何「正在工作」的档（目前只有检查）—— 检查时一个静止的同步图标
      配上转圈的进度条很怪，自转读起来才像「正在查」。
    * **InfoBar 三连**：错误条（「更新时发生错误…」）照抄；
      「更新将在重启后应用」属于部署环节，**部署未实现、没有这一条**；
      多一条本项目自己的 Warning 条 —— 「下载并安装」点了之后亮出来
      （部署占位，见下）。⚠️ RinUI 的 ``InfoBar`` 自带关闭钮只会播退出动画、
      没有可接的信号，而且动画结束会把 ``opacity`` 写死在 0（绑定没了），
      之后这条既看不见又占着布局位。所以两条都用 ``CloseableInfoBar``
      包装：``closable: false`` 关掉自带钮，右上角自摆一枚 dismiss
      （外观位置与 WinUI/ClassIsland 的同款），关闭直接摘掉整条。
    * **按钮组**（``WrapPanel`` → ``Flow``）：结论为已是最新 → 强调色
      「检查更新」；有更新 → 强调色「下载并安装」+ 普通「检查更新」
      （ClassIsland 的 MultiBinding：非最新且未部署就补一枚普通检查）。
      工作中整组 **disabled**（ClassIsland 把 WrapPanel 的 IsEnabled 钉在
      Idle 上，是变灰不是藏起来）。「下载并安装」是**占位**：ClassIsland
      那边是 SplitButton（主按 = 下载并安装，flyout = 仅下载），部署没接
      之前两个动作都无处可去， RinUI 也没有 SplitButton —— 这里用普通
      强调色按钮，点了亮 Warning 条说明情况；部署接入时再换成
      SplitButton + 真动作。
    * **进度区**：工作中出现不确定态进度条 + 工作状态文字
      （「正在检查更新…」，对应 ``UpdateWorkingStatusToMessageConverter``）。
      「查看下载状态 / 取消」两枚按钮属于下载档，随部署一起加。
    * **分隔线 + 双 Tab**（``TabControl Classes="compact"`` →
      ``SelectorBar``）：RinUI 没有 TabView/TabControl，
      ``SelectorBar``（Fluent 的选择条，下划线选中态）是与 compact
      TabControl 最接近的一档：
      * **更新日志**：有更新 → 直接铺更新日志（Markdown）；已是最新 →
        居中的大图标 + 「真棒，您已更新到最新版本！」+「查看更新日志」
        按钮（ClassIsland 是一张 HoYo 贴图，本项目没有贴图资产，用同尺寸
        的对勾图标顶上）。⚠️ ClassIsland 的日志在 Tab 内**自成滚动**
        （MarkdownScrollViewer），这里直接铺在页面里、靠页面本身滚
        （FluentPage 自带 Flickable）：页面里再嵌一个 Flickable 会跟
        页面滚动抢滚轮，版式收益却只有「滚到顶后接着滚日志」。
      * **更新设置**：两张 ``SettingExpander`` —— 「更新模式」（下拉四档，
        对应 ``Settings.UpdateMode``）与「更新通道」（下拉稳定/预览 +
        通道说明行 + 「强制检查更新」入口，对应
        ``SelectedUpdateChannelV3`` 与 ``CheckUpdateAsync(isForce)``）。
        通道下拉的候选在 ClassIsland 来自发行服务器的元数据；本项目
        通道是静态两档（见 ``update_channels``），说明文案与
        ``app/update_checker.py::CHANNELS`` 同一份口径。

    机制侧见 ``app/update_checker.py``（GitHub Releases 源 + 版本比较）与
    ``app/bridge.py`` 的「检查更新」一节（后台线程 + 信号，ClassIsland 的
    ``UpdateService`` 是常驻服务 + 属性通知，形态不同、链路同构）。
    **下载 / 安装 / 部署未实现**（2026-10-05 用户指令）：状态机里
    ``updatedownloaded`` / ``updatedeployed`` 两档与「安装更新」「重启并
    应用更新」两枚按钮留给部署接入时，现在不出现。
*/
Rin.FluentPage {
    id: page

    title: qsTr("检查更新")
    contentSpacing: 6

    // ================================================================ 状态
    /*! 上次检查的结论：``unknown``（没查过）/ ``uptodate`` / ``available`` /
        ``error``。ClassIsland 把出错也记成 UpToDate（错误只亮 InfoBar），
        这里分开记一档 —— 副行显示「检查更新失败」比「您已更新到最新版本」
        诚实，错误细节仍在 InfoBar 里。 */
    readonly property string status: Backend.updateStatus
    readonly property bool working: Backend.updateWorkingStatus !== "idle"
    readonly property bool isAvailable: status === "available"
    readonly property bool isUpToDate: status === "uptodate"

    /*! 仓库 Releases 页（Warning 条里的链接）。 */
    readonly property string releasesUrl:
        "https://github.com/SECTL/Luminalium-2/releases"

    /*! 状态大图标（对应 ``UpdateStatusToIconGlyphConverter``）。 */
    readonly property string statusIconName: isAvailable
        ? "ic_fluent_arrow_download_20_regular"
        : (isUpToDate ? "ic_fluent_checkmark_circle_20_regular"
                      : "ic_fluent_arrow_sync_20_regular")

    /*! 状态大字（对应 ``UpdateStatusToMessageConverter``）。 */
    readonly property string statusMessage: isAvailable
        ? qsTr("检测到更新。")
        : isUpToDate ? qsTr("您已更新到最新版本。")
        : status === "error" ? qsTr("检查更新失败。")
        : qsTr("尚未检查更新。")

    /*! 通道候选与说明（与 ``app/update_checker.py::CHANNELS`` 同一份口径）。 */
    readonly property var updateChannels: [
        { id: "stable", name: qsTr("稳定版"),
          description: qsTr("正式发布的版本，经过完整测试。") },
        { id: "preview", name: qsTr("预览版"),
          description: qsTr("包含最新的功能与修复，但可能不稳定。") }
    ]

    readonly property var selectedChannel: {
        var id = Backend.settings.update_channel
        for (var i = 0; i < updateChannels.length; ++i) {
            if (updateChannels[i].id === id) {
                return updateChannels[i]
            }
        }
        return updateChannels[0]
    }

    /*! 「查看更新日志」对话框的内容：当前版本自己的更新日志；查不到
        就交代一句（ClassIsland 里这是随包发行的 ChangeLog.md，不会空）。 */
    function changelogText() {
        var text = Backend.updateCurrentChangelog
        return text !== "" ? text : qsTr("未找到当前版本的更新日志。")
    }

    // ==================================================== 可关闭 InfoBar 包装
    /*! RinUI ``InfoBar`` 的关闭钮不可控（见文件头注释），包装一层：
        自带 ``closable: false`` + 右上角一枚 dismiss。 */
    component CloseableInfoBar: Item {
        id: barRoot

        property alias severity: bar.severity
        property alias title: bar.title
        property alias text: bar.text
        signal closed

        Layout.fillWidth: true
        height: bar.height
        clip: true

        Rin.InfoBar {
            id: bar
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
            }
            closable: false
        }

        Rin.ToolButton {
            anchors {
                top: bar.top
                right: bar.right
                topMargin: 5
                rightMargin: 4
            }
            flat: true
            icon.name: "ic_fluent_dismiss_20_regular"
            width: 38
            height: 38

            Rin.ToolTip {
                text: qsTr("关闭")
                visible: parent.hovered
            }

            onClicked: barRoot.closed()
        }
    }

    // ============================================================ 头部状态区
    Item {
        objectName: "updateStatusHeader"
        Layout.fillWidth: true
        // 48 图标与两行文字取高者；文字列自然高约 24+6+18=48，刚好同档。
        implicitHeight: 52

        RowLayout {
            anchors.fill: parent
            spacing: 12

            Rin.Icon {
                id: statusIcon
                objectName: "updateStatusIcon"
                name: page.statusIconName
                size: 48
                Layout.alignment: Qt.AlignVCenter

                /*! 检查（以及将来的下载）期间自转（ClassIsland 的
                    ``Spinning`` 样式，1s 一圈）。⚠️ 无限循环动画停在中途会把
                    rotation 定格在半圈（图标歪着），所以用目标式动画 +
                    ``onStopped`` 复位到 0，下次开始也是正的。 */
                NumberAnimation {
                    id: statusIconSpin
                    target: statusIcon
                    property: "rotation"
                    from: 0
                    to: 360
                    duration: 1000
                    loops: Animation.Infinite
                    running: page.working
                    onStopped: statusIcon.rotation = 0
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Rin.Text {
                    objectName: "updateStatusText"
                    font.pixelSize: 24
                    font.weight: Font.Medium
                    text: page.statusMessage
                }

                /*! 副行：已是最新（含没查过 / 失败）→ 上次检查时间；
                    有更新 → 新版本号（对应 axaml 里两段互斥的 ``Run``）。 */
                Rin.Text {
                    objectName: "updateStatusSubText"
                    color: Lumi.textSecondary
                    text: page.isAvailable
                        ? qsTr("发现新版本：%1").arg(Backend.updateLatestVersion)
                        : qsTr("上次检查更新时间：%1").arg(
                              Backend.updateLastCheckTime !== ""
                              ? Backend.updateLastCheckTime : qsTr("从未"))
                }
            }
        }
    }

    // ================================================================ InfoBar
    /*! 网络错误条（ClassIsland 第一条 Error InfoBar 同款文案）。 */
    CloseableInfoBar {
        objectName: "updateErrorBar"
        visible: Backend.updateError !== ""
        severity: Rin.Severity.Error
        title: qsTr("更新时发生错误，请检查您的网络连接并重试。")
        text: Backend.updateError
        onClosed: Backend.clearUpdateError()
    }

    /*! 部署占位提示（本项目特有 —— ClassIsland 无此条）。 */
    CloseableInfoBar {
        objectName: "updateDeployStubBar"
        visible: page.deployNotice
        severity: Rin.Severity.Warning
        title: qsTr("更新部署尚未实现")
        text: qsTr("下载与安装更新的环节还没有接入，目前只能检查更新。"
                   + "可以前往 <a href=\"%1\">GitHub Releases</a> 手动下载新版本。"
                   ).arg(page.releasesUrl)
        onClosed: page.deployNotice = false
    }

    /*! 「下载并安装」被点过之后亮 Warning 条；关掉按钮或重开页面就复位。 */
    property bool deployNotice: false

    // ================================================================ 按钮组
    /*! 对应 ClassIsland 的 ``WrapPanel``：工作中整组变灰（不是藏起来）。 */
    Flow {
        objectName: "updateButtonRow"
        Layout.fillWidth: true
        spacing: 8
        enabled: !page.working

        /*! 已是最新 → 强调色「检查更新」。没查过（unknown）也给这枚：
            空着按钮行会像坏了。 */
        Rin.Button {
            objectName: "updateCheckButton"
            visible: page.isUpToDate || page.status === "unknown"
                     || page.status === "error"
            highlighted: true
            text: qsTr("检查更新")
            onClicked: {
                page.deployNotice = false
                Backend.requestCheckUpdate(false)
            }
        }

        /*! 有更新 → 强调色「下载并安装」（部署占位，见文件头注释）+ 普通检查。 */
        Rin.Button {
            objectName: "updateDownloadButton"
            visible: page.isAvailable
            highlighted: true
            text: qsTr("下载并安装")
            onClicked: page.deployNotice = true
        }

        Rin.Button {
            visible: page.isAvailable
            text: qsTr("检查更新")
            onClicked: {
                page.deployNotice = false
                Backend.requestCheckUpdate(false)
            }
        }
    }

    // ================================================================ 进度区
    /*! 工作状态：不确定态进度条 + 状态文字（ClassIsland 同款组合；
        下载/部署档的确定态进度与「取消」随部署接入）。 */
    ColumnLayout {
        objectName: "updateProgressRow"
        Layout.fillWidth: true
        spacing: 4
        visible: page.working

        Rin.ProgressBar {
            Layout.fillWidth: true
            indeterminate: true
        }

        Rin.Text {
            text: page.working ? qsTr("正在检查更新…") : ""
            color: Lumi.textSecondary
        }
    }

    // ================================================================ 分隔线
    /*! ClassIsland 的 ``Separator``：1px、比内容行高一点的颜色档。 */
    Rectangle {
        Layout.fillWidth: true
        Layout.topMargin: 8
        height: 1
        color: Lumi.hairline
    }

    // ================================================================ 双 Tab
    /*! 对应 ``TabControl Classes="compact"``（工作中同样禁用）。 */
    Rin.SelectorBar {
        id: tabs

        objectName: "updateTabs"
        enabled: !page.working

        Rin.SelectorBarItem { text: qsTr("更新日志") }
        Rin.SelectorBarItem { text: qsTr("更新设置") }
    }

    // ---- Tab 1：更新日志 ----
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        visible: tabs.currentIndex === 0
        enabled: !page.working

        /*! 有更新：直接铺新版本的更新日志（Markdown，ClassIsland 的
            ``MarkdownScrollViewer`` 内容层）。链接可点。 */
        Rin.Text {
            objectName: "updateChangelogView"
            Layout.fillWidth: true
            visible: page.isAvailable
            textFormat: Text.MarkdownText
            wrapMode: Text.WordWrap
            text: page.isAvailable ? Backend.updateChangelog : ""
            onLinkActivated: (link) => Qt.openUrlExternally(link)
        }

        /*! 已是最新：居中的空状态（ClassIsland 的贴图 + 一句夸 + 看日志）。 */
        ColumnLayout {
            objectName: "updateUpToDatePanel"
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 50
            Layout.bottomMargin: 50
            spacing: 8
            visible: !page.isAvailable

            Rin.Icon {
                Layout.alignment: Qt.AlignHCenter
                name: "ic_fluent_checkmark_circle_20_regular"
                size: 81
            }

            Rin.Text {
                Layout.alignment: Qt.AlignHCenter
                horizontalAlignment: Text.AlignHCenter
                text: page.status === "error"
                      ? qsTr("检查没能完成，稍后再试一次吧。")
                      : qsTr("真棒，您已更新到最新版本！")
            }

            /*! ClassIsland 的这条按钮任何时候都在（这是最新那个 Tab 里），
                点开是当前版本自己的更新日志。 */
            Rin.Button {
                objectName: "updateShowChangelogButton"
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("查看更新日志")
                onClicked: changelogDialog.open()
            }
        }
    }

    // ---- Tab 2：更新设置 ----
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 6
        visible: tabs.currentIndex === 1
        enabled: !page.working

        /*! 更新模式（ClassIsland 的 ``Settings.UpdateMode``：0 从不 /
            1 检查并通知 / 2 检查并下载 / 3 检查并安装）。2 / 3 在部署接入
            之前与 1 等效（见 ``Backend.autoCheckUpdates``）。 */
        Rin.SettingExpander {
            objectName: "updateModeExpander"
            Layout.fillWidth: true

            icon.name: "ic_fluent_arrow_download_20_regular"
            title: qsTr("更新模式")
            description: qsTr("设置应用的更新模式。")

            content: Rin.ComboBox {
                Layout.preferredWidth: 190
                model: [
                    qsTr("从不自动更新"),
                    qsTr("自动检查更新并通知"),
                    qsTr("自动检查更新并下载"),
                    qsTr("自动检查更新并安装")
                ]
                currentIndex: Backend.settings.update_mode === undefined
                    ? 1 : Backend.settings.update_mode
                onActivated: Backend.setSetting("update_mode", currentIndex)
            }
        }

        /*! 更新通道（ClassIsland 的 ``SelectedUpdateChannelV3`` + 通道说明 +
            「强制检查更新」）。说明行与入口都收在展开区里。 */
        Rin.SettingExpander {
            objectName: "updateChannelExpander"
            Layout.fillWidth: true
            expanded: true

            icon.name: "ic_fluent_globe_20_regular"
            title: qsTr("更新通道")
            description: qsTr("控制应用的更新目标版本。版本的发行节奏和稳定程度"
                              + "因更新通道而异，部分通道可能包含不稳定的功能，"
                              + "请谨慎使用。")

            content: Rin.ComboBox {
                Layout.preferredWidth: 150
                model: page.updateChannels
                textRole: "name"
                currentIndex: {
                    var index = 0
                    for (var i = 0; i < page.updateChannels.length; ++i) {
                        if (page.updateChannels[i].id
                                === Backend.settings.update_channel) {
                            index = i
                            break
                        }
                    }
                    return index
                }
                onActivated: Backend.setSetting(
                    "update_channel", page.updateChannels[currentIndex].id)
            }

            /*! 通道说明行（ClassIsland 展开区第一项就是一段描述文字）。 */
            Rin.SettingItem {
                objectName: "updateChannelDescItem"
                title: page.selectedChannel.name
                description: page.selectedChannel.description
            }

            /*! 强制检查更新（``CheckUpdateAsync(isForce: true)``）：即使远端
                版本不比当前新也按「有更新」处理。 */
            Rin.SettingItem {
                objectName: "updateForceCheckItem"
                title: qsTr("强制检查更新")
                description: qsTr("强制将应用更新到当前通道上的最新版本，"
                                  + "即使此版本比应用当前版本更旧。")
                actionIcon.name: "ic_fluent_arrow_sync_20_regular"
                clickable: true

                onClicked: {
                    page.deployNotice = false
                    Backend.requestCheckUpdate(true)
                }
            }
        }
    }

    // ============================================================ 更新日志框
    /*! 「查看更新日志」的对话框：照「关于」页诊断信息框的骨架
        （RinUI 标准底栏 + ScrollableTextArea），宽度收到 640 就够。 */
    Rin.Dialog {
        id: changelogDialog

        objectName: "updateChangelogDialog"
        title: qsTr("更新日志")
        modal: true

        readonly property int dialogWidth: 640

        implicitWidth: Math.min(
            changelogDialog.dialogWidth,
            Math.max(0, QQC2.Overlay.overlay.width - 16))

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            Rin.ScrollableTextArea {
                objectName: "updateChangelogBox"
                Layout.fillWidth: true
                Layout.preferredHeight: 320
                readOnly: true
                font.pixelSize: 13
                text: page.changelogText()
            }
        }

        footer: Rin.DialogButtonBox {
            Rin.Button {
                Layout.fillWidth: true
                Layout.preferredWidth: parent.availableWidth
                text: qsTr("关闭")
                onClicked: changelogDialog.close()
            }
        }
    }
}
