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

    ## 名称文本（``label`` / ``showLabel``）

    「显示按钮文本」打开后（``presentation.buttons.show_labels``，入口在主界面编辑器），
    按钮从**圆**变成**胶囊**：图标仍停在左端那个圆里，右边接一段名称文字::

        [ 11 ][ 22 图标 ][ 8 ][ 文字 ][ 12 ]

    宽度按文字**实际**宽度撑开，所以整条控制条会自然变宽 —— 真机上
    ``windows.py::_load_docks`` 挂了 ``widthChanged`` → 重摆，位置不会漂。

    ⚠️ 文字宽度用**隐藏的探针标签**量（同组件同字阶），不用 ``TextMetrics``：
    后者得自己抄一遍字体族与字号，主题一换就漂。探针是被量对象的同一个类，
    宽度天然一致。

    ## 为什么换掉 ``contentItem``

    ``Rin.Button`` 默认 contentItem 里的 ``IconWidget`` 只设了 ``width`` /
    ``height``，**没设 ``size``**，而 ``Rin.Icon`` 的字形大小由 ``size``
    （默认 16）驱动 —— ``icon.width`` 调多大字形都不变。

    ⛔ **不能覆写 ``background``**：基类有 ``property alias radius:
    background.radius``，替换掉 background 会让这个别名指向不存在的对象
    （同 ``SegmentedItem`` 的坑）。所以这里换个办法：把基类的
    ``backgroundColor`` 置成 ``transparent``（基类在 flat 时
    ``hoverColor === backgroundColor``，于是它的悬停填充自然消失），
    填充由 ``contentItem`` 里的矩形自己画 —— 还能顺手做圆形 / 胶囊形。

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
    /*! 按钮的名称文本（「笔」「清屏」「退出放映」…）。空串时退化成纯图标按钮。 */
    property string label: ""
    /*! 是否在按钮旁显示 ``label``。 */
    property bool showLabel: false
    property int glyphSize: Lumi.dockIconSize
    property int hitSize: Lumi.dockHitSize
    property color glyphColor: Lumi.textPrimary
    property color labelColor: Lumi.textPrimary
    /*! 选中态（工具类按钮）：圆底填充，对应 L1 的 ``.tool-btn.active``。 */
    property bool active: false
    property color activeFill: Lumi.dockButtonActiveFill
    property color hoverFill: Lumi.dockButtonHoverFill

    /*! 图标与文字之间的间距 / 文字右端留白（见 ``Lumi.dockLabelGap`` 的算式图）。 */
    readonly property int labelGap: Lumi.dockLabelGap
    readonly property int labelTrail: Lumi.dockLabelTrail
    /*! 文字是否真的呈现（开关打开 **且** 这个名字非空）。 */
    readonly property bool labelVisible: showLabel && label !== ""

    /*! 宽度探针 —— 与下面那个可见的标签是**同一个组件、同一个字阶**，
        宽度天然一致。不参与渲染。 */
    Rin.Text {
        id: labelProbe
        visible: false
        typography: Rin.Typography.Body
        wrapMode: Text.NoWrap
        text: root.label
    }

    /*! 纯图标时是圆的直径；带名称文本时 = 图标圆 + 间距 + 文字 + 右留白。 */
    implicitWidth: labelVisible
        ? hitSize + labelGap + Math.ceil(labelProbe.implicitWidth) + labelTrail
        : hitSize
    implicitHeight: hitSize
    width: implicitWidth
    height: implicitHeight
    padding: 0
    // 半径取**短边**的一半：带名称文本时按钮是宽的，仍要恒为胶囊而不是椭圆
    // （``Rectangle.radius`` 不保证自己钳制，自己算最稳）。
    radius: Math.min(width, height) / 2
    flat: true
    // 见文件头：基类的 flat 填充让位给下面自绘的圆底
    backgroundColor: "transparent"

    contentItem: Item {
        // 兼容垫片：满足基类对 id `text` 的引用（font / disabled state）
        Text {
            id: text
            visible: false
        }

        // 圆底 / 胶囊底填充：选中 > 悬停（与 L1 的 CSS 顺序一致，active 覆盖 hover）。
        // 必须声明在图标**之前**，否则会盖住图标。
        Rectangle {
            anchors.fill: parent
            radius: Math.min(width, height) / 2
            color: root.active
                ? root.activeFill
                : (root.hovered ? root.hoverFill : "transparent")

            Behavior on color {
                ColorAnimation { duration: Lumi.durationFast }
            }
        }

        /*! 图标槽 —— 恒为 ``hitSize`` 的正圆，图标在它里面居中。
            带名称文本时按钮向右长，图标仍停在左端这个圆里（就是它平时占的位置）。 */
        Item {
            id: glyphSlot
            width: root.hitSize
            height: root.hitSize
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter

            Rin.Icon {
                anchors.centerIn: parent
                icon: root.iconName
                size: root.glyphSize
                color: root.glyphColor
            }
        }

        Rin.Text {
            objectName: "dockButtonLabel"
            visible: root.labelVisible
            anchors.left: glyphSlot.right
            anchors.leftMargin: root.labelGap
            anchors.verticalCenter: parent.verticalCenter
            typography: Rin.Typography.Body
            wrapMode: Text.NoWrap
            color: root.labelColor
            text: root.label
        }
    }

    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
