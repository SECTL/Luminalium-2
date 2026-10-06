import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    插件管理页：列出加载清单里的全部插件，每项一个启用 / 禁用开关。

    2026-10-05（插件系统 Wave 3 任务 17）新增。数据源是 ``Backend.pluginItems``
    （``app/bridge.py`` 把 ``loader.loaded_plugins()`` 的清单 + 正式 Config
    里的 ``plugins.<id>.enabled`` 合成的列表），开关写回走
    ``Backend.setPluginEnabled``（常规配置路径，防抖落盘）。

    ⚠️ **启用 / 禁用重启后生效，本进程内不做任何动态增删** —— 这不是偷懒，
    是两个架构前提决定的：
      ① 注册表在加载期末 ``registry.freeze()`` 冻结，之后任何 ``add_*``
         直接抛 RuntimeError，根本没有 unregister 这条路；
      ② 窗口全是懒创建、只藏不销毁 —— 插件注册的窗口一旦建出来就没有
         「销毁」这一说，实时禁用也没法把它从世界里抹掉。
    实时反注册跟这两条都打架，所以唯一语义就是「写配置 → 下次启动时
    loader 按新 enabled 过滤」。界面上对应的提示是拨过开关后出现的
    内联横幅（``restartHint``），不做弹窗系统（仓库没有这个先例）。

    ⚠️ 调试插件（``_demo`` / ``_demo_dep`` 这类 ``_`` 前缀目录）**显示在
    列表里、带「调试插件」标记**，不过滤 —— 决策理由：调试插件的开关正是
    验收「禁用 → 重启 → 零贡献」链路（任务 11 的过滤机制）的唯一 UI 触点，
    过滤掉之后这条链路在界面上就没法验证了；正式环境（非 debug 启动）
    它们根本不进加载清单，普通用户看不到。

    页面结构（自上而下）：
      ① 「重启后生效」内联横幅（拨过任意开关才出现）；
      ② 空态占位（加载清单为空时 —— 未跑加载 / 无插件，普通用户常态）；
      ③ 插件卡片列表（Repeater 遍历 ``Backend.pluginItems``）：标题 =
         名称 + 版本号，副文案 = 调试标记 / 加载结果 / 跳过原因，右侧开关。
*/
Rin.FluentPage {
    id: page

    title: qsTr("插件")
    contentSpacing: 10

    /*! 拨过任意开关后置 true，「重启后生效」横幅据此显示。 */
    property bool restartHintShown: false

    /*! 卡片副文案：调试标记 / 加载结果 / 跳过原因拼一行（「·」分隔）。 */
    function describe(item) {
        var parts = []
        if (item.debug) {
            parts.push(qsTr("调试插件"))
        }
        if (item.loaded) {
            parts.push(qsTr("已加载"))
        } else if (item.reason) {
            parts.push(qsTr("未加载：%1").arg(item.reason))
        } else {
            parts.push(qsTr("未加载"))
        }
        if (!item.enabled) {
            parts.push(qsTr("已禁用"))
        }
        return parts.join(" · ")
    }

    // ==================================================== 重启生效提示（内联）
    Rin.SettingCard {
        objectName: "pluginsRestartHint"

        Layout.fillWidth: true
        visible: page.restartHintShown
        title: qsTr("更改将在重启应用后生效")
        description: qsTr("插件的启用状态只在启动时读取，本进程内不会动态加载或卸载")
        icon.name: "ic_fluent_arrow_sync_circle_20_regular"
    }

    // ==================================================== 空态占位
    // 加载清单为空（未跑加载 / 无插件）时整个列表区换成一段占位文案，
    // 不能让页面只剩一个标题。
    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: emptyState.implicitHeight + 48
        visible: Backend.pluginItems.length === 0

        ColumnLayout {
            id: emptyState
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            Rin.Icon {
                Layout.alignment: Qt.AlignHCenter
                icon: "ic_fluent_puzzle_piece_20_regular"
                size: 40
                color: Lumi.textSecondary
            }
            Rin.Text {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("没有已安装的插件")
                color: Lumi.textSecondary
            }
        }
    }

    // ==================================================== 插件卡片列表
    Repeater {
        model: Backend.pluginItems

        delegate: Rin.SettingCard {
            id: pluginCard

            required property var modelData

            Layout.fillWidth: true
            title: {
                var text = modelData.title || modelData.id
                if (modelData.version) {
                    text += "  v" + modelData.version
                }
                return text
            }
            description: page.describe(modelData)
            icon.name: modelData.debug
                       ? "ic_fluent_beaker_20_regular"
                       : "ic_fluent_puzzle_piece_20_regular"

            Rin.Switch {
                primaryColor: Lumi.accent
                checked: pluginCard.modelData.enabled === true
                onToggled: {
                    Backend.setPluginEnabled(pluginCard.modelData.id, checked)
                    page.restartHintShown = true
                    // ⚠️ 点击已经把 ``checked`` 上的绑定打断了（C++ 侧
                    // ``setChecked`` 会摘掉 QML 绑定，与「通用」页开机自启
                    // 开关是同一个坑）。虽然 ``pluginItemsChanged`` 会让
                    // Repeater 重建代理、绑定自然刷新，但「值没变 → 不重建」
                    // 的边角下开关会停在用户点的那一格；重装是幂等的。
                    checked = Qt.binding(function () {
                        return pluginCard.modelData.enabled === true
                    })
                }
            }
        }
    }
}
