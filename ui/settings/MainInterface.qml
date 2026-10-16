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
    5. 2026-10-07 用户指令：自建批注 —— 末尾新增「墨迹」组：引擎选择
       （自建批注 / COM画笔）、手掌擦除开关、手掌判定阈值。
       它们调的是**放映时谁在屏幕上画墨迹**，行为主体是主界面上那层叠加窗，
       归这一页（放映页已删，见上）。橡皮子模式的入口不在这里 —— 它在控制条
       上（橡皮已选中时再点一下橡皮，见 ``EraserModeCard.qml``）。
    6. 2026-10-08 用户指令：引擎下拉第二项改名「COM画笔」（原
       「PowerPoint·WPS 自带 (COM)」）；手掌擦除两张卡只在自建引擎下
       **显示**（``visible`` 绑 ``presentation_ink_engine``）—— COM 引擎下
       它们本来也不生效（InkLayer 不在场），留着只会让用户以为能调。
       设置页现有惯例就是裸 ``visible:`` 绑定（见 Plugins.qml / Update.qml），
       不做收起动画。
    7. 2026-10-08 用户反馈「目标显示器认不出显示器」：下拉从「跟随 /
       主显示器」两项改成「跟随 + 逐台显示器（厂商+型号，EDID）」，
       名单来自 ``Backend.monitorList``（``app/monitors.py``，做法移植自
       Luminalium 1 ``webview_runner.py::get_screen_list``）。钉屏存
       ``presentation.screen_name``（稳定 id），旧配置 ``screen_index``
       语义保留兼容。「主显示器」项折叠成主屏那台的「（主显示器）」后缀。

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
        // ⚠️ 基准是**遮罩**（2026-10-06「智能跟随」后遮罩贴着放映窗口走，见
        // ``windows.py::_position_dock`` 用 ``_overlay_rect`` 而非 ``screen.geometry()``）。
        // 别再写回「屏幕边缘」—— 窗口化放映时那是错的，全屏时才恰好等价。
        description: qsTr("控制条距放映窗口左右边缘的距离（全屏放映时即屏幕边缘）")
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
        // 同「水平边距」：基准是遮罩（= 放映窗口），不是整屏。
        description: qsTr("控制条距放映窗口上下边缘的距离（全屏放映时即屏幕边缘）")
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
        // 2026-10-08 改口：不再只有「跟随 / 主显示器」两项，逐台列出。
        description: qsTr("控制条跟着放映窗口走，或固定在某台显示器上")
        icon.name: "ic_fluent_desktop_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 240

            // 名单 = 「跟随放映窗口」+ 每台显示器（厂商+型号，来自
            // ``Backend.monitorList`` → ``app/monitors.py``，Qt 从 EDID 解出；
            // 读不到的回退「显示器 N」）。「主显示器」不单独占位 —— 折叠成
            // 主屏那台的「（主显示器）」后缀：钉主屏与选主屏那台是同一件事，
            // 两个入口只会让用户分不清（2026-10-08）。
            property var monitorEntries: Backend.monitorList

            model: {
                var items = [qsTr("跟随放映窗口")]
                for (var i = 0; i < monitorEntries.length; i++) {
                    var entry = monitorEntries[i]
                    var label = entry.label ? entry.label : qsTr("显示器 %1").arg(i + 1)
                    if (entry.primary)
                        label += qsTr("（主显示器）")
                    items.push(label)
                }
                return items
            }

            // 钉屏存的是 ``presentation.screen_name``（稳定 id）；旧配置的
            // ``screen_index >= 0``（原「主显示器」写的 0）按枚举索引映射回
            // 对应那台 —— 行为不变，只是显示成了带名字的那一项。
            currentIndex: {
                var name = Backend.settings.presentation_screen_name
                if (name) {
                    for (var i = 0; i < monitorEntries.length; i++) {
                        if (monitorEntries[i].name === name)
                            return i + 1
                    }
                    // 钉的那台被拔掉了：Python 侧回退跟随，这里也显示「跟随」
                    return 0
                }
                var index = Backend.settings.presentation_screen_index
                if (index >= 0 && index < monitorEntries.length)
                    return index + 1
                return 0
            }

            // 选具体某台时把索引复位成 -1：钉屏名称优先于索引，留着旧索引
            // 只会在显示器被拔掉时多一层没人记得的兜底。
            onActivated: {
                if (currentIndex === 0) {
                    Backend.setSetting("presentation_screen_name", "")
                    Backend.setSetting("presentation_screen_index", -1)
                } else {
                    Backend.setSetting("presentation_screen_index", -1)
                    Backend.setSetting(
                        "presentation_screen_name",
                        monitorEntries[currentIndex - 1].name
                    )
                }
            }
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
        objectName: "mainInterfaceInkEngine"

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
        objectName: "mainInterfaceInkPalmErase"

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
        objectName: "mainInterfaceInkPalmThreshold"

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
