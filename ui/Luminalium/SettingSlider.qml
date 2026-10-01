import QtQuick
import QtQuick.Layouts
import RinUI as Rin

/*!
    设置项里的**滑块 + 数值读数**（放在 ``SettingCard`` 右侧那一格）。

    2026-10-01 用户指令：「把能改成滑块的改成滑块」—— 有明确上下限、且**边拖边看
    效果**的数值项（边距 / 不透明度 / 轮询间隔）用滑块比 SpinBox 直观得多。

    用法：

        SettingSlider {
            primaryColor: Lumi.accent
            from: 0; to: 200; stepSize: 1
            suffix: " px"
            value: Backend.settings.presentation_margin_x
            onMoved: Backend.setSetting("presentation_margin_x", Math.round(value))
        }

    ⚠️ **必须在 ``onMoved`` 里写回配置，而不是 ``onValueChanged``**：

    * ``moved`` 只在**用户动手**时发；``valueChanged`` 在程序改 ``value`` 时也发，
      一挂上去就是「写配置 → 广播 → 重读配置 → 再写」的死循环；
    * 写配置本身已经做了延迟落盘合并（``bridge.Backend._save_timer``），拖一次
      不会再往磁盘上刷几十遍。

    ⚠️ 组件在 ``Luminalium`` 模块里、**不 import 自己**：强调色由调用方传
      （``primaryColor: Lumi.accent``）—— 否则就是模块自引用，QML 会给出
      「circular import」类告警。
*/
RowLayout {
    id: root

    /*! 数值读数的固定宽度。定住它，拖动时右侧那串字不会被挤得左右跳。 */
    property int valueWidth: 60
    /*! 数值后缀（``" px"`` / ``" %"`` / ``" ms"``）。 */
    property string suffix: ""
    /*! 小数位数（不透明度这类 0~1 的值先自己乘 100，再按整数显示）。 */
    property int decimals: 0
    /*! 滑块自己的宽度。 */
    property real sliderWidth: 168

    property alias from: slider.from
    property alias to: slider.to
    property alias stepSize: slider.stepSize
    property alias value: slider.value
    property alias primaryColor: slider.primaryColor

    /*! 用户拖出来的值（只在手指动作时发，程序改 ``value`` 不发）。 */
    signal moved(real value)

    spacing: 12

    Rin.Text {
        Layout.preferredWidth: root.valueWidth
        Layout.alignment: Qt.AlignVCenter
        horizontalAlignment: Text.AlignRight
        typography: Rin.Typography.BodyStrong
        text: slider.value.toFixed(root.decimals) + root.suffix
    }

    Rin.Slider {
        id: slider
        Layout.preferredWidth: root.sliderWidth
        Layout.alignment: Qt.AlignVCenter
        onMoved: root.moved(value)
    }
}
