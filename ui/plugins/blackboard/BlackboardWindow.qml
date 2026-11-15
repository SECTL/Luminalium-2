import QtQuick
import RinUI as Rin
import Luminalium
import Luminalium.Ink 1.0
// 2026-10-19 审计 D5：跨目录引用（ink 的 EraserGhost；2026-11-01 起还有
// presentation 的放映条胶囊组件）不违反「插件目录要自足」——那条原则约束的是
// **外部插件**（整目录拷进数据根，拷走即断链）；黑板是内建插件不拷贝，
// 与放映叠加层同款走公共组件同源引用。别拿黑板当外部插件的目录结构范本。
import "../../ink"
import "../../presentation"

/*!
    小黑板插件窗口 —— 可涂写的板书板。

    2026-10-17 用户指令：现有小黑板 UI「丑死了」，按 Lmn-copy 项目的小黑板
    （``plugins/builtins/board/Board.qml``）重做一版「史诗级好看好用」的。
    本次是**纯 UI 重做**：墨迹引擎、导出、快捷键、窗口生命周期全部保留
    既有契约（逐条列在下方），版式照蓝本落地：

    * 板面铺满整个窗口内容区（**全 bleed** —— 旧版四边 10px 边距取消）；
    * 板色 #2A3C34 → **#202020**（蓝本值；黑板就是深色物件，不随主题）；
    * **底部居中悬浮胶囊工具栏**，距底 20，六个工具（粉笔/橡皮/清空/撤销/
      重做/导出）。⚠️ 胶囊本身 2026-11-01 已换成放映控制条同款（见下方
      2026-11-01 条目）；蓝本那版「深灰 90% 底 + 36px 图标位 + 下方 11px
      标签、恒定带标签」随之退役；
    * **色板弹层**：粉笔已选中时再点粉笔钮开合（橡皮态下点粉笔 = 回粉笔，
      蓝本同约定）。⚠️ 2026-11-08 起这一块已换成放映条的 ``PenPaletteCard``
      （见下方同日条目），蓝本那套「18 色 Office 盘 + 底部信息条」与
      「右侧笔宽滑条卡」都已退役 —— 本段保留作版式沿革记录；
    * **滑动清屏弹层**：橡皮已选中时再点橡皮钮开合。滑动确认把误点清屏的
      代价从「整板没了」降到「弹层缩回去」；单击清空钮仍是直接
      ``clearPage()``（蓝本如此；本项目 clearPage 进撤销栈、可整板恢复，
      安全）；
    * 左下圆形全屏钮：与胶囊同底同描边、尺寸 = 胶囊高、左 20 底 20。

    对蓝本的有意偏差（其余照抄蓝本）：
    * 工具钮补 hover 白 8% 填充（蓝本无 hover 态；Fluent 每个可点表面都
      有悬停反馈）；
    * 弹层卡不画投影（蓝本如此；深色板面上投影读不出形，旧版把
      flyout 阴影收小一档正是为了躲窗口下沿切边，这次直接不画）。胶囊与
      全屏钮 2026-11-01 起随放映条底板自带 flyout 投影 —— 那是放映条外观
      的一部分，照搬就整套照搬；笔选单 2026-11-08 换成 ``PenPaletteCard``
      后同样自带 flyout 投影（同一块卡，放映条那边就有）；
    * 默认笔色 #FFFFFF（蓝本初始值；旧版 #F3F3EE 随旧选单退役）；
    * 点色即收弹层（蓝本行为，**覆盖 2026-10-09「选色不收」旧约定**：
      信息条 hover 即读色名 / RGB / HEX，「对比着挑色」由信息条承接，
      选中即收是更果断的交互）；
    * 选中色块的标记从「色块上的 2px 描边」改成「色块外的 2px 描环」
      （PenPaletteCard 的 dockSwatchRing 先例）—— 蓝本的画法在白色 /
      浅色块上完全不可辨（离屏目检实锤）；色块另加常驻 1px 定义线，
      纯黑 / 深蓝块在深卡片底上才立得住。

    2026-11-08 用户指令：「小黑板这个笔工具的二级菜单改成放映界面的那种」。
    蓝本那套「18 色方形色块卡 + 右侧独立笔宽滑条卡」整体退役（``ChalkPalettePopup.qml``
    / ``PenWidthPopup.qml`` 两个文件一并删除），改用放映控制条的
    ``PenPaletteCard`` —— 30 色 × 3 行圆形色点 + 「粗细」四档 + 「预览」波浪，
    一套卡片三个分区。色板 / 粗细档直接读 ``presentation.pen.*``（与放映条
    逐字同源），改放映条的色板黑板跟着变。连带影响：笔宽从连续滑条（1–12）
    变成四档离散值，默认值从 3 改成配置里的 ``default_width``（4）。

    2026-11-01 用户指令：「小黑板的胶囊太丑了，改成和放映界面一样的胶囊，
    文字显示按放映界面的胶囊设置来，就算打开了文字显示也要显示在图标右边」。
    胶囊与左下全屏钮**直接复用**放映控制条的组件（``import "../../presentation"``）：

    * 底板 = ``FlyoutSurface``（62 高、内边距 9、全圆、65% 半透明 + CW2 渐变
      高光环 + flyout 投影），与放映条底中那条同一块底板；
    * 粉笔 / 橡皮 = ``ToolSegment`` + ``ToolSegmentItem``（放映条「指针 / 笔 /
      橡皮」那个深色胶囊槽 + 圆形分页）；清空 / 撤销 / 重做 / 导出 = 44px
      圆钮（``BoardToolButton`` → ``IconButton``）。槽与动作钮之间不加分隔线
      （放映条同款：槽自带胶囊容器，紧跟竖线是「双层边」）。
    * **「显示按钮文本」读 ``Backend.presentationConfig.buttons.show_labels``**，
      与放映条同一个开关（入口：主界面编辑器 → 选中工具栏），改了两边一起
      变。关 = 纯图标圆钮 + 悬停提示名字；开 = 文字接在**图标右边**、钮长成
      胶囊（IconButton / ToolSegmentItem 的版式），不再有蓝本「标签在下」那档。
      放映条的缩放倍率（``presentation.scale``）不接：那是放映叠加层的尺寸，
      黑板窗口自己能拉伸。
    * **取色钉在 RinUI 深色档**（``capsuleSurfaceColor`` 等读 ``Rin.Theme.dark``）：
      放映条随主题翻，黑板悬浮件不翻 —— 板面恒深、三张弹层卡恒深，胶囊单独
      变浅会和它们打架；深色主题下与放映条逐值一致。
    * 选单开着时对应工具描一圈强调色环（放映条 ``expanded`` 同款）：粉笔 ↔
      色板，橡皮 ↔ 滑动清屏 —— 告诉用户「再点一下能收」。
    * 胶囊 / 全屏钮的命中矩形 = 可见底板：``FlyoutSurface`` 自带 24px 投影
      余量，整块挂进 ``excludedItems`` / 吸收 hover 会在胶囊外圈留一道写不上
      字、不出幻影的死区，所以外层 Item 只框底板。
    * 光标：胶囊与全屏钮上一律箭头（放映条同款）；吸收层显式给 ArrowCursor，
      否则会漏出板面 HoverHandler 的十字。旧版工具钮的手型光标随旧钮退役。
    * 全屏钮提示改用 IconButton 自带的 ToolTip（delay 600）。t29 U4 的判断
      「delay 只对 open()/popup() 生效、声明式 visible 绑定下无效」不成立：
      2026-11-01 PySide6 6.11.2 离屏实测，``visible`` 绑定翻 true 后 150 /
      400ms 未显示、1000ms 显示，delay 照常生效。手搓的计时器提示随之撤掉。
    * 最小宽度改成跟着胶囊实宽算（文字打开后胶囊约 591 宽，写死 480 会让
      胶囊压到全屏钮上），推导见 ``minimumWidth`` 处注释。
    * 分段的两页是静态子项，``contentWidth`` 必须显式给，否则槽窄 3px、粉笔
      圆钮探出槽外（根因见 ``toolSegment`` 处注释）。
    * 离屏证据：``.omo/evidence/cpp-blackboard-dock-capsule.py``（放映条参照 +
      黑板各态出图到 ``preview/cpp_bb_*.png``，带几何断言）。

    2026-11-01 用户报告：「在默认窗口大小画了点东西然后擦掉，点最大化后又有一些
    神秘的笔迹」。根因在墨迹层：点按 0..1 归一化存、笔宽按逻辑 px 存，改尺寸重烘
    时位置按横竖两个倍率拉伸、宽度不动，像素橡皮与笔迹的覆盖关系变了，擦净处露出
    月牙形残片。InkLayer 加 ``scaleWithSize`` 开关，黑板设 false：归一化基准锁在
    首次烘焙时的尺寸，最大化 / 还原只是板面变大变小，已画的东西原地不动（放映叠加
    层保持缺省 true，随画面缩放）。代价：还原窗口时超出新边界的板书暂时看不见，
    导出也只抓当前看得见的部分。复现与回归：``tests/ink_resize_selftest.cpp``。

    2026-10-19 插件审计 todo 29（B3/B4/U2-U5）一致性收口：
    * E/B 快捷键与清空钮补「先收弹层」——撤销/重做/导出三钮一直都有，
      就这两处漏口径：弹层开着切工具，弹层悬在新工具态上；开弹层时
      点清空，无声重置屏幕。快捷键照按钮的收口镜像（E 收色板 /
      B 收滑动清屏）。
    * 导出文件名同秒去重（B4）：秒级时间戳撞名，放映讲台上连按两次
      导出，第二张无声盖掉第一张——同秒续按追加 ``-2/-3`` 序号。
    * 结果提示带目录（U3）+ 空板清空给「板已空」反馈（U2，清空钮与
      滑动确认两条路径）：提示是放映中唯一不打断的回执，要说清去向、
      空操作也要有下文。
    * 全屏钮 ToolTip 要 600ms 延迟（U4）。当时的计时器实现与「delay 在
      声明式 visible 下无效」的判断已于 2026-11-01 撤销（实测 delay 有效，
      见上方 2026-11-01 条目），延迟语义现由 IconButton 的 delay 600 承接。
    * 笔宽滑条顶部加常驻当前值（U5，改动全在 PenWidthPopup.qml）。
      ⚠️ 2026-11-08 滑条卡随笔选单改版退役（换成放映条 ``PenPaletteCard``
      的四档粗细），本条只剩历史价值。

    ======================= 保留契约（每条注明出处）=======================

    * **InkLayer 墨迹层**（2026-10-08 用户指令，照搬叠加层自建批注）：
      笔画平滑滤波、像素橡皮真擦除（透出下层板色矩形）、PageStore 真操作
      栈（落笔 / 擦除 / 清屏全进栈，清空可撤销）、增量烘焙。板面结构 =
      容器 Item（``blackboardBoard``，导出抓图目标）里先铺板色矩形再放
      铺满的 InkLayer —— InkLayer 自身透明只画墨，板色必须由下层矩形
      提供（像素橡皮透出它、导出 PNG 底色靠它）。
    * **导出 PNG**（2026-10-08）：抓 ``boardContainer`` 整棵子树（悬浮件
      不进图）；启用条件只看 ``exportDir !== ""``（PageStore 没有「本页
      有墨」判据，空板导出纯板色 PNG 无害）；结果提示 Text + Timer 2 秒
      淡出，不弹系统对话框（放映中弹对话框是教学事故）。
    * **快捷键**（窗口作用域，黑板藏起来时必须失效）：Ctrl+Z 撤销 /
      Ctrl+Y 重做 / E 橡皮 / B 粉笔。写死不做可配置（讲课要肌肉记忆）。
    * **关窗路径**：``onClosing`` → ``Backend.triggerAction(
      "plugin:blackboard:close")`` → 句柄 hide；窗口懒创建、只藏不销毁，
      InkLayer 实例与笔画随窗口存续，隐藏不丢板书。
    * **隐藏常驻导航栏**：本窗口无导航项，``Component.onCompleted`` 里
      ``navigationView.navigationBar.visible = false``（藏而不改 RinUI
      包 —— site-packages 不许动）。
    * **全屏 = 最大化 ↔ 还原**（2026-10-09 真机实测）：⚠️ 不许用
      ``Window.FullScreen`` —— 进入正常但**退出**时 GUI 线程在
      ``setProperty(visibility, Windowed)`` 里同步卡死（RinUI/Win32 非
      客户区处理与全屏还原相冲，裸建窗口与全接管路径都复现，修不了也不
      绕过）；最大化往返实测干净。``fullScreenOn`` 绑
      ``visibility === Window.Maximized`` 而不是自存状态 —— 标题栏最大化
      钮点出来的态图标也得跟得上。
    * **EraserGhost 橡皮幻影**（2026-10-09 用户指令，希沃同款）：板面上
      InkLayer 之后铺一份（``ui/ink/``，绑层的 ``eraserGhost*`` 属性），
      不吃输入、不进导出抓图。
    * **悬浮件排除**（2026-10-10 用户指令：鼠标移到悬浮件上不显橡皮
      幻影）：InkLayer ``excludedItems`` 挂上胶囊 / 全屏钮 / 三张弹层卡，
      胶囊与全屏钮另盖 ``hoverEnabled`` MouseArea 吸收 hover（两者都只框
      可见底板，不含投影余量，见 2026-11-01 条目）。
    * **悬浮件固定深色、不随主题**（黑板就是深色物件）；⚠️ 描边禁用
      ``Lumi.hairline``（浅色档它是黑 8%，压在深底上不可见 ——
      ``Lumi.hairline`` 头注释那个坑的反向版）：弹层卡用固定白 hairline，
      胶囊 / 全屏钮用 RinUI 深色档令牌（``capsuleSurfaceColor`` /
      ``capsuleBorderColor``）。
    * **弹层吞噬层**：任一弹层开着时盖住板面，第一按消费成「收起弹层」
      不起笔（PenPaletteCard 在放映叠加层的同款先例）。
    * **objectName 契约**（离屏脚本按名找）：``blackboardBoard`` /
      ``blackboardInkLayer`` / ``blackboardToolbar``（胶囊的可见底板，
      2026-11-01 前是胶囊里的按钮行）/ ``blackboardChalkButton`` /
      ``blackboardEraserButton`` / ``blackboardClearButton`` /
      ``blackboardUndoButton`` / ``blackboardRedoButton`` /
      ``blackboardExportButton`` / ``blackboardFullScreenButton`` /
      ``blackboardPalettePopup`` / ``blackboardResultHint``（结果提示
      文本，t29 起承担导出与空板两类反馈）。

    2026-11-01 Python 侧同步注记（本文件自 C++ 版 ``cpp-version/qml/plugins/
    blackboard/BlackboardWindow.qml`` 整体搬迁）：上面所有历史条目原样保留 ——
    它们是决策记录，与宿主语言无关。Python 侧的差异只有三处，都落在
    ``ui/plugins/blackboard/`` 与 ``app/plugins/blackboard/plugin.py`` 之内：
    ``presentation/`` 的组件已在 2026-11-01 同步到与 C++ 版同一套接口
    （``FlyoutSurface.surfaceColor/borderColor``、``IconButton`` 的 ToolTip），
    所以本文件对它们的引用逐字照搬；``InkLayer`` 的 ``scaleWithSize`` /
    ``excludedItems`` 由 ``app/ink/layer.py`` 回植，属性名一致；位置记忆
    （C++ ``registerWindow`` 第 4 参 ``rememberPosition``）Python 侧暂无对应
    参数，见 ``plugin.py`` 的说明。
*/
Rin.FluentWindow {
    id: boardWindow

    title: qsTr("小黑板")
    visible: false
    width: 760
    // 2026-11-08：默认高从 540 提到 640 —— 笔选单换成放映条 ``PenPaletteCard``
    // 后卡片高 ≈352（旧蓝本色板卡 ≈163），540 的窗口里弹层会顶到上沿、板面
    // 只剩一条缝。
    height: 640
    // ⚠️ 最小宽度跟着胶囊实宽走（2026-11-01 放映条胶囊，旧「480」口径作废）：
    //   左下全屏钮直径 62、左距 20 → 右沿 82，与居中的胶囊留 8 间隙；RinUI
    //   窗口内容区左右各内缩 ``Utils.windowDragArea``（5，FluentWindowBase 的
    //   拖拽边，离屏实测内容区 = 窗宽 − 10）：
    //   (W − 10 − 胶囊宽) / 2 ≥ 90 → W ≥ 胶囊宽 + 190。胶囊宽随「显示按钮
    //   文本」变：纯图标 303（槽 92 + 间距 5 + 四钮 188 + 内边距 18）→ W ≥ 493；
    //   文字打开约 591 → W ≥ 781 左右（按字宽实算，不写死）。窗口比它窄时
    //   Qt 会把窗口撑到新的最小宽。
    //   弹层钳制校核（2026-11-08 笔选单改版后重算）：``PenPaletteCard`` 内容宽
    //   = 10 列 × 30 + 9 × 10 = 390，加内边距 32 = **卡片 422**（投影余量 20×2
    //   另计，摆位按 ``cardWidth`` 不按 ``width``）。两侧各留 8 → 438。
    //   ⚠️ 这比旧蓝本色板（312）宽了 110，所以最小宽不能再取 493 —— 见下面的
    //   取法：``Math.max(胶囊推导, 卡片钳制)``，两个约束都得满足。
    //   高度：卡片 ≈ 352（三段内容 + 内边距，实测见 preview 的
    //   ``plugin_blackboard_palette.png``），落位需要 8（钳制）+ 352 + 12（间隙）
    //   + 62（胶囊）+ 20（底距）= 454；加 RinUI 标题栏（≈48）→ 502，取 520 留余量。
    minimumWidth: Math.max(
        Math.ceil(capsule.width + 2 * (Rin.Utils.windowDragArea
                 + fullScreenButton.x + fullScreenButton.width + 8)),
        // 笔选单卡片 + 两侧各 8 的钳制留白（内容区比窗宽少 10，见上一段）
        Math.ceil(palettePopup.cardWidth + 2 * 8 + 2 * Rin.Utils.windowDragArea))
    minimumHeight: 520

    onClosing: function (event) {
        event.accepted = false
        Backend.triggerAction("plugin:blackboard:close")
    }

    Component.onCompleted: {
        // FluentWindow 常驻一条 NavigationBar（左侧 rail + ≡ 折叠按钮），
        // 本窗口没有任何导航项，空 rail 和 ≡ 是纯干扰。NavigationBar 在
        // NavigationView 的 RowLayout 里，不可见即被布局跳过，内容区自动
        // 铺满；标题在 titleBarLeadingHost 里，不受影响。藏它而不改 RinUI
        // 包（AGENTS.md 铁律：site-packages 不许动）。
        navigationView.navigationBar.visible = false
    }

    // ------------------------------------------------ 快捷键
    // 窗口作用域（Shortcut 默认 context）——黑板藏起来时这些键必须失效，
    // 不然用户在本子外按个 E 就把模式翻了。不做成可配置键位：讲课场景
    // 要的是肌肉记忆，四个键写死够用（todo 9 指令明确不加可配置）。
    Shortcut {
        sequence: "Ctrl+Z"
        onActivated: inkLayer.undo()
    }
    Shortcut {
        sequence: "Ctrl+Y"
        onActivated: inkLayer.redo()
    }
    Shortcut {
        sequence: "E"
        // 快捷键照按钮路径的收口镜像（B3，2026-10-19 插件审计）：色板
        // 弹层属粉笔态，切去橡皮前先收——开着弹层翻工具，弹层悬在新
        // 工具态上，下一次落墨前还得先被它吞一按。
        onActivated: {
            boardWindow.paletteOpen = false
            boardWindow.eraserOn = true
        }
    }
    Shortcut {
        sequence: "B"
        // 同源镜像：滑动清屏弹层属橡皮态
        onActivated: {
            boardWindow.slideClearOpen = false
            boardWindow.eraserOn = false
        }
    }

    // ------------------------------------------------ 板面与笔的状态
    /*! 板色 #202020（蓝本值，不随主题 —— 黑板就是深色物件）。 */
    readonly property color boardColor: "#202020"

    property bool eraserOn: false
    /*! 当前粉笔色（``presentation.pen.palette`` 之一；默认白 —— 深色板面上
        白粉笔是蓝本的初始值，也是板书最常用的颜色）。 */
    property color penColor: "#FFFFFF"
    /*! 当前笔宽（``presentation.pen.widths`` 四档之一；默认 4 = 配置里的
        ``default_width``。2026-11-08 起笔选单改成放映条同款后，笔宽不再由
        滑条连续给值，只从四档里挑 —— 档位表与放映条同一份，别在这里另立）。 */
    property real penWidth: 4
    /*! 笔选单开合；只在「粉笔已选中时再点粉笔钮」翻转，点色即收
        （蓝本行为，见头注释偏差清单）。 */
    property bool paletteOpen: false
    /*! 「滑动清屏」弹层开合；只在「橡皮已选中时再点橡皮钮」翻转。 */
    property bool slideClearOpen: false
    /*! 「填满屏幕」态 —— 绑 visibility 而不是自存：标题栏最大化钮
        点出来的最大化也要让左下圆钮的图标跟着翻（实测退回最大化的理由
        见头注释保留契约）。 */
    readonly property bool fullScreenOn: visibility === Window.Maximized

    // ------------------------------------------------ 悬浮件的固定深色档
    // 不随主题（与板色同一套理由）；浅色档的 Lumi 令牌压在深底上不可见，
    // 禁用 Lumi.hairline 的理由见头注释保留契约。胶囊 / 全屏钮的底色与描边
    // 取 RinUI **深色档**的同名令牌（2026-11-01）：放映条在深色主题下就是这两个
    // 值，这里不管当前主题是什么都钉在它上面。冒号后是主题对象缺席时的兜底
    // （与 RinUI dark.qml 同值）。
    readonly property var _darkColors: Rin.Theme.dark ? Rin.Theme.dark.colors : null
    readonly property color capsuleSurfaceColor: _darkColors
        ? _darkColors.backgroundAcrylicColor : "#2C2C2C"
    readonly property color capsuleBorderColor: _darkColors
        ? _darkColors.windowBorderColor : "#12757575"

    /*! 「显示按钮文本」—— 与放映控制条同一个开关（``presentation.buttons.
        show_labels``，2026-11-01 用户指令：按放映界面的胶囊设置来），打开后
        文字接在图标右边。无 Backend 的预览宿主当关。 */
    readonly property bool showLabels: typeof Backend !== "undefined"
        && Backend.presentationConfig.buttons !== undefined
        && Backend.presentationConfig.buttons.show_labels === true

    // ------------------------------------------------ 笔选单的配置（放映条同源）
    // 2026-11-08 用户指令「笔的二级菜单改成放映界面的那种」：色板 / 粗细档 /
    // 小标题全部读 ``presentation.pen.*``，与放映条 ``PresentationDock`` 逐字
    // 同源（那边也是整块读这三个键）。无 Backend 的预览宿主走下面的兜底值 ——
    // 卡片在预览里也得画得出来，不能因为缺配置就空着。
    readonly property var _penCfg: typeof Backend !== "undefined"
        && Backend.presentationConfig.pen !== undefined
        ? Backend.presentationConfig.pen : ({})

    /*! 色板（``presentation.pen.palette``，30 色 = 3 行 × 10 列）。 */
    readonly property var penPaletteColors: _penCfg.palette !== undefined
        ? _penCfg.palette : []

    /*! 色板每行几格（``presentation.pen.columns``，10 = PowerPoint 调色板列数）。 */
    readonly property int penPaletteColumns: _penCfg.columns !== undefined
        ? Number(_penCfg.columns) : 10

    /*! 粗细档（``presentation.pen.widths``，四档逻辑 px）。 */
    readonly property var penPaletteWidths: _penCfg.widths !== undefined
        ? _penCfg.widths : []

    readonly property string penLabelColor: _penCfg.label_color !== undefined
        ? String(_penCfg.label_color) : qsTr("颜色")
    readonly property string penLabelPreview: _penCfg.label_preview !== undefined
        ? String(_penCfg.label_preview) : qsTr("预览")
    /*! 「粗细」段的小标题没有独立配置键（放映条那边写死在 PenPaletteCard
        的缺省值里），这里跟着用同一句。 */
    readonly property string penLabelWidth: qsTr("粗细")

    /*! 按下粉笔 / 橡皮那一刻橡皮是否开着。``clicked`` 落地时 TabBar 早把
        currentIndex（→ eraserOn）换好了，那时再读分不清「切工具」和「再点
        一次」—— 放映条 ``noteToolPress`` 同一个坑。 */
    property bool _eraserBeforePress: false

    // 快捷键 / 点色回粉笔等**胶囊之外**的路径改了 eraserOn：同步分段的选中页
    // （点击会打断 currentIndex 的绑定，放映条底部 Connections 同款兜底）
    onEraserOnChanged: {
        var index = eraserOn ? 1 : 0
        if (toolSegment.currentIndex !== index)
            toolSegment.currentIndex = index
    }

    /*! 板书导出目录（file URL 字符串带尾斜杠，Python 注册期经
        ``app/plugins/blackboard/plugin.py`` 的 ``_push_export_dir()`` 推来；
        空串 = 还没推送 / 目录不可用，导出按钮保持禁用）。 */
    property string exportDir: ""

    // ------------------------------------------------ 板书导出 PNG
    /*! 导出文件名时间戳 ``yyyyMMdd-HHmmss``（Windows 文件名禁冒号）。 */
    function _exportTimestamp() {
        var d = new Date()
        function pad(n) { return (n < 10 ? "0" : "") + n }
        return String(d.getFullYear())
            + pad(d.getMonth() + 1) + pad(d.getDate()) + "-"
            + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds())
    }

    // 同秒重名去重状态（B4）：「上一张落的是哪一秒 + 同秒内第几张」。
    property string _lastExportStamp: ""
    property int _lastExportSeq: 0

    /*! 导出文件名：``板书-<yyyyMMdd-HHmmss>``，同秒第二次起在尾巴上
        追加 ``-2/-3``。跨秒互不相干，序号只在同一秒内续（B4，2026-10-19
        插件审计：放映讲台上连按两次导出是很真实的操作）。 */
    function _exportName() {
        var stamp = _exportTimestamp()
        if (stamp === _lastExportStamp) {
            _lastExportSeq += 1
        } else {
            _lastExportStamp = stamp
            _lastExportSeq = 1
        }
        var name = "板书-" + stamp
        return _lastExportSeq === 1 ? name : name + "-" + _lastExportSeq
    }

    /*! 导出目录的本地路径显示形（U3）：file:/// 前缀剥掉 + 百分号解码。 */
    function _localExportDir() {
        return decodeURIComponent(exportDir.substring("file:///".length))
    }

    /*! 一键导出板书 PNG 到 ``exportDir``。
        抓的是板面容器整棵子树（板色矩形 + InkLayer 的自定义场景图节点）：
        ``grabToImage`` 离屏渲染 item 子树，自定义 SG 节点照常进图 ——
        抓 InkLayer 本身会丢板色（层的底色是透明的），抓窗口又会带上
        胶囊与全屏钮，所以容器是唯一正确目标。空板也照导（理由见保留
        契约）。失败不炸：``saveToFile`` 返回 false 时只把提示换成
        「导出失败」。 */
    function exportBoard() {
        if (exportDir === "") return
        // 文件名在进抓图回调**之前**定死（B4 的另一半）：名字若放回回调
        // 里现算，连按两次导出的两张图拿到的是「同一秒的同一个名字」——
        // 谁后保存谁覆盖谁；先定死，落盘自然各自排队互不相扰。
        var name = _exportName()
        // 提示带目录（U3）：放映中的提示是唯一不打断的回执，「已导出」
        // 不告诉去向，等于没说。
        var dirText = _localExportDir()
        boardContainer.grabToImage(function (result) {
            var ok = result.saveToFile(exportDir + name + ".png")
            showExportHint(ok ? qsTr("已导出至 %1").arg(dirText)
                              : qsTr("导出失败"))
        })
    }

    /*! 2 秒淡出的结果提示（SpotlightOverlay 开场提示同款写法）。 */
    function showExportHint(msg) {
        exportHintText.text = msg
        exportHintTimer.restart()
    }

    /*! 全屏切换（左下圆钮）。⚠️ 用**最大化**落地而不是
        ``Window.FullScreen`` —— 真全屏的**退出**在这套 RinUI 窗口上会
        同步卡死 GUI 线程（2026-10-09 实测证据见头注释保留契约）。 */
    function toggleFullScreen() {
        visibility = fullScreenOn ? Window.Windowed : Window.Maximized
    }

    // ================================================ 板面
    // 容器 = 板色矩形 + 铺满的 InkLayer；导出抓图以它为目标（悬浮件不进图）。
    // 全 bleed 铺满窗口内容区（2026-10-17 蓝本版式：旧版四边 10px 取消）。
    Item {
        id: boardContainer
        objectName: "blackboardBoard"

        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            color: boardWindow.boardColor
        }

        InkLayer {
            id: inkLayer
            objectName: "blackboardInkLayer"
            anchors.fill: parent
            // 改尺寸不拉伸已画的东西（2026-11-01，见头注释同日第二条）：最大化 =
            // 板面变大，还原 = 边缘那块暂时看不见、再放大就回来。缺省的随尺寸缩放
            // 会让擦净的墨迹在最大化后露出残片（机理见 InkLayer.h scaleWithSize）。
            scaleWithSize: false

            tool: boardWindow.eraserOn ? "eraser" : "pen"
            penColor: boardWindow.penColor
            penWidth: boardWindow.penWidth
            // 沿用「橡皮 = 笔宽 × 6」的手感：橡皮的本职是快速抹掉一片。
            // ⚠️ 有意硬编码（设计取舍标注，2026-10-28 审查确认）：不跟
            // 放映叠加层的 eraser_widths 配置档走 —— 黑板笔宽档少（见色板
            // 卡），×6 随笔宽连续缩放已够用；若黑板要出橡皮粗细档再换配置。
            eraserWidth: boardWindow.penWidth * 6
            // 排除悬浮件（2026-10-10 用户指令：鼠标在悬浮件上不显橡皮幻影）。
            // 2026-11-08 起笔选单只有一张卡（PenPaletteCard 替掉蓝本色板 + 滑条），
            // ``widthPopup`` 随滑条卡一起退役。
            excludedItems: [
                capsule, fullScreenButton,
                palettePopup, slideClearPopup,
            ]
            // 手掌擦除参数用 InkLayer 默认（20mm / enabled），不接线配置。
            // 因果写正（2026-10-19 审计 D6）：层的 palmEraseEnabled 默认
            // 就是 true（``app/ink/layer.py`` 的 ``_palm_erase_enabled = True``、
            // ``_palm_threshold_mm = 20.0``），黑板沿用即得——触屏板书手掌会搁在
            // 板面上，防掌误触在这同样是真需求，并非「放映叠加层才有的
            // 场景」（旧注因果反）。
        }

        // 橡皮幻影（2026-10-09 用户指令，希沃同款）：按下橡皮期间跟着触点
        // 走的灰橡皮块，与层同一坐标系铺在层上（EraserGhost 不吃输入，
        // 导出抓图目标是 boardContainer —— 幻影只在按下擦除那一瞬可见，
        // 抓图触发于按钮点击、彼时幻影必不在场，不进图）
        EraserGhost {
            anchors.fill: parent
            inkLayer: inkLayer
        }

        // InkLayer 只管笔画不管光标；光标由它提供（粉笔 = 十字瞄准落点，
        // 橡皮 = SizeAll 四向箭头 —— 手型光标的语义是「这里有个可点的
        // 链接」，SizeAll 才读作「大面积挪动/擦除」）
        HoverHandler {
            cursorShape: boardWindow.eraserOn ? Qt.SizeAllCursor : Qt.CrossCursor
        }

        // 弹层开着时的吞噬层：板面上的第一按消费成「收起弹层」、不起笔
        // （PenPaletteCard 同款先例，见头注释保留契约）。禁用的 MouseArea
        // 对事件透明 —— 弹层关着时按下照常穿透到 InkLayer 落墨。
        // enabled 时 hoverEnabled 也开（P2-7）：否则 hover 穿到 InkLayer，
        // 橡皮幻影在弹层开着时跟鼠标跑，而第一按却被消费成收弹层 ——
        // 「幻影在」和「按下收卡」连着出现，橡皮就是落不下去。
        MouseArea {
            anchors.fill: parent
            enabled: boardWindow.paletteOpen || boardWindow.slideClearOpen
            hoverEnabled: true
            onPressed: {
                boardWindow.paletteOpen = false
                boardWindow.slideClearOpen = false
            }
        }
    }

    // ================================================ 底部居中胶囊工具栏
    // 2026-11-01 起与放映控制条底中那条同一套组件（版式、取色、文字开关的来历
    // 见头注释 2026-11-01 条目）。外层 Item 只框**可见底板**：FlyoutSurface
    // 自带 24px 投影余量，按它的外框挂 excludedItems / 吸收 hover 会在胶囊外圈
    // 留一道写不上字的死区。
    Item {
        id: capsule
        // objectName 供离屏验收脚本量胶囊实宽（minimumWidth 护栏）
        objectName: "blackboardToolbar"

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 20
        width: capsuleSurface.implicitWidth - capsuleSurface.margin * 2
        height: capsuleSurface.implicitHeight - capsuleSurface.margin * 2

        // 吸收 hover 防止底层 InkLayer 收到胶囊区移动（2026-10-10 自建批注）；
        // 光标显式给箭头，否则会漏出板面 HoverHandler 的十字
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            cursorShape: Qt.ArrowCursor
        }

        FlyoutSurface {
            id: capsuleSurface
            x: -capsuleSurface.margin
            y: -capsuleSurface.margin
            surfaceColor: boardWindow.capsuleSurfaceColor
            borderColor: boardWindow.capsuleBorderColor

            // 粉笔 / 橡皮 = 放映条「指针 / 笔 / 橡皮」那个分段槽。currentIndex
            // 绑 eraserOn；点击会打断这条绑定，eraserOn 由别处改时靠根上的
            // onEraserOnChanged 同步回来
            ToolSegment {
                id: toolSegment
                currentIndex: boardWindow.eraserOn ? 1 : 0
                onCurrentIndexChanged: boardWindow.eraserOn = currentIndex === 1
                // ⚠️ contentWidth 必须显式给（2026-11-01 离屏实测）：两页是**静态
                // 子项**，它们的 implicitWidth 先于 ToolSegment 的 ``spacing:
                // itemSpacing`` 求值，TabBar 按样式缺省 spacing（1）算出 89，
                // spacing 变成 4 之后不重算 —— 槽窄 3px，ListView 为把当前页放进
                // 可视区左移 3px，粉笔圆钮探出槽外。放映条的分页由 Repeater 晚建，
                // spacing 早已就位，没有这个问题。
                contentWidth: chalkSegmentItem.implicitWidth
                              + eraserSegmentItem.implicitWidth + spacing

                ToolSegmentItem {
                    id: chalkSegmentItem
                    objectName: "blackboardChalkButton"
                    icon.name: "ic_fluent_pen_20_regular"
                    label: qsTr("粉笔")
                    tooltip: label
                    showLabel: boardWindow.showLabels
                    expanded: boardWindow.paletteOpen
                    onPressed: boardWindow._eraserBeforePress = boardWindow.eraserOn
                    // 粉笔已选中时再点 = 开合色板弹层；橡皮态下点 = 回到粉笔
                    // （蓝本同约定，与 PenPaletteCard「当前工具再点一下出选单」一致）
                    onClicked: {
                        if (boardWindow._eraserBeforePress) {
                            boardWindow.eraserOn = false
                        } else {
                            boardWindow.paletteOpen = !boardWindow.paletteOpen
                        }
                        boardWindow.slideClearOpen = false
                    }
                }
                ToolSegmentItem {
                    id: eraserSegmentItem
                    objectName: "blackboardEraserButton"
                    icon.name: "ic_fluent_eraser_20_regular"
                    label: qsTr("橡皮")
                    tooltip: label
                    showLabel: boardWindow.showLabels
                    expanded: boardWindow.slideClearOpen
                    onPressed: boardWindow._eraserBeforePress = boardWindow.eraserOn
                    // 橡皮已选中时再点 = 开合「滑动清屏」弹层（蓝本同约定）
                    onClicked: {
                        if (boardWindow._eraserBeforePress) {
                            boardWindow.slideClearOpen = !boardWindow.slideClearOpen
                        } else {
                            boardWindow.eraserOn = true
                        }
                        boardWindow.paletteOpen = false
                    }
                }
            }

            // 清空 / 撤销 / 重做 / 导出 = 放映条动作组同款 44px 圆钮（间距同
            // Lumi.dockButtonSpacing）。不加分隔线，理由见头注释 2026-11-01 条目
            Row {
                spacing: Lumi.dockButtonSpacing

                BoardToolButton {
                    objectName: "blackboardClearButton"
                    iconName: "ic_fluent_delete_20_regular"
                    label: qsTr("清空")
                    showLabel: boardWindow.showLabels
                    // 清空走 store.clear_page（_ClearOp 进撤销栈，可整板恢复），
                    // enabled 与撤销同源：有东西可撤销时板上才有东西可清
                    enabled: inkLayer.canUndo
                    // 单击直接清屏（蓝本如此；滑动确认在橡皮弹层里，见头注释）
                    onClicked: {
                        // 撤销/重做/导出三钮都是「先收弹层再动作」，清空是唯
                        // 一漏收的（B3，2026-10-19 插件审计）：开弹层时误点
                        // 相邻的清空，弹层盖在重置后的屏幕上毫无来由。
                        boardWindow.paletteOpen = false
                        boardWindow.slideClearOpen = false
                        // clearPage() 对空板返回 false——橡皮擦空但操作栈还
                        // 在时钮照样可点，这时给「板已空」反馈而不是毫无
                        // 动静（U2）
                        if (!inkLayer.clearPage())
                            showExportHint(qsTr("板已空"))
                    }
                }
                BoardToolButton {
                    objectName: "blackboardUndoButton"
                    iconName: "ic_fluent_arrow_undo_20_regular"
                    label: qsTr("撤销")
                    showLabel: boardWindow.showLabels
                    // 绑层的真操作栈（PageStore），清空也进栈 —— 清空之后恰恰
                    // 是最要点撤销的时刻，绑「有没有墨」就点不动了
                    enabled: inkLayer.canUndo
                    onClicked: {
                        boardWindow.paletteOpen = false
                        boardWindow.slideClearOpen = false
                        inkLayer.undo()
                    }
                }
                BoardToolButton {
                    objectName: "blackboardRedoButton"
                    iconName: "ic_fluent_arrow_redo_20_regular"
                    label: qsTr("重做")
                    showLabel: boardWindow.showLabels
                    enabled: inkLayer.canRedo
                    onClicked: {
                        boardWindow.paletteOpen = false
                        boardWindow.slideClearOpen = false
                        inkLayer.redo()
                    }
                }
                BoardToolButton {
                    objectName: "blackboardExportButton"
                    iconName: "ic_fluent_arrow_export_up_20_regular"
                    label: qsTr("导出")
                    showLabel: boardWindow.showLabels
                    // 启用只看导出目录有没有推来：空板导出一张纯板色 PNG 无害
                    // （PageStore 没有「本页有墨」的 QML 判据，理由见保留契约）
                    enabled: boardWindow.exportDir !== ""
                    onClicked: {
                        boardWindow.paletteOpen = false
                        boardWindow.slideClearOpen = false
                        boardWindow.exportBoard()
                    }
                }
            }
        }
    }

    // ================================================ 笔的选单（放映条同款）
    // 2026-11-08 用户指令：「小黑板这个笔工具的二级菜单改成放映界面的那种」。
    // 原先的「18 色蓝本色板卡 + 右侧独立笔宽滑条卡」两张卡整体退役，换成放映
    // 控制条的 ``PenPaletteCard``（``import "../../presentation"`` 已在文件顶部）：
    // 30 色 × 3 行网格 + 「粗细」四档 + 「预览」波浪，一套卡片三个分区。
    //
    // 色板 / 粗细档**直接读 ``presentation.pen.*``**（与放映条同一个配置源）：
    // 放映条那边改色板，黑板跟着变 —— 用户要的是「放映界面那种」，不是另一套
    // 长得像的。``show_labels`` 已经是同一条共享口径，这里沿用同一纪律。
    //
    // ⚠️ 与小_黑板旧卡的差异（有意为之，别再按蓝本改回去）：
    //   * 圆角 8 / 30px 圆形色点 / 外圈描环，取代 12 圆角 / 24px 方形块 / 内缩描边；
    //   * 笔宽从连续滑条（1–12）变成四档离散值 —— 与放映条一致，黑板墨迹层
    //     本来就是同一个 ``InkLayer.penWidth``，没有语义损失；
    //   * 卡片浮在胶囊正上方居中（不再与滑条卡拼成左右两块，钳制只剩一份）。
    PenPaletteCard {
        id: palettePopup
        objectName: "blackboardPalettePopup"

        opened: boardWindow.paletteOpen
        selectedColor: boardWindow.penColor
        palette: boardWindow.penPaletteColors
        columns: boardWindow.penPaletteColumns
        widths: boardWindow.penPaletteWidths
        selectedWidth: boardWindow.penWidth
        titleColor: boardWindow.penLabelColor
        titlePreview: boardWindow.penLabelPreview
        titleWidth: boardWindow.penLabelWidth

        // 点色 = 选色 + 回粉笔 + 收卡（蓝本旧行为；放映条那边点色不收，
        // 黑板是板书工作面，选完就该继续写）
        onColorPicked: function (c) {
            boardWindow.penColor = c
            boardWindow.eraserOn = false
            boardWindow.paletteOpen = false
        }
        // 点粗细档：收卡后接着写（同点色），不切工具
        onWidthPicked: function (v) { boardWindow.penWidth = v }

        // 卡片本体（不含投影余量）浮在胶囊正上方 12px，钳进窗口四边留 8。
        // ⚠️ 用 ``cardWidth`` / ``cardHeight`` 而不是 ``width`` / ``height`` ——
        // 后者含 20px 投影余量，按它摆会多浮出一截（见 PenPaletteCard 头注释）。
        x: Math.round(Math.min(
            Math.max(8, capsule.x + capsule.width / 2 - cardWidth / 2),
            boardWindow.width - cardWidth - 8))
        y: Math.round(Math.max(8, capsule.y - 12 - cardHeight - shadowMargin))
    }

    // ================================================ 「滑动清屏」弹层
    // 胶囊正上方居中（钳进窗口四边留 8），与色板弹层互斥（开合逻辑见
    // 胶囊按钮：色板只在粉笔态开合，清屏只在橡皮态开合，切换工具即收）。
    SlideClearPopup {
        id: slideClearPopup

        opened: boardWindow.slideClearOpen
        onTriggered: {
            // 空板滑动确认同样给反馈（U2）：滑完整条确认手势等来悄无声
            // 息，比清空钮更让人怀疑黑板坏了
            if (!inkLayer.clearPage())
                showExportHint(qsTr("板已空"))
            boardWindow.slideClearOpen = false
        }

        x: Math.round(Math.min(
            Math.max(8, capsule.x + capsule.width / 2 - width / 2),
            boardWindow.width - width - 8))
        y: Math.round(Math.max(8, capsule.y - 12 - height))
    }

    // ================================================ 左下全屏切换圆钮
    // 与胶囊同一块放映条底板（2026-11-01）：FlyoutSurface 包一颗 44px 圆钮，
    // 内边距 9 → 直径 62 = 胶囊高，正圆。外层 Item 同样只框可见底板（理由见胶囊）。
    Item {
        id: fullScreenButton
        objectName: "blackboardFullScreenButton"

        anchors.left: parent.left
        anchors.leftMargin: 20
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 20
        width: fullScreenSurface.implicitWidth - fullScreenSurface.margin * 2
        height: fullScreenSurface.implicitHeight - fullScreenSurface.margin * 2

        // 吸收 hover 防止底层 InkLayer 收到浮层区移动（2026-10-10 自建批注）；
        // 箭头光标同胶囊
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            cursorShape: Qt.ArrowCursor
        }

        FlyoutSurface {
            id: fullScreenSurface
            x: -fullScreenSurface.margin
            y: -fullScreenSurface.margin
            surfaceColor: boardWindow.capsuleSurfaceColor
            borderColor: boardWindow.capsuleBorderColor

            // 悬停 600ms 才弹提示（U4）：IconButton 自带 ToolTip 的 delay 600，
            // 声明式 visible 下实测生效（见头注释 2026-11-01 条目）
            BoardToolButton {
                iconName: boardWindow.fullScreenOn
                          ? "ic_fluent_full_screen_minimize_20_regular"
                          : "ic_fluent_full_screen_maximize_20_regular"
                tooltip: boardWindow.fullScreenOn ? qsTr("退出全屏") : qsTr("全屏")
                onClicked: boardWindow.toggleFullScreen()
            }
        }
    }

    // ------------------------------------------------ 结果提示
    // 浮在胶囊正上方居中（深色板面上白字才看得清）；透明度绑 Timer.running，
    // 时间到自然淡出（SpotlightOverlay 同款）。t29 起不止报「已导出」：
    // 成功带目录（U3）、空板报「板已空」（U2）。目录可能比最小窗（≈493）
    // 还宽——钳宽 + 中段省略，盘符头与最深层级的目录尾两端都留得住。
    Rin.Text {
        id: exportHintText
        objectName: "blackboardResultHint"

        anchors.horizontalCenter: capsule.horizontalCenter
        anchors.bottom: capsule.top
        anchors.bottomMargin: 12
        font.pixelSize: 13
        color: Qt.rgba(1, 1, 1, 0.85)
        width: Math.min(implicitWidth, boardWindow.width - 40)
        elide: Text.ElideMiddle
        horizontalAlignment: Text.AlignHCenter

        opacity: exportHintTimer.running ? 1 : 0
        Behavior on opacity {
            NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
        }

        Timer {
            id: exportHintTimer
            interval: 2000
        }
    }
}
