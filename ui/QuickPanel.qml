import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium
import "QuickPanel"
/*!
    快捷面板（托盘浮窗）。

    结构与交互逐条对齐 **Class Widgets 2** 的 ``Windows/TrayPanel.qml``：

    * **保留 RinUI 的自绘窗口边框**：标题栏 + 关闭按钮照常显示，只藏
      最小化 / 最大化；标题栏文本是版本号（CW2 同款）。关闭按钮由
      ``app/windows.py`` 拦截成「隐藏」。
    * 内容区是一张卡片：``layerColor`` 底 + ``cardBorderColor`` 描边，
      宽度 ``parent.width + 8``（补回窗口拖拽边距，正好贴满窗口）、
      高度留出底部工具条的位置。
    * 头部：logo + 应用名（Luminalium 没有更新摘要功能，不做该按钮）；
    * 快捷方式：``TrayShortcuts``（3 列网格 + 编辑态 + 空状态）；
    * 底栏：**卡片外**、窗口右下角一排扁平图标按钮 + ToolTip；
    * 点托盘图标时由 Python 侧按**光标位置**摆放（``pos.x - w/2``，
      ``pos.y + 30``，下方放不下就翻到上方，夹取到屏幕内），然后
      ``raise() + requestActivate()``。

    2026-10-01 移除了「放映状态」区块（``StatusCard``）—— 用户指令
    「删除快捷面板的放映状态相关代码」；放映状态另有展示位置（控制条本身
    就在放映画面上），面板里再放一张卡片属于重复。

    内容（区块开关 / 底栏动作 / 快捷方式清单）由
    ``config/default_config.json`` 的 ``quick_panel`` 段驱动；**尺寸与位置
    不再读配置**（见下方 ``panelWidth`` / ``panelHeight``）。
*/
Rin.Window {
    id: panel

    readonly property var cfg: Backend.quickPanelConfig
    readonly property var sectionsCfg: cfg.sections !== undefined ? cfg.sections : ({})
    readonly property var footerCfg: cfg.footer !== undefined ? cfg.footer : ({})
    readonly property var footerActions: footerCfg.actions !== undefined ? footerCfg.actions : []

    /*! 面板尺寸**写死**，不再读配置。

        2026-10-01 用户指令：删掉「尺寸与位置」的设置**包括行为的代码** ——
        ``quick_panel.width`` / ``height`` 已从 ``default_config.json`` 与
        ``bridge.SETTING_PATHS`` 一并移除，尺寸不再随配置变化，这里就是唯一
        来源（375 宽，与 CW2 的托盘面板同宽；440 高给网格留三行 + 底栏）。
        面板弹出位置同样不再可配（``windows.py::_position_panel`` 用常量
        偏移），但**光标锚定行为本身保留** —— 那是托盘面板的基本交互。 */
    readonly property int panelWidth: 375
    readonly property int panelHeight: 440

    title: Backend.appVersion
    minimizeVisible: false
    maximizeVisible: false

    visible: false
    width: panelWidth
    height: panelHeight
    minimumWidth: panelWidth
    maximumWidth: panelWidth
    minimumHeight: panelHeight
    maximumHeight: panelHeight

    // 关闭按钮 = 隐藏（托盘常驻应用不销毁窗口）。
    // 必须在 QML 侧拦：Python 槽接 ``closing(QQuickCloseEvent*)`` 会因
    // 类型无法转换而抛 TypeError，直接把应用打死。
    onClosing: function (event) {
        event.accepted = false
        Backend.hidePanel()
    }

    // ================================================== 内容卡片（CW2 同款）
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width + 8
        height: parent.height - bottomRow.height - 10
        color: Lumi.panelCardBg
        border.color: Lumi.panelCardBorder
        border.width: 1
    }

    ColumnLayout {
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            bottom: bottomRow.top
        }
        anchors.margins: Lumi.panelPadding
        anchors.bottomMargin: Lumi.panelBottomPadding
        spacing: Lumi.panelSectionSpacing

        // ======================================================== 头部
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 4
            Layout.preferredHeight: Lumi.panelLogoSize
            spacing: 8

            // 品牌标记：直接取 resources/logo.svg（矢量，任意尺寸都清晰）。
            // 资源缺失时（Image 加载失败会显示空白）回落到手绘渐变方块。
            Image {
                Layout.preferredWidth: Lumi.panelLogoSize
                Layout.preferredHeight: Lumi.panelLogoSize
                source: Backend.resourceFile("logo.svg")
                sourceSize: Qt.size(Lumi.panelLogoSize, Lumi.panelLogoSize)
                asynchronous: true
                fillMode: Image.PreserveAspectFit
            }

            Rin.Text {
                Layout.fillWidth: true
                typography: Rin.Typography.BodyLarge
                elide: Text.ElideRight
                text: Backend.appName
            }
        }

        // ================================================ 快捷方式
        TrayShortcuts {
            id: shortcuts
            visible: sectionsCfg.shortcuts !== false
            locked: cfg.shortcuts_locked === true
            Layout.fillWidth: true
            Layout.fillHeight: true
            onShortcutTriggered: Backend.hidePanel()
            onAddRequested: addOverlay.open()
        }

    }

    // ============================================================ 底栏
    // CW2：卡片**外**、窗口右下角一排扁平图标按钮（margins 4）。
    Row {
        id: bottomRow
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 4
        spacing: 0
        visible: sectionsCfg.footer !== false

        Repeater {
            model: panel.footerActions

            delegate: IconButton {
                iconName: modelData.icon !== undefined ? modelData.icon : ""
                tooltip: modelData.tooltip !== undefined ? modelData.tooltip : ""
                onClicked: {
                    const actionId = modelData.id
                    if (actionId === "reload") {
                        Backend.requestReload()
                    } else if (actionId === "exit") {
                        Backend.requestQuit()
                    } else {
                        Backend.triggerAction(actionId)
                    }
                    Backend.hidePanel()
                }
            }
        }
    }

    // ============================================================ 开发水印
    // 左下角（底栏按钮在右下角，正好不冲突）；纯文字不吃点击。
    DevWatermark {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10
        anchors.bottomMargin: 8
        z: 800
    }

    // ================================================== 添加快捷方式（覆盖层）
    // CW2 用小 ``Dialog``；本版本 RinUI 的 ``Dialog`` 依赖
    // ``QQC2.Overlay.overlay``（只有 ApplicationWindow 才有），而托盘浮窗是普通
    // ``Window``，直接用会拿到 null。所以改用面板内的覆盖层，视觉等价且更稳。
    Item {
        id: addOverlay
        anchors.fill: parent
        z: 900
        visible: opacity > 0
        opacity: 0

        function open() {
            opacity = 1
        }
        function close() {
            opacity = 0
        }

        Behavior on opacity {
            NumberAnimation {
                duration: Lumi.durationFast
                easing.type: Easing.OutQuad
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Lumi.fade(Lumi.panelCardBg, 0.75)
        }

        Rin.Frame {
            anchors.fill: parent
            anchors.margins: Lumi.panelPadding
            radius: Lumi.flyoutRadius
            hoverable: false

            ColumnLayout {
                anchors.fill: parent
                spacing: Lumi.panelSectionSpacing

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32

                    Rin.Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        typography: Rin.Typography.BodyStrong
                        text: qsTr("添加快捷方式")
                    }

                    IconButton {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        iconName: "ic_fluent_dismiss_20_regular"
                        tooltip: qsTr("关闭")
                        onClicked: addOverlay.close()
                    }
                }

                EmptyState {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: Backend.availableShortcutItems.length === 0
                    iconName: "ic_fluent_checkmark_circle_20_regular"
                    title: qsTr("都加上了")
                    description: qsTr("所有可用的快捷方式都已经在面板里。")
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: Backend.availableShortcutItems.length > 0
                    clip: true
                    spacing: 4
                    model: Backend.availableShortcutItems

                    delegate: Rin.SettingCard {
                        title: modelData.title !== undefined ? modelData.title : ""
                        clickable: true
                        icon.name: modelData.icon !== undefined ? modelData.icon : ""
                        onClicked: Backend.setShortcutEnabled(modelData.id, true)

                        IconButton {
                            iconName: "ic_fluent_add_20_regular"
                            tooltip: qsTr("添加")
                            onClicked: Backend.setShortcutEnabled(modelData.id, true)
                        }
                    }
                }
            }
        }
    }
}
