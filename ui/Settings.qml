import QtQuick
import QtQuick.Window
import RinUI as Rin

/*!
    设置窗口。

    结构照搬 **Class Widgets 2** 的 ``Windows/Settings.qml``：

    * ``Rin.FluentWindow`` —— 自带标题栏 / 左侧导航 / 内容层圆角；
    * ``navigationItems`` —— 每项 ``{ title, page, icon, position }``（还支持
      ``subItems`` 折叠子项，本项目目前没用到），``page`` 必须是**绝对 URL**：
      ``NavigationView`` 内部用 ``Qt.createComponent`` 加载，相对路径会以 RinUI
      模块自身为基准而找不到文件，所以统一走 ``Qt.resolvedUrl``；
    * 页面本体是 ``Rin.FluentPage``：``title`` 走页面头部，内容默认进一个带
      左右留白的 ``ColumnLayout``；
    * ``position: Rin.Position.Bottom`` 的项（关于 / 更新）钉在导航底部。
      调试项**不在导航里** —— 2026-09-30 起它是独立窗口（``DebugWindow.qml``），
      入口是连点左上角标题文本 10 次，见文件末尾的 ``debugTitleHotspot``。

    关闭按钮只隐藏窗口，不销毁 —— 桌面常驻应用里重建一个窗口没有必要。
*/
Rin.FluentWindow {
    id: settingsWindow

    property var settingsCfg: Backend.settingsConfig !== undefined
        ? Backend.settingsConfig : ({})

    readonly property real widthRatio: settingsCfg.width_ratio !== undefined
        ? settingsCfg.width_ratio : 0.64
    readonly property real heightRatio: settingsCfg.height_ratio !== undefined
        ? settingsCfg.height_ratio : 0.68

    /*! 尺寸：按屏幕比例算，宽高各自取「比例值」与「硬下限」的较大者，再被
        「屏幕尺寸 − 留白」夹住。

        ⚠️ 那两组数字（``0.64`` / ``0.68`` 与 ``1000`` / ``640``）是**成对**的，
        改一个要想着另一个：下限是给小屏的兜底 —— 1366×768 上比例值（874×522）
        比下限还小，实际开出来就是 1000×640。2026-10-01 用户指令「默认尺寸宽高
        大一些，横纵比例大一些」把两对都抬了（原值 0.5/0.6 + 900/600）。

        1920×1080 上：``0.64`` → 1229 宽、``0.68`` → 734 高，比 1.674
        （原值 960×648 = 1.481）。1366×768 上：1000×640 = 1.5625。
        **本机**（1755×987 逻辑像素）→ 1123×671，比 1.674。
        ``preview.py`` 的 ``PAGE_WIDTH`` 是对齐**真机页面内容列**（本机实测 807）
        而不是窗口宽度，所以那边默认是 961 —— 换显示器 / 改这里的比例后两处都要重算。
        真实值由 ``config/default_config.json`` 的 ``settings.width_ratio`` 等覆盖。 */
    title: qsTr("设置")
    visible: false
    width: Math.min(Screen.width - 80, Math.max(1000, Screen.width * widthRatio))
    height: Math.min(Screen.height - 120, Math.max(640, Screen.height * heightRatio))
    minimumWidth: settingsCfg.minimum_width !== undefined ? settingsCfg.minimum_width : 820
    minimumHeight: settingsCfg.minimum_height !== undefined ? settingsCfg.minimum_height : 560

    // 标题只由左侧导航栏承担：``titleEnabled: false`` 关掉 ``FluentWindow``
    // 自绘标题栏里的「图标 + 文字」，否则窗口标题会出现两次。
    titleEnabled: false

    // ``NavigationView`` 的导航栏在窗口宽度低于 ``minimumExpandWidth``（默认 900）
    // 时会**自动收成图标条**。设置窗口现在默认开 1229 宽（远大于 900），但最小可拖到
    // 820（``settings.minimum_width``），仍是比 900 窄 —— 不降阈值的话，一缩小就
    // 变成图标条。所以保留 640 这个兜底（低于它才收）。导航栏宽度沿用动态模式
    // （``expandWidth`` 默认 0）。
    navigationView.navMinimumExpandWidth: 640

    onClosing: function (event) {
        event.accepted = false
        Backend.closeSettings()
    }

    /*! **原生边框交给 RinUI 管，QML 侧不再干预 ``flags``。**

        ``Rin.FluentWindowBase`` 在 Windows 上会摘掉 ``FramelessWindowHint``、
        加回 ``WS_CAPTION | WS_THICKFRAME``，再由 ``WinEventFilter`` 处理
        ``WM_NCCALCSIZE`` 把非客户区压掉 —— 这样既有 RinUI 自绘标题栏，又保住
        DWM 的系统阴影、圆角、8px resize 边框与贴边（Snap）。

        这里原先有一行 ``flags = flags | Qt.FramelessWindowHint`` 用来挡掉原生
        标题栏，那是**窗口没被 RinUI 接管**时的兜底：没人处理 ``WM_NCCALCSIZE``，
        ``WS_CAPTION`` 就真的画出一条标题栏压在自绘标题栏上。2026-09-30 起
        Python 侧（``WindowManager._attach_to_rinui``）会把本窗口补登记进 RinUI
        的三份名单，这个兜底反而会顺手把系统阴影一起挡掉，故移除。
        若接管失败，Python 侧会自己退回 frameless（``_keep_frameless``）。
    */

    /*! 供 Python 侧 ``QMetaObject.invokeMethod`` 调用：跳到指定设置页。
        ``url`` 是 ``file:///`` 绝对地址（由 windows.py 拼好）。 */
    function openPage(url) {
        navigationView.push(url)
    }

    navigationItems: [
        {
            title: qsTr("主页"),
            page: Qt.resolvedUrl("settings/Home.qml"),
            icon: "ic_fluent_home_20_regular"
        },
        {
            // 2026-10-01：原先挂在「通用」下的子项「快捷面板」已删除
            // （尺寸与位置、显示内容那些开关），此项现在是叶子节点。
            title: qsTr("通用"),
            page: Qt.resolvedUrl("settings/General/Index.qml"),
            icon: "ic_fluent_settings_20_regular"
        },
        {
            // 2026-10-01 用户指令：导航项「外观」改名「主界面」，原页面里的
            // 主题 / 强调色 / 界面语言三张卡挪去了「通用」页；本页留空，
            // 专放主界面自己的设定（可视化编辑在独立的 MainInterfaceEditor 窗口）。
            title: qsTr("主界面"),
            page: Qt.resolvedUrl("settings/MainInterface.qml"),
            icon: "ic_fluent_window_20_regular"
        },
        {
            title: qsTr("放映"),
            page: Qt.resolvedUrl("settings/Presentation.qml"),
            icon: "ic_fluent_slide_play_20_regular"
        },
        {
            title: qsTr("关于"),
            page: Qt.resolvedUrl("settings/About.qml"),
            icon: "ic_fluent_info_20_regular",
            position: Rin.Position.Bottom
        },
        {
            title: qsTr("更新"),
            page: Qt.resolvedUrl("settings/Update.qml"),
            icon: "ic_fluent_arrow_sync_20_regular",
            position: Rin.Position.Bottom
        }
    ]

    // ========================================================== 隐藏入口：调试窗口
    // 2026-09-30 用户指令：「把调试菜单单独作为一个窗口打开，打开方式就是设置
    // 界面的标题文本连续按 10 次」。
    //
    // 标题文本是 RinUI ``NavigationBar`` 自绘的（``titleLabel.text`` ← 窗口
    // ``title``），它内部只把**文字**通过 ``windowTitle`` alias 暴露出来，
    // 拿不到那个 Text 对象，所以没法直接给它挂点击。改用一个**透明热区**压在
    // 它上面：点击穿透一样能落到热区（Text 默认不吃鼠标事件）。
    //
    // 热区挂在 ``titleBarLeadingHost`` —— 也就是 RinUI 塞标题行的那块**同一个
    // 坐标空间**（``TitleBar.leadingContentItem``）。那条标题行的排布是
    // ``[返回按钮 40][间距 16][图标 16][间距 16][标题文字]``（``NavigationBar``
    // 内部 ``Row { spacing: 16 }``），所以标题文字从 x = 40+16+16+16 = 88 起。
    // 热区取 x = 72（正好压在图标右边缘之后）起、220 宽，既完整盖住标题文字，
    // 又不会抢走返回按钮（0~40）和图标（56~72）的点击。
    //
    // ``z: -1`` 是刻意的：热区要待在标题行**下层**，只接住落在它范围内的点击，
    // 不改变任何既有交互的层级。
    readonly property int debugTitleHotspotX: 72
    readonly property int debugTitleHotspotWidth: 220

    /*! 连点计数。**「连续」= 停手 1.5s 就清零** —— 否则攒够十次会非常容易
        （正常使用里点标题旁边的空白也算）。 */
    property int debugTitleTapCount: 0
    /*! 达成条件（10 次）。自检会读它来验「热区够不够得着标题文字」。 */
    readonly property int debugTitleTapTarget: 10

    Timer {
        id: debugTitleTapReset
        interval: 1500
        onTriggered: settingsWindow.debugTitleTapCount = 0
    }

    /*! 记一次标题点击；连够 ``debugTitleTapTarget`` 次就开调试窗口。

        抽成**无参函数**（而不是把逻辑全写在 ``MouseArea.onClicked`` 里）是为了
        让自检能直接驱动这条路径 —— ``MouseArea`` 的 ``clicked`` 信号带一个
        ``QQuickMouseEvent*``，从 Python 侧 invoke 带 Qt 对象参数的信号是雷区
        （本项目在 ``closing(QQuickCloseEvent*)`` 上踩过直接崩），调无参函数则
        完全安全。 */
    function registerDebugTitleTap() {
        debugTitleTapCount += 1
        if (debugTitleTapCount >= debugTitleTapTarget) {
            debugTitleTapCount = 0
            debugTitleTapReset.stop()
            Backend.openDebugWindow()
        } else {
            debugTitleTapReset.restart()
        }
    }

    MouseArea {
        id: debugTitleHotspot
        objectName: "debugTitleHotspot"
        parent: settingsWindow.titleBarLeadingHost
        x: settingsWindow.debugTitleHotspotX
        y: 0
        width: settingsWindow.debugTitleHotspotWidth
        height: parent ? parent.height : 0
        z: -1
        onClicked: settingsWindow.registerDebugTitleTap()
    }

    // ============================================================ 开发水印
    // 内容区的左下角（导航栏右侧 —— 导航底部钉着「关于/检查更新」，不盖它们）。
    // 注意 navigationView 本身铺满整窗，**导航栏实际宽度**要用
    // ``navigationView.navigationBar.width``（公开 alias）。
    // 纯文字不吃点击。
    DevWatermark {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: navigationView.navigationBar.width + 16
        anchors.bottomMargin: 10
        z: 1000
    }
}
