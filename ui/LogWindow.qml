import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.qmlmodels
import RinUI as Rin
import Luminalium

/*!
    日志窗口（2026-11-21 用户指令：按 ClassIsland 的日志窗口重做）。

    版式照搬 ClassIsland ``Views/AppLogsWindow.axaml``：

    - 顶栏：左侧六个等级筛选胶囊（灾难 / 错误 / 警告 / 信息 / 调试 / 追踪），
      默认只勾「警告」及以上；右侧「筛选日志…」搜索框，匹配区域或正文。
    - 表格：时间 / 等级 / 区域 / 内容 四列，行间横线，选中行铺强调色淡底。
    - 底栏：右对齐「清空日志」「复制选中」。

    数据来源与 ClassIsland 不同 —— 那边直接用内存里的 ``AppLogService``，本项目
    日志只有 ``logs/luminalium.log``，所以由 ``Backend.readLogEntries`` 解析文件
    尾部（最多 1000 条）。窗口露出时全量读一次，之后每秒轮询；文件没动时后端
    直接回 ``changed=False``，不会重复搬运数据。

    「清空日志」与 ClassIsland 同义：只清**窗口里的显示**，文件不删。切点记在
    ``Backend._log_cleared_offset``，之前的行不再返回，之后新写的照常进来；
    真要删文件走设置标题栏「更多」→「打开日志目录」。

    选中项按 ``entry.key``（该行在文件里的字节偏移）记，不按行号 —— 轮询追加
    或 256 KB 尾部窗口挤掉旧行时，行号会错位而偏移不会。Ctrl 点按切换单条，
    Shift 点按从锚点选一段，普通点按只选当前这条。

    2026-11-22 用户指令「排版你可以学，组件你要用 RinUI 的啊」：所有能对上的
    控件一律换成 RinUI 的 —— 筛选胶囊用 ``Rin.PillButton``（可勾选、自动处理
    底色与悬停；勾选态用 ``primaryColor`` 换成各等级的实底色，见
    :func:`levelFill`），搜索框 ``Rin.TextField``，表格外框 ``Rin.Frame``、表格
    本体 ``Rin.TableView``（自带滚动条），行内文字 / 图标 ``Rin.Text`` /
    ``Rin.Icon``，底栏 ``Rin.Button``。只保留 Rectangle 画行底色与 1px 分隔线
    这类纯装饰。

    ⚠️ 表格用 ``Rin.TableView``（2026-11-22 用户指令），而不是 ``Rin.ListView``：
    后者 delegate 写死成单行 ``ListViewDelegate``，装不下四列和会换行的堆栈。
    TableView 的列数由模型决定，所以配 ``Qt.labs.qmlmodels.TableModel`` 四列
    （时间 / 等级 / 区域 / 内容）；行高不固定，用 ``rowHeightProvider`` 按
    「内容列宽下消息文本的换行高度」现算（缓存见 :func:`rowHeightFor`）。
*/

Rin.FluentWindowBase {
    id: logWindow

    objectName: "logWindow"
    title: qsTr("日志")
    visible: false
    width: 1040
    height: 640
    minimumWidth: 760
    minimumHeight: 420

    // ------------------------------------------------------------ 列宽
    // 表头与行共用同一组值，改一处两边一起动。
    // 内容列吃掉剩余宽度；末尾 18px 给 TableView 的滚动条留位，
    // 单元格再各留 12px 左内边距、内容列额外留 18px 右内边距。
    readonly property int timeColumnWidth: 168
    readonly property int levelColumnWidth: 96
    readonly property int categoryColumnWidth: 200
    readonly property int messageColumnWidth: Math.max(160,
        logTable.width - timeColumnWidth - levelColumnWidth - categoryColumnWidth - 18)
    readonly property int messageTextWidth: Math.max(100, messageColumnWidth - 30)

    // ------------------------------------------------------------ 数据
    property var entries: []
    property string searchText: ""
    property bool followTail: true
    property string copyHint: ""

    // 行高缓存（行号 -> 高度）。过滤 / 搜索 / 窗口宽度一变就整体作废，
    // 详见 :func:`syncTableModel` 与 :func:`rowHeightFor`。
    property var rowHeights: ({})
    // 上一轮写进 TableModel 的过滤结果，用来做增量同步（只比 key）。
    property var syncedEntries: []
    property int hoveredRow: -1

    // 与 ClassIsland 的默认值一致：只显示警告及以上。
    property bool filterCritical: true
    property bool filterError: true
    property bool filterWarning: true
    property bool filterInfo: false
    property bool filterDebug: false
    property bool filterTrace: false

    // 选中集合用「key -> true」的对象存，整体重新赋值来通知绑定刷新。
    property var selectedKeys: ({})
    property int selectionAnchor: -1
    readonly property int selectedCount: Object.keys(selectedKeys).length

    readonly property var filteredEntries: {
        var needle = searchText.trim().toLowerCase()
        var result = []
        for (var i = 0; i < entries.length; i++) {
            var entry = entries[i]
            if (!levelEnabled(entry.level))
                continue
            if (needle !== ""
                    && String(entry.message).toLowerCase().indexOf(needle) < 0
                    && String(entry.category).toLowerCase().indexOf(needle) < 0)
                continue
            result.push(entry)
        }
        return result
    }

    // 过滤结果一变（追加 / 筛选 / 搜索）就同步 TableModel。
    onFilteredEntriesChanged: syncTableModel()

    // 列宽变了，消息的换行高度全部重算。
    onMessageTextWidthChanged: {
        logWindow.rowHeights = ({})
        logTable.forceLayout()
    }

    Component.onCompleted: syncTableModel()

    // 深色档的 SystemFillColorCritical / Caution 是提亮过的，和浅色档不能共用。
    readonly property color criticalColor: Lumi.isDark ? "#FF99A4" : "#C42B1C"
    readonly property color warningColor: Lumi.isDark ? "#FCE100" : "#9D5D00"

    //: 顶栏胶囊的数据源：顺序照 ClassIsland（严重 → 追踪）。
    readonly property var filterLevels: [
        { level: "CRITICAL", label: qsTr("灾难"),
          icon: "ic_fluent_error_circle_20_regular" },
        { level: "ERROR", label: qsTr("错误"),
          icon: "ic_fluent_dismiss_circle_20_regular" },
        { level: "WARNING", label: qsTr("警告"),
          icon: "ic_fluent_warning_20_regular" },
        { level: "INFO", label: qsTr("信息"),
          icon: "ic_fluent_info_20_regular" },
        { level: "DEBUG", label: qsTr("调试"),
          icon: "ic_fluent_bug_20_regular" },
        { level: "TRACE", label: qsTr("追踪"),
          icon: "ic_fluent_arrow_right_20_regular" }
    ]

    function filterOn(level) {
        switch (level) {
        case "CRITICAL": return logWindow.filterCritical
        case "ERROR": return logWindow.filterError
        case "WARNING": return logWindow.filterWarning
        case "INFO": return logWindow.filterInfo
        case "DEBUG": return logWindow.filterDebug
        case "TRACE": return logWindow.filterTrace
        default: return true
        }
    }

    /*!
        写回某个等级的开关并清掉选中项（筛选范围变了，旧选中已不在列表里）。

        ⚠️ 胶囊控件点按后必须重装 ``checked`` 绑定：``AbstractButton`` 内部改
        ``checked`` 会把 QML 绑定摘掉，不重装的话配置再变胶囊就不跟了 —— 与
        设置页「开机自启」开关是同一个坑。
    */
    function setFilterOn(level, value) {
        switch (level) {
        case "CRITICAL": logWindow.filterCritical = value; break
        case "ERROR": logWindow.filterError = value; break
        case "WARNING": logWindow.filterWarning = value; break
        case "INFO": logWindow.filterInfo = value; break
        case "DEBUG": logWindow.filterDebug = value; break
        case "TRACE": logWindow.filterTrace = value; break
        }
        logWindow.resetSelection()
    }

    function levelEnabled(level) {
        return logWindow.filterOn(level)
    }

    function levelName(level) {
        switch (level) {
        case "CRITICAL": return qsTr("灾难")
        case "ERROR": return qsTr("错误")
        case "WARNING": return qsTr("警告")
        case "INFO": return qsTr("信息")
        case "DEBUG": return qsTr("调试")
        case "TRACE": return qsTr("追踪")
        default: return level
        }
    }

    function levelIcon(level) {
        switch (level) {
        case "CRITICAL": return "ic_fluent_error_circle_20_regular"
        case "ERROR": return "ic_fluent_dismiss_circle_20_regular"
        case "WARNING": return "ic_fluent_warning_20_regular"
        case "INFO": return "ic_fluent_info_20_regular"
        case "DEBUG": return "ic_fluent_bug_20_regular"
        case "TRACE": return "ic_fluent_arrow_right_20_regular"
        default: return "ic_fluent_text_bullet_list_20_regular"
        }
    }

    function levelColor(level) {
        switch (level) {
        case "CRITICAL":
        case "ERROR": return criticalColor
        case "WARNING": return warningColor
        case "INFO": return Lumi.textSecondary
        default: return Lumi.textTertiary
        }
    }

    /*!
        胶囊勾选态的实底色。

        为什么不直接用 :func:`levelColor`：那是给深色底上的文字 / 图标用的
        「提亮档」，深色主题的警告黄是 #FCE100，做成实心底配白字根本看不清。

        暗色档整体再提亮一档（2026-11-22 用户指令「按等级着色要在暗色模式下
        加权提亮」）：深红 / 深琥珀压在深色窗口上会糊掉，换成饱和度高一级的
        Fluent 色；每档都保证白字对比度 ≥ 4.5:1。
    */
    function levelFill(level) {
        switch (level) {
        case "CRITICAL": return Lumi.isDark ? "#D13438" : "#A4262C"
        case "ERROR": return Lumi.isDark ? "#E81123" : "#C42B1C"
        case "WARNING": return Lumi.isDark ? "#D83B01" : "#9D5D00"
        case "INFO": return Lumi.isDark ? "#0078D4" : "#0F6CBD"
        case "DEBUG": return Lumi.isDark ? "#7E5BC4" : "#6E4AB8"
        case "TRACE": return Lumi.isDark ? "#757575" : "#5C5C5C"
        default: return Lumi.accent
        }
    }

    function resetSelection() {
        selectedKeys = ({})
        selectionAnchor = -1
    }

    function applyPayload(payload, force) {
        if (!payload || (!force && !payload.changed))
            return
        var next = payload.entries || []
        // 旧选中项里已经被轮转 / 256 KB 窗口挤掉的 key 要清掉，否则底栏计数
        // 会把不存在的行也算进去。
        var alive = ({})
        for (var i = 0; i < next.length; i++)
            alive[next[i].key] = true
        var kept = ({})
        var hasKept = false
        for (var key in selectedKeys) {
            if (alive[key]) {
                kept[key] = true
                hasKept = true
            }
        }
        if (hasKept)
            selectedKeys = kept
        else if (selectedCount > 0)
            selectedKeys = ({})

        entries = next
        if (followTail)
            Qt.callLater(scrollToBottom)
    }

    function reload() {
        followTail = true
        resetSelection()
        applyPayload(Backend.readLogEntries(true), true)
        Qt.callLater(scrollToBottom)
    }

    function entryKey(row) {
        return row >= 0 && row < filteredEntries.length
               ? filteredEntries[row].key : -1
    }

    function entryLevel(row) {
        return row >= 0 && row < filteredEntries.length
               ? filteredEntries[row].level : ""
    }

    /*!
        行高 = 内容列在**当前列宽**下换行后的高度 + 上下留白。

        测量借用一个不可见的 ``Rin.Text``（``rowMeasure``），排版参数与真正
        渲染消息的单元格完全一致，所以量出来的高度就是实际需要的高度。
        结果按行号缓存，TableView 一次布局会反复问同一行，不能每次都排一遍
        文本；缓存作废时机见上面 ``rowHeights`` 的注释。
    */
    function rowHeightFor(row) {
        var heights = logWindow.rowHeights
        if (heights[row] !== undefined)
            return heights[row]
        rowMeasure.text = row >= 0 && row < filteredEntries.length
                          ? filteredEntries[row].message : ""
        var height = Math.max(30, Math.ceil(rowMeasure.implicitHeight) + 12)
        heights[row] = height
        return height
    }

    /*!
        把过滤结果增量写进 TableModel。

        日志每秒追加一条，尾部窗口（最多 1000 条）再挤掉一条 —— 全量重建会
        每秒发上千个行信号。这里按 key 找公共前缀，只删尾巴、只追加新行；
        筛选 / 搜索变化时前缀通常为 0，退化成全量重建，反正是用户操作。
    */
    function syncTableModel() {
        var wanted = filteredEntries
        var previous = syncedEntries
        var common = 0
        var limit = Math.min(previous.length, wanted.length)
        while (common < limit && previous[common].key === wanted[common].key)
            common++

        if (common === 0)
            logModel.clear()
        else
            while (logModel.rowCount > common)
                logModel.removeRow(logModel.rowCount - 1)

        for (var i = common; i < wanted.length; i++) {
            var entry = wanted[i]
            logModel.appendRow({
                time: entry.time,
                level: entry.level,
                category: entry.category,
                message: entry.message
            })
        }

        syncedEntries = wanted

        // 前缀之后的行高全部作废：行号对应的内容变了，或列宽变了。
        var heights = logWindow.rowHeights
        var changed = common !== wanted.length || common !== previous.length
        if (changed) {
            for (var index in heights) {
                if (Number(index) >= common)
                    delete heights[index]
            }
            logWindow.rowHeights = heights
            logTable.forceLayout()
        }

        if (followTail)
            Qt.callLater(scrollToBottom)
    }

    function scrollToBottom() {
        if (logModel.rowCount === 0)
            return
        // 不调 positionViewAtRow：这个 Qt 版本里它的 mode 枚举（TableView.End）
        // 是 undefined，传进去会被当成默认值先跳回顶部。contentHeight 由
        // rowHeightProvider 逐行算出，直接按它贴底就是准的。
        logTable.contentY = Math.max(0, logTable.contentHeight - logTable.height)
        // 委托真正加载后 contentHeight 可能再微调一点，bottomSettle 补一次。
        bottomSettle.restart()
    }

    function handleRowClick(index, modifiers) {
        var entry = filteredEntries[index]
        if (!entry)
            return
        var ctrl = (modifiers & Qt.ControlModifier) !== 0
        var shift = (modifiers & Qt.ShiftModifier) !== 0
        var next = ({})

        if (shift && selectionAnchor >= 0 && selectionAnchor < filteredEntries.length) {
            var start = Math.min(selectionAnchor, index)
            var end = Math.max(selectionAnchor, index)
            for (var i = start; i <= end; i++)
                next[filteredEntries[i].key] = true
        } else if (ctrl) {
            for (var key in selectedKeys)
                next[key] = true
            if (next[entry.key] === true)
                delete next[entry.key]
            else
                next[entry.key] = true
            selectionAnchor = index
        } else {
            next[entry.key] = true
            selectionAnchor = index
        }
        selectedKeys = next
    }

    function copySelected() {
        var parts = []
        for (var i = 0; i < filteredEntries.length; i++) {
            var entry = filteredEntries[i]
            if (selectedKeys[entry.key] === true) {
                // 与 ClassIsland 的 LogEntry.ToString() 相同：
                // [时间] [等级] 区域:\n正文
                parts.push("[" + entry.time + "] [" + entry.level + "] "
                           + entry.category + ":\n" + entry.message)
            }
        }
        if (parts.length === 0)
            return
        Backend.copyToClipboard(parts.join("\n"))
        copyHint = qsTr("已复制 %1 条日志").arg(parts.length)
        copyHintTimer.restart()
    }

    function clearLogs() {
        Backend.clearLogEntries()
        entries = []
        resetSelection()
        copyHint = ""
        followTail = true
    }

    onVisibleChanged: {
        if (visible)
            reload()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        // -------------------------------------------------------- 顶栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // 六个等级胶囊：Rin.PillButton 自带可勾选 / 强调色选中态 / 悬停，
            // 不再手画 Chip。
            Repeater {
                model: logWindow.filterLevels

                delegate: Rin.PillButton {
                    required property var modelData

                    text: modelData.label
                    icon.name: modelData.icon
                    // 勾选后整颗胶囊就是该等级的实底色（RinUI 的 PillButton
                    // 用 primaryColor 画底与描边），未勾选仍是中性灰。
                    primaryColor: logWindow.levelFill(modelData.level)
                    checkable: true
                    checked: logWindow.filterOn(modelData.level)
                    onToggled: {
                        logWindow.setFilterOn(modelData.level, checked)
                        checked = Qt.binding(function () {
                            return logWindow.filterOn(modelData.level)
                        })
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Item {
                Layout.preferredWidth: 240
                Layout.preferredHeight: 32

                Rin.TextField {
                    id: searchField
                    anchors.fill: parent
                    leftPadding: 32
                    placeholderText: qsTr("筛选日志…")
                    onTextChanged: {
                        logWindow.searchText = text
                        logWindow.resetSelection()
                    }
                }
                Rin.Icon {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    name: "ic_fluent_search_20_regular"
                    size: 14
                    color: Lumi.textSecondary
                }
            }
        }

        // -------------------------------------------------------- 表格
        Rin.Frame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0
            radius: Lumi.controlRadius
            color: Lumi.panelCardBg
            clip: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36

                    RowLayout {
                        anchors.fill: parent
                        spacing: 0

                        Rin.Text {
                            Layout.preferredWidth: logWindow.timeColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                            leftPadding: 12
                            text: qsTr("时间")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                        Rin.Text {
                            Layout.preferredWidth: logWindow.levelColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                            leftPadding: 12
                            text: qsTr("等级")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                        Rin.Text {
                            Layout.preferredWidth: logWindow.categoryColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                            leftPadding: 12
                            text: qsTr("区域")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                        Rin.Text {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
                            leftPadding: 12
                            text: qsTr("内容")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1
                        color: Lumi.hairline
                    }
                }

                // 表格本体：RinUI 的 TableView（Qt Quick TableView 的封装）。
                // 列数由 TableModel 决定（四列），不再手拼 RowLayout。
                Rin.TableView {
                    id: logTable
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    columnSpacing: 0
                    rowSpacing: 0
                    model: logModel

                    // RinUI 的 TableView 自带一段「contentY 归零 + 淡入」的入场
                    // 动画，每次 rowsInserted 都会重播。日志每秒追加一条，
                    // 留着它用户往下翻一屏就会被弹回顶部，贴底也永远贴不住。
                    // 换成空动画后 restart() 无害。
                    updateAnimation: ParallelAnimation {}

                    columnWidthProvider: function (column) {
                        switch (column) {
                        case 0: return logWindow.timeColumnWidth
                        case 1: return logWindow.levelColumnWidth
                        case 2: return logWindow.categoryColumnWidth
                        default: return logWindow.messageColumnWidth
                        }
                    }
                    rowHeightProvider: function (row) {
                        return logWindow.rowHeightFor(row)
                    }

                    onMovementEnded: {
                        // 留 24px 容差：程序化贴底偶尔差几像素，别把它当成
                        // 「用户滚上去了」而关掉跟随。
                        logWindow.followTail =
                            contentY >= contentHeight - height - 24
                    }
                    onContentHeightChanged: {
                        if (logWindow.followTail)
                            Qt.callLater(logWindow.scrollToBottom)
                    }

                    delegate: Item {
                        id: logCell

                        required property int row
                        required property int column
                        required property string display

                        readonly property bool isSelected:
                            logWindow.selectedKeys[logWindow.entryKey(row)] === true
                        readonly property bool isHovered: logWindow.hoveredRow === row

                        // 行底色铺满单元格；四列拼起来就是一整条选中带。
                        Rectangle {
                            anchors.fill: parent
                            color: logCell.isSelected
                                   ? Lumi.fade(Lumi.accent, logCell.isHovered ? 0.20 : 0.12)
                                   : logCell.isHovered ? Lumi.tileHover : "transparent"
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Lumi.hairline
                        }

                        // 时间列
                        Rin.Text {
                            visible: logCell.column === 0
                            x: 12
                            y: 6
                            width: logCell.width - 12
                            text: logCell.display
                            textFormat: Text.PlainText
                            typography: Rin.Typography.Body
                            color: Lumi.textSecondary
                        }

                        // 等级列：图标 + 文字，颜色按等级
                        RowLayout {
                            visible: logCell.column === 1
                            x: 12
                            y: 6
                            spacing: 4

                            Rin.Icon {
                                Layout.alignment: Qt.AlignVCenter
                                name: logWindow.levelIcon(logWindow.entryLevel(logCell.row))
                                size: 14
                                color: logWindow.levelColor(logWindow.entryLevel(logCell.row))
                            }
                            Rin.Text {
                                Layout.alignment: Qt.AlignVCenter
                                text: logWindow.levelName(logWindow.entryLevel(logCell.row))
                                typography: Rin.Typography.Body
                                color: logWindow.levelColor(logWindow.entryLevel(logCell.row))
                            }
                        }

                        // 区域列
                        Rin.Text {
                            visible: logCell.column === 2
                            x: 12
                            y: 6
                            width: logCell.width - 12
                            text: logCell.display
                            textFormat: Text.PlainText
                            typography: Rin.Typography.Body
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            color: Lumi.textSecondary
                        }

                        // 内容列：允许换行，行高由 rowHeightProvider 量出来
                        Rin.Text {
                            visible: logCell.column === 3
                            x: 12
                            y: 6
                            width: logCell.width - 30
                            text: logCell.display
                            textFormat: Text.PlainText
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            typography: Rin.Typography.Body
                            color: Lumi.textPrimary
                            opacity: logWindow.entryLevel(logCell.row) === "DEBUG" ? 0.85
                                     : logWindow.entryLevel(logCell.row) === "TRACE" ? 0.7 : 1
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton
                            onEntered: logWindow.hoveredRow = logCell.row
                            onExited: {
                                if (logWindow.hoveredRow === logCell.row)
                                    logWindow.hoveredRow = -1
                            }
                            onClicked: (mouse) =>
                                logWindow.handleRowClick(logCell.row, mouse.modifiers)
                        }
                    }
                }
            }

            // 隐藏的测量文本：排版参数与内容列的实际单元格保持一致，
            // rowHeightFor 靠它的 implicitHeight 算换行后的真实行高。
            // 必须放在布局器外面，否则 ColumnLayout 会接管它的位置和宽度。
            Rin.Text {
                id: rowMeasure
                visible: false
                width: logWindow.messageTextWidth
                textFormat: Text.PlainText
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                typography: Rin.Typography.Body
            }

            Rin.Text {
                anchors.centerIn: parent
                width: parent.width - 48
                horizontalAlignment: Text.AlignHCenter
                visible: logWindow.filteredEntries.length === 0
                text: logWindow.entries.length === 0
                      ? qsTr("暂无日志内容")
                      : qsTr("没有符合筛选条件的日志")
                typography: Rin.Typography.Body
                color: Lumi.textTertiary
            }
        }

        // -------------------------------------------------------- 底栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rin.Text {
                text: logWindow.copyHint
                visible: text !== ""
                typography: Rin.Typography.Caption
                color: Lumi.textSecondary
            }

            Item { Layout.fillWidth: true }

            Rin.Button {
                objectName: "logClearButton"
                text: qsTr("清空日志")
                icon.name: "ic_fluent_broom_20_regular"
                enabled: logWindow.entries.length > 0
                onClicked: logWindow.clearLogs()
            }
            Rin.Button {
                objectName: "logCopyButton"
                text: qsTr("复制选中")
                icon.name: "ic_fluent_copy_20_regular"
                enabled: logWindow.selectedCount > 0
                onClicked: logWindow.copySelected()
            }
        }

        // 非可视对象挂在 ColumnLayout 下而不是窗口根节点：FluentWindowBase 的
        // 默认属性只收 Item，Timer/Shortcut 直接写在根上会编译失败。布局器会
        // 忽略非 Item 子节点，不影响排版。
        // 四列表格的数据源：TableView 的列数由模型决定，所以用 TableModel
        // 声明四列；内容由 syncTableModel 增量写入。
        TableModel {
            id: logModel
            TableModelColumn { display: "time" }
            TableModelColumn { display: "level" }
            TableModelColumn { display: "category" }
            TableModelColumn { display: "message" }
        }

        // 窗口露出时每秒看一次日志文件；隐藏时停掉，别让常驻应用白轮询。
        Timer {
            interval: 1000
            repeat: true
            running: logWindow.visible
            onTriggered: logWindow.applyPayload(Backend.readLogEntries(false), false)
        }

        Timer {
            id: copyHintTimer
            interval: 2000
            onTriggered: logWindow.copyHint = ""
        }

        // 贴底的第二次修正：等最后一条委托的真实高度出来再对齐一次。
        Timer {
            id: bottomSettle
            interval: 60
            onTriggered: {
                if (!logWindow.followTail || logModel.rowCount === 0)
                    return
                logTable.contentY = Math.max(0, logTable.contentHeight - logTable.height)
            }
        }

        Shortcut {
            sequences: ["Ctrl+C"]
            // 搜索框有焦点时让 Ctrl+C 走输入框自己的复制，别抢它。
            enabled: logWindow.visible && logWindow.selectedCount > 0
                     && !searchField.activeFocus
            onActivated: logWindow.copySelected()
        }
    }
}
