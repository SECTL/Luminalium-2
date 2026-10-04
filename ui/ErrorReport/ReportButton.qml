import QtQuick
import RinUI as Rin
import Luminalium

/*!
    报告窗左下角的标准按钮（**图标 + 文本**）。

    直接坐在 ``Rin.Button`` 上 —— 默认（非 flat / 非 highlighted）就是 Fluent 的
    标准按钮：``controlColor`` 底 + 1px 描边 + 悬停加深。这里只把「图标 + 文案」
    收成两个语义属性，免得每个调用点都去拼 ``icon.name`` / ``text``。

    ⚠️ 刻意**不换** ``contentItem``：``Rin.Button`` 默认的内容项就是
    ``Row { IconWidget + Text }``（间距 8），换掉要连带满足 ``implicitWidth``
    与 ``id: text`` 两个契约（见 ``ui/presentation/IconButton.qml`` 的头注释），
    这里没有非改不可的理由。
*/
Rin.Button {
    id: root

    property string iconName: ""
    property string label: ""

    text: root.label
    icon.name: root.iconName
    implicitHeight: 32
}
