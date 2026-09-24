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
    ``Rin.SettingCard`` / ``Rin.Segmented``），它们自带主题取色。本单例只服务于：

    1. RinUI 没有对应组件、必须手绘的地方（分段控件的选中板与下划线）；
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
    // 尺寸比例全部对照**参考稿实测**（参考稿条高 H = 187 px）：
    //
    //   | 元素                     | 实测      | 占 H   |
    //   |--------------------------|-----------|--------|
    //   | 内容高（= 退出键高）      | 121       | 0.647H |
    //   | 图标（圆占位）直径        | 62        | 0.331H |
    //   | 横向内边距                | 50        | 0.267H |
    //   | 上下内边距                | 33        | 0.176H |
    //   | 底板圆角                  | 25        | 0.134H |
    //   | 分段项宽                  | 192       | 1.027H |
    //   | 分段选中板宽              | 156       | 0.81 项宽 |
    //   | 下划线宽 / 高             | 62 / 11   | 0.331H / 0.059H |
    //   | 退出键 宽×高              | 129 × 121 | 0.69H × 0.647H |
    //
    // 设计语言（与参考稿一致）：
    //   · 圆环是**图标占位**，真实界面里用图标，不做描边圆环
    //   · 分段容器**比底板更暗**并有极淡描边；选中项**比底板更亮**
    //   · 下划线宽度 = 图标宽度，紧贴容器底部
    //   · 退出键 = 略宽于高的强调色圆角块 + 黑色图标（不是白色）

    // ---- 底板 ----
    readonly property int dockPaddingX: 14
    readonly property int dockPaddingY: 10
    readonly property int dockSurfaceRadius: 8
    readonly property real dockSurfaceOpacity: 0.97
    readonly property int dockShadowMargin: 24

    // ---- 控件（图标按钮 / 分段 / 退出共用同一档内容高）----
    readonly property int dockIconSize: 18
    readonly property int dockHitSize: 36
    readonly property int dockControlRadius: 5

    // ---- 分段控件 ----
    readonly property int dockSegmentRadius: 5
    /*! 选中板相对分段项左右各内缩多少（实测 192→156，故约 18；按比例缩到 5）。 */
    readonly property int dockSegmentPlateInset: 5
    // 容器：黑 10% 叠加 → 比底板暗（实测 #292929 vs 底板 #2E2E2E）
    readonly property color dockSegmentBg: themeColors
        ? themeColors.controlAltSecondaryColor : "#1A000000"
    // 容器描边：白 8% → 实测 #3E3E3E
    readonly property color dockSegmentBorder: themeColors
        ? themeColors.controlBorderAccentColor : "#14FFFFFF"
    // 选中板：白 6% 叠在容器上 → 实测 #373737（比底板亮）
    readonly property color dockSegmentCheckedBg: themeColors
        ? themeColors.controlFillColor : "#0FFFFFFF"

    // ---- 分隔线（实测比底板暗，与分段容器同色）----
    readonly property int dockDividerWidth: 1
    readonly property int dockDividerHeight: 20
    readonly property int dockDividerGap: 12
    readonly property color dockDivider: themeColors
        ? themeColors.controlAltSecondaryColor : "#1A000000"

    // ---- 退出键（实测 129×121，略宽于高）----
    readonly property real dockExitWidthRatio: 1.07

    // ---- 页码 ----
    readonly property int dockPagerWidth: 48
    readonly property int dockPagerSpacing: 14
    /*! 页码 pill 的横向内边距明显大于工具条（实测 98/187 = 0.52H）。 */
    readonly property int dockPagerPaddingX: 26

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
