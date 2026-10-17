import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    聚光灯插件的设置页（2026-10-06 聚光灯插件）。

    两个滑条都**边拖边看效果**：

    * 遮罩浓度直写 ``plugins_spotlight_dim``，遮罩 QML 直读该键
      （settingsChanged 推重读），拖动即变；
    * 光斑大小写 ``plugins_spotlight_radius``，插件的 side_effect 实时改
      会话值并重设光斑（键盘 / 胶囊按钮的会话调整不回写这里 —— 写回
      配置会把「试出来的大小」变成永久默认，语义就乱了）。

    滑条走 ``onMoved`` 写回而不是 ``onValueChanged``（后者程序改值也发，
    一挂上去就是「写配置 → 广播 → 重读 → 再写」死循环 —— 见
    ``Luminalium/SettingSlider.qml`` 头注释）。

    2026-10-08：「怎么退出」卡片补上「光斑外点击被遮住」与「+ / − 全局
    生效」两句 —— 遮罩吃点击却无任何说明时，用户把这堵看不见的点击墙
    当成「电脑卡死」；说明文字是唯一出路（刻意**不加**点击穿透开关，
    遮罩吃点击是设计语义本身）。文案长到 4 行开外，SettingCard 的
    description 是 ``maximumLineCount: 3`` + ``ElideRight``（RinUI 包内
    写死，不能改包）会把最关键的「+ / − 全局」一句吃掉，所以这张卡用
    ``Rin.Frame`` 自绘同款版式（内边距 18/16、图标 22、Body + Caption
    与 SettingCard 逐一对齐），说明文字不设行数上限 —— 先例是
    ``MainInterface.qml`` 的推广卡。
*/
Rin.FluentPage {
    id: page

    title: qsTr("聚光灯")
    contentSpacing: 10

    Rin.SettingCard {
        objectName: "spotlightDimCard"

        Layout.fillWidth: true
        title: qsTr("遮罩浓度")
        description: qsTr("光斑之外压暗的程度；开着的遮罩上拖动即刻生效")
        icon.name: "ic_fluent_flashlight_20_regular"

        SettingSlider {
            primaryColor: Lumi.accent
            // 下限 5 而不是 0：全透明遮罩仍会吃掉光斑外的所有点击（窗口命中
            // 按区域算），一块看不见的点击墙像「电脑卡死」—— 见遮罩 QML 同日注释
            from: 5; to: 85; stepSize: 1
            suffix: " %"
            value: Backend.settings.plugins_spotlight_dim
            onMoved: Backend.setSetting("plugins_spotlight_dim", Math.round(value))
        }
    }

    Rin.SettingCard {
        objectName: "spotlightRadiusCard"

        Layout.fillWidth: true
        title: qsTr("光斑大小")
        description: qsTr("光斑半径占屏幕短边的百分比；遮罩开着时拖动即刻生效")
        icon.name: "ic_fluent_circle_small_20_regular"

        SettingSlider {
            primaryColor: Lumi.accent
            from: 6; to: 70; stepSize: 1
            suffix: " %"
            value: Backend.settings.plugins_spotlight_radius
            onMoved: Backend.setSetting("plugins_spotlight_radius", Math.round(value))
        }
    }

    /*! 说明卡（无操作项）：Rin.Frame 自绘 SettingCard 版式，缘由见头注释。
        Frame 的 contentItem 没有隐式高度（``MainInterface.qml`` 推广卡同坑），
        高度 = 行布局隐式高 + 上下内边距，随文案换行行数自适应。 */
    Rin.Frame {
        id: exitCard

        objectName: "spotlightExitCard"
        Layout.fillWidth: true
        // 静态说明卡不跟 hover 提亮（Frame 默认 hoverable）
        hoverable: false
        leftPadding: 18
        rightPadding: 18
        topPadding: 16
        bottomPadding: 16
        Layout.preferredHeight: exitRow.implicitHeight
                                + exitCard.topPadding + exitCard.bottomPadding

        RowLayout {
            id: exitRow
            width: exitCard.availableWidth
            spacing: 18

            Rin.Icon {
                icon: "ic_fluent_question_circle_20_regular"
                size: 22
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                Rin.Text {
                    Layout.fillWidth: true
                    typography: Rin.Typography.Body
                    text: qsTr("怎么退出")
                }
                Rin.Text {
                    Layout.fillWidth: true
                    typography: Rin.Typography.Caption
                    color: Lumi.textSecondary
                    wrapMode: Text.Wrap
                    text: qsTr("遮罩顶部的 ✕ 胶囊按钮、快捷面板磁贴或放映控制条动作都可关闭；光斑以外的区域点击会被遮住（方向键与滚轮始终归放映窗口）；键盘 + / − 在任何界面都会调光斑大小")
                }
            }
        }
    }
}
