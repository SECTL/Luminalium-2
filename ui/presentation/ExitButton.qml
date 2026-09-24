import QtQuick
import RinUI as Rin
import Luminalium

/*!
    强调色「退出放映」按钮（参考稿最右侧的蓝色方块）。

    底色 / 悬停 0.875、按下 0.65 的透明度状态机、以及底部
    ``controlAccentBottomBorderColor`` 压边全部来自 ``Rin.Button``，
    不自建颜色插值。

    尺寸对照参考稿实测：**129 × 121**（条高 187），即
    **满内容高、略宽于高**（1.07 倍），圆角很小 —— 不是正方形也不是胶囊。
    图标是**黑色**（参考稿里电源字形是纯黑 ``#000000``），取
    ``Lumi.onAccent``（主题的 ``textOnAccentColor``，dark 主题即黑）。

    为什么要换掉 ``contentItem``：
    ``Rin.Button`` 默认 contentItem 里的 ``IconWidget`` 只设了 ``width`` /
    ``height``，**没设 ``size``**，而 ``Rin.Icon`` 的字形大小由 ``size``
    （默认 16）驱动 —— 所以 ``icon.width`` 调多大字形都不变。
    换成自己的 ``Rin.Icon`` 才能让 ``icon_size`` 真正生效。

    换 ``contentItem`` 的两个连带契约（都得一起满足，否则 ``ReferenceError``）：

    * ``implicitWidth`` / ``implicitHeight`` —— 基类这两个绑定引用了默认
      contentItem 里的 ``row``；
    * ``id: text`` —— 基类的 ``font: text.font`` 与 ``disabled`` state 里的
      ``PropertyChanges { target: text }`` 都指向那个 id。

    所以下面保留一个不可见的 ``Text { id: text }`` 作为兼容垫片，
    它不参与渲染。
*/
Rin.Button {
    id: root

    property string iconName: "ic_fluent_power_20_regular"
    property string tooltip: ""
    property int buttonHeight: Lumi.dockHitSize
    /*! 宽:高比（参考稿实测 1.07）。 */
    property real widthRatio: Lumi.dockExitWidthRatio
    property int glyphSize: Lumi.dockIconSize
    property color accent: Lumi.accent

    implicitWidth: Math.round(buttonHeight * widthRatio)
    implicitHeight: buttonHeight
    width: implicitWidth
    height: buttonHeight
    padding: 0
    radius: Lumi.dockControlRadius

    highlighted: true
    primaryColor: accent

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
            color: Lumi.onAccent
        }
    }

    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
