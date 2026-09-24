import QtQuick
import RinUI as Rin
import Luminalium

/*!
    悬浮底板（Design: "Flyout Base"）。

    一整块大圆角表面 + ``Rin.Shadow`` 的 flyout 投影，内容以 ``Flow``
    从左到右一行排布（控制条**恒横向**）::

        FlyoutSurface {
            IconButton { ... }
        }

    投影必须画在窗口内，否则会被窗口边界裁掉 —— 因此窗口尺寸里要留出
    ``shadowMargin`` 的余量（``implicit*`` 已经把余量算进去了）。
    Python 侧按窗口尺寸贴角，所以配置里的 ``margin_x`` / ``margin_y``
    应该相应地减小，二者相加才是**视觉上**距屏幕边缘的距离。

    参考稿实测：沿轴向内边距（50/187）明显大于横向内边距（33/187），
    所以 ``paddingX`` / ``paddingY`` 是两个独立参数，不做统一 padding。
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

    default property alias contentData: inner.data

    readonly property int margin: shadowEnabled ? shadowMargin : 0

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
        radius: root.surfaceRadius
        // 透明度揉进颜色而不是 opacity，避免把投影也一起淡掉
        color: Lumi.fade(Lumi.surfaceBg, root.surfaceOpacity)
        border.width: 1
        border.color: Lumi.surfaceBorder
    }

    Flow {
        id: inner
        x: surface.x + root.paddingX
        y: surface.y + root.paddingY
        flow: Flow.LeftToRight
    }
}
