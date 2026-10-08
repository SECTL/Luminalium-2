import QtQuick
import QtQuick.Window
import RinUI as Rin
import Luminalium

/*!
    竖版两侧翻页 pill —— **横版翻页 pill（``PresentationDock`` 的 ``pager``
    区块）旋转 90° 的同款布局**，贴屏幕左右边缘、垂直居中。

    尺寸与排布**直接由横版转置**而来，不是另一套比例（2026-09-30 用户指令：
    「竖版的按照横版翻转的布局来，不要全抄 L1」—— L1 竖版那套 margin 8 /
    大小字页码弃用）::

        横版 180×62：4 + 圆钮44 + 8 + 页码68 + 8 + 圆钮44 + 4
        竖版  62×180：同一行账，方向朝下 —— 圆钮 / 图标 / 间距 / 页码区 /
                      沿轴留白全部与横版同档，配置直接共用
                      （``pager.width`` / ``pager.spacing`` /
                        ``pager.surface_padding_x``）

    即::

        ║                       ║
        ║  ┌─────┐              ║
        ║  │  ▲  │              ║
        ║  │26/41│              ║
        ║  │     │              ║
        ║  │  ▼  │              ║
        ║  └─────┘              ║
        ║                       ║

    设计语言与横版共用：

    * 全圆胶囊底板（``FlyoutSurface`` 的 ``vertical`` 模式：内容自上而下，
      圆角按短边钳制）+ CW2 同款渐变边框高光 + flyout 投影 —— 全部照旧；
    * 圆形翻页钮就是 ``IconButton`` 本尊（与横版同一枚）；
    * 页码**三行堆叠**：当前页 / 斜杠 / 总页数，斜杠用小一号的字
      （Caption）—— 2026-09-30 用户指令；横版仍是单行 ``26/41``；
      翻页时页码做透明度脉冲（``PagePulse``），横竖版同一套节奏；
    * chevron 图标直接用 Fluent 的上 / 下箭头（横版是左右箭头，转向即旋转）。

    点击行为与横版一致，走 ``Backend.previousSlide()`` / ``nextSlide()``
    （含限流与轻量页码刷新）。

    ``corner`` 由 Python 注入（middle_left / middle_right）；显隐由
    ``presentation.corners.<corner>.enabled`` 与 ``pager.enabled`` 决定。
    本组件**只有翻页一组**—— 竖条里塞工具 / 动作组是另一个命题（L1 也没做）。
*/
Item {
    id: pager

    property string corner: "middle_left"

    /*! 挂在屏幕**右侧**（``middle_right``）—— 快速切页面板往条的另一侧长，
        于是「面板总在屏幕内侧」这条在两个角落都成立。 */
    readonly property bool cornerIsRight: corner.indexOf("right") >= 0

    // ------------------------------------------------------------ 配置读取
    readonly property var cfg: Backend.presentationConfig

    /*! **组件整体缩放倍率**（``presentation.scale``，与横版工具栏同一个开关）。
        1.0 = 设计原档。画法与横版 ``PresentationDock`` 完全一致：一个 ``scale``
        变换打在底板上（投影 / 高光 / 页码文字一起缩放），而 ``width`` /
        ``height`` / ``shadowMargin`` / ``interactiveRect`` 这几个**对外**的量
        换算成屏幕像素，于是 Python 摆位与区域塑形、编辑器预览都不用改。
        ⚠️ 别把倍率乘进下面的尺寸令牌（``pillWidth`` / ``contentHeight`` …）——
        那些是设计单位，再乘一遍就是双重缩放。 */
    readonly property real scaleFactor: {
        var value = cfg.scale !== undefined ? Number(cfg.scale) : 1.0
        if (!(value > 0))
            return 1.0
        return Math.max(0.25, Math.min(4.0, value))
    }

    readonly property var surfaceCfg: cfg.surface !== undefined ? cfg.surface : ({})
    readonly property var shadowCfg: surfaceCfg.shadow !== undefined ? surfaceCfg.shadow : ({})
    readonly property var buttonsCfg: cfg.buttons !== undefined ? cfg.buttons : ({})
    readonly property var pagerCfg: cfg.pager !== undefined ? cfg.pager : ({})
    readonly property var sideCfg: pagerCfg.side !== undefined ? pagerCfg.side : ({})

    /*! ``pager.enabled`` 与横版同一开关（设置页「页码切换」）。 */
    readonly property bool pagerEnabled: pagerCfg.enabled !== false

    // ---- 页码快速跳转（点页码展开的面板，``presentation/PageJumpPanel.qml``）----
    // 与横版**共用同一个组件、同一份配置**（``presentation.pager.jump``）——
    // 两个形态只是面板往外长的那一侧不同（见 ``enterFrom``）。横版接线的来龙
    // 去脉写在 ``PresentationDock.qml`` 与 ``PageJumpPanel.qml`` 的注释里。
    readonly property var jumpCfg: pagerCfg.jump !== undefined ? pagerCfg.jump : ({})
    readonly property bool jumpEnabled: jumpCfg.enabled !== false

    /*! 快速切页面板展开着没有（``interactiveRect`` / 区域塑形 / Python 侧
        「光标移出就收」都看它，与横版同名同义）。另外它还是**同侧 pill 的显隐
        开关** —— 面板贴窗口边铺满整高，正好把 pill 整个盖住，留着它既多余又
        会跟面板抢那一块命中区（L1 是 ``hidden-flipper`` 同款做法）。 */
    readonly property bool jumpPanelOpened: jumpPanel.opened

    /*! 可用空间（**屏幕逻辑像素**）= 所在**窗口**的尺寸 —— 遮罩层是铺满放映
        窗口的整屏窗口，所以窗口尺寸就是面板能用的地方。

        ⚠️ 别改成 ``parent.width/height``：``TopWindow`` 的 ``containerItem`` 是
        ``anchors.fill: parent``，而那个 ``Qt.Tool`` 透明窗口的 contentItem 尺寸
        **实测不可靠**（0 / 陈旧值 / 建窗口那一刻的默认 160×160，取决于读的时机）
        —— 拿它算可用空间，面板会被静默压扁或压成单列（2026-10-06 预览实锤：
        屏幕底部那条横版控制条算出来的面板只有一行高）。 */
    readonly property real availableWidth: {
        var win = Window.window
        if (win) {
            return win.width
        }
        return parent ? parent.width : 0
    }
    readonly property real availableHeight: {
        var win = Window.window
        if (win) {
            return win.height
        }
        return parent ? parent.height : 0
    }

    /*! 点页码区：开 / 关面板（总页数为 0 时不动，理由同横版）。 */
    function toggleJumpPanel() {
        if (!jumpEnabled || Backend.slideTotal <= 0) {
            return
        }
        jumpPanel.opened = !jumpPanel.opened
    }

    /*! 收起切页面板（给 Python 侧的「点外部收起」调）。 */
    function closeJumpPanel() {
        jumpPanel.opened = false
    }

    // ---- 尺寸（横版 pill 的转置；默认值 = Lumi 里同档令牌）----
    readonly property int pillWidth: sideCfg.width !== undefined
        ? sideCfg.width : Lumi.dockSidePagerWidth
    readonly property int pillHeight: sideCfg.height !== undefined
        ? sideCfg.height : Lumi.dockSidePagerHeight
    /*! 沿轴留白（竖条即上下）= 横版翻页 pill 的 surface_padding_x（4）。 */
    readonly property int pillPadding: sideCfg.padding !== undefined
        ? sideCfg.padding : Lumi.dockSidePagerPadding
    /*! 横向（垂直于轴）留白 = 工具条档的 9（横版 pill 的上下也是这一档）。 */
    readonly property int crossPadding: surfaceCfg.padding_y !== undefined
        ? surfaceCfg.padding_y : Lumi.dockPaddingY
    /*! 圆钮直径与横版同档（buttons.hit_size）。 */
    readonly property int contentHeight: buttonsCfg.hit_size !== undefined
        ? buttonsCfg.hit_size : Lumi.dockHitSize
    /*! 圆钮与页码区之间的间距 = 横版的 pager.spacing（8）。 */
    readonly property int pagerSpacing: pagerCfg.spacing !== undefined
        ? pagerCfg.spacing : Lumi.dockPagerSpacing
    /*! 页码区高度 = 横版页码文本区的宽度 pager.width（68）—— 转置关系。 */
    readonly property int infoHeight: pagerCfg.width !== undefined
        ? pagerCfg.width : Lumi.dockPagerWidth

    readonly property int iconSize: buttonsCfg.icon_size !== undefined
        ? buttonsCfg.icon_size : Lumi.dockIconSize
    readonly property int hitSize: contentHeight

    // ---- 图标（chevron 朝上 / 朝下 = 横版左右箭头旋转 90° 的对应物）----
    readonly property string iconPrev: sideCfg.icon_prev !== undefined
        ? sideCfg.icon_prev : "ic_fluent_chevron_up_20_filled"
    readonly property string iconNext: sideCfg.icon_next !== undefined
        ? sideCfg.icon_next : "ic_fluent_chevron_down_20_filled"

    // ---- 底板 / 投影 / 高光（与横版同一套开关）----
    readonly property real surfaceRadius: surfaceCfg.radius !== undefined
        ? surfaceCfg.radius : Lumi.dockSurfaceRadius
    readonly property real surfaceOpacity: surfaceCfg.opacity !== undefined
        ? surfaceCfg.opacity : Lumi.dockSurfaceOpacity
    readonly property bool highlightEnabled: surfaceCfg.highlight !== undefined
        ? surfaceCfg.highlight === true : true
    readonly property bool shadowEnabled: shadowCfg.enabled !== undefined
        ? shadowCfg.enabled : true
    readonly property int shadowMarginCfg: shadowCfg.margin !== undefined
        ? shadowCfg.margin : Lumi.dockShadowMargin
    readonly property real shadowBlur: shadowCfg.blur !== undefined ? shadowCfg.blur : 18
    readonly property real shadowOffsetY: shadowCfg.offset_y !== undefined
        ? shadowCfg.offset_y : 6
    /*! 投影余量（**屏幕像素**）—— Python 摆放时扣掉；竖条垂直居中时它上下对称，
        无需特殊处理。跟着 ``scaleFactor`` 走，否则缩放后贴边 / 居中会漂。 */
    readonly property int shadowMargin: Math.round(bar.margin * scaleFactor)
    /*! 高光环是否真的在画（自检用；经 FlyoutSurface 透出，与横版同名同义）。 */
    readonly property bool highlightRingVisible: bar.highlightRingVisible

    /*! 本条表面（不含投影余量）的交互矩形，坐标相对本 Item（= 屏幕像素，
        已按 ``scaleFactor`` 换算）。

        快速切页面板展开时把面板那一块也**并进来** —— 它浮在条的包围盒之外
        （条贴屏幕边，面板往屏幕内侧长），不并的话面板既画不出来（``SetWindowRgn``
        裁掉）也点不动（点击穿透到 PowerPoint，在幻灯片上乱画一笔）。 */
    readonly property rect interactiveRect: {
        var s = scaleFactor
        var m = bar.margin * s
        var left = m
        var top = m
        var right = bar.implicitWidth * s - m
        var bottom = bar.implicitHeight * s - m
        if (jumpPanelOpened && jumpPanel.visible) {
            left = Math.min(left, jumpPanel.x)
            right = Math.max(right, jumpPanel.x + jumpPanel.width * s)
            top = Math.min(top, jumpPanel.y)
            bottom = Math.max(bottom, jumpPanel.y + jumpPanel.height * s)
        }
        return Qt.rect(left, top, Math.max(right - left, 0), Math.max(bottom - top, 0))
    }

    /*! 命中矩形变了（快速切页面板开合）。Python 侧连这个信号去重算窗口区域 ——
        平时的区域同步是 800ms 一拍，跟不上「点一下就长出一块面板」这种瞬时变化。 */
    signal hitRectChanged()

    onInteractiveRectChanged: hitRectChanged()

    /*! 根 Item 的尺寸 = **缩放后**的屏幕像素（Python 摆位 / 区域塑形 / 编辑器
        预览都读它，见 ``scaleFactor`` 的说明）。 */
    implicitWidth: Math.round(bar.implicitWidth * scaleFactor)
    implicitHeight: Math.round(bar.implicitHeight * scaleFactor)
    width: implicitWidth
    height: implicitHeight

    FlyoutSurface {
        id: bar
        // ⚠️ 不能用 ``anchors.fill: parent``：根 Item 已是缩放后的尺寸，再铺满
        //    就是双重缩放。底板保持设计尺寸，缩放交给 ``scale``（左上角钉死，
        //    与根 Item 的 0 点重合）。
        width: implicitWidth
        height: implicitHeight
        scale: pager.scaleFactor
        transformOrigin: Item.TopLeft
        vertical: true
        // 面板展开时把自己让开（面板贴的是窗口边，与 pill 同一块地方）
        visible: !pager.jumpPanelOpened
        // 横版的两个留白档原样转置：沿轴 4（横版的左右）、横向 9（横版的上下）
        paddingX: pager.crossPadding
        paddingY: pager.pillPadding
        contentSpacing: pager.pagerSpacing
        surfaceRadius: pager.surfaceRadius
        surfaceOpacity: pager.surfaceOpacity
        highlightEnabled: pager.highlightEnabled
        shadowEnabled: pager.shadowEnabled
        shadowMargin: pager.shadowMarginCfg
        shadowBlur: pager.shadowBlur
        shadowOffsetY: pager.shadowOffsetY

        // ================================================ 上一页（chevron 朝上）
        IconButton {
            objectName: "sidePagerPrev"
            visible: pager.pagerEnabled
            iconName: pager.iconPrev
            tooltip: qsTr("上一页")
            hitSize: pager.hitSize
            glyphSize: pager.iconSize
            onClicked: Backend.previousSlide()
        }

        // ==================================== 页码（三行：26 / 小斜杠 / 41）
        // 除了显示，**还是快速切页面板的触发点**（与横版同一个落点，只是这里
        // 的条是竖的）。包一层 Item 是因为 ``Flow`` 的子项不能用 anchors
        // （见竖版说明），而这个热区里要有「hover 底 + 脉冲文字 + 点击」三层。
        Item {
            id: pagerHit
            objectName: "sidePagerHit"
            visible: pager.pagerEnabled
            width: pager.contentHeight
            height: pager.infoHeight

            // hover 底 / 面板开着时保持点亮（与横版同一套反馈，见 PresentationDock）
            //
            // ⚠️ 圆角用 ``Lumi.dockPagerHitRadius``（短边一半 = 胶囊），**不是**
            //    ``Lumi.dockJumpItemRadius``(8) —— 那是快速切页面板里**卡片**的圆角，
            //    与这里不是同一族（2026-10-06 用户实锤「翻页组件的 hover 不行」，
            //    竖版偏位）。理由与横版逐条相同，见 ``Lumi.qml`` 里那枚令牌的说明。
            Rectangle {
                objectName: "sidePagerHitSurface"
                anchors.fill: parent
                radius: Lumi.dockPagerHitRadius
                color: pagerHitArea.containsMouse || pager.jumpPanelOpened
                    ? Lumi.dockJumpItemHover : "transparent"
                Behavior on color {
                    ColorAnimation {
                        duration: Lumi.dockJumpFadeDuration
                        easing.type: Easing.OutQuint
                    }
                }
            }

            // 变化时走透明度脉冲（与横版同一套节奏，见 PagePulse.qml）
            PagePulse {
                anchors.fill: parent
                page: Backend.slideIndex

                Column {
                    anchors.centerIn: parent
                    spacing: 0

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        typography: Rin.Typography.BodyLarge
                        text: Backend.slideTotal > 0 ? Backend.slideIndex : "-"
                    }

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        typography: Rin.Typography.Caption
                        text: "/"
                    }

                    Rin.Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        typography: Rin.Typography.BodyLarge
                        text: Backend.slideTotal > 0 ? Backend.slideTotal : "-"
                    }
                }
            }

            MouseArea {
                id: pagerHitArea
                anchors.fill: parent
                enabled: pager.jumpEnabled
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: pager.toggleJumpPanel()
            }
        }

        // ================================================ 下一页（chevron 朝下）
        IconButton {
            objectName: "sidePagerNext"
            visible: pager.pagerEnabled
            iconName: pager.iconNext
            tooltip: qsTr("下一页")
            hitSize: pager.hitSize
            glyphSize: pager.iconSize
            onClicked: Backend.nextSlide()
        }
    }

    // ============================================ 快速切页面板（点页码展开）
    // 声明在 ``bar`` 之后 → 绘制、命中都在控制条之上。
    //
    // ⚠️ **面板贴的是窗口边，不是控制条**。L1 的形态是 ``right: 16px; top: 24px;
    //    bottom: 24px`` —— 一整条贴屏幕边的侧栏。第一版把它贴着条摆（往屏幕
    //    内侧长），用户对着 L1 直说「不像」，所以整块定位重来了。既然它盖的正是
    //    pill 那一块，pill 就得让开（见 ``bar.visible``）。
    //
    // ⚠️ 与横版同一条约定：**不进**根 Item 的 ``implicitWidth/Height``（否则
    //    Python 摆位要重算，条会闪一帧），代价是 ``interactiveRect`` 必须自己
    //    把面板包进来（上面那段就是）。
    PageJumpPanel {
        id: jumpPanel
        objectName: "sidePageJumpPanel"

        // 翻页组被关掉（``pager.enabled``）时不铺卡片 —— 那个角落没有页码区、
        // 没有触发点，白建几十张卡片纯属浪费（与横版同一条）。
        total: pager.pagerEnabled ? Backend.slideTotal : 0
        current: Backend.slideIndex
        opened: false
        // 条贴窗口左边 → 面板也贴窗口左边（L1 按点击位置选边，这里条的位置
        // 已经说明了点击在哪一侧，同一个结论）
        side: pager.cornerIsRight ? "right" : "left"

        // ``scale`` 跟着倍率（与笔选单一致）：底板的字号 / 图形一起缩放，面板
        // 不跟着走就成两个体量。⚠️ x/y 是**屏幕逻辑像素**，宽高是设计单位。
        scale: pager.scaleFactor
        transformOrigin: Item.TopLeft

        // 横向：贴窗口的左右边（``Lumi.dockJumpEdge``）。
        // ⚠️ 面板 Item 的宽是**滑行路径的并集**（比卡片多出 ``enterDistance``，
        //    见组件头注释），所以贴左边时要再往左让出一整条 ``enterDistance``。
        //    ``want`` 是 dock 内部坐标 —— 先把 ``pager.x``（本条的窗口原点）扣掉。
        x: (pager.cornerIsRight
            ? pager.availableWidth
              - (Lumi.dockJumpEdge + jumpPanel.cardWidth) * pager.scaleFactor
            : (Lumi.dockJumpEdge - jumpPanel.enterDistance) * pager.scaleFactor)
            - pager.x

        // 纵向：L1 是 ``top: 24px`` —— 面板自己铺满整高，上下各让 24
        y: Lumi.dockJumpInset * pager.scaleFactor - pager.y

        // 可用高度 = 窗口高减去上下那两条 24（L1 的面板高度由**窗口**决定，
        // 与页数无关；页数少时由组件自己收短，见组件头注释）
        maxHeight: Math.max(pager.availableHeight / pager.scaleFactor
                            - Lumi.dockJumpInset * 2, 0)
        maxWidth: Math.max(pager.availableWidth / pager.scaleFactor, 0)

        onPagePicked: function (page) {
            Backend.gotoSlide(page)
            // 跳完就收 —— 面板的使命结束了
            jumpPanel.opened = false
        }
    }

    // 退出放映 → 收起面板：下一次放映进来时不该看到上次遗留的一块卡片
    //（横版同一处逻辑在 Connection 里，见 PresentationDock.qml）。
    Connections {
        target: Backend

        function onPresentationActiveChanged() {
            if (!Backend.presentationActive) {
                jumpPanel.opened = false
            }
        }
    }
}
