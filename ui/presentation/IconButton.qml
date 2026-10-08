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

    ⚠️ **圆形底只盖图标那个正圆，不铺满整条胶囊**（2026-10-06 用户实锤
    「hover 背景和图标没居中」：实测块 107×86、图标中心偏右 7px）。悬停 / 选中的
    底色跟着 ``glyphSlot`` 走，文字那截保持透明 —— 填充的圆心与图标的圆心必须
    同源，改一个要改两个。

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
    // ⚠️⚠️ **四个 padding 必须逐个清零，只写 ``padding: 0`` 不够**
    //（2026-10-06 实测：圆钮 hover 底相对按钮本体偏 +2 / -1）。
    //
    // Qt Quick Controls 里 ``padding`` 与 ``topPadding`` / ``bottomPadding`` 是
    // **各自独立**的属性：派生类写 ``padding: 0`` 覆盖不了基类里显式赋值过的
    // ``topPadding`` / ``bottomPadding``。``Rin.Button`` 正好就显式写了
    // ``padding: 6`` + ``topPadding: 5`` + ``bottomPadding: 7``
    // （``RinUI/components/BasicInput/Button.qml:35-37``）——
    // 净剩 **L2 T5 R2 B7**，于是 Qt 把contentItem 摆成 40×32 并居中。
    //
    // 本控件把 contentItem整个换掉了、自己管内边距，基类那套 padding 布局
    // 只会把图标和填充一起挤歪 → 四边全部显式归零，让 contentItem 拿满整颗按钮。
    padding: 0
    topPadding: 0
    bottomPadding: 0
    leftPadding: 0
    rightPadding: 0
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
        //
        // ⚠️ **宽度只盖图标那个圆（``glyphSlot``），不是铺满整个按钮**
        //（2026-10-06 用户实锤「hover 背景和图标没居中」，实测块 107×86、
        // 图标中心偏 +7px）。「显示按钮文本」打开时按钮是胶囊（图标圆 + 间距 +
        // 文字 + 右留白），若这里 ``anchors.fill: parent``，填充就会铺满整条胶囊：
        // 块变宽而 ``glyphSlot`` 恒在左端，于是**块中心与图标中心必然错开** ——
        // 悬停时看着像「圆底歪了」。
        //
        // 正确形态：填充跟着 ``glyphSlot``（图标那个正圆）走，文字部分保持透明 ——
        // 也正是 L1 ``.tool-btn`` 只给圆加背景、名字那截不加的做法。
        //
        // 声明顺序：必须压在图标**之前**（同层级后声明的在上），否则盖住图标。
        // ``objectName`` 是**几何诊断锚点**（2026-10-06）：肉眼只能看出「歪了」，
        // 判不出歪多少。这枚矩形没有 ``id``（外层拿不到，见 FlyoutSurface 的作用域），
        // 探针 / smoke 就靠这个名字从 ``contentItem`` 的子项里把它挑出来，
        // 直接读 x/width 与 ``glyphSlot`` 比 —— 像素量测会被条的渐变边框吃掉一块，
        // 读树里的真几何才是可信判据。
        Rectangle {
            objectName: "dockButtonFill"
            anchors.fill: glyphSlot
            radius: width / 2
            color: root.active
                ? root.activeFill
                : (root.hovered ? root.hoverFill : "transparent")

            Behavior on color {
                ColorAnimation { duration: Lumi.durationFast }
            }
        }

        /*! 图标槽 —— 恒为 ``hitSize`` 的正圆，图标在它里面居中。
            带名称文本时按钮向右长，图标仍停在左端这个圆里（就是它平时占的位置）。
            ⚠️ **上面的圆底填充也是按它铺的**，两者必须同源，否则填充分区和图标
            对不上（2026-10-06 修的就是这个）。 */
        Item {
            id: glyphSlot
            objectName: "dockButtonGlyphSlot"
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
