import QtQuick
import RinUI as Rin
import Luminalium

/*!
    分段控件的单页（笔 / 橡皮），**圆形**。

    基类是 ``Rin.SegmentedItem``（= ``TabButton``）：``checked``、组内互斥、
    键盘导航全部由它提供。本组件只把它的**方语言换成圆语言**：

    * 项是**正方形**（``itemWidth = itemHeight = 内容高``）→ 选中钮半径取
      高/2 时正好是**圆**（旧版式是「圆角矩形容器 + 圆角矩形选中板 + 下划线」）；
    * **没有下划线**（基类 contentItem 里那条 ``Indicator`` 随 contentItem 一起被换掉）。

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
    /*! 正方形：项里只有一枚图标，宽 = 高 —— 选中钮取 高/2 半径就是正圆。 */
    property int itemWidth: itemHeight

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
        // 圆钮：选中 > 悬停（与 L1 的 CSS 顺序一致，active 覆盖 hover）。
        // 必须声明在图标**之前**，否则会盖住图标。
        Rectangle {
            id: knob
            anchors.fill: parent
            radius: width / 2
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

        Rin.Icon {
            anchors.centerIn: parent
            icon: root.icon.name
            size: root.glyphSize
            color: root.glyphColor
        }
    }

    // 分段项只有图标，用 ``tools[].label`` 补一个悬停提示
    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
