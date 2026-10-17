import QtQuick
import QtQuick.Controls.Basic
import RinUI as Rin
import Luminalium

/*!
    滚轮选择器的一列（计时页的「时 / 分 / 秒」与到点页的「时 / 分」共用）。

    2026-10-17 随 ``TimerWindow.qml`` 落地：L1 的 ``.wheel-col`` 是一列
    ``scroll-snap-type: y mandatory`` 的 div，行高 80、字号 56、非当前项
    ``opacity: .3`` + ``scale: .8``，上下各留半屏让首尾也能停在正中；单位字
    （时 / 分 / 秒）挂在选中行的右下角（``.wheel-label``，``bottom: 90px;
    right: -10px``）。值跟着 ``contentY`` **连续**算（L1 也是滚动即亮）。

    ⚠️ 居中的正确姿势（2026-10-17 连试三版才对）：

    * ``ListView`` 的 ``topMargin/bottomMargin`` **只扩可滚动边界**，不挪内容
      起点 —— 所以「让内容偏移」必须**自己算进 contentY**：
      ``contentY = index * itemHeight - topMargin``（i=0 时正好是 -80，靠
      topMargin 才允许滚到负值）。
    * ``snapMode: ListView.SnapToItem`` 不能和「居中对齐」共存：它把行吸到
      **视口顶边**，一松手整列又被顶回去。→ ``NoSnap`` + 自己算目标位并动画。
    * ``header`` + ``footer`` 也别用：ListView 会把 contentItem 整体下移、同时
      把 contentY 记成 -headerHeight，两套偏移叠在一起，实际落点跟算出来的
      差一行（探针里 header 的 y 是 -80，就是它在报警）。
    * 懒创建时给 ``contentY`` 赋值会被夹成 0（那时 ``contentHeight`` 还是 0），
      ``setIndex`` 在窗口刚建出来时因此静默失效。→ 记一个 ``_pendingIndex``，
      等 ``contentHeight`` 有了再落。

    ⚠️ 不要在这上面套 ``layer.enabled`` + ``OpacityMask`` 做上下淡出：① 单位字
    在 ``right: -10`` 的界外会被图层按自身 bounds 裁掉；② 图层化之后 ListView
    的滚动与命中都变得不可靠。淡出由外层（``TimerPage.qml`` 的滚轮容器）用
    两片「页面底色 → 透明」的渐变盖片做，页面底色不透明，观感等价。

    ⚠️ ``currentIndex`` 是**双向**的普通属性，不是绑定：组件自己滚的时候写它，
    外部（预设按钮 / 到点页初始化）用 :meth:`setIndex` 写。故意不用绑定 ——
    双向写同一属性一定会互相顶掉。

    文字（数字与单位字）一律 ``Rin.Text``：``RinUI 规范``那一轮替换把裸
    ``Text`` 全清了。字号保留 L1 的 56 / 14 —— RinUI 字阶（``Rin.Typography``）
    最大只到 Display 68，中间没有 56 这一档，属于「RinUI 没有对应档位」的
    显示级文字，显式给 ``font.pixelSize``（实例赋值会盖掉基类按 typography
    的绑定）。``font.weight`` 同理必须显式写，否则会撞上基类默认分支里那个
    ``return font.weight`` 的自指绑定。
*/
Item {
    id: root

    /*! 取值个数（24 → 0…23，60 → 0…59）。 */
    property int count: 60
    /*! 行高（L1 ``.wheel-item`` 是 80）。 */
    property int itemHeight: 80
    /*! 当前值（双向，见文件头注释）。 */
    property int currentIndex: 0
    property int fontSize: 56
    /*! 单位字（「时」「分」「秒」），画在选中行右下角；空串 = 不画。 */
    property string unitText: ""
    property color textColor: Lumi.textPrimary

    implicitWidth: 80
    implicitHeight: 240

    //: 内容还没量出来时先记下来，等 contentHeight 有了再补（见头注释第 3 条）
    property int _pendingIndex: -1

    /*! 外部设值入口（预设按钮、到点页默认值）。 */
    function setIndex(value) {
        var idx = Math.max(0, Math.min(count - 1, Math.round(value)))
        currentIndex = idx
        // 用 ListView 自己的 Center 定位：它会把「首尾项也居中」算上
        // topMargin/bottomMargin，比手写 contentY 少一套换算。
        if (wheel.contentHeight > 0) {
            wheel.positionViewAtIndex(idx, ListView.Center)
            _pendingIndex = -1
        } else {
            // 懒创建：此刻还没量出来，等 contentHeight 有了再落（见头注释）
            _pendingIndex = idx
        }
    }

    ListView {
        id: wheel
        objectName: "wheelList"

        anchors.fill: parent
        model: root.count
        clip: true
        cacheBuffer: 600
        // 不用 SnapToItem：它吸附到视口顶边，会把「居中」顶掉（见头注释第 2 条）
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds

        // 半屏留白：让首尾也能停在正中（L1 的 padding-top/bottom: 80px）。
        // ⚠️ 这两个 margin 只是**扩边界**，偏移量在 contentY 里自己减。
        topMargin: Math.round((root.height - root.itemHeight) / 2)
        bottomMargin: topMargin

        // 当前值 = 滚动位置对应的行（滚动途中连续更新，和 L1 一致）
        onContentYChanged: {
            // 视口正中对应的行 = (contentY + topMargin) / itemHeight
            var idx = Math.round((contentY + topMargin) / root.itemHeight)
            root.currentIndex = Math.max(0, Math.min(root.count - 1, idx))
        }

        onContentHeightChanged: {
            if (root._pendingIndex >= 0 && contentHeight > 0) {
                positionViewAtIndex(root._pendingIndex, ListView.Center)
                root._pendingIndex = -1
            }
        }

        // 松手 / 甩动结束后吸附到最近一行（SnapToItem 的等价物，但对齐的是中线）
        onMovementEnded: snapToNearest()
        onFlickEnded: snapToNearest()

        function snapToNearest() {
            if (root._pendingIndex >= 0)
                return
            var idx = Math.round((contentY + topMargin) / root.itemHeight)
            idx = Math.max(0, Math.min(root.count - 1, idx))
            var target = idx * root.itemHeight - topMargin
            if (Math.abs(target - contentY) > 0.5) {
                snapAnimation.to = target
                snapAnimation.start()
            }
        }

        delegate: Item {
            required property int index

            width: wheel.width
            height: root.itemHeight

            //: 离选中行的距离：0 = 选中，其余按 L1 压暗缩小
            readonly property int distance: Math.abs(index - root.currentIndex)

            Rin.Text {
                anchors.centerIn: parent
                text: (index < 10 ? "0" : "") + index
                // 等宽数字：滚动时字宽不抖
                font.features: ({ "tnum": 1 })
                // RinUI 字阶没有 56 这一档，显式给（见文件头注释）
                font.pixelSize: root.fontSize
                font.weight: parent.distance === 0 ? Font.DemiBold : Font.Normal
                color: root.textColor
                opacity: parent.distance === 0 ? 1 : 0.3
                scale: parent.distance === 0 ? 1 : 0.8

                Behavior on opacity {
                    NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                }
                Behavior on scale {
                    NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: root.setIndex(index)
            }
        }
    }

    NumberAnimation {
        id: snapAnimation
        target: wheel
        property: "contentY"
        duration: 160
        easing.type: Easing.OutCubic
    }

    // 单位字（L1 .wheel-label：选中行右下角，压在列外侧 10px）
    Rin.Text {
        anchors.right: parent.right
        anchors.rightMargin: -10
        y: parent.height / 2 + 12
        visible: root.unitText !== ""
        text: root.unitText
        typography: Rin.Typography.Body
        color: Lumi.textSecondary
    }
}
