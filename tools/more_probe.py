#!/usr/bin/env python
"""开发用：验证设置标题栏「更多」按钮 + 菜单 + 日志窗口（2026-11-21 用户指令）。

用户原话：「在最小化按钮左侧，版本号右侧增加『更多』按钮。点击后弹出菜单，
菜单内内容如下：创建快捷方式（两个：创建桌面快捷方式/创建快捷菜单快捷方式）、
日志、重新启动并进入维护模式、打开日志目录、打开应用目录。」

验的东西：

* 按钮在版本号**右侧**、三大键**左侧**，且没越出 ``titleBarHost``（越出会被
  ``clip`` 裁成半截）；
* 点按钮 → 菜单可见，右缘不戳出窗口；
* 五个条目顺序 / 文案对得上，维护模式那一项**禁用**（实现方案还没给）；
* 子菜单挂在「创建快捷方式」下、**弹在父菜单右侧**（Qt 自己定位）—— 这条是
  最容易坏的：``Rin.Menu`` 自带的进出场动画会改 ``x``/``y``，当子菜单用时
  必须换成空过渡（见 ``Settings.qml`` 那段注释）；
* 日志窗口能加载、正文非空、打开时停在**最新一行**。

不点「创建快捷方式」（会往真桌面 / 开始菜单写 .lnk）也不点两个「打开目录」
（会弹出资源管理器）。只验它们的存在与位置。

⚠️ 用临时用户配置，不碰 ``config/config.json``。
⚠️ 会 ``setTheme`` → 收尾还原并落盘，否则污染 ``rin_ui.json``。
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

from PySide6.QtCore import QMetaObject, QObject, QPoint, QUrl, Qt  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RinConfig  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.paths import UI_DIR  # noqa: E402

OFFSCREEN = -6000
THEME_TAG = "dark"

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {label}" + (f" —— {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def pump(app, ms: float) -> None:
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.005)


def wait_until(app, predicate, timeout: float = 3000.0, step: float = 40.0) -> bool:
    end = time.perf_counter() + timeout / 1000.0
    while time.perf_counter() < end:
        if predicate():
            return True
        app.processEvents()
        time.sleep(step / 1000.0)
    return predicate()


def find_obj(root_obj, name: str):
    """按 objectName 找任意 QObject 子代（Popup 不在 QQuickItem 树里）。"""
    return root_obj.findChild(QObject, name) if root_obj is not None else None


def invoke(obj, method: str) -> bool:
    return QMetaObject.invokeMethod(obj, method, Qt.DirectConnection)


def rect_in(obj, root) -> tuple[float, float, float, float]:
    """``(x, y, w, h)`` —— 位置按 ``mapToItem(root)`` 折算。"""
    pos = obj.mapToItem(root, 0, 0)
    return (
        float(pos.x()),
        float(pos.y()),
        float(obj.property("width")),
        float(obj.property("height")),
    )


def _walk(item):
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _type_name(item) -> str:
    try:
        return item.metaObject().className()
    except (AttributeError, RuntimeError):  # pragma: no cover
        return ""


def main() -> int:
    tmp_config = Path(tempfile.gettempdir()) / "lumi_more_probe_config.json"
    tmp_config.write_text("{}", encoding="utf-8")
    config = Config(user_file=str(tmp_config))

    real_config = ROOT / "config" / "config.json"
    real_before = real_config.read_text(encoding="utf-8") if real_config.exists() else ""

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, app)
    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    previous_theme = rinui.theme_manager.get_theme_name()
    previous_effect = rinui.theme_manager.get_backdrop_effect()
    rinui.setTheme(Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.load(UI_DIR / "QuickPanel.qml")
    rinui.root_window.setPosition(OFFSCREEN, OFFSCREEN)
    rinui.root_window.show()

    # ==================================================== 设置窗口（标题栏那一行）
    component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "Settings.qml")))
    if component.isError():
        for error in component.errors():
            print("SETTINGS ERROR:", error.toString())
        return 1
    window = component.createWithInitialProperties({"visible": True})
    if window is None:
        for error in component.errors():
            print("SETTINGS CREATE ERROR:", error.toString())
        return 1
    window._component = component
    window.setPosition(OFFSCREEN - 900, OFFSCREEN - 900)
    window.show()
    pump(app, 900)

    root = window.contentItem()
    more = find_obj(window, "settingsMoreButton")
    version = find_obj(window, "settingsVersionLabel")
    menu = find_obj(window, "settingsMoreMenu")

    check("「更多」按钮存在", more is not None)
    check("版本号还在", version is not None)
    check("菜单对象存在", menu is not None)
    if more is None or version is None or menu is None:
        app.quit()
        return 1

    check("菜单初始不可见", not bool(menu.property("visible")))

    # ---------------------------------------------------------- 版式：那一条的顺序
    mx, my, mw, mh = rect_in(more, root)
    vx, vy, vw, vh = rect_in(version, root)
    check("「更多」在版本号右侧", vx + vw <= mx + 1.0,
          f"版本号右缘 {vx + vw:.0f} / 按钮左缘 {mx:.0f}")

    host = more.parentItem()
    if host is not None:
        hx, hy, hw, hh = rect_in(host, root)
        check("按钮竖直居中于标题栏", abs((my + mh / 2) - (hy + hh / 2)) <= 4.0,
              f"中心差 {abs((my + mh / 2) - (hy + hh / 2)):.1f}px")
        check("按钮高度落在标题栏内", 16 <= mh <= hh + 0.5, f"按钮 {mh:.0f} / 栏 {hh:.0f}")
        # 2026-11-21 用户圈出「更多」与最小化之间那条空隙后：按钮故意用负
        # rightMargin 伸进托管区右侧那 48px，所以它**应当**越过托管区右缘。
        # 真正该守的是「紧挨着最小化」——按类名找 RinUI 的 CtrlBtn（没有 objectName）。
        ctrl = [it for it in _walk(root) if _type_name(it).startswith("CtrlBtn")
                and it.isVisible()]
        if ctrl:
            ctrl_left = min(rect_in(it, root)[0] for it in ctrl)
            gap = ctrl_left - (mx + mw)
            check("「更多」紧挨最小化按钮（间距 ≤ 12px）", 0 <= gap <= 12.0,
                  f"间距 {gap:.0f}px（按钮右缘 {mx + mw:.0f} / 三大键最左 {ctrl_left:.0f}）")
        else:
            check("找到三个窗口按钮", False, "未找到 CtrlBtn")

    # ---------------------------------------------------------------- 菜单：打开
    invoke(more, "clicked")  # QQuickAbstractButton 的信号可以直接触发
    if not wait_until(app, lambda: bool(menu.property("visible"))):
        # 信号名对不上时退一步：直接调 open()
        invoke(menu, "open")
        wait_until(app, lambda: bool(menu.property("visible")))
    check("点「更多」后菜单弹出", bool(menu.property("visible")))

    pump(app, 500)  # 等进场动画跑完（宽度 / 位置才会落定）
    popx = float(menu.property("x"))
    popw = float(menu.property("width"))
    check("菜单宽度按内容自适应（≥200，装得下最长那条）", popw >= 200.0, f"{popw:.0f}")
    # 「hover 没铺满」的根因是项宽小于菜单宽（菜单被写死成一个比内容大的数字，
    # 内容列居中，两侧露边）。项宽 == 菜单宽才叫铺满。
    probe_items = [("desktop", find_obj(menu, "settingsMoreDesktopShortcut")),
                   ("log", find_obj(menu, "settingsMoreLogItem"))]
    overhang = [f"{k}:{float(v.property('width')):.0f}" for k, v in probe_items
                if v is not None and abs(float(v.property("width")) - popw) > 12]
    check("菜单项宽度撑满菜单（悬停底色才能横贯整条）", not overhang,
          " / ".join(overhang) if overhang else f"项宽≈{popw:.0f}")
    check("菜单没戳出窗口右缘", popx + popw <= float(window.property("width")) + 1.0,
          f"右缘 {popx + popw:.0f} / 窗口 {float(window.property('width')):.0f}")

    # ---------------------------------------------------------------- 菜单：条目
    items = {
        "desktop": ("settingsMoreDesktopShortcut", "创建桌面快捷方式", True),
        "startMenu": ("settingsMoreStartMenuShortcut", "创建开始菜单快捷方式", True),
        "log": ("settingsMoreLogItem", "日志", True),
        "maintenance": ("settingsMoreMaintenanceItem", "重新启动并进入维护模式", False),
        "openLogDir": ("settingsMoreOpenLogDirItem", "打开日志目录", True),
        "openAppDir": ("settingsMoreOpenAppDirItem", "打开应用目录", True),
    }
    found: dict[str, QObject] = {}
    for key, (name, text, _enabled) in items.items():
        item = find_obj(menu, name)
        found[key] = item
        check(f"菜单项「{text}」存在", item is not None)
        if item is not None:
            check(f"菜单项文案 = {text}",
                  str(item.property("text") or "") == text,
                  str(item.property("text") or ""))

    if all(found.get(key) is not None for key in items):
        check("维护模式项是禁用态", not bool(found["maintenance"].property("enabled")))
        ys = []
        content = menu.property("contentItem")
        anchor_item = content if content is not None else root
        for key in ("desktop", "startMenu", "log", "maintenance", "openLogDir", "openAppDir"):
            pos = found[key].mapToItem(anchor_item, 0, 0)
            ys.append(float(pos.y()))
        check("条目自上而下按用户给的顺序排列",
              all(ys[i] < ys[i + 1] for i in range(len(ys) - 1)),
              " / ".join(f"{y:.0f}" for y in ys))

    # --------------------------------------------- 两条「创建快捷方式」（平铺）
    desktop = find_obj(menu, "settingsMoreDesktopShortcut")
    start_menu = find_obj(menu, "settingsMoreStartMenuShortcut")
    check("「创建桌面快捷方式」存在", desktop is not None)
    check("「创建开始菜单快捷方式」存在", start_menu is not None)
    if desktop is not None and start_menu is not None:
        check("两条创建快捷方式文案对",
              str(desktop.property("text") or "") == "创建桌面快捷方式"
              and str(start_menu.property("text") or "") == "创建开始菜单快捷方式",
              f"{desktop.property('text')} / {start_menu.property('text')}")

        content = menu.property("contentItem")
        anchor_item = content if content is not None else root
        dpos = desktop.mapToItem(anchor_item, 0, 0)
        spos = start_menu.mapToItem(anchor_item, 0, 0)
        check("两条创建快捷方式紧挨着（同一组）", abs(spos.y() - dpos.y() - 34) <= 4,
              f"{dpos.y():.0f} / {spos.y():.0f}")
        if found.get("log") is not None:
            dpos_root = desktop.mapToItem(root, 0, 0)
            lpos_root = found["log"].mapToItem(root, 0, 0)
            check("两条创建快捷方式在「日志」上方", dpos_root.y() < lpos_root.y(),
                  f"{dpos_root.y():.0f} / {lpos_root.y():.0f}")

    # ------------------------------------------- 真点一下「更多」，再点「日志」
    # ⚠️ 窗口默认搁在 -6900（不打扰桌面），而 ``QTest.mouseClick`` 是按窗口坐标
    # 落到**真实屏幕**上的 —— 屏外点击根本进不了窗口，什么都不会发生（第一版
    # 就这么误判过）。这一段把窗口搬回屏幕内，测完搬走。
    opened_log: list[int] = []
    backend.logWindowRequested.connect(lambda: opened_log.append(1))
    window.setPosition(80, 80)
    pump(app, 700)
    # 搬回屏内后重开菜单：Popup 在屏外时会被 Qt 夹到屏幕边缘，位置不可信
    # （截图里菜单明明窄了一截就是因为这个），屏内才是真位置。
    if not bool(menu.property("visible")):
        invoke(more, "clicked")
        wait_until(app, lambda: bool(menu.property("visible")))
    pump(app, 600)

    # 截图：菜单开着、窗口在屏内
    png = ROOT / "preview" / f"more_menu_{THEME_TAG}.png"
    window.grabWindow()
    img = window.grabWindow()
    if img.isNull():
        check("菜单剧情图已生成", False, "grabWindow() 返回空图")
    else:
        img.save(str(png))
        check("菜单剧情图已生成", True, f"{png.name} ({img.width()}x{img.height()})")

    # hover 一项再拍一张：用户反馈「hover 没铺满」，这里把悬停态也留成图。
    # ⚠️ hover 由**真实鼠标位置**驱动，窗口必须在屏内（上面已经搬进来了）。
    hover_target = find_obj(menu, "settingsMoreDesktopShortcut")
    if hover_target is not None:
        hp = hover_target.mapToItem(root, 0, 0)
        QTest.mouseMove(window, QPoint(int(hp.x() + 40),
                                       int(hp.y() + float(hover_target.property("height")) / 2)))
        pump(app, 400)
        hover_png = ROOT / "preview" / f"more_menu_hover_{THEME_TAG}.png"
        window.grabWindow()
        himg = window.grabWindow()
        if not himg.isNull():
            himg.save(str(hover_png))
            print(f"[OK] 悬停态图: {hover_png.name}")

    # 版式：菜单右缘应当和「更多」按钮右缘对齐（两者都在 titleBarHost 右侧）
    menu_anchor = menu.property("parentItem")
    if menu_anchor is not None:
        anchor_x = float(menu_anchor.mapToItem(root, 0, 0).x())
        menu_right = anchor_x + float(menu.property("x")) + float(menu.property("width"))
        btn_right = mx + mw
        check("菜单右缘对齐「更多」按钮右缘", abs(menu_right - btn_right) <= 6.0,
              f"菜单右缘 {menu_right:.0f} / 按钮右缘 {btn_right:.0f}")

    # 真点「更多」：按钮现在用负 rightMargin 伸出了 titleBarHost（clip 已关），
    # 必须确认它在托管区之外**仍然可点** —— 只关 clip 不保证输入也放行。
    invoke(menu, "close")
    pump(app, 300)
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     QPoint(int(mx + mw / 2), int(my + mh / 2)))
    pump(app, 500)
    check("「更多」按钮伸出托管区后仍可点开菜单", bool(menu.property("visible")))

    log_pos = found["log"].mapToItem(root, 0, 0)
    center = QPoint(
        int(log_pos.x() + float(found["log"].property("width")) / 2),
        int(log_pos.y() + float(found["log"].property("height")) / 2),
    )
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center)
    pump(app, 500)
    check("点「日志」发出 logWindowRequested", len(opened_log) == 1, f"{len(opened_log)} 次")
    check("点完菜单自动收起", not bool(menu.property("visible")))
    window.setPosition(OFFSCREEN - 900, OFFSCREEN - 900)
    pump(app, 300)

    # ==================================================== 日志窗口（单独加载）
    payload = backend.readLogEntries(True)
    log_entries = payload.get("entries", [])
    check("readLogEntries 有内容", len(log_entries) > 0, f"{len(log_entries)} 条")

    log_component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "LogWindow.qml")))
    if log_component.isError():
        for error in log_component.errors():
            print("LOG WINDOW ERROR:", error.toString())
    else:
        log_window = log_component.createWithInitialProperties({"visible": True})
        if log_window is None:
            for error in log_component.errors():
                print("LOG WINDOW CREATE ERROR:", error.toString())
        else:
            log_window._component = log_component
            log_window.setPosition(OFFSCREEN - 1500, OFFSCREEN - 900)
            log_window.show()
            pump(app, 900)

            flick = None

            # 列表数据由 Backend 解析后灌进 filteredEntries，不再有「正文 TextEdit」。
            filtered = log_window.property("filteredEntries").toVariant()
            check("日志列表已灌进窗口", len(filtered) > 0, f"{len(filtered)} 条")
            check("默认只显示警告及以上",
                  all(entry["level"] in ("WARNING", "ERROR", "CRITICAL")
                      for entry in filtered),
                  f"等级集合 {sorted({entry['level'] for entry in filtered})}")

            # 「打开就在最新一行」：滚动到底后 contentY 应等于 contentHeight - height
            for node in _walk(log_window.contentItem()):
                # ⚠️ 别用 ``flickableDirection`` 之类枚举属性做判据（PySide 没有
                # 那个枚举的转换器，读到就抛 RuntimeError）；``flicking`` 是布尔。
                if node.property("flicking") is not None \
                        and node.property("contentY") is not None:
                    flick = node
                    break
            if flick is not None:
                pump(app, 400)  # callLater 的滚动
                cy = float(flick.property("contentY"))
                ch = float(flick.property("contentHeight"))
                vh = float(flick.property("height"))
                check("打开时停在最新一行",
                      ch <= vh + 1.0 or abs(cy - (ch - vh)) <= 2.0,
                      f"contentY={cy:.0f} / 最大 {(ch - vh):.0f}")

            png = ROOT / "preview" / f"log_window_{THEME_TAG}.png"
            log_window.grabWindow()
            img = log_window.grabWindow()
            if img.isNull():
                check("日志窗口图已生成", False, "grabWindow() 返回空图")
            else:
                img.save(str(png))
                check("日志窗口图已生成", True, f"{png.name} ({img.width()}x{img.height()})")

    # ==================================================== 真配置未被碰
    if real_config.exists():
        check("真配置未被本次探针改动",
              real_config.read_text(encoding="utf-8") == real_before)

    if rinui.theme_manager.get_theme_name() != previous_theme:
        rinui.theme_manager.toggle_theme(previous_theme)
        RinConfig.save_config()
        print(f"[OK] 主题已还原并落盘为 {previous_theme}")
    if rinui.theme_manager.get_backdrop_effect() != previous_effect:
        rinui.theme_manager.apply_backdrop_effect(previous_effect)
        RinConfig.save_config()
        print(f"[OK] 背景特效已还原为 {previous_effect}")

    print()
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项: {FAILURES}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
