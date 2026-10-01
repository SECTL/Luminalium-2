import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    关于页：流光英雄区（L1 同款）+ 应用信息卡。

    ## 一、流光英雄区（2026-10-01 用户指令「给设置的关于界面上安排
    Luminalium 1 的同款流光背景 Logo 混色效果」）

    版式／配色／动效全部照 Luminalium 1 插件式设置页
    （``plugins/builtins/settings/settings.html`` 的 ``#section-about``）复刻，
    逐条对照与实现细节写在两个组件的头注释里：

    * ``Luminalium.AuroraFlow`` —— ``.hyperos-bg``：10 层 radial-gradient 的
      200% 画幅 + ``blur(60px)`` + 25s 匀速自转、中点放大到 1.1；
    * ``Luminalium.GlassLogo`` —— ``.about-main-logo``：两层半透明白渐变
      （``::before`` 160deg / ``::after`` 180deg）按剪影蒙版叠在流光上
      —— 也就是「混色」；外挂 accent 光晕与整体投影。
      ⚠️ L1 的 ``backdrop-filter`` 是**空转**的（CSS 的 Backdrop Root 规则，
      已实测只有 3/255 的差别），所以这里没有采背景那一层，细节见组件头注释。

    ⚠️ 英雄区**没有**走 ``FluentPage.contentHeader``。那个槽名义上是「页面级
    全宽」的，但实测（2026-10-01，``page_About`` 用红底试色）Item 会被塞进内容
    列 ``container``，宽度受 ``horizontalPadding`` 夹到 846 并居中 —— 与普通
    content 无异，白折腾。所以这里就用普通的 content 子项：宽度跟随内容列，
    靠**圆角 + 强调色底**把它读成一张横幅。

    页面**不带标题**（2026-10-01 用户指令「把关于大标题去掉」）。机制：
    ``Rin.FluentPage`` 的头部高度是 ``title !== "" ? 36 + 44 : 0``，所以不写
    ``title`` 头部会整个塌成 0，英雄区直接顶到内容区顶部 —— 这里也顺带更贴 L1：
    L1 的 ``#section-about`` 本身就是**光秃秃一块英雄区**，上方没有小节标题。
    左侧导航里的「关于」项照旧（那是 ``navigationItems`` 的 ``title``，与页面
    标题是两码事，别一起删）。

    ⚠️ 圆角是**四角统一** 16，L1 原值是 ``16px 16px 0 0``（上圆下直）：L1 那块
    是出血横幅（左右各多 48、顶上顶出 32，下沿直接接下一组设置），本项目是张
    内嵌卡，照抄会让下沿像被切一刀。理由与原文都记在 ``Lumi.qml`` 的
    ``aboutHeroRadius`` 上方。

    ## 二、应用信息卡（2026-10-01 用户指令「参考 Class Widgets 2 的关于界面的
    那个设置卡，填充关于界面的内容」）

    **版式**照 CW2 ``src/qml/ClassWidgets/pages/settings/About.qml`` 的那张主卡：
    一张 ``Rin.SettingExpander``——头部是「图标 + 应用名 + 版权描述」、右栏塞
    渠道徽章与版本，展开后是一串 ``Rin.SettingItem``（仓库 / 反馈 / 依赖）。

    ⚠️ ``content:`` 那一格是**卡片头部的右栏**（CW2 在那儿放渠道徽章），
    折叠区才是下面那串 ``SettingItem``（走 Expander 的 default property）。别把
    两者搞反：往 ``content:`` 里塞 SettingItem 是不会进折叠区的。

    **内容**按本项目实际改写，不是照抄 CW2：CW2 是 ``Class Widgets 2`` / GPL-3 /
    Loguru + Pydantic；本项目是 ``Luminalium 2`` / MIT / Qt 系（PySide6 +
    pywin32）。依赖清单只留本项目**真的在用**的东西，照抄会变成假信息。

    ### 同一轮的几处口径（2026-10-01，用户逐条指定）

    * **徽章只区分渠道**：``Dev`` / ``Release``，值来自 ``app.channel``
      （``Backend.appChannel``，默认 ``Dev``）。它**不再**顺带显示开发代号。
    * **开发代号跟在版本号后面的括号里**：``1.6.633.1（Codename AwaSubaru）``。
    * **仓库地址在打开按钮的左边**，用系统自带的等宽字体（Consolas）。
    * **依赖与参考的标题与内容上下换行**（原来是左右并排）。
    * 版权署名 ``Seirai Haraguchi / @SECTL Studio``。
    * **许可相关内容全部移出**：先删掉页内那张「MIT 许可证」展开卡（因此
      ``Backend.licenseText`` 与其 ``_license_text`` 缓存一并删除），随后按
      「关于界面的开源许可关掉」把最后那条外链项（``aboutLicenseItem``）也去掉。
      版权与许可证口径只保留在卡片头部 ``description`` 的那两行里。
*/
Rin.FluentPage {
    id: aboutPage

    contentSpacing: 10

    /*! 两条外链。集中在这里而不是散在下面：自检要在树里比对它们，
        以后换组织名也只改这一处。
        （第三条 ``licenseUrl`` 已随「开源许可」那一项一起删除 —— 2026-10-01。） */
    readonly property string repoUrl: "https://github.com/SECTL/Luminalium-2"
    readonly property string issuesUrl: repoUrl + "/issues/new/choose"

    /*! 英雄区 = 一块圆角底板 + 流光 + Logo。
        底板取 ``Lumi.auroraSurface``，也就是 L1 ``--bg-surface`` 那一档
        （深色主题下 = 强调色压暗到 30%）。十团光斑只比它亮一点点，所以「板」
        是整块的强调色底、光斑是上面缓慢流动的深浅变化 —— 和 L1 里头图与页面
        同色时的关系一致；本项目页面是中性灰（#202020），这块底才需要靠圆角
        被读成**刻意的横幅**而不是「页面上一块色斑」。 */
    Item {
        id: hero

        objectName: "aboutHero"
        Layout.fillWidth: true
        Layout.preferredHeight: Lumi.aboutHeroHeight
        implicitHeight: Lumi.aboutHeroHeight

        Rectangle {
            id: heroSurface
            anchors.fill: parent
            radius: Lumi.aboutHeroRadius
            color: Lumi.auroraSurface

            /*! 流光自带圆角蒙版 —— 别指望 ``heroSurface`` 的 ``clip: true``：
                Qt 的裁剪是**矩形**的，不认 ``radius``，圆角会被流光的实色方块
                盖成直角（踩过）。 */
            AuroraFlow {
                objectName: "aboutAurora"
                anchors.fill: parent
                cornerRadius: Lumi.aboutHeroRadius
                fadeHeight: Lumi.aboutHeroFade
            }
        }

        /*! Logo 在英雄区正中（L1：420×420 的容器压着 320 高的头图，Logo 实际
            就居中落在 36~284 之间；超出部分被流光的圆角蒙版一并裁掉）。 */
        GlassLogo {
            id: aboutLogo

            objectName: "aboutLogo"
            anchors.centerIn: parent
            width: Lumi.aboutLogoSize
            height: Lumi.aboutLogoSize
            maskUrl: Backend.resourceFile("logo_grayscale.svg")
        }
    }

    /*! 分组小标题：与「通用」「主界面」等页同一层级（``BodyStrong``）。
        CW2 的关于页也是「About」小标题 + 卡片这个组合。 */
    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("关于")
    }

    /*! 应用信息卡。详见文件头注释第二节。 */
    Rin.SettingExpander {
        id: appCard

        objectName: "aboutAppCard"
        Layout.fillWidth: true

        /*! 默认**展开**（CW2 那张是收起的）：关于页进来就是来看版本、找仓库、
            看依赖的，内容直接摆在眼前比再点一下强。 */
        expanded: true

        /*! 图标用仓库里的彩色 ``logo.svg``：**别**开 ``enableColorOverlay``
            —— 那是给单色图标适配主题用的，会把这个彩色 Logo 糊成一片纯色。 */
        icon.source: Backend.resourceFile("logo.svg")
        icon.size: 28

        title: Backend.appName
        description: qsTr("© 2025-2026 Seirai Haraguchi / @SECTL Studio")
                     + "\n" + qsTr("本程序基于 MIT License 获得许可")

        /*! 头部右栏：渠道徽章 + 版本行（对应 CW2 的渠道徽章 + 版本）。
            徽章**只**表达渠道；开发代号挪到版本号后面的括号里。 */
        content: RowLayout {
            spacing: 8

            Rin.InfoBadge {
                objectName: "aboutChannelBadge"
                text: Backend.appChannel
            }

            Rin.Text {
                objectName: "aboutVersionText"
                typography: Rin.Typography.Body
                color: Lumi.textSecondary
                text: Backend.appVersion
                      + qsTr("（Codename %1）").arg(Backend.devCodename)
            }
        }

        /*! 仓库地址在**打开按钮的左边**：右栏先放地址文本（系统等宽字体），
            再是 ``actionIcon`` 那枚外链图标。整行可点。 */
        Rin.SettingItem {
            objectName: "aboutRepoItem"

            title: qsTr("查看本仓库")
            actionIcon.name: "ic_fluent_open_20_regular"
            clickable: true

            Rin.Text {
                objectName: "aboutRepoUrl"
                typography: Rin.Typography.Caption
                font.family: "Consolas"
                color: Lumi.textSecondary
                text: aboutPage.repoUrl
            }

            onClicked: Qt.openUrlExternally(aboutPage.repoUrl)
        }

        Rin.SettingItem {
            objectName: "aboutIssuesItem"

            title: qsTr("反馈问题或功能建议")
            description: qsTr("在 GitHub 上提交 Issue")
            actionIcon.name: "ic_fluent_open_20_regular"
            clickable: true

            onClicked: Qt.openUrlExternally(aboutPage.issuesUrl)
        }

        /*! 依赖与参考：**标题在上、链接在下**（原来是左右并排）。
            做法是 ``title`` / ``description`` 都留空 —— 左栏于是
            ``visible: false``，``SettingItem`` 中间那个
            ``Item { Layout.fillWidth: leftContent.visible }`` 不占宽，
            右栏就从左边起排；标题由右栏里的 ``ColumnLayout`` 自己画。
            ⚠️ 别用「往 title 里塞换行」之类的招：SettingItem 的标题
            ``maximumLineCount: 2`` + ``ElideRight``，会截。 */
        Rin.SettingItem {
            objectName: "aboutDepsItem"

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                Rin.Text {
                    objectName: "aboutDepsTitle"
                    Layout.fillWidth: true
                    typography: Rin.Typography.Body
                    text: qsTr("依赖与参考")
                }

                /*! ``Rin.Hyperlink`` 是 ``flat`` 的 ``Button``，自带 ~44 的最小
                    高度，竖排五个会把这行撑到 250 高。这里统一压到 26 —— 只动
                    高度，不碰 ``background``（铁律）。 */
                Rin.Hyperlink {
                    objectName: "aboutDepsLink0"
                    Layout.preferredHeight: 26
                    text: qsTr("Qt & Qt Quick")
                    openUrl: "https://www.qt.io/"
                }
                Rin.Hyperlink {
                    Layout.preferredHeight: 26
                    text: qsTr("Qt for Python（PySide6）")
                    openUrl: "https://doc.qt.io/qtforpython-6/"
                }
                Rin.Hyperlink {
                    Layout.preferredHeight: 26
                    text: qsTr("Fluent Design System")
                    openUrl: "https://fluent2.microsoft.design/"
                }
                Rin.Hyperlink {
                    Layout.preferredHeight: 26
                    text: qsTr("RinUI")
                    openUrl: "https://ui.rinlit.cn/"
                }
                Rin.Hyperlink {
                    Layout.preferredHeight: 26
                    text: qsTr("pywin32")
                    openUrl: "https://github.com/mhammond/pywin32"
                }
            }
        }

        /*! 许可：**没有这一项**。2026-10-01 用户先删了页内那张「MIT 许可证」展开卡，
            随后又指令「关于界面的开源许可关掉」，于是连这条外链也一并去掉。
            页面的 ``licenseUrl`` 属性同时删除（没有界面再用它，留着就是死代码）。
            版权与许可证信息仍留在卡片头部（``description`` 那两行）。 */
    }
}
