import QtQuick
import RinUI as Rin

/*!
    主界面：**目前刻意留空**。

    2026-10-01 用户指令：「把『外观』改成『主界面』」—— 导航项由「外观」改名
    而来，同时原页面里的**主题模式 / 强调色 / 界面语言**三张卡整体挪去了
    「通用」页（那三项是全局外观设定，不属于「主界面」这个概念）。

    本页留空，专放**主界面本身**的设定；主界面的可视化编辑走独立窗口
    ``ui/MainInterfaceEditor.qml``（由快捷面板的「主界面编辑器」快捷方式打开）。

    留空时不写任何子项：``Rin.FluentPage`` 的内容层是 default property
    （``freeContainter``），没有子项就是干净的一页，不需要占位符 ——
    与 ``Home.qml`` / ``About.qml`` / ``Update.qml`` 同一惯例。

    ⚠️ 本文件原名 ``Appearance.qml``。改名是安全的：设置页路径只被
    ``Settings.qml`` 的 ``navigationItems`` 与 ``default_config.json`` 里的
    ``shortcut_catalog`` 动作引用，两处都在仓库内、已同批更新；
    用户配置只存「启用了哪些快捷方式 id」，不存页面路径。
*/
Rin.FluentPage {
    id: page

    title: qsTr("主界面")
}
