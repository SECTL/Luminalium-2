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

    /*! 强调色之上的前景色：参考稿里退出键的电源图标是**纯黑**。 */
    readonly property color onAccent: themeColors
        ? themeColors.textOnAccentColor : "#000000"

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
    // 尺寸一律照 **Luminalium 1 的实装值**（`ppt_assistant/ui/overlay.html` 的
    // CSS 原值，不是按比例折算的近似）：
    //
    //   | 元素                | L1 原值                          | 本档   |
    //   |---------------------|----------------------------------|--------|
    //   | 条高                | .tool-btn 38 + padding 上下 8    | 54     |
    //   | 底板圆角            | border-radius: 999px（全圆胶囊）  | 高 / 2 |
    //   | 内边距 上下 / 左右  | #toolbar padding: 8 / 12         | 8 / 12 |
    //   | 按钮                | .tool-btn 38×38，圆角 19（圆）    | 38     |
    //   | 图标                | .icon-mask 20×20                 | 20     |
    //   | 按钮间距            | #toolbar gap: 4px                | 4      |
    //   | 分隔线              | .separator 1×24，margin: auto 4  | 1×24   |
    //   | 分隔线颜色          | --overlay-toolbar-line 白 15%     | 同     |
    //   | 翻页 pill           | .flipper 160×54，圆钮 margin 0 4  | 160×54 |
    //   | 退出键              | .tool-btn-danger 38 圆形          | 38     |
    //   | 悬停 / 选中填充      | 白 8% / 白 15%（浅色主题黑 6/12） | 同     |
    //   | 危险色（退出）       | 图标 #D9485A、悬停填充红 14%       | 同     |
    //
    // 设计语言（与 L1 一致）：
    //   · 底板是**全圆胶囊**，不是圆角矩形
    //   · 按钮一律**圆形**，平时完全透明、只在悬停 / 选中时浮现填充
    //   · 工具没有「容器 + 下划线」的分段控件，选中就是圆底填充
    //   · 翻页 pill 比工具条紧凑：圆钮几乎贴着 pill 边缘（留白 4 vs 12）
    //   · 退出键是**红色图标**的圆形按钮，不是强调色实底方块
    //   · 颜色仍走 RinUI 主题；只有「白 8% / 15%」这类**比例**照 L1 落实

    // ---- 底板 ----
    readonly property int dockPaddingX: 12
    readonly property int dockPaddingY: 8
    /*! 999 = 胶囊；``FlyoutSurface`` 会按 高/2 钳制，改条高不会失形。 */
    readonly property int dockSurfaceRadius: 999
    readonly property real dockSurfaceOpacity: 0.97
    readonly property int dockShadowMargin: 24

    // ---- 控件（工具 / 动作 / 翻页 / 退出共用同一档内容高）----
    readonly property int dockIconSize: 20
    readonly property int dockHitSize: 38
    /*! 同一组按钮之间的间距（L1 ``#toolbar gap: 4px``）。 */
    readonly property int dockButtonSpacing: 4
    /*! 只有 ``style: "accent"`` 的退出键用得到（L1 的 danger 版是纯圆）。 */
    readonly property int dockControlRadius: 5

    // ---- 按钮状态填充（L1 --overlay-button-hover / -active）----
    // 用 textPrimary 的透明度而不是写死白色：浅色主题下 L1 同样翻成
    // 黑 6% / 黑 12%，跟着文本色走天然对齐。
    readonly property color dockButtonHoverFill: fade(textPrimary, 0.08)
    readonly property color dockButtonActiveFill: fade(textPrimary, 0.15)
    /*! 退出键（L1 ``.tool-btn-danger``）：图标 #D9485A、悬停填充红 14%。 */
    readonly property color dockDangerIcon: "#D9485A"
    readonly property color dockDangerFill: "#24E03E3E"

    // ---- 分隔线（L1 .separator：1×24、两侧各 4、白 15%）----
    readonly property int dockDividerWidth: 1
    readonly property int dockDividerHeight: 24
    readonly property int dockDividerGap: 4
    readonly property color dockDivider: fade(textPrimary, 0.15)

    // ---- 退出键（仅 style=accent 时用到的宽:高比）----
    readonly property real dockExitWidthRatio: 1.07

    // ---- 页码 ----
    readonly property int dockPagerWidth: 60
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
