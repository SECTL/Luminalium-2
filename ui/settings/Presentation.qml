import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    放映：放映**行为**相关的设定。

    ⚠️ 2026-10-01 用户指令：这一页的设置项已经**全部搬走**，当前刻意留空
    （与「主页 / 关于 / 更新」一样，是留白不是漏写）：

    * **水平边距 / 垂直边距 / 目标显示器 / 底板不透明度 / 投影** —— 它们调的都是
      「主界面长什么样」，搬去了**设置 → 主界面**页（``settings/MainInterface.qml``）；
    * **退出键样式** —— 属于「工具栏上的某个按钮长什么样」，搬去了
      **主界面编辑器 → 选中工具栏**的右侧设置面板（``MainInterfaceEditor.qml``）；
    * **组分隔线 / 页码切换** 两个开关已**删除**（不再有界面入口）。两个配置键
      ``presentation.divider.enabled`` / ``presentation.pager.enabled`` **仍然生效**
      （默认都是 true），只是改成纯配置项 —— 想关就在 ``config/config.json`` 里写。

    页面上剩下的放映行为项（轮询间隔等）在**调试窗口**里
    （隐藏入口：在设置窗口标题文本上连点 10 次）。

    更早（同日）按用户指令删掉的两块：
    * **总开关**（「放映时显示控制条」）—— 配置键 ``presentation.enabled``
      连同 ``windows.py::show_docks`` 里的判断一并移除，探测到放映就显示；
    * **检测状态卡片**（原来显示识别到的软件族与窗口句柄）—— 属于放映状态
      显示，连同 ``Backend.presentingKind`` / ``presentingWindow`` 一起删除。
      排查「探测认没认出放映窗口」改看日志：``logs/luminalium.log``。
*/
Rin.FluentPage {
    id: page

    title: qsTr("放映")
    contentSpacing: 10
}
