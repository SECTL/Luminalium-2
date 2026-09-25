import QtQuick
import RinUI as Rin
import Luminalium

/*!
    工具分段控件的容器（笔 / 橡皮）。

    基类是 ``Rin.Segmented``（= ``TabBar``，Container 家族）：**组内互斥**、
    ``currentIndex``、键盘导航都由它提供 —— 这正是「用 RinUI 的 Segmented」
    而不是自己搓的理由。

    形态是**圆的**（对照 L1 的设计语言）：

    * 容器 = 全圆胶囊（``border-radius: 999px`` 那套，按 高/2 钳制）；
    * 底色 ``Lumi.dockSegmentBg`` 比底板亮一档，读出「这是一只凹槽」；
    * 两个分页各自是**圆形**（见 ``ToolSegmentItem``），选中的那页浮现一枚
      与容器同高的圆钮 —— 所以容器高 = 分页高 = 内容高，上下不留 padding。

    只重写 ``background``：``TabBar`` 基类没有任何 id 或 ``states`` 引用
    background（不像 ``SegmentedItem`` 那样一旦替换就在构造期抛 null），
    所以这里是安全的。但 ``implicitWidth`` 得自己把 padding 加回来 ——
    ``Rin.Segmented`` 覆写成 ``implicitWidth: contentWidth``，没算 padding。

    子项经默认属性直接进入容器（``Repeater`` 也行），所以在这里直接写
    ``ToolSegmentItem`` 即可。
*/
Rin.Segmented {
    id: root

    property int itemHeight: Lumi.dockHitSize
    /*! 容器左右留白（上下为 0：分页高 = 容器高）。 */
    property int edgePadding: Lumi.dockSegmentPadding
    property int itemSpacing: Lumi.dockSegmentSpacing

    /*! 钳制后的**实际**圆角（胶囊时为 高/2）。自检会读这个值。 */
    readonly property real effectiveRadius: bg.radius

    implicitWidth: contentWidth + leftPadding + rightPadding
    implicitHeight: itemHeight
    height: implicitHeight
    spacing: itemSpacing
    leftPadding: edgePadding
    rightPadding: edgePadding
    topPadding: 0
    bottomPadding: 0

    background: Rectangle {
        id: bg
        // 胶囊：请求值超过 高/2 就按 高/2 收（Qt 的 Rectangle 不会自己钳）
        radius: Math.min(Lumi.dockSegmentRadius, Math.round(root.height / 2))
        color: Lumi.dockSegmentBg
        border.width: 0
    }
}
