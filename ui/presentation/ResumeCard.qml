import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    续播提示卡片 —— 放映时贴**屏幕一角**的一张提示：**上次放映到第 N 页，点一下继续**。

    2026-11-08 用户指令（参照 ClassIsland 的「课件续页」插件，见
    ``app/page_memory.py``）：按演示文件记住上次放到第几页，下次放映同一份文件
    时把这张卡片摆出来，点一下就 ``GotoSlide`` 回去接着讲。

    2026-11-22 用户指令：表述从课堂场景改成通用（「课件续页」→「续播」），
    并按人机交互习惯重做版式。旧版一屏说了三遍同一个页码（大号数字 +
    「上次停在第 8 页」+「点击从第 8 页开始放映」），信息重复且主操作
    混在一行文字里，不像按钮。

    ## 版式（2026-11-22 重做）

    ::

        ┌──────────────────────────────┐
        │ 测试.pptx                 × │   ← 文件名 + 收起
        │ 上次放映到第 8 页             │   ← 卡片唯一一次提到页码
        │ 记录于 3 分钟前               │   ← Caption（次要信息）
        │ [ ▶ 继续放映 ]               │   ← Rin.Button 强调按钮（主操作）
        └──────────────────────────────┘

    信息层级按「标题 → 正文 → 次要 → 主操作」从上到下排：

    * **页码只说一次**。正文那句就是全部信息，按钮只写「继续放映」——
      按钮重复页码既占宽度，又让用户在两处之间做无意义的比对。
    * **主操作是一个真正的按钮**（``Rin.Button`` + ``highlighted``，Fluent
      强调样式），不再是一行可点的文字：按钮有明确的边界、悬停 / 按下反馈和
      ``PointingHandCursor``，符合「看起来可点就得真的可点」。
    * **完成后按钮原地换成结果**（✓ 已继续放映），高度与按钮相同，卡片不
      跳一下。旧版把按钮文字改掉继续留着，看起来仍然可点。
    * 卡片不参与「光标移出控制条就收」（见下），退路始终是「×」与退出放映。

    ## 与「区域塑形」的关系（改这块前必读）

    顶层窗口被 ``SetWindowRgn`` 裁成「只有控制条几块」，**区域外既不绘制也不
    参与命中**。

    ⚠️ **2026-11-08 用户指令「让那个卡片显示在右下角」之后，本卡片不再挂在
    控制条里**（那条路会让控制条的 ``interactiveRect`` 撑满半个屏幕，区域塑形
    之后整个右下角都吃点击、放映时点画面翻不了页）。现在它挂在
    ``TopWindow.qml`` 的**根**上，由 Python 侧 ``windows.py::_resume_card_rect_local``
    把矩形单独并进窗口区域与命中判定 —— 与开发水印**逐字同一套机制**。
    改了挂法要同步改那三处（``_dock_rects_local`` / ``_update_overlay_hit`` /
    ``_touch_over_ui``），漏一处就是「画不出来」或「点不动」。

    ## 贴边靠 ``positionPreset``

    调用方（``TopWindow`` / ``MainInterfaceEditor``）给 ``positionPreset``，
    本组件内部用 ``anchors`` 交给 Qt 布局引擎 —— **不要**改成手算
    ``窗口宽 - width``：``Window.window.width`` 求值早于窗口尺寸落定（读到 0），
    而 Python / 预览的 ``setWidth()`` 会摘掉调用方那条绑定（2026-11-08 预览
    实锤，卡片整个跑到左上角）。

    ## 为什么它自己收 / 不收

    * **不参与**「光标移出控制条就收」（``windows.py::_dismiss_popup_panels`` 只认
      ``jumpPanelOpened`` / ``overflowPanelOpened``）—— 与放大镜选单同一个理由：这张卡是**要人读一下再点**
      的，光标飘出去就消失会很难用（翻页时手根本不在控制条上）。退路是「点 ×」
      与「退出放映」，两者都由调用方处理。
    * 点「继续放映」之后**不收**，按钮原地换成「已继续放映」——
      用户可能还要拿它对着页码确认跳没跳对。

    ## 文案的来源

    全部由 Python 侧喂（``Backend.pageMemory``，见 ``PageMemory.snapshot``），
    卡片自己不拼字符串：中文原文与译文的对应关系在 ``translations/`` 里，
    QML 侧只做 ``qsTr`` 的**格式串**（``%1`` 之类）。「记录于 N 分钟前」这种
    相对时间在这里算（QML 侧拿 ``ageSeconds`` 翻），因为它是**显示**逻辑，
    不该在 Python 里提前定死。

    ## 自检相关的镜像属性

    * ``reveal``（0..1 展开进度）：等它到 1 再读几何，别读进出场动画半路的值；
    * ``cardWidth`` / ``cardHeight``：卡片本体尺寸（调用方按它算落点）；
    * ``lastPage`` / ``fileName`` / ``recordedText``：文案的最终值（Python 侧读
      文本要走这些镜像，``Rin.Text.text`` 经 ``property()`` 能拿到，但拼好的
      相对时间只有这里知道）。
*/
Item {
    id: root

    // ------------------------------------------------------------ 数据（调用方给）
    /*! 卡片是否该露脸（``Backend.pageMemory.visible``）。 */
    property bool opened: false
    /*! 上次停的那一页（1-based，0 = 没有记录）。 */
    property int lastPage: 0
    /*! 上次记录时的总页数（保留给编辑器假数据；卡片版式不再展示）。 */
    property int lastTotal: 0
    /*! 当前这场放映的总页数（``Backend.slideTotal``；0 = 还没读到）。 */
    property int currentTotal: 0
    /*! 当前页码（``Backend.slideIndex``）。 */
    property int currentPage: 0
    /*! 演示文件名（卡片标题）。 */
    property string fileName: ""
    /*! 距记录时刻过了多少秒（相对时间由本组件翻成人话）。 */
    property real ageSeconds: 0
    /*! 用户点过「继续放映」没有 —— 主操作区据此换成完成态。 */
    property bool resumed: false

    /*! 点「继续放映」—— 交给调用方去驱动后端（``Backend.resumeToMemory()``）。 */
    signal resumeRequested()
    /*! 点「×」—— 本场不再弹（调用方转给 ``Backend.dismissPageMemory()``）。 */
    signal dismissRequested()

    /*! 进出场是否走动画。默认开；关掉时 ``reveal`` 直接落到 0 / 1。
        ⚠️ 这个开关是给**离屏抓图工具**用的（``tools/preview.py`` 里置 false）：
        预览在屏幕外建窗口抓帧，``Behavior`` 的时间轴在那种环境下推进不可靠
        （与 ``PageJumpPanel`` / ``PenPaletteCard`` 同一条坑）。 */
    property bool animate: true

    // ------------------------------------------------------------ 尺寸令牌
    readonly property int shadowMargin: Lumi.dockPaletteShadowMargin
    readonly property int padding: Lumi.dockPalettePadding
    /*! 卡片宽度（设计单位）。比笔选单窄一档 —— 这里只有几行字 + 一个按钮。 */
    readonly property int cardWidthToken: Lumi.dockResumeWidth
    /*! 主操作按钮高度。完成态占位用同一个值，避免切换时卡片高度跳一下。 */
    readonly property int actionHeight: 34

    /*! 尺寸含投影余量（与 ``FlyoutSurface`` / ``PenPaletteCard`` 同一套约定：
        摆放方按 ``implicit*`` 摆，卡片本体在 ``shadowMargin`` 处）。 */
    implicitWidth: card.width + shadowMargin * 2
    implicitHeight: card.height + shadowMargin * 2
    /*! 根 Item 的尺寸 = ``implicit*``。

        ⚠️ **必须有这两行**（2026-11-08 改挂右下角时暴露的）：``Item`` 不会
        自动跟随自己的 ``implicitWidth/Height``（那是给布局器看的建议值）。
        以前挂在控制条里时靠「绘制溢出」侥幸显示，改成贴窗口右下角之后
        ``x = 窗口宽 - width`` 里的 ``width`` 是 **0**，卡片整个跑到左上角
        （预览实锤：``rect=(0,0)``）。 */
    width: implicitWidth
    height: implicitHeight

    /*! 贴父项的**哪个角 / 哪条边**（2026-11-08 用户指令：「点击卡片时弄几个
        位置预设：左上左下右上右下还有中间」）。

        取值与 ``app/windows.py::CORNERS`` 同源：``top_left`` / ``top_right`` /
        ``bottom_left`` / ``bottom_right`` / ``middle_left`` / ``middle_right``。
        空串 = 不自动贴边（调用方自己给 ``x/y``，预览与探针用）。

        ⚠️ 「中间」落到 ``middle_left`` / ``middle_right`` —— **屏幕一侧垂直
        居中**，不是正中央。卡片浮在幻灯片正中会挡住讲课内容；贴边一列既不挡
        画面又能一眼看到。

        ⚠️ 实现用 ``anchors``（Qt 布局引擎在父项尺寸变化时自动重算），**不要**
        改成手算 ``parent.width - width``：``Window.window.width`` 求值早于窗口
        尺寸落定（读到 0），而 Python / 预览的 ``setWidth()`` 会摘掉调用方那条
        绑定（2026-11-08 预览实锤，卡片整个跑到左上角）。

        ⚠️ 边距要**减去** ``shadowMargin``：``anchors.right`` 贴的是 Item 的
        **右沿**，而卡片本体在 Item 内还往左缩了一份投影余量 —— 所以 Item
        右沿要比本体多让出 ``Lumi.dockJumpEdge - shadowMargin``，本体离窗口边
        才正好是 ``Lumi.dockJumpEdge``。写成 ``edge + shadowMargin`` 会让本体
        离窗口边差出两倍投影余量（实测 56px，期望 16）。

        ⚠️⚠️ **anchors 必须用命令式重设，不能写成条件绑定**（2026-11-08 实测）：
        ``anchors.left: cond ? parent.left : undefined`` 这种写法在**切换**档位时
        不会可靠地断开旧 anchor —— 从 ``top_left`` 切到 ``middle_right`` 之后，
        左边那条 anchor 还在，于是 ``width`` 被 Qt 接管、卡片撑成 1108×648
        （窗口 1100×640，整个屏幕都被它盖住）。所以见下面的 ``_applyPreset()``：
        先把五条 anchor 全部显式清成 ``undefined``，再按档位一条条设。
        anchors 一旦设好就由 Qt 自己跟着父项尺寸重算，不需要任何人重装绑定。
    */
    property string positionPreset: ""

    readonly property bool _hasPreset: positionPreset !== ""
    readonly property bool _alignLeft: positionPreset.indexOf("left") >= 0
    readonly property bool _alignRight: positionPreset.indexOf("right") >= 0
    readonly property bool _alignTop: positionPreset.indexOf("top") >= 0
    readonly property bool _alignBottom: positionPreset.indexOf("bottom") >= 0
    readonly property bool _alignMiddle: positionPreset.indexOf("middle") >= 0
    /*! 边距（**屏幕像素**）：Item 的边沿到父项边沿的距离。 */
    readonly property real _inset: Lumi.dockJumpEdge - shadowMargin

    /*! 按 ``positionPreset`` 重设 anchors（**命令式**，理由见上面那段 ⚠️⚠️）。

        ⚠️ 判据**直接读 ``positionPreset``**，不要用 ``_alignLeft`` 那些派生
        ``readonly property``：它们在 ``onPositionPresetChanged`` 跑的时候
        还没重算（QML 的派生属性在属性变化处理器里拿到的是旧值，与
        ``MainInterfaceEditor.onSelectedCornerChanged`` 那条注释同一个坑）——
        实测症状是位置永远慢一档（设 ``top_left`` 却停在 ``bottom_right``）。
    */
    function _applyPreset() {
        var preset = positionPreset
        var has = preset !== ""
        var left = preset.indexOf("left") >= 0
        var right = preset.indexOf("right") >= 0
        var top = preset.indexOf("top") >= 0
        var bottom = preset.indexOf("bottom") >= 0
        // 第一步：五条 anchor 全部断开。顺序无关，但必须都做 —— 少清一条就是
        // 「上一档的位置残留」。
        anchors.left = undefined
        anchors.right = undefined
        anchors.top = undefined
        anchors.bottom = undefined
        anchors.verticalCenter = undefined
        anchors.horizontalCenter = undefined
        anchors.leftMargin = 0
        anchors.rightMargin = 0
        anchors.topMargin = 0
        anchors.bottomMargin = 0
        if (!has)
            return
        // 第二步：按档位设。横档 2 条（左右之一）、纵档 2 条（上 / 下 / 居中之一）。
        if (left)
            anchors.left = parent.left
        else if (right)
            anchors.right = parent.right
        else
            anchors.horizontalCenter = parent.horizontalCenter
        if (top)
            anchors.top = parent.top
        else if (bottom)
            anchors.bottom = parent.bottom
        else
            anchors.verticalCenter = parent.verticalCenter
        // 第三步：边距。居中的那两条不吃 margin（居中就是居中）。
        anchors.leftMargin = left ? _inset : 0
        anchors.rightMargin = right ? _inset : 0
        anchors.topMargin = top ? _inset : 0
        anchors.bottomMargin = bottom ? _inset : 0
    }

    onPositionPresetChanged: _applyPreset()
    Component.onCompleted: _applyPreset()

    /*! 卡片**本体**的尺寸（不含投影余量）—— 调用方按它算落点。 */
    readonly property real cardWidth: card.width
    readonly property real cardHeight: card.height

    // ------------------------------------------------ 动画（Fluent 2 flyout）
    /*! 展开进度 0..1。``opened`` 是语义开关，``reveal`` 是它的动画影子 ——
        自检等 ``reveal`` 到位再读几何，别读半路值。 */
    property real reveal: 0
    onOpenedChanged: reveal = opened ? 1 : 0
    Behavior on reveal {
        enabled: root.animate
        NumberAnimation {
            // 与笔选单同一分工：展开淡入快、收起更快（退出比进入干脆）
            duration: root.opened ? Lumi.dockPaletteEnterDuration
                                  : Lumi.dockPaletteFadeDuration
            easing.type: Easing.OutQuint
        }
    }
    opacity: reveal
    /*! 收起动画期间还得画着（不然淡出没了），归零后才真正藏起。 */
    visible: reveal > 0.001

    // ------------------------------------------------------------ 文案
    /*! 「上次放映到第 N 页」。页码缺失时整行不显示（调用方也不该放卡片出来）。 */
    readonly property string lastPageText: lastPage > 0
        ? qsTr("上次放映到第 %1 页").arg(lastPage) : ""
    /*! 记录时间的人话版本。**故意做得很短** —— 这一行是辅助信息，
        不能让用户的注意力从「第几页」上移开。 */
    readonly property string recordedText: {
        var seconds = Math.max(0, Number(ageSeconds) || 0)
        if (seconds < 60) {
            return qsTr("记录于 刚刚")
        }
        if (seconds < 3600) {
            return qsTr("记录于 %1 分钟前").arg(Math.floor(seconds / 60))
        }
        if (seconds < 86400) {
            return qsTr("记录于 %1 小时前").arg(Math.floor(seconds / 3600))
        }
        return qsTr("记录于 %1 天前").arg(Math.floor(seconds / 86400))
    }

    /*! 投影**必须先于**底板声明，否则会盖在底板上面。 */
    Rin.Shadow {
        source: card
        style: "flyout"
        radius: 18
        verticalOffset: 6
    }

    Rectangle {
        id: card
        objectName: "resumeCardSurface"

        x: root.shadowMargin
        // Fluent 2 flyout enter：卡片在条上方 → 起点比终点低（往下偏），
        // reveal=1 时归位。
        y: root.shadowMargin + (1 - root.reveal) * Lumi.dockPaletteEnterOffset
        width: root.cardWidthToken
        height: content.implicitHeight + root.padding * 2
        radius: Lumi.dockPaletteRadius
        // 92% 实底（与笔选单同档）：这张卡要能读出页码数字，透出放映画面会糊
        color: Lumi.dockPaletteBg
        border.width: 1
        border.color: Lumi.dockPaletteBorder

        /*! 自检镜像（PySide 侧拿不到 ``border`` 分组属性里的 QQuickPen）。 */
        readonly property color surfaceBorderColor: border.color
        readonly property real effectiveRadius: radius
    }

    /*! 吞掉落在卡片范围内的点击 —— 不吞的话会穿到底下的舞台（放映画面）上，
        用户点在自己的卡片上却给幻灯片画了一笔。 */
    MouseArea {
        anchors.fill: card
        acceptedButtons: Qt.AllButtons
    }

    Column {
        id: content

        x: card.x + root.padding
        y: card.y + root.padding
        width: root.cardWidthToken - root.padding * 2
        spacing: Lumi.dockResumeGap

        // ====================================================== 标题行（文件名 + ×）
        Item {
            width: parent.width
            height: Math.max(titleText.implicitHeight, closeButton.height)

            Rin.Text {
                id: titleText
                objectName: "resumeCardTitle"
                width: parent.width - closeButton.width - 6
                text: root.fileName !== "" ? root.fileName : qsTr("续播")
                typography: Rin.Typography.Body
                color: Lumi.textPrimary
                elide: Text.ElideMiddle
                wrapMode: Text.NoWrap
                anchors.verticalCenter: parent.verticalCenter
            }

            /*! 「×」—— 本场不再弹。用 ``Rin.Button`` 的 flat 档（悬停才浮出
                淡底），尺寸做得比主操作小一档：它是次要操作，不该跟
                「继续放映」抢注意力。 */
            Rin.Button {
                id: closeButton
                objectName: "resumeCardClose"
                width: 28
                height: 28
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                padding: 0
                topPadding: 0
                bottomPadding: 0
                leftPadding: 0
                rightPadding: 0
                radius: Math.min(width, height) / 2
                flat: true
                onClicked: root.dismissRequested()

                /*! ⚠️ 换 ``contentItem`` 的两个连带契约（与 ``QuickPanel/IconButton``
                    同一条）：基类的 ``implicitWidth/Height`` 引用了默认
                    contentItem 里的 ``row``，``font`` / disabled state 引用了
                    ``text`` —— 这里留一个不可见的 ``text`` 垫片，并显式给
                    width / height。 */
                contentItem: Item {
                    Text { id: text; visible: false }
                    Rin.Icon {
                        anchors.centerIn: parent
                        // ⚠️ 只用 ``_20_`` 那一档：RinUI 随包的 FluentSystemIcons
                        // 只有 20_regular / 20_filled 两种后缀，写 ``_16_regular``
                        // 不报错但字形是空的（图标静默消失）。
                        icon: "ic_fluent_dismiss_20_regular"
                        size: 14
                        color: Lumi.textSecondary
                    }
                }
            }
        }

        // ====================================================== 正文（唯一一次页码）
        Rin.Text {
            objectName: "resumeCardLastPage"
            visible: text !== ""
            width: parent.width
            text: root.lastPageText
            typography: Rin.Typography.BodyLarge
            color: Lumi.textPrimary
            // 译文可能比中文长（韩文 / 意大利语），宁可换行也不截断
            wrapMode: Text.WordWrap
        }

        // ====================================================== 记录时间（次要）
        Rin.Text {
            objectName: "resumeCardRecorded"
            width: parent.width
            text: root.recordedText
            typography: Rin.Typography.Caption
            color: Lumi.textTertiary
            elide: Text.ElideRight
            wrapMode: Text.NoWrap
        }

        // ====================================================== 主操作 / 完成态
        /*! 两块共用同一个高度：完成后由按钮换成结果文字，卡片高度不跳。
            RinUI 的 ``Rin.Button`` 承担边界、悬停 / 按下反馈与快捷键语义，
            不再手绘 Rectangle + MouseArea。 */
        Item {
            objectName: "resumeCardActionSlot"
            width: parent.width
            height: root.actionHeight

            Rin.Button {
                id: actionButton
                objectName: "resumeCardAction"
                anchors.fill: parent
                visible: !root.resumed
                highlighted: true
                radius: Lumi.dockJumpItemRadius
                icon.name: "ic_fluent_play_20_regular"
                text: qsTr("继续放映")
                onClicked: root.resumeRequested()
            }

            RowLayout {
                objectName: "resumeCardDone"
                visible: root.resumed
                anchors.centerIn: parent
                spacing: 6

                Rin.Icon {
                    icon: "ic_fluent_checkmark_circle_20_regular"
                    size: 16
                    color: Lumi.accent
                    Layout.alignment: Qt.AlignVCenter
                }

                Rin.Text {
                    objectName: "resumeCardDoneLabel"
                    text: qsTr("已继续放映")
                    typography: Rin.Typography.BodyStrong
                    color: Lumi.accent
                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }
    }
}
