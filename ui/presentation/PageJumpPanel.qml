import QtQuick
import RinUI as Rin
import Luminalium

/*!
    页码快速跳转面板 —— **点控制条上的页码**展开的一块浮出层，点哪一格跳哪一页。

    ## 出处：Luminalium 1 的「点按翻页」扩展

    L1 的 ``ppt_assistant/ui/overlay.html`` 里，翻页 pill 中间那块 ``.page-info-container``
    是可以点的：点下去从屏幕侧边滑出一列页面（``#page-selector``），每一页是一张
    缩略图 + 右下角大号页码，当前页描一圈 accent，点缩略图就 ``bridge.gotoSlide``。
    那个交互解决的是「几十页的演示翻到第 7 页要点七下」这件事 —— 值得搬。

    ## 搬过来时改掉的一处：内容从「缩略图列表」换成「页码网格」

    L2 的后端**没有导出幻灯片缩略图这条通道**：``ppt_controller`` 只读页码与总页数
    （``View.CurrentShowPosition`` / ``Slides.Count``），要出图得走 COM 的
    ``Slides(i).Export`` 逐页写临时文件 —— 对一个「点一下就要立刻看到」的浮出层
    来说这是很重的一笔开销（几十页 = 几十次 COM 调用 + 一堆临时文件的清理），
    而且 COM 命令是异步投递的，缩略图会一格一格慢慢长出来（L1 里那圈
    ``.loading-spinner`` 就是为它准备的）。

    所以这里改成 **Fluent 的页码网格**：格子就是数字，天然不需要异步加载，
    打开即完整；触屏上点数字也比点一张 16:9 缩略图更准（后者要精细瞄准）。
    代价是丢掉了「用画面找页」的能力 —— 换来的是「一按就到」。

    ## 保留的 L1 手感

    * **点页码展开 / 点外部收起 / 当前页一眼可见**，三条都在；
    * **滑入而不是缩放**：缩放会让数字发虚（``scale`` 在非整数倍下会重采样文字），
      位移则始终清晰。曲线走 Fluent 2 的 decelerate（``OutQuint``），收起更快更干脆；
    * 面板**贴边**展开：横版条在屏幕下部 → 面板往条上方长；竖版条在屏幕两侧 →
      面板往条的内侧长（见 ``enterFrom``）。

    ## 当前页的高亮方式换了

    L1 是「2px accent 描边」（``.page-item.active { border-color: var(--accent-color) }``）。
    这里改成 Fluent 的**实底强调**（WinUI 的 SelectedBackground 同款）+ 反色文字：
    描边在触屏上扫过去几乎看不见，而「我现在在第几页」是这块面板唯一的锚点。

    ## 与「区域塑形」的关系（改这块前必读）

    顶层窗口被 ``SetWindowRgn`` 裁成「只有控制条几块」，**区域外既不绘制也不参与
    命中**。本面板浮在控制条包围盒**之外**，所以：

    * 调用方必须把它算进 ``interactiveRect``（``PresentationDock`` / ``SidePager``
      里各有一段），否则点格子会穿透到 PowerPoint，变成在幻灯片上乱画一笔；
    * 展开的一瞬间区域要**立刻**重算 —— 调用方为此发 ``hitRectChanged``，
      Python 侧接住后重算（只靠 800ms 一拍那份是来不及的）。

    ## 「点外部收起」为什么在 Python 侧

    窗口在区域塑形模式下，面板以外的区域是**系统级穿透**的 —— 点过去的事件根本
    到不了这个进程，QML 里挂多少个 MouseArea 都收不到。所以「点外面」的判据是
    Python 侧的光标位置（``windows.py::_watch_overlay``，200ms 一拍），它读控制条的
    ``interactiveRect``（含本面板）判断光标是否还在里面，不在就调
    ``closeJumpPanel()``。

    ## 自检相关的镜像属性

    * ``reveal``（0..1 展开进度）：等它到 1 再读几何，别读进出场动画半路的值；
    * ``cardWidth`` / ``cardHeight`` / ``cardX`` / ``cardY``：卡片本体（不含投影余量）
      的几何 —— 调用方按它算落点，自检按它算间距；
    * 格子上的 ``surfaceFill`` / ``labelColor``：颜色经效果层 / 分组属性在 PySide
      侧拿不到，各挂一份；
    * ``currentCell``：当前页那一格的 Item 引用（找不到时为 null）—— 「高亮有没有
      落在对的那一格上」直接查它，不用去遍历所有格子。
*/
Item {
    id: root

    // ------------------------------------------------------------ 数据（调用方给）
    /*! 总页数（``Backend.slideTotal``）。0 = 没在放映 / 还没读到页码 —— 此时
        面板空着，调用方也不该放它出来。 */
    property int total: 0
    /*! 当前页，**1-based**（``Backend.slideIndex``，与页码显示同一个口径）。 */
    property int current: 0
    /*! 每行几格（``presentation.pager.jump.columns``）。 */
    property int columns: Lumi.dockJumpColumns

    // ------------------------------------------------------------ 空间约束
    /*! 这块面板**整体**（含投影余量）能用多大 —— 调用方按「从条的边缘到屏幕另一
        端」算好传进来。行数或列数超出时就吃这个上限，内容转为滚动。

        ⚠️ 传 0 表示「不限制」，不是「没有空间」：调用方拿不到父级尺寸时给 0，
        面板就按内容自然尺寸摆（自检 / 预览里宿主尺寸不一时不至于塌成 0 宽）。 */
    property real maxWidth: 0
    property real maxHeight: 0

    // ------------------------------------------------------------ 展开 / 收起
    /*! 展开开关（语义）。动画进度看 ``reveal``。 */
    property bool opened: false
    /*! 面板相对**触发点**的方位 —— 只决定滑入的起点方向：
        ``up`` 面板在条上方（横版），``right`` 在条右侧，``left`` 在条左侧。 */
    property string enterFrom: "up"

    /*! 进出场是否走动画。默认开；关掉时 ``reveal`` 直接落到 0 / 1。

        ⚠️ 这个开关是给**离屏抓图工具**用的（``tools/preview.py`` 里置 false）：
        预览在屏幕外建窗口抓帧，``Behavior`` 的时间轴在那种环境下**推进不可靠**
        —— 同一份面板实测在可见窗口、离屏窗口、TopWindow 宿主里都能正常推到 1，
        唯独走完整预览流程时停在 0（组件逻辑没问题，是预览环境的问题，详见
        ``tools/jump_probe.py``）。抓图要的是**稳定终态**而不是动画中间态，
        所以让它一步到位。

        顺带也是个正经的「减少动效」钩子 —— 将来要接系统设置就从这儿接。 */
    property bool animate: true

    /*! 点了一格（页码 **1-based**）—— 交给调用方去驱动后端跳页。 */
    signal pagePicked(int page)

    // ------------------------------------------------------------ 尺寸令牌
    readonly property int shadowMargin: Lumi.dockJumpShadowMargin
    readonly property int padding: Lumi.dockJumpPadding
    readonly property int cellSize: Lumi.dockJumpCellSize
    readonly property int cellSpacing: Lumi.dockJumpCellSpacing

    /*! 实际列数：配置值先按「一格都不许挤扁」的宽度上限收一次。
        列数是由宽度**约束**出来的，不是反过来 —— 否则列数配大一点，格子就会
        顶出屏幕（面板不像文字那样能省略，格子必须完整可见）。 */
    readonly property int effColumns: {
        if (total <= 0) {
            return Math.max(1, columns)
        }
        var step = cellSize + cellSpacing
        var limit = Math.max(1, columns)
        if (maxWidth > 0) {
            var usable = maxWidth - shadowMargin * 2 - padding * 2
            limit = Math.min(limit, Math.max(1, Math.floor((usable + cellSpacing) / step)))
        }
        return limit
    }
    /*! 需要几行。 */
    readonly property int rows: total > 0
        ? Math.ceil(total / effColumns) : 0

    /*! 网格区域的宽 / 内容总高。 */
    readonly property real gridWidth: effColumns * cellSize
        + Math.max(effColumns - 1, 0) * cellSpacing
    readonly property real gridHeight: rows > 0
        ? rows * cellSize + (rows - 1) * cellSpacing : 0

    /*! 卡片**本体**（不含投影余量）的尺寸。宽按网格算死（不靠内容撑 ——
        内容在 Flickable 里，撑不到卡片）；高取内容高，超上限就由视口裁掉、转滚动。 */
    readonly property real maxCardWidth: maxWidth > 0
        ? Math.max(maxWidth - shadowMargin * 2, cellSize + padding * 2) : Infinity
    readonly property real maxCardHeight: maxHeight > 0
        ? Math.max(maxHeight - shadowMargin * 2, cellSize + padding * 2) : Infinity
    readonly property real cardWidth: Math.min(
        Math.max(gridWidth + padding * 2, cellSize + padding * 2), maxCardWidth)
    readonly property real cardHeight: Math.min(
        gridHeight + padding * 2, maxCardHeight)

    /*! 内容区（滚动视口）——
        ⚠️ 它是滚动的**唯一**依据：``gridHeight > viewportHeight`` 才需要滚。
        ``cardHeight`` 被上限钳住时两者就会不等。 */
    readonly property real viewportWidth: cardWidth - padding * 2
    readonly property real viewportHeight: cardHeight - padding * 2
    readonly property bool scrollable: gridHeight > viewportHeight + 0.5

    /*! 含投影余量的整体尺寸（调用方按它摆位）。 */
    implicitWidth: cardWidth + shadowMargin * 2
    implicitHeight: cardHeight + shadowMargin * 2

    /*! 镜像给调用方 / 自检：卡片本体几何。 */
    readonly property real cardX: shadowMargin
    readonly property real cardY: shadowMargin

    // 面板是纯绘制物，尺寸由 ``implicit*`` 自己说了算
    width: implicitWidth
    height: implicitHeight

    // ------------------------------------------------------- 动画（Fluent 2 flyout）
    /*! 展开进度 0..1。``opened`` 是语义开关，``reveal`` 是它的动画影子。 */
    property real reveal: 0
    onOpenedChanged: {
        reveal = opened ? 1 : 0
        if (opened) {
            // ⚠️ 必须等这一帧的几何都落地（``cardHeight`` / 视口高度都还要重算）
            //     再定位，否则读到的是上一帧的视口高，滚到的地方会偏。
            Qt.callLater(centerOnCurrent)
        }
    }
    Behavior on reveal {
        // 关掉动画时 ``reveal`` 直接落地（离屏抓图用，见 ``animate``）
        enabled: root.animate
        NumberAnimation {
            // 展开：淡入快、滑入慢一档（与笔选单同一套分工）；收起整体更快 ——
            // 退出比进入干脆，这是 Fluent 2 的直觉。
            duration: opened ? Lumi.dockJumpEnterDuration : Lumi.dockJumpFadeDuration
            easing.type: Easing.OutQuint
        }
    }
    opacity: reveal
    /*! 收起动画期间还得画着（不然淡出没了），归零后才真正藏起来。 */
    visible: reveal > 0.001

    /*! 滑入的起点偏移：面板在条上方 → 起点偏下；在条右侧 → 起点偏左；左侧反之。
        终点（``reveal`` = 1）时归零。 */
    readonly property int enterDx: enterFrom === "right" ? -Lumi.dockJumpEnterOffset
        : (enterFrom === "left" ? Lumi.dockJumpEnterOffset : 0)
    readonly property int enterDy: enterFrom === "up" ? Lumi.dockJumpEnterOffset : 0

    /*! 页码 → 那一格所在的行号（0-based）。当前页超出范围时返回 -1。 */
    function rowOfPage(page) {
        if (page < 1 || page > total) {
            return -1
        }
        return Math.floor((page - 1) / effColumns)
    }

    /*! 把当前页所在的那一行滚到视口**正中** —— 上下都能看到前后的邻居，
        用户一眼就知道「我在中间偏哪边」。已经能看到时也照样居中对齐：
        点到第 7 页再来开面板，那一行立刻在正中，比「刚好露出来」好找。
        内容不够一屏（不可滚 / 居中位置越界）时会被 Flickable 自己钳住。 */
    function centerOnCurrent() {
        if (total <= 0 || !opened) {
            return
        }
        var row = rowOfPage(current)
        if (row < 0 || !scrollable) {
            flick.contentY = 0
            return
        }
        var step = cellSize + cellSpacing
        var want = row * step - (viewportHeight - cellSize) / 2
        var maxY = Math.max(0, gridHeight - viewportHeight)
        flick.contentY = Math.max(0, Math.min(maxY, want))
    }

    // ================================================================ 卡片本体
    /*! 投影必须先于底板声明，否则会盖在底板上面。与笔选单同一枚（``Rin.Shadow``
        的 flyout 一档），两块浮出层才是「一家人」。

        ⚠️ 排查记录（2026-10-06）：预览图里本面板「底部少一行」，一度怀疑是这里
        的 ``cached: true`` 在卡片长高后没刷新。**不是** —— 那是左下角的**开发
        水印**盖住了最后一行（``DevWatermark`` 正好在左翻页条那一侧）。两侧面板
        只有左侧「缺行」、而且只在开发版出现，就是这条线索。
        复现/排除的工具留在 ``tools/jump_probe.py``：``LUMI_PROBE_NOWATERMARK=1``
        关掉水印再抓一张，一眼就能分清水印遮挡与真裁切。 */
    Rin.Shadow {
        source: card
        style: "flyout"
        radius: 18
        verticalOffset: 6
    }

    Rectangle {
        id: card
        objectName: "pageJumpCard"

        x: root.cardX + (1 - root.reveal) * root.enterDx
        y: root.cardY + (1 - root.reveal) * root.enterDy
        width: root.cardWidth
        height: root.cardHeight
        radius: Lumi.dockJumpRadius
        // 实底 92%（与笔选单同档）：页码要看得清，透出放映画面会糊
        color: Lumi.dockJumpBg
        border.width: 1
        border.color: Lumi.dockJumpBorder

        /*! 描边色经 ``border`` 分组属性拿不到（PySide 侧没有 ``QQuickPen*`` 的
            转换器），复制一份给自检读。 */
        readonly property color surfaceBorderColor: border.color
        readonly property real effectiveRadius: radius
    }

    /*! 吞掉落在卡片范围内的点击 —— 不吞的话会穿到底下的舞台（放映画面）上，
        用户点在自己的面板上却给幻灯片画了一笔。 */
    MouseArea {
        anchors.fill: card
        acceptedButtons: Qt.AllButtons
    }

    // ================================================================ 页码网格
    Flickable {
        id: flick
        objectName: "pageJumpFlickable"

        x: card.x + root.padding
        y: card.y + root.padding
        width: root.viewportWidth
        height: root.viewportHeight
        contentWidth: root.gridWidth
        contentHeight: root.gridHeight
        // 只纵向滚：横向由列数适配保证一定装得下（见 ``effColumns``）
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds
        // 触屏上「甩」的惯性稍微收一点 —— 格子是按钮，甩过头反而要点两下
        maximumFlickVelocity: 1600
        clip: true

        Grid {
            id: grid
            objectName: "pageJumpGrid"
            columns: root.effColumns
            width: root.gridWidth
            rowSpacing: root.cellSpacing
            columnSpacing: root.cellSpacing

            Repeater {
                model: root.total

                delegate: Rin.Clip {
                    id: cell
                    // 名字带页码：同一个 delegate 会建 N 份，光叫 "pageJumpCell"
                    // 的话按名字找只会命中**先声明的**那一份（量到的是别人）
                    objectName: "pageJumpCell_" + (index + 1)

                    readonly property int pageNumber: index + 1
                    readonly property bool pageCurrent: root.current === pageNumber
                    /*! 自检读的镜像：``Rin.Clip`` 的底色经 ``background`` 拿不到。 */
                    readonly property color surfaceFill: surface.color
                    readonly property color labelColor: label.color

                    width: root.cellSize
                    height: root.cellSize
                    radius: Lumi.dockJumpCellRadius
                    // 格子自己画（下面那块 Rectangle），按钮底层留空
                    color: "transparent"
                    padding: 0
                    hoverEnabled: true
                    onClicked: root.pagePicked(pageNumber)

                    // 按下缩一点（不做位移：跳页控件要「稳」，动了反而像滑走了）
                    scale: cell.down ? Lumi.dockJumpCellPressedScale : 1.0
                    Behavior on scale {
                        NumberAnimation {
                            duration: Lumi.dockJumpFadeDuration
                            easing.type: Easing.OutQuint
                        }
                    }

                    /*! 格子底板。三态：当前页（accent 实底）> hover > 常态。
                        当前页优先 —— 鼠标划过的正是当前页时不该把它变成 hover 色。 */
                    Rectangle {
                        id: surface
                        objectName: "pageJumpCellSurface"
                        anchors.fill: parent
                        radius: parent.radius
                        color: cell.pageCurrent ? Lumi.dockJumpCurrentFill
                            : cell.hovered ? Lumi.dockJumpCellHover
                            : Lumi.dockJumpCellFill
                        Behavior on color {
                            ColorAnimation {
                                duration: Lumi.dockJumpFadeDuration
                                easing.type: Easing.OutQuint
                            }
                        }
                    }

                    Rin.Text {
                        id: label
                        objectName: "pageJumpCellLabel"
                        anchors.centerIn: parent
                        text: cell.pageNumber
                        typography: Rin.Typography.Body
                        // 当前页用反色（深色档白 / 浅色档黑），别写死白：
                        // 浅色主题的 accent 是亮蓝，白字压上去读不出来
                        color: cell.pageCurrent ? Lumi.dockJumpCurrentText : Lumi.textSecondary
                    }
                }
            }
        }
    }

    // ================================================================ 滚动条
    /*! 自绘（不用 ScrollViewer，项目明确不用它）：内容超出视口才出现，
        拖动手势只给网格留 —— 这条纯指示、不接鼠标。 */
    Rectangle {
        objectName: "pageJumpScrollThumb"
        visible: root.scrollable && root.reveal > 0.5
        x: card.x + card.width - root.padding / 2 - width / 2
        width: 3
        radius: width / 2
        color: Lumi.dockJumpScrollThumb
        height: Math.max(24, root.viewportHeight * root.viewportHeight / Math.max(root.gridHeight, 1))
        y: card.y + root.padding
            + (root.viewportHeight - height) * (flick.contentY / Math.max(root.gridHeight - root.viewportHeight, 1))
    }

    /*! 当前页那一格的引用（调用方 / 自检用；找不到时为 null）。 */
    readonly property Item currentCell: {
        if (!opened || total <= 0 || current < 1 || current > total) {
            return null
        }
        var cells = grid.children
        for (var i = 0; i < cells.length; i++) {
            var item = cells[i]
            if (item && item.pageNumber === current) {
                return item
            }
        }
        return null
    }

    /*! 内容装得下时永远贴回顶端。

        ⚠️ 这不是多余的：``centerOnCurrent`` 在**开门那一刻**跑，而那一帧的几何
        可能还没稳定（``maxHeight`` 刚拿到窗口尺寸、卡片高度刚重算），于是会按
        「可滚动」算出一个 ``contentY`` 存进去。之后几何稳了、``scrollable``
        变 false，**那个 ``contentY`` 不会自己回来** —— ``StopAtBounds`` 只管
        手势与惯性，程序性赋值不钳（症状：内容装得下却整体上移、首行被切）。
        所以几何一稳就显式归零。 */
    function settleScroll() {
        if (!scrollable) {
            flick.contentY = 0
        }
    }

    onViewportHeightChanged: Qt.callLater(settleScroll)
    onGridHeightChanged: Qt.callLater(settleScroll)

    // 页码在面板开着的时候被翻页键 / 遥控器改掉 → 跟着把那一行滚回正中
    onCurrentChanged: {
        if (opened) {
            Qt.callLater(centerOnCurrent)
        }
    }
    // 页数变了（换了一份演示 / 读到新页码）→ 布局变了，重新定位
    onTotalChanged: {
        if (opened) {
            Qt.callLater(centerOnCurrent)
        }
    }
}
