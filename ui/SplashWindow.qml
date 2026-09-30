import QtQuick
import QtQuick.Window
import Qt5Compat.GraphicalEffects
import Luminalium

/*!
    启动画面。

    **版式**取自 Figma 设计稿「启动画面 Dark / Light」（2026-10-01 还原）；
    **外观语言**走 Fluent 2（同日用户指令「比例过大了、也不符合 RinUI 的
    Fluent 2 设计语言」后重做）。两层严格分开，改之前先确认自己在动哪一层：

    ─ 版式层 ─────────────────────────────────────────────────────────────
    设计稿是一张 **2984×1679** 的画布（左品牌栏 + 右插画卡）::

        ┌────────────────────────────────────────────────────┐
        │  ⬤ 44                 ┌────────────────────┐       │
        │  logo                 │  插画卡 349×347 r8  │       │
        │                       │                    │       │
        │  Luminalium      ← 35 │                    │       │
        │  1.5.0.1 // AwaSubaru │                    │       │
        │  ▬▬▬▬▬▬▬▭▭▭▭▭▭▭▭▭▭▭▭▭ │                    │       │
        │  正在启动     60% 就绪 └────────────────────┘       │
        └────────────────────────────────────────────────────┘
              卡面 720×405（Fluent：圆角 8 + 1px 描边 + flyout 阴影）

    本文件所有**位置/尺寸**都写成设计稿原值，统一乘 ``k = cardWidth / designWidth``
    （= 720/2984 ≈ 0.2413）。要微调版式请改设计稿原值，不要改乘出来的结果。

    ─ 外观层 ─────────────────────────────────────────────────────────────
    圆角 / 描边 / 字阶 / 配色 / 阴影一律取 ``Lumi.qml``「启动画面」段里的 Fluent 2
    令牌，**不过 ``px()``**。设计稿的圆角 92 折算到 720 宽是 22px（iOS 语汇），
    Fluent 大表面的圆角上限是 8；设计稿底部那行字折算下来只有 9.4px，比 Fluent
    最小档还小，提到 caption 12。

    ─ 窗口尺寸 ───────────────────────────────────────────────────────────
    窗口比卡面四周各大 ``Lumi.splashShadowMargin``（阴影得画在卡外），所以窗口
    本身是 784×469，**用户看到的卡面才是 720×405**。定位依旧靠窗口居中 ——
    边距是四边对称的，所以窗口居中就等于卡面居中。

    为什么是一个纯 ``Window`` 而不是 ``Rin.FluentWindowBase``：

    * 设计稿是**无标题栏的整块卡片**，没有 RinUI 那套窗口边框；
    * 窗口**刻意不登记进 RinUI**（同 ``TopWindow``）—— 登记后 RinUI 会给它加
      ``WS_CAPTION`` 并让 DWM 画系统圆角/阴影，和这儿自绘的 Fluent 卡片打架。
*/

Window {
    id: splash

    objectName: "SplashWindow"
    title: qsTr("Luminalium")
    visible: false
    color: "transparent"
    // SplashScreen 自带无边框；再加置顶。不加 Qt.Tool —— 启动画面应当在
    // 任务栏短暂出现一下，用户才知道程序起来了。
    flags: Qt.SplashScreen | Qt.WindowStaysOnTopHint

    // ============================================================ 设计空间

    /*! 设计稿画布（版式坐标系）与卡面宽度。窗口大小由它俩推出来。 */
    readonly property real designWidth: Lumi.splashDesignWidth
    readonly property real designHeight: Lumi.splashDesignHeight
    readonly property real cardWidth: Lumi.splashCardWidth
    readonly property real cardHeight: Math.round(cardWidth * designHeight / designWidth)

    /*! 设计空间 → 逻辑像素的**唯一**缩放因子。 */
    readonly property real k: cardWidth / designWidth
    /*! 卡面外留给 Fluent 阴影的透明边距。 */
    readonly property int shadowMargin: Lumi.splashShadowMargin

    /*! 卡面的 Fluent 外观参数（**固定值，不随 k 缩放**）。
        挂在窗口上而不是直接写在卡面上，是因为 ``Rectangle.border`` 是**分组属性**，
        PySide 侧读不到它的子属性（``Can't find converter for 'QQuickPen*'``）——
        挂到窗口上，``smoke.py`` 才能断言「这些值没有偷偷跟着版式缩放」。 */
    readonly property int cardRadius: Lumi.splashRadius
    readonly property int cardBorderWidth: Lumi.splashBorderWidth

    /*! 矢量素材的过采样倍率。
        为什么不是「按 DPR 请求就够」：logo 里星形的白色描边只有约 1.2 设计单位，
        换算到 720 宽的卡面上只有 0.3 个 logical pixel —— 按显示尺寸 1:1 光栅化的
        话，这条线会被抗锯齿摊平成一片糊影（设计稿是 3× 导出，所以它那儿是实线）。
        这里按 DPR 再乘 4 做超采样，让 SVG 在足够高的分辨率上算覆盖率，再由场景图
        缩回去，细笔画才保得住。 */
    readonly property real sampleScale: Math.max(4, (screen ? screen.devicePixelRatio : 1) * 4)

    width: Math.round(cardWidth) + 2 * shadowMargin
    height: Math.round(cardHeight) + 2 * shadowMargin

    /*! 设计值 → 逻辑像素。**只给版式用**；Fluent 外观项（圆角/描边/字号/进度条高）
        直接用令牌原值，一律不要过这个函数。 */
    function px(v) {
        return v * k
    }

    // ============================================================ 淡出

    signal fadeOutFinished()

    function fadeOut() {
        fadeAnim.start()
    }

    NumberAnimation {
        id: fadeAnim
        target: contentRoot
        property: "opacity"
        to: 0
        duration: Lumi.splashFadeDuration
        easing.type: Easing.OutCubic
        onFinished: splash.fadeOutFinished()
    }

    // ============================================================ 内容

    Item {
        id: contentRoot
        anchors.fill: parent

        // ------------------------------------------------------ 卡面
        // Fluent 浮出层：8 圆角 + 1px 描边 + flyout 阴影。卡面自己没有子项
        // （版式都在下面那层），于是可以整块单独成层，阴影直接挂在它身上。
        Rectangle {
            id: card
            objectName: "splashCard"
            x: splash.shadowMargin
            y: splash.shadowMargin
            width: Math.round(splash.cardWidth)
            height: Math.round(splash.cardHeight)
            color: Lumi.splashBg
            radius: splash.cardRadius              // Fluent 值，**不过 px()**
            border.width: splash.cardBorderWidth   // 同上：固定 1px
            border.color: Lumi.splashBorder

            layer.enabled: true
            layer.effect: DropShadow {
                verticalOffset: Lumi.splashShadowOffsetY
                radius: Lumi.splashShadowBlur
                color: Lumi.splashShadowColor
                samples: 1 + radius * 2
                cached: true
            }
        }

        // ------------------------------------------------------ 版式层
        // 原点与卡面左上角重合；下面所有坐标都是「设计稿原值 × k」。
        Item {
            id: cardContent
            x: card.x
            y: card.y
            width: card.width
            height: card.height

            // 品牌标记 184×184（设计值）
            Image {
                objectName: "splashLogo"
                x: splash.px(131)
                y: splash.px(121)
                width: splash.px(184)
                height: splash.px(184)
                source: Backend.resourceFile("splash/logo.svg")
                sourceSize: Qt.size(Math.round(width * splash.sampleScale),
                                    Math.round(height * splash.sampleScale))
                smooth: true
                // mipmap 必须开。sourceSize 是 ~7 倍超采样（311px 显示到 44px），
                // 只靠 ``smooth`` 的双线性在 7 倍降采样下等于点采样 —— 圆边会出现
                // 一圈锯齿（2026-10-01 实测）。开了以后场景图挑的 mip 档刚好落在
                // 目标尺寸附近，边缘才是干净的。
                // 顺带记一笔：星形那道 ~0.3px 的白描边在这个尺寸下本来就只剩一点点
                // 反差，**设计稿在同分辨率下同样只是淡填充** —— 别为了让描边「看得见」
                // 去调粗 SVG，那是把放大倍率的假象当成 bug 改。
                mipmap: true
            }

            // 标题：**直接搬设计稿的矢量轮廓**，不是在写文字。
            // 设计稿墨迹框 x[147.3, 875.0] y[1176.5, 1290.2]，SVG 的 viewBox 就是
            // 它，所以把图按框摆好就与设计稿逐像素重合，不需要再对基线。
            // （设计稿原稿的字体是一款带尾钩 l/i 的无衬线体，比对了本机全部字体
            //   与 20 余款免费字体都没找到等值款，所以走轮廓这条路。）
            Image {
                objectName: "splashWordmark"
                x: splash.px(147.3)
                y: splash.px(1176.5)
                width: splash.px(727.7)
                height: splash.px(113.7)
                source: Backend.resourceFile(
                    Lumi.isDark ? "splash/wordmark_dark.svg" : "splash/wordmark_light.svg")
                sourceSize: Qt.size(Math.round(width * splash.sampleScale),
                                    Math.round(height * splash.sampleScale))
                smooth: true
                mipmap: true          // 同 logo：7 倍降采样，不开会出锯齿
            }

            // -------------------------------------------------- 版本行
            // 设计稿基线（多数字形墨迹底）在 1388.4。位置照设计稿走，字号走
            // Fluent 的 bodyLarge。
            // ⚠️ 用 ``FontMetrics`` 而不是 ``TextMetrics``：后者在这版 Qt（6.11）里
            // **没有暴露 ``ascent``**，取到的是 undefined，``y - undefined`` 会变成
            // NaN 而 Qt 把 NaN 静默当成 0 —— 文本会整行贴到窗口顶上。
            FontMetrics {
                id: subtitleMetrics
                font.family: Lumi.splashFontFamily
                font.pixelSize: Lumi.splashSubtitleSize
            }

            Text {
                objectName: "splashSubtitle"
                x: splash.px(134)
                y: splash.px(1388.4) - subtitleMetrics.ascent
                font.family: Lumi.splashFontFamily
                font.pixelSize: Lumi.splashSubtitleSize
                color: Lumi.splashSubtitle
                text: Backend.splashSubtitle
            }

            // -------------------------------------------------- 进度条
            // 横向位置/宽度照设计稿（x 134 / 宽 1178），**高度与圆角走 Fluent**
            // （ProgressBar 规格 4 / 2，设计稿折算出来是 6）。既然变薄了，纵向就按
            // 设计稿那条槽的**中线**对齐，不然顶边对齐会让整条上浮 1px。
            Rectangle {
                objectName: "splashTrack"
                x: splash.px(134)
                y: Math.round(splash.px(1459 + 25 / 2) - Lumi.splashProgressHeight / 2)
                width: splash.px(1178)
                height: Lumi.splashProgressHeight
                radius: Lumi.splashProgressRadius
                color: Lumi.splashTrackBg

                Rectangle {
                    objectName: "splashProgressFill"
                    width: parent.width * Math.max(0, Math.min(1, Backend.splashProgress))
                    height: parent.height
                    radius: parent.radius
                    color: Lumi.splashTrackFill
                    // 阶段是一跳一跳推进的，没有这个补间会一顿一顿的
                    Behavior on width {
                        NumberAnimation {
                            duration: 220
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }

            // -------------------------------------------------- 底部状态行
            // 设计稿：左「正在启动」x[133.1,288.8]、右「60% 创建托盘图标」
            // x[1002.6,1310.3]，两者基线同为 1559.7 —— 也就是跟进度条**同一列宽**
            // （进度条右沿 1312）。位置照旧，字号提到 Fluent 的 caption 12。
            FontMetrics {
                id: labelMetrics
                font.family: Lumi.splashFontFamilyCjk
                font.pixelSize: Lumi.splashLabelSize
            }

            Text {
                objectName: "splashStageLeft"
                x: splash.px(134)
                y: splash.px(1559.7) - labelMetrics.ascent
                font.family: Lumi.splashFontFamilyCjk
                font.pixelSize: Lumi.splashLabelSize
                color: Lumi.splashLabel
                text: qsTr("正在启动")
            }

            Text {
                objectName: "splashStageRight"
                x: splash.px(1312) - width
                y: splash.px(1559.7) - labelMetrics.ascent
                font.family: Lumi.splashFontFamilyCjk
                font.pixelSize: Lumi.splashLabelSize
                color: Lumi.splashLabel
                text: Math.round(Backend.splashProgress * 100) + "% " + Backend.splashStage
            }

            // -------------------------------------------------- 插画卡
            // 设计稿：卡片 x[1444,2892] y[121,1559]，插画位图本身摆在 x=1309
            // （比卡片左沿还左 135）、尺寸 1717×1640，靠卡片**裁掉**多出来的部分，
            // 所以这里位图要负偏移、并给卡片开圆角裁切（圆角走 Fluent 的 8，
            // 不是设计稿那个折算下来 26 的 r107）。
            Item {
                id: artCard
                objectName: "splashArtCard"
                x: splash.px(1444)
                y: splash.px(121)
                width: splash.px(1448)
                height: splash.px(1438)

                layer.enabled: true
                layer.effect: OpacityMask {
                    maskSource: Rectangle {
                        width: artCard.width
                        height: artCard.height
                        radius: Lumi.splashArtRadius
                    }
                }

                // 渐变底（设计稿端点 (1405.5,121)→(2821.5,1539.5)，换算成卡片内坐标）
                LinearGradient {
                    anchors.fill: parent
                    start: Qt.point(splash.px(-38.5), 0)
                    end: Qt.point(splash.px(1377.5), splash.px(1418.5))
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Lumi.splashArtGradientFrom }
                        GradientStop { position: 1.0; color: Lumi.splashArtGradientTo }
                    }
                }

                Image {
                    objectName: "splashArt"
                    x: splash.px(-135)
                    y: 0
                    width: splash.px(1717)
                    height: splash.px(1640)
                    source: Backend.resourceFile("splash/art.png")
                    fillMode: Image.Stretch
                    smooth: true
                    mipmap: true
                    // 降饱和：设计稿那张插画彩度很高，原样摆进 Fluent 界面里太跳。
                    // ⚠️ ``Desaturate`` 的属性叫 ``desaturation``（0 = 原图，1 = 全灰），
                    // 不叫 ``amount`` —— 写成 ``amount`` 只在运行期报「non-existent property」。
                    layer.enabled: true
                    layer.effect: Desaturate {
                        desaturation: Lumi.splashArtDesaturation
                    }
                }
            }
        }
    }
}
