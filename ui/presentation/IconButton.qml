import QtQuick
import RinUI as Rin
import Luminalium

/*!
    控制条上的纯图标按钮（工具 / 动作 / 翻页 / 溢出）。

    形态照 Luminalium 1 的 ``.tool-btn``：**38×38 圆形**，平时完全透明，
    悬停浮现一层极淡填充（L1 ``--overlay-button-hover`` 白 8%），
    选中的工具再深一档（``--overlay-button-active`` 白 15%）。
    L1 里工具没有「分段容器 + 下划线」这种东西 —— 选中就是圆底填充，
    所以本控件带一个 ``active`` 属性，工具组直接绑 ``Backend.activeTool``。

    为什么要换掉 ``contentItem``：
    ``Rin.Button`` 默认 contentItem 里的 ``IconWidget`` 只设了 ``width`` /
    ``height``，**没设 ``size``**，而 ``Rin.Icon`` 的字形大小由 ``size``
    （默认 16）驱动 —— ``icon.width`` 调多大字形都不变。

    ⛔ **不能覆写 ``background``**：基类有 ``property alias radius:
    background.radius``，替换掉 background 会让这个别名指向不存在的对象
    （同 ``SegmentedItem`` 的坑）。所以这里换个办法：把基类的
    ``backgroundColor`` 置成 ``transparent``（基类在 flat 时
    ``hoverColor === backgroundColor``，于是它的悬停填充自然消失），
    填充由 ``contentItem`` 里的矩形自己画 —— 还能顺手做圆形。

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
    property color glyphColor: Lumi.textPrimary
    /*! 选中态（工具类按钮）：圆底填充，对应 L1 的 ``.tool-btn.active``。 */
    property bool active: false
    property color activeFill: Lumi.dockButtonActiveFill
    property color hoverFill: Lumi.dockButtonHoverFill

    implicitWidth: hitSize
    implicitHeight: hitSize
    width: hitSize
    height: hitSize
    padding: 0
    radius: hitSize / 2   // 圆形（L1 .tool-btn 38×38 → border-radius: 19）
    flat: true
    // 见文件头：基类的 flat 填充让位给下面自绘的圆底
    backgroundColor: "transparent"

    contentItem: Item {
        // 兼容垫片：满足基类对 id `text` 的引用（font / disabled state）
        Text {
            id: text
            visible: false
        }

        // 圆底填充：选中 > 悬停（与 L1 的 CSS 顺序一致，active 覆盖 hover）。
        // 必须声明在图标**之前**，否则会盖住图标。
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: root.active
                ? root.activeFill
                : (root.hovered ? root.hoverFill : "transparent")

            Behavior on color {
                ColorAnimation { duration: Lumi.durationFast }
            }
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
