import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    主页的「链接卡」与插件页的「导入磁贴」—— **同一张卡**，两个尺寸。

    版式沿用 CW2 的 ``Component card``（``Home.qml`` 里那两张外链卡）：
    ``Rin.Clip`` 打底（= Button：可点、可聚焦、悬停自带高亮），主图标 + 撑开 +
    标题 + 右下角一枚 open 角标，**整张卡就是点击区**（右下角那枚角标是
    「点这里会弹出去」的提示，不是第二个语义）。

    2026-10-17 合并：原先插件页另起了一份 ``PluginImportTile``，被指出「复用
    主页那两个 card 调整一下大小即可」—— 确实是一回事。两份合并到这里，
    差异全部做成参数（默认值就是主页那份，插件页覆写）：

      * 主页：128 高 / 图标 32 / 标题 18（``BodyLarge``）/ **图标靠左**；
      * 插件页：116 高 / 图标 24 / 标题 16 / **图标靠左** —— 设计稿的导入磁贴
        是「左上图标 + 左下标题」的对角版式，不是居中。

    ⚠️ **属性叫 ``label``，不叫 ``title``**：``tools/preview.py`` 的 ``_is_page``
    用「有没有 ``title`` 属性」区分「整页」与「页面里的组件」，``ui/settings/**``
    下任何一个带 ``title`` 的组件都会被当成设置页单独渲一张 ``page_*.png``
    （2026-10-17 实测过一次：那块磁贴在一张 940 高的图里孤零零地出过镜）。
    要改名之前先看 ``_is_page``。
*/
Rin.Clip {
    id: root

    /*! 左下角的标题（「GitHub」/「导入文件夹」）。 */
    property string label: ""
    /*! 主图标（Fluent 字体图标名）。 */
    property string iconName: ""
    /*! 悬停提示 —— 卡里只剩得下标题，具体情况（选什么、装到哪）挂在这里。 */
    property string tooltip: ""

    property int iconSize: 32
    property int glyphSize: 18
    property int contentPadding: 18
    /*! 下内边距单独一档（<= 0 时跟 ``contentPadding``）。设计稿的磁贴上下并不
        对称：上 20、下 16 —— 标题贴着下缘那一档比上缘紧一点。 */
    property int contentPaddingBottom: -1
    property int contentSpacing: 18
    property int glyphMargin: 12
    /*! 主图标靠左：主页与插件页磁贴共用这一对齐方式（2026-10-17 用户指令）。 */
    property bool centerIcon: false
    /*! 标题的字号 / 字重。``titleTypography`` 先定基线（行高也跟它走），下面
        两行再压字号与字重 —— 设计稿的磁贴标题是 16，落在 RinUI 字号梯的
        Body 14 与 BodyLarge 18 中间，梯上没有 16，只能显式给。 */
    property int titleTypography: Rin.Typography.BodyLarge
    property int titlePixelSize: 18
    property int titleWeight: Font.DemiBold

    implicitWidth: 220
    implicitHeight: 128

    /*! 描边走 ``Lumi.hairline``（= 主题的 DividerStrokeColorDefault），**不能**
        用 ``Rin.Clip`` 基类 ``Frame`` 自带的 ``cardBorderColor`` —— 那一支在
        深色档是「黑 9%」，压在深色页底上等于没有，磁贴就读不出边界（铁律 4；
        主页那两张卡也是同一个毛病，一并修在这里）。 */
    radius: Lumi.pluginTileRadius
    border.width: 1
    border.color: Lumi.hairline

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: root.contentPadding
        anchors.rightMargin: root.contentPadding
        anchors.topMargin: root.contentPadding
        anchors.bottomMargin: root.contentPaddingBottom > 0
                             ? root.contentPaddingBottom : root.contentPadding
        /*! ⚠️ ``spacing`` 必须是 0：撑开的 ``Item`` 会让 ColumnLayout 在它**上下
            各算一次** spacing，图标 30 + 标题行盒 24 + 20×2 = 94 超过磁贴的可用
            高度 81，标题被挤出容器下缘 13px（2026-10-17 用户指出「这里是不是缺
            下边距」—— 其实是被挤出去了，不是内边距设小了）。图标与标题之间的
            间距改由 ``Item`` 自己的 ``preferredHeight`` 给。 */
        spacing: 0

        Rin.Icon {
            Layout.alignment: root.centerIcon ? Qt.AlignHCenter : Qt.AlignLeft
            name: root.iconName
            size: root.iconSize
        }

        Item {
            Layout.fillHeight: true
            Layout.preferredHeight: root.contentSpacing
        }

        Rin.Text {
            Layout.fillWidth: true
            typography: root.titleTypography
            font.pixelSize: root.titlePixelSize
            font.weight: root.titleWeight
            text: root.label
        }
    }

    /*! 右下角 open 角标（CW2 是 ``IconWidget``，RinUI 0.4.4.1 没有 —— 用
        ``Rin.Icon`` 按同样的锚点与尺寸摆，见 ``Home.qml`` 历史注释）。 */
    Rin.Icon {
        anchors {
            bottom: parent.bottom
            right: parent.right
            margins: root.glyphMargin
        }
        size: root.glyphSize
        name: "ic_fluent_open_20_regular"
    }

    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
