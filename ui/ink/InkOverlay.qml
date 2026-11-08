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
    * 2026-10-09 橡皮幻影：``EraserGhost`` 与 InkLayer 同一坐标系铺在层上，
      绑层的 ``eraserGhost*`` 属性（缘由见 EraserGhost.qml 头注释）——
      ``enabled: false`` 不吃输入，笔画事件原样落层。
    * 2026-10-10 鼠标/触控橡皮适配：鼠标移动在画布上时橡皮擦始终显示（放映控制条
      胶囊区域由 WindowManager 挂入 capsule_hit_hook 排除）；触控下仅按下才显。
    * 2026-10-13 自建批注手势防穿透：底色不能用纯 ``"transparent"``（``#00000000``）。
      Qt 6 RHI D3D11 对带透明通道的顶层窗口走 ``WS_EX_LAYERED`` + DirectComposition
      预乘 Alpha 交换链，画布无墨迹处像素 ``alpha == 0`` 会被 DWM 视觉树与 Office
      ``DirectManipulation`` 命中测试当成「镂空像素」直接穿透到底下 PowerPoint
      ``screenClass``，导致手画横线被 PPT 识别为翻页手势。改用 ``#01000000``
      （``alpha = 1/255``，肉眼完全透明）封死 DWM 像素级穿透；指针态与抑制态仍由
      Python 侧 ``WS_EX_TRANSPARENT`` 保证整窗 100% 穿透。
*/
Window {
    id: inkOverlay

    objectName: "inkOverlay"
    title: qsTr("墨迹")
    visible: false
    color: "#01000000"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        | Qt.WindowDoesNotAcceptFocus

    InkLayer {
        id: inkLayer
        objectName: "inkLayer"
        anchors.fill: parent
    }

    EraserGhost {
        anchors.fill: parent
        inkLayer: inkLayer
    }
}
