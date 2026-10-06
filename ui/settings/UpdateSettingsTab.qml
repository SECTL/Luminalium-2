import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    设置 → 更新 → 「更新设置」Tab 的内容（由 ``Update.qml`` 用 ``Loader``
    按需加载，见那边同名注释）。

    ⚠️ **为什么单独拆文件、而不是在 ``Update.qml`` 里靠 ``visible`` 切两段**：
    RinUI ``SettingItem`` 内部左栏的可见性是一个绑定
    （``visible: titleLabel.visible || descriptionLabel.visible``，而这两个又
    取决于 ``title.length > 0``）。整段一开始是 ``visible: false`` 时，
    构造期求值拿到的是空串 → 左栏被判定为「无内容」而整层隐藏；之后 Tab 切
    过来、``visible`` 翻 true，**这一层的可见性不会重新求值**，于是
    标题 / 描述都传对了、也有高度，却一个字都不画（实测：
    ``updateForceCheckItem`` 的 title='强制检查更新'、height=50，而内部
    ``RowLayout.visible == false``）。

    改成 ``Loader``（``active`` 跟着 Tab 索引）之后，这些控件是**选中那一刻
    才构造**的，构造期 ``title`` / ``description`` 已经是最终值，绑定一次性
    求对。顺带的好处：没点开的 Tab 不进渲染循环。

    组件本身是 ``Update.qml`` 的上下文依赖（要读 ``page.*`` 与
    ``Backend.settings``），所以作为内联组件不合适 —— 独立文件 + 一组
    显式属性传入，耦合点集中在下面几行。
*/
Item {
    id: root

    /*! ⚠️ 高度自撑：``implicitHeight`` 取内容，子 ``ColumnLayout`` **只锚左右**。
        别写 ``anchors.fill: parent`` —— 那会让 layout 的高度也绑回 ``root.height``，
        而 ``root.height`` 又来自 ``implicitHeight``，成环。在 ``Update.qml`` 的
        ``Loader`` 里碰巧解得对，但**独立加载时环会解出另一个值**：实测把
        ``UpdateSettingsTab.qml`` 单独塞进宿主，第一张卡片被撑到 387px（真身 72），
        两张卡片之间凭空多出 320px 空档。锚左右就够（宽度要跟着父级走），
        高度交给内容算，任何父级下都稳。 */
    implicitHeight: layout.implicitHeight
    /*! 通道候选表：直接读 ``Backend.updateChannels``（= Python 侧
        ``update_checker.CHANNELS`` / ``CHANNEL_NAMES`` 派生，**唯一一份**）。

        ⚠️ 刻意**不**由页面用 ``Loader.setProperty`` 推过来（2026-10-05 实测）：
        QML 的 ``var`` 属性期望 ``QJSValue``，把 JS ``Array`` 直接塞进去会被
        包成**空 QJSValue**，子项遍历 ``.length`` 得 0 → 通道下拉空、说明行
        标题与描述双空。由 Python 发 ``QVariantList`` 则拿到的就是原生数组。 */
    readonly property var channels: Backend.updateChannels

    /*! 当前通道 id。**自己读** ``Backend.settings``，不由页面推 ——
        页面侧那个「遍历候选表求选中项」的计算属性在 ``Loader.onLoaded``
        触发时还没算出来，推过去是空串。 */
    readonly property string currentChannelId: {
        var raw = Backend.settings.update_channel
        for (var i = 0; i < channels.length; ++i) {
            if (channels[i].id === raw) {
                return raw
            }
        }
        return channels.length > 0 ? channels[0].id : "stable"
    }

    /*! 通道名 / 说明：由 ``currentChannelId`` 在 ``channels`` 里现查。
        同样绕开「推过来的时候还是空」的问题。 */
    readonly property var currentChannel: {
        for (var i = 0; i < channels.length; ++i) {
            if (channels[i].id === currentChannelId) {
                return channels[i]
            }
        }
        return channels.length > 0 ? channels[0] : null
    }

    ColumnLayout {
        id: layout

        anchors {
            left: parent.left
            right: parent.right
        }
        spacing: 6

        /*! 更新模式（ClassIsland 的 ``Settings.UpdateMode``：0 从不 /
            1 检查并通知 / 2 检查并下载 / 3 检查并安装）。2 / 3 在部署接入
            之前与 1 等效（见 ``Backend.autoCheckUpdates``）。 */
        Rin.SettingExpander {
            objectName: "updateModeExpander"
            Layout.fillWidth: true

            icon.name: "ic_fluent_arrow_download_20_regular"
            title: qsTr("更新模式")
            description: qsTr("设置应用的更新模式。")

            content: Rin.ComboBox {
                Layout.preferredWidth: 190
                model: [
                    qsTr("从不自动更新"),
                    qsTr("自动检查更新并通知"),
                    qsTr("自动检查更新并下载"),
                    qsTr("自动检查更新并安装")
                ]
                currentIndex: Backend.settings.update_mode === undefined
                    ? 1 : Backend.settings.update_mode
                onActivated: Backend.setSetting("update_mode", currentIndex)
            }
        }

        /*! 更新通道（ClassIsland 的 ``SelectedUpdateChannelV3`` + 通道说明 +
            「强制检查更新」）。默认展开（原版 ``IsExpanded="True"``）。
            ⚠️ 通道语义 = 本项目对 GitHub Releases 的取用方式：
            **stable 只接受 Release，preview 接受 Prerelease + Release**
            （实现见 ``app/update_checker.py::_release_matches_channel``）。 */
        Rin.SettingExpander {
            objectName: "updateChannelExpander"
            Layout.fillWidth: true
            expanded: true

            icon.name: "ic_fluent_globe_20_regular"
            title: qsTr("更新通道")
            description: qsTr("控制应用的更新目标版本。版本的发行节奏和稳定程度"
                              + "因更新通道而异，部分通道可能包含不稳定的功能，"
                              + "请谨慎使用。")

            content: Rin.ComboBox {
                Layout.preferredWidth: 150
                model: root.channels
                textRole: "name"
                currentIndex: {
                    for (var i = 0; i < root.channels.length; ++i) {
                        if (root.channels[i].id === root.currentChannelId) {
                            return i
                        }
                    }
                    return 0
                }
                onActivated: Backend.setSetting(
                    "update_channel", root.channels[currentIndex].id)
            }

            /*! 通道说明行（ClassIsland 的 ``SettingsExpanderItem`` 里只有**一个
                ``TextBlock``**，绑 ``SelectedChannel.Description``、``TextWrapping=Wrap``
                —— 没有标题、也没有通道名。本项目一度多写一行「稳定版」当标题，
                与原型对不上，2026-10-05 按原版删掉，只留描述。

                ⚠️ 文案放 ``title`` 而不是 ``description``：RinUI ``SettingItem``
                的 ``title`` 走 ``Typography.Body``（正文号），``description`` 走
                ``Caption``（小一号 + 次要色）。原版那个 TextBlock 是**正文号、
                正色**，所以对应的是 ``title`` 这一档 —— 放 ``description`` 会
                小一号且发灰。 */
            Rin.SettingItem {
                objectName: "updateChannelDescItem"
                title: root.currentChannel !== null
                    ? root.currentChannel.description : ""
            }

            /*! 强制检查更新（``CheckUpdateAsync(isForce: true)``）：即使远端
                版本不比当前新也按「有更新」处理。 */
            Rin.SettingItem {
                objectName: "updateForceCheckItem"
                title: qsTr("强制检查更新")
                description: qsTr("强制将应用更新到当前通道上的最新版本，"
                                  + "即使此版本比应用当前版本更旧。")
                actionIcon.name: "ic_fluent_arrow_sync_20_regular"
                clickable: true

                onClicked: Backend.requestCheckUpdate(true)
            }
        }
    }
}
