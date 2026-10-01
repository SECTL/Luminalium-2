import QtQuick
import QtQuick.Layouts
import RinUI as Rin

/*!
    设置首页：resources/WARNING.png 黄色警示横幅。

    2026-10-01 用户指令「设置的主页目前留空」后本页一度什么都不放；
    2026-10-02 用户指令「给设置的主页先挂上resources里面的警告黄色横幅
    位置稍微靠下」—— 挂回一张横幅图（**先**用图片，将来要做成可换文案的
    自绘横幅再说）。

    * 图就是 ``resources/WARNING.png``（1064×~170 的整幅设计稿切片，
      自带黄底 / 黑线 / 星形标记 / 文案，不需要也不应该再包卡片底板）；
    * 「稍微靠下」= 内容列顶部再多让 24px（页面头部本身占的高度不算，
      那是 FluentPage 的 ``title`` 机制，与这里的 margin 是两码事）；
    * 高度按**容器宽等比缩**（``width * implicitHeight / implicitWidth``），
      别用图的天然高 —— 内容列会被 ``horizontalPadding`` 夹到 ~846，
      PreserveAspectFit 下天然高会在图上方留一截空白。

    其余区域仍留空，往后要加卡片直接往下排即可。
*/
Rin.FluentPage {
    id: page

    title: qsTr("主页")

    Image {
        id: warningBanner

        objectName: "homeWarningBanner"
        Layout.fillWidth: true
        Layout.topMargin: 24
        source: Backend.resourceFile("WARNING.png")
        asynchronous: true
        fillMode: Image.PreserveAspectFit
        mipmap: true
        /*! 天然尺寸（1064×~170）加载后按列宽等比折算高度；
            未加载完（implicitWidth=0）先给 0，别除零。 */
        Layout.preferredHeight: warningBanner.implicitWidth > 0
            ? Math.round(warningBanner.width * warningBanner.implicitHeight / warningBanner.implicitWidth)
            : 0
    }
}
