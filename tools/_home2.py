"""开发用：更新页（``ui/settings/Home.qml``）的结构与状态机探针。

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
  available 档的按钮 / 副行 / 状态大字 / 日志视图。

环境变量：``LUMI_UPDATE_PROBE_THEME=light`` —— 换浅色主题跑全套（顺带
刷新 ``preview/page_Update_light.png``；深色跑法同样刷新 ``_dark`` 那张，
宿主与 ``tools/preview.py`` 的单页宿主同规格，替代它 9 分钟的全量渲染）。

截图存 ``preview/update_probe_*.png`` 供人工目检。
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
    # 检查会写 update.last_* —— 用临时用户配置承接，不污染真 config.json。
    tmp_config = Path(tempfile.gettempdir()) / "lumi_update_probe_config.json"
    tmp_config.write_text("{}", encoding="utf-8")
    config = Config(user_file=str(tmp_config))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, app)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    theme = os.environ.get("LUMI_UPDATE_PROBE_THEME", "dark").lower()
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
        "pageUrl": QUrl.fromLocalFile(str(UI_DIR / "settings/Home.qml")),
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
    # 顺手刷新 preview.py 同名规格的整页截图（深/浅按本次主题）。
    grab(window, app, ROOT / "preview" / f"page_Update_{theme_tag}.png")

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
    real_config = ROOT / "config" / "config.json"
    if real_config.exists():
        text = real_config.read_text(encoding="utf-8")
        check("真配置未被探针写入", "last_check_time" not in text)
    grab(window, app, ROOT / "preview" / "update_probe_after_check.png")

    # ==================================================== D. Tab 切换
    tabs = find_by_name(root_item, "updateTabs")
    tabs.setProperty("currentIndex", 1)
    pump(app, 200)
    mode_expander = find_by_name(root_item, "updateModeExpander")
    channel_expander = find_by_name(root_item, "updateChannelExpander")
    force_item = find_by_name(root_item, "updateForceCheckItem")
    check("更新模式 Expander 可见",
          mode_expander is not None and bool(mode_expander.property("visible")))
    check("更新通道 Expander 可见",
          channel_expander is not None and bool(channel_expander.property("visible")))
    check("强制检查更新入口存在",
          force_item is not None and bool(force_item.property("visible")))
    grab(window, app, ROOT / "preview" / "update_probe_settings_tab.png")

    # ==================================================== E. 「有更新」一整档
    # 沙箱 / 内网里 GitHub 未必可达（真检查可能落 error），「available」这档
    # 的界面用**打桩的发布列表**验：比当前版本新的假发布 → 按钮、副行、
    # 状态大字、日志视图全部跟进。
    from app import update_checker as update_checker_mod

    fake_releases = [{
        "tag_name": "27.1.808.1",
        "prerelease": False,
        "draft": False,
        "body": "## 新增\n- 测试日志条目",
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
        check("「下载并安装」出现",
              download_button is not None and bool(download_button.property("visible")))
        changelog_view = find_by_name(root_item, "updateChangelogView")
        tabs.setProperty("currentIndex", 0)
        pump(app, 200)
        check("更新日志视图出现",
              changelog_view is not None and bool(changelog_view.property("visible")))
        check("日志内容来自发布说明",
              "测试日志条目" in str(changelog_view.property("text")))
        check("空状态面板隐藏",
              not find_by_name(root_item, "updateUpToDatePanel").property("visible"))
        grab(window, app, ROOT / "preview" / "update_probe_available.png")
    finally:
        update_checker_mod._fetch_releases = original_fetch

    # ==================================================== 汇总
    print()
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
