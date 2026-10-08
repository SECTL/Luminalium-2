import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    插件管理页：列出加载清单里的全部插件，每项一个启用 / 禁用开关；
    外部导入的插件带删除按钮，页首提供两条导入入口。

    2026-10-05（插件系统 Wave 3 任务 17）新增。数据源是 ``Backend.pluginItems``
    （``app/bridge.py`` 把 ``loader.loaded_plugins()`` 的清单 + 正式 Config
    里的 ``plugins.<id>.enabled`` 合成的列表），开关写回走
    ``Backend.setPluginEnabled``（常规配置路径，防抖落盘）。

    2026-10-06（用户指令「给插件系统添加外部导入插件功能」）加外部插件
    管理：页首两张「导入插件」卡片（.zip 包 / 文件夹）分别走
    ``Backend.importPluginZip`` / ``importPluginFolder``（模态原生对话框，
    Python 侧校验 + 拷贝，见 ``app/plugins/external.py``）；结果经
    ``pluginManageResult(ok, message)`` 信号回来显示在页首横幅里。外部
    插件卡片多一枚「删除」按钮（两段式确认，避免手滑整包删掉）—— 只删
    用户插件目录里的安装副本，原始文件不动。

    ⚠️ **导入 / 删除 / 启用 / 禁用都是重启后生效，本进程内不做任何动态
    增删** —— 这不是偷懒，是两个架构前提决定的：
      ① 注册表在加载期末 ``registry.freeze()`` 冻结，之后任何 ``add_*``
         直接抛 RuntimeError，根本没有 unregister 这条路；
      ② 窗口全是懒创建、只藏不销毁 —— 插件注册的窗口一旦建出来就没有
         「销毁」这一说，实时禁用也没法把它从世界里抹掉。
    唯一语义就是「动配置 / 动安装目录 → 下次启动时 loader 按新状态装」。
    界面上对应的提示是操作后出现的内联横幅（``restartHintShown``），
    不做弹窗系统（仓库没有这个先例）。

    ⚠️ 调试插件（``_demo`` / ``_demo_dep`` 这类 ``_`` 前缀目录）**显示在
    列表里、带「调试插件」标记**，不过滤 —— 决策理由：调试插件的开关正是
    验收「禁用 → 重启 → 零贡献」链路（任务 11 的过滤机制）的唯一 UI 触点，
    过滤掉之后这条链路在界面上就没法验证了；正式环境（非 debug 启动）
    它们根本不进加载清单，普通用户看不到。

    ⚠️ 删除是**两段式确认**（先点变「确认删除」、3 秒内再点才真删）：
    删的是安装副本，导入一次不容易，手滑一次就没了不像话。确认态由
    ``armTimer`` 复位。

    页面结构（自上而下）：
      ① 导入结果横幅（导入 / 删除完成后短暂可见）；
      ② 「重启后生效」内联横幅（拨过开关 / 导入删除成功后出现）；
      ③ 两张导入入口卡片（zip 包 / 文件夹）；
      ④ 空态占位（加载清单为空时 —— 未跑加载 / 无插件）；
      ⑤ 插件卡片列表（Repeater 遍历 ``Backend.pluginItems``）：标题 =
         名称 + 版本号，副文案 = 调试 / 外部标记 + 加载结果 / 跳过原因，
         右侧外部插件删除按钮 + 启用开关。
*/
Rin.FluentPage {
    id: page

    title: qsTr("插件")
    contentSpacing: 10

    /*! 拨过任意开关 / 导入删除成功后置 true，「重启后生效」横幅据此显示。 */
    property bool restartHintShown: false
    /*! 导入 / 删除结果横幅的文案；空串隐藏（结果只在操作后看一眼）。 */
    property string resultText: ""
    /*! 本次结果是成功（true）还是失败（false），横幅配色与图标跟着换。 */
    property bool resultOk: false
    /*! 本会话里已删除的插件 id —— 加载清单是启动快照，删掉的要就地改观。 */
    property var removedIds: ({})

    /*! 卡片副文案：调试 / 外部标记 + 加载结果 / 跳过原因拼一行（「·」分隔）。 */
    function describe(item) {
        var parts = []
        if (item.debug) {
            parts.push(qsTr("调试插件"))
        }
        if (item.external) {
            parts.push(qsTr("外部导入"))
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

    Connections {
        target: Backend
        function onPluginManageResult(ok, message) {
            page.resultOk = ok
            page.resultText = message
            if (ok) {
                page.restartHintShown = true
            }
        }
    }

    // ==================================================== 导入 / 删除结果横幅
    Rin.SettingCard {
        objectName: "pluginsResultBanner"

        Layout.fillWidth: true
        visible: page.resultText !== ""
        title: page.resultOk ? qsTr("操作成功") : qsTr("操作失败")
        description: page.resultText
        icon.name: page.resultOk
                  ? "ic_fluent_checkmark_circle_20_regular"
                  : "ic_fluent_error_circle_20_regular"
    }

    // ==================================================== 重启生效提示（内联）
    Rin.SettingCard {
        objectName: "pluginsRestartHint"

        Layout.fillWidth: true
        visible: page.restartHintShown
        title: qsTr("更改将在重启应用后生效")
        description: qsTr("插件的启用状态与导入 / 删除只在启动时读取，本进程内不会动态加载或卸载")
        icon.name: "ic_fluent_arrow_sync_circle_20_regular"
    }

    // ==================================================== 导入入口
    // 两条入口分开（而不是一个按钮里做格式判断）：原生对话框「选文件夹」
    // 与「选文件」是两种交互，硬捏在一个入口里只能二选一。
    Rin.SettingCard {
        objectName: "pluginsImportZip"

        Layout.fillWidth: true
        title: qsTr("导入插件（.zip 包）")
        description: qsTr("导入即拷贝安装，重启应用后生效；插件将在本机运行，请只导入可信来源")
        icon.name: "ic_fluent_folder_zip_20_regular"

        Rin.Button {
            text: qsTr("选择 zip 包")
            onClicked: Backend.importPluginZip()
        }
    }

    Rin.SettingCard {
        objectName: "pluginsImportFolder"

        Layout.fillWidth: true
        title: qsTr("导入插件（文件夹）")
        description: qsTr("选择包含 plugin.py 的插件文件夹；导入即拷贝安装，重启应用后生效")
        icon.name: "ic_fluent_folder_open_20_regular"

        Rin.Button {
            text: qsTr("选择文件夹")
            onClicked: Backend.importPluginFolder()
        }
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
            /*! 删除的两段式确认：第一次点击进入待确认态，3 秒后自动复位。 */
            property bool removeArmed: false

            Timer {
                id: removeArmTimer
                interval: 3000
                onTriggered: pluginCard.removeArmed = false
            }

            Layout.fillWidth: true
            visible: !(pluginCard.modelData.external
                       && page.removedIds[pluginCard.modelData.id] === true)
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
                       : (modelData.external
                          ? "ic_fluent_puzzle_cube_20_regular"
                          : "ic_fluent_puzzle_piece_20_regular")

            content: [
                // 外部插件的删除按钮（两段式确认；内建与调试夹具不给删 ——
                // 它们的本体在安装目录里，删安装副本这个语义对它们无意义）。
                // 两个控件直接做卡片子件：SettingCard 的默认属性把它们排进
                // 右侧 Row，套一层 RowLayout 反而拿不到正确的宽度语义。
                Rin.Button {
                    visible: pluginCard.modelData.external === true
                    text: pluginCard.removeArmed ? qsTr("确认删除") : qsTr("删除")
                    onClicked: {
                        if (!pluginCard.removeArmed) {
                            pluginCard.removeArmed = true
                            removeArmTimer.restart()
                            return
                        }
                        removeArmTimer.stop()
                        pluginCard.removeArmed = false
                        // 必须换新对象再赋值：同一个引用原样写回去不会发
                        // 属性变更通知，卡片就地隐藏就不会生效
                        var ids = Object.assign({}, page.removedIds)
                        ids[pluginCard.modelData.id] = true
                        page.removedIds = ids
                        Backend.removePlugin(pluginCard.modelData.id)
                    }
                },

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
            ]
        }
    }
}
