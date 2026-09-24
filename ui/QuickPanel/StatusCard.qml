import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    放映状态卡片（快捷面板里「放映状态」区块的主体）。

    位置对应 Class Widgets 2 面板里的课程表区块 —— Luminalium 是放映伴侣，
    这里显示的是**放映检测的实时状态**：

    * 放映中：强调色图标 + 「放映中 · 第 X / Y 页」；
    * 空闲：次级图标 + 「未检测到放映」提示。

    点击卡片 = 触发「放映控制」快捷方式（打开设置里的放映控制页；
    若该快捷方式已被移除则不响应）。
*/
Rin.Clip {
    id: root

    readonly property bool presenting: Backend.presentationActive === true
    readonly property string progress: Backend.describeSlideProgress()

    radius: Lumi.shortcutTileRadius
    padding: 0

    onClicked: {
        if (Backend.activateShortcut("presentation")) {
            Backend.hidePanel()
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 12

        Rin.Icon {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            icon: root.presenting
                ? "ic_fluent_slide_play_20_regular"
                : "ic_fluent_slide_multiple_20_regular"
            size: 22
            color: root.presenting ? Lumi.accent : Lumi.textSecondary
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Body
                elide: Text.ElideRight
                text: root.presenting ? qsTr("放映中") : qsTr("未检测到放映")
            }

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.Caption
                color: Lumi.textSecondary
                elide: Text.ElideRight
                text: root.presenting && Backend.slideTotal > 0
                    ? qsTr("第 %1 / %2 页").arg(Backend.slideIndex).arg(Backend.slideTotal)
                    : (root.presenting ? qsTr("读取页码中…")
                                        : qsTr("开始放映后，控制条会自动出现"))
            }
        }
    }
}
