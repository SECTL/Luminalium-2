# Luminalium 2

基于 **RinUI**（Qt Quick / QML 的 Fluent Design 组件库）构建的桌面快捷控制中枢。

启动后**常驻系统托盘**，点击托盘图标会在**光标附近**弹出「快捷面板」；当检测到
**PowerPoint 正在放映**时，会在屏幕**左下 / 右下**自动浮出**横版放映控制条**。
面板与托盘右键菜单都能打开**设置窗口**。

---

## 功能一览

| 模块 | 说明 |
| --- | --- |
| 托盘常驻 | 启动即为托盘态，不显示主窗口；左键切换面板，右键出菜单 |
| 快捷面板 | 品牌区 + 3 列快捷方式网格（可增删 / 拖拽排序）+ 横向课程表列表 + 底部工具条 |
| 放映控制条 | 笔/橡皮 Segmented、清屏、溢出「⋯」、翻页（上一页 / `n/N` / 下一页）、退出放映 |
| 设置窗口 | FluentWindow + 左侧导航；通用 / 外观 / 行为 / 放映控制 / 快捷面板 / 关于 / 更新 |
| 放映检测 | 无依赖的窗口类名探测 + COM 自动化读取页码，二者互为补充 |

---

## 快速开始

```bash
# 1. 创建虚拟环境（示例使用 Python 3.13）
python -m venv .venv

# 2. 安装依赖
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 运行
.venv\Scripts\python.exe main.py
```

启动后不会出现窗口 —— 请到**系统托盘**找到 Luminalium 图标并点击。

> 首次启动时 RinUI 会生成自己的主题配置 `RinUI/config/rin_ui.json`（已被 `.gitignore` 忽略）。

---

## 目录结构

```
Luminalium-2/
├── main.py                     启动脚本（固定工作目录于项目根）
├── requirements.txt
├── pyproject.toml
├── app/                        Python 侧（不写任何 UI 细节）
│   ├── application.py          应用装配：配置 → Qt → RinUI → 窗口 → 托盘
│   ├── bridge.py               QML 桥接层（QML 只依赖这里）
│   ├── config.py               配置读写（点号路径访问 / 深合并 / 增量落盘）
│   ├── paths.py                路径常量
│   ├── ppt_controller.py       PPT 控制器（独立模块）：放映探测 + 控制 + 状态广播
│   ├── tray.py                 托盘图标与菜单
│   └── windows.py              窗口创建 / 摆放 / 显隐
├── ui/                         QML 侧（不含任何业务判断）
│   ├── Luminalium/             设计令牌单例（颜色 / 尺寸 / 动效）
│   ├── QuickPanel.qml          快捷面板窗口（托盘浮窗）
│   ├── QuickPanel/             面板内的可复用组件
│   │   ├── TrayShortcuts.qml     快捷方式区（3 列网格 + 编辑态 + 空状态）
│   │   ├── ShortcutTile.qml      单个磁贴（圆角表面 + 图标 + 文字）
│   │   ├── ScheduleClip.qml      课程表卡片（横向列表里的一项）
│   │   ├── SectionHeader.qml     小节标题行（标题 + 编辑 / 添加）
│   │   ├── IconButton.qml        扁平图标按钮（带 ToolTip）
│   │   └── EmptyState.qml        空状态（RinUI 没有，手绘）
│   ├── Settings.qml            设置窗口（FluentWindow + 左侧导航）
│   ├── settings/               设置页（每页一个 FluentPage）
│   └── presentation/
│       ├── TopWindow.qml          顶层窗口（全屏置顶叠加层，整窗点击穿透）
│       ├── PresentationDock.qml   控制条本体（Item，恒横向 + 配置读取）
│       ├── FlyoutSurface.qml      悬浮底板（大圆角 + flyout 投影）
│       ├── ToolSegment.qml        分段容器（Rin.Segmented 的样式）
│       ├── ToolSegmentItem.qml    分段单页（选中底 + 强调色下划线）
│       ├── IconButton.qml         扁平图标按钮（动作 / 翻页 / 溢出）
│       ├── SectionDivider.qml     分组间的竖分隔线
│       └── ExitButton.qml         强调色实底按钮
├── assets/icons/               应用图标
├── config/default_config.json  默认配置（唯一真相来源）
├── tools/
│   ├── check_qml.py            ui/ 下全部 QML 的编译检查（不弹窗）
│   ├── preview.py              离屏渲染界面截图（不打扰桌面）
│   ├── smoke.py                端到端自检（无需真实 PowerPoint）
│   └── rinui_probe.py          探测当前 RinUI 版本里哪些组件真的可用
└── logs/                       运行日志（自动创建）
```

**分层约定**

- `app/bridge.py` 是 QML 唯一可见的 Python 对象（上下文属性名 `Backend`）。
  QML 里不出现任何 `win32` / `PowerPoint` 字眼，Python 里不出现任何颜色和尺寸。
- 所有可调项都进 `config/default_config.json`，新增动作 = 往 `presentation.actions`
  里加一条 + 在 `application._on_action` 里加一个分支。

---

## 放映控制条的设计语言

规则来自**对参考稿的像素实测**（参考稿条高 `H = 187px`），比例全部落到
`ui/Luminalium/Lumi.qml` 的令牌上：

| 元素 | 实测 | 结论 |
| --- | --- | --- |
| 底板圆角 | 25 / 187 | 0.134H → `dockSurfaceRadius: 8` |
| 横 / 纵内边距 | 50 / 33 | 0.267H / 0.176H → `dockPaddingX/Y: 14 / 10`（**两档不同**） |
| 内容高 | 121 / 187 | 0.647H → `dockHitSize: 36` |
| 图标（圆占位）直径 | 62 / 187 | 0.331H → `dockIconSize: 18` |
| 分段项宽 | — | 参考稿是宽项，实测显得空 → **改成正方形**（宽 = 内容高 36，缺省不写 `item_width`） |
| 下划线 宽 / 高 | 62 / 11 | = 图标宽 / 0.059H → `18 / 3` |
| 退出键 宽×高 | 129 × 121 | 0.69H × 0.647H → `dockExitWidthRatio: 1.07` |

设计语言四条：

| 元素 | 处理方式 |
| --- | --- |
| 底板 | 一整块、大圆角、无强描边、带 `Rin.Shadow` 的 flyout 投影 |
| 图标按钮 | **没有描边圆环** —— 参考稿里的圆是**图标占位**，真实界面就一枚图标。即 `Rin.Button { flat: true }` |
| 分段 | 容器（`#292929`）**比底板（`#2E2E2E`）更暗**并有极淡描边；选中项（`#373737`）**比底板更亮**，下划线宽度 = 图标宽度、紧贴容器底部 |
| 退出 | 略宽于高的强调色实底圆角块，图标是**黑色**（`Lumi.onAccent`），不是白色 |
| 分隔线 | 比底板暗，与分段容器同色；只在**组之间**出现（`工具 │ 动作 │ 退出`） |

颜色**一律取自 RinUI 主题**（`Rin.Theme.currentTheme`），不写死设计稿色值，
切浅色主题时会自动跟随。只有「比底板更亮 / 更暗」这种**相对关系**需要显式选
`controlFillColor`（白 6%）与 `controlAltSecondaryColor`（黑 10%），因为
RinUI 的默认取值方向与参考稿相反。

> 投影画在控制条 Item 的边界内（`surface.shadow.margin` 的余量）。
> Python 按**含余量的 Item** 尺寸贴角，因此配置里的 `margin_x` / `margin_y`
> 与 `shadow.margin` **相加**才是视觉上距屏幕边缘的距离（默认 8 + 24 = 32）。

---

## UI 组件来源（RinUI 优先）

界面**优先使用 RinUI 自带组件**，只有 RinUI 没有对应控件时才手绘：

| 界面元素 | 使用组件 |
| --- | --- |
| 窗口壳 | `Rin.Window`（快捷面板）· `Rin.FluentWindow`（设置） |
| 设置页 | `Rin.FluentPage` + `Rin.SettingCard` + `Rin.Switch` / `ComboBox` / `SpinBox` / `TextField` |
| 图标 | `Rin.Icon` |
| 笔 / 橡皮切换 | `Rin.Segmented` + `Rin.SegmentedItem`（覆写底板与 contentItem） |
| 面板图标按钮 | `Rin.Button { flat: true }`（等价于 CW2 的 `ToolButton { flat: true }`） |
| 面板磁贴 / 课程表卡片 | `Rin.Clip`（`Button` + 圆角 `Frame` 背景，悬停自带高亮） |
| 退出放映 | `Rin.Button { highlighted: true }`（覆写 contentItem） |
| 投影 | `Rin.Shadow`（`style: "flyout"` 的 `DropShadow`） |
| 分隔线 | `Rin.ToolSeparator` |
| 悬停提示 | `Rin.ToolTip` |
| 全部文字 | `Rin.Text` + `Rin.Typography.*` |
| 颜色 / 圆角 / 动效 | `Rin.Theme`，经 `ui/Luminalium/Lumi.qml` 转发 |

仍然手绘的只有：品牌 logo（渐变方块 + 图标）、`QuickPanel/EmptyState.qml`
（RinUI 0.4.4.1 没有 `EmptyState`）、设置页的强调色圆形色板
（用 `Rin.Clip` 把圆角拉满，没有对应组件）。

---

## RinUI 0.4.4.1 的坑（`tools/rinui_probe.py` 实测 + 源码核对）

**组件可用性**

- `ScrollViewer` / `ScrollView`：`qmldir` 里登记了，但指向的文件不存在 → 滚动区只能用原生 `Flickable` / `GridView` / `ListView`。
- `EmptyState`：**没有**这个组件（Class Widgets 2 用的新版本才有）→ 见 `ui/QuickPanel/EmptyState.qml`。
- `ToolButton`：能用，但源码里 `flat: true` 那行是**注释掉的** → 默认会画出一块带描边的实心按钮。
  想要 CW2 那种弱按钮，要么显式 `flat: true`，要么直接用 `Rin.Button { flat: true }`。
  它的 `contentItem` 有 `size` / `color` 别名，可以控字形大小与颜色。
- `Hyperlink`：能用，但基类的 `onClicked` 被写死成 `Qt.openUrlExternally(openUrl)` →
  只想当普通弱链接用就得覆写 `onClicked`；更省事的做法是 `Rin.Button { flat: true; highlighted: true }`。
- `Expander`：没有 `title` 属性。
- `Dialog`：`anchors.centerIn: QQC2.Overlay.overlay`，而 `Overlay` **只有 `ApplicationWindow` 有** →
  在普通 `Window`（托盘浮窗）里用会拿到 `null`。面板里的「添加」改用面板内覆盖层。
- `ScrollBar.vertical` / `.horizontal` 是 QtQuick.Controls 的**附着属性** →
  本项目的 QML 约定不导入 `QtQuick.Controls`（会与 RinUI 的同名 `Window` / `ScrollBar` 打架），
  所以滚动区一律不挂可见滚动条，靠滚轮 / 拖拽。
  `Rin.FluentPage` 自己挂了，会打印一条 `ScrollBar attached property must be attached to an object
  deriving from Flickable or ScrollView` —— RinUI 内部问题（它把 ScrollBar 的 `parent` 改成了 Page），**无害可忽略**。

**覆写样式时的连带契约**（违反会 `ReferenceError` 或构造期报错）

- 覆写 `Rin.Button` / `Rin.RoundButton` / `Rin.SegmentedItem` 的 `contentItem`，
  **必须一并覆写 `implicitWidth` / `implicitHeight`** —— 基类这两个绑定引用了
  默认 contentItem 里的 `row` / `text`。
- 覆写 `Rin.Button` 的 `contentItem` 还要提供 **`id: text`** ——
  基类的 `font: text.font` 与 `disabled` state 里的 `PropertyChanges { target: text }`
  都指向那个 id。`ExitButton.qml` 里留了一个不可见的 `Text { id: text }` 作兼容垫片。
- **不要覆写 `Rin.SegmentedItem` 的 `background`** —— 基类 background 的
  `width: checked ? parent.width : ...` 引用了 `parent`，旧对象被替换后 `parent`
  变为 null，构造期抛 `TypeError: Cannot read property 'width' of null`。
  改为在 `contentItem` 最底层铺一层自己的圆角底（`Control` 先画 background
  再画 contentItem，能完整盖住）。
- 覆写 `Rin.Button` / `Rin.RoundButton` 的 `background` 是安全的
  （只用 anchors，不读 `parent.width`）。
- `Rin.Clip` = `Button` + 圆角 `Frame` 背景，覆写了 `background` / `contentItem`，
  所以**它也必须显式给宽高**；另外它**已经自带 `clicked()`**，
  派生组件里再写 `signal clicked()` 会报 `Duplicate signal name: invalid override`。
- `Clip` 是 `Button`，**按下事件会被它吃掉** —— 想在磁贴上叠拖拽 `MouseArea`，
  手柄必须声明在磁贴**之后**（同级兄弟、z 更高）。

**取色与图标**

- `IconWidget` 只是 `Icon.qml` 的**别名**（同一个文件），不是另一个组件。
- `Rin.Icon` 的 `color` 直接 alias 到内部 `Text`，而 Text 默认色是**黑** ——
  凡是不显式给色的地方（如 `SegmentedItem` 的图标），深色主题下都不可见。
- `Rin.Button` 默认 contentItem 里的 `IconWidget` 只设了 `width` / `height`，
  **没设 `size`**，而 `Rin.Icon` 的字形大小由 `size`（默认 16）驱动 ——
  所以 `icon.width` 调多大字形都不变。要控字形必须换掉 `contentItem`。
- 两个 `primaryColor` 不是一个东西：
  `Utils.primaryColor` 是 `set_theme_color()` 塞进去的**原始强调色**（本项目 = `app.accent`）；
  `Theme.currentTheme.colors.primaryColor` 是它经 `lighter(1.6).darker(1.2)` 的**变体**，
  被 `Switch` / `textAccentColor` 等复用 —— 和设计稿的 `#4CC2FF` 不完全一致。
  需要精确对齐设计稿的地方（控制条下划线、退出键、设置里的开关）显式用 `Lumi.accent`。

**文件与窗口**

- `QQmlEngine` 会给每个 QML 源文件挂**文件监视器**：源文件一消失，引擎会判定文档失效并
  **回收由它创建的全部对象**（表现为 `Internal C++ object (QQuickWindow) already deleted`）。
  `tools/preview.py` 的临时宿主 QML 因此写在 `preview/` 里且**不删**；
  另外 PySide6 里 `QQmlComponent` 本身也要被持有，否则实例会被一并销毁。
- `QQmlEngine` 的 `importPathList` 只有 `RinUIWindow.load()` 被调用时才会补上 RinUI 模块目录 →
  不加载任何窗口的纯检查脚本（`tools/check_qml.py`）要自己 `addImportPath(RINUI_PATH)`。
- `Rin.Window` **总会**在顶部预留 `titleBar.height` 的条带（`TitleBar` 的
  `titleEnabled: false` 只隐藏里面的文字，不压缩高度）→ 做无标题栏浮窗要设
  `titleBarHeight: 0`，否则顶部会吊着一条空白拖拽区。
- `FluentWindow` 默认就 `titleEnabled: false`；再把它设成 `true` 会让窗口标题出现两次
  （标题栏一次 + 左侧导航栏一次），保持 `false` 即可。
- `NavigationView` 在窗口宽度低于 `navMinimumExpandWidth`（默认 **900**）时会把导航栏
  **自动收成图标条**。设置窗口通常不到 900 逻辑像素宽，必须显式调低阈值，
  否则用户看到的是「只有图标」的导航。
- `navigationItems[].page` 必须是**绝对 URL**：`NavigationView` 内部用
  `Qt.createComponent(page)` 加载，相对路径会以 RinUI 模块自身为基准而找不到文件。
  统一写 `Qt.resolvedUrl("settings/Xxx.qml")`。
- `FluentWindow` 把 `navigationView` 暴露成了 alias，所以
  `navigationView.navMinimumExpandWidth: 640` 这种「限定属性赋值」是**可用**的；
  但 `FluentWindow` 没有 alias `navExpandWidth` 之外的更多属性，先试再信。

**QML 通用**

- `Row` / `Column` / `Grid` 是**定位器**，子项不得使用 `anchors`
  （会打断布局并刷告警）。需要居中的子项包一层显式宽高的 `Item`，锚在 `Item` 上。

---

## 配置说明（`config/default_config.json`）

用户改动会写入 `config/config.json`（仅记录与默认值不同的键）。

### 放映控制条

```jsonc
"presentation": {
  "enabled": true,
  "poll_interval_ms": 400,     // 放映状态轮询间隔
  "margin_x": 8,               // 窗口距屏幕左/右边缘（真实视觉留白还要加 shadow.margin）
  "margin_y": 8,               // 窗口距屏幕下边缘
  "screen_index": -1,          // -1 = 跟随放映窗口所在显示器
  "bar_height": 56,            // 底板高度（参考稿 187px 的约 0.3 倍落地）
  "surface": {
    "radius": 8,               // 实测 25/187
    "opacity": 0.97,
    "padding_x": 14,           // 实测 50/187 = 0.267H（横竖两档不同）
    "padding_y": 10,           // 实测 33/187 = 0.176H
    "shadow": { "enabled": true, "margin": 24, "blur": 18, "offset_y": 6 }
  },
  "segment": {                 // 笔/橡皮分段控件
    "item_width": 36,          // 缺省 = 内容高（正方形，项里只有一枚图标）；要宽项才填
    "indicator_width": 18,     // 实测下划线宽 = 图标直径 62/187
    "indicator_height": 3      // 实测 11/187
  },
  "buttons": {
    "icon_size": 18,           // 实测圆（= 图标占位）直径 62/187
    "hit_size": 36,            // = 内容高 121/187
    "spacing": 10
  },
  "divider":  { "enabled": true, "width": 1, "height": 20, "gap": 14 },
  "overflow": { "enabled": true, "icon": "...", "tooltip": "更多操作" },
  "tools":    [ { "id": "pen",    "label": "笔",   "icon": "..." },
                { "id": "eraser", "label": "橡皮", "icon": "..." } ],
  "actions":  [ { "id": "clear_screen", "label": "清屏", "icon": "...", "tooltip": "..." } ],
  "pager":    { "enabled": true, "width": 48, "spacing": 14, "surface_padding_x": 26,
                "icon_prev": "...", "icon_next": "..." },
  "exit":     { "enabled": true, "label": "退出放映", "icon": "..." },
  "corners": {
    "bottom_center": { "enabled": true, "groups": ["tools", "actions", "exit"] },
    "bottom_left":   { "enabled": true, "groups": ["pager"] },
    "bottom_right":  { "enabled": true, "groups": ["pager"] }
  }
}
```

- `tools[].label` 是分段项的悬停提示（分段只有图标）；`actions[].label` 同时用于
  溢出菜单。`divider` 只在**组之间**画（`工具 │ 动作 │ 退出`）。
- `corners.<名称>.groups` 决定该角落显示哪些分组，可选值 `tools` / `actions` /
  `pager` / `exit`。控制条**恒横向**。**工具栏与翻页栏是两套独立的条**：
  `bottom_center` 是工具栏（tools/actions/exit，摆在下中部），`bottom_left` 与
  `bottom_right` 各是一只翻页 pill —— 同一套组件渲染三份，只是 `groups` 不同。
- `exit.accent` 缺省跟随 `app.accent`；只有想给退出键固定一个独立颜色时才填。
- 支持的位置：`bottom_left`、`bottom_center`、`bottom_right`、`top_left`、
  `top_center`、`top_right`。
- 图标名取自 RinUI 内置的 **Fluent System Icons**（如 `ic_fluent_pen_20_regular`），
  可在 `RinUI/assets/fonts/FluentSystemIcons-Index.js` 中查询可用名称。
  索引里只有 `_20_` 系列，但字体可缩放，`size` 任意值都行。

### 快捷面板

```jsonc
"quick_panel": {
  "width": 375, "height": 480,
  "offset_y": 30,                  // 面板顶边 = 光标 y + 30；下方放不下就翻到光标上方
  "hide_on_deactivate": true,      // 失焦自动收起
  "shortcuts": ["settings", "schedule_editor", "..."],   // 已启用的 id，顺序即显示顺序
  "shortcut_catalog": [ { "id": "settings", "title": "设置", "icon": "...", "action": "..." } ],
  "shortcuts_locked": false,       // true 时面板隐藏「编辑」按钮
  "sections": { "shortcuts": true, "schedules": true, "footer": true },
  "header": { "summary_text": "更新摘要", "summary_icon": "..." },
  "footer": { "actions": [ { "id": "settings", "icon": "...", "tooltip": "设置" } ] },
  "schedules": [ { "id": "local_default", "title": "New Schedule 1", "source": "本地", "active": true } ]
}
```

版式与交互对齐 **Class Widgets 2** 的托盘面板（`Windows/TrayPanel.qml` +
`Components/TrayShortcuts.qml`）：

| 部分 | 做法 |
| --- | --- |
| 浮窗 | 固定尺寸、无标题栏、`Qt.Tool \| Qt.FramelessWindowHint \| Qt.WindowStaysOnTopHint` |
| 位置 | 按**光标**摆：`x = 光标x - w/2`、`y = 光标y + offset_y`；下方放不下翻到上方；再夹取进屏幕可用区 |
| 头部 | logo + 应用名 + 弹簧 + 「更新摘要」弱按钮 |
| 快捷方式 | 3 列 `GridView`（`cellHeight: 84`，磁贴比单元格小 6）＋ 编辑态（拖拽换位 / 移除）＋ 空状态 |
| 课程表 | 定宽卡片（200）的**横向** `ListView`，选中项自动居中 |
| 底栏 | 右侧一排扁平图标按钮 + `ToolTip` |

> **不要**用 `QSystemTrayIcon.geometry()` 定位：Windows 上 Qt 返回空矩形
> （只有 macOS 有实现），拿它当锚点会退化成「屏幕正中」。

### 设置

```jsonc
"settings": {
  "width_ratio": 0.5, "height_ratio": 0.6,
  "minimum_width": 680, "minimum_height": 480,
  "default_page": "settings/Home.qml"
}
```

设置窗口是 `Rin.FluentWindow` + `navigationItems`（左侧导航），页面是
`Rin.FluentPage`，一行设置就是一个 `Rin.SettingCard`（右侧放 `Switch` /
`ComboBox` / `SpinBox` / `TextField`）。

**加一个可改项只需要两步**：在 `app/bridge.py::SETTING_PATHS` 里加一行
`扁平键 -> 配置点号路径`，然后在页面上写
`checked: Backend.settings.<扁平键>` ＋ `onToggled: Backend.setSetting("<扁平键>", checked)`。
`setSetting` 会按默认值的类型做一次兜底转换并落盘。

---

## 放映控制的实现说明

**检测**（`app/ppt_controller.py`，独立模块，双通道互为补充）

判定顺序（照 [Luminalium 1](https://github.com/SECTL/Luminalium) 的
`ppt_monitor` 对齐过）：**前台窗口优先**，再枚举全部顶层窗口逐个判定。

1. **窗口类名**命中 `presentation.window_classes`（不区分大小写，另含
   `slideshow` 子串通配）。默认表里除了 PowerPoint 的 `screenClass`，**还有 WPS
   演示自己的三个类名**（`wppSlideShowWindowClass` / `WPP SlideShow Window` /
   `WPP SlideShow Window 8.0`）——只认 `screenClass` 会把 WPS 整个漏掉。
2. **进程名 + 标题像放映**：进程名命中 `presentation.process_names`，且标题里
   含「放映 / slide show / スライドショー …」等字样（多语言）。
3. **进程名 + 铺满整屏 + 不是编辑器主窗口**：标题没提示时的兜底，要求覆盖所在
   显示器 ≥ `presentation.fullscreen_ratio`（默认 0.7）、类名不是
   `PP**FrameClass`、且**没有标题栏**——否则最大化的 PowerPoint / WPS 编辑器
   会被误判成放映，控制条在不该出现时弹出来。
4. COM 兜底：`GetActiveObject` 依次尝试 `PowerPoint.Application`（MS Office）
   与 `Kwpp.Application` / `wpp.Application`（WPS 演示，对象模型同构），
   `SlideShowWindows.Count > 0` 即算放映中。

> ⚠️ **COM 受 UAC 完整性级别隔离**：本程序与演示软件权限级别不一致时
> （一个以管理员运行、另一个不是），ROT 里看不到对方的 COM 对象，
> `GetActiveObject` 直接 `0x800401E3`。实测本进程 High + PowerPoint Medium 时
> ROT 条目数为 0。表现是翻页 / 笔 / 页码 / 退出放映全部只剩键盘回退。
> **请以与演示软件相同的权限级别运行 Luminalium**；诊断里会直接提示这一条。

> ⚠️ 取窗口类名**不能**用「先传 NULL 查长度」的写法 —— Win32 的
> `GetClassNameW` 不支持，`nMaxCount=0` 时直接返回 0，类名永远是空串，
> 整条窗口类探测会静默失效（症状：PowerPoint 明明在放映，日志却说没检测到）。
> 必须直接给 256 字符的缓冲区。`tools/smoke.py` 里有这条的回归断言。

每次状态变化（放映开始 / 结束 / 翻页）都以 INFO 级写入日志（`luminalium.ppt`），
「顶层窗口没出来」先查日志里有没有 `放映开始` 一行。**诊断**（托盘右键
「诊断信息」）会把当前所有「像放映窗口」的顶层窗口连同类名 / 标题 / 进程名 /
矩形列出来：若真正的放映窗口在列表里却没被认出来，把它的 `class` 或 `proc`
填进 `presentation.window_classes` / `presentation.process_names` 即可。

探测万一还是认不出来，托盘右键「显示/隐藏放映控制条（手动）」可强制叫出控制条，
用来区分「探测没认出来」与「窗口画不出来」。

**操作**

| 动作 | COM | 降级方案 |
| --- | --- | --- |
| 下一页 / 上一页 | `View.Next()` / `View.Previous()` | `PageDown` / `PageUp` |
| 退出放映 | `View.Exit()` | `Esc` |
| 笔 / 橡皮 | `View.PointerType = 2 / 3` | `Ctrl+P` / `Ctrl+E` |
| 清屏 | `View.EraseDrawing()` | `E` |

未安装 `pywin32` 或演示软件未运行时，检测与操作会**自动降级**，应用其余功能不受影响。

**焦点与穿透（「顶层窗口」）**

所有控制条都托管在一个**全屏置顶的顶层窗口**（`TopWindow.qml`，标题即「顶层窗口」）里。
穿透的实现分两层：

* **首选：区域塑形（`SetWindowRgn`）** —— 显示后把窗口裁成「只有控制条那几块」
  （`app/windows.py::_update_overlay_region`）。区域外**既不绘制也不参与命中测试**，
  由系统保证鼠标 / 触摸穿透，无轮询、无状态机，也不可能出现「整块屏幕吃掉点击」。
  `SetWindowRgn` 的坐标单位（逻辑 / 物理）跟 DPI 模式有关，代码**先设再读回**
  （`GetWindowRgn` + `GetRgnBox`）自行校准，不猜。
* **兜底：整窗穿透轮询** —— 塑形不可用时才启用：常驻 `WS_EX_TRANSPARENT`，
  25ms 轮询光标，悬到控制条表面内才临时收回（`presentation.pass_through`
  可整体关闭穿透用于排查）。

两条铁律（都真机踩过，症状都是「窗口存在、`isVisible()=True`，但整窗不画」）：

1. **绝不动 Qt 自己加的 `WS_EX_LAYERED`**。Qt 为了给顶层透明窗口画逐像素
   alpha，自己会加这个位并走 `UpdateLayeredWindow`（实测 exstyle
   `0x08080088`）。在外面剥掉它 → `UpdateLayeredWindow` 全部失败 → 隐形；
2. **绝不调 `SetLayeredWindowAttributes`** —— 它与 `UpdateLayeredWindow`
   互斥，一样隐形。

其余保障：

* 点击工具 / 翻页按钮不激活窗口（`WS_EX_NOACTIVATE`），放映窗口焦点不被抢走；
* 放映窗口本身也是 TOPMOST 且会重申 z 序 → 顶层窗口显示时立即 + 每
  `topmost_interval_ms`（默认 800ms）`SetWindowPos(HWND_TOPMOST)` 压回去；
  每次压完还会用 `GetWindow` 走一遍顶层序列，确认我们确实**排在放映窗口之上**，
  连续 3 次压不过去才报 ERROR（区分「竞态」和「压根压不过去」）；
* 显示后 `verify_after_ms` 做一次自检（`_verify_overlay`）：对照窗口**真实**
  物理矩形与目标（不符就用原生 `SetWindowPos` 纠正）、检查 DWM 是否把窗口
  披风化（cloaked）、并写一行 `overlay_report()` 进日志；
* 探测与 COM 全部在独立线程（`ppt_controller._ProbeThread`），演示程序再忙
  也卡不住界面。

真机排查（顺序很重要，**先让放映真正开始**再取诊断）：

1. 在 PowerPoint / WPS 里按 `F5` 进入放映；
2. 托盘右键「诊断信息（写入日志）」，看 `logs/luminalium.log` 末尾：

   * `放映开始: hwnd=0x... 来源=window/process/com` —— 探测正常，往下看窗口状态；
   * 没有这一行 —— 探测没认出来，诊断会把当前**所有可疑顶层窗口**连同类名 /
     标题 / 进程名 / 矩形 / 有无标题栏列出来（按相关度排序）。找到真正的放映
     窗口，把它的 `class` 或 `proc` 填进 `presentation.window_classes` /
     `presentation.process_names` 即可，不用改代码。
   * `顶层窗口结论` 直接给一句人话结论。

> ⚠️ 诊断里 `rect=(1397, 683, 280, 280)` 这类小矩形**不是**定位错了：那是 Qt
> 给「还没 show 过的窗口」的默认尺寸（160×160 逻辑 × DPR）。它只说明这个进程
> 从来没进入过放映态。真正显示过之后再隐藏，矩形会保持整屏。

若怀疑探测，托盘右键「显示/隐藏放映控制条（手动）」可**不依赖任何探测**强制叫出
控制条，用来区分「探测没认出来」和「窗口画不出来」。放映中运行
`tools/diag_overlay.py` 则会额外在屏幕中央放一块红方块，判定该屏是否允许叠加。

唯一例外是溢出「⋯」：它必须弹菜单，而 QML 的 `Popup` 会另开一个真窗口并抢焦点，
因此改用**原生 `QMenu`**（`application._show_overflow_menu`）。原生菜单是临时的，
关闭后焦点立刻回到放映窗口；样式用 QSS 近似控制条（同底色 / 圆角 / 悬停色）。
不想要这个按钮就把 `presentation.overflow.enabled` 设为 `false`。

---

## 扩展指引

- **加一个放映动作**：在 `presentation.actions` 加一条 → 在
  `app/application.py::_on_action` 里加分支 → 在 `app/ppt_controller.py`
  里加对应方法。QML 无需改动，动作按钮与溢出菜单会自动多出一项。
- **加一个工具**：往 `presentation.tools` 加一条，分段控件由 `Repeater` 驱动，
  会自动多一页。
- **加一个角落**：往 `presentation.corners` 加一个键（名称需在
  `app/windows.py::CORNERS` 中已定义）。
- **加一个面板快捷方式**：往 `quick_panel.shortcut_catalog` 加一条（这样它会出现在
  面板的「+」列表里）→ 在 `app/application.py::_on_shortcut` 的 `handlers` / `labels`
  里注册。默认启用哪些、什么顺序，由 `quick_panel.shortcuts` 决定，也可以在面板里
  点「编辑」直接改。
- **加一个设置项**：在 `app/bridge.py::SETTING_PATHS` 加一行 `扁平键 -> 配置路径`，
  页面上写 `Backend.settings.<扁平键>` + `Backend.setSetting(...)`。
- **加一个设置页**：在 `ui/settings/` 下新建一个 `Rin.FluentPage`，然后往
  `ui/Settings.qml` 的 `navigationItems` 里加一项（`page` 用 `Qt.resolvedUrl(...)`）。

---

## 开发工具

| 脚本 | 用途 |
| --- | --- |
| `tools/check_qml.py` | 把 `ui/` 下**每个** QML 都编译一遍并汇总错误。不创建窗口，秒级，适合改完 QML 先跑这个。 |
| `tools/preview.py` | 离屏渲染出 `preview/*.png`：快捷面板 / 顶层窗口（含两条控制条）/ 设置窗口 / **每个设置页各一张**。窗口摆在 `x = -6000`，不打扰桌面。 |
| `tools/smoke.py` | 端到端自检：托盘 / 面板定位 / 顶层窗口与控制条贴角 / 可见性三要素（LAYERED / Win32 可见 / 未披风化）/ 区域塑形命中 / 设置窗口 / 快捷方式增删排序 / 设置项读写。无需真实 PowerPoint。 |
| `tools/live_probe.py` | **真机自检（推荐先跑这个）**：自己 `Dispatch` 一个独立 PowerPoint 实例、新建 2 页空白稿开始放映，放映中采样探测状态 / 页码 / 顶层窗口矩形 / 区域塑形 / **z 序是否压在放映窗口之上**，最后自动退出放映并关闭该实例。不用手动开 PPT 就能把整条链路验一遍（会全屏约 13 秒）。 |
| `tools/diag_overlay.py` | **真机诊断**：放映中运行，用真实链路显示顶层窗口 + 一块红测试方块，把窗口句柄 / 扩展样式 / DWM 披风 / 区域塑形 / z 序全部打到 stdout，用于把「看不见」二分定位。 |
| `tools/rinui_probe.py` | 逐个实例化候选 RinUI 组件，报告哪些真的可用。换 RinUI 版本后先跑它。 |

跑之前记得设 UTF-8，否则 RinUI 启动时打印的 ✨ 会让 Python 在 GBK 控制台上报
`UnicodeEncodeError`：

```powershell
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe tools\preview.py
```

---

## 已知限制

- 目前仅支持 Windows（PowerPoint 自动化与托盘定位依赖 Win32）。
- 「顶层窗口」的**屏幕上合成效果**离屏渲染测不到，需要真机确认；
  放映中运行 `tools/diag_overlay.py` 可一键判定（控制条 / 红方块 / 都看不见
  三种结果对应三类问题）。若两个都看不见，通常是演示软件走了独占呈现
  （可尝试关闭 PowerPoint「硬件图形加速」）。
- 快捷面板中的「课程编辑 / 插件广场 / 调休 / 换课 / 诊断 / 更新摘要」目前是占位
  （点击后在日志与状态栏提示），等待后续接入真实功能。
- 「清屏」在 COM 可用时调用 `EraseDrawing()`，否则模拟 `E` 键；
  若放映窗口未获得前台焦点，模拟按键可能失效。
- 设置页的滚动条不显示：`Rin.FluentPage` 把 `ScrollBar` 重挂到了 Page 上，
  附着属性因此失效（RinUI 内部问题，会打印一条告警）。滚轮仍可滚动。
- 托盘右键菜单（`QMenu`）与快捷面板是两套 UI：前者是原生菜单，样式跟随系统，
  不受主题影响。
- `ui/Luminalium/Lumi.qml` 的部分令牌是 QML 侧兜底值，运行时以
  `config/default_config.json` 为准（两者保持同值）。
