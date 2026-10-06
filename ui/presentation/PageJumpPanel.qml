import QtQuick
import RinUI as Rin
import Luminalium

/*!
    页码快速跳转面板 —— **点控制条上的页码**展开的一整条侧栏，点哪一张跳哪一页。

    ## 形态：照搬 Luminalium 1 的 ``#page-selector``

    L1 的 ``ppt_assistant/ui/overlay.html`` 里，翻页 pill 中间那块
    ``.page-info-container`` 是可以点的：点下去从**屏幕侧边**滑出一整条侧栏
    （``#page-selector``），里面是**一列 16:9 的幻灯片缩略图**，每张右下角压着
    大号页码，当前页描一圈 accent；点缩略图就 ``bridge.gotoSlide``。
    那个交互解决的是「几十页的演示翻到第 7 页要点七下」这件事。

    ⚠️ **2026-10-06 返工记录（改这块前必读）**：本组件第一版做成了
    「5 列页码网格 + 贴着控制条浮在旁边 + Fluent flyout 令牌」。自检全绿、
    结构也没错，但用户看了预览图只说了一句「不像」—— 因为 L1 的形态是
    **一整条贴屏幕边的侧栏**：260 宽、上下各留 24 铺满整高、单列 16:9 卡片、
    卡间距 16、当前页 2px accent 描边、页码压在卡片右下角、从屏幕外滑入。
    现在这一版就是照那份规格重做的。**别再往「密实的方格」方向收。**

    ## 形态照 L1，设计语言走 Fluent

    上面那张表是**形态**的逐条对照（宽度 / 贴边 / 铺满整高 / 单列 16:9 / 卡间距 /
    进场）。**外观**那一层是 Fluent 化的 —— 用户在认可形态之后明确要求
    「Fluent 化改造」，所以下面这些刻意偏离 L1，每条都有依据（都写在
    ``Lumi.qml`` 对应令牌的注释里）：

    * **圆角**：面板用项目的 ``flyoutRadius``（12，笔选单同款）而不是 L1 的 16 ——
      Fluent 没有 16 这一档，贴边浮出层在项目里一律 12；卡片留 8，与笔选单色板
      卡片同档。
    * **底色**：Fluent ``SolidBackgroundFillColorBase``（深 #202020 / 浅 #F3F3F3），
      而 L1 那个 ``--overlay-popup-bg`` 恰好也是 #202020 —— 对齐了，只是这回取的是
      主题里有名有姓的那一档。
    * **描边**：RinUI 的**表面**描边（``windowBorderColor``）。``hairline`` 是
      ``dividerBorderColor``，Fluent 里那是分隔线；面板是独立表面，绕着一整块面
      走的那圈线对应 ControlStroke。
    * **卡片三态**：常态 ``controlFillColor`` / hover 8% / 按下 15%（后两档直接
      复用控制条按钮的 ``dockButtonHoverFill`` / ``dockButtonActiveFill``）。
      L1 只有 hover，且是「放大 + 投影」。
    * **hover 不再缩放**：L1 的 ``scale(1.02)`` 是 Web CSS 的做法，Fluent 走状态层。
      缩放挪到**按下**（0.96），与 ``PenPaletteCard`` 的色板格子同款。
    * **当前页**：2px accent 描边留着（L1 的做法，也是项目里笔选单选中的做法），
      Fluent 化补的是一层**淡底**（AccentFill Subtle）—— 描边管「定位到哪一页」，
      淡底管「它在这儿」。
    * **页码字重**：SemiBold（600）而不是 Bold（700）—— Fluent 字阶里
      Display / Title 都是 SemiBold，32px 的粗体压在图上已经够重。
    * **滚动条**：Fluent 细滚动条（常态 2px、悬停加粗到 6px、中性色），宽度取
      主题的 ``scrollBarMinWidth`` / ``scrollBarWidth``；L1 是 3px 固定 accent。
    * **仍然不挂投影**。贴边的大表面在 Fluent 里靠描边分层，不靠投影（L1 也是
      ``box-shadow: none``）。真要加的话走 ``Rin.Shadow { style: "flyout" }``，
      但那要先恢复投影余量（卡片内缩 + 摆位各扣一次），别顺手就加。

    ## 与 L1 有两处**故意**不同（形态层面）

    1. **高度不再无脑铺满**。L1 是 ``top: 24; bottom: 24``，只有 3 页的演示也是
       一整条空侧栏。这里取 ``min(内容高 + 内边距, 满高)`` —— 页数够多时**与 L1
       逐像素一致**（40 页的演示必定铺满），页数很少时收成一块，不摆一条空壳。
    2. **内容从「缩略图」补上了**（第一版缺的就是这个）。缩略图由 Python 侧
       ``app/slide_thumbs.py`` 通过 COM ``Slides(i).Export`` 逐页导出（L1 同款），
       打开面板先要当前页 ±5，其余 500ms 一格在后台补齐。缩略图**在 Python 侧
       就烤好圆角 alpha**（``dockJumpItemRadius``），所以这里不必给每张图挂
       ``OpacityMask`` —— 41 张图就是 41 个离屏 FBO，代价太大。
       图还没到时卡片是空的、只有页码（这正是 L1 加载中的样子，不是坏掉）。

    ## 进场：整块从窗口外滑进来

    L1 的进场是 ``transform: translateX(±(100% + 32px))`` —— 面板整体在**屏幕外**
    起步，完全滑进来。所以本组件的 ``implicitWidth`` 是**滑行路径的并集**
    （``cardWidth + enterDistance``），终点位置在 Item 内部偏移；这样调用方只把
    Item 摆到位的口径不用变，而区域塑形一次就把整条路径盖住（路径超出窗口的部分
    被 ``SetWindowRgn`` 自然裁掉）。

    ## 与「区域塑形」的关系

    顶层窗口被 ``SetWindowRgn`` 裁成「只有控制条几块」，**区域外既不绘制也不参与
    命中**。本面板浮在控制条包围盒**之外**，所以：

    * 调用方必须把它算进 ``interactiveRect``（``PresentationDock`` / ``SidePager``
      里各有一段），否则点卡片会穿透到 PowerPoint，变成在幻灯片上乱画一笔；
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
    * ``cardWidth`` / ``cardHeight`` / ``cardX`` / ``cardY``：卡片本体（含滑动
      路径的并集口径见 ``implicitWidth``）的几何；
    * ``itemWidth`` / ``itemHeight`` / ``contentHeight`` / ``viewportHeight``：
      卡片列表的度量（自检按它算「第 n 张卡在不在视口里」）；
    * ``currentCard``：当前页那一张卡的 Item 引用（找不到时为 null）—— 「高亮有
      没有落在对的那张卡上」直接查它，不用遍历；
    * ``readyCount``：已经拿到缩略图的张数（Python 侧喂过来的 ``thumbs``），
      「图有没有真的下来」查它。
*/
Item {
    id: root

    // ------------------------------------------------------------ 数据（调用方给）
    /*! 总页数（``Backend.slideTotal``）。0 = 没在放映 / 还没读到页码 —— 此时
        面板空着，调用方也不该放它出来。 */
    property int total: 0
    /*! 当前页，**1-based**（``Backend.slideIndex``，与页码显示同一个口径）。 */
    property int current: 0
    /*! 每页的缩略图 URL（``Backend.thumbUrls``，**索引 = 页码 - 1**）。
        空串 = 还没导出好 —— 卡片就显示空底 + 页码（L1 加载中的样子）。
        后端给的是 ``file:///…`` 本地临时文件（见 ``app/slide_thumbs.py``）。 */
    readonly property var thumbs: Backend.thumbUrls

    // ------------------------------------------------------------ 空间约束
    /*! 面板**整个滑行路径**能用多大（**设计单位**，= 屏幕逻辑像素 / ``scaleFactor``）。
        调用方按「窗口尺寸减去上下左右该留的边」算好传进来。传 0 = 不限制。 */
    property real maxWidth: 0
    property real maxHeight: 0

    /*! 面板贴**窗口**哪一条边 —— ``left`` / ``right``。L1 是「点在屏幕左半边
        就往左边缘靠」，L2 里直接由「点的是哪一侧的翻页条」决定。 */
    property string side: "left"

    // ------------------------------------------------------------ 展开 / 收起
    /*! 展开开关（语义）。动画进度看 ``reveal``。 */
    property bool opened: false
    /*! 进出场是否走动画。默认开；关掉时 ``reveal`` 直接落到 0 / 1。

        ⚠️ 这个开关是给**离屏抓图工具**用的（``tools/preview.py`` 里置 false）：
        预览在屏幕外建窗口抓帧，``Behavior`` 的时间轴在那种环境下**推进不可靠**
        —— 同一份面板实测在可见窗口、离屏窗口、TopWindow 宿主里都能正常推到 1，
        唯独走完整预览流程时停在 0（组件逻辑没问题，是预览环境的问题，详见
        ``tools/jump_probe.py``）。抓图要的是**稳定终态**而不是动画中间态。 */
    property bool animate: true

    /*! 点了一张卡（页码 **1-based**）—— 交给调用方去驱动后端跳页。 */
    signal pagePicked(int page)

    // ------------------------------------------------------------ 缩略图预取
    /*! 展开时先要的页数半径 —— L1 ``requestThumbnailsForRange`` 的「当前页 ±5」。
        眼睛正盯着的那几张必须最快到位。 */
    readonly property int prefetchSpan: 5
    /*! 滚动时补要的半径 —— L1 ``onPageGridScroll`` 的「可见范围 ±3」。 */
    readonly property int scrollPrefetchSpan: 3
    /*! 鼠标在不在列表范围内 —— Fluent 细滚动条据此加粗（常态 2px → 6px）。 */
    property bool scrollHovered: false

    // ------------------------------------------------------------ 尺寸令牌
    readonly property int padding: Lumi.dockJumpPadding
    readonly property int spacing: Lumi.dockJumpItemSpacing
    readonly property int itemRadius: Lumi.dockJumpItemRadius

    /*! 面板宽度（L1 ``width: 260px``）。 */
    readonly property int cardWidth: Lumi.dockJumpWidth
    /*! 卡片宽 = 面板宽扣内边距；高按 **16:9** 算（L1 ``aspect-ratio: 16/9``）。
        ⚠️ 取整是为版式落到整数像素，比值 236:133 与 16:9 差 0.2%，图上看不出来。 */
    readonly property real itemWidth: Math.max(cardWidth - padding * 2, 1)
    readonly property real itemHeight: Math.max(Math.round(itemWidth * 9 / 16), 1)
    /*! 列表内容总高。 */
    readonly property real contentHeight: total > 0
        ? total * itemHeight + (total - 1) * spacing : 0
    /*! 面板可用高度（设计单位）。0 = 不限制。
        ⚠️ 下限是一张卡加内边距 —— 窗口矮到装不下一张卡时宁可让它顶出去，
        也不要把卡片压扁（压扁的 16:9 缩略图等于把「用画面找页」这件事废掉）。 */
    readonly property real maxCardHeight: maxHeight > 0
        ? Math.max(maxHeight, itemHeight + padding * 2) : Infinity
    /*! 面板高度：**装得下就收，装不下才铺满**（与 L1 的差别之一，见头注释）。 */
    readonly property real cardHeight: Math.min(
        Math.max(contentHeight + padding * 2, itemHeight + padding * 2), maxCardHeight)

    /*! 滚动视口 —— 它是滚动的**唯一**依据：``contentHeight > viewportHeight`` 才要滚。 */
    readonly property real viewportWidth: cardWidth - padding * 2
    readonly property real viewportHeight: cardHeight - padding * 2
    readonly property bool scrollable: contentHeight > viewportHeight + 0.5

    // ------------------------------------------------------------ 进场滑动
    /*! 滑行距离 = L1 的 ``translateX(calc(100% + 32px))``。 */
    readonly property int enterDistance: cardWidth + 32
    /*! 起点偏移：贴左边缘的面板从左边滑进来（负数），贴右边则相反。 */
    readonly property int enterDx: side === "left" ? -enterDistance : enterDistance
    /*! 卡片**终点**在本 Item 内的偏移 —— Item 是滑行路径的并集，终点要往内让。 */
    readonly property int dockedInset: enterDx > 0 ? 0 : enterDistance

    /*! Item 尺寸 = 滑行路径的并集（见头注释）。 */
    implicitWidth: cardWidth + enterDistance
    implicitHeight: cardHeight

    // 面板是纯绘制物，尺寸由 ``implicit*`` 自己说了算
    width: implicitWidth
    height: implicitHeight

    /*! 镜像给调用方 / 自检：卡片本体（终态）在 Item 内的几何。 */
    readonly property real cardX: dockedInset
    readonly property real cardY: 0

    // ------------------------------------------------------- 动画（L1 的曲线）
    /*! 展开进度 0..1。``opened`` 是语义开关，``reveal`` 是它的动画影子。 */
    property real reveal: 0
    onOpenedChanged: {
        reveal = opened ? 1 : 0
        if (opened) {
            // ⚠️ 必须等这一帧的几何都落地（``cardHeight`` / 视口高度都还要重算）
            //     再定位，否则读到的是上一帧的视口高，滚到的地方会偏。
            Qt.callLater(centerOnCurrent)
            // 展开的一瞬间就播下 ±5 的预取（L1 的 ``requestThumbnailsForRange``）
            prefetch(current - prefetchSpan, current + prefetchSpan)
        }
    }
    Behavior on reveal {
        // 关掉动画时 ``reveal`` 直接落地（离屏抓图用，见 ``animate``）
        enabled: root.animate
        NumberAnimation {
            // ⚠️ 展开与收起**同一个时长**（L1 只有一条 transition：.4s 来回都走
            //    它）。第一版给收起配了更短的时长，那不是 L1 的手感。
            duration: Lumi.dockJumpEnterDuration
            // L1 的 cubic-bezier(0.19, 1, 0.22, 1) 就是 OutExpo：起步极快、尾巴
            // 很长 —— 面板「啪」地滑到位再缓缓收尾。
            easing.type: Easing.OutExpo
        }
    }
    opacity: reveal
    /*! 收起动画期间还得画着（不然淡出没了），归零后才真正藏起来。 */
    visible: reveal > 0.001

    /*! 已经拿到缩略图的张数（自检用）。 */
    readonly property int readyCount: {        var list = root.thumbs
        if (!list || !list.length) {
            return 0
        }
        var n = 0
        for (var i = 0; i < Math.min(list.length, root.total); i++) {
            if (list[i]) {
                n++
            }
        }
        return n
    }

    /*! 第 ``page`` 页（1-based）的缩略图 URL；没就绪 / 越界时返回空串。 */
    function thumbFor(page) {
        var list = root.thumbs
        if (!list || page < 1 || page > list.length) {
            return ""
        }
        var url = list[page - 1]
        return url ? String(url) : ""
    }

    /*! 要 ``[from, to]``（1-based 闭区间）这几页的缩略图。

        后端在缓存没接上时（预览 / 自检宿主只造 ``Backend``）静默忽略，
        所以这里不用判断「有没有后端」；已经在队列里 / 已经拿到的也不会重复要
        （见 ``app/slide_thumbs.py``）。 */
    function prefetch(from, to) {
        if (total <= 0) {
            return
        }
        Backend.requestThumbnails(Math.max(1, from), Math.min(total, to))
    }

    /*! 视口里那几张 ± ``span`` —— 与 L1 ``onPageGridScroll`` 同一套算法。 */
    function prefetchVisible(span) {
        if (total <= 0 || viewportHeight <= 0) {
            return
        }
        var step = itemHeight + spacing
        var first = Math.floor(flick.contentY / step) + 1
        var last = Math.floor((flick.contentY + viewportHeight) / step) + 1
        prefetch(first - span, last + span)
    }

    /*! 把当前页那一张滚到视口**正中** —— 上下都能看到前后的邻居，
        用户一眼就知道自己在第几页附近。已经能看到时也照样居中对齐：
        点到第 7 页再来开面板，那一张立刻在正中，比「刚好露出来」好找。
        内容不够一屏（不可滚 / 居中位置越界）时会被 Flickable 自己钳住。 */
    function centerOnCurrent() {
        if (total <= 0 || !opened) {
            return
        }
        if (current < 1 || current > total || !scrollable) {
            flick.contentY = 0
            return
        }
        var step = itemHeight + spacing
        var want = (current - 1) * step - (viewportHeight - itemHeight) / 2
        var maxY = Math.max(0, contentHeight - viewportHeight)
        flick.contentY = Math.max(0, Math.min(maxY, want))
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
    onContentHeightChanged: Qt.callLater(settleScroll)

    // ================================================================ 面板本体
    /*! ⚠️ **不挂投影**（L1 ``box-shadow: none``）。第一版挂了 ``Rin.Shadow``
        （flyout 一档），那正是「不像」的一部分：L1 的面板是**贴边的一整条**，
        贴边的面不投自己的影子。 */
    Rectangle {
        id: card
        objectName: "pageJumpCard"

        x: root.dockedInset + (1 - root.reveal) * root.enterDx
        y: root.cardY
        width: root.cardWidth
        height: root.cardHeight
        radius: Lumi.dockJumpRadius
        // 实底（L1 深色档 #202020）：页码与缩略图都要看得清，透出放映画面会糊
        color: Lumi.dockJumpBg
        border.width: 1
        border.color: Lumi.dockJumpBorder

        /*! 描边色经 ``border`` 分组属性拿不到（PySide 侧没有 ``QQuickPen*`` 的
            转换器），复制一份给自检读。 */
        readonly property color surfaceBorderColor: border.color
        readonly property real effectiveRadius: radius
    }

    /*! 描边就是那一圈 1px 均匀线，**不加别的东西**。⚠️ 2026-10-06 曾照
        ``FlyoutSurface`` / ``PenPaletteCard`` 补了一道 CW2 渐变高光环，用户明确
        否掉：「不应该加高光的」—— 那两块有那道光，不代表所有浮出表面都得有；
        这面板贴边、面积大，加高光反而显脏。 */

    /*! 吞掉落在卡片范围内的点击 —— 不吞的话会穿到底下的舞台（放映画面）上，
        用户点在自己的面板上却给幻灯片画了一笔。 */
    MouseArea {
        anchors.fill: card
        acceptedButtons: Qt.AllButtons
    }

    // ================================================================ 缩略图列表
    /*! 滚动后延迟一下再播预取：``contentY`` 每帧都在变（甩动时一秒几十次），
        真按帧去投请求只是把同一个范围算几十遍。停手 150ms 之后再要。 */
    Timer {
        id: scrollPrefetch
        interval: 150
        onTriggered: root.prefetchVisible(root.scrollPrefetchSpan)
    }

    /*! 单列纵向列表（L1 ``.page-grid`` 是 flex column）。横向不滚 —— 卡片宽就是
        视口宽。 */
    Flickable {
        id: flick
        objectName: "pageJumpFlickable"

        x: card.x + root.padding
        y: card.y + root.padding
        width: root.viewportWidth
        height: root.viewportHeight
        contentWidth: root.itemWidth
        contentHeight: root.contentHeight
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds
        // 触屏上「甩」的惯性稍微收一点 —— 卡片是按钮，甩过头反而要点两下
        maximumFlickVelocity: 1600
        clip: true
        // 滚到哪就要到哪（L1 ``onPageGridScroll``）
        onContentYChanged: scrollPrefetch.restart()

        // ⚠️ 用 ``HoverHandler`` 而不是「盖一个 MouseArea」：后者为了不抢拖拽
        // 得把 ``acceptedButtons`` 设成 NoButton，很别扭；``HoverHandler`` 与
        // 鼠标 grabbing 无关，纯粹跟着光标走，正是这里要的东西。
        HoverHandler {
            onHoveredChanged: root.scrollHovered = hovered
        }

        Column {
            id: list
            objectName: "pageJumpList"
            width: root.itemWidth
            spacing: root.spacing

            Repeater {
                model: root.total

                delegate: Rin.Clip {
                    id: cell
                    // 名字带页码：同一个 delegate 会建 N 份，光叫 "pageJumpCell"
                    // 的话按名字找只会命中**先声明的**那一份（量到的是别人）
                    objectName: "pageJumpCell_" + (index + 1)

                    readonly property int pageNumber: index + 1
                    readonly property bool pageCurrent: root.current === pageNumber
                    /*! 缩略图就绪了没有 —— 「空卡片 + 页码」是 L1 的加载态本身。 */
                    readonly property string thumbUrl: root.thumbFor(pageNumber)
                    readonly property bool thumbReady: thumbUrl !== ""
                    /*! 自检读的镜像：``Rin.Clip`` 的底色经分组属性拿不到；描边在
                        ``ring`` 那层自绘的上面，镜像跟着它走。 */
                    readonly property color surfaceFill: cell.color
                    readonly property color frameBorder: ring.border.color

                    width: root.itemWidth
                    height: root.itemHeight
                    radius: root.itemRadius
                    // 卡片自己给出底色（``Rin.Clip`` 的 background 别换，那是基类
                    // 引用；走 color 这个别名）
                    //
                    // Fluent 的可点表面是**三态状态层**：常态 Subtle → hover 一档
                    // → 按下再一档。当前页优先（鼠标划过的正是当前页时，不该把它
                    // 变成 hover 色 —— 那样「我在第几页」这条唯一的锚点就丢了）。
                    color: cell.pageCurrent ? Lumi.dockJumpCurrentFill
                        : cell.down ? Lumi.dockJumpItemPressed
                        : cell.hovered ? Lumi.dockJumpItemHover
                        : Lumi.dockJumpItemFill
                    // ⚠️ **描边不在这里画**。L1 是 border-box 做法（2px
                    // transparent 占位 + 图往里让 2px），本项目改成下面那层自绘的
                    // ``ring`` 压在**图片之上**，图因此可以铺满整张卡。
                    //
                    //    为什么必须改：内缩 2px 之后，图自己的圆角得等于
                    //    「卡片圆角 − 内缩量」（8 − 2 = 6）才和卡片轮廓同心，而图是
                    //    按 8 烤的 —— 转角处于是出现一圈「双层边」，圆角看着对不上
                    //    （2026-10-06 用户报「圆角不太匹配」查出来的就是这个）。
                    //    铺满之后图的圆角就是卡片圆角本身：Python 侧烤的值不用动，
                    //    也就没有可错的地方。选中环压在内容上也是 WinUI 的做法。
                    border.width: 0
                    padding: 0
                    hoverEnabled: true
                    onClicked: root.pagePicked(pageNumber)

                    // ⚠️ 按下缩一点（**不是** hover 放大）。L1 的
                    // ``.page-item:hover { transform: scale(1.02) }`` 是 Web CSS
                    // 的做法，Fluent 控件的 hover 走状态层；项目里已有的同款是
                    // ``PenPaletteCard`` 的色板格子（``down ? 0.88 : 1``）。
                    scale: cell.down ? Lumi.dockJumpItemPressedScale : 1.0
                    Behavior on scale {
                        NumberAnimation {
                            duration: Lumi.dockJumpFadeDuration
                            easing.type: Easing.OutQuint
                        }
                    }

                    /*! 缩略图。**圆角已由 Python 侧烤进 PNG 的 alpha**（见头注释），
                        所以这里不需要任何蒙版 / 裁切 —— 41 张图挂 41 层
                        ``OpacityMask`` 是这块最贵的一种写法。 */
                    Image {
                        id: thumb
                        objectName: "pageJumpCellThumb"
                        // 铺满整张卡：圆角由 PNG 的 alpha 自己带（Python 侧烤的），
                        // 所以这里不需要内缩，也就不存在「内外圆角不同心」
                        anchors.fill: parent
                        source: cell.thumbUrl
                        // 裁切式填满：缩略图本身就是 16:9，与卡片同比例
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        // 没下到图时别画（空 source 会在某些平台画出警告框）
                        visible: cell.thumbReady
                        // 图未就绪时不参与命中（点卡片任意位置都算点它）
                        enabled: false
                    }

                    /*! 当前页的 2px accent 环 —— **画在图片之上**。

                        为什么不走 ``Rin.Clip`` 的 ``border``：Button 的 background
                        画在子项**之下**，环会被图片盖住；而 L1 为了让环可见采取
                        「2px transparent 占位 + 图内缩 2px」，那个内缩正是圆角对不
                        上的根源（见上面那段）。压在内容上是 WinUI 的做法
                        （``SelectionIndicator`` 同样压在 item 内容上）。

                        声明位置有讲究：夹在「图」与「页码」之间 —— 页码仍是最上层，
                        环压不到那两个字。 */
                    Rectangle {
                        id: ring
                        objectName: "pageJumpCellRing"
                        anchors.fill: parent
                        radius: root.itemRadius
                        color: "transparent"
                        border.width: Lumi.dockJumpCurrentBorderWidth
                        border.color: cell.pageCurrent
                            ? Lumi.dockJumpCurrentBorder : "transparent"
                    }

                    /*! 右下角的页码（L1 ``.page-num``：``bottom: 4px; right: 8px;
                        font-size: 2em; color: rgba(255,255,255,.9)``）。

                        ⚠️ L1 用的是 ``text-shadow``。QML 没有文字阴影，这里用
                        **同一串字错位 1px 再画一遍**代替（一层纯 Text，比给 41 张
                        图挂 ``DropShadow``/``layer.effect`` 便宜一个数量级）。
                        影子只在有缩略图时出现 —— 空底上压一层黑影反而脏。 */
                    Rin.Text {
                        objectName: "pageJumpCellNumberShadow"
                        visible: cell.thumbReady
                        x: numberLabel.x + 1
                        y: numberLabel.y + 1
                        text: numberLabel.text
                        font.pixelSize: Lumi.dockJumpNumberSize
                        font.weight: Lumi.dockJumpNumberWeight
                        color: "#000000"
                        opacity: Lumi.dockJumpNumberShadowOpacity
                    }

                    Rin.Text {
                        id: numberLabel
                        objectName: "pageJumpCellNumber"
                        // L1 的锚点是**卡片右下角**（不是缩略图右侧）
                        x: cell.width - width - 8
                        y: cell.height - height - 4
                        text: cell.pageNumber
                        font.pixelSize: Lumi.dockJumpNumberSize
                        font.weight: Lumi.dockJumpNumberWeight
                        color: Lumi.dockJumpNumberColor
                    }
                }
            }
        }
    }

    // ================================================================ 滚动条
    /*! 自绘（不用 ScrollViewer，项目明确不用它）：内容超出视口才出现，
        拖动手势只给列表留 —— 这条纯指示、不接鼠标。

        Fluent 的**细滚动条**行为：常态 2px、鼠标进到面板里加粗到 6px、颜色中性。
        L1 是「3px 固定 + accent 色」，那是它自己 CSS 变量的选择 —— WinUI 的
        ScrollBar 常态本来就不是强调色。宽度取主题的 ``scrollBarMinWidth`` /
        ``scrollBarWidth``（见 ``Lumi.dockJumpScrollWidth*``）。 */
    Rectangle {
        objectName: "pageJumpScrollThumb"
        visible: root.scrollable && root.reveal > 0.5
        // 加粗时整条往右挪半个差值，**中心线不动** —— 否则「加粗」看起来像「歪了」。
        // 中心线贴在**内容**右缘外 ``dockJumpScrollInset``（不是面板内边距的一半：
        // 那会让它悬在面板与卡片之间两边不靠）。
        x: card.x + card.width - Lumi.dockJumpScrollInset - width / 2
        width: root.scrollHovered ? Lumi.dockJumpScrollWidthHover
                                  : Lumi.dockJumpScrollWidth
        radius: width / 2
        color: root.scrollHovered ? Lumi.dockJumpScrollThumbHover
                                  : Lumi.dockJumpScrollThumb
        height: Math.max(28, root.viewportHeight * root.viewportHeight
                             / Math.max(root.contentHeight, 1))
        y: card.y + root.padding
            + (root.viewportHeight - height)
              * (flick.contentY / Math.max(root.contentHeight - root.viewportHeight, 1))

        Behavior on width {
            NumberAnimation {
                duration: Lumi.dockJumpFadeDuration
                easing.type: Easing.OutQuint
            }
        }
        Behavior on color {
            ColorAnimation {
                duration: Lumi.dockJumpFadeDuration
                easing.type: Easing.OutQuint
            }
        }
    }

    /*! 当前页那一张卡的引用（调用方 / 自检用；找不到时为 null）。 */
    readonly property Item currentCard: {
        if (!opened || total <= 0 || current < 1 || current > total) {
            return null
        }
        var cells = list.children
        for (var i = 0; i < cells.length; i++) {
            var item = cells[i]
            if (item && item.pageNumber === current) {
                return item
            }
        }
        return null
    }

    // 页码在面板开着的时候被翻页键 / 遥控器改掉 → 跟着把那一张滚回正中，
    // 并把新位置的 ±5 播下去（用户正在这一段里走）
    onCurrentChanged: {
        if (opened) {
            Qt.callLater(centerOnCurrent)
            prefetch(current - prefetchSpan, current + prefetchSpan)
        }
    }
    // 页数变了（换了一份演示 / 读到新页码）→ 布局变了，重新定位
    onTotalChanged: {
        if (opened) {
            Qt.callLater(centerOnCurrent)
        }
    }
}
