import QtQuick
import RinUI as Rin
import Luminalium

/*!
    快捷面板上的扁平图标按钮（小节标题行 / 底栏 / 对话框头部）。

    形态对齐 Class Widgets 2 里的 ``ToolButton { flat: true }``：默认全透明、
    悬停浮现极淡底色、按下更深，并带 ToolTip。尺寸按 CW2 实测（本仓库探针
    量得 RinUI ToolButton 隐式 44×32、字形 20），宽大于高。

    为什么要自己换 ``contentItem`` 而不是直接用 ``Rin.ToolButton``：
    ``Rin.ToolButton`` 在本版本里**没有**强制 ``flat``（源码里那行是注释掉的），
    默认会画出一块带描边的实心按钮；而且它的 ``implicitWidth`` 继承了基类对
    内部 ``row`` id 的引用，覆写 contentItem 后不满足契约。这里落回最稳的
    ``Rin.Button { flat: true }`` —— 它与 CW2 的 flat ToolButton 是同一个视觉。

    换 ``contentItem`` 的两个连带契约（必须同时满足，否则运行期报错）：

    * ``implicitWidth`` / ``implicitHeight`` —— 基类这两个绑定引用了默认
      contentItem 里的 ``row``；
    * ``id: text`` 垫片 —— 基类的 ``font: text.font`` 与 disabled state 里的
      ``PropertyChanges { target: text }`` 都指向该 id。

    另外 ``IconWidget`` 只设 ``width`` / ``height`` 而**不设** ``Rin.Icon.size``，
    字形大小实际由 ``size``（默认 16）决定，所以必须自绘图标。
*/
Rin.Button {
    id: root

    property string iconName: ""
    property string tooltip: ""
    // CW2 实测比例（RinUI ToolButton 隐式尺寸）：44 宽 × 32 高、字形 20 ——
    // 宽大于高（基类 implicitWidth = max(内容+26, 40)），不是正方形。
    property int buttonWidth: 44
    property int buttonHeight: 32
    property int iconSize: 20
    property color glyphColor: Lumi.textPrimary

    implicitWidth: buttonWidth
    implicitHeight: buttonHeight
    width: buttonWidth
    height: buttonHeight
    padding: 0
    radius: Lumi.controlRadius
    flat: true

    contentItem: Item {
        // 兼容垫片：满足基类对 id `text` 的引用
        Text {
            id: text
            visible: false
        }

        Rin.Icon {
            anchors.centerIn: parent
            icon: root.iconName
            size: root.iconSize
            color: root.glyphColor
        }
    }

    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
