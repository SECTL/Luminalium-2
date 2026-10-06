import QtQuick
import QtQuick.Window
import ".."

/*!
    顶层窗口 —— 放映时的**全屏叠加层**。

    把原本分散的各角落控制条窗口（工具栏 / 翻页栏等）合并成一个
    独立的全屏置顶窗口：本身完全透明，控制条作为 Item 挂在
    ``container`` 里、由 Python 定位到各角落。

    交互约定（Windows 原生实现，见 ``app/windows.py``）：

    * 窗口样式含 ``WS_EX_TRANSPARENT | WS_EX_NOACTIVATE``（**不含**
      ``WS_EX_LAYERED`` —— Qt Quick 的 D3D flip 呈现与分层合成不兼容，
      加了会整窗隐形），即**整窗鼠标 / 触摸穿透**；
    * 轮询光标位置：落在某个控制条的 ``interactiveRect``（工具栏表面，
      不含投影余量）内时**临时移除** ``WS_EX_TRANSPARENT``，让控制条可点；
      离开后恢复穿透。放映窗口的焦点全程不被抢走。

    窗口级属性统一在这里，控制条只管内容：

    * ``Qt.Tool`` —— 不占任务栏；
    * ``Qt.WindowDoesNotAcceptFocus`` —— 点按钮不抢放映窗口焦点；
    * ``Qt.WindowStaysOnTopHint`` —— 压在放映窗口之上。

    本窗口会被 **区域塑形**（``SetWindowRgn``）裁成「只有控制条几块」，
    区域外既不绘制也不命中 —— 所以左下角的开发水印必须让 Python 侧
    把它的矩形一并算进区域（``windows.py`` 读 ``watermarkItem``），
    否则会被整个裁掉。

    2026-10-06 用户指令「放映工具顶层窗口可以更智能些」之后，窗口本身也归
    Python 侧的看护定时器管（``windows.py::_watch_overlay``）：

    * **几何跟着放映窗口走** —— 全屏放映时两者重合，窗口化放映时遮罩就贴着
      那个窗口（``_apply_overlay_geometry``）；
    * **放映窗口不在前台时临时隐去** —— 走下面这个 ``suppressed`` 属性做淡出，
      不是 ``hide()`` 窗口（藏一只全屏分层窗口再显示会闪一帧）。

    QML 这边只管「淡成 0 / 淡回来」，穿透与区域由 Python 同步处理。
*/
Window {
    id: topWindow

    objectName: "TopWindow"
    title: qsTr("顶层窗口")
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        | Qt.WindowDoesNotAcceptFocus

    /*! 各角落控制条（``PresentationDock`` Item）的挂载容器。 */
    property alias container: containerItem

    /*! 左下角开发水印（Python 侧把它的矩形加进窗口区域）。

        **不要用 ``property alias``**：别名会推断成匿名 QML 类型
        （``DevWatermark_QMLTYPE_*``），PySide6 的 ``QObject.property()``
        转换不了它（RuntimeError: Can't find converter）；
        显式声明成 ``Item`` 类型就能正常取回。
    */
    readonly property Item watermarkItem: devWatermark

    /*! 「临时隐去」开关（Python 侧 ``windows.py::_set_overlay_suppressed`` 置位）。

        放映窗口不在前台时（用户切去别的程序），控制条淡出；切回来自动淡入。
        用淡出而不是 ``hide()``：隐藏一只全屏分层窗口再显示会闪一帧，而这里
        只是「先让开」。淡出期间 Python 会把整窗穿透打开 —— 内容看不见了，
        但那几块命中矩形还在，不穿透的话会继续吃掉点击。
    */
    property bool suppressed: false

    Item {
        id: containerItem
        anchors.fill: parent
        opacity: topWindow.suppressed ? 0 : 1
        Behavior on opacity {
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }

    // 开发中水印：左下角、左翻页 pill 的**上方**（pill 占 bottom-82..bottom-20，
    // 水印 90 起步正好不叠）。纯文字不吃点击；区域由 Python 一并纳入。
    // ⚠️ 不用 anchors：这个 Qt.Tool 透明窗口的 contentItem 高度是 0
    // （实测），``anchors.bottom: parent.bottom`` 会解析到 y=-124；
    // 直接对**窗口尺寸**绑 y 才可靠。
    DevWatermark {
        id: devWatermark
        x: 20
        y: topWindow.height - 90 - height
        z: 10
        // 水印是窗口根的直接子项（不在 container 里），临时隐去要跟着一起淡
        opacity: containerItem.opacity
    }
}
