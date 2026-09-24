import QtQuick
import QtQuick.Window
import RinUI as Rin

/*!
    设置窗口。

    结构照搬 **Class Widgets 2** 的 ``Windows/Settings.qml``：

    * ``Rin.FluentWindow`` —— 自带标题栏 / 左侧导航 / 内容层圆角；
    * ``navigationItems`` —— 每项 ``{ title, page, icon, subItems, position }``，
      ``page`` 必须是**绝对 URL**：``NavigationView`` 内部用 ``Qt.createComponent``
      加载，相对路径会以 RinUI 模块自身为基准而找不到文件，所以统一走
      ``Qt.resolvedUrl``；
    * 页面本体是 ``Rin.FluentPage``：``title`` 走页面头部，内容默认进一个带
      左右留白的 ``ColumnLayout``；
    * ``position: Rin.Position.Bottom`` 的项（关于 / 检查更新）钉在导航底部。

    关闭按钮只隐藏窗口，不销毁 —— 桌面常驻应用里重建一个窗口没有必要。
*/
Rin.FluentWindow {
    id: settingsWindow

    property var settingsCfg: Backend.settingsConfig !== undefined
        ? Backend.settingsConfig : ({})

    readonly property real widthRatio: settingsCfg.width_ratio !== undefined
        ? settingsCfg.width_ratio : 0.5
    readonly property real heightRatio: settingsCfg.height_ratio !== undefined
        ? settingsCfg.height_ratio : 0.6

    title: qsTr("Luminalium 2 设置")
    visible: false
    width: Math.min(Screen.width - 80, Math.max(900, Screen.width * widthRatio))
    height: Math.min(Screen.height - 120, Math.max(600, Screen.height * heightRatio))
    minimumWidth: settingsCfg.minimum_width !== undefined ? settingsCfg.minimum_width : 680
    minimumHeight: settingsCfg.minimum_height !== undefined ? settingsCfg.minimum_height : 480

    // 标题只由左侧导航栏承担：``titleEnabled: false`` 关掉 ``FluentWindow``
    // 自绘标题栏里的「图标 + 文字」，否则窗口标题会出现两次。
    titleEnabled: false

    // ``NavigationView`` 的导航栏在窗口宽度低于 ``minimumExpandWidth``（默认 900）
    // 时会**自动收成图标条**。设置窗口通常不到 900 逻辑像素宽，所以把阈值降下来
    // 让它保持展开；导航栏宽度沿用动态模式（``expandWidth`` 默认 0）。
    navigationView.navMinimumExpandWidth: 640

    onClosing: function (event) {
        event.accepted = false
        Backend.closeSettings()
    }

    /*! **去掉 Win32 原生边框，只用 RinUI 自绘边框。**

        ``Rin.FluentWindowBase`` 在 Windows 上的 ``Component.onCompleted`` 里会
        **主动摘掉** ``Qt.FramelessWindowHint`` 并调
        ``WinEventManager.syncWindowFrame()``，后者直接用 Win32 API 给窗口加上
        ``WS_CAPTION | WS_THICKFRAME``（换系统阴影 / 贴边 / 最大化动画）。
        代价就是窗口外圈有一层系统画的边框，与本项目的自绘标题栏叠在一起。

        QML 里**派生组件的 ``Component.onCompleted`` 晚于基类**，所以这里
        能把 frameless 加回去；Qt 重建窗口样式时不会再带 ``WS_CAPTION``。
    */
    Component.onCompleted: {
        flags = flags | Qt.FramelessWindowHint
    }

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
            title: qsTr("通用"),
            page: Qt.resolvedUrl("settings/General/Index.qml"),
            icon: "ic_fluent_settings_20_regular",
            subItems: [
                {
                    title: qsTr("外观"),
                    page: Qt.resolvedUrl("settings/General/Appearance.qml"),
                    icon: "ic_fluent_paint_brush_20_regular"
                },
                {
                    title: qsTr("行为"),
                    page: Qt.resolvedUrl("settings/General/Behavior.qml"),
                    icon: "ic_fluent_cursor_20_regular"
                }
            ]
        },
        {
            title: qsTr("放映控制"),
            page: Qt.resolvedUrl("settings/Presentation.qml"),
            icon: "ic_fluent_slide_play_20_regular"
        },
        {
            title: qsTr("快捷面板"),
            page: Qt.resolvedUrl("settings/QuickPanelSettings.qml"),
            icon: "ic_fluent_apps_list_20_regular"
        },
        {
            title: qsTr("关于"),
            page: Qt.resolvedUrl("settings/About.qml"),
            icon: "ic_fluent_info_20_regular",
            position: Rin.Position.Bottom
        },
        {
            title: qsTr("检查更新"),
            page: Qt.resolvedUrl("settings/Update.qml"),
            icon: "ic_fluent_arrow_sync_20_regular",
            position: Rin.Position.Bottom
        }
    ]
}
