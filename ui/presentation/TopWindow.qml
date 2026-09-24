import QtQuick
import QtQuick.Window

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

    Item {
        id: containerItem
        anchors.fill: parent
    }
}
