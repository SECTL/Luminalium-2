import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    通用：开机自启、快捷面板开关与界面语言。

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
        Layout.fillWidth: true
        title: qsTr("界面语言")
        description: qsTr("切换后需要重新加载应用")
        icon.name: "ic_fluent_local_language_20_regular"

        /*! 语言名单：code 落 ``app.language`` 配置（zh_CN / en_US / ja_JP），
            name 用**各自语言的母语名**显示（「界面语言」这一项本身该让
            看不懂当前语言的人也认得，惯例同 Windows / VS Code）。
            name 不参与存储与匹配，改显示名不用动配置。 */
        readonly property var languages: [
            { code: "zh_CN", name: "简体中文" },
            { code: "en_US", name: "English" },
            { code: "ja_JP", name: "日本語" }
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
}
