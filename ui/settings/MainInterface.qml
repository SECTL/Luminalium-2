import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    主界面：主界面本身的设定。目前只有一张**推广卡**「编辑主界面的新方式」。

    2026-10-01 用户指令两轮：

    1. 「把『外观』改成『主界面』」—— 导航项由「外观」改名而来，原页面里的
       **主题模式 / 强调色 / 界面语言**三张卡整体挪去了「通用」页（那三项是
       全局外观设定，不属于「主界面」这个概念）。
    2. 「主界面设置加一个卡片 类似 Class Widgets 2 的『编辑组件的新方式』，
       这里改为『编辑主界面的新方式』」—— 即下面这张 ``Rin.Frame``。
    3. 「将 水平/垂直边距 目标显示器 背景不透明度 移到主界面设置 …… 阴影开关
       也移到主界面设置」—— 即下面「位置 / 外观」两组。它们调的都是**主界面
       （放映时那块全屏画布上的控制条）长什么样**，归这一页；放映页只剩下行为项。
    4. 2026-10-05「主界面设置新增缩放大小滑块 用于调整顶层窗口中组件的大小」
       —— 即下面「缩放」组的「缩放大小」卡：整块等比放大 / 缩小控制条组件
       （配置键 ``presentation.scale``，落在 ``PresentationDock`` / ``SidePager``
       的 ``scaleFactor`` 上）。

    主界面的**可视化编辑**走独立窗口 ``ui/MainInterfaceEditor.qml``
    （入口之一就是这张卡上的按钮），单个按钮的样式（如退出键样式）在那边的
    右侧设置面板里。⚠️ 本文件原名 ``Appearance.qml``：改名是安全的，设置页路径
    只被 ``Settings.qml`` 的 ``navigationItems`` 与 ``default_config.json`` 里的
    ``shortcut_catalog`` 动作引用，两处都在仓库内、已同批更新；用户配置只存
    「启用了哪些快捷方式 id」，不存页面路径。
*/
Rin.FluentPage {
    id: page

    title: qsTr("主界面")
    contentSpacing: 10

    /*! 「编辑主界面的新方式」—— 版式照搬 Class Widgets 2 的推广卡
        （``ClassWidgets/Components/Introduction.qml``，用例在
        ``pages/settings/General/Widgets.qml``）：左边一张示意图、右边
        **标题 + 说明 + 一个右对齐的 ``flat + highlighted`` 按钮**。

        ⚠️ 配图是**两个文件**（``resources/new_editor_maininterface_{light,dark}.png``），
        按 ``Lumi.isDark`` 二选一 —— RinUI 没有「同一 Image 按主题换源」的机制；
        也别用 ColorOverlay 把浅色图染成暗色（示意图里自带投影与灰阶层次，
        染色会一并糊掉）。用户已经把两张图放进 ``resources/``。
    */
    Rin.Frame {
        id: editorIntro

        objectName: "mainInterfaceEditorIntro"
        Layout.fillWidth: true
        // Frame 的 contentItem 没有隐式高度（背景是 Rectangle），高度得自己算：
        // 图的最大高度 + 上下内边距。
        Layout.preferredHeight: Lumi.editorIntroImageHeight + editorIntro.padding * 2
        // 推广卡不跟着鼠标变底色（Frame 默认 hoverable 会把整张卡提亮一档）
        hoverable: false
        padding: Lumi.editorIntroPadding

        RowLayout {
            anchors.fill: parent
            spacing: Lumi.editorIntroSpacing

            Image {
                objectName: "mainInterfaceEditorIntroImage"
                Layout.alignment: Qt.AlignCenter
                Layout.maximumWidth: Lumi.editorIntroImageWidth
                Layout.maximumHeight: Lumi.editorIntroImageHeight
                Layout.preferredWidth: Lumi.editorIntroImageWidth
                Layout.preferredHeight: Lumi.editorIntroImageHeight
                fillMode: Image.PreserveAspectFit
                // sourceSize 只声明**逻辑**尺寸：原图 321×225，高 DPI 下按需取更细的
                // mip 层，不会糊（smooth/mipmap 才是真正的插值开关）。
                sourceSize: Qt.size(Lumi.editorIntroImageWidth, Lumi.editorIntroImageHeight)
                source: Backend.resourceFile(
                    Lumi.isDark ? "new_editor_maininterface_dark.png"
                                : "new_editor_maininterface_light.png")
                smooth: true
                mipmap: true
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 12

                Rin.Text {
                    objectName: "mainInterfaceEditorIntroTitle"
                    Layout.fillWidth: true
                    typography: Rin.Typography.BodyLarge
                    text: qsTr("编辑主界面的新方式")
                }

                Rin.Text {
                    Layout.fillWidth: true
                    text: qsTr("右键托盘图标或唤出快捷面板，点「主界面编辑器」即可体验：\n"
                               + "点击任意组件聚焦放大，右侧面板里调整它的设置。")
                }

                Rin.Button {
                    objectName: "mainInterfaceEditorIntroButton"
                    Layout.alignment: Qt.AlignRight
                    flat: true
                    highlighted: true
                    icon.name: "ic_fluent_arrow_right_20_regular"
                    text: qsTr("打开主界面编辑器")
                    onClicked: Backend.openMainEditor()
                }
            }
        }
    }

    // ------------------------------------------------------------------ 缩放
    //
    // 2026-10-05 用户指令：「主界面设置新增缩放大小滑块 用于调整顶层窗口中组件的
    // 大小」—— 顶层窗口 = 主界面（放映时那块全屏叠加层），组件 = 上面的控制条
    // （工具栏 / 翻页 pill）。整块等比缩放：投影、渐变高光、图标、页码文字一起变。
    //
    // 配置里存的是 **0.5~2.0 的小数**（``presentation.scale``），滑块按整数百分比
    // 走（写回时再除 100）—— 与「底板不透明度」同一套约定。
    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("缩放")
    }

    Rin.SettingCard {
        objectName: "mainInterfaceScale"

        Layout.fillWidth: true
        title: qsTr("缩放大小")
        description: qsTr("整体放大或缩小控制条上的组件；位置与边距不受影响")
        icon.name: "ic_fluent_zoom_in_20_regular"

        SettingSlider {
            primaryColor: Lumi.accent
            from: 50
            to: 200
            stepSize: 5
            suffix: " %"
            value: Backend.settings.presentation_scale !== undefined
                ? Math.round(Backend.settings.presentation_scale * 100) : 100
            onMoved: Backend.setSetting("presentation_scale", value / 100)
        }
    }

    // ------------------------------------------------------------------ 位置
    //
    // 2026-10-01 从「放映」页整组搬来（用户指令）。摆位公式在
    // ``windows.py::_position_dock``，QML 编辑器里还有一份副本
    // （``MainInterfaceEditor``），两边都按这一组值算。
    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("位置")
    }

    Rin.SettingCard {
        objectName: "mainInterfaceMarginX"

        Layout.fillWidth: true
        title: qsTr("水平边距")
        description: qsTr("控制条距屏幕左右边缘的距离")
        icon.name: "ic_fluent_arrow_bidirectional_left_right_20_regular"

        // 默认 20 = Luminalium 1 的贴边内边距（``presentation.margin_x``）。
        // 滑块宽度按 0~200 分档，20 大约落在左边 10% 处 —— 想贴死就拖到 0。
        SettingSlider {
            primaryColor: Lumi.accent
            from: 0
            to: 200
            stepSize: 1
            suffix: " px"
            value: Backend.settings.presentation_margin_x !== undefined
                ? Backend.settings.presentation_margin_x : 20
            onMoved: Backend.setSetting("presentation_margin_x", Math.round(value))
        }
    }

    Rin.SettingCard {
        objectName: "mainInterfaceMarginY"

        Layout.fillWidth: true
        title: qsTr("垂直边距")
        description: qsTr("控制条距屏幕上下边缘的距离，以整屏边缘为准")
        icon.name: "ic_fluent_arrow_bidirectional_up_down_20_regular"

        SettingSlider {
            primaryColor: Lumi.accent
            from: 0
            to: 200
            stepSize: 1
            suffix: " px"
            value: Backend.settings.presentation_margin_y !== undefined
                ? Backend.settings.presentation_margin_y : 20
            onMoved: Backend.setSetting("presentation_margin_y", Math.round(value))
        }
    }

    Rin.SettingCard {
        objectName: "mainInterfaceScreenIndex"

        Layout.fillWidth: true
        title: qsTr("目标显示器")
        description: qsTr("控制条跟着放映窗口走，还是固定在主显示器上")
        icon.name: "ic_fluent_desktop_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: [qsTr("跟随放映窗口"), qsTr("主显示器")]
            currentIndex: Backend.settings.presentation_screen_index === -1 ? 0 : 1
            onActivated: Backend.setSetting("presentation_screen_index", currentIndex === 0 ? -1 : 0)
        }
    }

    // ------------------------------------------------------------------ 外观
    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("外观")
    }

    Rin.SettingCard {
        objectName: "mainInterfaceSurfaceOpacity"

        Layout.fillWidth: true
        title: qsTr("底板不透明度")
        description: qsTr("越透明，放映画面透出来越多，边缘高光也越明显")
        icon.name: "ic_fluent_blur_20_regular"

        // 配置里存的是 0~1 的小数，滑块按整数百分比走（写回时再除 100）。
        SettingSlider {
            primaryColor: Lumi.accent
            from: 20
            to: 100
            stepSize: 5
            suffix: " %"
            value: Backend.settings.presentation_surface_opacity !== undefined
                ? Math.round(Backend.settings.presentation_surface_opacity * 100) : 65
            onMoved: Backend.setSetting("presentation_surface_opacity", value / 100)
        }
    }

    Rin.SettingCard {
        objectName: "mainInterfaceShadowEnabled"

        Layout.fillWidth: true
        title: qsTr("阴影")
        description: qsTr("底板下方的柔和投影；纯色背景下关掉更清爽")
        icon.name: "ic_fluent_layer_diagonal_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.presentation_shadow_enabled === true
            onToggled: Backend.setSetting("presentation_shadow_enabled", checked)
        }
    }
}
