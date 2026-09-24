import QtQuick
import RinUI as Rin
import Luminalium

/*!
    分段控件的单页（笔 / 橡皮）。

    基类是 ``Rin.SegmentedItem``（= ``TabButton``），选中状态、组内互斥、
    键盘导航全部由它提供。

    **选中底板直接用基类自带的**：基类 background 在 ``checked`` 时是
    ``controlFillColor``（白 6%）的整块圆角底 —— 与参考稿实测的选中板
    （#373737，即白 6% 叠在容器上）**完全同色**，所以不必也不该自绘。
    参考稿里选中板左右各内缩约 9% 项宽，这个内缩改由容器
    （``ToolSegment``）的 ``leftPadding/rightPadding`` 提供 ——
    因为容器高度 = 内容高时（实测两者相等），只用水平 padding 即可
    得到「板内缩、容器满高」的效果。

    ⛔ **绝不能重写 ``background``**：``SegmentedItem`` 基类的 ``states`` 里有
    ``PropertyChanges { target: background; scale: 0.95 }``，``PropertyChanges``
    在构造期就解析 target；``background`` 一旦被替换，旧对象不存在 → 构造期
    直接抛 ``TypeError: Cannot read property 'width' of null``，窗口都建不起来。

    这里只重写 ``contentItem``，做两件事：

    1. **图标** —— 基类用 ``IconWidget`` 且**不设颜色**；``Rin.Icon`` 的 color
       直接 alias 到内部 Text，而 Text 默认色是**黑**，深色主题下完全不可见。
       另外 ``IconWidget`` 只设 ``width/height`` 不设 ``size``，字形大小根本
       改不动。所以换成自定义 ``Rin.Icon`` 并显式给 ``size`` + ``color``。
    2. **下划线** —— 基类的 ``Indicator`` 用的是 ``Utils.primaryColor``
       （默认 ``#605ed2`` 经 lighter/darker 后是**紫色**，不是设计稿的蓝）。
       这里按应用令牌重画：宽度取图标宽度、紧贴容器底部（实测 62/187 与 11/187）。

    重写 ``contentItem`` 必须同时重写 ``implicitWidth`` / ``implicitHeight`` ——
    基类这两个绑定引用的是默认 contentItem 里的 ``row``。
*/
Rin.SegmentedItem {
    id: root

    property int glyphSize: Lumi.dockIconSize
    property color glyphColor: Lumi.textPrimary
    property string tooltip: ""
    property int itemHeight: Lumi.dockHitSize
    // 正方形：项里只有一枚图标，宽 = 高。要宽项由调用方显式给 itemWidth
    property int itemWidth: itemHeight
    property int indicatorWidth: Lumi.dockIconSize
    property int indicatorHeight: 3
    property int indicatorMargin: 2

    implicitWidth: itemWidth
    implicitHeight: itemHeight
    width: itemWidth
    height: itemHeight
    // 内容区铺满整项：参考稿的图标在容器里是垂直居中的
    padding: 0

    contentItem: Item {
        // ---- 图标 ----
        Rin.Icon {
            anchors.centerIn: parent
            icon: root.icon.name
            size: root.glyphSize
            color: root.glyphColor
        }

        // ---- 选中下划线（宽度 = 图标宽度，紧贴容器底）----
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: root.indicatorMargin
            width: root.indicatorWidth
            height: root.indicatorHeight
            radius: height / 2
            color: Lumi.accent
            visible: root.checked
        }
    }

    // 分段项只有图标，用 ``tools[].label`` 补一个悬停提示
    Rin.ToolTip {
        visible: root.tooltip !== "" && root.hovered
        text: root.tooltip
        delay: 600
    }
}
