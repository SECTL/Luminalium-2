import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium
import "components"

/*!
    插件管理页：两张导入磁贴 + 筛选胶囊 + 插件行列表。

    2026-10-05（插件系统 Wave 3 任务 17）新增。数据源是 ``Backend.pluginItems``
    （``app/bridge.py`` 把 ``loader.loaded_plugins()`` 的清单 + 正式 Config
    里的 ``plugins.<id>.enabled`` 合成的列表），开关写回走
    ``Backend.setPluginEnabled``（常规配置路径，防抖落盘）。

    2026-10-06（用户指令「给插件系统添加外部导入插件功能」）加外部插件管理：
    导入走 ``Backend.importPluginZip`` / ``importPluginFolder``（模态原生对话框，
    Python 侧校验 + 拷贝，见 ``app/plugins/external.py``）；结果经
    ``pluginManageResult(ok, message)`` 信号回来显示在页首横幅里。外部插件行
    多一枚「删除」按钮（两段式确认，避免手滑整包删掉）—— 只删用户插件目录里
    的安装副本，原始文件不动。

    2026-10-17（用户指令「将插件界面的排版改成如图排版」）整页重排版：
    原先的「两张 SettingCard 导入卡片 + 一条平铺列表」换成设计稿的四段式 ——

      ① **小节标签**（``导入`` / ``插件``）—— ``Rin.Text { BodyStrong }``，
         不再靠标题栏分区；
      ② **两张并排的导入磁贴**（``ActionCard``，与主页外链卡共用）：
         整张磁贴即入口，右下角一枚「打开」字形提示可点；
      ③ **筛选胶囊**（``PluginFilterChip``）—— 选中 = 强调色实底 + 对比文字色，
         未选中 = 弱对比底色。**横向可滚动**：行是 ``Flickable``，
         内容溢出时右端才出现一枚 chevron。

    2026-10-17（用户指令「我是叫你把已启用作为筛选项，然后把 Segments 整个删掉」）
    把上一版的「范围分段（已安装的全部 / 已安装且已启用）+ 胶囊」两段式**整个
    去掉分段**：范围分段连同临时抽出的 ``components/SegmentedTab*`` 一并删除，
    「已启用」变成筛选胶囊里的一枚（排在「全部」之后），与来源、分类**互斥单选**。
    理由：分段与胶囊本来就是同一个语义（筛列表），做成两种控件只是让人多学一遍；
    多一行控件换来的信息量，还不如多一枚胶囊。

    2026-10-17（用户指令「按 SVG 复刻」）**尺寸全部重按 SVG 量过**：上一版把
    SVG 值乘了 0.844（1080 宽的 PNG / 1280 宽的 SVG），整页矮了一档；设计稿里
    的字给出了判决 —— 行标题 14、行副文案 12、胶囊文字 14，全落在 RinUI
    的字号梯上，说明 **SVG 单位 = 逻辑 px**。具体值与理由见
    ``ui/Luminalium/Lumi.qml`` 的「设置 · 插件页」一节。横向照旧交给布局。

    2026-10-17（用户指令「设计稿和成品必须高度一致」）按 SVG 补齐完整类别筛选，
    不再只放三只来源胶囊。分类值来自可选 ``META.category``；未声明的插件归
    ``other``，所以外部插件不会因缺字段消失。同理，设计稿副文案上的作者名当时
    没有数据源，``describe()`` 只能走本项目自己可验证的状态信息（版本 / 调试 /
    外部导入 / 加载结果），把**版本号提到最前**。

    2026-10-17（用户指令「给插件的信息增加图标和作者的接口并且在设置显示」）
    META 补上可选 ``icon`` / ``author``：行图标优先用插件自己的（字形名或相对
    插件目录的图片），副文案在版本号后紧跟作者。两个字段都可空 —— 缺省回落
    到「按插件类型给的字形」和「不显示」，老插件一行都不用改。接口与解析规则
    见 ``app/bridge.py::_plugin_icon`` 与 ``docs/plugin-development.md``。

    ⚠️ **导入 / 删除 / 启用 / 禁用都是重启后生效，本进程内不做任何动态
    增删** —— 这不是偷懒，是两个架构前提决定的：
      ① 注册表在加载期末 ``registry.freeze()`` 冻结，之后任何 ``add_*``
         直接抛 RuntimeError，根本没有 unregister 这条路；
      ② 窗口全是懒创建、只藏不销毁 —— 插件注册的窗口一旦建出来就没有
         「销毁」这一说，实时禁用也没法把它从世界里抹掉。
    唯一语义就是「动配置 / 动安装目录 → 下次启动时 loader 按新状态装」。
    界面上对应的提示是操作后出现的内联横幅（``restartHintShown``），
    不做弹窗系统（仓库没有这个先例）。

    ⚠️ 调试插件（``_demo`` / ``_demo_dep`` 这类 ``_`` 前缀目录）**显示在
    列表里、带「调试插件」标记**，不过滤 —— 决策理由：调试插件的开关正是
    验收「禁用 → 重启 → 零贡献」链路（任务 11 的过滤机制）的唯一 UI 触点，
    过滤掉之后这条链路在界面上就没法验证了；正式环境（非 debug 启动）
    它们根本不进加载清单，普通用户看不到。

    ⚠️ 删除是**两段式确认**（先点变「确认删除」、3 秒内再点才真删）：
    删的是安装副本，导入一次不容易，手滑一次就没了不像话。确认态由
    ``armTimer`` 复位。

    页面结构（自上而下）：
      ① 导入 / 删除结果横幅（操作后短暂可见）；
      ② 「重启后生效」内联横幅（拨过开关 / 导入删除成功后出现）；
      ③ 「导入」小节标签 + 两张导入磁贴；
      ④ 「插件」小节标签 + 筛选胶囊行；
      ⑤ 空态占位（无插件，或筛选后一条都不剩 —— 两种文案分开）；
      ⑥ 插件行（Repeater 遍历 ``Backend.pluginItems``）：图标 = 插件声明的图标 /
         类型字形，标题 = 插件名，副文案 = 版本号 + 作者 + 调试 / 外部标记 +
         加载结果，右侧外部插件删除按钮 +「启用」标签 + 启用开关。

    ⚠️ **筛选没有走「先过滤再喂 Repeater」**（那要另建一个 JS 数组属性，
    还得自己维护变更通知）：代理照旧遍历全量，各自 ``visible: page.matches()``，
    空态用 ``shownCount`` 这只现算的只读属性。插件数量是个位数，多建的隐藏
    代理不值一提，换来的是「删掉一条就地隐藏」那套既有逻辑一行都不用动。
*/
Rin.FluentPage {
    id: page

    title: qsTr("插件")
    contentSpacing: 10

    /*! 拨过任意开关 / 导入删除成功后置 true，「重启后生效」横幅据此显示。 */
    property bool restartHintShown: false
    /*! 导入 / 删除结果横幅的文案；空串隐藏（结果只在操作后看一眼）。 */
    property string resultText: ""
    /*! 本次结果是成功（true）还是失败（false），横幅配色与图标跟着换。 */
    property bool resultOk: false
    /*! 本会话里已删除的插件 id —— 加载清单是启动快照，删掉的要就地改观。 */
    property var removedIds: ({})

    /*! 筛选胶囊的**唯一状态位**（2026-10-17 起范围分段整个删了，「已启用」是
        其中一枚胶囊 —— 状态与来源、分类同一排、互斥）。 */
    property string kindFilter: "all"
    /*! 分类词表：只负责 **id → 可翻译标签**，以及**显示顺序**。它不决定「有哪几个
        分类」—— 那由插件自己说了算（见 ``kindFilters``）。表里没写到的 id 原样
        显示，插件自定义的分类不该被 UI 吃掉。 */
    readonly property var categoryLabels: ({
        "utility": qsTr("实用工具"),
        "subject": qsTr("学科工具"),
        "office": qsTr("办公工具"),
        "entertainment": qsTr("娱乐工具"),
        "improve": qsTr("改进"),
        "optimize": qsTr("优化"),
        "injection": qsTr("注入式修改类"),
        "integration": qsTr("联动类"),
        "shortcut": qsTr("快捷方式类"),
        "other": qsTr("其他"),
        "quicktool": qsTr("快捷工具")
    })

    /*! 筛选胶囊的模型 = 全部 / 已启用 / 内置 / 非内置 + **插件实际声明过的分类**。
        ``id`` 是不随翻译变化的 ``META.category`` 值（``app/bridge.py`` 的
        ``pluginItems`` 逐项透出，缺省归 ``other``），来源筛选也走同一模型，
        免得 UI 与过滤逻辑各维护一份顺序。

        「已启用」排第三位而不是塞在末尾：它是**使用频率最高**的那一枚
        （用户多半只想看正在跑的东西），而分类是自己的私事。

        ⚠️ **这里刻意不读 ``kindFilter``**：绑上它就会「点一下 → 重建 Repeater →
        把这个 delegate 自己从事件处理中拆掉」。选中的分类若因插件变动消失，
        由 ``Backend.pluginItemsChanged`` 那条兜底把筛选退回「全部」。 */
    readonly property var kindFilters: {
        var out = [
            { id: "all", label: qsTr("全部") },
            { id: "enabled", label: qsTr("已启用") },
            { id: "builtIn", label: qsTr("内置") },
            { id: "external", label: qsTr("非内置") }
        ]
        var seen = {}
        var items = Backend.pluginItems
        for (var i = 0; i < items.length; ++i) {
            var c = items[i].category
            if (c) {
                seen[c] = true
            }
        }
        var known = Object.keys(page.categoryLabels)
        for (var k = 0; k < known.length; ++k) {
            if (seen[known[k]] === true) {
                out.push({ id: known[k], label: page.categoryLabels[known[k]] })
                delete seen[known[k]]
            }
        }
        // 词表外的分类（插件自定义）：按发现顺序缀在后面。
        for (var m = 0; m < items.length; ++m) {
            var extra = items[m].category
            if (extra && seen[extra] === true) {
                out.push({ id: extra, label: extra })
                delete seen[extra]
            }
        }
        return out
    }

    /*! 插件清单变了（启用开关 / 删除 / 重载）就核对一次当前筛选：选中的分类
        如果已经不存在了，退回「全部」—— 否则会出现「一个胶囊都没高亮，列表却是
        空的」这种没有出路的状态。 */
    function pruneKindFilter() {
        if (kindFilter === "all" || kindFilter === "enabled"
                || kindFilter === "builtIn" || kindFilter === "external") {
            return
        }
        var list = kindFilters
        for (var i = 0; i < list.length; ++i) {
            if (list[i].id === kindFilter) {
                return
            }
        }
        kindFilter = "all"
    }

    /*! 一行插件是否该露脸：**一枚胶囊一个判据**（状态「已启用」/ 来源「内置、
        非内置」/ 分类），互斥，不再有「范围 × 类别」的两维叠加。
        ``debug`` 归「内置」—— 它是 ``_`` 前缀的调试夹具，本来就在安装目录里。

        ⚠️ 判据**当参数传进来**、不在这里偷读 ``kindFilter``：传参让「这条
        visible 依赖了谁」在调用点一眼可读，绑定依赖也抓得明明白白（依赖是在
        绑定求值期抓的，函数里偷读当然也抓得到，但下一眼看不出来）。 */
    function matches(item, kind) {
        if (!item) {
            return false
        }
        /*! 「已启用」是唯一的**状态**判据；其余全部按来源 / 分类判，两者不叠加
            （叠加就得让用户同时盯着两枚高亮的胶囊，而这一排本来就是单选）。 */
        if (kind === "enabled") {
            return item.enabled === true
        }
        if (kind === "builtIn" && item.external === true) {
            return false
        }
        if (kind === "external" && item.external !== true) {
            return false
        }
        if (kind !== "all" && kind !== "builtIn" && kind !== "external"
                && item.category !== kind) {
            return false
        }
        return true
    }

    /*! 过滤之后还剩几条（空态据此显示）。写成属性而不是函数：只读属性会被当
        绑定求值，``pluginItems`` / ``kindFilter`` 任一变化都会重算。 */
    readonly property int shownCount: {
        var kind = kindFilter
        var items = Backend.pluginItems
        var n = 0
        for (var i = 0; i < items.length; ++i) {
            if (matches(items[i], kind) && !isRemoved(items[i])) {
                n += 1
            }
        }
        return n
    }

    /*! 是否已被本会话删掉（加载清单是启动快照，删掉的就地隐藏）。 */
    function isRemoved(item) {
        return item.external === true && removedIds[item.id] === true
    }

    /*! 行副文案：版本号提到最前，紧跟作者（设计稿就是「v1.0.0 · 作者」这种
        形状），后面接本项目真正有的状态信息，「·」分隔。
        2026-10-17：「作者」来自 ``META.author``（原来这一格没有数据源，见文件头
        「设计稿和成品必须高度一致」那段）；没声明就整段跳过，不留空档。 */
    function describe(item) {
        var parts = []
        if (item.version) {
            parts.push("v" + item.version)
        }
        if (item.author) {
            parts.push(item.author)
        }
        if (item.debug) {
            parts.push(qsTr("调试插件"))
        }
        if (item.external) {
            parts.push(qsTr("外部导入"))
        }
        if (item.loaded) {
            parts.push(qsTr("已加载"))
        } else if (item.reason) {
            parts.push(qsTr("未加载：%1").arg(item.reason))
        } else {
            parts.push(qsTr("未加载"))
        }
        /*! 「已禁用」只在**没有跳过原因**时补一句：``reason`` 里的
            「已禁用（plugins.x.enabled=false）」是启动快照的说法，两者同时出现
            会变成「未加载：已禁用（…） · 已禁用」。而 ``enabled`` 是**现读配置**的
            （见 ``app/bridge.py::_get_plugin_items``）—— 刚拨完开关、还没重启时
            快照里仍是 loaded / reason=null，这时这一句才是唯一看得出「你已经关了它」
            的地方，不能删。 */
        if (!item.enabled && !item.reason) {
            parts.push(qsTr("已禁用"))
        }
        return parts.join(" · ")
    }

    Connections {
        target: Backend
        function onPluginManageResult(ok, message) {
            page.resultOk = ok
            page.resultText = message
            if (ok) {
                page.restartHintShown = true
            }
        }
        /*! 分类胶囊是从 ``pluginItems`` 推出来的，清单一变就要核对选中的分类还在
            不在（启用开关 / 删除都会走这条路）。 */
        function onPluginItemsChanged() {
            page.pruneKindFilter()
        }
    }

    // ==================================================== 导入 / 删除结果横幅
    Rin.SettingCard {
        objectName: "pluginsResultBanner"

        Layout.fillWidth: true
        visible: page.resultText !== ""
        title: page.resultOk ? qsTr("操作成功") : qsTr("操作失败")
        description: page.resultText
        icon.name: page.resultOk
                  ? "ic_fluent_checkmark_circle_20_regular"
                  : "ic_fluent_error_circle_20_regular"
    }

    // ==================================================== 重启生效提示（内联）
    Rin.SettingCard {
        objectName: "pluginsRestartHint"

        Layout.fillWidth: true
        visible: page.restartHintShown
        title: qsTr("更改将在重启应用后生效")
        description: qsTr("插件的启用状态与导入 / 删除只在启动时读取，本进程内不会动态加载或卸载")
        icon.name: "ic_fluent_arrow_sync_circle_20_regular"
    }

    // ==================================================== ① 「导入」小节
    /*! 小节标签 = **RinUI 通用写法**：``Rin.Text { BodyStrong }``，与「通用」
        「主界面」「墨迹」「关于」等页的分组小标题同一层级（2026-10-17 用户指令
        「应该用 RinUI 的通用的」）。不再自定 ``font.pixelSize: 16`` —— 那是我
        照设计稿量出来的非标尺寸，字号梯上没有，且与别的设置页不一致。
        ``BodyStrong`` 行高 20，与原先 16 号字一样，整页纵向节奏不变。 */
    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("导入")
    }

    /*! 两条入口并排（而不是一个按钮里做格式判断）：原生对话框「选文件夹」与
        「选压缩包」是两种交互，硬捏在一个入口里只能二选一。

        2026-10-17：卡本体就是主页那两张外链卡（``components/ActionCard``），
        这里只覆写尺寸与版式参数 —— 高 116（设计稿原值）、主图标 24、标题 16、
        图标靠左、角标 16@15。间距 6 = 设计稿「标签 → 磁贴」16 - ``contentSpacing`` 10。 */
    RowLayout {
        objectName: "pluginsImportRow"

        Layout.fillWidth: true
        Layout.topMargin: Lumi.pluginLabelGap - page.contentSpacing
        spacing: Lumi.pluginTileGap

        ActionCard {
            objectName: "pluginsImportFolder"

            Layout.fillWidth: true
            Layout.preferredHeight: Lumi.pluginTileHeight

            label: qsTr("导入文件夹")
            iconName: "ic_fluent_folder_20_regular"
            tooltip: qsTr("选择包含 plugin.py 的插件文件夹；导入即拷贝安装")

            iconSize: Lumi.pluginTileIconSize
            glyphSize: Lumi.pluginTileGlyphSize
            contentPadding: Lumi.pluginTilePadding
            contentPaddingBottom: Lumi.pluginTilePaddingBottom
            contentSpacing: Lumi.pluginTileSpacing
            glyphMargin: Lumi.pluginTileGlyphMargin
            centerIcon: false
            titlePixelSize: Lumi.pluginTileTitleSize

            onClicked: Backend.importPluginFolder()
        }

        ActionCard {
            objectName: "pluginsImportZip"

            Layout.fillWidth: true
            Layout.preferredHeight: Lumi.pluginTileHeight

            label: qsTr("导入压缩包（.zip）")
            iconName: "ic_fluent_folder_zip_20_regular"
            tooltip: qsTr("选择 .zip 插件包；导入即拷贝安装")

            iconSize: Lumi.pluginTileIconSize
            glyphSize: Lumi.pluginTileGlyphSize
            contentPadding: Lumi.pluginTilePadding
            contentPaddingBottom: Lumi.pluginTilePaddingBottom
            contentSpacing: Lumi.pluginTileSpacing
            glyphMargin: Lumi.pluginTileGlyphMargin
            centerIcon: false
            titlePixelSize: Lumi.pluginTileTitleSize

            onClicked: Backend.importPluginZip()
        }
    }

    // ==================================================== ② 「插件」小节
    /*! 与小节①同一枚通用标签（``BodyStrong``）。间距 18 = 设计稿「磁贴底 →
        小节标签」28 - ``contentSpacing`` 10。 */
    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: Lumi.pluginSectionGap - page.contentSpacing
        typography: Rin.Typography.BodyStrong
        text: qsTr("插件")
    }

    // ==================================================== ③ 筛选胶囊
    RowLayout {
        objectName: "pluginsFilterRow"

        Layout.fillWidth: true
        // 设计稿「小节标签 → 筛选行」12（页级 contentSpacing 只给 10）。
        Layout.topMargin: Lumi.pluginFilterGap - page.contentSpacing
        spacing: 12

        /*! 横向滚动容器：完整类别在窄窗会溢出，设计稿的右端 chevron 因此只在
            内容放不下时出现。
            2026-10-17：行首那枚「筛选」字样按用户指令删掉 —— 胶囊本身已经把
            「这是筛选」说清楚了，删掉后胶囊列左缘对齐到内容起点。 */
        Flickable {
            id: chipScroll
            objectName: "pluginsFilterScroll"

            Layout.fillWidth: true
            Layout.preferredHeight: Lumi.pluginChipHeight
            contentWidth: chipRow.width
            contentHeight: height
            clip: true
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentWidth > width

            Row {
                id: chipRow
                width: implicitWidth
                height: chipScroll.height
                spacing: Lumi.pluginChipGap

                Repeater {
                    model: page.kindFilters

                    delegate: PluginFilterChip {
                        required property var modelData
                        required property int index

                        label: modelData.label
                        /*! 不用 ``checked``：基类按钮被点后会把绑定摘掉。这里的
                            选中态只读页面唯一状态位，指哪亮哪。 */
                        selected: page.kindFilter === modelData.id
                        onClicked: page.kindFilter = modelData.id
                    }
                }
            }
        }

        /*! 溢出指示（内容放不下才出现；胶囊行是 ``Layout`` 子项，``visible: false``
            的项不占位，所以不溢出时右端不会有空档）。 */
        Rin.Icon {
            Layout.alignment: Qt.AlignVCenter
            visible: chipScroll.contentWidth > chipScroll.width
            icon: "ic_fluent_chevron_right_20_regular"
            size: 16
            color: Lumi.textSecondary
        }
    }

    // ==================================================== ④ 空态占位
    /*! 加载清单为空（未跑加载 / 无插件）与「筛完一条不剩」是两件事，文案分开 ——
        后者要说清楚是筛掉的，不然看着像插件没了。 */
    Item {
        objectName: "pluginsEmptyState"

        Layout.fillWidth: true
        Layout.preferredHeight: emptyState.implicitHeight + 48
        visible: page.shownCount === 0

        ColumnLayout {
            id: emptyState
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            Rin.Icon {
                Layout.alignment: Qt.AlignHCenter
                icon: "ic_fluent_puzzle_piece_20_regular"
                size: 40
                color: Lumi.textSecondary
            }
            Rin.Text {
                Layout.alignment: Qt.AlignHCenter
                text: Backend.pluginItems.length === 0
                      ? qsTr("没有已安装的插件")
                      : qsTr("没有符合当前筛选条件的插件")
                color: Lumi.textSecondary
            }
        }
    }

    // ==================================================== ⑤ 插件行列表
    /*! 行距单独一层容器：行要贴着（设计稿的行距量不出来，取 4），而页面级
        ``contentSpacing`` 是 10 —— 不另起一层就只能让每行自己去顶。间距 11 =
        设计稿「胶囊底 → 首行顶」21 - ``contentSpacing`` 10。 */
    ColumnLayout {
        objectName: "pluginsRowList"

        Layout.fillWidth: true
        Layout.topMargin: Lumi.pluginListGap - page.contentSpacing
        spacing: Lumi.pluginRowGap

        Repeater {
            model: Backend.pluginItems

            delegate: Rin.SettingCard {
                id: pluginCard

                objectName: "pluginCard" + index
                required property var modelData
                required property int index
                /*! 删除的两段式确认：第一次点击进入待确认态，3 秒后自动复位。 */
                property bool removeArmed: false

                Timer {
                    id: removeArmTimer
                    interval: 3000
                    onTriggered: pluginCard.removeArmed = false
                }

                leftPadding: Lumi.pluginRowPaddingX
                rightPadding: Lumi.pluginRowPaddingX
                topPadding: Lumi.pluginRowPaddingY
                bottomPadding: Lumi.pluginRowPaddingY
                Layout.fillWidth: true
                visible: page.matches(pluginCard.modelData, page.kindFilter)
                         && !page.isRemoved(pluginCard.modelData)
                title: modelData.title || modelData.id
                description: page.describe(modelData)
                /*! 图标三档回落（2026-10-17 用户指令「给插件的信息增加图标和
                    作者的接口」）：插件自己声明的图片 → 自己声明的字形 →
                    按类型给的字形（调试 = 烧瓶 / 外部 = 立体拼图 / 内建 = 拼图）。
                    ``name`` 与 ``source`` **必须互斥**：``Rin.Icon`` 里两条渲染
                    路径都在（``Text`` 画字形、``Image`` 画图片），同时给会叠两层。
                    插件图标的解析（字形名 / 相对路径 / URL）在
                    ``app/bridge.py::_plugin_icon``，这里只认结果。 */
                icon.name: modelData.iconSource !== ""
                           ? ""
                           : (modelData.iconName !== ""
                              ? modelData.iconName
                              : (modelData.debug
                                 ? "ic_fluent_beaker_20_regular"
                                 : (modelData.external
                                    ? "ic_fluent_puzzle_cube_20_regular"
                                    : "ic_fluent_puzzle_piece_20_regular")))
                icon.source: modelData.iconSource
                /*! 行里的插件图标按设计稿只有 16（墨迹 15×15）——``SettingCard``
                    默认 22，比标题（14）大出一圈，整行会显得头重。 */
                icon.size: Lumi.pluginRowIconSize

                content: [
                    // 外部插件的删除按钮（两段式确认；内建与调试夹具不给删 ——
                    // 它们的本体在安装目录里，删安装副本这个语义对它们无意义）。
                    // 三个控件直接做卡片子件：SettingCard 的默认属性把它们排进
                    // 右侧 Row，套一层 RowLayout 反而拿不到正确的宽度语义。
                    Rin.Button {
                        visible: pluginCard.modelData.external === true
                        text: pluginCard.removeArmed ? qsTr("确认删除") : qsTr("删除")
                        onClicked: {
                            if (!pluginCard.removeArmed) {
                                pluginCard.removeArmed = true
                                removeArmTimer.restart()
                                return
                            }
                            removeArmTimer.stop()
                            pluginCard.removeArmed = false
                            // 必须换新对象再赋值：同一个引用原样写回去不会发
                            // 属性变更通知，卡片就地隐藏就不会生效
                            var ids = Object.assign({}, page.removedIds)
                            ids[pluginCard.modelData.id] = true
                            page.removedIds = ids
                            Backend.removePlugin(pluginCard.modelData.id)
                        }
                    },

                    // 设计稿右侧：「启用」标签 + 开关本体，不要 On/Off 状态字。
                    // 把两者包进同一个 RowLayout：减少 SettingItem 内部嵌套层级
                    //（直接塞 Button + Text + Switch 三个独立子件会触发
                    // RowLayout 递归重排警告）。间距 12 = 设计稿「启用」墨迹右
                    // → 开关左 14，扣掉开关盒子自身的内缩。
                    RowLayout {
                        spacing: 12

                        Rin.Text {
                            Layout.alignment: Qt.AlignVCenter
                            typography: Rin.Typography.Body
                            text: qsTr("启用")
                        }

                        Rin.Switch {
                            Layout.preferredWidth: 40
                            Layout.preferredHeight: 20
                            Layout.alignment: Qt.AlignVCenter
                            text: " "
                            checkedText: ""
                            uncheckedText: ""
                            primaryColor: Lumi.accent
                            checked: pluginCard.modelData.enabled === true
                            onToggled: {
                                Backend.setPluginEnabled(pluginCard.modelData.id, checked)
                                page.restartHintShown = true
                                // ⚠️ 点击已经把 ``checked`` 上的绑定打断了（C++ 侧
                                // ``setChecked`` 会摘掉 QML 绑定，与「通用」页开机自启
                                // 开关是同一个坑）。虽然 ``pluginItemsChanged`` 会让
                                // Repeater 重建代理、绑定自然刷新，但「值没变 → 不重建」
                                // 的边角下开关会停在用户点的那一格；重装是幂等的。
                                checked = Qt.binding(function () {
                                    return pluginCard.modelData.enabled === true
                                })
                            }
                        }
                    }
                ]
            }
        }
    }
}
