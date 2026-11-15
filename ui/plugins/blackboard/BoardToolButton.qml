import QtQuick
import "../../presentation"

/*!
    小黑板胶囊工具栏的工具钮。

    2026-11-01 用户指令：「小黑板的胶囊太丑了，改成和放映界面一样的胶囊，
    文字显示按放映界面的胶囊设置来，就算打开了文字显示也要显示在图标右边」——
    从「36px 图标位 + 下方 11px 标签」（2026-10-17 Lmn-copy 蓝本版式）换成
    **直接复用**放映控制条的 ``presentation/IconButton``：44px 圆钮、22px 图标，
    「显示按钮文本」打开后长成胶囊、文字接在图标右边（形态说明全在
    IconButton.qml 头注释）。复用而不是照抄：放映条那颗圆钮以后再调，黑板
    自动跟上，两边不会再走散。

    旧注「不复用 presentation/IconButton（尺寸取色对不上、插件目录要自足）」
    作废：尺寸对齐正是这次的目的；「自足」约束的是外部插件（整目录拷进数据
    根），黑板是内建插件，跨目录引用的先例见 BlackboardWindow.qml 顶部 D5 注释。

    在 IconButton 缺省值上只改两处：

    * **取色钉死深色档**：图标 / 文字白、悬停白 8%、选中白 15% —— 就是放映条
      在深色主题下 ``Lumi.dockButton*`` 的取值。黑板悬浮件不随主题（理由见
      BlackboardWindow.qml 头注释），浅色档的 textPrimary 是黑系，压在深底上
      等于没有。
    * **禁用态再暗一档**：Rin.Button 的 disabled state 只把整钮降到 0.65，黑板
      的清空 / 撤销 / 重做常年禁用，0.65 和可点的钮几乎分不开；图标与文字再乘
      0.6，合计 ≈ 0.39，接近旧版 38% 的辨识度。⚠️ 0.6 是按 RinUI Button.qml
      disabled state 的 0.65 配的，那个值变了这里跟着重算。

    ``enabled`` 用 Item 内建那份（旧版的同名遮蔽属性随旧实现退役，2026-10-19
    审计 D3 记的那笔遮蔽写法债就此结清）：禁用即不收 hover / 点击，tooltip 也
    不弹。悬停提示缺省就是名字本身 —— 文字关着时它是唯一的名字来源。
*/
IconButton {
    glyphColor: enabled ? "#FFFFFF" : Qt.rgba(1, 1, 1, 0.6)
    labelColor: glyphColor
    hoverFill: Qt.rgba(1, 1, 1, 0.08)
    activeFill: Qt.rgba(1, 1, 1, 0.15)
    tooltip: label
}
