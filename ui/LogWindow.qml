import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
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
    :func:`levelFill`），搜索框 ``Rin.TextField``，表格外框 ``Rin.Frame``，行内
    文字 / 图标 ``Rin.Text`` / ``Rin.Icon``，底栏 ``Rin.Button``，滚动条
    ``Rin.ScrollBar``。只保留 Rectangle 画行底色与 1px 分隔线这类纯装饰。

    ⚠️ 列表没用 ``Rin.ListView``：它的 delegate 是写死的单行 ``ListViewDelegate``，
    装不下会换行的异常堆栈和四列内容。这里用原生 ``ListView`` 自己画行，行内
    仍全部用 RinUI 组件。
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
    readonly property int timeColumnWidth: 168
    readonly property int levelColumnWidth: 96
    readonly property int categoryColumnWidth: 200
    readonly property int rowSpacing: 12

    // ------------------------------------------------------------ 数据
    property var entries: []
    property string searchText: ""
    property bool followTail: true
    property string copyHint: ""

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

    function scrollToBottom() {
        if (logList.count === 0)
            return
        logList.positionViewAtEnd()
        // positionViewAtEnd 对还没实例化的行只能按估算高度定位，最后一行换行后
        // 会差几个像素；直接贴住当前 contentHeight 的底，再等一拍让真实行高落定。
        logList.contentY = Math.max(0, logList.contentHeight - logList.height)
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
                        x: 12
                        y: 0
                        width: parent.width - 30
                        height: parent.height
                        spacing: logWindow.rowSpacing

                        Rin.Text {
                            Layout.preferredWidth: logWindow.timeColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                            text: qsTr("时间")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                        Rin.Text {
                            Layout.preferredWidth: logWindow.levelColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                            text: qsTr("等级")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                        Rin.Text {
                            Layout.preferredWidth: logWindow.categoryColumnWidth
                            Layout.alignment: Qt.AlignVCenter
                            text: qsTr("区域")
                            typography: Rin.Typography.BodyStrong
                            color: Lumi.textSecondary
                        }
                        Rin.Text {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
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

                ListView {
                    id: logList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    reuseItems: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: logWindow.filteredEntries

                    ScrollBar.vertical: Rin.ScrollBar {
                        policy: ScrollBar.AsNeeded
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

                    delegate: Rectangle {
                        id: entryRow
                        required property int index
                        required property var modelData

                        width: logList.width
                        height: rowLayout.implicitHeight + 12
                        color: {
                            if (logWindow.selectedKeys[modelData.key] === true)
                                return Lumi.fade(Lumi.accent,
                                                 rowHover.containsMouse ? 0.20 : 0.12)
                            return rowHover.containsMouse ? Lumi.tileHover : "transparent"
                        }

                        RowLayout {
                            id: rowLayout
                            x: 12
                            y: 6
                            width: entryRow.width - 30
                            spacing: logWindow.rowSpacing

                            Rin.Text {
                                Layout.preferredWidth: logWindow.timeColumnWidth
                                Layout.alignment: Qt.AlignTop
                                text: entryRow.modelData.time
                                textFormat: Text.PlainText
                                typography: Rin.Typography.Body
                                color: Lumi.textSecondary
                            }

                            RowLayout {
                                Layout.preferredWidth: logWindow.levelColumnWidth
                                Layout.alignment: Qt.AlignTop
                                spacing: 4

                                Rin.Icon {
                                    Layout.alignment: Qt.AlignVCenter
                                    name: logWindow.levelIcon(entryRow.modelData.level)
                                    size: 14
                                    color: logWindow.levelColor(entryRow.modelData.level)
                                }
                                Rin.Text {
                                    Layout.alignment: Qt.AlignVCenter
                                    text: logWindow.levelName(entryRow.modelData.level)
                                    typography: Rin.Typography.Body
                                    color: logWindow.levelColor(entryRow.modelData.level)
                                }
                            }

                            Rin.Text {
                                Layout.preferredWidth: logWindow.categoryColumnWidth
                                Layout.alignment: Qt.AlignTop
                                text: entryRow.modelData.category
                                textFormat: Text.PlainText
                                typography: Rin.Typography.Body
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                color: Lumi.textSecondary
                            }

                            Rin.Text {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignTop
                                text: entryRow.modelData.message
                                textFormat: Text.PlainText
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                typography: Rin.Typography.Body
                                color: Lumi.textPrimary
                                opacity: entryRow.modelData.level === "DEBUG" ? 0.85
                                         : entryRow.modelData.level === "TRACE" ? 0.7 : 1
                            }
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Lumi.hairline
                        }

                        MouseArea {
                            id: rowHover
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton
                            onClicked: (mouse) =>
                                logWindow.handleRowClick(entryRow.index, mouse.modifiers)
                        }
                    }
                }
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
                if (!logWindow.followTail || logList.count === 0)
                    return
                logList.positionViewAtEnd()
                logList.contentY = Math.max(0, logList.contentHeight - logList.height)
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
