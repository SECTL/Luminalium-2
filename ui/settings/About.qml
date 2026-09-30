import QtQuick
import RinUI as Rin

/*!
    关于：**目前刻意留空**。

    2026-10-01 用户指令：「关于界面留空」。原来的 banner + logo + 版本号 +
    「组成」三张卡片（界面框架 / 放映控制 / 配置文件）已全部移除；版本号在
    快捷面板的标题栏与开发水印里都能看到，不需要关于页再复述一遍。

    以后要填内容时注意：``resources/banner.png`` 与 ``logo.svg`` 仍在，
    取绝对 URL 走 ``Backend.resourceFile("...")``（QML 的 ``Image.source``
    不吃相对路径）。
*/
Rin.FluentPage {
    id: page

    title: qsTr("关于")
}
