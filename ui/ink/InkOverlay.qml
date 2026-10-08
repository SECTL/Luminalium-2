import QtQuick
import QtQuick.Window
import Luminalium.Ink 1.0

/*!
    自建墨迹叠加窗口 —— 整窗只装一块铺满的 InkLayer。

    2026-10-07 用户指令：自建批注替代 COM 笔/橡皮（计划 self-ink 第 3 项）。

    为什么要单独一只窗口：放映顶层窗口 TopWindow 被 ``SetWindowRgn`` 裁成
    「只剩控制条那几块」，区域外既不绘制也不命中 —— 墨迹画在它里面等于
    画在看不见的地方。所以墨迹有自己的全尺寸透明窗口，z 序夹在放映窗口
    与 TopWindow 之间（放映窗口 < 本窗口 < TopWindow），控制条恒在墨迹之上。

    * 本窗口属于 ``app/windows.py`` 的叠加窗口家族（与 TopWindow / 聚光灯
      同族），由 ``WindowManager`` 懒创建、只藏不销毁，**不做** RinUI 接管；
      所以这里声明 ``Qt.FramelessWindowHint`` 是必须的 —— AGENTS.md「禁
      Frameless」约束的是被 RinUI 接管的 FluentWindow。
    * 输入穿透**不在 QML 里管**：笔 / 橡皮时整窗吃输入，指针时整窗穿透，
      全由 Python 侧加减 ``WS_EX_TRANSPARENT`` 完成（``set_ink_tool``）。
      别在这里挂 MouseArea 去「拦点击」—— 穿透态下事件根本进不了进程。
    * 几何由 Python 跟随放映窗口矩形摆放，QML 侧只 ``anchors.fill``。
    * ``objectName`` 是 Python 侧按名查找的契约（``inkOverlay`` /
      ``inkLayer``），派生类名带 ``_QMLTYPE_<n>``，别按类名找。
*/
Window {
    id: inkOverlay

    objectName: "inkOverlay"
    title: qsTr("墨迹")
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        | Qt.WindowDoesNotAcceptFocus

    InkLayer {
        objectName: "inkLayer"
        anchors.fill: parent
    }
}
