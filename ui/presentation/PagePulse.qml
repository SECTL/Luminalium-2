import QtQuick

/*!
    页码变化的透明度脉冲 —— 横版 / 竖版翻页**共用**的「页码翻动」表达。

    页码本身就是个小数字，翻页时做位移 / 翻转都太闹；这里只用透明度：
    新页码出现瞬间快速下探到 ``dipOpacity``（留一点残影，避免全隐的
    闪烁感），再以稍长的回程回到 1 —— 一个短促的「呼吸」，把视线
    引到变化上，又不会抢戏。横版（``PresentationDock`` 的页码区）与
    竖版（``SidePager`` 的三行页码）都包这一层，节奏完全一致::

        PagePulse {
            page: Backend.slideIndex
            Rin.Text { ... }   // 页码内容，任意子项
        }

    只监听一个整数值（一般是 ``Backend.slideIndex``），值不变（比如
    轻量刷新回读同页）不触发；组件刚创建时也不触发。动画只动自身
    ``opacity``，与控制条整体的显隐透明度互不干扰。
*/
Item {
    id: root

    /*! 被监听的页码值；变化即播放一次脉冲。 */
    property int page: 0

    /*! 脉冲下探到的最低不透明度。 */
    property real dipOpacity: 0.2
    /*! 下探时长（新页码出现 → 最暗）。 */
    property int dipDuration: 110
    /*! 回升时长（最暗 → 完全显现），比下探长一点，落得柔和。 */
    property int returnDuration: 200

    onPageChanged: pulse.restart()

    SequentialAnimation {
        id: pulse
        NumberAnimation {
            target: root
            property: "opacity"
            to: root.dipOpacity
            duration: root.dipDuration
            easing.type: Easing.OutQuad
        }
        NumberAnimation {
            target: root
            property: "opacity"
            to: 1.0
            duration: root.returnDuration
            easing.type: Easing.OutCubic
        }
    }
}
