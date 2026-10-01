import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    编辑器右侧面板里的**平铺式**设置项：名称独占一行，控件排在**它下面**，
    整块**不带卡片底板、不带边框**。

    2026-10-01（第五轮）用户指令（附 Windows 11「设置 → 通知」截屏）：「主界面编辑器的
    组件设置内容其实不应该用常规的设置卡，而是类似图片的这种平铺设置名称和
    dropdown / 开关 / 选项」。

    ## 为什么不用 ``Rin.SettingCard``

    那是「左标题 / 右控件」**并排**的两栏卡：自带卡片底板 + 16px 上下内边距。
    放进这块只有 340 宽的窄面板里，两个问题都很实在：

    * 并排两栏把标题挤成两行、把控件挤窄 —— 本项目连着踩过两次
      （「退出键样式」第一版标题折行、「翻页组件位置」下拉窄到选项文字显示不全）；
    * 设置项一多，一张张卡片的底板把面板切成一格一格，与 Win11 设置页那种
      **一列平铺**的观感差得远（用户给的就是 Win11 的截图）。

    ## 用法

    子项**就是控件**，可以放任意几个（开关行 / 下拉 / 一组选项），它们会按顺序
    竖着排在名称下面：

        InspectorSetting {
            objectName: "editorSettingPagerPosition"
            title: qsTr("翻页组件位置")

            Rin.RadioButton { text: qsTr("竖版两侧中间"); ... }
            Rin.RadioButton { text: qsTr("横版两侧下部"); ... }
        }

    ⚠️ 控件**左对齐**、各按自己的隐式宽度排（``controlColumn`` 的子项不给
    ``Layout.fillWidth``）—— 与截屏里那种「控件与名称左对齐、宽度够用就好」
    的排法一致。下拉这类需要定宽的，自己写 ``Layout.preferredWidth``。

    ⚠️ 整个组件只是个 **ColumnLayout**，所以调用方那层 ``visible`` 照旧生效
    （布局器会跳过不可见项）—— 「设置项跟着选中的组件走」靠的就是它。
*/
ColumnLayout {
    id: root

    /*! 控件落点：本组件的所有子项都进这里。 */
    default property alias content: controlColumn.data

    /*! 设置名称（独占一行）。 */
    property string title: ""
    /*! 名称下方的一行浅色说明（可空 —— 窄面板里多数设置不需要它）。 */
    property string description: ""
    /*! 名称与控件之间、以及各控件之间的间距。 */
    property int itemSpacing: 8

    Layout.fillWidth: true
    spacing: root.itemSpacing

    Rin.Text {
        Layout.fillWidth: true
        visible: root.title.length > 0
        typography: Rin.Typography.BodyStrong
        color: Lumi.textPrimary
        text: root.title
    }

    Rin.Text {
        Layout.fillWidth: true
        visible: root.description.length > 0
        typography: Rin.Typography.Caption
        color: Lumi.textSecondary
        text: root.description
        wrapMode: Text.Wrap
    }

    ColumnLayout {
        id: controlColumn
        Layout.fillWidth: true
        spacing: 6
    }
}
