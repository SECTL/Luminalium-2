import QtQuick
import RinUI as Rin
import Luminalium
import ".."

/*!
    时钟页（L1 的 ``#view-clock``）。

    日期在上、大字时间在下（L1 的顺序）。星期名跟界面语言走 ——
    ``Qt.formatDate(now, "dddd")`` 取的是系统 locale，界面切中文它还是
    "Saturday"，所以星期表写在页面里（L1 也是每种语言自带一张）。

    2026-10-17「RinUI 规范」替换：裸 ``Text`` → ``Rin.Text``。
    * 大字时间保留 L1 的 120（RinUI 字阶没有这一档），显式 ``font.pixelSize``；
    * 日期行改走 RinUI 字阶 ``Subtitle``（20）—— L1 是 24，字阶里最近的
      就是它，按「语言革新」用字阶而不是抄原值。
*/
Item {
    id: clockPage

    readonly property var host: Window.window

    property string nowText: ""
    property string dateText: ""
    property string weekText: ""

    readonly property var weekdays: [
        qsTr("周日"), qsTr("周一"), qsTr("周二"), qsTr("周三"),
        qsTr("周四"), qsTr("周五"), qsTr("周六")
    ]

    Timer {
        interval: 250
        running: clockPage.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            var now = new Date()
            clockPage.nowText = Qt.formatTime(now, "HH:mm:ss")
            clockPage.dateText = Qt.formatDate(now, "yyyy/MM/dd")
            clockPage.weekText = clockPage.weekdays[now.getDay()]
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: 8

        Rin.Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: clockPage.dateText + "  " + clockPage.weekText
            typography: Rin.Typography.Subtitle
            color: Lumi.textSecondary
        }
        Rin.Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: clockPage.nowText
            font.features: ({ "tnum": 1 })
            font.letterSpacing: -1
            font.pixelSize: 120
            font.weight: Font.Bold
            color: Lumi.textPrimary
        }
    }
}
