import QtQuick
import RinUI as Rin
import Luminalium

/*!
    纯图标按钮（放映控制条上的动作 / 翻页 / 溢出按钮）。

    **参考稿里的「圆圈」是图标占位**，不是设计元素 —— 真实界面就是一枚图标，
    所以这里**不画任何描边圆环**，只是 ``Rin.Button { flat: true }``：
    默认全透明，悬停浮现极淡填充，按下更深，键盘焦点环由基类提供。

    为什么要换掉 ``contentItem``：
    ``Rin.Button`` 默认 contentItem 里的 ``IconWidget`` 只设了 ``width`` /
    ``height``，**没设 ``size``**，而 ``Rin.Icon`` 的字形大小由 ``size``
    （默认 16）驱动 —— ``icon.width`` 调多大字形都不变。

    换 ``contentItem`` 的两个连带契约（都得一起满足，否则 ``ReferenceError``）：

    * ``implicitWidth`` / ``implicitHeight`` —— 基类这两个绑定引用了默认
      contentItem 里的 ``row``；
    * ``id: text`` —— 基类的 ``font: text.font`` 与 ``disabled`` state 里的
      ``PropertyChanges { target: text }`` 都指向那个 id。

    所以下面保留一个不可见的 ``Text { id: text }`` 作为兼容垫片，它不参与渲染。
*/
Rin.Button {
    id: root

    property string iconName: ""
    property string tooltip: ""
    property int glyphSize: Lumi.dockIconSize
    property int hitSize: Lumi.dockHitSize
    /*! 图标颜色（默认主文本色；需要时可由外部改成强调色）。 */
    property color glyphColor: Lumi.textPrimary

    implicitWidth: hitSize
    implicitHeight: hitSize
    width: hitSize
    height: hitSize
    padding: 0
    radius: Lumi.dockControlRadius
    flat: true

    contentItem: Item {
        // 兼容垫片：满足基类对 id `text` 的引用（font / disabled state）
        Text {
            id: text
            visible: false
        }

        Rin.Icon {
            anchors.centerIn: parent
            icon: root.iconName
            size: root.glyphSize
            color: root.glyphColor
        }
    }

    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
