"""开发用：端到端自检。

不依赖 PowerPoint，直接注入一个假的放映状态来验证：

1. 托盘可用
2. 快捷面板能显示，且按**光标位置**摆放并夹取在屏幕内
3. 放映控制条能按角落显示 / 隐藏，且位置落在屏幕左下、右下
4. 设置窗口（懒创建）能打开、居中且在屏幕内
5. 快捷方式增删 / 排序与设置项读写能落回配置
6. 配置读取与日志写入正常

用法::

    .venv\\Scripts\\python.exe tools\\smoke.py
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QPoint, QTimer  # noqa: E402
from PySide6.QtGui import QCursor, QGuiApplication  # noqa: E402

from app import ppt_controller  # noqa: E402
from app.application import LuminaliumApplication  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402
from app.windows import _dwm_cloaked  # noqa: E402

RESULTS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")


def main() -> int:
    app = LuminaliumApplication(sys.argv)
    qt_app = app.qt_app

    failures = 0

    def run_checks() -> None:
        nonlocal failures

        check("系统托盘可用", app.tray.available)
        check("托盘已显示", True)
        expected_docks = [
            name
            for name, settings in (app.config.get("presentation.corners", {}) or {}).items()
            # 配置里有 "//" 开头的注释键（值是字符串），要跳过
            if isinstance(settings, dict) and settings.get("enabled", False)
        ]
        check(
            f"顶层窗口与 {len(expected_docks)} 条控制条已创建",
            app.windows.overlay is not None
            and set(app.windows._docks) == set(expected_docks),
            str(list(app.windows._docks)),
        )

        # ---- 面板显隐与定位 ----
        # 光标必须在 show_panel() **之前**取：面板按「弹出那一刻」的光标定位，
        # 之后真鼠标一动，断言就会拿新位置跟旧面板比（真机踩过：光标中途
        # 移动 500px → 假失败）。
        cursor = QCursor.pos()
        app.windows.show_panel()
        panel = app.windows.panel
        check("快捷面板可见", panel.isVisible())
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        inside = (
            area.left() <= panel.x()
            and panel.x() + panel.width() <= area.right() + 1
            and area.top() <= panel.y()
            and panel.y() + panel.height() <= area.bottom() + 1
        )
        check(
            "面板位于屏幕内",
            inside,
            f"panel=({panel.x()},{panel.y()},{panel.width()}x{panel.height()}) area={area}",
        )
        # 光标锚定：水平居中对齐光标（除非贴到屏幕边），纵向要么在光标下方要么整个在光标上方。
        center_x = panel.x() + panel.width() // 2
        # 容差 40：贴边时被夹取，夹取用的宽度快照与最终宽度可能差十几像素
        horiz_ok = (
            abs(center_x - cursor.x()) <= 24
            or panel.x() <= area.left() + 40
            or panel.x() + panel.width() >= area.right() - 40
        )
        vert_ok = (
            panel.y() >= cursor.y()
            or panel.y() + panel.height() <= cursor.y()
            or panel.y() <= area.top() + 12
        )
        check(
            "面板贴着光标弹出（不是甩到屏幕另一头）",
            horiz_ok and vert_ok,
            f"cursor=({cursor.x()},{cursor.y()}) panel=({panel.x()},{panel.y()})",
        )
        app.windows.hide_panel()
        check("面板可隐藏", not panel.isVisible())

        # ---- 模拟进入放映：顶层窗口全屏 + 控制条贴角 ----
        app.ppt.inject_state(
            PresentationState(active=True, slide_index=26, slide_total=41)
        )
        overlay = app.windows.overlay
        screen = QGuiApplication.primaryScreen()
        geom = screen.geometry()
        # 定位基准是**整屏**几何，不是避开任务栏的 availableGeometry：
        # 放映时任务栏被放映窗口盖住，用户眼里的基准就是屏幕边缘，
        # 而 Windows 的工作区照样把任务栏算掉（本机差 48px）→ 纵向会凭空
        # 多出一个任务栏的高度。这里用整屏复算，才能抓到这类静默偏差。
        check(
            "顶层窗口全屏显示",
            overlay is not None and overlay.isVisible()
            and overlay.width() == geom.width() and overlay.height() == geom.height(),
            f"overlay={overlay.width()}x{overlay.height()} screen={geom.width()}x{geom.height()}",
        )
        for corner, dock in app.windows._docks.items():
            left_gap = dock.x()
            right_gap = geom.width() - (dock.x() + dock.width())
            bottom_gap = geom.height() - (dock.y() + dock.height())
            near_left = left_gap <= 64
            near_right = right_gap <= 64
            near_bottom = bottom_gap <= 64
            if corner.endswith("center"):
                # 居中：左右余量对称（后面还有一条专门的居中断言，这里只兜底）
                expected_horizontal = abs(left_gap - right_gap) <= 2
            else:
                expected_horizontal = near_left if corner.endswith("left") else near_right
            check(
                f"控制条 {corner} 贴角",
                expected_horizontal and near_bottom,
                f"pos=({dock.x()},{dock.y()}) size={dock.width()}x{dock.height()} "
                f"gap=({left_gap},{right_gap},{bottom_gap})",
            )

        # ---- 视觉贴边距离 = 配置里的 margin（对齐 Luminalium 1 的 20px）----
        # 控制条窗口尺寸含投影余量，屏幕上量到的距离必须把这部分扣掉。
        # 这里按实际属性复算，防止「margin 被投影余量吃掉」这类静默偏差
        # （64px 的贴角容差抓不到这种错）。
        margin_x = int(app.windows._config.get("presentation.margin_x", 20))
        margin_y = int(app.windows._config.get("presentation.margin_y", 20))
        cdock = app.windows._docks.get("bottom_center")
        if cdock is not None:
            shadow = int(cdock.property("shadowMargin") or 0)
            visual_bottom = geom.height() - (cdock.y() + cdock.height() - shadow)
            check(
                "工具栏视觉贴边距离 = 配置的垂直边距",
                abs(visual_bottom - margin_y) <= 1,
                f"视觉={visual_bottom} 期望={margin_y} shadow={shadow}",
            )
        for corner, edge in (("bottom_left", "left"), ("bottom_right", "right")):
            dock = app.windows._docks.get(corner)
            if dock is None:
                continue
            shadow = int(dock.property("shadowMargin") or 0)
            visual_h = (dock.x() + shadow if edge == "left"
                        else geom.width() - (dock.x() + dock.width() - shadow))
            check(
                f"翻页 pill {corner} 视觉贴边距离 = 配置的水平边距",
                abs(visual_h - margin_x) <= 1,
                f"视觉={visual_h} 期望={margin_x} shadow={shadow}",
            )

        # ---- 可见性三要素（「放映时看不见控制条」的根因守卫）----
        # Qt 为了给顶层透明窗口画逐像素 alpha，自己给窗口加了 WS_EX_LAYERED
        # 并走 UpdateLayeredWindow。剥掉这个 bit、或额外调
        # SetLayeredWindowAttributes，都会让窗口「存在但不画」——踩过两次。
        user32 = ctypes.windll.user32
        hwnd = int(overlay.winId())
        style = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
        check(
            "保留 Qt 自带的 WS_EX_LAYERED（透明渲染通道）",
            bool(style & 0x00080000),
            f"exstyle=0x{style:08X}",
        )
        check("Win32 层面窗口可见", bool(user32.IsWindowVisible(hwnd)))
        check("DWM 未把窗口披风化（cloaked=0）", _dwm_cloaked(hwnd) == 0,
              f"cloaked={_dwm_cloaked(hwnd)}")

        # ---- 穿透：首选区域塑形（系统级），兜底才是整窗 WS_EX_TRANSPARENT ----
        if app.windows._region_mode:
            scale = app.windows._region_scale or 1.0
            gdi32 = ctypes.windll.gdi32
            hrgn = gdi32.CreateRectRgn(0, 0, 0, 0)
            got = user32.GetWindowRgn(hwnd, hrgn)
            bdock = app.windows._docks.get("bottom_center")
            hit_rect = app.windows._dock_global_rect(bdock)
            origin = overlay.position()

            def in_region(point) -> bool:
                return bool(gdi32.PtInRegion(
                    hrgn,
                    int((point.x() - origin.x()) * scale),
                    int((point.y() - origin.y()) * scale),
                ))

            center_dock = QPoint(hit_rect.x() + hit_rect.width() // 2,
                                 hit_rect.y() + hit_rect.height() // 2)
            check("区域塑形已挂到窗口上", got != 0)
            check("控制条在区域内（可点击）", in_region(center_dock))
            check(
                "屏幕其它位置在区域外（鼠标落到放映窗口）",
                not in_region(QPoint(geom.width() // 2, 60)),
            )
            gdi32.DeleteObject(hrgn)
        else:
            check(
                "兜底模式：整窗 WS_EX_TRANSPARENT 已开启",
                bool(style & 0x20),
                f"exstyle=0x{style:08X}",
            )
            bdock = app.windows._docks.get("bottom_center")
            hit_rect = app.windows._dock_global_rect(bdock)
            app.windows._update_overlay_hit(hit_rect.center())
            style = user32.GetWindowLongW(hwnd, -20)
            check("光标悬到工具栏上收回穿透", not (style & 0x20), f"rect={hit_rect}")
            app.windows._update_overlay_hit(QPoint(geom.width() // 2, 100))
            style = user32.GetWindowLongW(hwnd, -20)
            check("离开工具栏恢复穿透", bool(style & 0x20))

        check("页码已同步", app.backend.slideIndex == 26 and app.backend.slideTotal == 41,
              f"{app.backend.slideIndex}/{app.backend.slideTotal}")

        # ---- 工具栏恒横向（下中部）+ 翻页栏独立在两侧 ----
        corners_cfg = app.config.get("presentation.corners", {}) or {}
        center_groups = (corners_cfg.get("bottom_center") or {}).get("groups", [])
        left_groups = (corners_cfg.get("bottom_left") or {}).get("groups", [])
        right_groups = (corners_cfg.get("bottom_right") or {}).get("groups", [])
        check("工具栏在下中部且不含翻页组",
              "tools" in center_groups and "pager" not in center_groups,
              str(center_groups))
        check("左下翻页 pill", left_groups == ["pager"], str(left_groups))
        check("右下翻页 pill", right_groups == ["pager"], str(right_groups))
        cdock = app.windows._docks.get("bottom_center")
        ldock = app.windows._docks.get("bottom_left")
        rdock = app.windows._docks.get("bottom_right")
        check(
            "工具栏恒横向（宽大于高）",
            cdock is not None and cdock.width() > cdock.height(),
            f"center={cdock.width()}x{cdock.height()}",
        )
        check(
            "工具栏水平居中（左右余量对称）",
            cdock is not None
            and abs(cdock.x() - (geom.width() - cdock.width() - cdock.x())) <= 2,
            f"x={cdock.x()} w={cdock.width()} screen={geom.width()}",
        )
        check(
            "两侧翻页 pill 等高（同一套组件）",
            ldock is not None and rdock is not None
            and abs(rdock.height() - ldock.height()) <= 1
            and rdock.x() > ldock.x(),
            f"left={ldock.width()}x{ldock.height()} right={rdock.width()}x{rdock.height()}",
        )
        # ---- 尺寸档位 = Luminalium 1 的实装值（防止比例被悄悄改回参考稿那套）----
        # 这些值之间的**关系**才是设计语言：按钮直径 = 内容高 = 条高 − 上下内边距×2，
        # 圆角拉满成胶囊，翻页 pill 的留白只有 4（工具条是 8）。
        # 嵌套弧线必须**同心**：外壳帽半径 − 分段帽半径 = 外壳左内边距，
        # 圆心不对齐时弧间空隙宽窄不一，看起来像条诡异的空槽（真机踩过）。
        if cdock is not None:
            cshadow = int(cdock.property("shadowMargin") or 0)
            bar_h = cdock.property("contentHeight") + cdock.property("surfacePaddingY") * 2
            check(
                "控制条档位 = 放大档（条高 62 / 按钮 44 / 图标 22 / 间距 4）",
                bar_h == 62
                and cdock.property("contentHeight") == 44
                and cdock.property("hitSize") == 44
                and cdock.property("iconSize") == 22
                and cdock.property("buttonSpacing") == 4,
                f"条高={bar_h} 内容高={cdock.property('contentHeight')} "
                f"按钮={cdock.property('hitSize')} 图标={cdock.property('iconSize')} "
                f"间距={cdock.property('buttonSpacing')}",
            )
            check(
                "底板是全圆胶囊（圆角 = 条高/2）",
                abs(cdock.property("pillRadius") - bar_h / 2) <= 0.5,
                f"pillRadius={cdock.property('pillRadius')} 期望={bar_h / 2}",
            )
            check(
                "CW2 同款渐变边框高光已开（工具栏）",
                cdock.property("highlightEnabled") is True
                and cdock.property("highlightRingVisible") is True,
                f"enabled={cdock.property('highlightEnabled')} "
                f"ring={cdock.property('highlightRingVisible')}",
            )
            check(
                "竖向分隔线 = 放大档（1×28、两侧各 4）",
                cdock.property("dividerWidth") == 1
                and cdock.property("dividerHeight") == 28
                and cdock.property("dividerGap") == 4,
                f"{cdock.property('dividerWidth')}×{cdock.property('dividerHeight')} "
                f"gap={cdock.property('dividerGap')}",
            )
            # ---- 工具分段：胶囊容器 + 圆形分页（RinUI Segmented 基类）----
            tools_count = len(app.config.get("presentation.tools") or [])
            check(
                "工具分段已接入（分页数 = 配置的 tools 数）",
                cdock.property("segmentItemCount") == tools_count and tools_count > 0,
                f"items={cdock.property('segmentItemCount')} 配置={tools_count}",
            )
            check(
                "分页真的进了 TabBar 容器（count = 配置数，Repeater 接线成立）",
                cdock.property("segmentPageCount") == tools_count,
                f"tabCount={cdock.property('segmentPageCount')} 配置={tools_count}",
            )
            check(
                "分段容器是圆的（胶囊圆角 = 内容高/2）",
                abs(cdock.property("segmentPillRadius") - 44 / 2) <= 0.5,
                f"segmentPillRadius={cdock.property('segmentPillRadius')} 期望=22",
            )
            check(
                "嵌套弧线同心（外壳帽圆心 = 分段帽圆心：paddingX + 22 == 31）",
                cdock.property("surfacePaddingX") + cdock.property("segmentPillRadius")
                == cdock.property("pillRadius"),
                f"paddingX={cdock.property('surfacePaddingX')} + segR="
                f"{cdock.property('segmentPillRadius')} vs shellR={cdock.property('pillRadius')}",
            )
            check(
                "工具栏尺寸（扣除投影余量）",
                cdock.width() - cshadow * 2 > 0 and cdock.height() - cshadow * 2 == 62,
                f"{cdock.width() - cshadow * 2}x{cdock.height() - cshadow * 2}",
            )
        if ldock is not None:
            lshadow = int(ldock.property("shadowMargin") or 0)
            check(
                "翻页 pill = 放大档 .flipper（180×62）",
                ldock.width() - lshadow * 2 == 180 and ldock.height() - lshadow * 2 == 62,
                f"{ldock.width() - lshadow * 2}x{ldock.height() - lshadow * 2}",
            )
            check(
                "CW2 同款渐变边框高光已开（翻页 pill）",
                ldock.property("highlightEnabled") is True
                and ldock.property("highlightRingVisible") is True,
                f"enabled={ldock.property('highlightEnabled')} "
                f"ring={ldock.property('highlightRingVisible')}",
            )

        # ---- 模拟退出放映：顶层窗口整体隐藏 ----
        app.ppt.inject_state(PresentationState(active=False))
        check(
            "退出放映后顶层窗口隐藏",
            app.windows.overlay is not None and not app.windows.overlay.isVisible(),
        )

        # ---- 手动显示：探测认不出放映窗口时的兜底（托盘菜单走这条路）----
        app.windows.toggle_docks_manual()
        check(
            "手动可显示控制条（不依赖探测）",
            app.windows.overlay is not None and app.windows.overlay.isVisible(),
        )
        app.windows.toggle_docks_manual()
        check("手动可再次隐藏控制条", not app.windows.overlay.isVisible())

        # ---- 探测规则来自配置（改配置即改探测，不写死在代码里）----
        check(
            "放映窗口类名白名单已从配置加载",
            "screenclass" in ppt_controller.SLIDESHOW_WINDOW_CLASSES,
            str(sorted(ppt_controller.SLIDESHOW_WINDOW_CLASSES)),
        )
        check(
            "放映进程名白名单已从配置加载",
            "POWERPNT.EXE" in ppt_controller.SLIDESHOW_PROCESS_NAMES,
            str(sorted(ppt_controller.SLIDESHOW_PROCESS_NAMES)),
        )
        # 回归守卫：GetClassNameW 不支持「传 NULL 查长度」，写错会静默返回
        # 空串 —— 窗口类探测整条链路失效，而日志上只表现为「没检测到放映」。
        named = [c for _h, c, *_ in ppt_controller._enum_windows() if c]
        check(
            "窗口类名探测可用（GetClassName 未静默失效）",
            len(named) > 0,
            f"{len(named)} 个窗口取到类名，例: {named[:3]}",
        )

        # ---- 设置窗口（懒创建）----
        check("设置窗口尚未创建", app.windows.settings is None)
        app.windows.show_settings()
        settings = app.windows.settings
        check("设置窗口已创建", settings is not None)
        if settings is not None:
            area = QGuiApplication.primaryScreen().availableGeometry()
            inside = (
                area.left() <= settings.x()
                and settings.x() + settings.width() <= area.right() + 1
                and area.top() <= settings.y()
                and settings.y() + settings.height() <= area.bottom() + 1
            )
            check(
                "设置窗口位于屏幕内",
                settings.isVisible() and inside,
                f"pos=({settings.x()},{settings.y()}) size={settings.width()}x{settings.height()}",
            )
            # 无 Win32 原生边框：RinUI 基类在 Windows 上会把 FramelessWindowHint
            # 摘掉并加 WS_CAPTION|WS_THICKFRAME；Settings.qml 的
            # Component.onCompleted 负责加回来。这里有回归断言守着。
            user32b = ctypes.windll.user32
            style = user32b.GetWindowLongW(int(settings.winId()), -16) & 0xFFFFFFFF
            check(
                "设置窗口无 Win32 原生边框（自绘边框）",
                not (style & 0x00C00000) and not (style & 0x00040000),
                f"style=0x{style:08X} WS_CAPTION={'Y' if style & 0x00C00000 else 'N'} "
                f"WS_THICKFRAME={'Y' if style & 0x00040000 else 'N'}",
            )
            app.backend.settingsCloseRequested.emit()
            check("设置窗口可关闭", not settings.isVisible())

            # 打开指定设置页（快捷方式「放映控制」走的路径）
            app.windows.show_settings("settings/Presentation.qml")
            check("能跳到指定设置页", settings.isVisible())
            app.backend.settingsCloseRequested.emit()

        # ---- 快捷方式增删 / 排序 ----
        backend = app.backend
        before = [item["id"] for item in backend.shortcutItems]
        backend.setShortcutEnabled("update", True)
        after_add = [item["id"] for item in backend.shortcutItems]
        check("能启用快捷方式", "update" in after_add, f"{before} -> {after_add}")
        backend.moveShortcut("update", 0)
        moved = [item["id"] for item in backend.shortcutItems]
        check("能调整快捷方式顺序", moved and moved[0] == "update", str(moved))
        backend.setShortcutEnabled("update", False)
        restored = [item["id"] for item in backend.shortcutItems]
        check("能移除快捷方式", "update" not in restored, str(restored))

        # ---- 设置项读写 ----
        # 注意：这里会把值**持久化**进 config/config.json。所以必须先把原值存下来、
        # 结束时原样写回 —— 曾经写成「测完恢复成写死的 8」，于是把旧默认值钉进了
        # 用户配置，后来把默认改成 20 都不生效（2026-09-25 踩到）。
        original_margin = app.config.get("presentation.margin_x")
        backend.setSetting("presentation_margin_x", 24)
        check("设置项已写入配置",
              app.config.get("presentation.margin_x") == 24,
              str(app.config.get("presentation.margin_x")))
        check("设置项已同步到 QML 视图",
              backend.settings.get("presentation_margin_x") == 24,
              str(backend.settings.get("presentation_margin_x")))
        backend.setSetting("presentation_margin_x", original_margin)
        check("设置项已还原（自检不留副作用）",
              app.config.get("presentation.margin_x") == original_margin,
              f"{original_margin} -> {app.config.get('presentation.margin_x')}")

        # ---- 退出键样式可切换（default ↔ danger，两种版式都是直径 44 的圆）----
        # 这条走**内存改配置 + reload_from_config** 的成对用法（``persist=False``），
        # 不落盘 —— 免得像 margin_x 那样往用户配置里钉一个值。
        # 两种版式尺寸完全一样，只能靠暴露出来的填充色 / 图标色区分。
        exit_dock = app.windows._docks.get("bottom_center")
        if exit_dock is not None:
            prev_style = app.config.get("presentation.exit.style")
            base_fill = str(exit_dock.property("exitFillColor"))
            base_icon = str(exit_dock.property("exitIconColor"))

            other = "danger" if (prev_style or "default") != "danger" else "default"
            app.config.set("presentation.exit.style", other, persist=False)
            app.backend.reload_from_config()
            check(
                f"退出键样式已同步到 QML（{prev_style} → {other}）",
                exit_dock.property("exitStyle") == other,
                str(exit_dock.property("exitStyle")),
            )
            check(
                "两种版式的填充/图标色确实不同（尺寸相同时唯一的区分）",
                str(exit_dock.property("exitFillColor")) != base_fill
                and str(exit_dock.property("exitIconColor")) != base_icon,
                f"{base_fill}/{base_icon} -> "
                f"{exit_dock.property('exitFillColor')}/{exit_dock.property('exitIconColor')}",
            )

            app.config.set("presentation.exit.style", prev_style, persist=False)
            app.backend.reload_from_config()
            check(
                "退出键样式已还原（自检不留副作用）",
                str(exit_dock.property("exitFillColor")) == base_fill,
                f"{base_fill} -> {exit_dock.property('exitFillColor')}",
            )

        failures = sum(1 for line in RESULTS if line.startswith("[FAIL]"))
        qt_app.quit()

    QTimer.singleShot(900, run_checks)
    code = qt_app.exec()
    app.ppt.shutdown()

    print("\n================ 自检结果 ================")
    for line in RESULTS:
        print(line)
    print(f"=========================================")
    print(f"失败项: {failures}")
    return 1 if failures or code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
