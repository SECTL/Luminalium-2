import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    放映控制条：位置与外观细节。

    轮询间隔在**调试窗口**里（隐藏入口：在设置窗口标题文本上连点 10 次）。

    2026-10-01 按用户指令删掉两块：
    * **总开关**（「放映时显示控制条」）—— 配置键 ``presentation.enabled``
      连同 ``windows.py::show_docks`` 里的判断一并移除，探测到放映就显示；
    * **检测状态卡片**（原来显示识别到的软件族与窗口句柄）—— 属于放映状态
      显示，连同 ``Backend.presentingKind`` / ``presentingWindow`` 一起删除。
      排查「探测认没认出放映窗口」改看日志：``logs/luminalium.log``。
*/
Rin.FluentPage {
    id: page

    title: qsTr("放映")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("位置")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("水平边距")
        description: qsTr("控制条距屏幕左右边缘的距离（像素，屏幕上量到的值；默认 20 对齐 Luminalium 1）")
        icon.name: "ic_fluent_arrow_bidirectional_left_right_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 140
            from: 0
            to: 200
            value: Backend.settings.presentation_margin_x !== undefined
                ? Backend.settings.presentation_margin_x : 20
            onValueModified: Backend.setSetting("presentation_margin_x", value)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("垂直边距")
        description: qsTr("控制条距屏幕上下边缘的距离（像素，以整屏边缘为基准，不受任务栏影响；默认 20 对齐 Luminalium 1）")
        icon.name: "ic_fluent_arrow_bidirectional_up_down_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 140
            from: 0
            to: 200
            value: Backend.settings.presentation_margin_y !== undefined
                ? Backend.settings.presentation_margin_y : 20
            onValueModified: Backend.setSetting("presentation_margin_y", value)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("目标显示器")
        description: qsTr("宽屏放映时把控制条钉在指定屏幕上")
        icon.name: "ic_fluent_desktop_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: [qsTr("跟随放映窗口"), qsTr("主显示器")]
            currentIndex: Backend.settings.presentation_screen_index === -1 ? 0 : 1
            onActivated: Backend.setSetting("presentation_screen_index", currentIndex === 0 ? -1 : 0)
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("外观")
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("底板不透明度")
        description: qsTr("底板越透，放映画面越能透出来，渐变高光越像 CW2 小组件的材质光泽；默认 65%")
        icon.name: "ic_fluent_blur_20_regular"

        Rin.SpinBox {
            Layout.preferredWidth: 160
            from: 20
            to: 100
            stepSize: 5
            value: Backend.settings.presentation_surface_opacity !== undefined
                ? Math.round(Backend.settings.presentation_surface_opacity * 100) : 65
            onValueModified: Backend.setSetting("presentation_surface_opacity", value / 100)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("投影")
        description: qsTr("底板下方的柔和投影；纯色背景下关掉更清爽")
        icon.name: "ic_fluent_layer_diagonal_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_shadow_enabled === true
            onToggled: Backend.setSetting("presentation_shadow_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("组分隔线")
        description: qsTr("在动作 / 翻页 / 退出之间绘制细竖线（工具分段右侧不留）")
        icon.name: "ic_fluent_line_vertical_1_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_divider_enabled === true
            onToggled: Backend.setSetting("presentation_divider_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("页码切换")
        description: qsTr("翻页 pill：默认为屏幕左右、垂直居中的竖版（Luminalium 1 形态）；也可在配置里改用底部左右横版")
        icon.name: "ic_fluent_arrow_sort_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_pager_enabled === true
            onToggled: Backend.setSetting("presentation_pager_enabled", checked)
        }
    }

    Rin.SettingCard {
        Layout.fillWidth: true
        title: qsTr("退出键样式")
        description: qsTr("「危险红图标」是 Luminalium 1 的形态（圆形按钮 + 红色电源图标）；「普通圆钮」与其他工具栏按钮同款")
        icon.name: "ic_fluent_power_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 170
            model: [qsTr("普通圆钮"), qsTr("危险红图标（L1）")]
            currentIndex: Backend.settings.presentation_exit_style === "danger" ? 1 : 0
            onActivated: Backend.setSetting("presentation_exit_style",
                                            currentIndex === 1 ? "danger" : "default")
        }
    }
}
