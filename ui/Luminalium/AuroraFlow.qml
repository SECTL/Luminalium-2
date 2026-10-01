import QtQuick
import Qt5Compat.GraphicalEffects
import Luminalium

/*!
    流光背景（HyperOS 风格）—— Luminalium 1 的 ``.hyperos-bg`` 的 QML 版。

    出处：L1 插件式设置页 ``plugins/builtins/settings/settings.html`` 的
    ``#section-about``（详见 ``Lumi.qml`` 的「关于页英雄区」一节）。CSS 原文::

        .hyperos-bg {
          position: absolute; top: -50%; left: -50%;
          width: 200%; height: 200%;
          background: radial-gradient(circle at 20% 20%, var(--hyperos-g1) 0%, transparent 40%),
                      ... 共 10 层 ...;
          filter: blur(60px);
          animation: hyperos-flow 25s infinite linear;
          opacity: 0.9;
        }
        @keyframes hyperos-flow {
          0%   { transform: rotate(0deg)   scale(1); }
          50%  { transform: rotate(180deg) scale(1.1); }
          100% { transform: rotate(360deg) scale(1); }
        }

    逐条对应到 QML：

    * **200% 画幅** —— ``rotator`` 取 ``2×`` 父项大小、居中，于是同一个点在
      自转时始终盖得住视口（CSS 的 ``top/left: -50%`` 就是这个意思）。
    * **10 层 radial-gradient** —— 每层是一个 ``Qt5Compat`` 的 ``RadialGradient``；
      CSS 写 ``circle at X% Y%``，半径 = 到**最远角**的距离再乘那个百分比，
      所以圆心 / 半径都按 ``blobField`` 里的分数照着算，不写死像素。
    * **blur(60px)** —— ``GaussianBlur``。⚠️ 直接对 2× 画幅做半径 60 的模糊
      （samples 121）每帧都要几百次纹理采样，太贵；而半径 60 的高斯会把所有
      高频细节抹平，**先降采样再模糊再放大**在视觉上等价。所以 ``field`` 按
      ``1/downscale`` 分辨率绘制、模糊半径同比例缩小，最后 ``scale`` 放大回去
      —— FBO 和模糊开销都降到 1/downscale²。
    * **自转 + 呼吸** —— ``NumberAnimation on rotation``（0→360 匀速循环）+ 一条
      ``SequentialAnimation`` 把 ``scale`` 从 1 缓到 1.1 再回来，都用 linear。

    ⚠️⚠️ **别把 ``NumberAnimation`` 换回 ``RotationAnimator``**。Animator 系列走渲染线程，
      依赖渲染循环持续给帧；在软件渲染后端（或窗口未被 expose）下**整个动画静默失效**
      —— 2026-10-01 实测：同一个窗口里 ``NumberAnimation on rotation`` 正常走
      （116° → 261° → 48° → 195° → 340°），而并排的 ``RotationAnimator`` 恒为 0，
      抓帧差分 maxdelta 只有 2（等于没动）。自检 ``probe_anim4.py`` 的隔离实验。
      这一条 25 秒才转一圈，主线程属性动画的开销可以忽略，别为省这点去做优化。
    * **底部渐隐** —— CSS 是 ``.about-header::after`` 拿一层「透明 → 页面底色」
      的渐变盖住底部 100px。这里不画颜色、改用 ``OpacityMask`` 把流光本身按
      竖直渐变淡出，于是不需要知道页面底色是什么（深/浅主题通用）。

    ⚠️ 缓存的层次：``field`` 的内容是静态的，它的 ``layer`` 只烘一次；自转 /
      缩放只改 ``rotator``（无 layer）的变换，纹理照用。最外那层
      ``fadeHost`` 带 OpacityMask，因为底下在转所以每帧重画 —— 但它只有一次
      纹理取样乘算，很便宜。**别**把 OpacityMask 挪到 ``field`` / ``rotator``
      上：挪进去就会跟着一起转，渐隐方向就歪了。
*/
Item {
    id: root

    clip: true

    // ------------------------------------------------------------------ 光斑
    /*! 5 个渐变色（缺省取 ``Lumi`` 里按 L1 Monet 公式现算的那一组）。 */
    property color g1: Lumi.auroraG1
    property color g2: Lumi.auroraG2
    property color g3: Lumi.auroraG3
    property color g4: Lumi.auroraG4
    property color g5: Lumi.auroraG5

    /*! CSS 的 ``opacity: 0.9``。 */
    property real blobOpacity: 0.9
    /*! CSS 的 ``filter: blur(60px)``（**屏幕像素**，内部会按 ``downscale`` 折算）。 */
    property real blurRadius: 60
    /*! 一轮完整的「转一圈 + 呼吸一次」时长（CSS 25s）。 */
    property int flowPeriod: 25000
    property bool running: true
    /*! 降采样倍率，见文件头。1 = 关掉降采样（画质优先，慢）。 */
    property real downscale: 3
    /*! 底部渐隐的高度（屏幕像素，0 = 不渐隐）。 */
    property real fadeHeight: Lumi.aboutHeroFade
    /*! 输出的圆角（0 = 直角）。**必须由这里裁**：Qt 的 ``Item.clip`` 只认矩形，
        父级 ``Rectangle`` 的 ``radius`` 拦不住子项的实色方块，直角会露出来。 */
    property real cornerRadius: 0

    /*! 10 层光斑：``gradient`` 是取哪一号色，``cx/cy`` 是圆心（画幅分数，
        对应 CSS 的 ``at X% Y%``），``extent`` 是 CSS 里 ``transparent`` 那一档
        的位置 —— 乘上「到最远角的距离」就是这团光的半径。 */
    readonly property var blobField: [
        { gradient: 1, cx: 0.20, cy: 0.20, extent: 0.40 },
        { gradient: 2, cx: 0.80, cy: 0.80, extent: 0.40 },
        { gradient: 3, cx: 0.20, cy: 0.80, extent: 0.40 },
        { gradient: 4, cx: 0.80, cy: 0.20, extent: 0.40 },
        { gradient: 5, cx: 0.50, cy: 0.50, extent: 0.50 },
        { gradient: 2, cx: 0.50, cy: 0.12, extent: 0.42 },
        { gradient: 4, cx: 0.12, cy: 0.50, extent: 0.42 },
        { gradient: 1, cx: 0.88, cy: 0.50, extent: 0.42 },
        { gradient: 3, cx: 0.50, cy: 0.88, extent: 0.42 },
        { gradient: 5, cx: 0.70, cy: 0.30, extent: 0.46 }
    ]

    /*! 按编号取色（``blobField`` 里那个 ``gradient``）。 */
    function colorAt(index) {
        switch (index) {
        case 1: return g1
        case 2: return g2
        case 3: return g3
        case 4: return g4
        case 5: return g5
        }
        return g1
    }

    /*! 渐隐起点（0~1）。自检读它。 */
    readonly property real fadeStop: fadeHeight > 0 && height > 0
                                      ? Math.max(0, 1 - fadeHeight / height) : 1
    /*! 自检读数：当前自转角。 */
    readonly property real angle: rotator.rotation
    /*! 自检读数：当前呼吸缩放（1 ~ 1.1）。 */
    readonly property real spread: rotator.scale

    // ------------------------------------------------------------------ 画幅
    Item {
        id: fadeHost
        anchors.fill: parent

        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: fadeHost.width
                height: fadeHost.height
                /*! 圆角形状 × 竖直渐隐 —— ``Rectangle`` 同时支持这两样，
                    所以「裁圆角」和「底部化开」合成一次蒙版，不多花一层 FBO。 */
                radius: root.cornerRadius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#FFFFFFFF" }
                    GradientStop { position: root.fadeStop; color: "#FFFFFFFF" }
                    GradientStop { position: 1.0; color: "#00FFFFFF" }
                }
            }
        }

        /*! 2× 画幅，绕自身中心自转 —— 对应 CSS 的 ``200%`` + ``rotate()``。 */
        Item {
            id: rotator
            objectName: "auroraRotator"
            anchors.centerIn: parent
            width: root.width * 2
            height: root.height * 2

            /*! 自转角。见文件头：**必须**用主线程动画，Animator 类在软件渲染后端下不动。 */
            NumberAnimation on rotation {
                from: 0
                to: 360
                duration: root.flowPeriod
                loops: Animation.Infinite
                easing.type: Easing.Linear
                running: root.running && root.visible
            }

            SequentialAnimation on scale {
                running: root.running && root.visible
                loops: Animation.Infinite
                NumberAnimation {
                    from: 1.0; to: 1.1
                    duration: Math.round(root.flowPeriod / 2)
                    easing.type: Easing.Linear
                }
                NumberAnimation {
                    from: 1.1; to: 1.0
                    duration: Math.round(root.flowPeriod / 2)
                    easing.type: Easing.Linear
                }
            }

            /*! 光斑本体。低分辨率 + 同比例模糊，再 ``scale`` 放大回 2× 画幅。 */
            Item {
                id: field
                anchors.centerIn: parent
                width: Math.max(1, Math.round(root.width * 2 / root.downscale))
                height: Math.max(1, Math.round(root.height * 2 / root.downscale))
                scale: root.downscale
                opacity: root.blobOpacity

                layer.enabled: true
                layer.smooth: true
                layer.effect: GaussianBlur {
                    // radius 必须 ≤ samples / 2
                    radius: root.blurRadius / root.downscale
                    samples: Math.ceil(root.blurRadius / root.downscale * 2) + 1
                    transparentBorder: true
                }

                Repeater {
                    model: root.blobField

                    delegate: RadialGradient {
                        anchors.fill: parent

                        required property var modelData
                        required property int index

                        readonly property real cx: modelData.cx * width
                        readonly property real cy: modelData.cy * height
                        readonly property real farCorner: Math.max(
                            Math.max(Math.hypot(cx, cy),
                                     Math.hypot(width - cx, cy)),
                            Math.max(Math.hypot(cx, height - cy),
                                     Math.hypot(width - cx, height - cy)))
                        readonly property color tint: root.colorAt(modelData.gradient)

                        horizontalOffset: cx - width / 2
                        verticalOffset: cy - height / 2
                        horizontalRadius: farCorner * modelData.extent
                        verticalRadius: horizontalRadius

                        gradient: Gradient {
                            GradientStop { position: 0.0; color: tint }
                            // 末端用「同色 alpha 0」而不是 "transparent"（= 黑 alpha 0）：
                            // 无论 Qt 按预乘还是直通插值，都不会在尾巴上泛灰。
                            GradientStop { position: 1.0; color: Lumi.fade(tint, 0) }
                        }
                    }
                }
            }
        }
    }
}
