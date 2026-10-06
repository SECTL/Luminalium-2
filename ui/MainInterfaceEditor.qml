import QtQuick
import QtQuick.Layouts
// 编辑态暗罩要按**组件的形状**挖洞（`Shape` + `ShapePath` 的奇偶填充），
// 四块 Rectangle 拼出来的矩形洞已经不够用了 —— 2026-10-01 第八轮。
import QtQuick.Shapes
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
    | 预览区 | 只有画面 | 右上角多一枚悬浮缩放缓（``EditorZoomBar``） |

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
    底色**实色**（``Lumi.editorPanelBg``），**两段式**：设置项区（可滚动，按选中的
    组件摆）/ 下部常驻条（组件信息）；出口是**左沿中线上那枚圆按钮**
    （``inspectorHandle``，圆心压在面板左沿，与 Esc 同一个动作）。

    2026-10-01（第六轮）用户指令「把返回按钮删掉 加一个圆按钮放在侧面板的中部，
    缩放作为一个悬浮组件放在左侧的主界面预览区域」之后：顶部那条只放返回键的
    ``inspectorNav`` 整条撤掉、常驻条只剩一行读数（84 → 48）、缩放缓搬去预览区
    上的浮出层（``ui/Luminalium/EditorZoomBar.qml``）。

    设置项**跟着选中的组件变**（2026-10-01 三项）：

    * 工具栏 → 「显示按钮文本」（``presentation.buttons.show_labels``）、
      「退出键样式」（``presentation.exit.style``，从设置 → 放映页搬来）；
    * 翻页组件 → 「翻页组件位置」（``presentation.pager.position``：竖版两侧中间
      / 横版两侧下部，二选一 —— 后端顺带开关 ``corners`` 里那四个角）。

    2026-10-05 插件系统 Wave 2 任务 10：三项设置**不再是硬编码的
    InspectorSetting 块**，改为描述符驱动 —— 注册表条目的
    ``inspector_items``（形状 ``{key, kind, title, description?, options?,
    visible_when_group?}``，字段语义与注册侧校验见 ``registry.py`` 头注释
    第 7 条）经 ``Backend.presentationGroups`` 进来，``inspectorRepeater``
    取「选中角各组的并集」按 ``kind``（``switch`` / ``combo`` / ``radio``，
    能力上限与原三项严格对齐）分发渲染，值读写走
    ``Backend.settings.<key>`` / ``Backend.setSetting(...)``。这是插件往
    编辑器暴露设置项的唯一通道（插件不需要碰本文件）。

    2026-10-05 插件系统 Wave 2 任务 9：「这条是什么组件」的判定（组件名 / 图标 /
    有无工具栏语义、翻页语义）**不再由组名硬编码 if 链推导**，唯一事实来源是
    插件注册表 —— QML 侧经 ``Backend.presentationGroups`` 读
    ``registry.editor_groups()``（内建组登记见
    ``windows.py::_register_builtin_groups``）。组全都不认识的角落回落
    「控制条」并 ``console.warn``，不崩（与真机侧孤儿容忍同款）。

    两项改完**预览与真机同时变**（配置广播 → 预览副本重建、真机侧重建控制条）。

    「编辑态压暗」盖的是**面板左边的整块区域**（见 ``dimMask``），不是只盖屏幕 ——
    否则视口四周那圈留白会露出没压暗的亚克力。挖出来的「洞」是**选中组件自己的
    形状**（圆角矩形 / 胶囊），不是粗略的矩形排除。

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
    //
    // 2026-10-05 插件系统 Wave 2 任务 9：组件语义**不再由组名硬编码推导**
    // （原来那串 ``groups.indexOf("tools")`` if 链已删），注册表是唯一事实来源
    // —— 经 ``Backend.presentationGroups``（``registry.editor_groups()`` 的
    // 列表视图，条目形状 ``{name, display_name, icon, dock_qml?, traits,
    // inspector_items}``，注册时机见 ``windows.py::_register_builtin_groups``）。
    // 插件注册的组由此能以「有名字的组件」出现在编辑器里。

    /*! 某个角落启用了哪些区块（组名列表，内建是 tools / actions / pager / exit，
        插件组名由插件自定）。 */
    function groupsOf(cornerName) {
        var config = Backend.presentationConfig
        var corners = config && config.corners !== undefined ? config.corners : ({})
        var entry = corners[cornerName]
        return (entry !== undefined && entry.groups !== undefined) ? entry.groups : []
    }

    /*! 按组名查注册表条目；未登记返回 ``undefined``。 */
    function groupEntry(groupName) {
        var all = Backend.presentationGroups
        for (var i = 0; i < all.length; ++i) {
            if (all[i].name === groupName)
                return all[i]
        }
        return undefined
    }

    /*! 角落 groups 中**首个**在注册表里有条目的组 —— 组件身份的解析入口。
        顺序敏感：groups 数组里靠前的组优先，与 ``windows.py::_resolve_dock_qml``
        的「首个匹配胜出」同一条思路。全部未知返回 ``undefined``。 */
    function cornerGroupEntry(cornerName) {
        var groups = groupsOf(cornerName)
        for (var i = 0; i < groups.length; ++i) {
            var entry = groupEntry(groups[i])
            if (entry !== undefined)
                return entry
        }
        return undefined
    }

    /*! 角落的组里有没有带指定语义标记（``traits`` 键）的注册组。 */
    function cornerHasTrait(cornerName, traitName) {
        var groups = groupsOf(cornerName)
        for (var i = 0; i < groups.length; ++i) {
            var entry = groupEntry(groups[i])
            if (entry !== undefined && entry.traits !== undefined
                    && entry.traits[traitName] === true)
                return true
        }
        return false
    }

    /*! 组件名。首个注册组的 traits 含 ``toolbar`` → 「工具栏」；含 ``pager``
        → 「翻页组件」；都不含（插件组）→ 注册表条目的 ``display_name``。
        内建布局下与旧 if 链逐字一致（内建组没有混摆 toolbar / pager 的角落）；
        groups 全部未登记（手改 config / 插件卸载残留）→ 回落「控制条」并警告，
        与真机侧 ``_resolve_dock_qml`` 的孤儿容忍同款。 */
    function componentName(cornerName) {
        if (!cornerName || cornerName.length === 0)
            return ""
        var entry = cornerGroupEntry(cornerName)
        if (entry === undefined) {
            console.warn("MainInterfaceEditor: 角落", cornerName,
                         "的组全部未在注册表登记，组件名回落「控制条」")
            return qsTr("控制条")
        }
        var traits = entry.traits !== undefined ? entry.traits : ({})
        if (traits.toolbar === true)
            return qsTr("工具栏")
        if (traits.pager === true)
            return qsTr("翻页组件")
        return entry.display_name
    }

    /*! 组件图标 —— 与 ``componentName`` 同一套判别：toolbar / pager 沿用
        内建图标；插件组用注册表条目自己的 ``icon``；未知组回落默认图标
        （警告在 ``componentName`` 里打过了，这里不重复打）。 */
    function componentIcon(cornerName) {
        var entry = (cornerName && cornerName.length > 0)
                ? cornerGroupEntry(cornerName) : undefined
        if (entry === undefined)
            return "ic_fluent_options_20_regular"
        var traits = entry.traits !== undefined ? entry.traits : ({})
        if (traits.toolbar === true)
            return "ic_fluent_options_20_regular"
        if (traits.pager === true)
            return "ic_fluent_chevron_left_20_regular"
        return entry.icon
    }

    function cornerLabel(cornerName) {
        return cornerLabels[cornerName] !== undefined ? cornerLabels[cornerName] : cornerName
    }

    /*! 检查器列表 = 选中角**各组**的 ``inspector_items`` 并集（2026-10-05
        插件系统 Wave 2 任务 10）：原先三个硬编码 InspectorSetting 已删，
        改由注册表描述符驱动（``inspectorRepeater`` 的模型）。顺序 = 组在
        corner groups 里的出现顺序、组内保持注册顺序；同一 ``key`` 去重
        （同一描述符被同角多个组重复携带时只渲染一次）。描述符带
        ``visible_when_group`` 时，仅当选中角的 groups 含该组才收录。

        内建角落的 groups 配置下，与重构前的 trait 显隐（``selectedHasToolbar``
        / ``selectedHasPager``，已随本任务移除）逐项一致：下中部角
        （tools/actions/exit）→ 「显示按钮文本」+「退出键样式」；
        翻页角（pager）→ 「翻页组件位置」。 */
    readonly property var selectedInspectorItems: {
        var result = []
        if (selectedCorner.length === 0)
            return result
        var groups = groupsOf(selectedCorner)
        var seen = ({})
        for (var i = 0; i < groups.length; ++i) {
            var entry = groupEntry(groups[i])
            if (entry === undefined || entry.inspector_items === undefined)
                continue
            var items = entry.inspector_items
            for (var j = 0; j < items.length; ++j) {
                var item = items[j]
                if (item === undefined || item.key === undefined || seen[item.key])
                    continue
                if (item.visible_when_group !== undefined
                        && groups.indexOf(item.visible_when_group) < 0)
                    continue
                seen[item.key] = true
                result.push(item)
            }
        }
        return result
    }

    /*! 描述符的**当前值**：默认读扁平设置键（``Backend.settings[key]``）。

        ⚠️ 例外 ``presentation_pager_position``：显示要跟随**真实生效的
        corners**（``pagerPositionIndex`` 由 corners 反推，配置里的
        ``pager.position`` 只是它的影子 —— 理由见 ``pagerPositionIndex``
        的注释）。这是重构前那两枚 RadioButton 的既有读法，描述符化不能
        把它退回读影子值。 */
    function inspectorCurrentValue(key) {
        if (key === "presentation_pager_position")
            return pagerPositionIndex === 1 ? "bottom" : "side"
        return Backend.settings[key]
    }

    /*! ``combo`` 描述符的下拉文案列表（``options[].label``）。 */
    function inspectorOptionLabels(descriptor) {
        var labels = []
        var options = descriptor.options !== undefined ? descriptor.options : []
        for (var i = 0; i < options.length; ++i)
            labels.push(options[i].label)
        return labels
    }

    /*! ``combo`` 描述符的当前选中下标（按 ``options[].value`` 匹配当前值，
        找不到回落 0 —— 注册侧校验保证 options 非空）。 */
    function inspectorOptionIndex(descriptor) {
        var value = inspectorCurrentValue(descriptor.key)
        var options = descriptor.options !== undefined ? descriptor.options : []
        for (var i = 0; i < options.length; ++i) {
            if (options[i].value === value)
                return i
        }
        return 0
    }

    /*! 翻页组件位置下拉的选中项（0 = 竖版两侧中间，1 = 横版两侧下部）。

        **从真实生效的 ``corners`` 反推**，不是读 ``presentation.pager.position``：
        后者只是这个开关的影子（写的时候两者一起改），而用户手改配置只可能改到
        ``corners`` —— 「显示什么就代表屏幕上是什么」比显示那个影子值重要。
        四个角都关掉（等于把翻页栏藏起来）时才回落去读配置。 */
    readonly property int pagerPositionIndex: {
        var on = enabledCorners
        if (on.indexOf("middle_left") >= 0 || on.indexOf("middle_right") >= 0)
            return 0
        if (on.indexOf("bottom_left") >= 0 || on.indexOf("bottom_right") >= 0)
            return 1
        return Backend.settings.presentation_pager_position === "bottom" ? 1 : 0
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

    /*! 翻页组件换形态时的**对应角落**（竖版两侧 ↔ 横版下部）。
        竖版 ``middle_left`` 关掉、横版 ``bottom_left`` 打开，指的是**同一个**
        编辑对象 —— 切完形态还该停在它身上，不然用户刚点一下设置项面板就收了。 */
    function pagerCounterpart(cornerName) {
        if (cornerName === "middle_left")
            return "bottom_left"
        if (cornerName === "middle_right")
            return "bottom_right"
        if (cornerName === "bottom_left")
            return "middle_left"
        if (cornerName === "bottom_right")
            return "middle_right"
        return ""
    }

    /*! 配置重载后：选中的角落可能被关掉了，尺寸也可能变了。

        ⚠️ 角落被关掉时**先试对应形态**（翻页组件换位置就是这么一回事）：
        直接清空的话，用户点一下「翻页组件位置」面板就收起来了，看着像崩了。 */
    function refreshFromConfig() {
        if (selectedCorner.length === 0)
            return
        if (enabledCorners.indexOf(selectedCorner) < 0) {
            var counterpart = pagerCounterpart(selectedCorner)
            if (counterpart.length > 0 && enabledCorners.indexOf(counterpart) >= 0)
                selectCorner(counterpart)
            else
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
    //
    // 2026-10-01（第八轮）用户指令：「我希望压暗附近的时候不要只是粗略的矩形排除，
    // 而是除了那个组件以外的全压暗」—— 洞的形状从**矩形**换成了**组件自己的圆角
    // 形状**（见下面 ``editorDimShape`` 的说明）。
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
        // 洞的坐标是「相对暗罩」算出来的，洞越出视口时会溢出到面板 / 窗口外 ——
        // 裁掉（同时也是下面「洞退化时挪到画外」那条退路的兜底）。
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

        /*! 压暗本体 —— 铺满整块暗罩，中间按**选中组件的真实形状**挖洞。

            早先是**四块 ``Rectangle`` 拼出来的矩形洞**。可控制条的底板是**全圆
            胶囊**（``Lumi.dockSurfaceRadius`` = 999，由 ``FlyoutSurface`` 按短边
            钳成 高/2），于是画面里「选中描边是圆的、它外面那圈亮区却是方的」——
            四个角白亮出一大块，读起来就是个粗制滥造的矩形排除。

            现在改用**奇偶填充**（``ShapePath.OddEvenFill``）把洞减出来：一条外圈
            铺满、一条内圈是**与选中描边同心**的圆角矩形（半径 = 短边一半 = 胶囊），
            亮区就是组件自己的形状，其余**全**压暗。

            ⚠️ 外圈与内圈必须在**同一个** ``ShapePath`` 里才会相减 ——
            ``fillRule`` 是 ShapePath 级别的，拆成两个 ShapePath 只会叠出两块实心。 */
        Shape {
            id: dimShape
            objectName: "editorDimShape"
            anchors.fill: parent
            // 圆角走**解析曲线**渲染器：几何渲染器会把弧打散成折线，半径几十像素的
            // 圆角能看出棱角。
            preferredRendererType: Shape.CurveRenderer

            /*! 洞被夹没了（组件整个在视口外 —— 只在相机动画的过渡帧里可能出现）
                时把内圈挪到画布外：奇偶填充下它不参与「外圈内部」的计数，铺满的
                暗罩照旧完整。真跑到这一步罕见得很，纯属不留一个亮不起来的死角。 */
            readonly property bool holeValid: dimMask.holeW > 0.5 && dimMask.holeH > 0.5
            readonly property real pathHoleX: holeValid ? dimMask.holeX : -1000
            readonly property real pathHoleY: holeValid ? dimMask.holeY : -1000
            readonly property real pathHoleW: holeValid ? dimMask.holeW : 1
            readonly property real pathHoleH: holeValid ? dimMask.holeH : 1

            /*! 洞的圆角半径 = 短边一半（胶囊），与 ``selectionRing`` 同一套几何
                （那边也是 ``Math.min(width, height) / 2``）—— 于是描边与洞同心。
                镜像给自检读：``ShapePath`` 的子路径 Python 侧摸不到。 */
            readonly property real holeRadius: Math.min(pathHoleW, pathHoleH) / 2

            ShapePath {
                objectName: "editorDimPath"

                fillColor: "#000000"
                strokeColor: "transparent"
                fillRule: ShapePath.OddEvenFill

                // 外圈：铺满整块暗罩
                PathRectangle {
                    x: 0
                    y: 0
                    width: dimMask.width
                    height: dimMask.height
                    radius: 0
                }
                // 内圈：洞 —— 就是组件自己的形状（圆角矩形 / 胶囊）
                PathRectangle {
                    x: dimShape.pathHoleX
                    y: dimShape.pathHoleY
                    width: dimShape.pathHoleW
                    height: dimShape.pathHoleH
                    radius: dimShape.holeRadius
                }
            }
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
            拿「已钳制值」反推 ``panD*``。

            ⚠️ **编辑态额外放宽**（2026-10-01 第八轮用户指令：「我希望聚焦的时候其实
            那个组件可以在预览区的正中间，无论是否靠近边界」）：允许的区间里**恒含
            「取景目标居中」那一点**，于是右下角那条控制条也能精确落在视口正中。

            不放开的话贴边组件永远偏在一边 —— 「不许把画面拖出视口留出空档」这条
            钳制会先顶住位移，居中的需求根本排不上。放宽的幅度就**恰好是**「居中
            位移」本身（``lo = min(lo, base)``、``hi = max(hi, base)``），所以：
            聚焦一定居中，而拖动**再往外一步也不让**（画面不会整个飞出视口）。

            代价是画面会往左上越出去一截、视口里露出没画面的留白 —— 与 Figma
            聚焦画布边缘的对象时一个样子，是「居中优先」必然的样貌。 */
        function clampOriginX(value) {
            var content = screenWidth * stageScale
            var centered = (width - content) / 2
            var lo = content <= width ? centered : width - content
            var hi = content <= width ? centered : 0
            if (editorWindow.editing) {
                var base = baseOriginX()
                lo = Math.min(lo, base)
                hi = Math.max(hi, base)
            }
            return Math.min(hi, Math.max(lo, value))
        }

        function clampOriginY(value) {
            var content = screenHeight * stageScale
            var centered = (height - content) / 2
            var lo = content <= height ? centered : height - content
            var hi = content <= height ? centered : 0
            if (editorWindow.editing) {
                var base = baseOriginY()
                lo = Math.min(lo, base)
                hi = Math.max(hi, base)
            }
            return Math.min(hi, Math.max(lo, value))
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
        // ⚠️ 不能用 ``controlBorderColor``：深色档它是**黑 9%**，压在 #2C2C2C 的
        //    亚克力上等于没有 —— 屏幕框在深色下整条消失（用户 2026-10-01 反馈
        //    「整体的编辑器对暗色模式适配有点问题」里的其中一条）。
        border.color: Lumi.hairline
        z: 5

        /*! 描边色经 ``border`` 分组属性拿不到，复制一份给自检读。 */
        readonly property color frameBorderColor: border.color
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

    // ================================================== 预览区上的悬浮缩放缓
    //
    // 2026-10-01（第六轮）用户指令：「缩放作为一个悬浮组件放在左侧的主界面预览
    // 区域」。原先它长在右侧面板的下部常驻条里（和组件信息挤一行），现在整块搬
    // 出来，压在预览区上。组件本体见 ``ui/Luminalium/EditorZoomBar.qml``，这里
    // 只负责**摆**：
    //
    //   · 挂在**内容区**上、与视口是**兄弟** —— 不放进视口，是因为视口
    //     ``clip: true``，投影会被它的矩形裁成硬边；``anchors`` 取视口当基准
    //     是合法的（跨兄弟锚点）。
    //   · **右上角**、离视口上沿与右沿各 16（``editorZoomBarMargin``）。
    //     2026-10-01（第七轮）用户指令「缩放应该放在预览区右上方」—— 原先摆的
    //     是底边居中，那儿会跟「横版两侧下部」那类贴着屏幕下沿的翻页栏擦边。
    //   · ``z: 12`` —— 压在编辑态暗罩（10）之上、右侧面板（20）之下。
    //   · 只在编辑态出现（跟着 ``inspectorReveal`` 淡入淡出）：全景态相机恒为
    //     ``fitScale``，手动档位在那儿本来就不生效（见 ``viewport.stageScale``），
    //     摆一排按不动的按钮只会误导。
    EditorZoomBar {
        id: editorZoomBar
        objectName: "editorZoomBar"

        anchors.right: viewport.right
        anchors.top: viewport.top
        /*! 16 是量到**底板边缘**的视觉距离；组件盒子外面还留了投影余量
            （``shadowMargin``），所以这里把它扣掉 —— 与 ``FlyoutSurface``
            那套「margin 是视觉距离」的约定一致。 */
        anchors.rightMargin: 16 - editorZoomBar.shadowMargin
        anchors.topMargin: 16 - editorZoomBar.shadowMargin
        z: 12

        opacity: editorWindow.inspectorReveal
        visible: opacity > 0.004
        Behavior on opacity {
            NumberAnimation { duration: Lumi.editorAnimMs; easing.type: Easing.OutCubic }
        }

        percent: viewport.scalePercent
        autoMode: editorWindow.autoScale
        onZoomOutRequested: viewport.zoomBy(1 / Lumi.editorZoomStep)
        onZoomInRequested: viewport.zoomBy(Lumi.editorZoomStep)
        onResetRequested: viewport.resetZoom()
    }

    // ========================================================== 右侧设置面板
    //
    // 编辑态的侧栏（2026-10-01 用户指令：「右侧的设置面板应该是实色背景，组件信息
    // 就放在右侧设置面板的下部始终置着展示：工具栏 318x62」；同日「（右上角那个 ×）
    // 加大移到左边改为返回按钮」+「删掉」顶部那块设置项标题与占位文案）。**两段式**：
    //
    //   · 中部 —— **设置项区**（``inspectorBody``，可滚动，按选中的组件摆）；
    //   · 下部 —— **常驻条**（``inspectorFooter``，不滚动）：组件信息
    //     「工具栏 318 × 62」。
    //
    // 2026-10-01（第六轮）用户指令：「把返回按钮删掉 加一个圆按钮放在侧面板的中部，
    // 缩放作为一个悬浮组件放在左侧的主界面预览区域」。于是：
    //
    //   · 顶部那条 ``inspectorNav``（只有一枚返回键 + 一条分隔线）**整条撤掉** ——
    //     面板回到**两段式**：设置项区 + 常驻条；
    //   · 出口改成**左沿中线上的圆按钮**（``inspectorHandle``，圆心压在面板左沿上，
    //     一半悬在舞台上，读作「把面板收回去」的把手），动作仍是 ``clearSelection``
    //     （与 Esc 同一个出口）；
    //   · 缩放缓搬去**预览区上的浮出层**（``EditorZoomBar``），常驻条只剩
    //     「现在在编谁」那行读数，高度 84 → 48。
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

            /*! 左沿 1px 分隔线 —— 面板与舞台之间要有一条边。
                ⚠️ 用 ``Lumi.hairline`` 而不是 ``panelCardBorder``：后者深色档是
                黑 10%，压在 #303030 的面板上等于没有（用户 2026-10-01 反馈
                「暗色模式适配」时查出来的其中一条）。 */
            Rectangle {
                objectName: "editorInspectorEdge"
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: Lumi.hairline
            }
        }

        // -------------------------------------------------- 左沿中线的圆按钮
        //
        // 面板唯一的出口：与 Esc 同一个动作（``clearSelection``）。
        //
        // 2026-10-01（第六轮）用户指令：「把返回按钮删掉 加一个圆按钮放在侧面板的
        // 中部」。原先它是顶部导航条上那枚 40px 的**方形**返回键 —— 本轮把整条
        // ``inspectorNav`` 撤掉，换成这枚**正圆**、**圆心压在面板左沿**、**垂直
        // 居中**的按钮：一半悬在舞台上，读作「把面板收回去」的把手。
        //
        // ⚠️ ``x: -width / 2`` 是刻意的**负值** —— 面板是 ``Item`` 且不 ``clip``，
        //    悬出去的那一半才画得出来。别为了「不越界」把它挪进面板里：那样它就
        //    压在设置项上了（中部正是设置项区）。
        //
        // ⚠️⚠️ ``z: 1`` **不能省**。它下面（``y`` 中线上）正好压着**设置项区**
        //    （``inspectorBody``，一只 ``Flickable``），而那个 Flickable 是**后
        //    声明**的 —— 后声明者在同一父级里叠得更上，于是它会把这枚按钮的右半边
        //    （**连圆心在内**）的鼠标事件全部吃掉。症状特别阴：按钮画得好好的、
        //    ``isVisible()`` 也是 True、``onClicked`` 就是不触发，点上去**什么都
        //    不发生**（自检里「点面板左沿的圆按钮 → 退出编辑态」那条就是这么抓到
        //    的）。Flickable 自己会抢按下来做拖动，所以事件也不会继续往下传。
        Rin.Clip {
            id: inspectorHandle
            objectName: "editorInspectorHandle"

            width: Lumi.editorPanelHandleSize
            height: width
            x: -width / 2
            y: Math.round((parent.height - height) / 2)
            z: 1
            // 圆心压在左沿上 → 半径即圆角，读作正圆。
            radius: width / 2
            color: Lumi.editorPanelBg
            border.width: 1
            // 同「面板左沿那条线」：深色下 ``panelCardBorder`` 会消失。
            border.color: Lumi.hairline
            padding: 0
            // 和 Esc 同一个出口
            onClicked: editorWindow.clearSelection()

            /*! 描边色经 ``border`` 分组属性拿不到，复制一份给自检读。 */
            readonly property color handleBorderColor: border.color

            /*! 图标指向面板收起的方向（向右滑出）。 */
            Rin.Icon {
                objectName: "editorInspectorHandleIcon"
                anchors.centerIn: parent
                icon: "ic_fluent_chevron_right_20_regular"
                size: 20
                color: Lumi.textPrimary
            }
        }

        // ------------------------------------------------------------ 设置项区
        //
        // 面板顶端之下、下部常驻条之上，**整块**留给设置项（可滚动）。
        // 设置项是**描述符驱动**的 Repeater（2026-10-05 任务 10）：模型是选中角
        // 各组 ``inspector_items`` 的并集（``selectedInspectorItems``），
        // 选中组件一变模型就跟着变，不再逐项绑 ``visible``。
        //
        // 2026-10-01（第六轮）：顶部导航条撤掉后，这里**顶到面板自己的上沿**
        // （``anchors.top: parent.top``）—— 面板之外就是标题栏，间距靠
        // ``bodyColumn.y`` 自己留。
        Flickable {
            id: inspectorBody
            objectName: "editorInspectorBody"

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: inspectorFooter.top
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentHeight: bodyColumn.implicitHeight + 36

            /*! 设置项的落点：``x/y`` 与 ``width`` 已经排好版，往里加设置项即可。

                2026-10-01（第五轮）：间距 8 → **18**。改平铺版式之后设置项之间
                没有卡片底板隔着，8 会让「上一项的控件」和「下一项的名称」糊成
                一组；18 是把「名称 8 控件」的组内间距（``InspectorSetting.itemSpacing``）
                的两倍多一点，组的边界一眼看得出来。 */
            ColumnLayout {
                id: bodyColumn
                x: 16
                // 面板顶端不再有导航条挡着，第一项的名称要自己留出与窗口标题栏的
                // 呼吸量（14 → 18），下面 ``contentHeight`` 也同步改成 +36。
                y: 18
                width: parent.width - 32
                spacing: 18

                /*! 检查器项：**描述符驱动**（2026-10-05 插件系统 Wave 2 任务 10，
                    取代原先三个硬编码 InspectorSetting）。模型 = 选中角各组
                    ``inspector_items`` 的并集（``selectedInspectorItems``），
                    ``kind`` 分发到三种控件 —— 与原三项的能力上限严格对齐：

                      ``switch`` —— 布尔开关（原「显示按钮文本」）；
                      ``combo``  —— 下拉（原「退出键样式」）；
                      ``radio``  —— 单选组（原「翻页组件位置」）。

                    值读写统一走 ``Backend.settings.<key>`` /
                    ``Backend.setSetting(...)``（读入口 ``inspectorCurrentValue``
                    保留了「翻页组件位置跟随 corners 反推」的既有特例）。

                    ⚠️ 三种控件在用户交互后都用 ``Qt.binding`` **重装**被点击
                    打断的绑定（坑与解法见 ``ui/settings/General/Index.qml``
                    「开机自启」开关的注释：控件内部 setChecked 会摘掉 QML
                    绑定）。动态创建的控件尤其需要 —— 配置被别的写入方改动、
                    或写入被后端拒绝时，控件必须能跟着设置值回弹。 */
                Repeater {
                    id: inspectorRepeater
                    objectName: "editorInspectorRepeater"

                    model: editorWindow.selectedInspectorItems

                    delegate: InspectorSetting {
                        id: inspectorItem
                        objectName: "editorInspectorItem_" + descriptor.key

                        required property var modelData
                        readonly property var descriptor: modelData

                        title: descriptor.title !== undefined
                               ? String(descriptor.title) : ""
                        description: descriptor.description !== undefined
                                     ? String(descriptor.description) : ""

                        // kind == "switch"：布尔开关。
                        Rin.Switch {
                            objectName: "editorInspectorSwitch_"
                                        + inspectorItem.descriptor.key
                            visible: inspectorItem.descriptor.kind === "switch"
                            primaryColor: Lumi.accent
                            // 「开 / 关」状态字走 RinUI Switch 自带的 checkedText /
                            // uncheckedText —— 别再挂 Rin.Text（会跟默认的
                            // On/Off 并排出现）。
                            checkedText: qsTr("开")
                            uncheckedText: qsTr("关")
                            checked: editorWindow.inspectorCurrentValue(
                                         inspectorItem.descriptor.key) === true
                            onToggled: {
                                Backend.setSetting(
                                    inspectorItem.descriptor.key, checked)
                                checked = Qt.binding(function () {
                                    return editorWindow.inspectorCurrentValue(
                                        inspectorItem.descriptor.key) === true
                                })
                            }
                        }

                        // kind == "combo"：下拉。定宽 200（两个选项的名字都能
                        // 完整显示，与重构前一致）。
                        Rin.ComboBox {
                            objectName: "editorInspectorCombo_"
                                        + inspectorItem.descriptor.key
                            visible: inspectorItem.descriptor.kind === "combo"
                            Layout.preferredWidth: 200
                            model: editorWindow.inspectorOptionLabels(
                                       inspectorItem.descriptor)
                            currentIndex: editorWindow.inspectorOptionIndex(
                                              inspectorItem.descriptor)
                            onActivated: {
                                Backend.setSetting(
                                    inspectorItem.descriptor.key,
                                    inspectorItem.descriptor.options[currentIndex].value)
                                currentIndex = Qt.binding(function () {
                                    return editorWindow.inspectorOptionIndex(
                                        inspectorItem.descriptor)
                                })
                            }
                        }

                        // kind == "radio"：单选组（每个选项一枚 RadioButton，
                        // 「指示器 + 文字」一行一枚的平铺排法）。整组包进一只
                        // Column —— 它只占 controlColumn 的一个布局格；内层
                        // Repeater 直接进布局会多占一格间距。
                        Column {
                            visible: inspectorItem.descriptor.kind === "radio"
                            spacing: 6

                            Repeater {
                                model: inspectorItem.descriptor.kind === "radio"
                                       ? inspectorItem.descriptor.options : []

                                delegate: Rin.RadioButton {
                                    id: inspectorRadio
                                    objectName: "editorInspectorRadio_"
                                                + inspectorItem.descriptor.key + "_"
                                                + modelData.value

                                    required property var modelData

                                    primaryColor: Lumi.accent
                                    text: modelData.label
                                    checked: editorWindow.inspectorCurrentValue(
                                                 inspectorItem.descriptor.key)
                                             === modelData.value
                                    onClicked: {
                                        Backend.setSetting(
                                            inspectorItem.descriptor.key,
                                            modelData.value)
                                        checked = Qt.binding(function () {
                                            return editorWindow.inspectorCurrentValue(
                                                       inspectorItem.descriptor.key)
                                                   === inspectorRadio.modelData.value
                                        })
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ------------------------------------------------------------ 常驻条
        //
        // 「现在在编谁、它多大一块」—— 一行读数，常显不滚动。
        //
        // 2026-10-01（第六轮）：缩放缓搬去预览区的浮出层（``EditorZoomBar``），
        // 这里只剩组件信息一行，于是从「上行读数 + 下行缩放缓」的两行收到**一行**
        // （高度 84 → 48，居中摆）。
        Item {
            id: inspectorFooter
            objectName: "editorInspectorFooter"

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: Lumi.editorPanelFooterHeight

            Rectangle {
                objectName: "editorFooterEdge"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                // 同面板左沿那条线：深色下 ``panelCardBorder`` 会消失。
                color: Lumi.hairline
            }

            // ---- 组件信息：名字（左）+ 自身尺寸（右）
            Item {
                id: footerInfoRow
                objectName: "editorFooterInfoRow"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                anchors.rightMargin: 16
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
        }
    }
}
