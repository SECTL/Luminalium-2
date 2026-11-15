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
    * 两个分页各自是**圆形**（见 ``ToolSegmentItem``），选中的那页浮现一枚
      与容器同高的圆钮 —— 所以容器高 = 分页高 = 内容高，上下不留 padding。

    2026-10-09 用户指令「把小黑板的胶囊照搬 PPT 叠加层内的胶囊」：
    容器底色从 ``Lumi.dockSegmentBg``（主题令牌，浅色档是黑 6%）换成
    **固定深色壳**，数值取自当时的小黑板胶囊（黑 55% + 白 18% 细边；黑板
    那版胶囊后来重做过，2026-11-01 起小黑板反过来直接复用本组件，这两个值
    以这里为准）。理由与黑板同源：控制条浮在
    **任意幻灯片内容**之上，主题自适应的浅底压在亮幻灯片上会失去对比，
    固定深壳在亮暗幻灯片上都立得住（小黑板头注释 2026-10-09 条目的
    「黑板就是深色物件」类推到「放映画面颜色不可预知」）。⚠️ 描边同样
    **不能用** ``Lumi.hairline``（浅色档黑 8%，压在深壳上等于没有），
    用固定的白 hairline。

    只重写 ``background``：``TabBar`` 基类没有任何 id 或 ``states`` 引用
    background（不像 ``SegmentedItem`` 那样一旦替换就在构造期抛 null），
    所以这里是安全的。但 ``implicitWidth`` 得自己把 padding 加回来 ——
    ``Rin.Segmented`` 覆写成 ``implicitWidth: contentWidth``，没算 padding。

    子项经默认属性直接进入容器（``Repeater`` 也行），所以在这里直接写
    ``ToolSegmentItem`` 即可。

    ⚠️ 静态子项（直接写在 ``ToolSegment { }`` 里、不经 Repeater）要在实例上
    显式给 ``contentWidth``：TabBar 按样式缺省 spacing 算 contentWidth，
    ``spacing: itemSpacing`` 绑定后到时不重算，槽会窄一截（2026-11-01 小黑板
    离屏实测窄 3px，修法见 BlackboardWindow.qml 的 ``toolSegment``）。
    放映条的分页走 Repeater、建得晚，不受影响。
*/
Rin.Segmented {
    id: root

    property int itemHeight: Lumi.dockHitSize
    /*! 容器左右留白（上下为 0：分页高 = 容器高）。 */
    property int edgePadding: Lumi.dockSegmentPadding
    property int itemSpacing: Lumi.dockSegmentSpacing

    /*! 竖排（两侧合并布局）—— 见下面 ``implicitWidth`` 与 ``Component.onCompleted``。 */
    property bool vertical: false
    /*! 子项个数（竖版自己算高要用）。 */
    readonly property int itemCount: contentChildren.length

    /*! 钳制后的**实际**圆角（胶囊时为 短边/2）。自检会读这个值。 */
    readonly property real effectiveRadius: bg.radius

    /*! ⚠️ **竖版不能靠 ``contentWidth``**（2026-10-07 / 2026-10-13 实测踩坑）：
        外层 ``FlyoutSurface`` 的 ``inner`` 是 ``Flow``，它的 ``implicitWidth`` 在
        ``TopToBottom`` 下取「最宽子项的 implicitWidth」；而本组件的基类
        ``Rin.Segmented``（= ``TabBar``）内部 ``contentItem`` 是横向 ``ListView``，
        不显式切纵向并给对宽度时：
        1. 子项仍横向排成 140px 宽，把外层竖条撑成 254×286 的圆饼；
        2. 早期误把竖版 ``implicitHeight`` 的累加式拷给 ``implicitWidth``，导致竖版宽也算成 140px。
        竖版下宽度恒为单列项宽（``itemHeight``）加左右内边距（竖版左右留白为 0，
        沿轴留白转置到上下），高度按「项数 × 项高 + 间距 + 上下留白」算。 */
    implicitWidth: vertical
        ? itemHeight + leftPadding + rightPadding
        : contentWidth + leftPadding + rightPadding
    implicitHeight: vertical
        ? itemCount * itemHeight + Math.max(0, itemCount - 1) * itemSpacing
            + topPadding + bottomPadding
        : itemHeight
    width: implicitWidth
    height: implicitHeight
    spacing: itemSpacing
    leftPadding: vertical ? 0 : edgePadding
    rightPadding: vertical ? 0 : edgePadding
    topPadding: vertical ? edgePadding : 0
    bottomPadding: vertical ? edgePadding : 0

    function _syncOrientation() {
        if (root.contentItem && root.contentItem.orientation !== undefined) {
            root.contentItem.orientation = root.vertical
                ? ListView.Vertical : ListView.Horizontal
        }
    }

    onVerticalChanged: _syncOrientation()
    Component.onCompleted: _syncOrientation()

    background: Rectangle {
        id: bg
        // 胶囊：请求值超过 短边/2 就按 短边/2 收（横条短边是高、竖条短边是宽）
        radius: Math.min(
            Lumi.dockSegmentRadius,
            Math.round(Math.min(root.width, root.height) / 2)
        )
        // 固定深色壳（2026-10-09，见文件头）：不读主题令牌；小黑板胶囊
        // 复用本组件（2026-11-01），改这里两边一起变
        color: Qt.rgba(0, 0, 0, 0.55)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.18)
    }
}
