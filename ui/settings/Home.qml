import QtQuick
import RinUI as Rin

/*!
    设置首页：**目前刻意留空**。

    2026-10-01 用户指令：「设置的主页目前留空」。原内容（放映状态卡片 /
    主题摘要 / 快捷入口开关）已全部移除 —— 那些入口分别有各自的设置页，
    首页再复述一遍只会产生两处要同步维护的同一份状态。

    留空时不写任何子项：``Rin.FluentPage`` 的内容层是 default property
    （``freeContainter``），没有子项就是干净的一页，不需要占位符。

    以后要放什么，直接往这里加卡片即可；页面本身仍挂在导航第一项，
    配置里的 ``settings.default_page`` 也仍指向本文件。
*/
Rin.FluentPage {
    id: page

    title: qsTr("主页")
}
