import QtQuick
import Qt5Compat.GraphicalEffects
import Luminalium

/*!
    混色剪影（玻璃质感）—— Luminalium 1 ``.about-main-logo`` 的 QML 版。

    一句话：**两层半透明白渐变，按一份单色剪影蒙出形状，叠在背后的东西上**。
    所以它跟「Logo」其实无关，任何单色剪影都能用 —— 目前两个调用点：
    ``ui/settings/About.qml`` 英雄区正中的星形 Logo（L1 原档）与**右下角的
    YUNOFACTORY 字标**。⚠️ 几何全部按自身 ``width`` / ``height`` 现算，**不是
    为正方形写死的**：字标那份就是把宽高设成素材的 4687:734，``PreserveAspectFit``
    自己会把剪影填满盒子。

    L1 原文（``plugins/builtins/settings/settings.html``）::

        .about-main-logo { width:248; height:248;
                           filter: drop-shadow(0 16px 32px rgba(0,0,0,.12)); }
        [data-theme="dark"] .about-main-logo {
                           filter: drop-shadow(0 0 28px rgba(50,117,245,.36)); }

        .about-main-logo::before,
        .about-main-logo::after { inset:0;
            mask: url("./logo_grayscale.svg") center / contain no-repeat; }

        .about-main-logo::before {   // 下层：160deg 白渐变（顶部最白）
            background: linear-gradient(160deg, rgba(255,255,255,.84),
                                        rgba(255,255,255,.34) 46%,
                                        rgba(255,255,255,.14));
            backdrop-filter: blur(22px) saturate(170%); }
        [data-theme="dark"] .about-main-logo::before {
            background: linear-gradient(160deg, rgba(255,255,255,.28),
                                        rgba(255,255,255,.11) 46%,
                                        rgba(255,255,255,.04)); }

        .about-main-logo::after {    // 上层：180deg 白渐变 + 光晕
            background: linear-gradient(180deg, rgba(255,255,255,.95),
                                                rgba(255,255,255,.52));
            opacity: .72;
            filter: drop-shadow(0 0 22px var(--logo-glow)); }
        [data-theme="dark"] .about-main-logo::after {
            background: linear-gradient(180deg, rgba(255,255,255,.56),
                                                rgba(255,255,255,.18));
            opacity: .88; }

    ===========================================================================
    「混色」是怎么来的 —— ⚠️⚠️ **不是** ``backdrop-filter``

    2026-10-01 用 Edge headless 复刻上面这段 CSS，把 ``::before`` 的
    ``backdrop-filter`` 整行删掉再渲染一遍做差分，**全图 maxdelta 只有 3/255**
    （肉眼无差）。原因：CSS 规范里 ``.about-main-logo`` 自己带
    ``filter: drop-shadow(...)``，那是 **Backdrop Root** 的触发条件（同样触发的
    还有 ``opacity < 1`` / ``mask`` / ``isolation: isolate`` —— ``.about-logo-container``
    上就有一个），而 Backdrop Root 内部的 ``backdrop-filter`` 只能采到 root
    **内部**的内容；``.about-main-logo`` 自身没有背景，于是什么都采不到，
    **这一层是空转的**。

    所以 L1 的「混色」= **两层半透明白渐变叠在流光上面**，流光的颜色透过白色
    显出来（越靠下白越薄、透出的流光越多），再加一圈 accent 光晕和一层整体投影。
    本项目照此复刻，**没有** ShaderEffectSource / HueSaturation —— 既忠实又省两层 FBO。

    ⚠️ 以前这里真的做过「抓背景 → 模糊 → 增饱和」那一套（注释还写着「别用 Glow，
      实测星星中心 154 vs 期望 ~85」）。那个「期望 ~206」是**错的**：L1 深色档
      星星中心实测只有 **124**；而且那套写法在本环境里**实测贡献为 0**（把它
      ``visible`` 翻成 false，采样像素一个数都不变），纯成本无收益，已整段删除。

    ===========================================================================
    两个 Qt5Compat 的坑（都靠 ``J:/tmp/l1probe/`` 下的探针实测出来的）

    1. **``DropShadow { source: X }`` 会把 X 也画一遍。** 它的输出是「X + 影子」，
       和 ``Glow`` 一个行为 —— 不是 CSS ``drop-shadow`` 的语义。场景里 X 本来就
       会被画一次，再挂个 ``DropShadow`` 就成了**画两遍**：逐层 ``grabToImage()``
       实测「整体投影」那一层自己就输出了 alpha 0.698（它的 color 只有 0.36），
       整个 Logo 冲到 0.882，而正确值在 0.31 左右。

       所以这里的投影改用 ``layer.enabled`` + ``layer.effect: DropShadow``：
       layer 的输出被效果**整体替换**，源只出现一次，而 DropShadow 的
       「源 + 影子」正好就是 CSS ``filter: drop-shadow()`` 要的效果，
       影子的形状也自动等于源的 alpha（= 两层白色面合成后的元素 alpha），
       不用自己去拼。

    2. **别给这种 source 设 ``visible: false``** —— 实测会让效果整个失效，
       连影子都不画（``.about-main-logo`` 的两层白色面则反过来：它们必须
       ``visible: false``，只当 ``OpacityMask`` 的 source 用）。

    ⚠️ CSS 的 ``drop-shadow(0 0 Rpx c)`` 里 R 是**模糊半径**，对应标准差 ``R/2``；
      ``GaussianBlur.radius`` / ``DropShadow.radius`` 就是标准差，所以一律折半
      （``glowSigma`` / ``dropSigma``）。
    ⚠️ 光晕与投影的模糊会超出 Logo 的 248×248 边界，而 layer 是按矩形裁的 ——
      所以两个容器都用负 margin 外撑 ``3σ``（``glowPad`` / ``dropPad``）并各自
      按自己的原点放蒙版，否则光晕会被切成硬边方块。

    ===========================================================================
    四层（自下而上）与 CSS 的对应：

    | 层                          | CSS                                    |
    |-----------------------------|----------------------------------------|
    | 整体投影                     | ``.about-main-logo { filter }``        |
    | accent 光晕                  | ``::after { filter: drop-shadow }``    |
    | ``::before`` 160deg 白渐变   | 同名伪元素                              |
    | ``::after`` 180deg 白渐变    | 同名伪元素（含 ``opacity``）            |

    前两层（投影 / 光晕）是 L1 给那块 248 的 Logo 配的**附加装饰**，可以单独关掉
    （``shadowEnabled`` / ``glowEnabled``）；后两层才是「混色」本身。

    自检基准（846x320 英雄区，深色档，流光 angle≈0，出处 ``J:/tmp/l1probe/``）::

        星心 (423,160) ≈ (124,131,163)     星上 (423,95) ≈ (145,151,179)
        星下 (423,228) ≈ (101,107,140)     外环 (423,43) ≈  (72, 77,111)
      浅色档星心 ≈ (234,234,243)。
*/
Item {
    id: root

    /*! Logo 剪影（要求带 alpha 的灰度版，``resources/logo_grayscale.svg``）。 */
    property url maskUrl: ""

    /*! 内部各层的 ``objectName`` 前缀。两份实例共存时**必须**给不同的值 —— 同一个
        ``objectName`` 在树里出现两次，按名字找东西（自检、探针）只会拿到先声明
        的那一份，看着「找到了」其实量的是别人。 */
    property string layerPrefix: "aboutLogo"

    /*! 那圈 accent 光晕（``::after`` 的 ``drop-shadow``）与整体投影
        （``.about-main-logo`` 的 ``filter``）—— L1 的 Logo 原档两层都要。
        角上的字标用 ``false``：模糊半径（22 / 28）是按 248 的 Logo 配的，压在
        150×23 的字标上既糊成一团，容器四周外撑的 3σ ≈ 42px 还会**越过英雄区的
        圆角**把辉光洒到卡片外面去。剩下的那两层白渐变才是「混色」本身。 */
    property bool glowEnabled: true
    property bool shadowEnabled: true

    /*! 深浅两档外观。缺省跟主题走。 */
    property bool isDark: Lumi.isDark
    /*! ``--logo-glow``（``::after`` 的那圈光晕）。 */
    property color glowColor: Lumi.logoGlow

    /*! ``::after`` 的 ``opacity``。 */
    property real whiteOpacity: isDark ? 0.88 : 0.72
    /*! ``drop-shadow(0 0 22px …)`` 的模糊半径（CSS 值）。 */
    property real glowBlur: 22

    /*! 整体投影：浅色 = 下方黑影，深色 = 无位移蓝辉光。 */
    readonly property color dropColor: isDark
        ? Qt.rgba(50 / 255, 117 / 255, 245 / 255, 0.36) : Qt.rgba(0, 0, 0, 0.12)
    readonly property real dropBlur: isDark ? 28 : 32
    readonly property real dropOffsetY: isDark ? 0 : 16

    /*! ``GaussianBlur`` / ``DropShadow`` 的 ``radius`` 是**标准差**，CSS 给的是
        模糊半径 → 折半。 */
    readonly property real glowSigma: glowBlur / 2
    readonly property real dropSigma: dropBlur / 2

    // -------------------------------------------------- 两层的渐变色阶（唯一定义处）
    /*! ``::before`` —— 160deg，顶部最白。 */
    readonly property real beforeTopAlpha: isDark ? 0.28 : 0.84
    readonly property real beforeMidAlpha: isDark ? 0.11 : 0.34
    readonly property real beforeEndAlpha: isDark ? 0.04 : 0.14
    /*! ``::after`` —— 180deg。光晕用同一组 alpha 乘 ``--logo-glow`` 的 alpha。 */
    readonly property real sheenTopAlpha: isDark ? 0.56 : 0.95
    readonly property real sheenEndAlpha: isDark ? 0.18 : 0.52

    implicitWidth: Lumi.aboutLogoSize
    implicitHeight: Lumi.aboutLogoSize

    // ---------------------------------------------------- CSS 渐变线的几何
    /*! ``linear-gradient(160deg, …)``：CSS 角度以「向上」为 0°、顺时针为正，
        所以方向向量 = ``(sin θ, -cos θ)``（屏幕坐标 y 向下）。 */
    readonly property real beforeDirX: Math.sin(Math.PI * 160 / 180)
    readonly property real beforeDirY: -Math.cos(Math.PI * 160 / 180)
    /*! CSS 的渐变线长度 = ``|w·sinθ| + |h·cosθ|`` —— 不是对角线，照抄别改。 */
    readonly property real beforeLineLength:
        Math.abs(width * beforeDirX) + Math.abs(height * beforeDirY)

    /*! 模糊容器四周的外撑量（见文件头）。 */
    readonly property real glowPad: Math.ceil(glowSigma * 3)
    readonly property real dropPad: Math.ceil(dropSigma * 3)

    // ==================================================== ② ::after 的 accent 光晕
    /*! CSS ``drop-shadow`` 的影子 = 「形状的 alpha 模糊后涂上该颜色」，而这里的
        「形状」是 ``::after`` 本身（白渐变 × 剪影），**不是**原始剪影 —— 所以
        填充得用「同样色阶、换成 accent 色」的渐变，不能拿蒙版的 alpha 顶替
        （踩过：那样光晕会浓三倍，星星中心偏 +45、蓝色通道尤其超标）。 */
    Item {
        id: glowWrap

        x: -root.glowPad
        y: -root.glowPad
        width: root.width + root.glowPad * 2
        height: root.height + root.glowPad * 2
        visible: root.glowEnabled

        layer.enabled: true
        layer.effect: GaussianBlur {
            radius: root.glowSigma
            samples: Math.ceil(root.glowSigma * 2) + 1
            transparentBorder: true
        }

        Image {
            id: glowMask
            x: root.glowPad
            y: root.glowPad
            width: root.width
            height: root.height
            source: root.maskUrl
            sourceSize: Qt.size(Math.max(1, Math.round(root.width)),
                                Math.max(1, Math.round(root.height)))
            fillMode: Image.PreserveAspectFit
            visible: false
            smooth: true
            mipmap: true
        }

        LinearGradient {
            id: glowFill
            x: root.glowPad
            y: root.glowPad
            width: root.width
            height: root.height
            start: Qt.point(0, 0)
            end: Qt.point(0, height)
            gradient: Gradient {
                GradientStop {
                    position: 0.0
                    color: Qt.rgba(root.glowColor.r, root.glowColor.g,
                                   root.glowColor.b,
                                   root.sheenTopAlpha * root.glowColor.a
                                   * root.whiteOpacity)
                }
                GradientStop {
                    position: 1.0
                    color: Qt.rgba(root.glowColor.r, root.glowColor.g,
                                   root.glowColor.b,
                                   root.sheenEndAlpha * root.glowColor.a
                                   * root.whiteOpacity)
                }
            }
            visible: false
        }

        OpacityMask {
            objectName: root.layerPrefix + "GlowShape"
            x: root.glowPad
            y: root.glowPad
            width: root.width
            height: root.height
            source: glowFill
            maskSource: glowMask
        }
    }

    // ==================================== ① 整体投影 + ③④ 两层白色面
    /*! 白色面与投影放在同一个 layer 里：``layer.effect: DropShadow`` 的输出是
        「源 + 影子」，于是投影的形状自动等于两层白色面合成后的元素 alpha，
        不必自己拼 union。容器外撑 ``dropPad`` 让影子有地方画。 */
    Item {
        id: logoStack

        x: -root.dropPad
        y: -root.dropPad
        width: root.width + root.dropPad * 2
        height: root.height + root.dropPad * 2

        layer.enabled: root.shadowEnabled
        layer.effect: DropShadow {
            radius: root.dropSigma
            samples: Math.ceil(root.dropSigma * 2) + 1
            horizontalOffset: 0
            verticalOffset: root.dropOffsetY
            spread: 0
            color: root.dropColor
            transparentBorder: true
        }

        Image {
            id: logoMask
            objectName: root.layerPrefix + "Mask"
            x: root.dropPad
            y: root.dropPad
            width: root.width
            height: root.height
            source: root.maskUrl
            sourceSize: Qt.size(Math.max(1, Math.round(root.width)),
                                Math.max(1, Math.round(root.height)))
            fillMode: Image.PreserveAspectFit
            visible: false
            smooth: true
            mipmap: true
        }

        // ------------------------------------------------------ ③ ::before
        LinearGradient {
            id: beforeFill
            x: root.dropPad
            y: root.dropPad
            width: root.width
            height: root.height
            start: Qt.point(width / 2 - root.beforeDirX * root.beforeLineLength / 2,
                            height / 2 - root.beforeDirY * root.beforeLineLength / 2)
            end: Qt.point(width / 2 + root.beforeDirX * root.beforeLineLength / 2,
                          height / 2 + root.beforeDirY * root.beforeLineLength / 2)
            gradient: Gradient {
                GradientStop {
                    position: 0.0
                    color: Qt.rgba(1, 1, 1, root.beforeTopAlpha)
                }
                GradientStop {
                    position: 0.46
                    color: Qt.rgba(1, 1, 1, root.beforeMidAlpha)
                }
                GradientStop {
                    position: 1.0
                    color: Qt.rgba(1, 1, 1, root.beforeEndAlpha)
                }
            }
            visible: false
        }

        OpacityMask {
            objectName: root.layerPrefix + "Before"
            x: root.dropPad
            y: root.dropPad
            width: root.width
            height: root.height
            source: beforeFill
            maskSource: logoMask
        }

        // ------------------------------------------------------ ④ ::after
        Item {
            id: sheenGroup

            x: root.dropPad
            y: root.dropPad
            width: root.width
            height: root.height
            opacity: root.whiteOpacity

            LinearGradient {
                id: sheenFill
                anchors.fill: parent
                start: Qt.point(0, 0)
                end: Qt.point(0, height)
                gradient: Gradient {
                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(1, 1, 1, root.sheenTopAlpha)
                    }
                    GradientStop {
                        position: 1.0
                        color: Qt.rgba(1, 1, 1, root.sheenEndAlpha)
                    }
                }
                visible: false
            }

            OpacityMask {
                id: sheenShape
                objectName: root.layerPrefix + "Sheen"
                anchors.fill: parent
                source: sheenFill
                maskSource: logoMask
            }
        }
    }
}
