import QtQuick
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import RinUI as Rin
import Luminalium

/*! 关于：版本与运行环境。

    logo / banner 都从仓库根目录 ``resources/`` 取（``Backend.resourceFile``
    拼 ``file:///`` 绝对 URL —— QML 的 ``Image.source`` 不吃相对路径）。
*/
Rin.FluentPage {
    id: page

    title: qsTr("关于")
    contentSpacing: 10

    /*! banner 原图 3471x1884，按这个比例铺满内容宽度后限高，避免占满整页。 */
    readonly property real bannerRatio: 1884 / 3471
    readonly property int bannerMaxHeight: 150

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(bannerMaxHeight, width * bannerRatio)
        Layout.topMargin: 4

        Image {
            id: banner
            anchors.fill: parent
            source: Backend.resourceFile("banner.png")
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            // 圆角遮罩：Image 自己没有圆角，靠 OpacityMask 裁掉四角
            layer.enabled: true
            layer.effect: OpacityMask {
                maskSource: bannerMask
            }
        }

        Rectangle {
            id: bannerMask
            anchors.fill: parent
            radius: Lumi.dockSurfaceRadius
            visible: false
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 64

        Row {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            spacing: 16

            Image {
                width: 64
                height: 64
                source: Backend.resourceFile("logo.svg")
                sourceSize: Qt.size(64, 64)
                asynchronous: true
            }

            // Row 是定位器：子项不得用 anchors，故两层文字包在显式尺寸的 Item 里
            Item {
                width: 320
                height: 64

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    spacing: 2

                    Rin.Text {
                        typography: Rin.Typography.Title
                        text: Backend.appName
                    }

                    Rin.Text {
                        typography: Rin.Typography.Body
                        color: Lumi.textSecondary
                        text: qsTr("版本 %1").arg(Backend.appVersion)
                    }
                }
            }
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("组成")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("界面框架")
        description: "PySide6 + QML · RinUI Fluent 组件库"
        icon.name: "ic_fluent_window_dev_tools_20_regular"
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("放映控制")
        description: qsTr("通过 COM 自动化连接本机 PowerPoint")
        icon.name: "ic_fluent_slide_play_20_regular"
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("配置文件")
        description: qsTr("改动只写与默认值不同的部分")
        icon.name: "ic_fluent_document_text_20_regular"

        Rin.Button {
            flat: true
            text: qsTr("重新加载")
            onClicked: Backend.requestReload()
        }
    }
}
