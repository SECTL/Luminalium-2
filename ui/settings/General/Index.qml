import QtQuick
import QtQuick.Layouts
import RinUI as Rin
import Luminalium

/*!
    通用：快捷面板开关与界面语言。

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
*/
Rin.FluentPage {
    id: page

    title: qsTr("通用")
    contentSpacing: 10

    Rin.Text {
        Layout.fillWidth: true
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
