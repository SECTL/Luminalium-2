import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    通用：开机自启、快捷面板开关、界面语言与旁白语言。

    2026-09-25 导航重构后本页吸收了原「行为」子页的全部内容；
    2026-10-01 又吸收了原「外观」页的三张卡（应用主题 / 强调色 / 界面语言）——
    用户指令「把『外观』改成『主界面』」，而这三项是**全局外观设定**、不属于
    「主界面」这个概念，所以随改名一起并进来；原「外观」页改名为
    ``settings/MainInterface.qml`` 并留空。日志级别归调试窗口。

    ⚠️ 2026-10-01（第二轮）用户指令：「托盘」整组（常驻托盘 / 启动时提示 /
    左键打开快捷面板 / 托盘提示文字）**连着相关的逻辑和代码一块删掉**；
    「失去焦点时收起」**作为默认行为、不再作为设置项**。两者都已落地：
    托盘行为在 ``application.py`` / ``tray.py`` 里写死（常驻、提示文字取
    ``app.name``、左键恒唤出面板、启动不再弹气泡），失焦收起在
    ``windows.py::_on_panel_active_changed`` 里恒定生效。**别再往回加**。

    ⚠️ 2026-10-01（第四轮）用户指令：「把外观那一块除了界面语言改到新的个性化」
    —— 「应用主题」与「强调色」两张卡连同 ``accentPresets`` 一起搬去了新页
    ``settings/Personalization.qml``；本页只留下「界面语言」，分组标题相应由
    「外观」改成「语言」（语言不属于外观，留着旧标题名不副实）。
    于是本页只剩 2 张卡：快捷方式锁定 + 界面语言。

    ⚠️ 2026-10-06 用户指令：「把应用是跟随系统还是亮色暗色移到通用，个性化设置
    先只留强调色」—— 「应用主题」（跟随系统 / 浅色 / 深色）从「个性化」搬回来，
    单独成一组「外观」排在「启动」之后；「强调色」留在「个性化」不动。
    于是本页 4 张卡：开机自启 + 应用主题 + 快捷方式锁定 + 界面语言。
    （2026-10-17 起是 5 张：语言组末尾多了「旁白与配音语言」。）

    2026-10-04 用户指令：「通用设置新增开机自启开关」—— 顶部新增「启动」分组与
    「开机自启」卡（3 张卡）。**它和别的开关不是一回事**：本体是 Windows 注册表
    的 ``Run`` 键（``app/autostart.py``），``Backend.settings.autostart`` 读的
    也是注册表的**实时状态**，不是配置。所以：
      * 后端 ``setSetting("autostart", …)`` 是**同步**写注册表并回读，失败会把
        状态弹回去 —— 见下面开关的 ``onToggled`` 里为什么要重装 ``checked`` 绑定；
      * 手改 ``config/config.json`` 的 ``app.autostart`` 不会改变实际行为。
*/
Rin.FluentPage {
    id: page

    title: qsTr("通用")
    contentSpacing: 10

    // ============================================================ 启动
    // 2026-10-04 用户指令：通用设置新增开机自启开关。
    // 放在最上面：「随系统启动」是整页里层级最高的一项（其余都是应用内的行为）。

    Rin.Text {
        Layout.fillWidth: true
        typography: Rin.Typography.BodyStrong
        text: qsTr("启动")
    }

    Rin.SettingCard {
        objectName: "generalAutostart"

        Layout.fillWidth: true
        title: qsTr("开机自启")
        description: qsTr("登录系统后自动启动 Luminalium")
        icon.name: "ic_fluent_power_20_regular"

        Rin.Switch {
            id: autostartSwitch

            primaryColor: Lumi.accent
            checked: Backend.settings.autostart === true
            onToggled: {
                // 同步写注册表（失败时后端会把真实状态广播回来）。
                Backend.setSetting("autostart", checked)
                // ⚠️ 上面这一下点击**已经把 ``checked`` 上的绑定打断了** ——
                // 控件内部（C++ 侧 ``setChecked``）改这个属性会摘掉 QML 绑定，
                // 之后 ``Backend.settings`` 再怎么变它都不跟（实测：绑定在
                // 用户点击后失效，外部改值 checked 纹丝不动）。不重装的话，
                // 注册表写失败时开关会停在用户点的那一格，显示成「开着」而
                // 实际没写进去 —— 正是「关了却没关掉」的来源。重装是幂等的，
                // 写成功时也照装不误（值本来就一样，不会抖）。
                checked = Qt.binding(function () {
                    return Backend.settings.autostart === true
                })
            }
        }
    }

    // ============================================================ 外观
    // 2026-10-06 用户指令：主题模式（跟随系统 / 浅色 / 深色）从「个性化」搬回本页。
    // 排在「启动」之后：深浅模式是**跟系统走的环境设定**（跟「开机自启」一样属
    // 整机一级），比下面「快捷面板」那种应用内行为高一层。
    // ⚠️ 强调色不在这里 —— 它是纯审美选择，留在「个性化」页。

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("外观")
    }

    Rin.SettingCard {
        objectName: "generalTheme"

        Layout.fillWidth: true
        title: qsTr("应用主题")
        description: qsTr("影响所有窗口与控件的取色")
        icon.name: "ic_fluent_dark_theme_20_regular"

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: [qsTr("跟随系统"), qsTr("浅色"), qsTr("深色")]
            currentIndex: {
                const value = Backend.settings.theme
                if (value === "light") return 1
                if (value === "dark") return 2
                return 0
            }
            onActivated: Backend.setSetting("theme", ["auto", "light", "dark"][currentIndex])
        }
    }

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("快捷面板")
    }

    Rin.SettingCard {
        objectName: "generalShortcutsLock"

        Layout.fillWidth: true
        title: qsTr("快捷方式锁定")
        description: qsTr("锁定后面板上的「编辑」按钮消失，防止误改")
        icon.name: "ic_fluent_lock_closed_20_regular"

        Rin.Switch {
            primaryColor: Lumi.accent
            checked: Backend.settings.panel_shortcuts_locked === true
            onToggled: Backend.setSetting("panel_shortcuts_locked", checked)
        }
    }

    // ============================================================ 语言
    // 2026-10-01（第四轮）「外观」组的前两张卡（应用主题 / 强调色）整体搬去了
    // ``settings/Personalization.qml``（新导航项「个性化」），本页只剩「界面语言」。
    // 语言不属于外观，所以分组标题跟着从「外观」换成「语言」。
    // 2026-10-06：「应用主题」又搬回来了（见上面「外观」组），「强调色」仍在
    // 「个性化」。本页现在有**两个**分组标题各自叫「外观」以外的名字 —— 语言组
    // 保持独立成组，别跟上面合并。

    Rin.Text {
        Layout.fillWidth: true
        Layout.topMargin: 10
        typography: Rin.Typography.BodyStrong
        text: qsTr("语言")
    }

    Rin.SettingCard {
        id: card
        objectName: "generalInterfaceLanguage"

        Layout.fillWidth: true
        title: qsTr("界面语言")
        description: qsTr("切换后需要重新加载应用")
        icon.name: "ic_fluent_local_language_20_regular"

        /*! 语言名单：code 落 ``app.language`` 配置，同时也是
            ``translations/luminalium_<code>.qm`` 的文件名（zh_CN 是源语言、
            不装翻译器，界面即 QML 里的中文原文）。
            name 用**各自语言的母语名**显示（「界面语言」这一项本身该让
            看不懂当前语言的人也认得，惯例同 Windows / VS Code）。
            name 不参与存储与匹配，改显示名不用动配置。

            顺序：先源语言，再按字母排（en → ja → ko → yue → zh_TW）。
            ⚠️ 粤语用 ``yue_HK``（ISO 639-3 + 地区码），不是 ``zh_HK`` ——
            Qt 6 的 QLocale 认得这个代码（``QLocale("yue_HK").language()``
            = ``Cantonese``，nativeLanguageName = 粵語），写成 zh_HK 会被
            当成繁体中文、拿不到粤语译文。

            加一门语言的三处改动：这里 + ``tools/update_translations.py``
            的 ``LANGUAGES`` + ``translations/`` 下的两个 ts。详见
            update_translations.py 头注释。 */
        readonly property var languages: [
            { code: "zh_CN", name: "简体中文" },
            { code: "en_US", name: "English" },
            { code: "ja_JP", name: "日本語" },
            { code: "ko_KR", name: "한국어" },
            { code: "yue_HK", name: "粵語" },
            { code: "zh_TW", name: "繁體中文" }
        ]

        Rin.ComboBox {
            Layout.preferredWidth: 150
            model: card.languages
            textRole: "name"
            currentIndex: {
                var index = 0
                for (var i = 0; i < card.languages.length; ++i) {
                    if (card.languages[i].code === Backend.settings.language) {
                        index = i
                        break
                    }
                }
                return index
            }
            onActivated: Backend.setSetting("language", card.languages[currentIndex].code)
        }
    }

    /*! 2026-10-17 用户指令：「常规设置 → 语言」新增「旁白与配音语言」。

        这一项是**对外暴露的全局配音语种配置**：主程序里任何要出声的旁白
        模块、以及日后插件里的旁白 / 配音场景，都读同一个值
        （Python：``app/narration.py::language(config)``；插件：
        ``ctx.narration_language()``；QML：``Backend.narrationLanguage``）。
        **别**在别处再登记一份语种项 —— 那样界面语言和配音语言迟早会分裂。

        与上面「界面语言」的关系：**两个独立维度**。上面那个换 UI 文案与字体
        （``app.language``，要重启），这个只换旁白的声音（``narration.language``，
        立即生效）。英文界面 + 中文旁白是合法组合，所以刻意不复用同一个键、
        也不共用一个下拉。

        版式：下拉（与「界面语言」同款同宽，保持语言类设置项的一致观感）+
        紧邻的一颗试听按钮（放在下拉**左侧**：同一组里两张卡的下拉右沿因此落在
        同一条竖线上 —— 按钮若挂在右边，这一行的下拉会被挤左 40px，看着像没对齐）。
        这是 Windows 11「辅助功能 → 语音」那套「下拉 + 预览」的做法。
        为什么不做成「下拉里每一项右侧各挂一颗按钮」：RinUI 的
        ``ComboBox`` 弹出层是它自己的 ``ContextMenu``（``model: delegateModel``），
        没有 delegate 注入口，硬做就得改 site-packages —— 仓储铁律不允许。
        当前选中项就是试听对象，切一档点一下就听到那一档，功能上等价。

        语种表与素材映射**全部来自 Python**（``Backend.narrationLanguages``，
        源头 ``app/narration.py::SAMPLES``）：QML 这边不写死文件名，也不判断
        「有没有素材」——``sampleAvailable`` 由后端算好，素材缺失时按钮自己
        变灰（``resources/narration_testaudio_*.mp3`` 三条就是全部素材，
        加一档要连素材一起加）。

        播放状态：后端发 ``narrationPreviewState(code, playing)``，按钮据此在
        喇叭 / 停止之间换图标；正在放的时候再点一下是停止。没有这个回声，
        点下去界面毫无动静（示例音频有半秒前奏），看着像没反应。 */
    Rin.SettingCard {
        id: narrationCard
        objectName: "generalNarrationLanguage"

        Layout.fillWidth: true
        title: qsTr("旁白与配音语言")
        description: qsTr("旁白与配音类语音统一使用的语种，可试听该语种的示例")
        icon.name: "ic_fluent_speaker_2_20_regular"

        //: 候选表来自后端（每项 { code, name, sampleAvailable }）。
        readonly property var languages: Backend.narrationLanguages
        //: 正在试听的语种 code，空串 = 没在放。
        property string previewingCode: ""

        //: 当前选中项（按 ComboBox 的索引取，索引失配时退回第一项 ——
        //: 配置被手改成脏值时后端已归一，理论上不会走到，兜底而已）。
        function codeAt(index) {
            if (!languages || languages.length === 0)
                return ""
            return (index >= 0 && index < languages.length)
                    ? languages[index].code : languages[0].code
        }

        readonly property string selectedCode: codeAt(narrationCombo.currentIndex)
        readonly property bool selectedSampleAvailable: {
            if (!languages || languages.length === 0)
                return false
            var index = narrationCombo.currentIndex
            var entry = (index >= 0 && index < languages.length) ? languages[index] : languages[0]
            return entry.sampleAvailable === true
        }

        Connections {
            target: Backend
            function onNarrationPreviewState(code, playing) {
                narrationCard.previewingCode = playing ? code : ""
            }
        }

        // 试听按钮排在**下拉之前**：同一组里「界面语言」那张卡的下拉右沿与
        // 这张卡的下拉右沿因此落在同一条竖线上（按钮挂右侧会把下拉挤左 40px）。
        Rin.ToolButton {
            id: previewButton
            objectName: "narrationPreviewButton"

            flat: true
            width: 32
            height: 32
            enabled: narrationCard.selectedSampleAvailable
            icon.name: (narrationCard.previewingCode !== ""
                        && narrationCard.previewingCode === narrationCard.selectedCode)
                       ? "ic_fluent_stop_20_regular"
                       : "ic_fluent_speaker_2_20_regular"

            onClicked: {
                if (narrationCard.previewingCode === narrationCard.selectedCode)
                    Backend.stopNarrationSample()
                else
                    Backend.playNarrationSample(narrationCard.selectedCode)
            }

            Rin.ToolTip {
                // 素材缺失时把原因说清楚，别让用户看着一颗灰按钮猜。
                text: !narrationCard.selectedSampleAvailable
                      ? qsTr("该语种的示例音频缺失")
                      : (narrationCard.previewingCode === narrationCard.selectedCode
                         ? qsTr("停止试听")
                         : qsTr("试听该语种的配音示例"))
                visible: parent.hovered
            }
        }

        Rin.ComboBox {
            id: narrationCombo
            Layout.preferredWidth: 150

            model: narrationCard.languages
            textRole: "name"
            currentIndex: {
                var index = 0
                for (var i = 0; i < narrationCard.languages.length; ++i) {
                    if (narrationCard.languages[i].code === Backend.narrationLanguage) {
                        index = i
                        break
                    }
                }
                return index
            }
            // 换语种时先把还在放的那条停掉，否则会听到上一档的尾音。
            onActivated: {
                if (narrationCard.previewingCode !== "")
                    Backend.stopNarrationSample()
                Backend.setSetting("narration_language",
                                   narrationCard.languages[currentIndex].code)
            }
        }
    }
}
