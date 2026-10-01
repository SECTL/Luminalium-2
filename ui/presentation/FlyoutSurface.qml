import QtQuick
import RinUI as Rin
import Luminalium

/*!
    悬浮底板（Design: "Flyout Base"，形态取自 Luminalium 1 的 ``#toolbar``）。

    一整块**全圆胶囊** + ``Rin.Shadow`` 的 flyout 投影，内容以 ``Flow``
    从左到右一行排布（横条）或从上到下一列排布（``vertical: true``，
    竖版两侧翻页用）::

        FlyoutSurface {
            IconButton { ... }
        }

    L1 的底板是 ``border-radius: 999px``（胶囊），本组件照做：
    ``surfaceRadius`` 缺省 999，实际半径用 ``Math.min(值, 短边/2)`` 钳制，
    横条按高钳、竖条按宽钳，所以改尺寸不会失形（54 高 → 27 半径）。

    投影必须画在窗口内，否则会被窗口边界裁掉 —— 因此窗口尺寸里要留出
    ``shadowMargin`` 的余量（``implicit*`` 已经把余量算进去了）。
    ``margin_x`` / ``margin_y`` 是**视觉距离**（屏幕上量到的底板到屏幕边缘），
    Python 侧贴角时会自动扣掉这份余量，所以不必手工换算；
    ``margin`` 小于 ``shadowMargin`` 时多出来的只是阴影尾部被屏幕边缘裁掉。

    ``paddingX`` / ``paddingY`` 是两个独立参数，不做统一 padding：
    L1 的 ``#toolbar`` 是 ``padding: 8px 8px 8px 12px``（上下 8、左右 12），
    而翻页 ``.flipper`` 的圆钮只距 pill 边缘 4px —— 两档差别很大，
    所以调用方（``PresentationDock``）会按是否「只剩翻页一块」分别给值。

    **渐变边框高光（CW2 小组件同款）**：Class Widgets 2 的
    ``Theme/components/Widget.qml`` 用一个对角线渐变（起点亮、中段全透明、
    终点又亮）裁出 ``borderWidth`` 的描边环当「光影」（lighting effect）。
    画法照抄 CW2：``Qt5Compat.GraphicalEffects`` 的 ``LinearGradient``
    渐变填充 → ``OpacityMask`` 用「只有描边的形状」做蒙版裁出圆环。
    （Qt 的 ``Gradient.Custom`` 任意方向渐变在本机 Qt 里不可用，别试图换。）

    2026-09-30 加了一层 ``GaussianBlur``（``highlightBlur``，默认 3）：只做
    ``LinearGradient`` + ``OpacityMask`` 出来的是一道**像素级硬边描边**，贴在
    胶囊廓形上「边界感」很重，像加了个框。模糊把这条线摊成向外扩散的柔光，
    才是「玻璃边缘的反光」而不是「描边」。代价是峰值亮度会掉，所以
    ``dockHighlightColor`` 的 alpha 同步从 0.55 降到 0.40 只是「削弱一点」，
    别按纯 alpha 换算。

    ⚠️ 模糊必须留透明边界（``blurPad``）：图层尺寸若与光晕等大，外侧的光会被
    图层边界切平，又变回硬边。所以高光 Item 比 ``surface`` 四周各外扩
    ``2×blur``，圆环本体（``highlightRing``）仍然与 ``surface`` 重合。
    外扩量远小于窗口预留的 ``shadowMargin``（24），不会顶到窗口边界。
*/
Item {
    id: root

    property int paddingX: Lumi.dockPaddingX
    property int paddingY: Lumi.dockPaddingY
    property real surfaceRadius: Lumi.dockSurfaceRadius
    property real surfaceOpacity: Lumi.dockSurfaceOpacity
    property bool shadowEnabled: true
    property int shadowMargin: Lumi.dockShadowMargin
    property real shadowBlur: 18
    property real shadowOffsetY: 6
    /*! CW2 同款渐变边框高光（工具栏 / 翻页 pill 都开）。 */
    property bool highlightEnabled: true
    /*! 高光环的柔化模糊半径（0 = 退回硬描边环）。 */
    property real highlightBlur: Lumi.dockHighlightBlur
    /*! 竖排模式：内容自上而下排（横条默认自左而右）。竖版两侧翻页用 ——
        底板 / 投影 / 渐变高光的画法两种方向完全共用，只有内容流向不同。 */
    property bool vertical: false
    /*! 表面级内容间距。横向 dock 的各区块自管间距（分段 / 分隔线自带留白），
        保持 Qt Flow 默认 5 不动；竖版翻页传 8（= 横版 pager.spacing）。 */
    property real contentSpacing: 5
    readonly property real highlightWidth: Lumi.dockHighlightWidth

    default property alias contentData: inner.data

    readonly property int margin: shadowEnabled ? shadowMargin : 0
    /*! 钳制后的**实际**圆角（胶囊时为 高/2）。自检会读这个值。 */
    readonly property real effectiveRadius: surface.radius
    /*! 高光环是否真的在画（自检用）。 */
    readonly property bool highlightRingVisible: highlight.visible

    implicitWidth: surface.width + margin * 2
    implicitHeight: surface.height + margin * 2

    // 投影必须先于底板声明，否则会盖在底板上面
    Rin.Shadow {
        source: surface
        style: "flyout"
        radius: root.shadowBlur
        verticalOffset: root.shadowOffsetY
        visible: root.shadowEnabled
    }

    Rectangle {
        id: surface
        x: root.margin
        y: root.margin
        width: inner.implicitWidth + root.paddingX * 2
        height: inner.implicitHeight + root.paddingY * 2
        // 胶囊：请求值超过 短边/2 就按 短边/2 收（Qt 的 Rectangle 不会自己钳）。
        // 横条短边是高、竖条短边是宽 —— 用 min(w,h) 两种方向都对。
        radius: Math.min(root.surfaceRadius, Math.round(Math.min(surface.width, surface.height) / 2))
        // 透明度揉进颜色而不是 opacity，避免把投影也一起淡掉
        color: Lumi.fade(Lumi.surfaceBg, root.surfaceOpacity)
        border.width: 1
        border.color: Lumi.surfaceBorder
    }

    // ==================================== CW2 同款渐变边框高光
    // 三层结构已抽到 ``SurfaceHighlight.qml``（笔选单卡片同一道光 —— 两块
    // 浮出层必须像一家人）。这里只传参；环的可见性照旧由 ``highlightEnabled``
    // 说了算（``highlightRingVisible`` 属性转发给自检）。
    SurfaceHighlight {
        id: highlight
        source: surface
        visible: root.highlightEnabled
        highlightWidth: root.highlightWidth
        blur: root.highlightBlur
    }

    Flow {
        id: inner
        x: surface.x + root.paddingX
        y: surface.y + root.paddingY
        spacing: root.contentSpacing
        flow: root.vertical ? Flow.TopToBottom : Flow.LeftToRight
    }
}
