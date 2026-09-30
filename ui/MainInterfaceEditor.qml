import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    主界面编辑器 —— 顶层窗口的可视化编辑舞台。

    2026-10-01 用户指令：「主界面编辑器先完整的把顶层窗口的页面显示出来，
    窗口整体背景除了标题栏都是亚克力」；同日追加「做『编辑态』适应 主界面编辑器的
    缩放，先默认就整体匹配界面的比例，点到那个组件再聚焦，然后从右侧展开居右的
    组件设置面板」。

    ## 「主界面」是什么

    Luminalium 没有传统意义上的主窗口 —— 应用常驻托盘，放映时把所有界面元素
    挂在一只**全屏穿透的顶层窗口**（``ui/presentation/TopWindow.qml``）上。
    换句话说 **顶层窗口就是主界面**，「主界面编辑器」编辑的就是它。

    ## 正文 = 一块「屏幕舞台」

    顶层窗口本身只有控制条、其余全透明（它叠在放映画面上），所以这里不能把
    ``TopWindow.qml`` 直接搬进来 —— 那是只 ``Window``，而且没有放映时它什么
    都不显示。做法是**复刻一份**：

    * ``planeLayer`` —— **1:1 的屏幕坐标系**（尺寸 = 放映显示器的逻辑尺寸），
      控制条副本挂在它上面，位置照 ``cornerAlign`` 摆到各角落 —— 于是
      「下中部工具栏」「左右垂直居中的翻页栏」这些语义在预览里和真机上完全一致；
    * ``screenFrame`` —— 屏幕范围的描边（在**视口坐标**里画，描边宽度不随缩放
      变粗；真机上顶层窗口就是整屏大小，贴边控制条的投影本来就会被屏幕边缘切掉，
      所以副本另有一层 ``screenClip`` 负责裁切）。

    ⚠️ 摆放算法 **与 ``app/windows.py::_position_dock`` 同源**（含 shadowMargin
    扣减、贴边基准是整屏而非工作区）。那边是真实摆放的权威，这边只是预览副本，
    改公式要两边一起改。

    ## 两个态（2026-10-01 用户指令）

    | | 全景态（默认） | 编辑态 |
    |---|---|---|
    | 触发 | 没有选中任何组件 | 在画面里点中一条控制条 |
    | 缩放 | ``fitScale`` —— 整屏等比装进舞台 | 聚焦放大到被点中的那条 |
    | 画面 | 原样 | 面板左边的**整块区域**压一层暗罩、选中项套强调色描边 |
    | 右侧 | 收起的设置面板 | 滑出的组件设置面板 |

    缩放**只动相机**（``scale`` / 位移），不改任何布局尺寸 —— 控制条副本始终活在
    1:1 的屏幕坐标系里。相机三件套：

    * ``stageScale`` —— 目标比例：全景态 = ``fitScale``；编辑态 = 自动档
      （聚焦取景，``focusScale``）或手动档（``manualScale``）；
    * 位移 —— 把**取景目标**（全景态是整屏、编辑态是选中的那条）居中到**视口**
      中央，再按「画面比视口大才允许越界拖动」钳制（``clampOrigin*``）；
    * 拖动平移 —— 见 ``editorStageShield``：屏蔽层挂在**视口**上（不是平面上），
      于是输入坐标不跟着相机走，``mouse.x - pressX`` 就是真实位移（原因写在注释里）。

    鼠标在画面里只有三个动作：**点控制条**（选中 → 进编辑态）、**点空白**（回全景）、
    **拖动**（平移相机）。控制条副本本身**不接**鼠标 —— 它是素材，
    点它不该真的翻页 / 切指针 / 退出放映。

    ## 右侧设置面板

    面板是**挤窄舞台**而不是浮在舞台上面（``anchors.rightMargin`` 跟着
    ``inspectorInset`` 走）—— 聚焦的组件要落在真正可见的那块区域中央。
    底色**实色**（``Lumi.editorPanelBg``），三段式：顶部返回键（``inspectorNav``）/
    中部设置项区（可滚动，待接入）/ 下部常驻条（组件信息 + 缩放）。

    「编辑态压暗」盖的是**面板左边的整块区域**（见 ``dimMask``），不是只盖屏幕 ——
    否则视口四周那圈留白会露出没压暗的亚克力。

    ## 亚克力

    背景是**整窗透明 + 标题栏实色**（见下面 ``background`` 的说明），DWM 的系统
    背景材质由 Python 侧 ``windows.py::_apply_acrylic`` 打在窗口句柄上。

    ## 生命周期

    窗口**只隐藏不销毁**（桌面常驻应用里重建一个 Fluent 窗口的开销不值得），
    关闭走 ``Backend.closeMainEditor()``；入口是快捷面板的「主界面编辑器」快捷方式。
*/
Rin.FluentWindowBase {
    id: editorWindow

    title: qsTr("主界面编辑器")
    visible: false
    // 编辑器比调试窗口大一档：正文是一块 16:9 的屏幕舞台，窗口小了控制条
    // 会缩到看不清。最小尺寸按「面板展开后舞台还剩 400px 宽」倒推。
    width: 1080
    height: 720
    minimumWidth: 780
    minimumHeight: 480

    /*! RinUI 的**按窗口**背景钩子（``core/window.py::extend_frame_into_client_area``）。
        置 true 才会对这只窗口调 ``DwmExtendFrameIntoClientArea``，把 frame 铺满
        客户区 —— 亚克力能覆盖整个内容区的前提。RinUI 的全局开关
        （``Utils.backdropEnabled``）在这里**不能**用：那是给所有窗口的。 */
    property bool backdropEnabled: true

    /*! 亚克力是否真的打上了（Python 侧 ``WindowManager._attach_editor_acrylic``
        回写，自检读它）。 */
    property bool acrylicActive: false

    onClosing: function (event) {
        event.accepted = false
        Backend.closeMainEditor()
    }

    // ============================================================== 窗口背景
    //
    // 「除标题栏外整体亚克力」= 两层：
    //   ① 整窗透明 —— DWM 在窗口背后画的亚克力才透得出来；
    //   ② 标题栏高度那一条铺实色 —— 盖住亚克力。
    //
    // ⚠️ 必须**覆盖**基类的 ``background``。基类那份的底色是
    //    ``Utils.backdropEnabled ? "transparent" : backgroundColor``，而全局开关
    //    由 ``rinui.setBackdropEffect()`` 统一控制（本项目是 none）→ 不覆盖的话
    //    这里会是一块不透明底色，亚克力一点都透不出来。
    //
    // ⚠️ 根节点必须是 ``Rectangle``：基类的 ``onVisibilityChanged`` 会写
    //    ``background.radius`` 与 ``background.border.width``，换成普通 ``Item``
    //    会在首次显隐时抛「Cannot assign to non-existent property」。
    background: Rectangle {
        anchors.fill: parent
        z: -1
        // 亚克力开着时**透明** —— DWM 的材质才透得上来；关掉时退回 Fluent 的
        // 亚克力兜底色（``backgroundAcrylicColor``）。兜底不是摆设：离屏抓图
        // 看不到 DWM 合成层、Win10 没开合成、以及 ``tools/preview.py`` 里
        // 刻意关掉 ``backdropEnabled`` 的预览，都得有东西可看。
        color: editorWindow.backdropEnabled
               ? "transparent"
               : Rin.Theme.currentTheme.colors.backgroundAcrylicColor
        radius: Rin.Theme.currentTheme.appearance.windowRadius
        border.width: 1
        border.color: Rin.Theme.currentTheme.colors.windowBorderColor

        /*! 标题栏实色块。直角即可 —— 窗口顶角由 DWM 的
            ``DWMWA_WINDOW_CORNER_PREFERENCE`` 裁圆，不必自己算圆角。 */
        Rectangle {
            objectName: "editorTitleBarPlate"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: editorWindow.titleBarHeight
            color: Rin.Theme.currentTheme.colors.backgroundColor
        }
    }

    // ============================================================ 编辑态状态
    //
    // 全部状态就这四个属性（外加平移偏移），舞台的缩放与位移全是从它们**派生**
    // 出来的绑定 —— 别在别处再存一份「当前缩放」，两份状态一定漂。

    /*! 选中的角落名（``bottom_center`` / ``middle_left`` / ...）；空串 = 全景态。 */
    property string selectedCorner: ""

    /*! 是否处于编辑态。 */
    readonly property bool editing: selectedCorner.length > 0

    /*! 缩放是否走自动档。
        true  = 跟着取景目标走（全景 = 装下整屏，聚焦 = 装下选中的那条）；
        false = 用 ``manualScale``（用户点过 ＋/－ 或 Ctrl+滚轮）。 */
    property bool autoScale: true

    /*! 手动档比例（相对 1:1 屏幕坐标系）。 */
    property real manualScale: 1.0

    /*! **平面坐标**下的取景目标矩形（选中那条控制条的可见表面，不含投影余量）。
        由 ``updateFocusRect()`` 在选中 / 组件尺寸变化 / 配置重载时刷新。 */
    property rect focusRect: Qt.rect(0, 0, 0, 0)

    /*! 拖动平移的额外偏移（叠加在「取景目标居中」算出来的基准位移上）。
        「取景目标」一变就清零 —— 否则换个组件还在原来的偏移上，会飞出画面。 */
    property real panDX: 0
    property real panDY: 0

    /*! 是否正在拖动平移。拖动期间相机的动画时长归零（要跟手）。 */
    property bool panning: false

    /*! 右侧面板的展开度（0 = 收起，1 = 全展）。面板宽度、舞台右留白都跟着它走。
        不是 ``readonly``：带 ``Behavior`` 的属性必须可写（动画就是往它写值）。 */
    property real inspectorReveal: editing ? 1 : 0

    /*! 面板占掉的横向空间（舞台要让出来）。 */
    readonly property real inspectorInset: Lumi.editorInspectorWidth * inspectorReveal

    /*! 相机动画时长：拖动时归零，其余走 Fluent 的快档。 */
    readonly property int transitionMs: panning ? 0 : Lumi.editorAnimMs

    Behavior on inspectorReveal {
        NumberAnimation { duration: Lumi.editorAnimMs; easing.type: Easing.OutCubic }
    }

    onSelectedCornerChanged: {
        panDX = 0
        panDY = 0
        panning = false
        autoScale = true
        // ⚠️ 这里**不能**用 ``if (editing)`` 把关：``editing`` 是从
        //    ``selectedCorner`` 派生的绑定，本处理器跑的时候它**还没重算**
        //    （还是旧值 false）—— 真踩过：改成编辑态后 focusRect 一直是空矩形，
        //    于是聚焦退化成「全景比例」、暗罩的洞也塌成 0×0。
        //    所以下面的函数一律以 ``selectedCorner`` 为准，不看派生量。
        updateFocusRect()
    }

    // 关掉再开时回到全景态 —— 编辑对象是**会话状态**，不该跟着窗口一起被记住
    // （窗口是只隐藏不销毁的，不清的话下次打开会停在上次的放大位置）。
    onVisibleChanged: {
        if (!visible) {
            clearSelection()
        }
    }

    // ================================================================ 角落表
    //
    // 控制条副本的摆放参数。

    /*! 角落 → (水平对齐, 垂直对齐)。**与 ``app/windows.py::CORNERS`` 同源**
        （那份是权威，这里只是预览副本），改一处要改两处。 */
    readonly property var cornerAlign: ({
        "bottom_left": ["left", "bottom"],
        "bottom_right": ["right", "bottom"],
        "bottom_center": ["center", "bottom"],
        "top_left": ["left", "top"],
        "top_right": ["right", "top"],
        "top_center": ["center", "top"],
        "middle_left": ["left", "middle"],
        "middle_right": ["right", "middle"]
    })

    /*! 角落的遍历顺序 —— 与 ``app/windows.py::CORNERS`` 的键顺序一致，
        保证预览里控制条的层叠顺序和真机上一样。 */
    readonly property var cornerOrder: [
        "bottom_left", "bottom_right", "bottom_center",
        "top_left", "top_right", "top_center",
        "middle_left", "middle_right"
    ]

    /*! 角落 → 面板里显示的位置名。 */
    readonly property var cornerLabels: ({
        "bottom_left": qsTr("屏幕左下角"),
        "bottom_center": qsTr("屏幕底边居中"),
        "bottom_right": qsTr("屏幕右下角"),
        "top_left": qsTr("屏幕左上角"),
        "top_center": qsTr("屏幕顶边居中"),
        "top_right": qsTr("屏幕右上角"),
        "middle_left": qsTr("屏幕左侧垂直居中"),
        "middle_right": qsTr("屏幕右侧垂直居中")
    })

    /*! 配置里**开着**的角落（真机上 Python 也是只给这些角建控制条）。 */
    readonly property var enabledCorners: {
        var config = Backend.presentationConfig
        var corners = config && config.corners !== undefined ? config.corners : ({})
        var names = []
        for (var i = 0; i < cornerOrder.length; ++i) {
            var entry = corners[cornerOrder[i]]
            if (entry !== undefined && entry.enabled === true)
                names.push(cornerOrder[i])
        }
        return names
    }

    /*! 把预览里的控制条摆到角落。

        **算法与 ``app/windows.py::_position_dock`` 逐行对应**：坐标是屏幕
        局部坐标；``margin_x/margin_y`` 的语义是**视觉距离**，所以要扣掉控制条
        自带的投影余量 ``shadowMargin``（扣完贴边的那个角会是负值，投影被屏幕
        裁掉一截 —— 真机上也一样，因为顶层窗口就是整屏大小）。 */
    function placePreviewDock(item, cornerName, planeWidth, planeHeight) {
        if (!item || item.width <= 0 || item.height <= 0)
            return
        var align = cornerAlign[cornerName]
        if (align === undefined)
            return
        var config = Backend.presentationConfig
        var marginX = config && config.margin_x !== undefined ? Number(config.margin_x) : 20
        var marginY = config && config.margin_y !== undefined ? Number(config.margin_y) : 20
        var shadow = item.shadowMargin !== undefined ? Number(item.shadowMargin) : 0

        var x = 0
        if (align[0] === "left")
            x = marginX - shadow
        else if (align[0] === "center")
            x = Math.round((planeWidth - item.width) / 2)
        else
            x = planeWidth - item.width - marginX + shadow

        var y = 0
        if (align[1] === "top")
            y = marginY - shadow
        else if (align[1] === "middle")
            y = Math.round((planeHeight - item.height) / 2)
        else
            y = planeHeight - item.height - marginY + shadow

        item.x = x
        item.y = y
    }

    // ============================================================ 组件语义
    //
    // 面板上要写人话（「工具栏」「翻页组件」），这些名字**从配置推**而不是按角落
    // 写死：同一个角落换了 ``groups`` 就换了身份。

    /*! 某个角落启用了哪些区块（tools / actions / pager / exit）。 */
    function groupsOf(cornerName) {
        var config = Backend.presentationConfig
        var corners = config && config.corners !== undefined ? config.corners : ({})
        var entry = corners[cornerName]
        return (entry !== undefined && entry.groups !== undefined) ? entry.groups : []
    }

    /*! 组件名。竖版两侧翻页（``middle_*``）恒为翻页组件；横条里带工具/动作/退出的
        是**工具栏**，只有翻页区块的是**翻页组件** —— 与用户的口径一致。 */
    function componentName(cornerName) {
        if (!cornerName || cornerName.length === 0)
            return ""
        if (cornerName.indexOf("middle") === 0)
            return qsTr("翻页组件")
        var groups = groupsOf(cornerName)
        if (groups.indexOf("tools") >= 0 || groups.indexOf("actions") >= 0
                || groups.indexOf("exit") >= 0)
            return qsTr("工具栏")
        if (groups.indexOf("pager") >= 0)
            return qsTr("翻页组件")
        return qsTr("控制条")
    }

    /*! 组件图标 —— 与 ``componentName`` 同一套判别。 */
    function componentIcon(cornerName) {
        return componentName(cornerName) === qsTr("翻页组件")
                ? "ic_fluent_chevron_left_20_regular"
                : "ic_fluent_options_20_regular"
    }

    function cornerLabel(cornerName) {
        return cornerLabels[cornerName] !== undefined ? cornerLabels[cornerName] : cornerName
    }

    /*! 面板上那行尺寸（屏幕坐标系里的真实像素，不是缩放后的）。
        用 ``focusRect`` 而不是控制条 Item 的宽高：那个含投影余量，
        写出来会比肉眼看到的条子大 48px。 */
    function focusSizeText() {
        var r = focusRect
        if (r.width <= 0 || r.height <= 0)
            return "-"
        return Math.round(r.width) + " × " + Math.round(r.height)
    }

    // ============================================================ 选中 / 寻址

    function selectCorner(cornerName) {
        if (!cornerName || cornerName.length === 0 || cornerName === selectedCorner)
            return
        selectedCorner = cornerName
    }

    function clearSelection() {
        if (selectedCorner.length === 0)
            return
        selectedCorner = ""
        autoScale = true
        panDX = 0
        panDY = 0
    }

    /*! 按角落名找预览里的控制条副本（还没加载完 / 已卸载 → null）。 */
    function findDockItem(cornerName) {
        var repeater = dockRepeater
        if (!repeater)
            return null
        for (var i = 0; i < repeater.count; ++i) {
            var loader = repeater.itemAt(i)
            if (loader && loader.cornerName === cornerName)
                return loader.item
        }
        return null
    }

    /*! **平面坐标**下的命中测试 → 角落名（没命中返回空串）。

        控制条在编辑器里是「素材」，点它不该真的去翻 PPT / 切指针 / 退出放映
        —— 鼠标事件被 ``editorStageShield`` 拦住，由这里反查点到的是谁。
        判定用 ``interactiveRect``（**可见表面**，已扣掉投影余量）而不是整个
        Item：投影那 24px 是看不见的，不该抢点击。
        从后往前遍历 —— 与绘制顺序相反，先命中后画（更靠上）的那条。 */
    function dockAt(planeX, planeY) {
        var repeater = dockRepeater
        if (!repeater)
            return ""
        for (var i = repeater.count - 1; i >= 0; --i) {
            var loader = repeater.itemAt(i)
            var item = loader ? loader.item : null
            if (!item)
                continue
            var rect = item.interactiveRect
            if (rect === undefined)
                continue
            if (planeX >= item.x + rect.x && planeX <= item.x + rect.x + rect.width
                    && planeY >= item.y + rect.y && planeY <= item.y + rect.y + rect.height)
                return loader.cornerName
        }
        return ""
    }

    /*! 刷新 ``focusRect``（选中项或它的尺寸变了就调）。

        ⚠️ 判空一律看 ``selectedCorner`` 而不是派生的 ``editing`` —— 从属性变化
        处理器里调进来的时候派生量还没更新。 */
    function updateFocusRect() {
        if (selectedCorner.length === 0)
            return
        var item = findDockItem(selectedCorner)
        if (!item || item.width <= 0 || item.height <= 0) {
            focusRect = Qt.rect(0, 0, 0, 0)
            return
        }
        var margin = item.shadowMargin !== undefined ? Number(item.shadowMargin) : 0
        focusRect = Qt.rect(
            item.x + margin, item.y + margin,
            Math.max(item.width - margin * 2, 1),
            Math.max(item.height - margin * 2, 1))
    }

    /*! 配置重载后：选中的角落可能被关掉了，尺寸也可能变了。 */
    function refreshFromConfig() {
        if (selectedCorner.length === 0)
            return
        if (enabledCorners.indexOf(selectedCorner) < 0) {
            clearSelection()
            return
        }
        updateFocusRect()
    }

    // ======================================================== 非可视宿主
    //
    // ⚠️ ``Shortcut`` / ``Connections`` 都**不是** ``Item``，而 ``FluentWindowBase``
    //    把 default property 改写成了 ``contentArea.children``（只收 Item）——
    //    直接写在窗口里会抛「Cannot assign QObject to QQuickItem* list」。
    //    包一层普通 ``Item``：Item 的 default property 是 ``data``（QObject 也收）。
    Item {
        objectName: "editorShortcutHost"

        Shortcut {
            sequence: "Escape"
            onActivated: editorWindow.clearSelection()
        }
        Shortcut {
            sequence: "Ctrl+="
            onActivated: viewport.zoomBy(Lumi.editorZoomStep)
        }
        Shortcut {
            sequence: "Ctrl+-"
            onActivated: viewport.zoomBy(1 / Lumi.editorZoomStep)
        }
        Shortcut {
            sequence: "Ctrl+0"
            onActivated: viewport.resetZoom()
        }
    }

    // ============================================================ 编辑态暗罩
    //
    // 编辑态把**面板左边的整块区域**压暗（2026-10-01 用户指令：「左边的压暗你应该
    // 占满左半边啊而不是留一圈亚克力」）。所以它挂在**窗口坐标**里、铺满内容区
    // 的左半边 —— 早先是挂在 ``planeLayer`` 里的，那样只盖得住「屏幕」本身，
    // 视口四周那 16px 留白会露出一圈没压暗的亚克力。
    //
    // 代价是「洞」要自己换算坐标：取景矩形 ``focusRect`` 活在 **1:1 屏幕坐标系**
    // 里，这里得经相机（``planeLayer`` 的比例与位移）+ 视口在窗口里的偏移，换到
    // 窗口坐标。洞直接取「选中描边 + ``editorDimHolePad``」，于是暗罩与描边天然
    // 同心（描边画在视口坐标里，宽度不随缩放 —— 洞也跟着不缩放）。
    //
    // 洞还要**夹在视口内**：手动放大到 400% 时洞会比视口还宽，不夹的话亮区会漫到
    // 视口外面那圈留白上，跟「铺满左半边」的初衷正好相反。
    Item {
        id: dimMask
        objectName: "editorDimMask"

        /*! 铺满「面板左边的整块区域」，**一路顶到窗口边**。
            内容区被 RinUI 的 ``Utils.windowDragArea`` 四周内缩了 5px（那圈是窗口
            拖拽热区），所以左边与下边各往外撑出这么多 —— 不撑的话贴着窗口边会留下
            一圈 5px 没压暗的亚克力，跟「占满左半边」差着意思。上面不动：标题栏
            是窗口自己的 chrome，不该被压。 */
        readonly property real edgeBleed: Rin.Utils.windowDragArea

        x: -edgeBleed
        y: 0
        width: Math.max(0, parent.width - editorWindow.inspectorInset + edgeBleed)
        height: parent.height + edgeBleed
        // 四块矩形的坐标是「洞相对暗罩」算出来的，洞越出视口时会溢出到面板 /
        // 窗口外 —— 裁掉。
        clip: true
        opacity: editorWindow.editing ? Lumi.editorDimOpacity : 0
        visible: opacity > 0.002
        z: 10

        Behavior on opacity {
            NumberAnimation { duration: Lumi.editorAnimMs; easing.type: Easing.OutCubic }
        }

        /*! 视口在**暗罩坐标**里的范围（暗罩的 0 点比内容区左沿还往外 5px）。 */
        readonly property real viewX: viewport.x + edgeBleed
        readonly property real viewY: viewport.y
        readonly property real viewRight: viewX + viewport.width
        readonly property real viewBottom: viewY + viewport.height

        /*! 洞在**暗罩坐标**里的边界（未夹取）。 */
        readonly property real rawHoleX: viewX + planeLayer.x
            + editorWindow.focusRect.x * planeLayer.scale
            - (Lumi.editorSelectionRingGap + Lumi.editorDimHolePad)
        readonly property real rawHoleY: viewY + planeLayer.y
            + editorWindow.focusRect.y * planeLayer.scale
            - (Lumi.editorSelectionRingGap + Lumi.editorDimHolePad)
        readonly property real rawHoleW: editorWindow.focusRect.width * planeLayer.scale
            + (Lumi.editorSelectionRingGap + Lumi.editorDimHolePad) * 2
        readonly property real rawHoleH: editorWindow.focusRect.height * planeLayer.scale
            + (Lumi.editorSelectionRingGap + Lumi.editorDimHolePad) * 2

        /*! 洞（已夹进视口）—— 亮区绝不越过视口边界。 */
        readonly property real holeX: Math.max(viewX, rawHoleX)
        readonly property real holeY: Math.max(viewY, rawHoleY)
        readonly property real holeRight: Math.min(viewRight, rawHoleX + rawHoleW)
        readonly property real holeBottom: Math.min(viewBottom, rawHoleY + rawHoleH)
        readonly property real holeW: Math.max(0, holeRight - holeX)
        readonly property real holeH: Math.max(0, holeBottom - holeY)

        Rectangle {
            objectName: "editorDimTop"
            x: 0
            y: 0
            width: dimMask.width
            height: Math.max(0, dimMask.holeY)
            color: "#000000"
        }
        Rectangle {
            objectName: "editorDimBottom"
            x: 0
            y: dimMask.holeY + dimMask.holeH
            width: dimMask.width
            height: Math.max(0, dimMask.height - dimMask.holeY - dimMask.holeH)
            color: "#000000"
        }
        Rectangle {
            objectName: "editorDimLeft"
            x: 0
            y: dimMask.holeY
            width: Math.max(0, dimMask.holeX)
            height: dimMask.holeH
            color: "#000000"
        }
        Rectangle {
            objectName: "editorDimRight"
            x: dimMask.holeX + dimMask.holeW
            y: dimMask.holeY
            width: Math.max(0, dimMask.width - dimMask.holeX - dimMask.holeW)
            height: dimMask.holeH
            color: "#000000"
        }
    }

    // ================================================================ 舞台
    //
    // 视口 = 内容区去掉 16 留白，**再让出右侧面板占掉的宽度**。
    // 里面只放「相机」（planeLayer）+ 两块不随缩放变形的描边（屏幕框 / 选中框）。

    Item {
        id: viewport
        objectName: "editorStageViewport"

        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.leftMargin: 16
        anchors.topMargin: 16
        anchors.bottomMargin: 16
        anchors.rightMargin: 16 + editorWindow.inspectorInset
        // 裁掉溢出屏幕的部分（透视放大时画面会伸出视口）
        clip: true

        // ---------------------------------------------------------- 屏幕信息
        readonly property var screenInfo: Backend.presentationScreen
        readonly property real screenWidth: {
            var info = screenInfo
            var value = info && info.width !== undefined ? Number(info.width) : 0
            return value > 0 ? value : 1920
        }
        readonly property real screenHeight: {
            var info = screenInfo
            var value = info && info.height !== undefined ? Number(info.height) : 0
            return value > 0 ? value : 1080
        }

        // ---------------------------------------------------------- 相机三件套
        /*! 全景比例：整屏等比装进视口，长边贴合。 */
        readonly property real fitScale: Math.max(0.02, Math.min(
            Math.max(1, width) / screenWidth,
            Math.max(1, height) / screenHeight))

        /*! 聚焦比例：把选中的那条（+ 取景留白）装进视口。
            下限就是全景比例（聚焦不会比全景还小 —— 否则「点一下反而更小」），
            上限 ``editorFocusMaxScale``。 */
        readonly property real focusScale: {
            var r = editorWindow.focusRect
            if (r.width <= 0 || r.height <= 0)
                return fitScale
            var s = Math.min(
                (Math.max(1, width) - Lumi.editorFocusPaddingX * 2) / r.width,
                (Math.max(1, height) - Lumi.editorFocusPaddingY * 2) / r.height)
            return Math.max(fitScale, Math.min(s, Lumi.editorFocusMaxScale))
        }

        /*! 目标比例。全景态恒为 ``fitScale``（手动档位只在编辑态有意义）。 */
        readonly property real stageScale: !editorWindow.editing
            ? fitScale
            : (editorWindow.autoScale ? focusScale : clampScale(editorWindow.manualScale))

        /*! 面板上显示的百分比。屏幕坐标系是 1:1，所以 100% = 真实像素大小。 */
        readonly property int scalePercent: Math.round(stageScale * 100)

        function clampScale(value) {
            return Math.max(Lumi.editorZoomMinScale,
                            Math.min(Lumi.editorZoomMaxScale, value))
        }

        /*! 取景目标：编辑态是选中的那条，全景态是整屏。 */
        function targetRect() {
            if (editorWindow.editing && editorWindow.focusRect.width > 0
                    && editorWindow.focusRect.height > 0)
                return editorWindow.focusRect
            return Qt.rect(0, 0, screenWidth, screenHeight)
        }

        /*! 取景目标居中到视口中央（未钳制）。 */
        function baseOriginX() {
            var t = targetRect()
            return width / 2 - (t.x + t.width / 2) * stageScale
        }

        function baseOriginY() {
            var t = targetRect()
            return height / 2 - (t.y + t.height / 2) * stageScale
        }

        /*! 钳制位移：画面比视口大 → 允许在范围内拖（但不许把画面拖出视口留出空档）；
            画面比视口小 → 钉在居中（于是全景态永远居中，拖不动）。
            ``clamp(clamp(v)) == clamp(v)``，所以 ``setOrigin`` 可以放心地
            拿「已钳制值」反推 ``panD*``。 */
        function clampOriginX(value) {
            var content = screenWidth * stageScale
            if (content <= width)
                return (width - content) / 2
            return Math.min(0, Math.max(width - content, value))
        }

        function clampOriginY(value) {
            var content = screenHeight * stageScale
            if (content <= height)
                return (height - content) / 2
            return Math.min(0, Math.max(height - content, value))
        }

        /*! 直接把画面原点摆到 ``(vx, vy)``（拖动平移用）。 */
        function setOrigin(vx, vy) {
            editorWindow.panDX = clampOriginX(vx) - baseOriginX()
            editorWindow.panDY = clampOriginY(vy) - baseOriginY()
        }

        /*! 手动缩放，一档一乘（拖动 / 快捷键都走这里）。 */
        function zoomBy(factor) {
            editorWindow.manualScale = clampScale(stageScale * factor)
            editorWindow.autoScale = false
        }

        /*! 回到自动档（面板上点百分比 / Ctrl+0）。 */
        function resetZoom() {
            editorWindow.autoScale = true
            editorWindow.panDX = 0
            editorWindow.panDY = 0
        }

        Connections {
            target: Backend
            function onPresentationConfigChanged() {
                Qt.callLater(editorWindow.refreshFromConfig)
            }
        }

        // ------------------------------------------------------------ 相机本体
        Item {
            id: planeLayer
            objectName: "editorScreenPlane"

            width: viewport.screenWidth
            height: viewport.screenHeight
            scale: viewport.stageScale
            transformOrigin: Item.TopLeft
            x: viewport.clampOriginX(viewport.baseOriginX() + editorWindow.panDX)
            y: viewport.clampOriginY(viewport.baseOriginY() + editorWindow.panDY)

            Behavior on scale {
                NumberAnimation { duration: editorWindow.transitionMs; easing.type: Easing.OutCubic }
            }
            Behavior on x {
                NumberAnimation { duration: editorWindow.transitionMs; easing.type: Easing.OutCubic }
            }
            Behavior on y {
                NumberAnimation { duration: editorWindow.transitionMs; easing.type: Easing.OutCubic }
            }

            /*! 屏幕范围里的东西都挂在这一层 —— ``clip`` 让贴边控制条的投影
                像真机一样被屏幕边缘切掉。 */
            Rectangle {
                id: screenClip
                objectName: "editorScreenClip"
                anchors.fill: parent
                color: "transparent"
                clip: true

                // 各角落的控制条副本
                Repeater {
                    id: dockRepeater
                    model: editorWindow.enabledCorners

                    delegate: Loader {
                        id: previewLoader

                        readonly property string cornerName: String(modelData)

                        // 竖版两侧翻页（middle_*）是独立的竖排组件，其余角落是
                        // 横向 dock —— 与 ``windows.py::_load_docks`` 同一条判断。
                        // ⚠️ 这里用 ``source``（URL）而不是 ``sourceComponent``：
                        // ``Component`` 不是 QQuickItem，声明在窗口里会被塞进
                        // ``default property``（= ``contentArea.children``）而报
                        // 「Cannot assign object of type QQmlComponent to list
                        // property content」。
                        source: Qt.resolvedUrl(cornerName.indexOf("middle") === 0
                            ? "presentation/SidePager.qml"
                            : "presentation/PresentationDock.qml")

                        onLoaded: {
                            item.objectName = "editorPreviewDock_" + cornerName
                            item.corner = cornerName
                            previewLoader.place()
                        }

                        /*! 组件尺寸是异步就绪的（implicitWidth/Height 要等内容
                            排完），所以不能只在 onLoaded 里摆一次 —— 真机侧
                            Python 也是挂 ``widthChanged`` / ``heightChanged``
                            重摆的。 */
                        Connections {
                            target: previewLoader.item
                            function onWidthChanged() { previewLoader.place() }
                            function onHeightChanged() { previewLoader.place() }
                        }

                        function place() {
                            editorWindow.placePreviewDock(
                                previewLoader.item, previewLoader.cornerName,
                                planeLayer.width, planeLayer.height)
                            // 尺寸变了 → 面板上的尺寸与取景矩形都要跟着走
                            editorWindow.updateFocusRect()
                        }
                    }
                }

                // 开发水印：与顶层窗口里同一位置（左下角、左翻页 pill 上方）
                DevWatermark {
                    x: 20
                    y: planeLayer.height - 90 - height
                    z: 10
                }
            }

        }
        /*! 鼠标屏蔽层 —— 同时也是编辑器的**指针**：

            * **点击** → 命中测试（``dockAt``）选中那条控制条；点空白 → 回全景；
            * **拖动** → 平移相机（只在画面比视口大时动得起来，见 ``setOrigin``）。

            ⚠️⚠️ 这一层**挂在视口上、不挂在 planeLayer 上**，输入坐标也因此
            是「视口坐标」。看着别扭，但它就是拖动平移能不能跟手的分水岭：

            挂在 planeLayer 里 → 鼠标坐标跟着相机一起动，算出来的增量
            「自己抵消自己」。这个坑的经典表现是画面**半速跟手**，而本项目的
            实测更阴：MouseArea 的鼠标事件上 **``scenePosition`` 与 ``screenX``
            都不存在**（Qt 6 这两个都取到 undefined），回退到 ``mouse.x`` 之后
            增量没乘缩放，实测 60px 的拖动只走了 33.7px（= 60/1.783）。
            画在视口里就没这回事 —— 视口不跟着相机动，``mouse.x - pressX``
            直接就是真实位移。

            于是坐标换算只剩一处：命中测试要的是**平面坐标**，
            用 ``planeX() / planeY()`` 反算回去。 */
        MouseArea {
            id: stageShield
            objectName: "editorStageShield"
            anchors.fill: parent
            z: 20
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            cursorShape: hoverCorner.length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor

            /*! 光标底下压着哪条控制条（悬停反馈用）。 */
            property string hoverCorner: ""

            property real pressViewX: 0
            property real pressViewY: 0
            property real pressOriginX: 0
            property real pressOriginY: 0
            property bool dragged: false

            /*! 视口坐标 → 平面坐标（相机的逆变换）。 */
            function planeX(viewX) {
                return planeLayer.scale > 0
                    ? (viewX - planeLayer.x) / planeLayer.scale : 0
            }

            function planeY(viewY) {
                return planeLayer.scale > 0
                    ? (viewY - planeLayer.y) / planeLayer.scale : 0
            }

            onPressed: function (mouse) {
                pressViewX = mouse.x
                pressViewY = mouse.y
                pressOriginX = planeLayer.x
                pressOriginY = planeLayer.y
                dragged = false
            }

            onPositionChanged: function (mouse) {
                var corner = editorWindow.dockAt(planeX(mouse.x), planeY(mouse.y))
                if (corner !== hoverCorner)
                    hoverCorner = corner
                if (!pressed)
                    return
                var dx = mouse.x - pressViewX
                var dy = mouse.y - pressViewY
                // 4px 死区：手抖不该把点击变成拖动
                if (!dragged && Math.abs(dx) + Math.abs(dy) < 4)
                    return
                if (!dragged) {
                    dragged = true
                    editorWindow.panning = true
                }
                viewport.setOrigin(pressOriginX + dx, pressOriginY + dy)
            }

            onReleased: editorWindow.panning = false

            onClicked: function (mouse) {
                if (dragged)
                    return
                var corner = editorWindow.dockAt(planeX(mouse.x), planeY(mouse.y))
                if (corner.length > 0)
                    editorWindow.selectCorner(corner)
                else
                    editorWindow.clearSelection()
            }
        }

        /*! 屏幕范围的描边。画在**视口坐标**里（不是 planeLayer 里）—— 这样描边
            宽度与圆角不随缩放变粗变大，放大到 200% 也还是 1px 的细线。
            半径随缩放跟着走的话，全景态 8px 的窗口圆角会缩成 4px、放大又撑成 16px。 */
        Rectangle {
            id: screenFrame
            objectName: "editorScreenFrame"

            x: planeLayer.x
            y: planeLayer.y
            width: Math.round(viewport.screenWidth * planeLayer.scale)
            height: Math.round(viewport.screenHeight * planeLayer.scale)
            color: "transparent"
            radius: Rin.Theme.currentTheme.appearance.windowRadius
            border.width: 1
            border.color: Rin.Theme.currentTheme.colors.controlBorderColor
            z: 5
        }

        /*! 选中项的强调色描边。同样在视口坐标里 —— 2px 恒为 2px。
            几何取 ``planeLayer`` 的**实时**值（正在动画）而不是目标值，
            否则相机动的那 220ms 里框会跟内容脱开。 */
        Rectangle {
            id: selectionRing
            objectName: "editorSelectionRing"

            visible: dimMask.opacity > 0.002
            x: planeLayer.x + editorWindow.focusRect.x * planeLayer.scale
               - Lumi.editorSelectionRingGap
            y: planeLayer.y + editorWindow.focusRect.y * planeLayer.scale
               - Lumi.editorSelectionRingGap
            width: editorWindow.focusRect.width * planeLayer.scale
                   + Lumi.editorSelectionRingGap * 2
            height: editorWindow.focusRect.height * planeLayer.scale
                    + Lumi.editorSelectionRingGap * 2
            color: "transparent"
            // 控制条的底板**恒为全圆胶囊**（``Lumi.dockSurfaceRadius`` = 999，由
            // ``FlyoutSurface`` 按短边钳成高/2），所以选中框也跟着取短边的一半 ——
            // 方角框套在胶囊外面，四个角上会空出一大块。
            radius: Math.min(width, height) / 2
            border.width: Lumi.editorSelectionRingWidth
            border.color: Lumi.accent
            z: 6

            /*! 描边属性经 ``border`` 分组属性拿不到（PySide 侧没有
                ``QQuickPen*`` 的转换器），复制一份给自检读。 */
            readonly property real ringBorderWidth: border.width
            readonly property color ringBorderColor: border.color
        }
    }

    // ========================================================== 右侧设置面板
    //
    // 编辑态的侧栏，三段式（2026-10-01 用户指令：「右侧的设置面板应该是实色背景，
    // 组件信息就放在右侧设置面板的下部始终置着展示：工具栏 318x62，上面的信息
    // 不要了，缩放的话也是放在下部置着，右侧面板其他地方是用来排设置项的」；
    // 同日追加「（右上角那个 ×）加大移到左边改为返回按钮」+「删掉」顶部那块
    // 设置项标题与占位文案）：
    //
    //   · 顶部 —— **返回键**（``inspectorNav``，40px，离开编辑态，和 Esc 同一个出口）；
    //   · 中部 —— **设置项区**（``inspectorBody``，可滚动，待接入）；
    //   · 下部 —— **常驻条**（``inspectorFooter``，不滚动）：组件信息
    //     「工具栏 318 × 62」+ 缩放缓。
    //
    // 底板**一路铺到窗口边**（``edgeBleed``，见 ``inspector`` 的说明）—— 否则右沿与
    // 下沿会露出内容区那 5px 的窗口拖动热区（一圈比面板还亮的亚克力）。
    //
    // 底色是**实色**（``Lumi.editorPanelBg``）—— 面板压在亚克力上，用 Fluent 那个
    // 半透明的「层」色会把背后的亚克力透出来。
    //
    // 面板是**挤窄舞台**而不是浮在舞台上面（视口的 ``anchors.rightMargin`` 跟着
    // ``inspectorInset`` 走）—— 聚焦的组件要落在真正可见的那块区域中央。

    Item {
        id: inspector
        objectName: "editorInspectorPanel"

        width: Lumi.editorInspectorWidth
        height: parent.height
        x: parent.width - width * editorWindow.inspectorReveal
        visible: editorWindow.inspectorReveal > 0.004
        z: 20

        /*! 实色底板要**往外撑**多少 —— 贴着窗口右沿与下沿的那一圈。
            内容区被 RinUI 的 ``Utils.windowDragArea``（5px）四周内缩了，那圈是窗口的
            拖动/缩放热区；底板不撑过去的话，右沿与下沿会露出一条 5px 的**窗口背景**
            （亚克力）。它本身不亮，但窗口自己的投影把窗外的桌面压暗了，两边一对比，
            那圈反而像一条比面板更亮的分隔带（真机实测：面板 #303030，那圈 #413F38）。
            左边不用管：编辑态那儿被暗罩盖着，暗罩本来就撑出去了。
            留 1px 不撑 —— 窗口 ``background`` 的 1px 描边画在最外圈，撑满会把它盖掉，
            那圈描边是暗色下窗口与桌面之间唯一的分界线。 */
        readonly property real edgeBleed: Math.max(0, Rin.Utils.windowDragArea - 1)

        // ------------------------------------------------------------ 实色底板
        Rectangle {
            objectName: "editorInspectorSurface"
            anchors.fill: parent
            anchors.rightMargin: -inspector.edgeBleed
            anchors.bottomMargin: -inspector.edgeBleed
            color: Lumi.editorPanelBg

            /*! 左沿 1px 分隔线 —— 面板与舞台之间要有一条边。 */
            Rectangle {
                objectName: "editorInspectorEdge"
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: Lumi.panelCardBorder
            }
        }

        // ------------------------------------------------------------ 顶部导航
        //
        // 面板最上面一条，只放**返回键**。
        //
        // 2026-10-01 用户指令：「（右上角那个 ×）加大移到左边改为返回按钮」，
        // 同时把顶部那块「设置项」标题 + 占位文案**删掉**。于是原来的
        // 「右上角浮动的 32px ×」变成了「左上角 40px 的返回键」，顶部不再有任何
        // 文字信息 —— 组件名与尺寸在下部常驻条里，本来就够。
        Item {
            id: inspectorNav
            objectName: "editorInspectorNav"

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: Lumi.editorPanelHeaderHeight

            Rin.Clip {
                id: inspectorBack
                objectName: "editorInspectorBack"

                width: Lumi.editorBackButtonSize
                height: width
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                radius: Lumi.controlRadius
                color: Lumi.controlHoverFill
                padding: 0
                // 和 Esc 同一个出口
                onClicked: editorWindow.clearSelection()

                Rin.Icon {
                    objectName: "editorInspectorBackIcon"
                    anchors.centerIn: parent
                    icon: "ic_fluent_arrow_left_20_regular"
                    size: 20
                    color: Lumi.textPrimary
                }
            }

            /*! 与下部常驻条同款的 1px 分隔线：顶部导航与设置项区之间要有一条边。 */
            Rectangle {
                objectName: "editorInspectorNavEdge"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Lumi.panelCardBorder
            }
        }

        // ------------------------------------------------------------ 设置项区
        //
        // 顶部导航条之下、下部常驻条之上，**整块**留给设置项（可滚动）。
        // 目前是空的 —— 用户把每类组件的设置项给过来之后排进 ``bodyColumn``。
        Flickable {
            id: inspectorBody
            objectName: "editorInspectorBody"

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: inspectorNav.bottom
            anchors.bottom: inspectorFooter.top
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentHeight: bodyColumn.implicitHeight + 28

            /*! 设置项的落点：``x/y`` 与 ``width`` 已经排好版，往里加设置项即可
                （间距 8 已经在 ``spacing`` 里）。 */
            ColumnLayout {
                id: bodyColumn
                x: 16
                y: 14
                width: parent.width - 32
                spacing: 8
            }
        }

        // ------------------------------------------------------------ 常驻条
        //
        // 「现在在编谁、看多大一块、放大到几成」—— 三条读数 + 缩放缓，常显不滚动。
        Item {
            id: inspectorFooter
            objectName: "editorInspectorFooter"

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: Lumi.editorPanelFooterHeight

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: Lumi.panelCardBorder
            }

            // ---- 组件信息：名字（左）+ 自身尺寸（右）
            Item {
                id: footerInfoRow
                objectName: "editorFooterInfoRow"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                anchors.topMargin: 14
                height: 20

                Rin.Text {
                    objectName: "editorInspectorName"
                    anchors.left: parent.left
                    anchors.right: footerSizeText.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    typography: Rin.Typography.BodyStrong
                    elide: Text.ElideRight
                    text: editorWindow.componentName(editorWindow.selectedCorner)
                }

                Rin.Text {
                    objectName: "editorInspectorSize"
                    id: footerSizeText
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    typography: Rin.Typography.Caption
                    color: Lumi.textSecondary
                    text: editorWindow.focusSizeText()
                }
            }

            // ---- 缩放缓：− / 百分比（点它回自动档）/ ＋
            Row {
                id: zoomRow
                objectName: "editorZoomRow"
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.top: footerInfoRow.bottom
                anchors.topMargin: 10
                spacing: 4

                Rin.Clip {
                    objectName: "editorZoomOut"
                    width: Lumi.editorMiniButtonSize
                    height: width
                    radius: Lumi.controlRadius
                    color: Lumi.controlHoverFill
                    padding: 0
                    onClicked: viewport.zoomBy(1 / Lumi.editorZoomStep)

                    Rin.Icon {
                        anchors.centerIn: parent
                        icon: "ic_fluent_subtract_20_regular"
                        size: 16
                        color: Lumi.textPrimary
                    }
                }

                /*! 百分比 —— 也是「回到自动档」的按钮（自动档时底色点亮）。 */
                Rin.Clip {
                    objectName: "editorZoomReset"
                    width: 64
                    height: Lumi.editorMiniButtonSize
                    radius: Lumi.controlRadius
                    color: editorWindow.autoScale ? Lumi.controlHoverFill : "transparent"
                    padding: 0
                    onClicked: viewport.resetZoom()

                    Rin.Text {
                        objectName: "editorZoomLabel"
                        anchors.centerIn: parent
                        typography: Rin.Typography.Body
                        text: viewport.scalePercent + "%"
                    }
                }

                Rin.Clip {
                    objectName: "editorZoomIn"
                    width: Lumi.editorMiniButtonSize
                    height: width
                    radius: Lumi.controlRadius
                    color: Lumi.controlHoverFill
                    padding: 0
                    onClicked: viewport.zoomBy(Lumi.editorZoomStep)

                    Rin.Icon {
                        anchors.centerIn: parent
                        icon: "ic_fluent_add_20_regular"
                        size: 16
                        color: Lumi.textPrimary
                    }
                }
            }

            Rin.Text {
                objectName: "editorZoomMode"
                anchors.left: zoomRow.right
                anchors.leftMargin: 10
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: zoomRow.verticalCenter
                typography: Rin.Typography.Caption
                color: Lumi.textTertiary
                elide: Text.ElideRight
                text: editorWindow.autoScale ? qsTr("自动适应") : qsTr("手动档位")
            }
        }
    }
}
