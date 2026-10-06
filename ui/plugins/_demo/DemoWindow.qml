import QtQuick
import RinUI as Rin
import Luminalium

/*!
    插件系统验收夹具 ``_demo`` 的夹具窗口（2026-10-05 插件系统计划 Wave 3 任务 12）。

    ⚠️ 本窗口与整个 ``_demo`` 插件组是**框架验收夹具**，禁止在此实现任何真实
    功能；内容刻意占位级（一个标题一行字）。

    **插件窗口的标准关窗路径**（供未来插件参照）：
    ``onClosing`` 里 ``event.accepted = false`` 拦掉默认关闭（窗口只藏不销毁），
    再走 ``Backend.triggerAction("plugin:<本插件id>:close")`` —— 经任务 6 的
    ``plugin:`` 特权通道 → 动词注册表最长前缀匹配 → 插件自己的动作处理器 →
    ``register_window`` 句柄 ``hide()``。这是唯一不依赖 Backend 专用槽
    （如 ``closeSettings``）的通用关窗通道，插件不要自己发明关窗路径。

    窗口的创建 / RinUI 接管 / 失败兜底 / 定位 / 显隐全由
    ``WindowManager.register_window`` 封装（``app/windows.py`` 任务 4 起），
    QML 侧**不得**加 ``Qt.FramelessWindowHint``（会把系统阴影一起弄没，
    历史见 ``ui/Settings.qml`` 头注释），也不许直接碰 ``_attach_to_rinui``。
*/
Rin.FluentWindow {
    id: demoWindow

    title: qsTr("演示插件")
    visible: false
    width: 420
    height: 240
    minimumWidth: 320
    minimumHeight: 200

    onClosing: function (event) {
        event.accepted = false
        Backend.triggerAction("plugin:_demo:close")
    }

    Rin.Text {
        anchors.centerIn: parent
        typography: Rin.Typography.BodyLarge
        text: qsTr("插件系统验收夹具：本窗口无任何实际功能")
    }
}
