import QtQuick
import Qt5Compat.GraphicalEffects
import RinUI as Rin
import Luminalium

/*!
    悬浮底板（Design: "Flyout Base"，形态取自 Luminalium 1 的 ``#toolbar``）。

    一整块**全圆胶囊** + ``Rin.Shadow`` 的 flyout 投影，内容以 ``Flow``
    从左到右一行排布（控制条**恒横向**）::

        FlyoutSurface {
            IconButton { ... }
        }

    L1 的底板是 ``border-radius: 999px``（胶囊），本组件照做：
    ``surfaceRadius`` 缺省 999，实际半径用 ``Math.min(值, 高/2)`` 钳制，
    所以改条高不会失形（54 高 → 27 半径）。

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
        // 胶囊：请求值超过 高/2 就按 高/2 收（Qt 的 Rectangle 不会自己钳）
        radius: Math.min(root.surfaceRadius, Math.round(surface.height / 2))
        // 透明度揉进颜色而不是 opacity，避免把投影也一起淡掉
        color: Lumi.fade(Lumi.surfaceBg, root.surfaceOpacity)
        border.width: 1
        border.color: Lumi.surfaceBorder
    }

    // ==================================== CW2 同款渐变边框高光
    // 对角线渐变填充 + 「只有描边的形状」蒙版 → 圆环。结构与 CW2
    // Widget.qml 的「渐变边框」段一致：内层矩形开 layer 走 LinearGradient，
    // 外层 Item 开 layer 用 OpacityMask 裁掉内部。
    // 注意 maskSource 的矩形**不要设填充**（透明填充 + 不透明描边 =
    // 只保留描边像素；描边色无所谓，蒙版只看 alpha）。
    Item {
        id: highlight
        visible: root.highlightEnabled
        x: surface.x
        y: surface.y
        width: surface.width
        height: surface.height

        Rectangle {
            anchors.fill: parent
            radius: surface.radius
            layer.enabled: true
            layer.effect: LinearGradient {
                start: Qt.point(0, 0)
                end: Qt.point(highlight.width, highlight.height)
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Lumi.dockHighlightColor }
                    GradientStop { position: 0.5; color: "transparent" }
                    GradientStop { position: 0.6; color: "transparent" }
                    GradientStop { position: 1.0; color: Lumi.dockHighlightColor }
                }
            }
        }

        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: highlight.width
                height: highlight.height
                radius: surface.radius
                color: "transparent"
                border.width: root.highlightWidth
            }
        }
    }

    Flow {
        id: inner
        x: surface.x + root.paddingX
        y: surface.y + root.paddingY
        flow: Flow.LeftToRight
    }
}
