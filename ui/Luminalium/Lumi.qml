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
    readonly property real dockSurfaceOpacity: 0.97
    readonly property int dockShadowMargin: 24

    // ---- 底板高光（CW2 小组件同款的「渐变边框光影」）----
    // 出处：Class Widgets 2 ``Theme/components/Widget.qml``——一个对角线
    // ``LinearGradient``（起点亮、中段全透明、终点又亮）裁成 ``borderWidth``
    // 的描边环，偏好里叫 lighting_effect。CW2 的描边色**深浅主题都用白**
    // （dark: 白 40%，light: 白 100%），本质上是一道「光泽」而不是描边，
    // 所以这里同样不跟主题取色。CW2 原档 1.5px / 白 40%（他们的组件 100px 高）；
    // 控制条只有 62px 高、还要在放映画面上**看得清**（2026-09-25 用户指令
    // 「要明显」），所以加到 2px / 白 55% —— 效果结构一模一样，强度加大档。
    readonly property real dockHighlightWidth: 2
    readonly property color dockHighlightColor: Qt.rgba(1, 1, 1, 0.55)

    // ---- 控件（工具 / 动作 / 翻页 / 退出共用同一档内容高）----
    // L1 原档是 38 / 20；2026-09-25 用户指令「默认的组件比例大一些（设计语言
    // 仍是 L1）」→ 整体放大一档，比例关系不变：按钮直径 = 内容高 = 44，
    // 条高 62 = 44 + 9×2，图标 22。
    readonly property int dockIconSize: 22
    readonly property int dockHitSize: 44
    /*! 同一组按钮之间的间距（L1 ``#toolbar gap: 4px``）。 */
    readonly property int dockButtonSpacing: 4

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

    // ================================================================== 快捷面板
    //
    // 版式对齐 **Class Widgets 2** 的托盘面板（`Windows/TrayPanel.qml` +
    // `Components/TrayShortcuts.qml`）：
    //   · 保留 RinUI 自绘窗口边框（隐藏最小化/最大化，仅留关闭）
    //   · 内容区是一张 layerColor 底 + cardBorderColor 描边的卡片，
    //     宽度 = 窗口宽 + 2*拖拽边距（正好贴满窗口）
    //   · 快捷方式 = 3 列 GridView，单元格 84 高，磁贴比单元格窄/矮 6
    //   · 放映状态 = 卡片内一行状态摘要（替代 CW2 的课程表区块）
    //   · 底部 = 卡片外、窗口右下角一排扁平图标按钮 + ToolTip
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

    /*! 放映状态行（icon + 文字一行）的高度。 */
    readonly property int statusRowHeight: 56

    readonly property int panelLogoSize: 32

    /*! CW2 面板卡片：layerColor 底 + cardBorderColor 描边（都来自 RinUI 主题）。 */
    readonly property color panelCardBg: themeColors
        ? themeColors.layerColor : "#803A3A3A"
    readonly property color panelCardBorder: themeColors
        ? themeColors.cardBorderColor : "#1A000000"

    // ------------------------------------------------------------------ 动效
    readonly property int durationFast: Rin.Utils.animationSpeedFaster
}
