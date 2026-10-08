import QtQuick
import RinUI as Rin
import Luminalium

/*!
    工具分段控件的容器（指针 / 笔 / 橡皮，分页由 ``presentation.tools`` 配置驱动）。

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

    /*! 竖排（两侧合并布局）—— 见头注释「竖版为什么不能靠 contentWidth」。 */
    property bool vertical: false
    /*! 子项个数（竖版自己算宽要用）。 */
    readonly property int itemCount: contentChildren.length

    /*! 钳制后的**实际**圆角（胶囊时为 高/2）。自检会读这个值。 */
    readonly property real effectiveRadius: bg.radius

    /*! ⚠️ **竖版不能靠 ``contentWidth``**（2026-10-07 实测踩坑）：外层
        ``FlyoutSurface`` 的 ``inner`` 是 ``Flow``，它的 ``implicitWidth`` 在
        ``TopToBottom`` 下取「最宽子项的 implicitWidth」；而本组件的
        ``contentWidth`` 又来自基类那行随容器宽走的 Row —— 两边互相等对方的宽，
        收敛到一个偏小值，结果 3 个钮只排得下 2 个（工具段被默默截掉一枚）。
        竖版与子项数无关，自己按「项数 × 项高 + 间距 + 留白」算，断开这个环。
        项全等高（``ToolSegmentItem`` 纯图标时宽 = 高），横向不折行。 */
    implicitWidth: vertical
        ? itemCount * itemHeight + Math.max(0, itemCount - 1) * itemSpacing
            + leftPadding + rightPadding
        : contentWidth + leftPadding + rightPadding
    implicitHeight: vertical
        ? itemCount * itemHeight + Math.max(0, itemCount - 1) * itemSpacing
            + topPadding + bottomPadding
        : itemHeight
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
