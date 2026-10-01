"""开发用：把界面离屏渲染成 PNG，便于快速核对版式。

用法::

    .venv\\Scripts\\python.exe tools\\preview.py

输出到 ``preview/``：

- ``quick_panel.png``      —— 快捷面板
- ``top_window.png``       —— 「顶层窗口」（全屏叠加层）+ 内嵌的下中部工具栏与
  屏幕两侧的竖版翻页 pill（预览里用紧凑尺寸代替真实全屏，版式一致）
- ``settings.png``         —— 设置窗口（主页）
- ``splash.png``           —— 启动画面（版式照设计稿「启动画面 Dark / Light」，外观走
  Fluent 2 令牌；用 ``DESIGN_STAGE`` 把进度钉在设计稿那一档，好跟原稿对照版式）
- ``splash_light.png``     —— 同上，浅色版。用 ``LUMI_PREVIEW_THEME=light`` 跑；
  此时别的窗口一律不截图（否则会把上面那些深色预览图覆盖成浅色的）
- ``debug_window.png``     —— 调试窗口（入口是设置标题连点 10 次，不在导航里）
- ``main_editor.png``      —— 主界面编辑器（入口是快捷面板的「主界面编辑器」
  快捷方式）。正文是**顶层窗口的完整预览舞台**，抓图前会关掉 ``backdropEnabled``
  以退回兜底底色 —— 离屏抓图看不到 DWM 亚克力层，真机效果得靠实机截屏确认
- ``main_editor_edit.png`` —— 上面那个编辑器停在**编辑态**（``LUMI_PREVIEW_EDIT``
  指定聚焦哪条控制条）
- ``page_*.png``           —— 设置窗口里每个页面单独渲染一张（``NavigationView``
  只有在用户点进去时才创建页面，所以这里用临时宿主窗口把它们全跑一遍）

窗口会被放到屏幕外（x = -6000）并强制渲染，因此**不会打扰桌面**。

环境变量：

- ``LUMI_PREVIEW_THEME=light`` —— 换成浅色主题，且**只**输出启动画面。
- ``LUMI_PREVIEW_ONLY=splash`` —— 保留当前主题但同样只输出启动画面。
- ``LUMI_PREVIEW_PAGE_ONLY=1`` —— 只输出设置页（``page_*.png``），且文件名带
  主题后缀（``page_MainInterface_light.png``）。配 ``LUMI_PREVIEW_THEME=light``
  用来看浅色主题下的页面版式（浅色那档默认只出启动画面）。
- ``LUMI_PREVIEW_PAGE_HEIGHT=<px>`` —— 单页预览（``page_*.png``）的宿主窗口高度，
  默认 940（「主界面」页在 2026-10-01 接收了放映页搬来的 5 张卡之后，640 已经
  截不全 —— 这种「页面比宿主还高」的情况看预览图是**看不出来**的，只能靠
  这个默认值留够）。
- ``LUMI_PREVIEW_PAGE_WIDTH=<px>`` —— 同上，宿主窗口宽度，默认 961 —— 对齐的是
  **真机页面内容列**（不是设置窗口宽度；预览宿主没有左侧导航），见下面
  ``PAGE_WIDTH`` 的推导。太窄会让页面里的并排卡片换行，看着像版式坏了。
- ``LUMI_PREVIEW_EDIT=<corner>`` —— 让主界面编辑器停在**编辑态**并聚焦这个角落
  （如 ``bottom_center``），输出到 ``main_editor_edit.png``。默认输出全景态。
- ``LUMI_PREVIEW_LABELS=1`` —— 打开「显示按钮文本」（``presentation.buttons.
  show_labels``，**只在内存里改、抓完图还原**），控制条按名称文本撑宽。
  输出文件名带 ``_labels`` 后缀，不覆盖常态那两张。
- ``LUMI_PREVIEW_PAGER=side|bottom`` —— 切「翻页组件位置」（``presentation.pager.
  position``，同样只在内存里改、抓完图还原）：side = 竖版两侧中间，bottom = 横版
  两侧下部。输出文件名带 ``_pager_<值>`` 后缀。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import BackdropEffect, RinUIWindow, Theme  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402

OFFSCREEN_X = -6000
OFFSCREEN_Y = -6000
OUT_DIR = ROOT / "preview"
#: 启动画面预览要钉死的进度：设计稿那张是「60% 创建托盘图标」，照抄好对照。
DESIGN_STAGE = (0.60, "创建托盘图标")
CORNERS = ("bottom_left", "bottom_center", "bottom_right", "middle_left", "middle_right")

#: 浅色主题（对照设计稿的「启动画面 Light」）。见模块 docstring。
IS_LIGHT = os.environ.get("LUMI_PREVIEW_THEME", "dark").lower().startswith("l")
#: 只渲染设置页（``page_*.png``）。用来核验**浅色主题**下的页面版式 ——
#: 浅色那一版默认只出启动画面（见 ``ONLY_SPLASH``），单独跑这档才看得到页面。
PAGE_ONLY = os.environ.get("LUMI_PREVIEW_PAGE_ONLY", "") not in ("", "0")
ONLY_SPLASH = (IS_LIGHT and not PAGE_ONLY) or os.environ.get(
    "LUMI_PREVIEW_ONLY", "") == "splash"
#: 单页预览的文件名后缀 —— 浅色那次不能把深色的常态图覆盖掉。
THEME_TAG = "light" if IS_LIGHT else "dark"
#: 单页预览的宿主窗口高度。页面长到一屏放不下时调大它（见模块 docstring）。
#: 940 是「最长的那个设置页（主界面）刚好放得下」的档位。
PAGE_HEIGHT = int(os.environ.get("LUMI_PREVIEW_PAGE_HEIGHT", "940") or 940)
#: 单页预览的宿主窗口宽度。默认 **961** —— 对齐的不是「设置窗口有多宽」，而是
#: **真机里页面内容列有多宽**：预览宿主只渲染单个页面（没有左侧导航），所以宿主
#: 宽度要等于真机的**页面宽度**，页面里的卡片版式（尤其是并排的图片 + 文字）才跟
#: 真机一模一样。
#: 推导（2026-10-01 实测，本机屏幕 1755×987 逻辑像素）：
#:   ① 真机窗口宽 = ``min(1755-80, max(1000, 1755*0.64))`` = 1123（``QWindow``
#:      量到 1135，多出的 ~13 是 Windows 不可见 resize 边框）；
#:   ② 真机内容列宽 = **807** —— 用 ``aboutHero`` 量出来（hero 是 ``Layout.fillWidth``，
#:      宽度就等于 ``FluentPage`` 的 ``container``）；
#:   ③ 宿主的左右留白 = 77/侧（在 961 宽的宿主里量过 ``page_About``，hero = 806.9，
#:      与真机 807 差 0.1px）；
#:   → 宿主宽度取 807 + 2×77 = 961。
#: ⚠️ 换显示器 / 改 ``settings.width_ratio`` / 页面 ``horizontalPadding`` 之后这个数
#: 会变，要重量一遍（``J:/tmp/l1probe/probe_page_col.py`` 量真机、
#: ``measure_hero.py`` 量预览图）。
#: 历史值 1000（内容列 846）是「窗口还开 900」那个年代定的，窗口改宽后偏宽 5%，故重算。
PAGE_WIDTH = int(os.environ.get("LUMI_PREVIEW_PAGE_WIDTH", "961") or 961)
#: 主界面编辑器停在编辑态时要聚焦的角落（空 = 全景态）。见模块 docstring。
PREVIEW_EDIT = os.environ.get("LUMI_PREVIEW_EDIT", "").strip()
#: 控制条「显示按钮文本」的预览开关。**只在内存里改配置**（``persist=False``），
#: 抓完图还原 —— 预览工具不该动用户的 ``config/config.json``。
PREVIEW_LABELS = os.environ.get("LUMI_PREVIEW_LABELS", "") not in ("", "0")
#: 「翻页组件位置」的预览档（side = 竖版两侧中间 / bottom = 横版两侧下部）。
#: 与 ``PREVIEW_LABELS`` 一样只改内存、抓完图还原。见模块 docstring。
PREVIEW_PAGER = os.environ.get("LUMI_PREVIEW_PAGER", "").strip().lower()
if PREVIEW_PAGER not in ("", "side", "bottom"):
    print(f"[WARN] LUMI_PREVIEW_PAGER 只认 side / bottom，收到 {PREVIEW_PAGER!r}，忽略")
    PREVIEW_PAGER = ""
#: 翻页组件位置 → 该形态下**启用**的角落（与 bridge.py 的常量同一份口径）
PAGER_POSITION_CORNERS = {
    "side": ("middle_left", "middle_right"),
    "bottom": ("bottom_left", "bottom_right"),
}


def preview_name(name: str) -> str:
    """给预览图文件名加后缀（``_labels`` / ``_pager_<值>``）。

    这些只是**对照图**，不该把常态那几张覆盖掉（控制条与编辑器两张都要加）。
    """
    stem, ext = os.path.splitext(name)
    if PREVIEW_LABELS:
        stem += "_labels"
    if PREVIEW_PAGER:
        stem += f"_pager_{PREVIEW_PAGER}"
    return stem + ext


def main() -> int:
    config = Config()
    # 「显示按钮文本」预览：改内存里的配置（控制条读它），抓完图在 capture() 里还原。
    labels_previous = config.get("presentation.buttons.show_labels")
    if PREVIEW_LABELS:
        config.set("presentation.buttons.show_labels", True, persist=False)
    # 「翻页组件位置」预览：同样只改内存 —— 它连带开关四个角落（真实生效的是
    # corners，所以两边一起改，否则预览里还是旧形态）。
    pager_previous = config.get("presentation.pager.position") or "side"
    if PREVIEW_PAGER:
        config.set("presentation.pager.position", PREVIEW_PAGER, persist=False)
        for corners in PAGER_POSITION_CORNERS.values():
            for corner in corners:
                config.set(f"presentation.corners.{corner}.enabled",
                           corner in PAGER_POSITION_CORNERS[PREVIEW_PAGER],
                           persist=False)

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, qt_app)
    backend.apply_state(
        PresentationState(active=True, slide_index=26, slide_total=41)
    )
    backend.setSplashStage(*DESIGN_STAGE)

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent")))
    # ⚠️ ``setTheme`` 会**持久化到 RinUI/config/rin_ui.json**，所以跑浅色那一版
    # 必须记下原值、截完图再切回去 —— 否则开发机上整个应用的下次启动会变成浅色。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Light if IS_LIGHT else Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(UI_DIR / "QuickPanel.qml")
    # 预览图不需要 DWM 背景特效，关掉能拿到实色背景（结束后恢复，避免污染用户配置）
    previous_effect = rinui.theme_manager.get_backdrop_effect()
    rinui.setBackdropEffect(BackdropEffect.None_)

    panel = rinui.root_window
    panel.setPosition(OFFSCREEN_X, OFFSCREEN_Y)
    panel.show()

    # ---- 顶层窗口（全屏叠加层）+ 内嵌控制条 ----
    # 预览用紧凑尺寸（1100x640）代替真实全屏；定位逻辑与 app/windows.py 一致。
    PREVIEW_W, PREVIEW_H = 1100, 640
    top_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "TopWindow.qml"))
    )
    top_window = None
    if top_component.isError():
        for error in top_component.errors():
            print("TOP WINDOW ERROR:", error.toString())
    else:
        top_window = top_component.createWithInitialProperties({"visible": True})
        if top_window is None:
            print("TOP WINDOW CREATE ERROR")
        else:
            top_window._top_component = top_component  # 持有引用防引擎回收
            top_window.setWidth(PREVIEW_W)
            top_window.setHeight(PREVIEW_H)
            top_window.setPosition(OFFSCREEN_X - 400, OFFSCREEN_Y)
            top_window.show()

    dock_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "PresentationDock.qml"))
    )
    if dock_component.isError():
        for error in dock_component.errors():
            print("DOCK ERROR:", error.toString())
    side_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "SidePager.qml"))
    )
    if side_component.isError():
        for error in side_component.errors():
            print("SIDE PAGER ERROR:", error.toString())

    container = top_window.property("container") if top_window is not None else None
    margin_x = int(config.get("presentation.margin_x", 20))
    margin_y = int(config.get("presentation.margin_y", 20))
    corners_cfg = config.get("presentation.corners", {}) or {}
    for corner in CORNERS:
        if not (corners_cfg.get(corner) or {}).get("enabled", False):
            continue
        # 与 windows.py::_load_docks 同语义：middle_* 用竖版组件
        vertical = corner.startswith("middle")
        component = side_component if vertical else dock_component
        dock = component.createWithInitialProperties({"corner": corner})
        if dock is None:
            for error in component.errors():
                print(f"DOCK {corner} ERROR:", error.toString())
            continue
        dock._dock_component = component  # 持有引用防引擎回收
        dock.setParentItem(container)
        # 与 windows.py::_position_dock 同语义：margin 是**视觉距离**，
        # 要扣掉控制条自带的投影余量（否则预览里的间距会比真机大 24px）
        shadow = int(dock.property("shadowMargin") or 0)
        if corner.endswith("left"):
            x = margin_x - shadow
        elif corner.endswith("center"):
            x = (PREVIEW_W - dock.width()) // 2
        else:
            x = PREVIEW_W - dock.width() - margin_x + shadow
        if vertical:
            # 竖版两侧翻页：垂直居中（L1 .flipper 默认形态）
            dock.setY((PREVIEW_H - dock.height()) // 2)
        else:
            dock.setY(PREVIEW_H - dock.height() - margin_y + shadow)
        dock.setX(x)

    # 设置窗口：默认页由 NavigationView 在 Component.onCompleted 里推入
    settings = None
    settings_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "Settings.qml"))
    )
    if settings_component.isError():
        for error in settings_component.errors():
            print("SETTINGS ERROR:", error.toString())
    else:
        settings = settings_component.createWithInitialProperties({"visible": True})
        if settings is None:
            for error in settings_component.errors():
                print("SETTINGS CREATE ERROR:", error.toString())
        else:
            settings.setPosition(OFFSCREEN_X, OFFSCREEN_Y - 900)
            settings.show()

    # 启动画面：设计稿还原结果。它是个**无边框透明窗口**（刻意不登记 RinUI），
    # 所以只能单独建实例；尺寸由 QML 自己定（设计稿 2984×1679 等比缩到 1080 宽）。
    splash = None
    splash_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "SplashWindow.qml"))
    )
    if splash_component.isError():
        for error in splash_component.errors():
            print("SPLASH ERROR:", error.toString())
    else:
        splash = splash_component.createWithInitialProperties({"visible": True})
        if splash is None:
            for error in splash_component.errors():
                print("SPLASH CREATE ERROR:", error.toString())
        else:
            splash._splash_component = splash_component  # 持有引用防引擎回收
            splash.setPosition(OFFSCREEN_X - 1500, OFFSCREEN_Y)
            splash.show()

    # 调试窗口：隐藏入口（设置窗口标题连点 10 次），与设置窗口同属按需创建，
    # 所以预览里也得单独建一个实例才看得到版式
    debug = None
    debug_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "DebugWindow.qml"))
    )
    if debug_component.isError():
        for error in debug_component.errors():
            print("DEBUG WINDOW ERROR:", error.toString())
    else:
        debug = debug_component.createWithInitialProperties({"visible": True})
        if debug is None:
            for error in debug_component.errors():
                print("DEBUG WINDOW CREATE ERROR:", error.toString())
        else:
            debug._debug_component = debug_component  # 持有引用防引擎回收
            debug.setPosition(OFFSCREEN_X, OFFSCREEN_Y - 1000)
            debug.show()

    # 主界面编辑器：入口是快捷面板的「主界面编辑器」快捷方式，与设置 / 调试窗口
    # 一样是按需创建，预览里同样单独建一个实例。
    #
    # ⚠️ 建完要**关掉** ``backdropEnabled``：编辑器窗口的背景是「整窗透明 +
    # DWM 亚克力」，而离屏抓图（``QQuickWindow.grabWindow``）拿的是 Qt 自己的
    # 渲染结果，**不含 DWM 合成层** —— 不关的话抓到的是透明（白）底板，正文像
    # 浮在半空中。关掉后 QML 会退回 Fluent 的亚克力兜底色，预览才有东西可看。
    # 真机上的亚克力由 ``windows.py::_apply_acrylic`` 负责，与这个开关无关。
    editor = None
    editor_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "MainInterfaceEditor.qml"))
    )
    if editor_component.isError():
        for error in editor_component.errors():
            print("EDITOR ERROR:", error.toString())
    else:
        editor = editor_component.createWithInitialProperties({"visible": True})
        if editor is None:
            for error in editor_component.errors():
                print("EDITOR CREATE ERROR:", error.toString())
        else:
            editor._editor_component = editor_component  # 持有引用防引擎回收
            editor.setProperty("backdropEnabled", False)
            editor.setPosition(OFFSCREEN_X - 1000, OFFSCREEN_Y - 900)
            editor.show()
            # 编辑态预览：钉一个聚焦目标，好核对「聚焦放大 + 暗罩 + 高亮 + 右侧面板」
            # 这一整套编排（相机有 220ms 动画，抓图在 1.8s 后，早就停稳了）。
            #
            # ⚠️ 光钉 ``selectedCorner`` 还不够：窗口摆在屏幕外**从没被暴露过**时，
            # 抓图可能拿到**上一帧**的合成结果 —— 实测偶发过一次
            # ``main_editor_edit.png`` 里右侧面板整块不见了（而同一时刻读
            # ``inspectorReveal`` 明明是 1.0）。抬一次窗口催曝光就稳了，
            # 与 ``smoke.py::_nudge_editor`` 同一个办法。
            if PREVIEW_EDIT:
                editor.setProperty("selectedCorner", PREVIEW_EDIT)
                editor.raise_()
                editor.requestActivate()

    # 各设置页单独渲染：用临时宿主窗口 + Loader 承载，逐页跑一遍
    page_hosts = _build_page_hosts(rinui.engine)

    OUT_DIR.mkdir(exist_ok=True)

    def capture() -> None:
        splash_name = "splash_light.png" if IS_LIGHT else "splash.png"
        if ONLY_SPLASH:
            # 只出启动画面：别的窗口照旧建着（都摆在屏幕外），但不截图 ——
            # 否则浅色那一版会把上面所有深色预览图覆盖掉。
            targets = [] if splash is None else [(splash_name, splash)]
        elif PAGE_ONLY:
            # 只出设置页（用来核验浅色主题下的页面版式），同样加主题后缀
            targets = [
                (name.replace(".png", f"_{THEME_TAG}.png"), window)
                for name, window in page_hosts
            ]
        else:
            targets = [("quick_panel.png", panel)]
            if top_window is not None:
                targets.append((preview_name("top_window.png"), top_window))
            if settings is not None:
                targets.append(("settings.png", settings))
            if splash is not None:
                targets.append((splash_name, splash))
            if debug is not None:
                targets.append(("debug_window.png", debug))
            if editor is not None:
                targets.append((
                    preview_name("main_editor_edit.png" if PREVIEW_EDIT
                                 else "main_editor.png"),
                    editor,
                ))
            targets += page_hosts

        for name, window in targets:
            try:
                image = window.grabWindow()
            except RuntimeError as exc:  # 窗口已被 QML 引擎回收
                print(f"[FAIL] {name}: {exc}")
                continue
            path = OUT_DIR / name
            if image.isNull():
                print(f"[FAIL] {name}: grabWindow() 返回空图")
                continue
            image.save(str(path))
            print(f"[OK] {name} -> {path} ({image.width()}x{image.height()})")
        # 主题要等所有窗口都截完才切回去（切主题会触发窗口重绘/重建）
        if rinui.theme_manager.get_theme_name() != previous_theme:
            rinui.theme_manager.toggle_theme(previous_theme)
            print(f"[OK] 主题已还原为 {previous_theme}")
        # 同理，「显示按钮文本」也只是预览用的一次性改动 —— 别留在内存里
        if PREVIEW_LABELS:
            config.set("presentation.buttons.show_labels", labels_previous,
                       persist=False)
        if PREVIEW_PAGER:
            config.set("presentation.pager.position", pager_previous, persist=False)
            enabled = PAGER_POSITION_CORNERS.get(pager_previous, ())
            for corners in PAGER_POSITION_CORNERS.values():
                for corner in corners:
                    config.set(f"presentation.corners.{corner}.enabled",
                               corner in enabled, persist=False)
        if PREVIEW_LABELS or PREVIEW_PAGER:
            backend.reload_from_config()
            print(f"[OK] 预览用的一次性改动已还原"
                  f"（show_labels={labels_previous}, pager.position={pager_previous}）")
        qt_app.quit()

    QTimer.singleShot(1800, capture)
    return qt_app.exec()


PAGE_HOST_QML = """import QtQuick
import RinUI as Rin

Rin.Window {
    id: host
    property url pageUrl: ""
    property int hostHeight: 640
    property int hostWidth: 1000

    width: hostWidth
    height: hostHeight
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


def _build_page_hosts(engine) -> list[tuple[str, object]]:
    """把 ``ui/settings`` 下每个页面塞进一个临时宿主窗口，返回 ``(文件名, 窗口)``。

    宿主 QML **写在 ``preview/`` 里且不删**：``QQmlEngine`` 会给每个 QML 源文件挂
    文件监视器，源文件一旦消失，引擎会判定文档失效并**回收由它创建的全部对象**
    （表现为 ``Internal C++ object already deleted``）。这也是为什么
    ``_probe_boot.qml`` 那种「写完就删」的用法只适合立即读属性的场景。
    """
    OUT_DIR.mkdir(exist_ok=True)
    host_path = OUT_DIR / "_page_host.qml"
    host_path.write_text(PAGE_HOST_QML, encoding="utf-8")

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(host_path)))
    if component.isError():
        for error in component.errors():
            print("PAGE HOST ERROR:", error.toString())
        return []

    hosts: list[tuple[str, object]] = []
    for index, page in enumerate(sorted((UI_DIR / "settings").rglob("*.qml"))):
        window = component.createWithInitialProperties(
            {
                "pageUrl": QUrl.fromLocalFile(str(page)),
                "hostHeight": PAGE_HEIGHT,
                "hostWidth": PAGE_WIDTH,
                "visible": True,
            }
        )
        if window is None:
            for error in component.errors():
                print(f"PAGE {page.name} ERROR:", error.toString())
            continue
        # 持有 component 引用：PySide 中 create() 出来的对象生命周期与组件绑定
        window._host_component = component
        window.setPosition(OFFSCREEN_X - index * 900, OFFSCREEN_Y - 1800)
        window.show()
        hosts.append((f"page_{page.stem}.png", window))
    return hosts


if __name__ == "__main__":
    raise SystemExit(main())
