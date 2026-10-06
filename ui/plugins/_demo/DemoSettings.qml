import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    插件系统验收夹具 ``_demo`` 的设置页（2026-10-05 插件系统计划 Wave 3 任务 12）。

    ⚠️ 本页与整个 ``_demo`` 插件组是**框架验收夹具**，禁止在此实现任何真实
    功能；内容刻意占位级（一张卡一个开关），只为验证「插件设置页进导航 +
    插件扁平设置键读写」这条链路。

    开关绑 ``Backend.settings.plugins__demo_flag``（键由
    ``app/plugins/_demo/plugin.py`` 的 ``register_setting`` 登记）。
    ``onToggled`` 里用 ``Qt.binding`` 重装 ``checked`` 绑定：控件内部改属性
    会摘掉 QML 绑定，不重装则外部改值开关不跟 —— 历史坑，同款注释见
    ``ui/settings/General/Index.qml`` 的开机自启开关。
*/
Rin.FluentPage {
    id: page

    title: qsTr("演示插件")
    contentSpacing: 10

    Rin.SettingCard {
        objectName: "demoFlagCard"

        Layout.fillWidth: true
        title: qsTr("演示开关")
        description: qsTr("验收夹具占位：只验证插件设置键的读写链路，无实际功能")
        icon.name: "ic_fluent_beaker_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.plugins__demo_flag === true
            onToggled: {
                Backend.setSetting("plugins__demo_flag", checked)
                // 重装绑定（理由见文件头注释）；幂等，写成功时照装不误。
                checked = Qt.binding(function () {
                    return Backend.settings.plugins__demo_flag === true
                })
            }
        }
    }
}
