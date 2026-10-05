import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    设置 → 更新：**一比一复刻 ClassIsland 的更新页**
    （``ClassIsland/Views/SettingPages/UpdateSettingsPage.axaml`` +
    ``UpdateSettingsPage.axaml.cs``，2026-10-05 用户指令「参阅 ClassIsland
    的排版，补全检查更新机制和界面，目前先不要实现更新部署，外观要一比一
    复刻」）。逐段对应关系：

    * **头部状态区**（axaml 顶部那个 ``Grid ColumnDefinitions="Auto *"``）：
      48px 的状态大图标 + 24px Medium 的状态大字 + 副行，全部照抄 —— 图标随
      结论换（已是最新 = 对勾圆 / 有更新 = 下载 / 其余 = 同步），副行在「已是
      最新」时显示「上次检查更新时间：…」、有更新时换成「发现新版本：…」。
      图标到文字的间距是原版的 ``Margin="0 0 4 0"``（**只有 4**，别按 Fluent
      习惯放宽到 12/16）。唯一的小动作：ClassIsland 只在**下载**时让图标自转，
      这里把自转放宽到任何「正在工作」的档（目前只有检查）—— 检查时一个静止的
      同步图标配上转圈的进度条很怪，自转读起来才像「正在查」。
    * **InfoBar**：错误条照抄（标题「出错了」+ 正文「更新时发生网络错误，请
      检查您的网络连接。」，细节另附）；「更新将在重启后应用」属于部署环节，
      **部署未实现、没有这一条**；多一条本项目自己的 Warning 条 ——
      「下载更新」点了之后亮出来（部署占位，见下）。⚠️ RinUI 的 ``InfoBar``
      自带关闭钮只会播退出动画、没有可接的信号，而且动画结束会把 ``opacity``
      写死在 0（绑定没了），之后这条既看不见又占着布局位。所以两条都用
      ``CloseableInfoBar`` 包装：``closable: false`` 关掉自带钮，右上角自摆
      一枚 dismiss（外观位置与 WinUI/ClassIsland 的同款），关闭直接摘掉整条。
    * **按钮组**（``WrapPanel`` → ``Flow``）：结论为已是最新 → 强调色
      「检查更新」；有更新 → 强调色「下载更新」+ 普通「检查更新」
      （ClassIsland 用两个互斥的可见性绑定分别挂两枚「检查更新」）。工作中整组
      **disabled**（ClassIsland 把 WrapPanel 的 IsEnabled 钉在 Idle 上，是变灰
      不是藏起来）。⚠️ 有更新档的文案是「**下载更新**」而不是「下载并安装」：
      原版的下载与安装是**两枚按钮**（``UpdateAvailable`` → 下载更新，
      ``UpdateDownloaded`` → 安装更新，另有 ``UpdateDeployed`` → 重启并应用
      更新），部署那一档尚未接入，只保留前者。「下载更新」是**占位**：点了
      亮 Warning 条说明情况；部署接入时再补「安装更新」「重启并应用更新」。
    * **进度区**：工作中出现不确定态进度条 + 工作状态文字
      （「正在检查更新…」，对应 ``UpdateWorkingStatusToMessageConverter``）。
      「查看下载状态 / 取消」两枚按钮属于下载档，随部署一起加。
    * **分隔线 + 双 Tab**（``TabControl Classes="compact"`` →
      ``SelectorBar``）：RinUI 没有 TabView/TabControl，
      ``SelectorBar``（Fluent 的选择条，下划线选中态）是与 compact
      TabControl 最接近的一档：
      * **更新日志**：有更新 → 直接铺更新日志（Markdown）；其余档 → 居中的
        81×81 贴图 + 「已经是最新版啦，真棒，夸夸你哦♪」（对应 ClassIsland 那张
        HoYo 贴图；本项目用 ``resources/up_to_date.png``，同尺寸 81）。
        ⚠️ 原版这块
        **没有**「查看更新日志」按钮（它看的是当前版本的日志，与本页「新版
        日志」方向相反），所以这里也不加。⚠️ ClassIsland 的日志在 Tab 内**自成
        滚动**（MarkdownScrollViewer），这里直接铺在页面里、靠页面本身滚
        （FluentPage 自带 Flickable）：页面里再嵌一个 Flickable 会跟页面滚动
        抢滚轮，版式收益却只有「滚到顶后接着滚日志」。
      * **更新设置**：两张 ``SettingExpander`` —— 「更新模式」（下拉四档，
        对应 ``Settings.UpdateMode``）与「更新通道」（下拉稳定/预览 +
        通道说明行 + 「强制检查更新」入口，对应
        ``SelectedUpdateChannelV3`` 与 ``CheckUpdateAsync(isForce)``）。
        通道下拉的候选在 ClassIsland 来自发行服务器的元数据；本项目通道是
        静态两档（见 ``update_channels``），说明文案与
        ``app/update_checker.py::CHANNELS`` 同一份口径。
      * ClassIsland 还有一个仅开发版可见的「(debug)调试设置」Tab（覆盖发行
        服务器根 Url / 子频道 / 公钥）。那三个开关绑的是 ClassIsland 自家的
        PDC，本项目走 GitHub Releases，没有对应物，**不做**。

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

    /*! 通道候选与说明**不在这里定义** —— 唯一一份在 Python 侧
        （``app/update_checker.py::CHANNELS`` / ``CHANNEL_NAMES``），由
        ``Backend.updateChannels`` 发出。这样「下拉显示名」「说明文案」
        「过滤语义」三处永远同源。（原先本页有一份 QML 字面量，经
        ``Loader.setProperty`` 推给子项时会被包成空 QJSValue，见
        ``UpdateSettingsTab.qml`` 注释。） */

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
    /*! 原版是 ``Grid ColumnDefinitions="Auto *" RowDefinitions="Auto Auto"``：
        48px 图标占第 0 列并 ``RowSpan=2`` 垂直居中，**右边距只有 4**（不是
        Fluent 常见的 12/16）—— 图标与状态大字贴得比较近，这是 ClassIsland
        那一版的原样，别按直觉放宽。

        ⚠️⚠️ **这个 ``RowLayout`` 必须直接当 ``FluentPage`` 的子项，别用
        ``Item`` 包一层再 ``anchors.fill``。**

        踩过的样子（2026-10-05）：写成
        ``Item { implicitHeight: rowLayout.implicitHeight; RowLayout { anchors.fill: parent } }``
        之后，``RowLayout`` 量到的宽度是对的（807），但它**不给 ``ColumnLayout``
        分配 ``Layout.fillWidth``** —— 文字列停在隐式宽 240，还被推到 x=138，
        于是图标与文字之间空出**一大片约 86px**（用户圈着问「这么大的空」）。

        原因是那个环比循环：``Item`` 的高由布局的 ``implicitHeight`` 决定，
        而布局的高又由 ``anchors.fill`` 回到 ``Item``；Qt 解环时会用一份
        **不完整**的几何跑布局，布局内部对「剩余空间怎么分」的判断就跟着错
        （实测剩余空间被按两者隐式宽**按比例**分给了图标和文字列 ——
        图标尺寸从 48 改到 20，空档也从 86 掉到 42，正是这个比例在作怪）。

        布局当「布局的儿子」是 Qt Quick Layouts 的正常用法，``implicitHeight``
        也天然由内容决定（56），不必再包一层。 */
    RowLayout {
        objectName: "updateStatusHeader"
        Layout.fillWidth: true
        /*! 图标 ↔ 文字的横向间距。
            ClassIsland 原版这里是 ``Margin="0 0 4 0"``（只有 4）—— 2026-10-05
            实测下来用户觉得**贴得太近**（48px 图标紧挨 24px 大字），改成 12。
            这个值就在这一行，觉得还要松/紧直接调它。 */
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
            objectName: "updateStatusColumn"
            /*! 吃掉中间所有余量 —— 按钮组因此被顶到最右边
                （``Layout.alignment: Qt.AlignRight`` 那条路在这里不适用：
                填充项自己会抢宽，见文件里「别拿自身不填宽当右对齐」的说明）。 */
            Layout.fillWidth: true
            spacing: 4

            Rin.Text {
                objectName: "updateStatusText"
                Layout.fillWidth: true
                font.pixelSize: 24
                font.weight: Font.Medium
                text: page.statusMessage
            }

            /*! 副行：已是最新（含没查过 / 失败）→ 上次检查时间；
                有更新 → 新版本号（对应 axaml 里两段互斥的 ``Run``）。 */
            Rin.Text {
                objectName: "updateStatusSubText"
                Layout.fillWidth: true
                color: Lumi.textSecondary
                text: page.isAvailable
                    ? qsTr("发现新版本：%1").arg(Backend.updateLatestVersion)
                    : qsTr("上次检查更新时间：%1").arg(
                          Backend.updateLastCheckTime !== ""
                          ? Backend.updateLastCheckTime : qsTr("从未"))
            }
        }

        // ---- 按钮组：贴在状态区右侧（用户 2026-10-05：右侧空着，挪过来）----
        /*! 与标题行同一水平线、垂直居中。工作中整组变灰（不是藏起来）。

            ⚠️ 原版 ClassIsland 是把按钮放在状态区**下方**的一个 ``WrapPanel`` 里
            （左对齐、每枚 ``Margin="4"``）。这里按用户要求挪到右侧 —— 右侧本来
            整条空着，状态大字又短，按钮挂在下面对着左边缘显得头重脚轻。
            改回左下的方式：把这段整个搬到 ``updateProgressRow`` 之前即可。 */
        RowLayout {
            objectName: "updateButtonRow"
            Layout.alignment: Qt.AlignVCenter
            spacing: 8
            enabled: !page.working

            /*! 已是最新 → 强调色「检查更新」。没查过（unknown）也给这枚：
                空着按钮行会像坏了。ClassIsland 的条件写死成
                ``LastUpdateStatus == UpToDate``，本项目另有两档（unknown / error）
                同样需要入口，否则这两档下按钮行全空。 */
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

            /*! 有更新 → 强调色「下载更新」（部署占位，见文件头注释）+ 普通检查。
                ⚠️ 文案是「下载更新」不是「下载并安装」：原版这两个动作是**两枚
                按钮**（``UpdateAvailable``→下载 / ``UpdateDownloaded``→安装），
                部署那一档尚未接入，只保留前者。 */
            Rin.Button {
                objectName: "updateDownloadButton"
                visible: page.isAvailable
                highlighted: true
                text: qsTr("下载更新")
                onClicked: page.deployNotice = true
            }

            Rin.Button {
                objectName: "updateRecheckButton"
                visible: page.isAvailable
                text: qsTr("检查更新")
                onClicked: {
                    page.deployNotice = false
                    Backend.requestCheckUpdate(false)
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
        // 原版是「标题=出错了 / 正文=更新时发生网络错误，请检查您的网络连接。」
        // 下面再附本项目抓到的具体异常（ClassIsland 那边只有异常对象、
        // 不显示内容，所以正文到「网络连接」为止）。
        title: qsTr("出错了")
        text: qsTr("更新时发生网络错误，请检查您的网络连接。")
              + (Backend.updateError !== "" ? "\n" + Backend.updateError : "")
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

    /*! 「下载更新」被点过之后亮 Warning 条；关掉按钮或重开页面就复位。 */
    property bool deployNotice: false

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
    /*! ClassIsland 的 ``Separator/>``：普通 1px 线。

        ⚠️ **上方这 18px 是补按钮搬走留下的空**，不是随手加的。
        原版里状态区与分隔线之间夹着**一整行按钮**（``WrapPanel``：按钮 32 高 +
        上下各 ``Margin=4``），实际间距是 ``6 + 40 + 6 = 52``；按钮被挪到页头右侧
        之后这段就只剩页面统一的 6px，目检「分割线直接贴上去了」——
        用户 2026-10-05 指出的就是这里。

        补到 **24px**（页面 ``contentSpacing`` 的 6 + 这里 18）：
        比原版那 52 收得多，因为按钮已经不在这一层了、不必再为它留位；
        但明显大于 6，状态区与 Tab 之间才有一道呼吸。
        下方保持 6（分隔线紧接 Tab 是原版的样子）。 */
    Rectangle {
        objectName: "updateSeparator"
        Layout.fillWidth: true
        Layout.topMargin: 18
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

        /*! 已是最新：居中的空状态（对应 ClassIsland 那张 81×81 的 HoYo 贴图 +
            一句夸）。贴图用 ``resources/up_to_date.png``（2026-10-05 用户备好，
            162×162、带 alpha，显示尺寸 81 —— 与原版同规格）。
            ⚠️ 文案照抄原版的「已经是最新版啦，真棒，夸夸你哦♪」。原版这块
            **没有**「查看更新日志」按钮（它看的是当前版本的日志，与本页
            「有新版的日志」是相反方向），所以这里也不加。

            ⚠️ 居中靠 ``Layout.fillWidth: true`` + 子项 ``AlignHCenter``，
            **不要**用「自身不填宽 + ``Layout.alignment: AlignHCenter``」那套：
            那样外层 ``ColumnLayout`` 会按内容宽度收缩，整块贴到左边
            （实测：图标与文字全挤在 x≈88，右侧空一大片）。原版是
            ``VerticalAlignment=Center`` + ``HorizontalAlignment=Center``，
            即「占满可用宽度、里面居中」，QML 这边对应写法就是下面这样。 */
        ColumnLayout {
            objectName: "updateUpToDatePanel"
            Layout.fillWidth: true
            Layout.topMargin: 50
            Layout.bottomMargin: 50
            spacing: 8
            visible: !page.isAvailable

            /*! ⚠️ 位图贴图要用 ``Image``，别套 ``Rin.Icon`` —— 后者是**字体图标**
                组件（``name`` 查 FluentSystemIcons 码位表），塞图片路径进去只会
                画出一个问号/空字。 */
            Image {
                objectName: "updateUpToDateImage"
                Layout.alignment: Qt.AlignHCenter
                source: Backend.resourceFile("up_to_date.png")
                /*! ⚠️ 尺寸要用 ``Layout.preferredWidth/Height``，**不能写 ``width``**：
                在 Layout 里项宽由布局按「隐式尺寸」决定，``width`` 会被直接覆盖
                （``Image`` 的隐式尺寸 = 原图 162）→ 贴图会按 162 画。实测把
                ``width: 81`` 留下的那次，探针量到 **162×162**。

                ⚠️ 也别用 ``sourceSize`` 去凑：它是**解码尺寸**不是显示尺寸，
                设成 81 会让纹理只解到 81px，而 81 逻辑像素在本机 DPR 1.75 下要画成
                ~142 物理像素 → 放大 1.75 倍，糊。不设则按 162 解码、缩到 142 绘制。 */
                Layout.preferredWidth: 81
                Layout.preferredHeight: 81
                fillMode: Image.PreserveAspectFit
                mipmap: true
                smooth: true
            }

            Rin.Text {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                horizontalAlignment: Text.AlignHCenter
                // 原版只在 UpToDate 档显示这句；本项目多两档，得各给一句，
                // 免得没查过时也说「您已更新到最新」。
                text: page.status === "error"
                      ? qsTr("检查没能完成，请检查网络后重试。")
                      : page.status === "unknown"
                      ? qsTr("还没有检查过更新。")
                      : qsTr("已经是最新版啦，真棒，夸夸你哦♪")
            }
        }
    }

    // ---- Tab 2：更新设置 ----
    /*! ⚠️ 必须走 ``Loader`` 而不是「一段 ColumnLayout + ``visible`` 切换」：
        RinUI ``SettingItem`` 左栏的可见性是绑定
        （``visible: titleLabel.visible || descriptionLabel.visible``，而这两个
        又看 ``title.length > 0``）。整段初始 ``visible: false`` 时，构造期
        求值拿到空串 → 左栏被判成「无内容」整层隐藏；等 Tab 切过来
        ``visible`` 翻 true，**这一层不会重新求值** —— 标题和描述都传对了、
        高度也正常，却一个字不画（实测 ``updateForceCheckItem``
        title='强制检查更新'、height=50，内部 ``RowLayout.visible == false``）。
        ``Loader`` 让这些控件在**选中那一刻才构造**，绑定一次求对；
        顺带没点开的 Tab 不进渲染循环。详见
        ``ui/settings/UpdateSettingsTab.qml`` 的文件头注释。 */
    Loader {
        id: settingsTab
        objectName: "updateSettingsTab"
        Layout.fillWidth: true
        active: tabs.currentIndex === 1
        /*! ⚠️⚠️ 这里**不要**再写 ``visible: active`` —— 它正是下面那个
            「有高度没字」的元凶。

            RinUI ``SettingItem`` 里左栏的可见性是
            ``visible: titleLabel.visible || descriptionLabel.visible``。而 QML 的
            ``Item.visible`` 是**有效可见性**（实测：父项不可见时子项读出来的
            ``visible`` 也是 ``false``，另外 ``isVisible()`` 同理）。也就是说
            这个绑定读的是**后代的有效可见性**，而后代的可见性又由它自己的祖先
            决定 —— **落在自家子树里，成环**。

            于是只要构造那一刻「祖先链里有谁不可见」，它就锁死在 ``false``，
            之后标题改对、高度也算得对，却一个字不画。``visible: active`` 恰好
            制造了这个时刻：``active`` 与 ``visible`` 同源，引擎先算 ``active``
            → 立刻建子项，而这一拍 Loader **自己还是不可见的** → 子项全判成
            不可见，环锁死。

            ``active: false`` 时 Loader 本来就会卸掉子项、尺寸归零，
            ``visible`` 是多余的。删掉它，子项就一定是在「自己在可见链上」
            的时刻被构造出来的。
            （2026-10-05 实测：删掉之前 ``updateChannelDescItem`` /
            ``updateForceCheckItem`` 内部的 Text 全是 ``visible=false``，
            图上那两行空白；删掉之后正常。） */
        // 工作中禁用（ClassIsland 把 TabControl 的 IsEnabled 钉在 Idle 上）
        enabled: !page.working

        /*! 子项自己读 ``Backend.updateChannels``（Python 侧唯一一份通道表）
            与 ``Backend.settings.update_channel``，页面这边**不做任何注入**：
            一来 QML 的 ``var`` 属性经 ``setProperty`` 收 JS ``Array`` 会被包成
            空 QJSValue（子项遍历得 0 → 通道表空 → 说明行双空，2026-10-05 实测），
            二来省掉一条「构造期谁先算好」的时序依赖。详见子项文件头注释。 */
        source: "UpdateSettingsTab.qml"

        onStatusChanged: {
            if (status === Loader.Error) {
                console.warn("[Update] 更新设置 Tab 加载失败:", source)
            }
        }
    }
}
