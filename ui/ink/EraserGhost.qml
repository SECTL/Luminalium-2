import QtQuick

/*!
    橡皮幻影 —— 按下橡皮期间跟着触点走的「模拟橡皮擦」。

    2026-10-09 初版（用户指令：「点下去就有一个模拟橡皮擦的 UI 出现」，
    希沃白板同款，白方块 + 橡皮图标）；同日用户指令改版：「橡皮擦好丑，
    仿照图里的样式，把中间的图案换成软件的 logo」—— 形态换成参考图的
    **竖版圆角灰块 + 中央软件 logo 剪影**：

    * 竖版（宽:高 ≈ 4:5，橡皮的实物比例），深灰体 #434347：幻影浮在
      **任意幻灯片 / 板色**之上，深灰在亮暗底上都立得住，也比白块更像
      一块橡皮本体。
    * 描边用固定的白 12% hairline 而不是 ``Lumi.hairline``：浅色档的
      hairline 是黑 8%，压在深灰体上等于没有（小黑板悬浮件描边同款反向坑，
      见 BlackboardWindow.qml 头注释保留契约）。
    * logo 用 ``resources/logo_grayscale.svg``（带 alpha 的灰度剪影版，
      GlassLogo 同款素材；彩色 logo.svg 的渐变圆底压在灰块上会糊），经
      ``Backend.resourceFile`` 取绝对 file URL（QML ``Image`` 的相对路径
      基准是 QML 文件目录，见 bridge.py 该槽的注释）。无 Backend 的预览
      宿主给空串 —— 只少 logo，不炸。
    * 2026-10-28 低档位视觉比例化（Plan P2-6）：尺寸下限从 32 降到 12 —— 原来
      Math.max(32, size) 会把 10px 最低档的擦除面放大成 32px 灰块，用户以为擦
      那么大、实际只擦 10。中央 logo 按块体比例缩放（62% 不变，2 倍 sourceSize
      光栅化，无放大伪影）。
    * 2026-10-31 几何一致性修复（擦除圆内接，对齐 Python 版 fact 510）：此前块体是
      width × (width×1.25) 的**竖矩形**，而真实擦除区域是直径 = eraserGhostSize
      的**圆**——块的上/下整条横带与四角落在圆外，「看得见却擦不掉」（Python 侧
      蒙卡量化：死区占显示面 33–54%，12px 下限在小档把比例推到 54%）。违反下方
      「视觉诚实」。现把块改为**内接于擦除圆的 4:5 竖矩形**（对角线 = D，宽≈0.625D、
      高≈0.781D，四角恰在圆上），并去掉 Math.max(12,…) 下限（下限会重新把小档显示
      块顶出擦除圆）。几何量化：死区面积归零 → 严格 display⊆erase，「显示范围内
      批注均可消失」。取舍：块比旧版视觉偏小（面积约 0.39×），且擦除圆略超出块边
      ——方向正确：宁可擦得比画得多，不可画得比擦得多。中央 logo 仍按块宽 62% 缩放。
    * 2026-10-10 鼠标/触控适配（用户指令）：鼠标模式下选橡皮擦后在画布移动
      始终显示橡皮擦（除胶囊区域外），松开按键亦不隐藏；触控模式下只有按下去
      时才显示。EraserGhost 渲染逻辑不变，依旧纯绑定 inkLayer.eraserGhost* 属性。

    状态来源与尺寸语义见 ``app/ink/layer.py`` 头注释 2026-10-09 条目，
    层本身不画这个 UI。用法：在 InkLayer 的**同一个坐标系**里挂一份
    （通常与层同级、铺满层），把 ``inkLayer`` 指到 InkLayer 实例即可。
    幻影位置 = 触点居中。
*/
Item {
    id: ghost

    /*! InkLayer 实例（宿主填入）。⚠️ 不能叫 ``layer`` ——
        QQuickItem 的 ``layer.*`` 是 FINAL 属性组，同名直接编译失败。 */
    property Item inkLayer: null

    // 真实擦除圆直径 D = 本笔橡皮宽度（layer.eraserGhostSize）。三条擦除路径
    // （整笔命中 hitTest、像素擦除烘焙盖圆盘、掌擦）的实际擦除区域都是
    // 直径 = D 的圆（radiusOf=width/2，RoundCap 盖圆盘），见 app/ink/{model,tessellate}.py。
    readonly property real eraseDiameter: inkLayer ? inkLayer.eraserGhostSize : 0

    // 幻影显示块 = 内接于擦除圆的 4:5 竖矩形：对角线 = D，宽高按 hypot(4,5)
    // 等比缩放 → width≈0.625D、height≈0.781D，四角恰落在圆上。这样严格保证
    // 「显示块 ⊆ 擦除圆」—— 幻影里见到的任何批注都在真实擦除面内、必被擦掉。
    // ⚠️ 刻意不加 Math.max(12,…) 下限：下限会把小档(如 10px)的显示块放大到
    // 超出真实擦除圆，正是旧版「看得见擦不掉」死区根因（Python fact 510 蒙卡量化：
    // 旧竖块死区占显示面 33–54%，本内接方案归零）。
    readonly property real blockW: eraseDiameter * 4 / Math.hypot(4, 5)
    readonly property real blockH: eraseDiameter * 5 / Math.hypot(4, 5)

    visible: inkLayer !== null && inkLayer.eraserGhostVisible

    // 幻影只是视觉反馈，绝不拦截输入 —— 笔画事件要原样落到 InkLayer
    enabled: false

    // ⚠️ 根是铺满宿主的容器（宿主 ``anchors.fill: parent`` 挂它），定位与
    // 尺寸全在视觉块自己身上 —— 宿主给的 anchors 会把根项的 width/height/x/y
    // 整个顶掉，把「触点居中」写在根上就是一块铺满全屏的灰板（2026-10-09
    // 离屏渲染实测抓到）
    Rectangle {
        // ⚠️ 用精确小数、刻意不 Math.round：向上取整会让高/宽略增、四角顶到
        // 擦除圆外，破坏「显示块 ⊆ 擦除圆」的内接不变量（幻影半透明，亚像素
        // 边缘无妨）。圆角进一步内切、只会让块更小于圆，不会外溢。
        width: ghost.blockW
        height: ghost.blockH
        x: ghost.inkLayer ? ghost.inkLayer.eraserGhostX - width / 2 : 0
        y: ghost.inkLayer ? ghost.inkLayer.eraserGhostY - height / 2 : 0
        radius: Math.min(12, width / 4)
        color: "#434347"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.12)

        Image {
            anchors.centerIn: parent
            width: Math.round(parent.width * 0.62)
            height: width  // logo 是正方形 viewBox
            source: typeof Backend !== "undefined"
                    ? Backend.resourceFile("logo_grayscale.svg") : ""
            // SVG 按 2 倍尺寸光栅化，高分屏不糊
            sourceSize.width: width * 2
            sourceSize.height: height * 2
            fillMode: Image.PreserveAspectFit
            smooth: true
        }
    }
}

