"""开发用：更新页（``ui/settings/Update.qml``）的结构与状态机探针。

``.venv\\Scripts\\python.exe tools\\update_probe.py``

离屏创建更新页，逐项断言版式与行为（当前模型不看截图，这是验收依据）：

* 初始态：状态大字「尚未检查更新。」、副行「上次检查更新时间」、
  按钮组可见、进度区隐藏、错误/占位 InfoBar 隐藏；
* 部署占位条：置 ``deployNotice`` 后可见且**不塌陷**（包装层高度 > 0 ——
  RinUI InfoBar 的关闭行为不可控，这里验的是自包装的布局代价）；
* 真检查一轮：点「检查更新」同款入口（``Backend.requestCheckUpdate``）→
  ``checking`` 档进度区出现、按钮组整组禁用（ClassIsland 的 WrapPanel
  IsEnabled 钉 Idle）→ 结束后回 ``idle``，结论落进
  {uptodate / available / error} 之一，时间戳写进配置（写到**临时**
  用户配置，不碰真 ``config/config.json``）；
* Tab 切换：``SelectorBar`` 切到「更新设置」后两张 Expander 与
  「强制检查更新」入口可见；
* 「有更新」一整档：GitHub 在沙箱里未必可达，用打桩的发布列表验
  available 档的按钮 / 副行 / 状态大字 / 日志视图；
* 大图回归（2026-10-06 用户指令）：打桩日志里插一张 1920×1080 的截图，
  日志视图的 ``contentWidth`` 不得超出自身宽度 —— ``MarkdownText`` 下图片
  按原始像素铺设，会把整页撑破、把兄弟项顶出可视区。

环境变量：``LUMI_UPDATE_PROBE_THEME=light`` —— 换浅色主题跑全套（截图文件名
随之带 ``_light`` / ``_dark`` 后缀）。

截图存 ``preview/update_probe_*.png``（各状态）与 ``preview/probe_update_*.png``
（整页）供人工目检。

⚠️⚠️ **截图里「更新设置」Tab 的卡片是白底 —— 那是本探针宿主的假象，不是缺陷。**
本脚本用一个 Python 侧 ``QQmlComponent`` 另建的 ``Rin.Window`` 当宿主，
而按项目铁律 10，RinUI 的窗口外观（ mica/acrylic 底、圆角、阴影）只在
``launcher.load()`` 那一刻登记一次 —— 另建的窗口没登记，底下就没有深色
底板，页面于是透出白（实测本探针那张整页图**alpha 全为 0**，白底还是我读图
时叠上去的）。对照实验：同一宿主里加载 ``About.qml``，它那张卡的中心像素
**同样是 ``#FFFFFF``**，而 ``preview/page_About_dark.png`` 里明明是深色卡片
—— 可见与 Update 页无关。

所以**判据是本脚本的断言，不是这些截图**；真要目检深色下的更新页，看
``preview/page_Update_dark.png``（由 ``preview.py`` 出图，宿主是登记过的）。
调色 / 圆角 / 阴影一类外观问题一律别用本探针的图下结论。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QUrl, QTimer  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RinConfig  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402

HOST_QML = """
import QtQuick
import RinUI as Rin

Rin.Window {
    id: host
    property url pageUrl: ""
    width: 961
    height: 940
    titleBarHeight: 0
    titleEnabled: false
    closeVisible: false
    minimizeVisible: false
    maximizeVisible: false
    flags: Qt.Tool | Qt.FramelessWindowHint

    Loader {
        anchors.fill: parent
        anchors.margins: 16
        source: host.pageUrl
    }
}
"""

OFFSCREEN = -6000
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "[OK]" if ok else "[FAIL]"
    print(f"{mark} {name}" + (f" —— {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def find_by_name(item, name: str):
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = find_by_name(child, name)
        if found is not None:
            return found
    return None


def walk(item, out: list | None = None):
    """整棵子树（``childItems()`` 递归）。左栏可见性那种回归要按树找。"""
    out = [] if out is None else out
    out.append(item)
    for child in item.childItems():
        walk(child, out)
    return out


def left_column_ready(item) -> bool:
    """``SettingItem`` 装标题 / 描述的那层是否**可见、有宽度、文字真的会画出来**。

    ⚠️ 三个判据缺一不可（2026-10-05 全部踩过）：

    * 只看外层 RowLayout 的 ``visible`` —— **假阳性**。QML 的 ``Item.visible``
      是**有效可见性**，而 RinUI 写的是 ``visible: titleLabel.visible ||
      descriptionLabel.visible``（读后代的有效可见性）→ 落在自家子树里成环。
      环锁死时内层 ``Text`` 全是 ``visible=false``，外层 RowLayout 却可能仍是
      ``true``；此时图上就是「有高度、没字」，断言却全绿。
    * 不看宽度 —— 左栏宽度被协商成 0 时 ``visible`` 仍是 true，同样是一行空白。
    * 认错对象 —— ``SettingItem`` 里有好几个 ``QQuickRowLayout``（左栏、右侧
      弹性占位、右栏），认错就得跟渲染无关的结论。

    所以：**必须逐个检查真正带文字的那些 ``Text`` 自己的 ``visible``**。
    """
    if item is None:
        return False
    for node in walk(item):
        if node.metaObject().className() != "QQuickRowLayout":
            continue
        if not bool(node.property("visible")):
            continue
        for sub in walk(node):
            if not sub.metaObject().className().startswith("Text_"):
                continue
            if not str(sub.property("text") or "").strip():
                continue
            # ⚠️ 这一行是 2026-10-05 补上的：文字节点自己不可见 = 不会画出来，
            # 外层可见也没用。
            if not bool(sub.property("visible")):
                continue
            return float(node.property("width") or 0) > 50
    return False


def pump(app, ms: float) -> None:
    """GIL 友好的事件泵（见 tools/scroll_probe.py 同款；qWait 会饿死线程）。"""
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.005)


def grab(window, app, path: Path) -> None:
    window.grabWindow()
    app.processEvents()
    window.grabWindow().save(str(path))


def main() -> int:
    # ============================================ 0. 通道过滤（纯逻辑，无需窗口）
    # ⚠️ 这一段钉的是用户口径：**稳定版 = 只接受 Release，预览版 =
    # Release + Prerelease**，两边都排 draft（draft 还没发出去）。
    # 界面上「稳定版 / 预览版」那两个字眼谁都能改，这里不能。
    from app import update_checker as _uc

    _fake = [
        {"tag_name": "v27.1.0.5", "prerelease": True, "draft": False},
        {"tag_name": "v27.0.900.0", "prerelease": False, "draft": False},
        {"tag_name": "v26.0.707.1", "prerelease": False, "draft": True},
    ]
    _got = {
        ch: [r["tag_name"] for r in _fake if _uc._release_matches_channel(r, ch)]
        for ch in ("stable", "preview")
    }
    check("通道 stable 只收 Release", _got["stable"] == ["v27.0.900.0"], str(_got["stable"]))
    check("通道 preview 收 Release + Prerelease",
          _got["preview"] == ["v27.1.0.5", "v27.0.900.0"], str(_got["preview"]))
    check("版本号可比较", _uc.parse_version("v26.0.707.1") == (26, 0, 707, 1))
    check("非版本号 tag 判为不可比", _uc.parse_version("nightly") is None)
    check("通道表与下拉显示名同源",
          set(_uc.CHANNELS) == set(_uc.CHANNEL_NAMES),
          f"{sorted(_uc.CHANNELS)} vs {sorted(_uc.CHANNEL_NAMES)}")

    # 检查会写 update.last_* —— 用临时用户配置承接，不污染真 config.json。
    tmp_config = Path(tempfile.gettempdir()) / "lumi_update_probe_config.json"
    tmp_config.write_text("{}", encoding="utf-8")
    config = Config(user_file=str(tmp_config))

    # 真配置的运行前快照（末尾比对「本次探针有没有动它」）。
    _real = ROOT / "config" / "config.json"
    real_config_before = (_real.read_text(encoding="utf-8")
                          if _real.exists() else "")
    real_config_mtime = _real.stat().st_mtime_ns if _real.exists() else 0

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, app)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    theme = os.environ.get("LUMI_UPDATE_PROBE_THEME", "dark").lower()
    # ⚠️ ``setTheme``会**持久化到 RinUI/config/rin_ui.json**（真机下次启动读
    # 那份）。跑完必须还原 —— 实测跑完一轮浅色探针，配置里``current_theme``
    # 就留下了 ``"Light"``，接着跑页面预览会把「还原」当成Light 还原，
    # 深浅两套图的主题就此串味。记下原值、收尾时切回去。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Light if theme.startswith("l") else Theme.Dark)
    theme_tag = "light" if theme.startswith("l") else "dark"
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(UI_DIR / "QuickPanel.qml")
    panel = rinui.root_window
    panel.setPosition(OFFSCREEN, OFFSCREEN)
    panel.show()

    host_path = ROOT / "preview" / "_update_probe_host.qml"
    host_path.write_text(HOST_QML, encoding="utf-8")
    component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(host_path)))
    if component.isError():
        for error in component.errors():
            print("HOST ERROR:", error.toString())
        return 1
    window = component.createWithInitialProperties({
        "pageUrl": QUrl.fromLocalFile(str(UI_DIR / "settings" / "Update.qml")),
        "visible": True,
    })
    if window is None:
        print("WINDOW CREATE ERROR")
        return 1
    window._host_component = component
    window.setPosition(OFFSCREEN - 900, OFFSCREEN - 1800)
    window.show()
    pump(app, 600)

    root_item = window.contentItem()
    assert root_item is not None

    # ==================================================== A. 初始态
    status_text = find_by_name(root_item, "updateStatusText")
    check("状态大字存在", status_text is not None)
    if status_text is not None:
        check("初始状态文字", str(status_text.property("text")) == "尚未检查更新。",
              str(status_text.property("text")))
    sub_text = find_by_name(root_item, "updateStatusSubText")
    if sub_text is not None:
        check("副行显示上次检查时间",
              "上次检查更新时间" in str(sub_text.property("text")),
              str(sub_text.property("text")))
    check_button = find_by_name(root_item, "updateCheckButton")
    check("「检查更新」按钮可见", bool(check_button.property("visible")))
    progress_row = find_by_name(root_item, "updateProgressRow")
    check("进度区初始隐藏",
          progress_row is not None and not progress_row.property("visible"))
    error_bar = find_by_name(root_item, "updateErrorBar")
    check("错误条初始隐藏", error_bar is not None and not error_bar.property("visible"))
    stub_bar = find_by_name(root_item, "updateDeployStubBar")
    check("部署占位条初始隐藏", stub_bar is not None and not stub_bar.property("visible"))
    check("图标初始不旋转",
          float(find_by_name(root_item, "updateStatusIcon").property("rotation")) == 0.0)

    # ⚠️ 回归钉：页头「图标右缘 → 状态文字左缘」的**净间隙**。
    # 2026-10-05 踩过两次，所以这里量的是**两者之间**，不是各自的绝对位置：
    #   ① 早期写成 ``Item { implicitHeight: row.implicitHeight; RowLayout { anchors.fill } }``
    #      —— 环比循环让布局拿到不完整几何，``Layout.fillWidth`` 不生效、剩余空间
    #      被按隐式宽**按比例**分掉，图标与文字之间空出 ~86px；
    #   ② 修好①之后按原版的 ``Margin="0 0 4 0"`` 用了 4px，用户反馈**贴太近**，
    #      改成 12。
    # 光看「图标在、文字在」两种错法都发现不了。
    _icon = find_by_name(root_item, "updateStatusIcon")
    _text = find_by_name(root_item, "updateStatusText")
    _header = find_by_name(root_item, "updateStatusHeader")
    if _icon is not None and _text is not None:
        _icon_right = (float(_icon.mapToItem(root_item, 0, 0).x())
                       + float(_icon.property("width")))
        _text_left = float(_text.mapToItem(root_item, 0, 0).x())
        _gap = _text_left - _icon_right
        check("页头图标↔状态文字间距 = 12px", 8.0 <= _gap <= 20.0,
              f"净间隙 {_gap:.1f}px")

    # ⚠️ 回归钉：按钮组**贴右**（用户 2026-10-05：右侧空着，把「检查更新」挪过来）。
    # 判据是「按钮组右缘 ≈ 页头内容区右缘」，不是「x 很大」—— 后者在窄窗口下
    # 会假通过。
    _btns = find_by_name(root_item, "updateButtonRow")
    if _header is not None and _btns is not None and bool(_btns.property("visible")):
        _hdr_right = (float(_header.mapToItem(root_item, 0, 0).x())
                      + float(_header.property("width")))
        _btn_right = (float(_btns.mapToItem(root_item, 0, 0).x())
                      + float(_btns.property("width")))
        _off = abs(_hdr_right - _btn_right)
        check("按钮组贴齐页头右缘", _off <= 2.0,
              f"右缘差 {_off:.1f}px（页头 {_hdr_right:.0f} / 按钮 {_btn_right:.0f}）")

    # ⚠️ 回归钉：状态区下沿 → 分隔线 的间距。
    # 原版这一段夹着**一整行按钮**（6 + 40 + 6 = 52）；按钮挪到页头右侧后只剩
    # 页面统一的 6px，目检「分割线直接贴上去了」（用户 2026-10-05 指出）。
    # 现在补到 24。别让它退回 6。
    _sep = find_by_name(root_item, "updateSeparator")
    if _header is not None and _sep is not None:
        _hdr_bottom = (float(_header.mapToItem(root_item, 0, 0).y())
                       + float(_header.property("height")))
        _sep_top = float(_sep.mapToItem(root_item, 0, 0).y())
        _v_gap = _sep_top - _hdr_bottom
        # 初始态两条 InfoBar 都是隐藏的，所以这段就是纯粹的留白
        check("状态区↔分隔线留出呼吸(≈24px)", 18.0 <= _v_gap <= 34.0,
              f"净间隙 {_v_gap:.1f}px")
    # ⚠️ 图存``probe_update_*.png``，**不写** ``preview/page_Update_*.png``：
    # 那个名字是 ``preview.py`` 的地盘，而 preview.py 的宿主是登记过的（铁律 10）、
    # 抓得到实色底板。本探针的宿主按铁律 10 刻意不登记 → 没有 mica，页面透出白
    # （对照实验：同一宿主加载 About.qml，卡片中心同样 ``#FFFFFF``）。
    # 两者曾用同一个文件名，探针一跑就把 preview.py 的可信图覆盖成白底版 ——
    # 现在分开，看配色一律回 ``preview/page_Update_*.png``。
    grab(window, app, ROOT / "preview" / f"probe_update_{theme_tag}.png")

    # 初始态就顺手验空状态居中：原版是「占满宽度、里面居中」
    # （VerticalAlignment/HorizontalAlignment=Center）。踩过的坑是拿
    # 「自身不填宽 + Layout.alignment: AlignHCenter」当居中 —— 那样整块
    # 会贴到左边，右边空一大片，图上很明显。
    #
    # ⚠️ 空状态那张图从 ``Rin.Icon``（字体图标，类名以 ``Icon_`` 开头）换成了
    # ``Image``（位图贴图 ``resources/up_to_date.png``）—— 找节点的判据要跟着改，
    # 否则 ``icon is None`` 会让整段**静默跳过**、断言不报错也不生效。
    up_panel = find_by_name(root_item, "updateUpToDatePanel")
    if up_panel is not None:
        pw = float(up_panel.property("width") or 0)
        art = find_by_name(up_panel, "updateUpToDateImage")
        if art is None:                      # 兼容旧版：字体图标那档
            for node in walk(up_panel):
                if node.metaObject().className().startswith("Icon_"):
                    art = node
                    break
        if art is not None:
            ix = float(art.mapToItem(up_panel, 0, 0).x())
            iw = float(art.property("width") or 0)
            # 图的水平中心应落在面板中心附近（容差 8px）
            off = abs((ix + iw / 2) - pw / 2)
            check("空状态贴图水平居中", off <= 8,
                  f"面板宽 {pw:.0f}，贴图中心 {ix + iw / 2:.0f}，偏移 {off:.0f}")
            check("空状态贴图 81×81",
                  abs(iw - 81) <= 1 and abs(float(art.property("height") or 0) - 81) <= 1,
                  f"{iw:.0f}×{float(art.property('height') or 0):.0f}")
            check("空状态面板占满宽度", pw > 400, f"width={pw:.0f}")

    # ==================================================== B. 部署占位条
    def find_page_with_property(item, prop: str):
        """页面根没有 objectName（Loader 塞进宿主的），按「谁有这个属性」找。"""
        if item.property(prop) is not None:
            return item
        for child in item.childItems():
            found = find_page_with_property(child, prop)
            if found is not None:
                return found
        return None

    page = find_page_with_property(root_item, "deployNotice")
    check("找到更新页根节点", page is not None)
    if page is None:
        print("失败: 找不到更新页根节点")
        return 1
    page.setProperty("deployNotice", True)
    pump(app, 150)
    check("占位条置 deployNotice 后可见", bool(stub_bar.property("visible")))
    check("占位条高度不塌陷", float(stub_bar.property("height")) > 20,
          f"height={float(stub_bar.property('height')):.0f}")
    grab(window, app, ROOT / "preview" / "update_probe_deploy_notice.png")
    page.setProperty("deployNotice", False)
    pump(app, 100)

    # ==================================================== C. 真检查一轮
    backend.requestCheckUpdate(False)
    pump(app, 400)
    check("检查中 working=checking", str(backend.property("updateWorkingStatus")) == "checking")
    check("检查中进度区出现", bool(progress_row.property("visible")))
    button_row = find_by_name(root_item, "updateButtonRow")
    check("检查中按钮组禁用", button_row is not None and not button_row.property("enabled"))
    check("检查中图标在转", float(
        find_by_name(root_item, "updateStatusIcon").property("rotation")) > 0.0)
    grab(window, app, ROOT / "preview" / "update_probe_checking.png")

    deadline = time.perf_counter() + 25.0
    while time.perf_counter() < deadline and str(
            backend.property("updateWorkingStatus")) == "checking":
        pump(app, 50)
    # ⚠️ 循环条件读的是 Python 侧属性（emit 前就置 idle 了）；queued 信号可能
    # 还没送达主线程，QML 绑定仍是旧值 —— 补一帧再读界面状态。
    pump(app, 300)
    final_status = str(backend.property("updateStatus"))
    check("检查结束回 idle", str(backend.property("updateWorkingStatus")) == "idle")
    check("结论落在预期集合内",
          final_status in ("uptodate", "available", "error"), final_status)
    check("进度区收起", not progress_row.property("visible"))
    check("图标停下（360° ≡ 0°）", float(
        find_by_name(root_item, "updateStatusIcon").property("rotation")) % 360 == 0.0)
    check("上次检查时间已写入",
          str(backend.property("updateLastCheckTime")) != "",
          str(backend.property("updateLastCheckTime")))
    if final_status == "error":
        check("失败时错误条出现", bool(error_bar.property("visible")))
        check("错误条高度不塌陷", float(error_bar.property("height")) > 20,
              f"height={float(error_bar.property('height')):.0f}")
    check("检查记录只进临时配置", tmp_config.stat().st_size > 2,
          f"{tmp_config.stat().st_size}B")
    # ⚠️ 别断言「真配置里没有 last_check_time」—— 那是**历史遗留**：真机上跑过
    # 一次应用就会留下这个键，断言会永远 FAIL。正解是比对**运行前后**内容
    # 是否被本进程改动。
    real_config = ROOT / "config" / "config.json"
    if real_config.exists():
        check("真配置未被本次探针改动",
              real_config.read_text(encoding="utf-8") == real_config_before,
              f"{real_config.stat().st_mtime_ns} vs {real_config_mtime}")
    grab(window, app, ROOT / "preview" / "update_probe_after_check.png")

    # ==================================================== D. Tab 切换
    tabs = find_by_name(root_item, "updateTabs")
    tabs.setProperty("currentIndex", 1)
    # ⚠️ 更新设置 Tab 现在是 ``Loader``（active 才构造，见 Update.qml 注释），
    # 轮询等到子项真的落地再断言 —— RinUI 那几层布局要先跑一轮才有尺寸。
    # 别用固定 qWait：Loader 异步只是第一步，里面 RinUI 那几层 RowLayout /
    # Column 还要再协商一两轮宽度。**左栏拿到宽度**才算版式定稿 —— 早一帧
    # 抓就是「有高度、没字」的中间态（这坑踩过一次，图上两行空白而断言全绿）。
    settings_tab = find_by_name(root_item, "updateSettingsTab")
    deadline = time.perf_counter() + 10.0
    settled = False
    while time.perf_counter() < deadline:
        pump(app, 80)
        item = settings_tab.property("item") if settings_tab else None
        if item is None:
            continue
        if (left_column_ready(find_by_name(root_item, "updateChannelDescItem"))
                and left_column_ready(find_by_name(root_item,
                                                   "updateForceCheckItem"))):
            settled = True
            break
    pump(app, 250)
    check("更新设置 Tab 已加载",
          settings_tab is not None and settings_tab.property("item") is not None)
    check("更新设置 Tab 版式已收敛（截图前）", settled)
    # ⚠️ 通道表**只允许**有一份（Python 的 CHANNELS/CHANNEL_NAMES）。原先
    # QML 里也抄了一份字面量，两边文案迟早漂；再抄回来时钉死它。
    ch_prop = backend.property("updateChannels")
    check("Backend 发出通道表", ch_prop is not None and len(ch_prop) == 2,
          str(ch_prop))
    if ch_prop:
        ids = {c.get("id") for c in ch_prop}
        check("通道 id 与 Python 侧一致", ids == set(_uc.CHANNELS), str(sorted(ids)))
        names = {c.get("name") for c in ch_prop}
        check("通道显示名非空", all(str(n).strip() for n in names), str(sorted(names)))
    mode_expander = find_by_name(root_item, "updateModeExpander")
    channel_expander = find_by_name(root_item, "updateChannelExpander")
    force_item = find_by_name(root_item, "updateForceCheckItem")
    check("更新模式 Expander 可见",
          mode_expander is not None and bool(mode_expander.property("visible")))
    check("更新通道 Expander 可见",
          channel_expander is not None and bool(channel_expander.property("visible")))
    check("强制检查更新入口存在",
          force_item is not None and bool(force_item.property("visible")))

    # ⚠️ 回归钉：SettingItem 的左栏可见性是个绑定，只在**构造期**求值一次。
    # 之前整段 Tab 靠 visible 切换（初始 false）→ 左栏拿到空 title 判成
    # 「无内容」整层隐藏，文字传对了也不画。改 Loader 后构造期就是最终值，
    # 这里逐个验「左栏可见 + 有宽度」+「文字非空」，别等看图才发现又白了。
    #
    # ⚠️ 两个条目的文案位置**不一样**，别按同一个模子验：
    #   * ``updateChannelDescItem`` —— 对齐原型后**只有正文、没有标题**
    #     （ClassIsland 那个 ``SettingsExpanderItem`` 里就一个 TextBlock），
    #     文案落在 ``title``（正文号；``description`` 是小一号的 Caption）。
    #   * ``updateForceCheckItem`` —— 原版是 ``Content`` + ``Description``，
    #     所以 title 和 description 都非空。
    desc_item = find_by_name(root_item, "updateChannelDescItem")
    for label, item in (("通道说明行", desc_item), ("强制检查更新", force_item)):
        if item is None:
            check(f"{label} 存在", False)
            continue
        title = str(item.property("title") or "")
        desc = str(item.property("description") or "")
        check(f"{label} 文案非空", (title + desc).strip() != "",
              (title or desc)[:24])
        check(f"{label} 左栏可见且有宽度", left_column_ready(item))
    # 说明行只留描述、不多写通道名 —— 顺带钉住「文案与 Python 侧同源」
    if desc_item is not None:
        settings_map = backend.property("settings") or {}
        current_id = str(settings_map.get("update_channel") or "stable")
        # 与 QML 侧的 ``currentChannelId`` 同一个兜底：值不在候选表里就用第一档
        if current_id not in _uc.CHANNELS:
            current_id = next(iter(_uc.CHANNELS), "stable")
        expected = _uc.CHANNELS.get(current_id, "")
        actual = str(desc_item.property("title") or "")
        check("通道说明行＝当前通道的描述（无多余标题行）",
              actual == expected, f"{actual!r} vs {expected!r}")
        check("通道说明行不带描述副行（原版只有一个 TextBlock）",
              str(desc_item.property("description") or "") == "",
              repr(str(desc_item.property("description") or "")))
    grab(window, app, ROOT / "preview" / "update_probe_settings_tab.png")

    # ==================================================== E. 「有更新」一整档
    # 沙箱 / 内网里 GitHub 未必可达（真检查可能落 error），「available」这档
    # 的界面用**打桩的发布列表**验：比当前版本新的假发布 → 按钮、副行、
    # 状态大字、日志视图全部跟进。
    from app import update_checker as update_checker_mod

    # 大图回归用的一张 1920×1080「发布截图」（本地文件，不联网也能验）。
    # 绿底 + 左上角一块橙，几何之外还能按颜色确认它真的画出来了。
    big_shot = ROOT / "preview" / "update_probe_bigimg.png"
    try:
        from PySide6.QtGui import QImage, QPainter, QColor
        _big = QImage(1920, 1080, QImage.Format_RGB32)
        _big.fill(QColor("#1a6b3c"))
        _painter = QPainter(_big)
        _painter.fillRect(0, 0, 600, 300, QColor("#e0a020"))
        _painter.end()
        _big.save(str(big_shot))
    except Exception as exc:  # noqa: BLE001 - 造不出图也要跑完其余断言
        print(f"[WARN] 大图素材生成失败，跳过尺寸断言: {exc}")
        big_shot = None

    fake_releases = [{
        "tag_name": "27.1.808.1",
        "prerelease": False,
        "draft": False,
        # ⚠️ **必须带 ``file:///`` 前缀**：写成 ``G:/xxx`` 的话 Qt 会把 ``G:``
        # 当成 URL 协议名、转去走网络请求，实测整个探针卡死在那里（十几分钟
        # 不返回，也不报错）。本地路径统一走 file 协议。
        "body": "## 新增\n- 测试日志条目\n\n## 截图\n![预览截图](file:///"
                + (big_shot.as_posix() if big_shot else "") + ")\n",
        "html_url": "https://github.com/SECTL/Luminalium-2/releases/tag/27.1.808.1",
    }]
    original_fetch = update_checker_mod._fetch_releases
    update_checker_mod._fetch_releases = lambda: fake_releases
    try:
        backend.requestCheckUpdate(False)
        deadline = time.perf_counter() + 10.0
        while time.perf_counter() < deadline and str(
                backend.property("updateWorkingStatus")) == "checking":
            pump(app, 50)
        pump(app, 300)
        check("打桩检查结论 available",
              str(backend.property("updateStatus")) == "available",
              str(backend.property("updateStatus")))
        check("状态大字改为检测到更新",
              str(status_text.property("text")) == "检测到更新。",
              str(status_text.property("text")))
        check("副行显示新版本号",
              "27.1.808.1" in str(sub_text.property("text")),
              str(sub_text.property("text")))
        download_button = find_by_name(root_item, "updateDownloadButton")
        check("「下载更新」出现",
              download_button is not None and bool(download_button.property("visible")))
        check("「下载更新」文案对齐原版",
              str(download_button.property("text") or "") == "下载更新",
              str(download_button.property("text") or ""))
        # 「有更新」是**唯一会出现两枚按钮**的档，最容易撑破右缘 —— 量一下：
        # 按钮组右缘不能越过页头内容区右缘。
        _avail_row = find_by_name(root_item, "updateButtonRow")
        _avail_hdr = find_by_name(root_item, "updateStatusHeader")
        if _avail_row is not None and _avail_hdr is not None:
            _row_right = (float(_avail_row.mapToItem(root_item, 0, 0).x())
                          + float(_avail_row.property("width")))
            _hdr_right = (float(_avail_hdr.mapToItem(root_item, 0, 0).x())
                          + float(_avail_hdr.property("width")))
            check("两枚按钮不撑破右缘", _row_right <= _hdr_right + 2.0,
                  f"按钮组右缘 {_row_right:.0f} / 页头右缘 {_hdr_right:.0f}")
            # 文字列不能被按钮挤到没宽度
            _col = find_by_name(root_item, "updateStatusColumn")
            if _col is not None:
                check("文字列仍有宽度", float(_col.property("width")) > 200,
                      f"width={float(_col.property('width')):.0f}")
        changelog_view = find_by_name(root_item, "updateChangelogView")
        tabs.setProperty("currentIndex", 0)
        pump(app, 200)
        check("更新日志视图出现",
              changelog_view is not None and bool(changelog_view.property("visible")))
        check("日志内容来自发布说明",
              "测试日志条目" in str(changelog_view.property("text")))
        # ---- 大图回归（2026-10-06 用户指令「大分辨率图片会把元素挡住」）----
        # 日志走 RichText + ``<img max-width:100%>``：图片按**列宽**缩放，
        # 不再按原始像素铺进文本流。
        # ⚠️ 只断言 contentWidth 会**假阳性** —— 图没加载出来时同样不超宽，
        # 所以必须再验一句「图确实画出来了」（内容高度远大于纯文字那几行）。
        _log_text = str(changelog_view.property("text"))
        _has_cap = "max-width:100%" in _log_text
        # detail 只在失败时给（check 无论成败都打印，成功行拖一句说明像报错）
        check("图片带宽度上限（max-width 已注入）", _has_cap,
              "" if _has_cap else _log_text[:120])
        _log_w = float(changelog_view.property("width"))
        _log_cw = float(changelog_view.property("contentWidth"))
        check("大图不撑破日志列", _log_cw <= _log_w + 2.0,
              f"contentWidth={_log_cw:.0f} / 列宽={_log_w:.0f}")
        if big_shot is not None:
            _log_ch = float(changelog_view.property("contentHeight"))
            check("大图确实画出来了（高度远大于纯文字）", _log_ch > 200.0,
                  f"contentHeight={_log_ch:.0f}")
        check("空状态面板隐藏",
              not find_by_name(root_item, "updateUpToDatePanel").property("visible"))
        grab(window, app, ROOT / "preview" / "update_probe_available.png")
    finally:
        update_checker_mod._fetch_releases = original_fetch

    # ==================================================== 汇总
    print()
    # 还原主题（见 main() 里 setTheme 那处的注释）。
    #
    # ⚠️⚠️ 必须在**退出前**显式落盘：``toggle_theme`` 只改内存里的
    # ``RinConfig``，真正写文件的是 ``theme_manager.clean_up()``（进程退出时
    # 才跑）。只调toggle 的话屏幕上会打印「主题已还原为 Auto」而文件里仍是
    # ``"Light"`` —— 下一轮跑页面预览就会把 Light 当成原值还原，深浅两套图
    # 的主题就此串味。``preview.py`` 的 ``_restore_preview_state`` 同样要落盘。
    if rinui.theme_manager.get_theme_name() != previous_theme:
        rinui.theme_manager.toggle_theme(previous_theme)
        RinConfig.save_config()
        print(f"[OK] 主题已还原并落盘为 {previous_theme}")
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
