import QtQuick
import RinUI as Rin
import Luminalium

/*!
    开发中水印 —— 挂在每个窗口的**左下角**。

    内容两行::

        

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

        Rin.Text {
            typography: Rin.Typography.Caption
            color: Lumi.textTertiary
            opacity: 0.75
            text: Backend.appVersion + " / " + Backend.devCodename
                  + " / " + Backend.deviceId
        }
    }
}
