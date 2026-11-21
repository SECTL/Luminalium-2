import QtQuick
import QtQuick.Window
import ".."

/*!
    顶层窗口 —— 放映时的**全屏叠加层**。

    把原本分散的各角落控制条窗口（工具栏 / 翻页栏等）合并成一个
    独立的全屏置顶窗口：本身完全透明，控制条作为 Item 挂在
    ``container`` 里、由 Python 定位到各角落。

    交互约定（Windows 原生实现，见 ``app/windows.py``）：

    * 窗口样式含 ``WS_EX_TRANSPARENT | WS_EX_NOACTIVATE``（**不含**
      ``WS_EX_LAYERED`` —— Qt Quick 的 D3D flip 呈现与分层合成不兼容，
      加了会整窗隐形），即**整窗鼠标 / 触摸穿透**；
    * 轮询光标位置：落在某个控制条的 ``interactiveRect``（工具栏表面，
      不含投影余量）内时**临时移除** ``WS_EX_TRANSPARENT``，让控制条可点；
      离开后恢复穿透。放映窗口的焦点全程不被抢走。

    窗口级属性统一在这里，控制条只管内容：

    * ``Qt.Tool`` —— 不占任务栏；
    * ``Qt.WindowDoesNotAcceptFocus`` —— 点按钮不抢放映窗口焦点；
    * ``Qt.WindowStaysOnTopHint`` —— 压在放映窗口之上。

    本窗口会被 **区域塑形**（``SetWindowRgn``）裁成「只有控制条几块」，
    区域外既不绘制也不命中 —— 所以左下角的开发水印必须让 Python 侧
    把它的矩形一并算进区域（``windows.py`` 读 ``watermarkItem``），
    否则会被整个裁掉。

    2026-10-06 用户指令「放映工具顶层窗口可以更智能些」之后，窗口本身也归
    Python 侧的看护定时器管（``windows.py::_watch_overlay``）：

    * **几何跟着放映窗口走** —— 全屏放映时两者重合，窗口化放映时遮罩就贴着
      那个窗口（``_apply_overlay_geometry``）；
    * **放映窗口不在前台时临时隐去** —— 走下面这个 ``suppressed`` 属性做淡出，
      不是 ``hide()`` 窗口（藏一只全屏分层窗口再显示会闪一帧）。

    QML 这边只管「淡成 0 / 淡回来」，穿透与区域由 Python 同步处理。
*/
Window {
    id: topWindow

    objectName: "TopWindow"
    title: qsTr("顶层窗口")
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        | Qt.WindowDoesNotAcceptFocus

    /*! 各角落控制条（``PresentationDock`` Item）的挂载容器。 */
    property alias container: containerItem

    /*! 左下角开发水印（Python 侧把它的矩形加进窗口区域）。

        **不要用 ``property alias``**：别名会推断成匿名 QML 类型
        （``DevWatermark_QMLTYPE_*``），PySide6 的 ``QObject.property()``
        转换不了它（RuntimeError: Can't find converter）；
        显式声明成 ``Item`` 类型就能正常取回。
    */
    readonly property Item watermarkItem: devWatermark

    /*! 右下角的**课件续页卡片**（2026-11-08 用户指令：「让那个卡片显示在右下角」）。

        为什么不挂在控制条里（改这块前必读）：这张卡是**贴屏幕右下角**的固定
        位置，与控制条在哪无关 —— 而控制条自己的 ``interactiveRect`` 只覆盖
        「条 + 紧贴它的浮出层」，卡片离条太远，硬塞进去会让那条交互矩形撑满
        小半个屏幕（区域塑形之后整个右下角都吃点击，放映时点画面翻不了页）。

        所以它走**开发水印的同一条路**：作为窗口根的直接子项，由 Python 侧
        ``windows.py::_resume_card_rect_local`` 把矩形单独并进 ``SetWindowRgn``
        的区域与命中判定 —— 与 ``watermarkItem`` 逐字同一套机制。

        ⚠️ 与 ``watermarkItem`` 同一条：**不要用 ``property alias``**
        （别名会推断成匿名 QML 类型，PySide6 的 ``property()`` 转换不了）。
    */
    readonly property Item resumeCardItem: resumeCard

    /*! 根级浮出物（续页卡片）的矩形变了 —— Python 侧据此**立刻**重算窗口区域。

        为什么需要（2026-11-08）：卡片挂在窗口根上、不进任何控制条的
        ``interactiveRect``，所以它挪位置 / 显隐时没有任何东西通知 Python。
        只靠 ``_assert_topmost`` 那 800ms 一拍的话，用户在主界面编辑器里换了
        位置预设，屏幕上要过半秒才点得动。接法与控制条的 ``hitRectChanged``
        完全一致（``windows.py::_connect_hit_rect`` 是同一个槽）。
    */
    signal hitRectChanged()

    Connections {
        target: resumeCard
        function onXChanged() { topWindow.hitRectChanged() }
        function onYChanged() { topWindow.hitRectChanged() }
        function onWidthChanged() { topWindow.hitRectChanged() }
        function onHeightChanged() { topWindow.hitRectChanged() }
        function onVisibleChanged() { topWindow.hitRectChanged() }
    }

    /*! 「临时隐去」开关（Python 侧 ``windows.py::_set_overlay_suppressed`` 置位）。

        放映窗口不在前台时（用户切去别的程序），控制条淡出；切回来自动淡入。
        用淡出而不是 ``hide()``：隐藏一只全屏分层窗口再显示会闪一帧，而这里
        只是「先让开」。淡出期间 Python 会把整窗穿透打开 —— 内容看不见了，
        但那几块命中矩形还在，不穿透的话会继续吃掉点击。
    */
    property bool suppressed: false

    Item {
        id: containerItem
        anchors.fill: parent
        opacity: topWindow.suppressed ? 0 : 1
        Behavior on opacity {
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }
    }

    // 开发中水印：左下角、左翻页 pill 的**上方**（pill 占 bottom-82..bottom-20，
    // 水印 90 起步正好不叠）。纯文字不吃点击；区域由 Python 一并纳入。
    // ⚠️ 不用 anchors：这个 Qt.Tool 透明窗口的 contentItem 高度是 0
    // （实测），``anchors.bottom: parent.bottom`` 会解析到 y=-124；
    // 直接对**窗口尺寸**绑 y 才可靠。
    DevWatermark {
        id: devWatermark
        x: 20
        y: topWindow.height - 90 - height
        z: 10
        // 水印是窗口根的直接子项（不在 container 里），临时隐去要跟着一起淡
        opacity: containerItem.opacity
    }

    // ======================================== 课件续页卡片（2026-11-08）
    // 用户指令：「让那个卡片显示在右下角」—— 固定贴**窗口**右下角，与控制条
    // 的位置无关（控制条可能在左下、右下或底中，三种都不该带着卡片跑）。
    //
    // 与开发水印同一个挂法（窗口根的直接子项），理由见 ``resumeCardItem``：
    // 控制条的 ``interactiveRect`` 装不下它，硬塞会把整个右下角变成吃点击的
    // 死区。这里由 Python 侧单独把它的矩形并进区域与命中判定。
    //
    // ⚠️ 同样**不用 anchors**（``contentItem`` 高度为 0 的老坑），对窗口尺寸绑。
    // ⚠️ ``z`` 要压在控制条之上（控制条在 container 里，z 默认 0）。
    ResumeCard {
        id: resumeCard
        objectName: "resumeCard"

        opened: Backend.pageMemory.visible === true
        animate: true

        lastPage: Backend.pageMemory.page !== undefined
            ? Number(Backend.pageMemory.page) : 0
        lastTotal: Backend.pageMemory.total !== undefined
            ? Number(Backend.pageMemory.total) : 0
        currentTotal: Backend.slideTotal
        currentPage: Backend.slideIndex
        fileName: Backend.pageMemory.name !== undefined
            ? String(Backend.pageMemory.name) : ""
        ageSeconds: Backend.pageMemory.ageSeconds !== undefined
            ? Number(Backend.pageMemory.ageSeconds) : 0
        resumed: Backend.pageMemory.resumed === true

        z: 20
        // 位置由配置的预设决定（2026-11-08 用户指令：主界面编辑器里给六档位置
        // 预设）。空串 / 未知值一律回落 ``bottom_right`` —— 卡片总得有个地方待着，
        // 而右下角是用户最初指定的那一档。
        positionPreset: {
            var memory = Backend.presentationConfig.page_memory
            var value = memory !== undefined && memory.position !== undefined
                ? String(memory.position) : ""
            return value !== "" ? value : "bottom_right"
        }
        // 临时隐去（放映窗口不在前台）时跟着一起淡 —— 与 container / 水印同源
        opacity: containerItem.opacity

        onResumeRequested: Backend.resumeToMemory()
        onDismissRequested: Backend.dismissPageMemory()
    }
}
