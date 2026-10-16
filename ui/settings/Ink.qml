import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    墨迹和批注：放映时「谁在屏幕上画墨迹」的设定。

    2026-10-16 用户指令：「将『设置-主界面』中的『墨迹』相关选项放在新的
    设置 tab 中，命名为『墨迹和批注』」—— 本页即原 ``MainInterface.qml``
    末尾「墨迹」组整组搬来（引擎选择 / 手掌擦除 / 手掌判定阈值，三张卡
    逐字未改），独立成页。

    值的即时改道（放映中切换引擎也生效）在 ``application._on_config_changed``，
    这里只负责读写配置。橡皮子模式（整笔 / 像素）的入口**刻意不放这里** ——
    它是「画的时候随手切」的档，入口在控制条橡皮卡片上
    （``ui/presentation/EraserModeCard.qml``）。

    导航项在 ``app/bridge.py::_BUILTIN_SETTINGS_NAV``（数据源，QML 不写死）。
*/
Rin.FluentPage {
    id: page

    title: qsTr("墨迹和批注")
    contentSpacing: 10

    // ------------------------------------------------------------------ 墨迹
    //
    // 2026-10-07 用户指令：自建批注（计划 self-ink 第 9 项）。这一组管
    // 「放映时谁在屏幕上画墨迹」：引擎选择（默认自建）、触摸屏手掌擦除。
    // 值变了由 ``application._on_config_changed`` 即时改道（放映中切换
    // 也生效），这里只负责读写配置。橡皮子模式（整笔 / 像素）的入口刻意
    // 不放这里 —— 它是「画的时候随手切」的档，入口在控制条橡皮卡片上。
    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("墨迹")
    }

    Rin.SettingCard {
        objectName: "inkEngine"

        Layout.fillWidth: true
        title: qsTr("墨迹引擎")
        description: qsTr("自建批注在放映画面上自己画，两家一致；COM 交给演示软件（兜底）")
        icon.name: "ic_fluent_pen_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 210
            // 2026-10-08 用户指令：第二项改名「COM画笔」（原「PowerPoint·WPS 自带 (COM)」）。
            model: [qsTr("自建批注"), qsTr("COM画笔")]
            // 未知值按自建显示（与 ``application._ink_engine()`` 的兜底一致）。
            currentIndex: Backend.settings.presentation_ink_engine === "com" ? 1 : 0
            onActivated: Backend.setSetting(
                "presentation_ink_engine", currentIndex === 1 ? "com" : "self")
        }
    }

    Rin.SettingCard {
        objectName: "inkPalmErase"

        Layout.fillWidth: true
        // 2026-10-08 用户指令：仅自建引擎下显示（COM 画笔时 InkLayer 不在场，
        // 这两项无的放矢）。``Backend.settings`` 是响应式的，切引擎立即收起。
        visible: Backend.settings.presentation_ink_engine !== "com"
        title: qsTr("手掌擦除")
        description: qsTr("触摸屏上手掌或手背压上去时临时切成像素擦除，抬起即还原；"
                          + "仅在使用自建批注时生效")
        icon.name: "ic_fluent_hand_left_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            // 默认 true（缺键 / 被改成 false 之外的值都按开处理，
            // 与 default_config.json 的 palm_erase 注释一致）。
            checked: Backend.settings.presentation_ink_palm_erase !== false
            onToggled: Backend.setSetting("presentation_ink_palm_erase", checked)
        }
    }

    Rin.SettingCard {
        objectName: "inkPalmThreshold"

        Layout.fillWidth: true
        // 与「手掌擦除」卡同一条显隐规则（2026-10-08 用户指令），理由见上。
        visible: Backend.settings.presentation_ink_engine !== "com"
        title: qsTr("手掌判定阈值")
        description: qsTr("接触直径达到该值才算手掌；指尖约 8~12 毫米，掌心 25 毫米以上")
        icon.name: "ic_fluent_resize_20_regular"

        // 档位 10~60mm（default_config.json 的 palm_threshold_mm 注释定档）。
        SettingSlider {
            primaryColor: Lumi.accent
            from: 10
            to: 60
            stepSize: 1
            suffix: " mm"
            value: Backend.settings.presentation_ink_palm_threshold_mm !== undefined
                ? Backend.settings.presentation_ink_palm_threshold_mm : 20
            onMoved: Backend.setSetting("presentation_ink_palm_threshold_mm", Math.round(value))
        }
    }
}
