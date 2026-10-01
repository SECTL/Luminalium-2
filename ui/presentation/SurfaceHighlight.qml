import QtQuick
import Qt5Compat.GraphicalEffects
import RinUI as Rin
import Luminalium

/*!
    CW2 小组件同款的**渐变边框高光** —— ``FlyoutSurface`` 与 ``PenPaletteCard``
    共用的「玻璃边缘反光」。

    三层结构（出处：Class Widgets 2 ``Theme/components/Widget.qml``，见
    ``FlyoutSurface`` 的头注释）：

        LinearGradient（对角渐变：起点亮、中段全透、终点又亮）
          → OpacityMask 用「只有描边的形状」做蒙版，裁出 ``highlightWidth`` 的环
            → GaussianBlur 把硬边环溶成外扩的柔光晕

    用法：与被描边的表面（``source``）放在**同一个父级**里 —— 本组件的几何
    直接读 ``source`` 的 x/y/width/height/radius，并按 ``blur`` 自动外扩
    ``2×blur`` 的透明边界（不留边界的话外侧光晕会被图层切平成硬边）。

    ⚠️ ``source`` 必须是**同级**的 Item：跨父级取 x/y 会拿到错的坐标系。
    ⚠️ 本组件**不裁剪、不拦截事件**，纯绘制层；声明在表面**之后**（画在
    表面上面），但会在内容之下 —— 放映条的内容都摆在高光之后声明的层里。
*/
Item {
    id: root

    /*! 被描边的表面（同级 Item，读它的 x / y / width / height / radius）。 */
    property Item source: null
    /*! 环的厚度。CW2 原档 1.5px（组件 100px 高）；本项目放大档见 Lumi 注释。 */
    property real highlightWidth: Lumi.dockHighlightWidth
    /*! 环色 —— CW2 的描边色深浅主题都用白（本质上是一道「光泽」），不跟主题。 */
    property color highlightColor: Lumi.dockHighlightColor
    /*! 高斯模糊半径。0 = 关（退回 CW2 原档的硬描边环）。 */
    property real blur: Lumi.dockHighlightBlur

    /*! 环是否真的在画（自检读这个）。 */
    readonly property bool ringVisible: visible && source !== null

    /*! 模糊需要四周留透明边界，否则外侧的光晕会被图层边界切平成硬边。
        取 2×半径，仍在宿主预留的投影余量之内。 */
    readonly property real blurPad: blur > 0 ? Math.ceil(blur * 2) : 0

    x: source !== null ? source.x - blurPad : 0
    y: source !== null ? source.y - blurPad : 0
    width: source !== null ? source.width + blurPad * 2 : 0
    height: source !== null ? source.height + blurPad * 2 : 0

    /*! 环本体：与 ``source`` 同尺寸、同圆角、同心（模糊只负责柔化，
        不改变光的落点，所以渐变方向也按它算）。 */
    Item {
        id: highlightRing
        anchors.centerIn: parent
        width: root.source !== null ? root.source.width : 0
        height: root.source !== null ? root.source.height : 0

        Rectangle {
            anchors.fill: parent
            radius: root.source !== null ? root.source.radius : 0
            layer.enabled: true
            layer.effect: LinearGradient {
                start: Qt.point(0, 0)
                end: Qt.point(highlightRing.width, highlightRing.height)
                gradient: Gradient {
                    GradientStop { position: 0.0; color: root.highlightColor }
                    GradientStop { position: 0.5; color: "transparent" }
                    GradientStop { position: 0.6; color: "transparent" }
                    GradientStop { position: 1.0; color: root.highlightColor }
                }
            }
        }

        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: highlightRing.width
                height: highlightRing.height
                radius: root.source !== null ? root.source.radius : 0
                color: "transparent"
                border.width: root.highlightWidth
            }
        }
    }

    layer.enabled: root.blur > 0
    layer.effect: GaussianBlur {
        radius: root.blur
        // samples 越大越接近真高斯；radius 必须 ≤ samples/2
        samples: Math.ceil(root.blur * 2) + 1
        transparentBorder: true
    }
}
