import QtQuick
import RinUI as Rin
import Luminalium

/*!
    区块之间的分隔线（横条里的**竖**线）。

    两侧各留 ``dividerGap``，中间一条 ``dividerWidth`` × ``dividerHeight``
    的细线，整体占满内容行高。

    之所以包一层 ``Item`` 而不是直接摆 ``Rin.ToolSeparator``，是因为参考稿里
    分隔线与两侧内容的留白是**对称且成对**的，收成一个组件后调用方
    不会各写一份尺寸。

    颜色必须覆写：RinUI 默认用 ``dividerBorderColor``（白 8.4%），
    而参考稿实测分隔线**比底板更暗**（#292929 附近），换 ``Lumi.dockDivider``。
    ``ToolSeparator`` 基类的 contentItem 没有被任何 id / ``states`` 引用，
    替换是安全的；但它写死了 ``padding/topPadding/bottomPadding = 2``，
    要精确尺寸必须一并覆写成 0。
*/
Item {
    id: root

    property int dividerWidth: 1   /*! 线的**厚度**。 */
    property int dividerHeight: 20 /*! 线的**长度**。 */
    property int dividerGap: 14
    /*! 内容行的跨度 —— 分隔线在其间垂直居中。 */
    property int rowHeight: Lumi.dockHitSize

    width: root.dividerGap * 2 + root.dividerWidth
    height: root.rowHeight

    Rin.ToolSeparator {
        anchors.centerIn: parent
        orientation: Qt.Vertical
        width: root.dividerWidth
        height: root.dividerHeight
        padding: 0
        topPadding: 0
        bottomPadding: 0

        contentItem: Rectangle {
            implicitWidth: parent.width
            implicitHeight: parent.height
            radius: Math.min(width, height) / 2
            color: Lumi.dockDivider
        }
    }
}
