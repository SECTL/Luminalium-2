pragma Singleton

import QtQuick
import RinUI as Rin

/*!
    设计令牌（Design Tokens）。

    颜色一律从 RinUI 主题取（``Rin.Theme.currentTheme``），主题未就绪时回退到
    与 dark 主题一致的常量，避免启动瞬间取到 null。**不写死设计稿的颜色值**，
    否则切浅色主题时控制条会瞎。

    背景：界面上的按钮 / 卡片 / 文本 / 分隔线已经直接使用 RinUI 组件
    （``Rin.Button`` / ``Rin.Frame`` / ``Rin.Text`` / ``Rin.ToolSeparator`` /
    ``Rin.SettingCard`` / ``Rin.Clip``），它们自带主题取色。本单例只服务于：

    1. RinUI 没有对应组件、必须手绘的地方（设置页的圆形色板、品牌块）；
    2. RinUI 的默认取色与设计稿不符、需要覆盖的地方；
    3. 间距 / 尺寸常量。

    因此这里只保留**真正被引用**的令牌，不堆放无人引用的「备用色」。
*/
QtObject {
    id: lumi

    readonly property var themeColors: Rin.Theme.currentTheme
        ? Rin.Theme.currentTheme.colors : null
    readonly property var themeAppearance: Rin.Theme.currentTheme
        ? Rin.Theme.currentTheme.appearance : null

    /*! 给主题色重投一个透明度，用于「同一个色、不同浓淡」的描边/填充。 */
    function fade(source, alpha) {
        return Qt.rgba(source.r, source.g, source.b, alpha)
    }

    /*! 把半透明色**压平**到某个底色上，得到一个等效的实色（alpha = 1）。

        用途：Fluent 压在亚克力上的「层」色是半透明的（``layerColor`` =
        ``#3A3A3A`` @30%），看着是 #303030，但它本身透光；需要**实底**的地方
        （编辑器右侧面板）得换算成不透明色 —— 观感一样，背后的亚克力不再透上来。 */
    function flatten(source, over) {
        var a = source.a
        return Qt.rgba(
            source.r * a + over.r * (1 - a),
            source.g * a + over.g * (1 - a),
            source.b * a + over.b * (1 - a),
            1)
    }

    // ---------------------------------------------------------------- 强调色
    // 设计稿的强调色就是配置里的原始值（`app.accent`）。
    // 注意 RinUI 有两个「强调色」：
    //   · `Utils.primaryColor`                 —— set_theme_color() 塞进去的原始值
    //   · `Theme.currentTheme.colors.primaryColor` —— 上面那个经
    //     lighter(1.6).darker(1.2) 的**变体**，Switch / textAccentColor 用它
    // 变体与本项目的 #4CC2FF 不完全一致，所以需要精确对齐设计稿的地方
    // （控制条下划线、退出键、设置里的开关）一律显式用 Lumi.accent。
    readonly property color accent: typeof Backend !== "undefined" && Backend.accent !== ""
        ? Backend.accent
        : (themeColors ? themeColors.primaryColor : "#4CC2FF")

    // ------------------------------------------------------------ 表面 / 卡片
    readonly property color surfaceBg: themeColors
        ? themeColors.backgroundAcrylicColor : "#2C2C2C"
    readonly property color surfaceBorder: themeColors
        ? themeColors.windowBorderColor : "#12FFFFFF"

    readonly property color tileBg: themeColors
        ? themeColors.controlFillColor : "#0FFFFFFF"
    readonly property color tileHover: themeColors
        ? themeColors.controlFillSecondaryColor : "#15FFFFFF"
    readonly property color cardBorder: themeColors
        ? themeColors.cardBorderColor : "#1A000000"

    /*! **细边**（hairline）—— 面板边线 / 分隔线 / 浮出层描边 / 屏幕框这类 1px
        的分界。深色档也看得见的那一支。

        ⚠️⚠️ 别拿 ``cardBorderColor`` 当它用：深色主题下那是 ``#000000`` @10%
        （见 ``RinUI/themes/dark.qml``）—— **黑色细边压在 #303030 的面板上等于
        没有**，与 ``splashBorder`` 是同一个坑。2026-10-01 用户反馈「整体的编辑器
        对暗色模式适配有点问题」时查出来的就是它：面板左沿、常驻条分隔线、浮出层
        描边、屏幕框**在深色下全部消失**，面板与舞台糊成一片。

        这里改用主题里**按主题翻**的那一支 ``dividerBorderColor``
        （Fluent ``DividerStrokeColorDefault``）：深色 = 白 8.37%、浅色 = 黑 8.03%，
        两边都是「比底色亮 / 暗一点点」，任何一个主题下都成立。 */
    readonly property color hairline: themeColors
        ? themeColors.dividerBorderColor : "#15FFFFFF"

    // ------------------------------------------------------------------ 文本
    readonly property color textPrimary: themeColors ? themeColors.textColor : "#FFFFFF"
    readonly property color textSecondary: themeColors
        ? themeColors.textSecondaryColor : "#9AFFFFFF"
    /*! 三级文本：空状态说明、占位提示这类最弱的信息。 */
    readonly property color textTertiary: themeColors && themeColors.textTertiaryColor !== undefined
        ? themeColors.textTertiaryColor : textSecondary

    // ------------------------------------------------------------ 通用「控件」
    readonly property color controlHoverFill: themeColors
        ? themeColors.controlFillColor : "#0FFFFFFF"
    readonly property color controlPressedFill: themeColors
        ? themeColors.controlFillSecondaryColor : "#15FFFFFF"

    // ------------------------------------------------------------------ 圆角
    readonly property int controlRadius: themeAppearance ? themeAppearance.buttonRadius : 5
    readonly property int flyoutRadius: 12

    // ================================================================== 放映控制条
    //
    // 尺寸照 **Luminalium 1 的实装值**（`ppt_assistant/ui/overlay.html` 的
    // CSS 原值）作基准；2026-09-25 用户指令「默认的组件比例大一些（设计语言
    // 仍是 L1）」→ 在 L1 档上整体放大约 15%（下表「本档」列）：
    //
    //   | 元素                | L1 原值                          | 本档        |
    //   |---------------------|----------------------------------|-------------|
    //   | 条高                | .tool-btn 38 + padding 上下 8    | 62（L1 54） |
    //   | 底板圆角            | border-radius: 999px（全圆胶囊）  | 高 / 2      |
    //   | 内边距 上下 / 左右  | #toolbar padding: 8 / 12         | 9 / 9       |
    //   | 按钮                | .tool-btn 38×38，圆角 19（圆）    | 44（L1 38） |
    //   | 图标                | .icon-mask 20×20                 | 22（L1 20） |
    //   | 按钮间距            | #toolbar gap: 4px                | 4           |
    //   | 分隔线              | .separator 1×24，margin: auto 4  | 1×28        |
    //   | 分隔线颜色          | --overlay-toolbar-line 白 15%     | 同          |
    //   | 翻页 pill           | .flipper 160×54，圆钮 margin 0 4  | 180×62      |
    //   | 竖版翻页 pill        | 横版 pill 旋转 90°：62×180，           | 62×180      |
    //   |                     | 屏幕两侧垂直居中（非 L1 竖版原档）      |             |
    //   | 退出键              | 普通圆钮（与其他按钮同款；          | 44          |
    //   |                     | ``danger`` 变体 = L1 红图标）       |             |
    //   | 悬停 / 选中填充      | 白 8% / 白 15%（浅色主题黑 6/12） | 同     |
    //   | 危险色（退出）       | 图标 #D9485A、悬停填充红 14%       | 同     |
    //
    // 设计语言（与 L1 一致）：
    //   · 底板是**全圆胶囊**，不是圆角矩形
    //   · 按钮一律**圆形**，平时完全透明、只在悬停 / 选中时浮现填充
    //   · 工具组是**圆的分段控件**（``ToolSegment``，基类 RinUI 的 ``Segmented``）：
    //     胶囊容器 + 圆形分页，选中的那页就是圆钮；**没有下划线**这一层
    //   · 翻页 pill 比工具条紧凑：圆钮几乎贴着 pill 边缘（留白 4 vs 12）
    //   · 退出键**不搞特殊**：与其他按钮同款的透明圆钮；``danger`` 变体才是
    //     L1 的红图标圆钮（强调色实底版式已按用户要求取消）
    //   · 工具栏与翻页栏的底板带 **CW2 小组件同款「渐变边框高光」**：
    //     对角线渐变描边，两端亮、中段隐去（见 ``dockHighlight*``）
    //   · 颜色仍走 RinUI 主题；只有「白 8% / 15%」这类**比例**照 L1 落实

    // ---- 底板 ----
    /*! 左右 9 = 外壳帽半径 31 − 分段帽半径 22：嵌套弧线**同心**，间隙恒定 9。 */
    readonly property int dockPaddingX: 9
    readonly property int dockPaddingY: 9
    /*! 999 = 胶囊；``FlyoutSurface`` 会按 高/2 钳制，改条高不会失形。 */
    readonly property int dockSurfaceRadius: 999
    /*! 底板不透明度：CW2 深色档同款 65%（``#1E1D22`` 65%）——半透明是
        高光的前提，放映画面从底板透出来，描边才有「材质光泽」感。 */
    readonly property real dockSurfaceOpacity: 0.65
    readonly property int dockShadowMargin: 24

    // ---- 底板高光（CW2 小组件同款的「渐变边框光影」）----
    // 出处：Class Widgets 2 ``Theme/components/Widget.qml``——一个对角线
    // ``LinearGradient``（起点亮、中段全透明、终点又亮）裁成 ``borderWidth``
    // 的描边环，偏好里叫 lighting_effect。CW2 的描边色**深浅主题都用白**
    // （dark: 白 40%，light: 白 100%），本质上是一道「光泽」而不是描边，
    // 所以这里同样不跟主题取色。CW2 原档 1.5px / 白 40%（他们的组件 100px 高）；
    // 控制条只有 62px 高、还要在放映画面上**看得清**（2026-09-25 用户指令
    // 「要明显」），所以加到 2px / 白 55% —— 效果结构一模一样，强度加大档。
    //
    // 2026-09-30 用户指令「高光削弱一点强度，边缘发光太有边界感，试试加个模糊」：
    //   · 亮度白 55% → 白 48%（削弱一档）
    //   · 新增 ``dockHighlightBlur``：描边环整体过一道 GaussianBlur，把
    //     2px 的**硬边线**溶成外扩的柔光晕 —— 硬边的「框」感没有了，
    //     看起来像玻璃边缘的折射光而不是一条描边。
    //   · 环宽仍 2px：模糊会把它摊宽摊淡，收窄反而会糊成一片没有形。
    readonly property real dockHighlightWidth: 2
    readonly property color dockHighlightColor: Qt.rgba(1, 1, 1, 0.48)
    /*! 高光环的高斯模糊半径（px）。0 = 关 —— 退回 CW2 原档的硬描边环。
        模糊后光晕会向外扩散，``FlyoutSurface`` 会按 2×半径自动外扩绘制区。 */
    readonly property real dockHighlightBlur: 3

    // ---- 控件（工具 / 动作 / 翻页 / 退出共用同一档内容高）----
    // L1 原档是 38 / 20；2026-09-25 用户指令「默认的组件比例大一些（设计语言
    // 仍是 L1）」→ 整体放大一档，比例关系不变：按钮直径 = 内容高 = 44，
    // 条高 62 = 44 + 9×2，图标 22。
    readonly property int dockIconSize: 22
    readonly property int dockHitSize: 44
    /*! 同一组按钮之间的间距（L1 ``#toolbar gap: 4px``）。 */
    readonly property int dockButtonSpacing: 4

    // ---- 按钮名称文本（「显示按钮文本」开关，2026-10-01 用户指令）----
    // 打开后按钮从「直径 44 的圆」变成「图标 + 文字」的胶囊：
    //
    //     [ 11 ][ 22 图标 ][ gap 8 ][ 文字 ][ 12 ]
    //
    // 左端那 11 = ``(hitSize − glyphSize) / 2``，就是图标平时在圆里居中让出来的量；
    // 右端取 12 与它呼应，于是文字两侧的视觉重量相当，不像贴在边上。
    // 宽度按文字**实际**宽度撑开（由组件里的隐藏探针量，不抄字体），所以
    // 「指针 / 笔 / 退出放映」这些不同长短的名字都各占各的，不需要预设档位。
    /*! 图标与文字之间的间距。 */
    readonly property int dockLabelGap: 8
    /*! 文字右端的留白。 */
    readonly property int dockLabelTrail: 12

    // ---- 按钮状态填充（L1 --overlay-button-hover / -active）----
    // 用 textPrimary 的透明度而不是写死白色：浅色主题下 L1 同样翻成
    // 黑 6% / 黑 12%，跟着文本色走天然对齐。
    readonly property color dockButtonHoverFill: fade(textPrimary, 0.08)
    readonly property color dockButtonActiveFill: fade(textPrimary, 0.15)
    /*! 退出键（L1 ``.tool-btn-danger``）：图标 #D9485A、悬停填充红 14%。 */
    readonly property color dockDangerIcon: "#D9485A"
    readonly property color dockDangerFill: "#24E03E3E"

    // ---- 工具分段控件（``ToolSegment`` / ``ToolSegmentItem``）----
    // 形态：**胶囊容器 + 圆形分页**。基类是 RinUI 的 ``Segmented``（TabBar）与
    // ``SegmentedItem``（TabButton），组内互斥、键盘导航都用它的 —— 只是把
    // 「圆角矩形容器 + 圆角矩形选中板 + 下划线」这套方语言换成圆的。
    /*! 999 = 胶囊；``ToolSegment`` 按 高/2 钳制（44 → 22）。 */
    readonly property int dockSegmentRadius: 999
    /*! 容器左右留白**必须为 0**（同心嵌套：外壳 9 + 0 + 半径 22 = 31 = 外壳帽半径）。
        上下为 0 —— 分页高 = 内容高（44），容器高也是它。 */
    readonly property int dockSegmentPadding: 0
    /*! 两个分页之间的间距。 */
    readonly property int dockSegmentSpacing: 4
    /*! 容器底：比底板亮一档（与按钮悬停同一档浓淡），读出「这是一个凹槽」。 */
    readonly property color dockSegmentBg: fade(textPrimary, 0.06)
    /*! 选中钮：L1 的 ``--overlay-button-active`` 浓淡（白 15%）。 */
    readonly property color dockSegmentCheckedBg: fade(textPrimary, 0.15)

    // ---- 分隔线（L1 .separator：1×24、两侧各 4、白 15%；放大档高 28）----
    readonly property int dockDividerWidth: 1
    readonly property int dockDividerHeight: 28
    readonly property int dockDividerGap: 4
    readonly property color dockDivider: fade(textPrimary, 0.15)

    // ---- 页码 ----
    readonly property int dockPagerWidth: 68
    readonly property int dockPagerSpacing: 8
    /*! 翻页 pill 的左右留白只有 4（L1 圆钮自带 margin），比工具条紧凑得多。 */
    readonly property int dockPagerPaddingX: 4

    // ---- 竖版两侧翻页（横版 pill 旋转 90° 的同款布局，屏幕左右、垂直居中）----
    // 2026-09-30 用户指令「竖版的按照横版翻转的布局来，不要全抄 L1」：
    // 尺寸**直接由横版翻页 pill（180×62）转置**成 62×180 —— 圆钮 44、间距 8、
    // 页码区 68、沿轴留白 4 全部与横版同档（配置直接共用 pager.* 那几项），
    // 只有 chevron 的朝向换成上 / 下。L1 竖版那套 margin 8 / 大小字页码弃用。
    readonly property int dockSidePagerWidth: 62
    readonly property int dockSidePagerHeight: 180
    /*! 竖版沿轴（上下）留白 = 横版翻页 pill 的 surface_padding_x（4）。 */
    readonly property int dockSidePagerPadding: 4

    // ---- 工具选单（笔的色板浮出层，``presentation/PenPaletteCard.qml``）----
    // 2026-10-01 用户指令：「当目前工具已经是笔的时候弹出如图的选单，图片的只供
    // 参考，实际的颜色列表要更多更丰富」。色板本身**不在这里**（30 色、可配置，
    // 见 ``config/default_config.json`` 的 ``presentation.pen.palette``），
    // 这里只放尺寸与配色。
    /*! 选单卡片与工具栏底板之间的竖直间距。 */
    readonly property int dockPaletteGap: 10
    /*! 卡片内边距（四周同档）。 */
    readonly property int dockPalettePadding: 16
    /*! 卡片圆角。8 = Fluent 2 的 **Overlay / Flyout corner radius** 一档 ——
        与编辑器里那个浮出缩放条（``editorFloatRadius``）同一个口径：独立浮出的
        大表面用 8，胶囊圆语言只留给控制条本体。（14 那档是哪来的都没有 ——
        Fluent 2 里浮出层没有 14。） */
    readonly property int dockPaletteRadius: 8
    /*! 卡片投影余量 —— 与 ``dockShadowMargin`` 同一个用途（留出画阴影的地方），
        但卡片是从零起的一块矩形，不需要那么大的余量。 */
    readonly property int dockPaletteShadowMargin: 20
    /*! 进出场动画：Fluent 2 的 flyout enter = **淡入 + 从触发点外侧滑入**。
        位移量取 12（RinUI 自家 ``Flyout`` 用 15，这里收一档落在 4px 网格上）；
        时长沿用 RinUI 的分工 —— opacity 快（167）、位移慢一档（250），
        easing 都是 ``OutQuint``（Fluent 2 的 decelerate 曲线）。 */
    readonly property int dockPaletteEnterOffset: 12
    readonly property int dockPaletteEnterDuration: Rin.Utils.animationSpeed
    readonly property int dockPaletteFadeDuration: durationFast
    /*! 色板圆点的直径 / 圆点间距。 */
    readonly property int dockSwatchSize: 30
    readonly property int dockSwatchSpacing: 10
    /*! 选中色点周围那圈白环的宽度，以及白环与色点之间的空隙 —— 就是截图里
        「选中的黄点外面套一圈白」的那个样子。

        ⚠️ 环色**跟着主题文本色走**（深色=白、浅色=黑），别写死白色：浅色档
        卡片底色本身就是白的，白环压在白色卡片上等于没有，选中态只剩「色点
        缩了一圈」这一个线索（2026-10-01 浅色预览实锤）。 */
    readonly property int dockSwatchRingWidth: 2
    readonly property int dockSwatchRingGap: 2
    readonly property color dockSwatchRingColor: textPrimary
    /*! 色点 hover 的外圈（Fluent 2 的 ControlStrokeColorSecondary 一档）——
        没有它鼠标划过色板毫无反馈，Fluent 2 的每个可点表面都有 hover 态。 */
    readonly property color dockSwatchHoverRing: fade(textPrimary, 0.45)
    readonly property int dockSwatchHoverRingWidth: 1
    /*! 预览区高度（波浪笔迹画在它里面）。 */
    readonly property int dockPalettePreviewHeight: 54
    /*! 预览笔迹的粗细 —— 比 PowerPoint 的实际笔迹细一点：这里是「看颜色」的
        示意图，太粗会糊成一团反而看不清色调。 */
    readonly property real dockPalettePreviewStroke: 5
    /*! 卡片底色：**不跟控制条底板共用 65% 那档** —— 色板要能读出真实颜色，
        底下透出放映画面会让每个色点都偏色。这里按「实底」压到 92%。 */
    readonly property color dockPaletteBg: fade(surfaceBg, 0.92)
    /*! 卡片描边：``hairline`` 同源（主题的 DividerStrokeColorDefault）——
        深色下 ``cardBorderColor`` 是黑 10%，压在深底板上等于没有。 */
    readonly property color dockPaletteBorder: hairline
    /*! 卡片里两个小标题（「颜色」「预览」）的字体色。 */
    readonly property color dockPaletteLabel: textSecondary
    /*! 两段（颜色 / 预览）之间的间距，以及中间那条 1px 分隔线。
        16 = Fluent 2 的 8px 节奏；分隔线用 ``hairline`` 同源（与卡片描边一致，
        分区线不该比卡片自己的边框更扎眼）。 */
    readonly property int dockPaletteSectionGap: 16
    readonly property color dockPaletteDivider: hairline
    /*! 预览区的**次级底板**（Fluent 2 的 Subtle fill 一档）+ 圆角与内留白：
        波浪画在块上，「预览」才像一块独立的只读区域，而不是直接飘在卡片
        底色上。嵌套圆角比外层（8）小一档 → 4（RinUI 的 smallRadius 同款）。 */
    readonly property color dockPalettePreviewFill: fade(textPrimary, 0.04)
    readonly property int dockPalettePreviewRadius: 4
    readonly property int dockPalettePreviewPad: 10
    /*! 还没选中任何一格时，预览笔迹用的颜色（= 卡片底色上一道中性线）。 */
    readonly property color dockPaletteIdleStroke: fade(textPrimary, 0.35)

    // ---- 页码快速跳转面板（``presentation/PageJumpPanel.qml``）----
    // 出处是 **Luminalium 1** 的点按翻页组件：L1 里点页码那一块，会从屏幕侧边
    // 滑出一列页面（``#page-selector``），点哪一页就跳哪一页。本档保留它的三件
    // 事 —— **点页码展开 / 当前页高亮 / 点外部收起**，但内容**换成 Fluent 的
    // 页码网格**，理由见组件头注释（L2 后端没有导出幻灯片缩略图这条通道）。
    //
    // L1 的手感也照搬了两条：面板是**滑入**（不用 scale —— 缩放会让数字发虚），
    // 曲线走 Fluent 2 的 decelerate（``OutQuint``），收起比展开干脆。
    /*! 面板与控制条底板之间的间距（同 ``dockPaletteGap`` 一档）。 */
    readonly property int dockJumpGap: 10
    /*! 面板内边距。 */
    readonly property int dockJumpPadding: 12
    /*! 面板圆角。8 = Fluent 2 的 Overlay / Flyout corner radius（同
        ``dockPaletteRadius``）—— 独立浮出的大表面用 8，胶囊圆语言只留给控制条本体。 */
    readonly property int dockJumpRadius: 8
    /*! 面板投影余量（同 ``dockPaletteShadowMargin`` 的用途：留出画阴影的地方）。 */
    readonly property int dockJumpShadowMargin: 20
    /*! 格子边长。**与 ``dockHitSize`` 同档（44）** —— 这是 Fluent 的最小可点
        尺寸，触屏上点页码本来就比点按钮更容易点偏，不该比工具按钮还小。 */
    readonly property int dockJumpCellSize: 44
    /*! 格子间距。6 = 8px 网格上的「紧凑一档」：格子自己已经 44，再拉开会让
        面板显得散，而跳跃列表应当是一块密实的砖。 */
    readonly property int dockJumpCellSpacing: 6
    /*! 格子圆角 —— 比面板（8）小一档，嵌套圆角同心（RinUI 的 smallRadius 同款）。 */
    readonly property int dockJumpCellRadius: 5
    /*! 每行几格的缺省值（真实值在 ``presentation.pager.jump.columns``）——
        5 列 × 44 的格子 ≈ 244 宽，与 L1 那块面板的 260 是同一个体量。 */
    readonly property int dockJumpColumns: 5
    /*! 格子 hover 底色（Fluent 2 的 Subtle fill 一档）。 */
    readonly property color dockJumpCellFill: fade(textPrimary, 0.04)
    readonly property color dockJumpCellHover: fade(textPrimary, 0.09)
    /*! 按下时轻微收缩的量感（不做位移动画：跳页类控件要「稳」）。 */
    readonly property real dockJumpCellPressedScale: 0.94
    /*! **当前页**格子的底色与文字色。L1 是「accent 描边」，这里改成 Fluent 的
        实底强调（WinUI 的 SelectedBackground 同款）—— 描边在触屏上一晃而过，
        实底才是一眼能找到「我现在在哪」。反色文字取主题的 ``textOnAccentColor``
        （深色档白 / 浅色档黑），别写死白色：浅色主题的 accent 是亮蓝，白字压上
        去几乎读不出来。 */
    readonly property color dockJumpCurrentFill: accent
    readonly property color dockJumpCurrentText: themeColors && themeColors.textOnAccentColor !== undefined
        ? themeColors.textOnAccentColor : (isDark ? "#FFFFFF" : "#000000")
    /*! 面板底色 —— 与笔选单同一档实底（92%）：页码要能看清，透出放映画面会糊。 */
    readonly property color dockJumpBg: fade(surfaceBg, 0.92)
    /*! 面板描边：``hairline`` 同源（深色下 ``cardBorderColor`` 是黑 10%，等于没有）。 */
    readonly property color dockJumpBorder: hairline
    /*! 面板滚动区里那一条细滚动条的颜色（Flickable 自绘，见组件）。 */
    readonly property color dockJumpScrollThumb: fade(textPrimary, 0.28)
    /*! 进出场动画：滑入位移 12（同笔选单）+ 时长沿用 RinUI 的分工。 */
    readonly property int dockJumpEnterOffset: 12
    readonly property int dockJumpEnterDuration: Rin.Utils.animationSpeed
    readonly property int dockJumpFadeDuration: durationFast
    /*! 面板高度上限占可用空间的比例 —— 行数很多的演示（几百页）不该让面板顶到
        屏幕另一头，超过就滚动。 */
    readonly property real dockJumpMaxHeightRatio: 0.72
    /*! 面板宽度上限占屏幕宽的比例（列数配得很大时兜底，别横着顶出屏幕）。 */
    readonly property real dockJumpMaxWidthRatio: 0.32

    // ================================================================== 快捷面板
    //
    // 版式对齐 **Class Widgets 2** 的托盘面板（`Windows/TrayPanel.qml` +
    // `Components/TrayShortcuts.qml`）：
    //   · 保留 RinUI 自绘窗口边框（隐藏最小化/最大化，仅留关闭）
    //   · 内容区是一张 layerColor 底 + cardBorderColor 描边的卡片，
    //     宽度 = 窗口宽 + 2*拖拽边距（正好贴满窗口）
    //   · 快捷方式 = 3 列 GridView，单元格 84 高，磁贴比单元格窄/矮 6
    //   · 底部 = 卡片外、窗口右下角一排扁平图标按钮 + ToolTip
    //   · （原「放映状态」行已于 2026-10-01 删除，`statusRowHeight` 令牌随之移除）
    readonly property int panelPadding: 14
    /*! CW2：ColumnLayout bottomMargin 22（给底栏让位）。 */
    readonly property int panelBottomPadding: 22
    readonly property int panelSectionSpacing: 8

    readonly property int shortcutCellHeight: 84
    /*! 磁贴比单元格内缩的量（CW2：`cellWidth - 6` / `cellHeight - 6`）。 */
    readonly property int shortcutCellGap: 6
    readonly property int shortcutTileRadius: 6
    readonly property int shortcutIconSize: 22
    readonly property int shortcutGridMaxHeight: 244

    readonly property int panelLogoSize: 32

    /*! CW2 面板卡片：layerColor 底 + cardBorderColor 描边（都来自 RinUI 主题）。 */
    readonly property color panelCardBg: themeColors
        ? themeColors.layerColor : "#803A3A3A"
    readonly property color panelCardBorder: themeColors
        ? themeColors.cardBorderColor : "#1A000000"

    // ================================================================== 启动画面
    //
    // 版式取自 Figma 设计稿「启动画面 Dark / Light」（2026-10-01），**外观语言走
    // Fluent 2**（同日用户指令「比例过大了、也不符合 RinUI 的 Fluent 2 设计语言」）。
    // 两者分工严格分开，改东西前先想清楚自己在动哪一层：
    //
    //   · **版式层** —— 谁在哪儿、占多大。照设计稿：画布 2984×1679，
    //     ``SplashWindow.qml`` 里一律写设计稿原值，乘统一的 ``k = 卡面宽 / 2984``。
    //   · **外观层** —— 圆角 / 描边 / 字阶 / 配色 / 阴影。走 Fluent 2 令牌，
    //     **不参与缩放**。设计稿的圆角 92 折算到 720 宽是 22px，那是 iOS 语汇；
    //     Fluent 大表面的圆角上限就是 8。
    //
    // 因此这一节**不再写死任何设计稿色值**，一律取 RinUI 主题令牌。
    readonly property bool isDark: themeColors ? Rin.Theme.currentTheme.isDark : true
    readonly property var themeType: Rin.Theme.currentTheme
        ? Rin.Theme.currentTheme.typography : null
    readonly property var themeShadows: Rin.Theme.currentTheme
        ? Rin.Theme.currentTheme.shadows : null

    /*! 设计稿画布 + 卡面宽度。卡面高度按画布比例算出（2984:1679 → 720:405）。 */
    readonly property real splashDesignWidth: 2984
    readonly property real splashDesignHeight: 1679
    readonly property real splashCardWidth: 720

    /*! Fluent 阴影。取 RinUI 的 ``flyout`` 档（黑 14% / blur 24 / 下偏 8）——
        启动画面是一块**浮出层**，不是模态对话框（``dialog`` 那档 blur 64 / 偏 32
        是给带遮罩的模态框用的，压在这儿太重）。 */
    readonly property int splashShadowBlur: themeShadows && themeShadows.flyout
        ? themeShadows.flyout.blur : 24
    readonly property int splashShadowOffsetY: themeShadows && themeShadows.flyout
        ? themeShadows.flyout.offsetY : 8
    readonly property color splashShadowColor: themeShadows && themeShadows.flyout
        ? themeShadows.flyout.color : Qt.rgba(0, 0, 0, 0.14)
    /*! 卡面四周留给阴影的透明边距。**必须 ≥ blur + 下偏**，否则阴影尾巴会被
        窗口边界切出一条硬边（窗口是透明的，切了看得出来）。 */
    readonly property int splashShadowMargin: splashShadowBlur + splashShadowOffsetY

    /*! 圆角 / 描边：Fluent 尺度，**与卡面大小无关**（设计稿的 92 是比例值，弃用）。
        8 = WinUI 的 ``OverlayCornerRadius``；描边 1px = Fluent 控件描边。 */
    readonly property int splashRadius: 8
    readonly property int splashArtRadius: 8
    readonly property int splashBorderWidth: 1

    /*! 表面：Fluent 2 ``SolidBackgroundFillColorBase``（深 #202020 / 浅 #F3F3F3）。 */
    readonly property color splashBg: themeColors
        ? themeColors.backgroundColor : "#202020"
    /*! 描边：RinUI 的窗口描边。⚠️ 别用 ``cardBorderColor`` —— 深色主题下它是
        「黑 10%」，压在 #202020 上等于没有，卡片的边就消失了。 */
    readonly property color splashBorder: themeColors
        ? themeColors.windowBorderColor : "#12FFFFFF"

    readonly property color splashSubtitle: themeColors
        ? themeColors.textSecondaryColor : "#9AFFFFFF"
    readonly property color splashLabel: themeColors
        ? themeColors.textSecondaryColor : "#9AFFFFFF"

    /*! 进度条 = Fluent ``ProgressBar`` 规格：4 高 / 2 圆角 / 强调色填充。
        槽色取 ``DividerStrokeColorDefault`` —— 深浅两版分别是「黑 8% / 白 8%」，
        正是压在卡面上看得见又不抢戏的那一档。 */
    readonly property int splashProgressHeight: 4
    readonly property int splashProgressRadius: 2
    readonly property color splashTrackBg: themeColors
        ? themeColors.dividerBorderColor : "#15FFFFFF"
    readonly property color splashTrackFill: accent

    /*! 字母 / 数字用 Segoe UI Variable Text，中日韩回退到 Microsoft YaHei UI
        —— Win11 上 Fluent 应用的标准组合，别退回 Candara 那类装饰体。
        ⚠️ UI 语言为日语（app/i18n.py 已把默认 QLocale 设成 ja_*）时改用
        Yu Gothic UI —— 与 RinUI 字体补丁（app/rinui_patch.py 改写
        Utils.fontFamily）保持同一套日语字体策略。 */
    readonly property string splashFontFamily: "Segoe UI Variable Text"
    readonly property string splashFontFamilyCjk: Qt.locale().name.startsWith("ja")
        ? "Yu Gothic UI" : "Microsoft YaHei UI"

    /*! 字阶：**Fluent 2 ramp**，不再按设计稿折算。
        版本行起初是照「相对标题的高度比 0.62」取了对得最像的 ``bodyLarge``（18），
        但用户 2026-10-01 反馈「版本号和开发代号那一栏的字体大小未免有点大了」——
        它本质是**标题底下的一行次要信息**，Fluent 里就是 ``body``（14）。
        层级现在很干净：Title 28 → Body 14 → Caption 12。
        底部状态行按设计稿折算只有 9.4px（**小于 Fluent 最小档**），取 ``caption``（12）。 */
    readonly property int splashSubtitleSize: themeType ? themeType.bodySize : 14
    readonly property int splashLabelSize: themeType ? themeType.captionSize : 12

    /*! 插画降饱和。设计稿那张彩度很高，原样放进 Fluent 界面里太跳；
        0 = 原图，1 = 全灰。名字对齐 ``GraphicalEffects.Desaturate.desaturation``。 */
    readonly property real splashArtDesaturation: 0.3

    /*! 插画卡背后那道斜向渐变。**属于原画的一部分、不是外观层**，所以保留设计稿
        色值：插画位图是不透明的（RGB 无 alpha）且盖满整卡，这层实际不会露出来，
        纯粹是换图时的兜底。 */
    readonly property color splashArtGradientFrom: "#DEFCF9"
    readonly property color splashArtGradientTo: "#C3BEF0"

    // ================================================================ 主界面编辑器
    //
    // 「主界面」= 顶层窗口（详见 ``ui/MainInterfaceEditor.qml``）。编辑器有**两个态**：
    //
    //   · **全景态** —— 没选中任何组件：整个屏幕等比装进舞台（``fitScale``），
    //     与真机上的排布一一对应；
    //   · **编辑态** —— 点中一条控制条：舞台聚焦放大它、右侧滑出设置面板，
    //     画面里其余部分压一层暗罩、选中的那个套一圈强调色描边。
    //
    // 缩放只动**相机**（``scale`` / 位移），不改任何布局尺寸 —— 控制条副本始终活在
    // 1:1 的屏幕坐标系里，摆位算法与 ``app/windows.py::_position_dock`` 同源。
    // 屏幕坐标系是 1:1 的，所以面板上的「100%」= 真实像素大小。

    /*! 右侧设置面板宽度。展开时**挤窄舞台**（不是浮在舞台上面）——
        聚焦的组件要落在真正可见的那块区域中央。 */
    readonly property int editorInspectorWidth: 340

    /*! 设置面板底色 —— **实色**（2026-10-01 用户指令「右侧的设置面板应该是实色
        背景」）。取 Fluent 的「层」色（半透明，压在亚克力上看着像 #303030）压平到
        ``backgroundAcrylicColor`` 上：观感不变，但不再把背后的亚克力透出来。 */
    readonly property color editorPanelBg: themeColors
        ? flatten(themeColors.layerColor, themeColors.backgroundAcrylicColor)
        : "#303030"

    /*! 面板下部**常驻条**的高度：只剩组件信息（「工具栏 318 × 62」）。
        常驻条不参与滚动 —— 它是「现在在编谁」的常显读数。

        2026-10-01（第六轮）用户指令「把返回按钮删掉 / 缩放作为一个悬浮组件放在
        左侧的主界面预览区域」：顶部的导航条（``editorPanelHeaderHeight``）整条
        撤掉 —— 面板回到「设置项区 + 常驻条」两段式；缩放缓搬去预览区，
        这里只剩一行读数，所以 84 → 48。 */
    readonly property int editorPanelFooterHeight: 48

    /*! 聚焦取景的留白（**视口像素**，不随缩放变化）：让被编辑的组件周围
        留一圈上下文，不至于顶满视口。 */
    readonly property int editorFocusPaddingX: 72
    readonly property int editorFocusPaddingY: 56

    /*! 聚焦缩放的**上限**。下限恒为全景比例（点一下不该反而更小）；
        上限 2× —— 控制条才 62px 高，再放大就是拿放大镜看它了。 */
    readonly property real editorFocusMaxScale: 2.0

    /*! 手动缩放档位范围（相对 1:1）与每档倍率（点一次 ＋/－）。 */
    readonly property real editorZoomMinScale: 0.1
    readonly property real editorZoomMaxScale: 4.0
    readonly property real editorZoomStep: 1.25

    /*! 相机动画时长；拖动平移期间临时归零（要跟手）。 */
    readonly property int editorAnimMs: 220

    /*! 非选中区域的暗罩浓度。Fluent 的 Smoke 档是黑 30%，这里略重一档 ——
        编辑器底下是半透明的亚克力，太淡压不住。 */
    readonly property real editorDimOpacity: 0.34

    /*! 暗罩上留给选中组件的「洞」比**选中框**每边多出来的量。量的是**界面里的
        东西**（视口像素，不随缩放变化）—— 与选中描边同一个坐标系，两者才同心
        （早先这里是屏幕坐标系的量，暗罩跟着平面一起缩放时会和描边错开）。

        洞的**形状**是组件自己的形状：圆角半径 = 短边一半 + 这个留白（见
        ``MainInterfaceEditor.qml`` 的 ``dimShape``），于是半径恰好比描边的
        半径（短边一半）大这么一圈 —— 描边整个落在亮区里，不会被暗罩压到。 */
    readonly property int editorDimHolePad: 6

    /*! 选中描边：2px 强调色，离组件表面 4px。画在视口坐标里，不随缩放变粗。 */
    readonly property int editorSelectionRingWidth: 2
    readonly property int editorSelectionRingGap: 4

    /*! 面板里小按钮（缩放 ± / 百分比）的边长。 */
    readonly property int editorMiniButtonSize: 28

    /*! 面板**中部圆按钮**（收起面板）的直径。

        2026-10-01（第六轮）用户指令：「把返回按钮删掉 / 加一个圆按钮放在侧面板的
        中部」—— 原先那枚 40 的方形返回键在**顶部**，现在换成**圆心压在面板左沿、
        垂直居中**的圆钮：一半悬在舞台上，读作「把面板收回去」的把手（与
        ``editorBackButtonSize`` 同尺寸，只是从方角换成正圆、从顶边挪到中线）。 */
    readonly property int editorPanelHandleSize: 40

    /*! 预览区上那枚**悬浮缩放缓**的高度（``EditorZoomBar``）。
        与 ``editorPanelHandleSize`` 同档，但两者不是一回事：那个是面板把手，
        这个是预览区的浮出层 —— 别互相引用。 */
    readonly property int editorZoomBarHeight: 40

    /*! 悬浮缩放缓的**圆角**。

        2026-10-01（第七轮）用户指令：「缩放应该放在预览区右上方 且不该是大圆角」
        —— 原先照 L1 的语言把圆角拉满（``height / 2`` = 20，一枚**药丸**），
        现在收到 Fluent 的 ``OverlayCornerRadius``（8）：还是一眼看出是「一块浮
        起来的板」，但不再圆头圆脑。

        ⚠️ 与 ``dockSurfaceRadius``(999) 不是一回事：那个是放映控制条的底板
        （L1 的胶囊语言，**刻意**保留），这里是编辑器里的工具浮出层。别顺手统一。 */
    readonly property int editorFloatRadius: 8

    /*! 悬浮组件（缩放缓）的投影 —— 与启动画面同源（Fluent flyout 档），但收小
        一档：它只有 40 高，flyout 那档（blur 24 / offsetY 8）的影子会比本体
        还大一圈。``editorFloatShadowMargin`` 是给影子留的余量（``EditorZoomBar``
        的容器外撑这么多），摆放时按它扣。 */
    readonly property int editorFloatShadowBlur: 10
    readonly property int editorFloatShadowOffsetY: 3
    readonly property int editorFloatShadowMargin: editorFloatShadowBlur
        + editorFloatShadowOffsetY + 1

    /*! 设置页「主界面」里那张**推广卡**（「编辑主界面的新方式」）的版式 ——
        照搬 Class Widgets 2 的 ``ClassWidgets/Components/Introduction.qml``
        （它的用例在 ``pages/settings/General/Widgets.qml``）：Frame 内边距 24，
        左图 + 右两列间距 24，图片最大 200×150。 */
    readonly property int editorIntroPadding: 24
    readonly property int editorIntroSpacing: 24
    readonly property int editorIntroImageWidth: 200
    readonly property int editorIntroImageHeight: 150

    // ================================================== 设置 · 关于页英雄区
    //
    // 2026-10-01 用户指令「给设置的关于界面上安排 Luminalium 1 的同款流光背景
    // Logo 混色效果」。出处 = L1 插件式设置页（``plugins/builtins/settings/
    // settings.html``）的 ``#section-about``：
    //
    //   · ``.about-header``        —— 320 高的英雄区，``overflow:hidden``；
    //     圆角 L1 原值是 ``16px 16px 0 0``（**上圆下直**），因为它是「出血」的：
    //     ``width: calc(100% + 96px)`` + ``margin: -32px -48px 32px``，左右各
    //     多出 48、顶上顶出 32，下沿是一条直边直接接上后面的设置组。
    //     本项目把英雄区摆成页面里的一张**内嵌卡**（四周都有留白），下沿没有
    //     「接着往下流」的东西，所以**刻意**用四角统一的 16（``aboutHeroRadius``）
    //     —— 照抄 16/16/0/0 会让卡片下沿像被切了一刀，不是设计意图。
    //   · ``.hyperos-bg``          —— HyperOS 风格的「流光」：10 层 radial-gradient
    //     铺成 200%×200% 的画幅、``blur(60px)``、25s 匀速自转 360° 且
    //     中点缩到 1.1（``@keyframes hyperos-flow``）；
    //   · ``.about-main-logo``     —— 248×248，两个伪元素都用
    //     ``logo_grayscale.svg`` 当 mask：``::before`` 是「毛玻璃」
    //     （渐变白 + ``backdrop-filter: blur(22px) saturate(170%)``，也就是
    //     把身后的流光透过 Logo 剪影show出来 —— 「混色」在这里），``::after``
    //     是白色渐变版 + ``drop-shadow(0 0 22px var(--logo-glow))`` 光晕；
    //   · ``.about-header::after`` —— 底部 100px 渐隐到页面底色，让流光化开。
    //
    // 十团光斑的颜色照 L1 ``applyMonetPalette()`` 的 Monet 公式以强调色为种
    // 现算（L1 那套是从壁纸抽色的，本项目没有抽色源，直接用强调色）。
    readonly property int aboutHeroHeight: 320
    readonly property int aboutHeroRadius: 16
    /*! 底部渐隐高度（L1 ``.about-header::after`` 的 100）。 */
    readonly property int aboutHeroFade: 100
    readonly property int aboutLogoSize: 248

    /*! 英雄区**右下角**的署名字标（``design_by_yunofactory.svg`` 那份
        「DESIGN BY + YUNOFACTORY」锁定版式）—— 与 Logo 同一套「混色」剪影，
        只是没有光晕与投影（见 ``GlassLogo.qml`` 的 ``glowEnabled``）。

        ⚠️ 尺寸是**字标本体**的量级，不是一块主视觉：150 宽时下面那行
        YUNOFACTORY 字高 ≈ 17，顶上那行 DESIGN BY 只剩 ~3px —— 它是落款里的
        小字，读作一道细纹而不是一行可读文本。2026-10-05 第一版给到 220
        （字高 24），用户反馈「太大了」，同时明确**不要**为了让它可读而把
        DESIGN BY 裁掉。想要那行小字真能读，字标得放到 270 以上 —— 那时它已经
        压到中间那个 248 的 Logo 了，摆不下。

        高度不写死，由 ``aboutCreditsAspect`` 现算，免得把字标拉变形。 */
    readonly property int aboutCreditsWidth: 150
    readonly property int aboutCreditsMargin: 20
    /*! 字标素材 ``resources/design_by_yunofactory.svg`` 的宽高比（4687 : 734）。
        ⚠️ 换素材这个数要跟着改 —— 写错的症状是字标被拉扁/拉长，预览图上不显眼。 */
    readonly property real aboutCreditsAspect: 4687 / 734

    /*! 窗口/页面基色 —— RinUI ``FluentWindowBase`` 在没有 backdrop 时就是用
        ``colors.backgroundColor`` 铺底（``app.backdrop`` 默认 "none"）。 */
    readonly property color pageBg: themeColors
        ? themeColors.backgroundColor : "#202020"

    /*! 两色按比例线性混合（L1 ``mixColor``），结果不透明。

        ⚠️⚠️ 两个端色必须走 **color 属性**传进来，别在调用点直接写字面量：QML 把
        函数参数当 JS 值，字面量 ``"#000000"`` 到了函数里就是字符串，
        ``.r/.g/.b`` 全是 ``undefined`` → ``Qt.rgba`` 恒返回**黑色**（静默、
        不报错）。2026-10-01 实测踩过：流光整片发灰黑，查了半天。 */
    function mix(base, target, ratio) {
        return Qt.rgba(base.r + (target.r - base.r) * ratio,
                       base.g + (target.g - base.g) * ratio,
                       base.b + (target.b - base.b) * ratio, 1)
    }

    /*! ``mix()`` 的两个端色（见上面的告警）。 */
    readonly property color mixBlack: "#000000"
    readonly property color mixWhite: "#FFFFFF"

    /*! 流光底色：深色档 = 强调色压暗（L1 ``mixColor(accent, "#000000", 0.78/0.7)``）；
        浅色档 = 页面基色往强调色里掺一档 —— L1 取的是 ``palette.background`` /
        ``palette.surface``，而 Monet 的那两色**本身就是带主色的浅色**，本项目主题
        基色是中性的，所以这里现掺（不掺的话浅色下整块是白的，流光和 Logo 一起
        看不见 —— 试过）。 */
    readonly property color auroraBase: isDark
        ? mix(accent, mixBlack, 0.78) : mix(pageBg, accent, 0.20)
    readonly property color auroraSurface: isDark
        ? mix(accent, mixBlack, 0.70) : mix(pageBg, accent, 0.15)
    readonly property color auroraG1: mix(auroraBase, accent, 0.15)
    readonly property color auroraG2: mix(auroraSurface, accent, 0.12)
    readonly property color auroraG3: mix(auroraSurface, accent, 0.20)
    readonly property color auroraG4: mix(auroraBase, accent, 0.25)
    readonly property color auroraG5: mix(auroraSurface, mixWhite, isDark ? 0.08 : 0.30)
    /*! ``::after`` 光晕色（L1 ``--logo-glow``）。 */
    readonly property color logoGlow: fade(accent, isDark ? 0.28 : 0.22)

    // ------------------------------------------------------------------ 动效
    readonly property int durationFast: Rin.Utils.animationSpeedFaster
    /*! 启动画面淡出时长。 */
    readonly property int splashFadeDuration: 280
}
