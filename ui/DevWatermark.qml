import QtQuick
import RinUI as Rin
import Luminalium

/*!
    开发中水印 —— 挂在每个窗口的**左下角**。

    内容两行::

        开发中版本，不代表最终品质
        26.0.823.1 / AwaSubaru / a798b54 / 1A2B3C4D

    第二行四段：版本号 / 开发代号 / **commit 短号** / 设备ID。
    2026-11-15（用户指令「开发中水印加上 commit 号」）：短号取
    ``Backend.commitHash``，唯一来源 ``app/build_info.py`` —— 源码跑实时读
    ``.git/HEAD``，打包跑读 ``Luminalium.spec`` 构建时写进包里的
    ``build_info.json``；读不到返回空串，这里把整段省掉，绝不显示
    "unknown" 这种假值（水印是给开发者定位版本用的，错号比没号更糟）。

    **只给开发者看的开关**：显隐由 ``app.dev_watermark`` 配置驱动
    （经 ``Backend.devWatermark`` 透出），设置页**不出现**这个开关 ——
    用户不知道它的存在；发给用户的包把配置改成 false 即可。

    纯文字、没有 ``MouseArea``：不拦截任何点击，悬停也无反馈，
    挂在窗口内容之上（调用方自己给 ``z``）也不影响下层交互。
    透明度给得低（75%），弱到不干扰界面、又能在任何底色上读出来。
*/
Item {
    id: wm

    /*! 调用方级别的总闸（如某窗口想临时不挂）。 */
    property bool shown: true

    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight
    width: implicitWidth
    height: implicitHeight
    visible: shown && Backend.devWatermark

    Column {
        id: column
        spacing: 2

        Rin.Text {
            typography: Rin.Typography.Caption
            color: Lumi.textSecondary
            opacity: 0.75
            text: qsTr("开发中版本，不代表最终品质")
        }

        // objectName 给 tools/smoke.py 用：自检要断言**真正显示出来的那段文字**
        // 里含短号，只查 Backend 有值会漏掉「后端有、QML 没拼上」这类静默失效。
        Rin.Text {
            objectName: "devWatermarkDetail"
            typography: Rin.Typography.Caption
            color: Lumi.textTertiary
            opacity: 0.75
            text: Backend.appVersion + " / " + Backend.devCodename
                  + (Backend.commitHash !== "" ? " / " + Backend.commitHash : "")
                  + " / " + Backend.deviceId
        }
    }
}
