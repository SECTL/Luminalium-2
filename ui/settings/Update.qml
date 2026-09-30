import QtQuick
import RinUI as Rin

/*!
    检查更新：**目前刻意留空**。

    2026-10-01 用户指令：「更新界面留空」。原来的「当前版本 / 更新渠道
    （稳定版 / 预览版）」全是占位说明，更新通道尚未接入，放着的按钮点了
    也没有真实行为，所以整页清空，等真正接入更新源再填。
*/
Rin.FluentPage {
    id: page

    title: qsTr("检查更新")
}
