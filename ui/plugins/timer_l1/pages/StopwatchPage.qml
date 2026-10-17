import QtQuick
import RinUI as Rin
import Luminalium
import ".."

/*!
    秒表页（L1 的 ``#view-stopwatch``）。

    侧边栏版窗口（``TimerWindow.qml``）把页面交给 ``NavigationView`` 加载，
    所以三页各自独立成文件。**状态全在宿主窗口上**，这里只读不写：

        var host = Window.window          // 注意不是裸 ``window``

    引擎（起停 / 清零）在 ``app/plugins/timer_l1/plugin.py``，交互只走
    ``Backend.triggerAction("plugin:timer_l1:…")``。

    2026-10-17「RinUI 规范」替换：裸 ``Text`` → ``Rin.Text``。字号保留 L1 的
    120（``.stopwatch-display``）—— RinUI 字阶最大只到 Display 68，显示级
    数字没有对应档，显式给 ``font.pixelSize``；``font.weight`` 也必须显式
    （基类默认分支是自指绑定）。等宽数字与 -1px 字距照 L1 原样。
*/
Item {
    id: stopwatchPage

    readonly property var host: Window.window

    Rin.Text {
        anchors.centerIn: parent
        text: host ? host.fmtStopwatch(host.swMs) : ""
        // 等宽数字：秒表跳到百分秒时字宽不抖
        font.features: ({ "tnum": 1 })
        font.letterSpacing: -1
        font.pixelSize: 120
        font.weight: Font.Bold
        color: Lumi.textPrimary
    }

    TimerControlLayer {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
    }
}
