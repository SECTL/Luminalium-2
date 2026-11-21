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

    2026-11-21 用户指令（同一天三轮，最后的形态是第三轮定的）：
    ①「『墨迹和批注』设置新增一个色板颜色，用于更改全局色板场景的颜色列表」；
    ②「为什么不把它做成一个 Dialog，左边是颜色板，右侧是功能选项，用 RinUI 的
       分割线分割」；
    ③「在设置里直接显示为一个 card，用按钮加入口，其余一切均在一个 dialog 内
       完成，颜色要加名称而非『第 xx 个颜色』」。
    所以本页对色板只留**一张卡 + 一个按钮**（见 ``inkPalette``），色板网格、
    取色器、添加 / 删除、颜色名全在 ``paletteDialog`` 里。放映笔选单与小黑板
    粉笔读的是同一份 ``presentation.pen.palette``，这里就是这份**全局色板**的
    唯一编辑入口。它不是「墨迹引擎」的子项（两种引擎下都生效，com 引擎也拿它
    去设 PointerColor），所以不跟手掌那两张卡一起藏。

    导航项在 ``app/bridge.py::_BUILTIN_SETTINGS_NAV``（数据源，QML 不写死）。
*/
Rin.FluentPage {
    id: page
    objectName: "inkPage"

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


    // ------------------------------------------------------------------ 色板
    //
    // 只留一张卡 + 一个按钮；改色在 paletteDialog 里做（左边色板 / 中间
    // Rin.ToolSeparator 竖线 / 右边功能选项）。前两版试过「卡片里摊开 30 个
    // 色块」和「卡片里就地展开取色器」，前者让设置页被一行色点撑得很花，后者
    // 把卡片顶到 600 多像素高 —— 都不如一个对话框干净。
    //
    // ⚠️ 写回走 ``presentation_pen_palette``（bridge.SETTING_PATHS），**整表
    // 替换**：配置里存的就是一张颜色列表，没有「改第 N 项」这种路径。
    // 只在「完成 / 换一格（有改动时）/ 添加 / 删除」这几拍写 —— 拖动取色器时
    // 逐帧写会刷满日志（``setSetting`` 每行一条 info）并让色板 Repeater 逐帧重建。

    /*! 全局色板（颜色字符串列表，顺序即放映条网格的从左到右、从上到下）。
        与两个消费方同一条读法：整块读 ``presentationConfig.pen``，改完经
        ``presentationConfigChanged`` 广播刷新。 */
    readonly property var paletteColors: {
        var pen = typeof Backend !== "undefined"
                  && Backend.presentationConfig.pen !== undefined
                  ? Backend.presentationConfig.pen : ({})
        return pen.palette !== undefined ? pen.palette : []
    }
    /*! 色点直径。2026-11-21 用户「或许可以考虑拉宽 dialog」之后从 28 提到 32 ——
        拉宽腾出来的空间给色点，而不是留一片更宽的白。 */
    readonly property int paletteSwatchSize: 32
    /*! 色点间距（Fluent 的 8px 档）。对话框宽度由内容算：6 列 × 32 + 5 × 8 = 232，
        加右栏 272、两条 20 间距、1px 分割线与 48 内边距 = **593** —— 仍在 RinUI 的
        ``dialogMaximumWidth``（600）以内，所以不用去覆盖 ``implicitWidth``。 */
    readonly property int paletteSwatchSpacing: 8
    /*! 对话框里色板每行几格。⚠️ 不是放映条的 10 列：对话框受 RinUI 的
        ``dialogMaximumWidth``（600）限制，10 列 350px 再把右栏 250 塞进来就
        超了。6 列 × 5 行正好装下默认的 30 色。 */
    readonly property int paletteColumns: 6
    /*! 色块上限 —— 放映条那张选单是「贴着控制条往上弹」的浮层，颜色再多就比
        屏幕还高。60 已经是 10 行的量了。 */
    readonly property int paletteMaxColors: 60
    readonly property int paletteGridWidth: paletteColumns * paletteSwatchSize
        + Math.max(paletteColumns - 1, 0) * paletteSwatchSpacing
    /*! 右栏（功能选项 + 取色器）宽度。拉宽后取色方块从 194 长到 216。 */
    readonly property int paletteOptionsWidth: 272

    /*! 对话框里选中的那一格。 */
    property int paletteIndex: 0

    // 列表被改短（删除 / 外部改配置）时不要留一个越界的下标在那儿。
    onPaletteColorsChanged: {
        if (paletteIndex >= paletteColors.length) {
            paletteIndex = Math.max(paletteColors.length - 1, 0)
        }
    }

    /*! 色值的名字 —— 取代「第 12 个颜色」那种编号（2026-11-21 用户指令：
        「颜色要加名称而非『第 xx 个颜色』」）。

        名字是**按色值现算**的，配置里仍然只存色值字符串：色板是放映条与小黑板
        共用的一张表，改结构（变成 ``{name, color}``）两个消费方都要跟着改，
        而用户真正要的是「认得出这是哪只色」，不是一个可以自定义的标签。
        判据：无彩色先按明度分黑 / 白 / 三档灰；有彩色先按色相分 11 档，再按
        感知亮度（Rec.709 luma，比 HSV 的 value 准 —— ``#C00000`` 的 v 是 0.75，
        但它显然是深红）加「深 / 浅」前缀，低饱和的加「灰」前缀。 */
    function colorNameOf(c) {
        var v = c.hsvValue
        var s = c.hsvSaturation
        var h = c.hsvHue * 360
        if (v < 0.15) {
            return qsTr("黑色")
        }
        if (s < 0.06) {
            if (v > 0.92) {
                return qsTr("白色")
            }
            if (v > 0.75) {
                return qsTr("浅灰")
            }
            if (v > 0.5) {
                return qsTr("灰")
            }
            return qsTr("深灰")
        }
        var base
        if (h < 12 || h >= 345) {
            base = qsTr("红")
        } else if (h < 34) {
            base = qsTr("橙")
        } else if (h < 50) {
            base = qsTr("金")
        } else if (h < 70) {
            base = qsTr("黄")
        } else if (h < 95) {
            base = qsTr("黄绿")
        } else if (h < 155) {
            base = qsTr("绿")
        } else if (h < 200) {
            base = qsTr("青")
        } else if (h < 250) {
            base = qsTr("蓝")
        } else if (h < 270) {
            base = qsTr("靛")
        } else if (h < 320) {
            base = qsTr("紫")
        } else {
            base = qsTr("品红")
        }
        if (s < 0.28) {
            return qsTr("灰%1").arg(base)
        }
        var luma = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
        if (luma < 0.32) {
            return qsTr("深%1").arg(base)
        }
        if (luma > 0.75 && s < 0.55) {
            return qsTr("浅%1").arg(base)
        }
        return base
    }

    /*! 把整表写回配置（唯一的写入口）。 */
    function paletteWrite(list) {
        Backend.setSetting("presentation_pen_palette", list)
    }

    /*! 打开对话框，默认停在「当前墨迹色」那一格（找不到就第一格）。 */
    function paletteOpen() {
        var colors = paletteColors
        var start = 0
        var current = String(Backend.penColor === undefined ? "" : Backend.penColor).toUpperCase()
        if (current !== "") {
            for (var i = 0; i < colors.length; i++) {
                if (String(colors[i]).toUpperCase() === current) {
                    start = i
                    break
                }
            }
        }
        if (colors.length > 0) {
            paletteIndex = start
            palettePicker.color = Qt.color(String(colors[start]))
        }
        paletteDialog.open()
    }

    /*! 选中另一格。切之前先把这一格的改动落盘 —— 不然「改一半又去点别的格子」
        改动会静默丢掉。 */
    function paletteSelect(index) {
        var colors = paletteColors
        if (index < 0 || index >= colors.length) {
            return
        }
        paletteCommit()
        paletteIndex = index
        palettePicker.color = Qt.color(String(colors[index]))
    }

    /*! 把取色器当前色写回选中那一格；没改动就什么都不做。 */
    function paletteCommit() {
        var colors = paletteColors
        if (paletteIndex < 0 || paletteIndex >= colors.length) {
            return
        }
        var hex = palettePicker.color.toString().toUpperCase()
        if (hex === String(colors[paletteIndex]).toUpperCase()) {
            return
        }
        var list = colors.slice(0)
        list[paletteIndex] = hex
        paletteWrite(list)
    }

    function paletteApply() {
        paletteCommit()
        paletteDialog.close()
    }

    /*! 「取消」只关框、不写 —— 选色器里的改动随对话框一起丢弃。 */
    function paletteCancel() {
        paletteDialog.close()
    }

    /*! 末尾追加一格并选中它 —— 新色的初始值取强调色（与主题同源，深浅两档
        底板都看得见），用户随即在取色器里改成想要的。 */
    function paletteAdd() {
        if (paletteColors.length >= paletteMaxColors) {
            return
        }
        paletteCommit()
        var accent = String(Lumi.accent).toUpperCase()
        var list = paletteColors.slice(0)
        list.push(accent)
        paletteWrite(list)
        // ⚠️ 不走 paletteSelect：它的越界守卫按 paletteColors 判，而那一拍新
        // 列表还没经配置回来，list.length - 1 会被当成越界弹回去。万一写失败，
        // onPaletteColorsChanged 会把越界的 paletteIndex 收掉。
        paletteIndex = list.length - 1
        palettePicker.color = Qt.color(accent)
    }

    /*! 删掉选中的那一格。只剩一色时不允许删（空色板在那儿既没法点也没法看，
        用户只能手改 config.json）。 */
    function paletteRemove() {
        var colors = paletteColors
        if (paletteIndex < 0 || colors.length <= 1) {
            return
        }
        var list = colors.slice(0)
        list.splice(paletteIndex, 1)
        paletteWrite(list)
        var next = Math.min(paletteIndex, list.length - 1)
        paletteIndex = next
        palettePicker.color = Qt.color(String(list[next]))
    }

    /*! 色板入口卡：「其余一切均在 dialog 内完成」，所以这里只有一个按钮。 */
    Rin.SettingCard {
        objectName: "inkPalette"

        Layout.fillWidth: true
        title: qsTr("色板")
        description: qsTr("放映时笔的选单与小黑板的粉笔共用这份颜色表，共 %1 个颜色")
                     .arg(page.paletteColors.length)
        icon.name: "ic_fluent_color_20_regular"

        Rin.Button {
            objectName: "inkPaletteEdit"

            text: qsTr("编辑颜色")
            onClicked: page.paletteOpen()
        }
    }

    /*! 色板对话框。

        版式走 **RinUI 的 ``Rin.Dialog`` + ``Rin.DialogButtonBox`` 标准**（2026-11-21
        用户指令：「怎么不是 RinUI dialog 标准了？」—— 曾按 WinUI 3 原生 ContentDialog
        自绘过右对齐底栏，被否：本应用所有对话框都是一条带底色的横条 + 两个均分整宽的
        按钮，这个不能例外）。

        * 宽度由内容算（198 色板 + 250 右栏 + 两条 20 间距 + 1px 分割线 + 48 内边距
          = 537，在 RinUI 的 ``dialogMaximumWidth`` 600 以内）；
        * 标题 24 起、标题与内容间距 12（``Rin.Dialog`` 模板现成的，别去覆盖
          ``contentItem`` —— 那要自己补 implicitWidth/Height）；
        * 正文左右 24，两块之间用 RinUI 竖 ``ToolSeparator`` 分开（用户明确要求
          「用 RinUI 的分割线分割」）；
        * 底栏见下面 ``footer`` 的注释（有两个必须绕开的坑）。
    */
    Rin.Dialog {
        id: paletteDialog

        objectName: "inkPaletteDialog"
        title: qsTr("色板")
        modal: true

        RowLayout {
            Layout.fillWidth: true
            spacing: 20

            // ---------------------------------------------------------- 左：色板
            ColumnLayout {
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: page.paletteGridWidth
                Layout.maximumWidth: page.paletteGridWidth
                spacing: 10

                Grid {
                    id: paletteGrid
                    objectName: "inkPaletteGrid"

                    Layout.alignment: Qt.AlignLeft
                    columns: page.paletteColumns
                    rowSpacing: page.paletteSwatchSpacing
                    columnSpacing: page.paletteSwatchSpacing

                    Repeater {
                        model: page.paletteColors

                        delegate: Rin.Clip {
                            id: swatch
                            objectName: "inkPaletteSwatch"

                            required property int index
                            required property var modelData

                            readonly property bool selected: page.paletteIndex === index
                            readonly property color dotColor: Qt.color(String(modelData))
                            /*! 色点描边色 —— 跟着**主题**走：浅色主题压黑 22%、
                                深色主题提白 22%（``textPrimary`` 正好是这两档）。
                                一条 1px 的边就够分清 (2026-11-21 用户追问
                                「这里为何渐变？」) —— 之前那版在色块内侧压了
                                一层渐变当内阴影，色块整个像打了光的球，颜色也
                                被带偏；色板要读**真实颜色**，只能是平涂色。
                                也试过「按色块自己的明暗配边」，深色块在浅底上
                                会多出一圈白边像光晕，不如按底色来。 */
                            readonly property color dotEdge: Lumi.fade(Lumi.textPrimary, 0.22)

                            width: page.paletteSwatchSize
                            height: width
                            radius: width / 2
                            padding: 0
                            // 圆点自己画（见下面两块），按钮底层留空
                            color: "transparent"
                            hoverEnabled: true
                            onClicked: page.paletteSelect(swatch.index)

                            // Fluent 2 的可点表面：按下缩一点、选中那格描一圈
                            // 强调色环（与放映条色板的选中环同一个语言）。
                            scale: swatch.down ? 0.88 : 1.0
                            Behavior on scale {
                                NumberAnimation {
                                    duration: Lumi.durationFast
                                    easing.type: Easing.OutQuint
                                }
                            }

                            Rectangle {
                                objectName: "inkPaletteSwatchRing"
                                visible: swatch.selected
                                anchors.fill: parent
                                radius: width / 2
                                color: "transparent"
                                border.width: 2
                                border.color: Lumi.accent
                            }

                            /*! 色点本体：**平涂色 + 一圈自适应描边**。
                                对话框底色就是主题卡片色，纯白块压在浅色底上
                                原本会糊住（2026-11-21 用户反馈），但解法不是
                                在色块里加渐变（那会把颜色本身染偏，用户当场
                                追问「这里为何渐变」），而是让描边跟着色块自己
                                的明暗走，见 ``dotEdge``。 */
                            Rectangle {
                                objectName: "inkPaletteSwatchDot"
                                anchors.centerIn: parent
                                width: parent.width - (swatch.selected ? 6 : 0)
                                height: width
                                radius: width / 2
                                color: swatch.dotColor
                                border.width: 1
                                border.color: swatch.dotEdge

                                Behavior on width {
                                    NumberAnimation {
                                        duration: Lumi.durationFast
                                        easing.type: Easing.OutQuint
                                    }
                                }
                            }
                        }
                    }
                }

                /*! 追加一格。⚠️ 不垫 ``Layout.fillHeight`` 的 spacer 把它推到底：
                    那样按钮会孤零零悬在左栏中下方的空白里，像是页面漏了一块。 */
                Rin.Button {
                    objectName: "inkPaletteAdd"

                    Layout.fillWidth: true
                    text: qsTr("添加颜色")
                    // 到上限就置灰（理由见 paletteMaxColors）
                    enabled: page.paletteColors.length < page.paletteMaxColors
                    onClicked: page.paletteAdd()
                }

                // 说明压在左栏最底下（中间留弹性空白），右栏比左栏高出来的那截
                // 就不会在左下角露出一块洞。
                Item {
                    Layout.fillHeight: true
                }

                /*! 说明放左栏底部：它讲的是整个对话框（点完成才写回），
                    挂在右栏会让右栏比左栏高出一大截、左下角空出一块。 */
                Rin.Text {
                    Layout.fillWidth: true
                    typography: Rin.Typography.Caption
                    color: Lumi.textSecondary
                    wrapMode: Text.Wrap
                    text: qsTr("点「完成」后，所有使用此色板的界面都会立即应用新的颜色。")
                }
            }

            /*! RinUI 的竖分割线（``ToolSeparator``）：``vertical`` 是**只读**的
                （Qt 按宽高比自己判「竖」，实测赋值直接编译失败），所以靠
                ``preferredWidth: 1`` + ``fillHeight`` 让它变成一根竖线。
                ⚠️ ``padding`` 必须归零：RinUI 那版给了四边 2，控件实际要占 5px，
                而对话框宽度是按「分割线 1px」算出来的，多出来的 4px 会把右栏
                顶出内边距（实测「删除这个颜色」压在卡片右沿上）。 */
            Rin.ToolSeparator {
                objectName: "inkPaletteDivider"

                padding: 0
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignVCenter
            }

            // ------------------------------------------------------ 右：功能选项
            ColumnLayout {
                id: paletteOptions

                objectName: "inkPaletteOptions"
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: page.paletteOptionsWidth
                Layout.maximumWidth: page.paletteOptionsWidth
                spacing: 8

                Rin.Text {
                    objectName: "inkPaletteColorName"

                    Layout.fillWidth: true
                    typography: Rin.Typography.BodyStrong
                    elide: Text.ElideRight
                    text: page.colorNameOf(palettePicker.color)
                }

                Rin.Text {
                    objectName: "inkPaletteColorHex"

                    Layout.fillWidth: true
                    typography: Rin.Typography.Caption
                    color: Lumi.textSecondary
                    text: palettePicker.color.toString().toUpperCase()
                }

                Rin.ColorPicker {
                    id: palettePicker
                    objectName: "inkPalettePicker"

                    // ⚠️ 必须给 ``maximumWidth``：``ColorPicker`` 的根是
                    // ``ColumnLayout``，套在另一个布局里时 Qt 会把它撑满整行
                    // （只写 preferredWidth 被无视，实测会变成整行宽、取色方块
                    // 跟着见方放大，把对话框顶出窗口）。
                    Layout.preferredWidth: page.paletteOptionsWidth
                    Layout.maximumWidth: page.paletteOptionsWidth
                    Layout.topMargin: 2
                    // 盒子取色器（不是环）：色板本来就是「一堆方块里挑一个」的
                    // 用法。通道输入与 alpha 都收起 —— 墨迹色没有透明度，通道
                    // 那一整块在这个宽度里也是噪音。
                    ringMode: false
                    moreVisible: false
                    colorChannelInputVisible: false
                    alphaEnabled: false
                }

                Rin.Button {
                    objectName: "inkPaletteDelete"

                    Layout.fillWidth: true
                    text: qsTr("删除这个颜色")
                    // 只剩一色时不给删（理由见 paletteRemove）
                    enabled: page.paletteColors.length > 1
                    onClicked: page.paletteRemove()
                }

            }
        }


        footer: Rin.DialogButtonBox {
            id: paletteDialogButtons

            objectName: "inkPaletteFooter"

            Rin.Button {
                objectName: "inkPaletteCancel"

                Layout.fillWidth: true
                Layout.preferredWidth: paletteDialogButtons.availableWidth / 2
                text: qsTr("取消")
                onClicked: page.paletteCancel()
            }

            Rin.Button {
                id: paletteDialogDone
                objectName: "inkPaletteDone"

                Layout.fillWidth: true
                Layout.preferredWidth: paletteDialogButtons.availableWidth / 2
                text: qsTr("完成")
                /*! 强调色三件套（2026-11-21 用户截图问「这个按钮？」）：
                    ``color`` 与 ``primaryColor`` 都钉成强调色 —— 只钉 ``color``
                    会留下「强调色实底 + 一圈 controlBorderColor 浅边」。 */
                highlighted: true
                primaryColor: Lumi.accent
                color: Lumi.accent
                /*! ⚠️ 自我纠正：``DialogButtonBox`` 会在建子项 / 布局时按 role 把
                    ``highlighted`` 清成 false（它自己的 delegate 只给 AcceptRole 高亮，
                    而我们这两个是手写的子项）。0ms 定时器补那一下**看时序**（浅色
                    主题实测会漏），所以改成「被清掉就立刻改回来」——写回 true 之后
                    不会再触发这个分支，不会打转。 */
                onHighlightedChanged: {
                    if (!highlighted) {
                        highlighted = true
                    }
                }
                onClicked: page.paletteApply()
            }
        }

    }
}
