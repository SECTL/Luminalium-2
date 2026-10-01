import QtQuick
import RinUI as Rin
import Luminalium

/*!
    分段控件的单页（指针 / 笔 / 橡皮），**圆形**。

    基类是 ``Rin.SegmentedItem``（= ``TabButton``）：``checked``、组内互斥、
    键盘导航全部由它提供。本组件只把它的**方语言换成圆语言**：

    * 项是**正方形**（``itemWidth = itemHeight = 内容高``）→ 选中钮半径取
      高/2 时正好是**圆**（旧版式是「圆角矩形容器 + 圆角矩形选中板 + 下划线」）；
    * **没有下划线**（基类 contentItem 里那条 ``Indicator`` 随 contentItem 一起被换掉）。

    ## 名称文本（``label`` / ``showLabel``）

    「显示按钮文本」打开后（``presentation.buttons.show_labels``），项从正方形
    长成胶囊：图标仍在左端那个高×高的方格里居中，右边接名称文字 ——
    容器（``ToolSegment``）宽度由 ``contentWidth`` 自己跟着变，不用另外接线。

    ⚠️ 文字宽度同样用**隐藏探针**量（见 ``IconButton.qml`` 的说明），
    不抄字体族与字号。

    ⛔ **绝不能替换 ``background`` 对象**：``SegmentedItem`` 基类的 ``states`` 里有
    ``PropertyChanges { target: background; scale: 0.95 }``，构造期就会解析这个 target；
    background 一旦被换掉，旧对象不存在 → 构造期直接抛
    ``TypeError: Cannot read property 'width' of null``，窗口都建不起来。

    ✅ 所以走和 ``IconButton`` 同一条路：**把基类那块选中板就地压平**（颜色透明、
    描边 0），填充改由 ``contentItem`` 底层的圆自己画。这样还能顺手做两件基类
    给不了的事 —— 形状恒定是圆（基类未选中时是个内缩的圆角小方块）、按下时
    圆钮缩到 0.95。

    换 ``contentItem`` 的两个连带契约（都得一起满足，否则 ``ReferenceError``）：

    * ``implicitWidth`` / ``implicitHeight`` —— 基类这两个绑定引用了默认
      contentItem 里的 ``row``；
    * 基类给图标留的 ``IconWidget`` 只设 ``width/height``、**不设 ``size`` 也不给
      颜色**（``Rin.Icon`` 的字形大小由 ``size`` 驱动，默认 16；颜色默认黑），
      所以图标必须自己画。
*/
Rin.SegmentedItem {
    id: root

    property int glyphSize: Lumi.dockIconSize
    property color glyphColor: Lumi.textPrimary
    property string tooltip: ""
    property int itemHeight: Lumi.dockHitSize
    /*! 按钮的名称文本（工具分页的 ``label``：「鼠标指针」「笔」「橡皮」）。 */
    property string label: ""
    /*! 是否在图标旁显示 ``label``。 */
    property bool showLabel: false
    /*! 「这个工具的选单正开着」（目前只有笔有选单）。
        选中钮外面再套一圈主题色描边 —— 顶层窗口是整窗穿透的，选单也没有关闭
        按钮，用户唯一的退路就是「再点一下这个工具」；没有这圈提示，他很难
        知道「再点一下能关」。 */
    property bool expanded: false

    /*! 图标与文字之间的间距 / 文字右端留白（与 ``IconButton`` 同档）。 */
    readonly property int labelGap: Lumi.dockLabelGap
    readonly property int labelTrail: Lumi.dockLabelTrail
    readonly property bool labelVisible: showLabel && label !== ""

    /*! 项宽：纯图标时是**正方形**（宽 = 高 → 选中钮取 高/2 半径就是正圆）；
        带名称文本时向右长成胶囊。 */
    readonly property int itemWidth: labelVisible
        ? itemHeight + labelGap + Math.ceil(labelProbe.implicitWidth) + labelTrail
        : itemHeight

    /*! 宽度探针 —— 与下面可见的那个标签**同组件同字阶**，宽度天然一致。 */
    Rin.Text {
        id: labelProbe
        visible: false
        typography: Rin.Typography.Body
        wrapMode: Text.NoWrap
        text: root.label
    }

    implicitWidth: itemWidth
    implicitHeight: itemHeight
    width: itemWidth
    height: itemHeight
    padding: 0

    // 见文件头：基类的选中板就地压平（不换对象、不删对象）
    Component.onCompleted: {
        var plate = root.background
        if (plate) {
            plate.color = "transparent"
            plate.border.width = 0
        }
    }

    contentItem: Item {
        // 圆钮 / 胶囊钮：选中 > 悬停（与 L1 的 CSS 顺序一致，active 覆盖 hover）。
        // 必须声明在图标**之前**，否则会盖住图标。
        Rectangle {
            id: knob
            anchors.fill: parent
            // 短边的一半 —— 正方形时是正圆，带名称文本时是胶囊
            radius: Math.min(width, height) / 2
            color: root.checked
                ? Lumi.dockSegmentCheckedBg
                : (root.hovered ? Lumi.dockButtonHoverFill : "transparent")
            // 基类的按下反馈落在被压平的那块板上，这里自己补一份
            scale: root.pressed ? 0.95 : 1

            Behavior on color {
                ColorAnimation { duration: Lumi.durationFast }
            }
            Behavior on scale {
                NumberAnimation {
                    duration: Lumi.durationFast
                    easing.type: Easing.OutQuart
                }
            }
        }

        /*! 「选单开着」的提示环（见 ``expanded``）。画在圆钮**之后**（= 上面），
            贴着项的外沿，1px 主题色。 */
        Rectangle {
            objectName: "segmentExpandedRing"
            visible: root.expanded
            anchors.fill: parent
            radius: Math.min(width, height) / 2
            color: "transparent"
            border.width: 1
            border.color: Lumi.accent
        }

        /*! 图标槽 —— 恒为 ``itemHeight`` 的正方形，图标在它里面居中。 */
        Item {
            id: glyphSlot
            width: root.itemHeight
            height: root.itemHeight
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter

            Rin.Icon {
                anchors.centerIn: parent
                icon: root.icon.name
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
            color: root.glyphColor
            text: root.label
        }
    }

    // 分段项用 ``tools[].label`` 补一个悬停提示（关掉名称文本时它就是唯一的名字来源）
    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
