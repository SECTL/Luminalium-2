import QtQuick
import RinUI as Rin
import Luminalium

/*!
    工具分段控件容器（笔 / 橡皮）。

    基类是 ``Rin.Segmented``（= ``TabBar``），组内互斥与键盘导航由它提供。
    子项经 ``contentData`` 进入其内部列表，所以在这里直接写
    ``ToolSegmentItem``（含 ``Repeater``）即可。

    只重写 ``background``（安全：``TabBar`` 基类的 background 没有被任何 id 或
    ``states`` 引用，不像 ``SegmentedItem`` 那样一旦替换就构造期抛 null）：

    * 底色 ``Lumi.dockSegmentBg`` —— 参考稿实测容器 **比底板更暗**
      （#292929 vs 底板 #2E2E2E，即黑 10% 叠加）；
    * 描边 ``Lumi.dockSegmentBorder`` —— 参考稿是 **极淡白描边**
      （#3E3E3E ≈ 白 8%），而 RinUI 默认是 ``controlBorderColor``（黑 9%），
      压在深色底板上等于看不见，与稿不符。

    ``implicitWidth`` 要自己把 padding 加回来：``Rin.Segmented`` 覆写成了
    ``implicitWidth: contentWidth``，没算 padding；padding 改非 0 时会少一截。

    ``leftPadding`` / ``rightPadding`` 取 ``dockSegmentPlateInset``：
    参考稿的选中板比容器左右各内缩约 9% 项宽，而上下不内缩
    （容器高 == 内容高 == 退出键高，实测三者都是 121/187）。
*/
Rin.Segmented {
    id: root

    property int itemHeight: Lumi.dockHitSize

    implicitWidth: contentWidth + leftPadding + rightPadding
    implicitHeight: itemHeight
    height: implicitHeight
    spacing: 0
    leftPadding: Lumi.dockSegmentPlateInset
    rightPadding: Lumi.dockSegmentPlateInset
    topPadding: 0
    bottomPadding: 0

    background: Rectangle {
        radius: Lumi.dockSegmentRadius
        color: Lumi.dockSegmentBg
        border.width: 1
        border.color: Lumi.dockSegmentBorder
    }
}
