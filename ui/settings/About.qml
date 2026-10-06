import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    关于页：流光英雄区（L1 同款）+ 应用信息卡 + 回声洞 + 诊断信息。

    三、四两节是 2026-10-04 用户指令「参考 Luminalium 1 给关于页加回声洞，
    再像 ClassIsland 那样加一条显示诊断信息的入口」的产物。两者都**照 L1 的
    交互原样复刻**，不是自己发挥的静态卡片：

    ## 三、回声洞（L1 ``plugins/builtins/settings/settings.html`` 的
    ``#echo-cave-item``）

    L1 那一条的形态与状态机（逐条对齐，别简化）：

    * 一行**可点击的设置项**：左栏「回声洞」标题 + 下面一行内容区
      （``.echo-cave-content``），右栏一枚「复制」按钮；
    * 初始内容是提示语「点击卡片获取回声洞句子」，复制按钮**不显示**；
    * 点击整行 → 内容变「获取中...」且**整行半透明**（``.loading{opacity:.5}``），
      复制按钮继续藏着；
    * 取到句子 → **逐字打字机**（``typewriteText(el, text, 50)``，50ms/字），
      期间行尾有一个**强调色闪烁光标**（``::after{content:"|"}`` +
      ``echoCaveBlink .7s steps(1)``，即 350ms 半周期）；
    * 打字**打完**才让「复制」出现（L1 是 ``await typewriteText`` 之后才
      ``display:''``）；点它复制全文，按钮自己变「已复制」1.5s 再变回来；
    * 取不到 → 「暂无回声洞」；出错 → 「获取失败，请稍后重试」。

    ⚠️ **取句是异步的**（``Backend.requestEchoCave`` → 后台线程 →
    ``echoCaveResult`` 信号）。同步返回的话「获取中...」根本没机会画出来 ——
    L1 用 ``await fetch()`` 拿到的正是这个效果。

    ⚠️ 光标必须和正文**同一段文字流**：L1 是 CSS ``::after``，跟着换行走到行尾。
    这里用 ``textFormat: Text.RichText`` 把光标拼进正文（颜色取 ``Lumi.accent``，
    见 ``cursorMarkup``），而不是在旁边另摆一个 ``Text`` —— 后者在正文折行时会
    停在整块文字的垂直中线上，离行尾十万八千里。

    ## 四、诊断信息（L1 的 ``showDiagnosticInfo()`` + ``#diagnostic-modal``）

    同样是「一行入口 + 一个模态框」，不是把一堆文本直接摊在页面上：

    * 入口是一张**独立的** ``Rin.SettingCard``「查看诊断信息」（2026-10-04
      用户指令：「查看诊断信息那一个卡移出程序信息那一栏」—— 原先它是应用信息卡
      里的一个 ``SettingItem``，现在单独成卡），``clickable`` 让它自带右向
      chevron —— 与 L1 ``about.diagnostic.label`` 那一行一致；
    * 点开是 ``Rin.Dialog``：标题「诊断信息」→「加载中...」→ **只读多行文本框**
      （2026-10-04 用户指令：「打开的 dialog 要是 ClassIsland 的那种，dialog
      内套文本框」；ClassIsland 的诊断信息窗就是一个只读多行 TextBox + 底部按钮，
      所以这里从「键值表格」改成了文本框）。文本框用 ``Rin.ScrollableTextArea``
      而不是 ``Rin.TextArea`` —— 后者不会滚（同日用户指令「滚不动」），
      对话框宽度也在派生组件里重写 ``implicitWidth`` 抬到 880（同日用户指令
      「宽度不够宽」，RinUI 默认上限只有 600）。两处的坑都写在下面正文的注释里；
    * 底栏是 RinUI 的**标准底栏** ``Rin.DialogButtonBox``（2026-10-04 用户指令：
      「RinUI 的 dialog 是有标准样式的，你去看看 RinUI 的用法」），内放「关闭」与
      「复制全部」两枚自定义按钮（复制成 ``Key: Value`` 的逐行文本，按钮自己变
      「已复制」2s）—— 复制的就是文本框里那一份，二者同源（``plainText()``）；
    * 文本框内容与 ClassIsland 的 ``GetDiagnosticInfo()`` **同口径**（2026-10-04
      用户指令：「内容也和 ClassIsland 的那种诊断信息统一」）：英文 PascalCase
      键 + ``Key: Value`` 逐行，**不翻译**；键名能与 ClassIsland 对上的逐字沿用
      （``SystemOsVersion`` / ``SystemDeviceName`` / ``AppCurrentDirectory`` /
      ``AppSubChannel`` …）。框内是英文、窗口文案是中文，看着别扭，但这正是
      ClassIsland 的做法 —— 这份文本要贴进 issue，键名得语言中立。

    ⚠️ 字段采集同样是**异步**的（``Backend.requestDiagnostics``）：硬件查询虽然
    都不起子进程，但没有理由压在 UI 线程上；更要紧的是同步返回就画不出
    「加载中...」。采集器在 ``app/diagnostics.py``（移植 L1 的
    ``diagnostic_info.py``，把 ``wmic`` 换成了注册表 / ``GlobalMemoryStatusEx``）。


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

    同一套「混色」还被复用到右下角的 YUNOFACTORY 字标上（2026-10-05 用户指令，
    见 ``aboutCredits``）—— ``GlassLogo`` 与「Logo」其实无关，它做的就是「一堆
    半透明白渐变按单色剪影蒙形」，换成字标素材、关掉光晕与投影就是一份落款。

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

        /*! 右下角的 YUNOFACTORY 署名字标（2026-10-05 用户指令）。

            **同一套「混色」**：还是 ``GlassLogo`` —— 两层半透明白渐变按剪影蒙出
            字标、叠在流光上（不是拿 ``Image`` 直接画一份实色 SVG，那样在深色底
            上就是一块死白）。区别只有两点：

            * ``glowEnabled`` / ``shadowEnabled`` 都关掉。那两层的模糊半径
              （22 / 28）是给 248 的 Logo 配的，压在 150×23 的字标上只会糊成一
              团；更要紧的是它们的容器四周要外撑 3σ（≈ 42px），而英雄区底部只留
              20 的边距 —— 辉光会**越过卡片的圆角**洒到页面上，卡片的边就没了。
            * ``layerPrefix`` 换成 ``aboutCredits``：两个实例内部的 ``objectName``
              本来一模一样，重名之后自检按名字找「Logo 四层」会翻到字标那四层上
              去 —— 找得到，但量的是别人。

            素材直接用原文件 ``design_by_yunofactory.svg``（「DESIGN BY + 大字标」
            的完整锁定版式），**不裁**：2026-10-05 第一版为了让它可读，把顶上那行
            DESIGN BY 裁掉了，用户明确要求保留 —— 落款就该是完整的那一份，那行小字
            在那个尺寸下本来也只是道细纹。 */

        /*! 尺寸见 ``Lumi.aboutCreditsWidth`` 上方的说明（150 宽 ≈ 英雄区的 19%）。 */
        GlassLogo {
            objectName: "aboutCredits"
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Lumi.aboutCreditsMargin
            width: Lumi.aboutCreditsWidth
            height: width / Lumi.aboutCreditsAspect
            layerPrefix: "aboutCredits"
            glowEnabled: false
            shadowEnabled: false
            maskUrl: Backend.resourceFile("design_by_yunofactory.svg")
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
        description: qsTr("© 2025-2026 Seirai Haraguchi, YUNOFACTORY & SECTL Studio")
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

    // ============================================================ 诊断信息入口
    /*! 2026-10-04 用户指令：「查看诊断信息那一个卡移出程序信息那一栏」——
        原先它是 ``appCard`` 里的一个 ``SettingItem``，现在**单独成卡**，
        不再挂在应用信息卡下面（那是「程序信息」，诊断不是它的子项）。

        这里用 ``SettingCard`` 而不是 ``SettingItem``：``SettingItem`` 是给
        ``SettingExpander`` / 卡片**内部**当行用的（自身没有圆角底板），
        单独摆在页面上会是一行浮在背景上的裸文本；``SettingCard`` 才是
        「独立一张卡」的那一档，与「通用」「个性化」页的卡同规格。

        ``clickable: true`` 会让它自己画上右向 chevron（与 L1
        ``.item-state > .chevron`` 同一套视觉语言），别手动再加图标。 */
    Rin.SettingCard {
        id: diagnosticsCard

        objectName: "aboutDiagnosticsEntry"
        Layout.fillWidth: true

        title: qsTr("查看诊断信息")
        description: qsTr("用于排查问题；分享前请检查其中包含的路径等信息")
        icon.name: "ic_fluent_bug_20_regular"
        clickable: true

        onClicked: diagnosticsDialog.open()
    }

    // ================================================================ 回声洞
    /*! 一行可点击的设置项 —— 版式与状态机照 L1 ``#echo-cave-item`` 逐条复刻，
        说明见文件头注释第三节。 */
    Rin.Frame {
        id: echoCave

        objectName: "aboutEchoCave"
        Layout.fillWidth: true
        // Frame 的 contentItem 没有隐式高度（背景是 Rectangle），高度得自己算：
        // 正文列的自然高 + 上下内边距。正文会随打字机增长，所以这是个活绑定。
        Layout.preferredHeight: echoInfo.implicitHeight + padding * 2
        padding: 16
        hoverable: true

        // 状态机：``hint``（初始提示）→ ``loading`` → ``ok``（打字机 / 已就绪），
        // 另有 ``empty``（池子空）与 ``error``（取句异常）。
        property string status: "hint"
        // 取到的完整句子；打字机从它逐字取前缀。
        property string fullText: ""
        // 打字机当前已经打出来的前缀。
        property string shownText: ""
        property bool typing: false
        property bool cursorOn: true
        // 「复制」按钮的可见性 —— L1 是**打完字**才让它出现，不是取到就出现。
        property bool copyVisible: false
        property bool copied: false

        /*! 光标要用**强调色**，而富文本的 ``<font color>`` 只认 ``#rrggbb``；
            QML 的 ``color`` 直接转字符串会得到 ``#aarrggbb``（带 alpha）。
            所以自己从分量拼，顺带把 alpha 丢掉（光标本来就该是实色）。 */
        function channelHex(value) {
            var n = Math.round(Math.max(0, Math.min(1, value)) * 255).toString(16)
            return n.length < 2 ? "0" + n : n
        }

        function cursorMarkup() {
            var c = Lumi.accent
            return "<font color=\"#" + channelHex(c.r) + channelHex(c.g)
                   + channelHex(c.b) + "\">|</font>"
        }

        /*! 正文可能是任意句子，进富文本前必须转义，否则句子里一个 ``<``
            就会把后半句吃掉（富文本解析器会把它当标签）。 */
        function escapeHtml(text) {
            return String(text)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
        }

        readonly property string displayText: {
            if (status === "hint")
                return qsTr("点击卡片获取回声洞句子")
            if (status === "loading")
                return qsTr("获取中...")
            if (status === "empty")
                return qsTr("暂无回声洞")
            if (status === "error")
                return qsTr("获取失败，请稍后重试")
            // ``ok``：正文 + 打字期间闪烁的光标
            return escapeHtml(shownText)
                   + ((typing && cursorOn) ? cursorMarkup() : "")
        }

        function requestSentence() {
            typeTimer.stop()
            typing = false
            copyVisible = false
            copied = false
            cursorOn = true
            status = "loading"
            Backend.requestEchoCave()
        }

        function applyResult(text, result) {
            if (result !== "ok" || text === "") {
                fullText = ""
                shownText = ""
                status = result === "empty" ? "empty" : "error"
                return
            }
            fullText = text
            shownText = ""
            status = "ok"
            cursorOn = true
            typing = true
            typeTimer.start()
        }

        /*! 整行可点。⚠️ 用 ``MouseArea`` 而不是 ``TapHandler``，并且把它**声明在
            正文之前**（= 叠在下面）：正文列里的「复制」按钮压在它上面，点按钮时
            事件被按钮先接住，不会顺带再取一次句 —— 等价于 L1 那句
            ``if (e.target === echoCaveCopy) return``，但靠层级而不是靠判断。 */
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: echoCave.requestSentence()
        }

        ColumnLayout {
            id: echoInfo
            anchors.fill: parent
            spacing: 0

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                text: qsTr("回声洞")
            }

            Rin.Text {
                id: echoContent
                objectName: "aboutEchoContent"
                Layout.fillWidth: true
                typography: Rin.Typography.Caption
                color: Lumi.textSecondary
                // 光标要跟着文字流走到行尾，只能和正文同一段富文本（见文件头注释）
                textFormat: Text.RichText
                text: echoCave.displayText
                // L1 ``.echo-cave-content.loading { opacity: 0.5 }``
                opacity: echoCave.status === "loading" ? 0.5 : 1

                Behavior on opacity {
                    NumberAnimation { duration: 120 }
                }
            }
        }

        /*! 右栏「复制」—— 它必须**压在 MouseArea 上面**，所以声明在正文列之后。 */
        Rin.Button {
            id: echoCopyButton

            objectName: "aboutEchoCopyButton"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: echoCave.copyVisible
            text: echoCave.copied ? qsTr("已复制") : qsTr("复制")

            onClicked: {
                Backend.copyToClipboard(echoCave.fullText)
                echoCave.copied = true
                copiedTimer.restart()
            }
        }

        // 逐字打出：L1 ``typewriteText(el, text, 50)`` 的 50ms/字。
        Timer {
            id: typeTimer
            interval: 50
            repeat: true

            onTriggered: {
                if (echoCave.shownText.length >= echoCave.fullText.length) {
                    stop()
                    echoCave.typing = false
                    echoCave.cursorOn = false
                    // 打完才亮出「复制」（L1 是 await 之后才 display:''）
                    echoCave.copyVisible = true
                    return
                }
                echoCave.shownText = echoCave.fullText.substring(
                    0, echoCave.shownText.length + 1)
            }
        }

        // 光标闪烁：L1 ``echoCaveBlink .7s steps(1)`` → 半周期 350ms 硬切。
        Timer {
            id: cursorTimer
            interval: 350
            repeat: true
            running: echoCave.typing
            onTriggered: echoCave.cursorOn = !echoCave.cursorOn
        }

        // 「已复制」的回显时长，L1 是 1500ms。
        Timer {
            id: copiedTimer
            interval: 1500
            onTriggered: echoCave.copied = false
        }

        Connections {
            target: Backend

            function onEchoCaveResult(text, result) {
                echoCave.applyResult(text, result)
            }
        }
    }

    // ============================================================ 诊断信息框
    /*! L1 ``showDiagnosticInfo()`` + ``#diagnostic-modal`` 的对应物。

        ``Rin.Dialog`` 底子是 ``QQC2.Dialog``，而它的 ``anchors.centerIn:
        QQC2.Overlay.overlay`` 要求宿主是 ``ApplicationWindow`` —— 设置窗口
        （``Rin.FluentWindow`` → ``FluentWindowBase`` → ``ApplicationWindow``）
        满足；托盘浮窗那种裸 ``Window`` 就不满足（``QuickPanel.qml`` 为此没用它）。
        所以这个框只能挂在设置页里，别搬去别处。 */
    Rin.Dialog {
        id: diagnosticsDialog

        objectName: "aboutDiagnosticsDialog"
        title: qsTr("诊断信息")
        modal: true

        /*! 宽度。2026-10-04 用户指令「宽度不够宽」。

            ``Rin.Dialog`` 把 ``implicitWidth`` 钉死在 ``Utils.dialogMaximumWidth``
            （= 600，见 ``RinUI/themes/utils.qml``），600 宽下诊断文本里
            ``AppExecutingEntrance: G:\\Dev\\...\\.venv\\Scripts\\python.exe`` 这种行
            一折就断成两截，读起来很难受。

            ⚠️ 要改的是 ``implicitWidth`` 而**不是** ``width``：``QQC2.Popup`` 里
            ``width`` 的默认值就是 ``implicitWidth``（一条绑定），直接写 ``width``
            会被那条绑定立刻盖回去 —— 症状是「改了没反应」。这里在派生组件里重写
            基类那条 ``implicitWidth`` 绑定，照抄 RinUI 的公式，只把上限换成
            ``dialogWidth``，保住「不超过窗口」的夹取。

            ⚠️ 不能用 ``implicitContentWidth + 48`` 那一段来定宽：文本框换成了
            ``Rin.ScrollableTextArea``，它的 ``implicitWidth`` 是死的 200（见
            ``RinUI/components/Text/ScrollableTextArea.qml``），照原公式算出来反而
            只有 320 宽。诊断文本是定长内容，宽度给死值更合适。 */
        readonly property int dialogWidth: 880

        implicitWidth: Math.min(
            diagnosticsDialog.dialogWidth,
            Math.max(0, QQC2.Overlay.overlay.width - 16))

        // 采集结果 ``[{"key":..., "value":...}]``；空数组 = 还没回来。
        property var fields: []
        property bool loading: false
        property bool copied: false

        // 只读文本框的高度。对话框加宽到 880 之后本机 22 个字段铺开是 386px
        // （没加宽那会儿一行一折，要 800+），仍比框高 —— 所以固定成一个比窗口矮的
        // 框，内容超出由文本框自己滚（``Rin.ScrollableTextArea`` 的 Flickable）。
        readonly property int boxHeight: 320

        onOpened: {
            fields = []
            copied = false
            loading = true
            Backend.requestDiagnostics()
            // ⚠️ 主按钮的高亮必须在**这里**补，不能写在按钮自己身上：``DialogButtonBox``
            // 创建子项时会覆盖 ``highlighted``（它 delegate 里那条绑定对着自定义按钮
            // 求值成 undefined），``highlighted: true`` 与 ``Component.onCompleted``
            // 都留不住。``onOpened`` 晚于子项创建，这时设才生效。
            diagnosticsCopyButton.highlighted = true
        }

        /*! 对话框正文 / 「复制全部」的内容：``Key: Value`` 逐行。

            2026-10-04 用户指令「内容也和 ClassIsland 的那种诊断信息统一」——
            于是**去掉**了原来那张 key → 中文名的映射表（``diagnosticLabel``），
            以及值的中文化（``diagnosticValue``）：ClassIsland 的诊断文本就是
            原始英文键 + 原始值，一个字都不翻译，好让人直接贴进 issue 里被
            不同语言的维护者检索到。采集侧的键名也已对齐 —— 见
            ``app/diagnostics.py::FIELD_ORDER``。

            取不到的字段渲染成 ``Unknown``（ClassIsland 那边是 ``???``），免得
            出现 ``LogFile: `` 这种看着像被截断的行。 */
        function plainText() {
            var lines = []
            for (var i = 0; i < fields.length; ++i) {
                var item = fields[i]
                var value = String(item.value === undefined || item.value === null
                                    ? "" : item.value)
                lines.push(item.key + ": " + (value === "" ? "Unknown" : value))
            }
            return lines.join("\n")
        }

        /*! 正文：加载中 → **只读多行文本框**。
            2026-10-04 用户指令：「打开的 dialog 要是 ClassIsland 的那种，
            dialog 内套文本框」—— 于是把原来的键值表格（``Flickable`` +
            ``Repeater`` 一行行画）整个换成文本框：ClassIsland 的诊断信息窗就是
            「一个只读多行 TextBox + 底部按钮」，文本本身也是 ``Key: Value`` 逐行，
            跟 ``plainText()`` 一模一样。

            ⚠️ 必须是 ``Rin.ScrollableTextArea`` 而**不是** ``Rin.TextArea``。
            2026-10-04 用户指令「滚不动」—— 那一版用的就是 ``Rin.TextArea``，
            实测它**不会滚**：它是 ``QtQuick.Controls.Basic`` 的 ``TextArea``
            （内容项是 C++ 侧的 TextEdit，``contentItem`` 取回来是 None），
            文本超长时只是把 ``implicitHeight`` 撑到 652 然后被
            ``Layout.preferredHeight: 320`` 裁掉，滚轮/拖动一概无效。
            ``Rin.ScrollableTextArea`` 才是 RinUI 里带滚动的那一档：底子是
            ``ScrollView``，实测它的 ``contentItem`` 是 ``QQuickFlickable``，
            ``contentHeight`` = 692 / ``height`` = 320 —— 这才是能滚的形态
            （``tools/scroll_probe.py`` 留了这份对照）。

            ⚠️ ``editable`` / ``enabled`` 的坑：``Rin.TextArea`` 把 ``enabled`` 绑在
            ``editable`` 上，用 ``editable: false`` 实现只读会把整框打成禁用 ——
            那样既不能滚也不能选中文字，只剩个样子。只读要用 ``readOnly``
            （``ScrollableTextArea`` 透出来的正是这个别名）。

            ⚠️ ``Layout.preferredHeight`` **不能删**：``ScrollableTextArea`` 里写着
            ``implicitHeight: defaultHeight``，而 ``defaultHeight`` 在 RinUI 里根本
            没有定义（上游的笔误），这条绑定会求值失败、``implicitHeight`` 落到 0。
            实测不写 ``Layout.preferredHeight`` 的话框会被压成一条线。

            ⚠️ 别去读 ``wrapMode``：它是 ``QQuickTextEdit::WrapMode`` 枚举，PySide
            没注册转换器，``property("wrapMode")`` 直接抛 ``RuntimeError``。
            换行沿用 ``ScrollableTextArea`` 内层 TextArea 的 ``Text.Wrap``。 */
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            Rin.Text {
                objectName: "aboutDiagnosticsLoading"
                Layout.fillWidth: true
                Layout.topMargin: 12
                Layout.bottomMargin: 12
                typography: Rin.Typography.Caption
                color: Lumi.textSecondary
                horizontalAlignment: Text.AlignHCenter
                text: qsTr("加载中...")
                visible: diagnosticsDialog.loading
            }

            Rin.ScrollableTextArea {
                objectName: "aboutDiagnosticsBox"
                Layout.fillWidth: true
                Layout.preferredHeight: diagnosticsDialog.boxHeight
                visible: !diagnosticsDialog.loading
                readOnly: true
                // 换行沿用内层 TextArea 的 ``Text.Wrap``：优先在词边界断，遇到超长
                // 的单个「词」（路径、显卡名）再硬断 —— 比 ``WrapAnywhere`` 好看得多
                // （后者会把 ``(10.0.26300)`` 这种直接拦腰截断），又不会让长路径把框
                // 撑出横向溢出。
                //
                // ``font`` 走 ``ScrollView`` 那一层：QQC2 的 ``ScrollView`` 会把
                // ``font`` / ``palette`` 传播给内容项，内层 TextArea 才拿得到 Consolas。
                font.family: "Consolas"
                font.pixelSize: 13
                text: diagnosticsDialog.plainText()
            }
        }

        /*! 底部按钮：用 RinUI ``Dialog`` 的**标准底栏** ``Rin.DialogButtonBox``。

            2026-10-04 用户指令「RinUI 的 dialog 是有标准样式的，你去看看 RinUI
            的用法」—— 之前这里是个裸 ``RowLayout``：没有底栏那条分隔背景，
            按钮也不按标准底栏的半宽均分排布，「复制全部」会直接压出圆角。
            RinUI 的 ``Dialog.qml`` 里标准写法就是
            ``footer: DialogButtonBox { standardButtons: root.standardButtons }``。

            ⚠️ 这里**不放** ``standardButtons``：标准按钮的文案来自 Qt 自带的
            ``qtbase_<语言>.qm``，而本应用只装 ``luminalium_*.qm``（见
            ``app/i18n.py``），装了也只会显示英文 OK / Cancel。改成把两枚自定义
            按钮**声明成子项**，由 ``DialogButtonBox`` 统一排布 + 统一画底栏背景；
            ``Layout.*`` 那两行是照抄它 delegate 的写法 —— 自定义子项不走
            delegate，宽度得自己撑。 */
        footer: Rin.DialogButtonBox {
            id: diagnosticsButtons

            Rin.Button {
                objectName: "aboutDiagnosticsCloseButton"
                Layout.fillWidth: true
                Layout.preferredWidth: diagnosticsButtons.availableWidth / 2
                text: qsTr("关闭")
                onClicked: diagnosticsDialog.close()
            }

            Rin.Button {
                id: diagnosticsCopyButton
                objectName: "aboutDiagnosticsCopyButton"
                Layout.fillWidth: true
                Layout.preferredWidth: diagnosticsButtons.availableWidth / 2
                text: diagnosticsDialog.copied ? qsTr("已复制") : qsTr("复制全部")
                onClicked: {
                    Backend.copyToClipboard(diagnosticsDialog.plainText())
                    diagnosticsDialog.copied = true
                    diagnosticsCopiedTimer.restart()
                }
            }
        }

        Timer {
            id: diagnosticsCopiedTimer
            interval: 2000
            onTriggered: diagnosticsDialog.copied = false
        }

        Connections {
            target: Backend

            function onDiagnosticsReady(items) {
                diagnosticsDialog.fields = items
                diagnosticsDialog.loading = false
            }
        }
    }
}
