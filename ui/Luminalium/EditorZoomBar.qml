import QtQuick
import RinUI as Rin
import Luminalium

/*!
    主界面编辑器里**悬浮在预览区上**的缩放缓（− / 百分比 / ＋ + 档位说明）。

    2026-10-01（第六轮）用户指令：「把返回按钮删掉 加一个圆按钮放在侧面板的中部，
    缩放作为一个悬浮组件放在左侧的主界面预览区域」。缩放缓原先长在右侧面板的
    **下部常驻条**里（和组件信息挤在同一行），现在整块搬出来，做成压在预览区上的
    浮出层 —— 面板底部只剩「现在在编谁」那行读数。

    ## 摆放

    组件自己的尺寸**含投影余量**（``implicit*`` 已经把 ``shadowMargin`` 算进去，
    胶囊本体在 ``shadowMargin`` 处），所以调用方按 ``implicit*`` 摆就行，不必
    手工扣 —— 与 ``ui/presentation/FlyoutSurface.qml`` 是同一套约定。

    2026-10-01（第七轮）用户指令：「缩放应该放在预览区右上方」—— 原先摆在预览区
    **底边居中**（离视口下沿 16），本轮挪到**右上角**（离视口上沿 / 右沿各 16）。
    两个理由：① 底边居中会跟「横版两侧下部」那类贴着屏幕下沿的翻页栏擦边；
    ② 右上角是视野里最闲的地方，放大后的控制条几乎不会去到那儿。

    ## 用法

        EditorZoomBar {
            anchors.right: viewport.right
            anchors.top: viewport.top
            percent: viewport.scalePercent
            autoMode: editorWindow.autoScale
            onZoomInRequested: viewport.zoomBy(Lumi.editorZoomStep)
            onZoomOutRequested: viewport.zoomBy(1 / Lumi.editorZoomStep)
            onResetRequested: viewport.resetZoom()
        }

    ⚠️ 容器**挂载点别放进视口**（``clip: true``）：投影会被视口的矩形裁成硬边。
    取视口当 ``anchors`` 的基准即可 —— 视口与它是**兄弟**，锚点跨兄弟是完全合法的。

    ⚠️ 三个按钮都只是**发信号**，不认识相机 —— 缩放状态（``autoScale`` /
    ``manualScale``）只有 ``MainInterfaceEditor`` 那份，别在这里再存一份。
*/
Item {
    id: root

    /*! 当前比例（屏幕坐标系 1:1，所以 100% = 真实像素大小）。 */
    property int percent: 100
    /*! 是否自动档（自动适应 = 相机跟着取景目标走）。驱动百分比那块的高亮。 */
    property bool autoMode: true

    signal zoomOutRequested()
    signal zoomInRequested()
    signal resetRequested()

    /*! 投影余量。摆放时按它扣（见头注释）。 */
    readonly property int shadowMargin: Lumi.editorFloatShadowMargin
    readonly property int buttonSize: Lumi.editorMiniButtonSize
    /*! 胶囊左右内边距。 */
    readonly property int paddingX: 12

    implicitWidth: pill.width + shadowMargin * 2
    implicitHeight: pill.height + shadowMargin * 2

    /*! 投影**必须先于**底板声明，否则会盖在底板上面。
        ⚠️ ``source`` 形态的 DropShadow 输出的是「源 + 影子」，所以胶囊本身
        也会被它画一遍 —— 不透明的胶囊上两次绘制像素完全一样，看不出差别，
        这也是 ``ui/presentation/FlyoutSurface.qml`` 的既有写法（那边是控制条
        底板）。 */
    Rin.Shadow {
        source: pill
        style: "flyout"
        radius: Lumi.editorFloatShadowBlur
        verticalOffset: Lumi.editorFloatShadowOffsetY
    }

    Rectangle {
        id: pill
        objectName: "editorZoomBarSurface"

        x: root.shadowMargin
        y: root.shadowMargin
        width: row.width + root.paddingX * 2
        height: Lumi.editorZoomBarHeight
        // 圆角矩形，**不是药丸**（2026-10-01 第七轮用户指令「不该是大圆角」）。
        // 早先是 ``height / 2``，那是 L1 的胶囊语言；编辑器里的工具浮出层走
        // Fluent 的 OverlayCornerRadius。
        radius: Lumi.editorFloatRadius
        color: Lumi.editorPanelBg
        border.width: 1
        // ⚠️ 不能用 ``panelCardBorder``：深色档它是黑 10%，压在 #303030 的底板上
        //    等于没有（这个坑见 ``Lumi.hairline``）。
        border.color: Lumi.hairline

        /*! 描边色经 ``border`` 分组属性拿不到（PySide 侧没有 ``QQuickPen*`` 的
            转换器），复制一份给自检读 —— 深色下「描边消失」是这块浮出层最容易
            回退的地方（用户 2026-10-01 的反馈就是它）。 */
        readonly property color surfaceBorderColor: border.color
    }

    /*! 吞掉落在胶囊**内边距**上的点击。

        不吞的话它会穿到底下的舞台屏蔽层（``editorStageShield``），变成
        「点了一下空白 → 退出编辑态」—— 用户点在自己刚看到的控件上却被弹出去，
        是这块浮出层最容易招骂的交互。 */
    MouseArea {
        anchors.fill: pill
        acceptedButtons: Qt.AllButtons
    }

    /*! 内容行。子项都取 ``buttonSize`` 高（Row 只管 x，子项是顶对齐的），
        需要竖向居中的文字各自包一层同高的 ``Item``。 */
    Row {
        id: row
        objectName: "editorZoomRow"

        x: pill.x + root.paddingX
        y: pill.y + Math.round((pill.height - height) / 2)
        spacing: 4

        Rin.Clip {
            objectName: "editorZoomOut"
            width: root.buttonSize
            height: width
            radius: Lumi.controlRadius
            color: Lumi.controlHoverFill
            padding: 0
            onClicked: root.zoomOutRequested()

            Rin.Icon {
                anchors.centerIn: parent
                icon: "ic_fluent_subtract_20_regular"
                size: 16
                color: Lumi.textPrimary
            }
        }

        /*! 百分比 —— 同时也是「回到自动档」的按钮（自动档时底色点亮）。 */
        Rin.Clip {
            objectName: "editorZoomReset"
            width: 64
            height: root.buttonSize
            radius: Lumi.controlRadius
            color: root.autoMode ? Lumi.controlHoverFill : "transparent"
            padding: 0
            onClicked: root.resetRequested()

            Rin.Text {
                objectName: "editorZoomLabel"
                anchors.centerIn: parent
                typography: Rin.Typography.Body
                text: root.percent + "%"
            }
        }

        Rin.Clip {
            objectName: "editorZoomIn"
            width: root.buttonSize
            height: width
            radius: Lumi.controlRadius
            color: Lumi.controlHoverFill
            padding: 0
            onClicked: root.zoomInRequested()

            Rin.Icon {
                anchors.centerIn: parent
                icon: "ic_fluent_add_20_regular"
                size: 16
                color: Lumi.textPrimary
            }
        }

        /*! 档位说明（自动适应 / 手动档位）—— 一枚孤零零的「100%」看不出它是不是
            在跟着取景目标走，所以这行字跟着缩放缓一起搬过来了。 */
        Item {
            width: modeLabel.implicitWidth
            height: root.buttonSize

            Rin.Text {
                id: modeLabel
                objectName: "editorZoomMode"
                anchors.verticalCenter: parent.verticalCenter
                typography: Rin.Typography.Caption
                color: Lumi.textTertiary
                text: root.autoMode ? qsTr("自动适应") : qsTr("手动档位")
            }
        }
    }
}
