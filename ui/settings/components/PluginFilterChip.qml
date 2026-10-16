import QtQuick
import RinUI as Rin
import Luminalium

/*!
    插件页筛选胶囊。

    2026-10-17（用户指令「这个 roundbutton 明显不是 rinui 的」）：改回 **RinUI 自家
    的 ``Rin.PillButton``**（``RoundButton``：药丸底 + ``controlQuaternaryColor``
    底 / 强调色实底 + 悬停·按压·焦点·禁用四态 + 底部指示条），不再用 ``Rin.Clip``
    加手绘 ``Rectangle`` 仿一个。文字色、圆角、状态动画全部由 RinUI 给。

    只覆写两处，都是**尺寸**（RinUI 的默认尺寸不是设计稿那一档）：

    * ``implicitHeight`` → 31（``Button`` 默认 32）；
    * ``implicitWidth`` → 文字宽 + 23 —— ``Button`` 把宽度写死成
      ``内容宽 + 26``，而设计稿逐枚量得 51 / 79 / 107 对 28 / 56 / 84 个汉字宽，
      差都是 23。宽度得自己算，所以下面另起了一枚**同款字**的隐形 ``Rin.Text``
      当尺子（同类型同 ``Typography.Body``，量出来的宽度才和按钮内部那枚一致）。

    ⚠️ 选中态**不用 ``checked``**：``PillButton`` 基类把 ``highlighted`` 绑在
    ``checked`` 上且 ``checkable`` 为真，点一下会把状态翻掉、并顺手摘掉绑定
    （C++ 侧 ``setChecked`` 的老毛病）。本页的选中态只有一个来源
    （``page.kindFilter``），所以这里取消 ``checkable``、把 ``highlighted``
    直接指过去：指哪亮哪，按钮自己不记状态。
*/
Rin.PillButton {
    id: root

    property string label: ""
    property bool selected: false

    text: root.label
    /*! RinUI 主题色的 ``primaryColor`` 跟的是**系统**主题色，本项目的强调色是
        自己的配置项（``Backend.accent``），必须显式传进来 —— 与 ``Rin.Switch``
        / ``Rin.Segmented`` 那些调用点同一写法。 */
    primaryColor: Lumi.accent

    checkable: false
    highlighted: root.selected

    implicitHeight: Lumi.pluginChipHeight
    implicitWidth: Math.max(40, Math.round(chipMetrics.implicitWidth)
                                + Lumi.pluginChipPadding)

    /*! 量宽用的隐形尺子。``visible: false`` 不影响 ``implicitWidth`` 的求值。 */
    Rin.Text {
        id: chipMetrics
        visible: false
        typography: Rin.Typography.Body
        text: root.label
    }
}
