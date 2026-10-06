import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import RinUI as Rin

/*!
    设置**主页**：一比一复刻 Class Widgets 2 的
    ``src/qml/ClassWidgets/pages/settings/Home.qml``（2026-10-05 用户指令
    「设置的主页参考一下 Class Widgets 2 …… 外观和用户体验上一比一复刻，
    逻辑上一模一样」—— 以下逐条对应 CW2 本地源码原档）：

    * ``horizontalPadding: 0`` + ``wrapperWidth: Math.min(width - 42*2, 1200)``：
      横幅左右**通栏出血**，内容列被夹到 743（827 − 84），与 CW2 同一组公式；
    * **横幅**：``contentHeader`` 里一张 ``Image``（``PreserveAspectCrop``），
      底部用 ``Qt5Compat`` 的 ``OpacityMask`` + 一条 0.7→1.0 的垂直渐变把横幅
      **溶进页面**（CW2 同一条渐变）；高度 ``max(window.height * 0.26, 200)``；
      标题「主页」压在横幅左上（``leftMargin: 56 / topMargin: 38``，
      ``Typography.Title``）—— 页面本体**不带** ``title``（CW2 也没有，头部
      随之塌成 0，大标题就由横幅承担）；
    * **InfoBar**：``Severity.Warning`` 的常驻提示（CW2 那页同款，「仍在测试
      中，欢迎来 GitHub 提 Issue」），``objectName`` 沿用
      ``homeWarningBanner``（自检按名字找它）；
    * **两张 220×128 的链接卡**（CW2 的 ``Component card`` + ``Repeater``）：
      ``Rin.Clip`` 底子，里面「32px 大图标 → 撑开 → ``BodyLarge`` 标题」，
      右下角一枚 18px 的 open 角标（CW2 的 ``IconWidget``，RinUI 0.4.4.1 没有
      这个组件，用 ``Rin.Icon`` 按同样的锚点摆），整卡点击 ``Qt.openUrlExternally``。

    与 CW2 的**刻意差异**只有资源层（结构、尺寸、交互全部照抄）：

    * 横幅图：CW2 按 ``Theme.isDark()`` 在 ``banner/4-1_{dark,light}.png`` 里
      二选一；本项目用通栏专用的 ``resources/banner-wide.png``（用户备好，
      2026-10-05 替换原来的 banner.png；旧图仍在 resources/ 里备用）。将来补
      浅色版时把 ``source`` 换成 ``Lumi.isDark ? … : …`` 即可（参照
      ``MainInterface.qml`` 的推广卡）。
    * 横幅大标题：CW2 用主题文本色（他们的图按主题配套）；本项目 banner 只有
      深色一张，标题按用户指令写死**白色**。
    * 两张卡的链接：CW2 是 GitHub / Discord；本项目对应 **GitHub 仓库** 与
      **GitHub Issues（反馈）**，URL 与「关于」页同一份口径。

    ⚠️ ``contentHeader`` 指向 ``headerContainer.data``（一条 ``Row``），子项
    **不会**自动拿到宽度 —— 里面的 ``Item`` 必须自己写 ``width``，否则按
    ``implicitWidth`` 排（横幅会缩成一条）。CW2 写 ``width: parent.width``，
    这里同理。
*/
Rin.FluentPage {
    id: page

    horizontalPadding: 0
    wrapperWidth: Math.min(width - 42 * 2, 1200)

    /*! 两条外链（与「关于」页同一份口径）。 */
    readonly property string repoUrl: "https://github.com/SECTL/Luminalium-2"
    readonly property string issuesUrl: repoUrl + "/issues/new/choose"

    // ================================================================ 横幅
    contentHeader: Item {
        id: homeBanner

        objectName: "homeBanner"
        width: parent.width
        /*! CW2 写的是 ``max(window.height * 0.26, 200)``。⚠️ 裸的 ``window``
            标识符只在真设置窗口里解析得到（实测 ``typeof window === "object"``），
            塞进 ``tools/preview.py`` 那种 Loader 宿主就是 ``undefined`` →
            ``undefined * 0.26`` = NaN → 横幅高度整个塌成 0。``Window.window``
            （QtQuick.Window 的附加属性）在两种宿主里都成立且语义相同 ——
            「页面所在的那扇窗」，所以这里用它表达同一条公式。 */
        height: Math.max((Window.window ? Window.window.height : 0) * 0.26, 200)

        Image {
            id: homeBannerImage

            objectName: "homeBannerImage"
            anchors.fill: parent
            source: Backend.resourceFile("banner-wide.png")
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
            mipmap: true
            smooth: true

            /*! 底部渐隐：CW2 用 ``OpacityMask`` + 一条 0.7→1.0 的垂直渐变把
                横幅溶进页面（没有圆角、没有边框）。 */
            layer.enabled: true
            layer.effect: OpacityMask {
                maskSource: Rectangle {
                    width: homeBannerImage.width
                    height: homeBannerImage.height

                    gradient: Gradient {
                        GradientStop { position: 0.7; color: "white" }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }
        }

        /*! 大标题压在横幅左上（CW2：``leftMargin: 56 / topMargin: 38``）。
            颜色写死**白色**（2026-10-05 用户指令「左上角的主页改成白色 因为
            banner 是黑色底」）：banner.png 只有一张深色图，深浅主题都是黑底，
            跟主题文本色走的话浅色主题下会变成黑字压黑底。 */
        Column {
            anchors {
                top: parent.top
                left: parent.left
                leftMargin: 56
                topMargin: 38
            }
            spacing: 8

            Rin.Text {
                objectName: "homeBannerTitle"
                typography: Rin.Typography.Title
                color: "#FFFFFF"
                text: qsTr("主页")
            }
        }
    }

    // ================================================================ 信息条
    /*! ``Severity.Warning`` 的常驻提示 —— CW2 主页同款（他们的文案是
        「仍在测试中，欢迎来 GitHub 提 Issue」，这里按本项目口径直译）。
        ``closable`` 不写、用默认的 true：CW2 也没写这一项，右上角的关闭按钮
        是它交互的一部分。 */
    Rin.InfoBar {
        objectName: "homeWarningBanner"
        Layout.fillWidth: true
        severity: Rin.Severity.Warning
        title: qsTr("警告")
        text: qsTr("当前版本仍在测试中，可能包含错误或未完成的功能。"
                   + "欢迎到 <a href=\"%1\">GitHub</a> 上提交 Issue。").arg(page.issuesUrl)
    }

    // ================================================================ 链接卡
    /*! 两张 220×128 的 ``Rin.Clip`` 卡（CW2 的 ``Component card``）：大图标 +
        撑开 + 标题，右下角 open 角标，整卡点击开外链。 */
    RowLayout {
        Layout.fillWidth: true

        Repeater {
            model: [
                {
                    icon: "ic_fluent_code_20_regular",
                    title: qsTr("GitHub"),
                    url: page.repoUrl
                },
                {
                    icon: "ic_fluent_chat_help_20_regular",
                    title: qsTr("反馈问题或功能建议"),
                    url: page.issuesUrl
                }
            ]

            delegate: Rin.Clip {
                id: linkCard

                objectName: "homeLinkCard" + index
                required property var modelData
                required property int index

                /*! 给自检用的：卡片点的就是这一个 URL（CW2 的逻辑是
                    ``onClicked: Qt.openUrlExternally(modelData.url)``，
                    URL 藏在 model 里，这里透出来一份）。 */
                property string linkUrl: modelData.url

                Layout.fillWidth: true
                Layout.preferredWidth: 220
                Layout.preferredHeight: 128

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 18

                    Rin.Icon {
                        Layout.alignment: Qt.AlignVCenter
                        name: linkCard.modelData.icon
                        size: 32
                    }

                    Item { Layout.fillHeight: true }

                    Rin.Text {
                        Layout.fillWidth: true
                        width: parent.width
                        typography: Rin.Typography.BodyLarge
                        text: linkCard.modelData.title
                    }
                }

                /*! 右下角 open 角标 —— CW2 的 ``IconWidget``（RinUI 0.4.4.1
                    没有，用 ``Rin.Icon`` 按同样的锚点与尺寸摆）。 */
                Rin.Icon {
                    anchors {
                        bottom: parent.bottom
                        right: parent.right
                        margins: 12
                    }
                    size: 18
                    name: "ic_fluent_open_20_regular"
                }

                onClicked: Qt.openUrlExternally(linkCard.modelData.url)
            }
        }
    }
}
