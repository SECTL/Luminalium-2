"""开发用：端到端自检。

不依赖 PowerPoint，直接注入一个假的放映状态来验证：

1. 托盘可用
2. 快捷面板能显示，且按**光标位置**摆放并夹取在屏幕内
3. 放映控制条能按角落显示 / 隐藏，且位置贴角（工具栏下中；翻页栏
   按配置在屏幕两侧垂直居中（竖版）或左下 / 右下（横版））
4. 设置窗口（懒创建）能打开、居中且在屏幕内；调试窗口（隐藏入口 = 设置标题
   连点 10 次）的热区盖得住标题文本、点够次数能开、与设置窗口并排不重叠
5. 快捷方式增删 / 排序与设置项读写能落回配置
6. 配置读取与日志写入正常
7. 启动画面（设计稿还原）：按 2984:1679 比例居中、无标题栏且**刻意不登记 RinUI**、
   各元素落在设计稿位置（按 ``k = 宽/2984`` 缩放）、描边贴住外沿、进度填充与
   淡出后的回收
8. 主界面编辑器（独立窗口）：懒创建、能从快捷面板的快捷方式派发打开、
   交给 RinUI 管、只隐藏不销毁；设置导航里「外观」已改名「主界面」
9. 编辑器的**顶层窗口预览舞台**：舞台平面 = 放映显示器 1:1 坐标系、外框跟着
   相机、控制条副本与配置里启用的角落一一对应且位置与
   ``windows.py::_position_dock`` 同源、预览层有鼠标屏蔽、亚克力已打到窗口
   句柄上、标题栏有不透明底板
10. 编辑器的**编辑态**（2026-10-01 用户指令）：默认全景（整屏等比 + 面板收起）、
   点中一条控制条 → 聚焦放大并居中 / **面板左边整块**压暗罩（铺满、不留一圈
   亚克力）/ 选中项套强调色描边 / 右侧滑出**实色**设置面板并挤窄舞台（组件信息
   与缩放**常驻在下部**，上部留给设置项）、手动档位与平移钳制、退出后回到全景

用法::

    .venv\\Scripts\\python.exe tools\\smoke.py
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QMetaObject, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtGui import QCursor, QGuiApplication  # noqa: E402

from app import ppt_controller  # noqa: E402
from app.application import LuminaliumApplication  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402
from app.windows import CORNERS, _dwm_cloaked  # noqa: E402

RESULTS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")


# ------------------------------------------------------------------ 启动画面

def _find_named(item, name):
    """在 QQuickItem 树里按 objectName 找一项（QML 的 Item 不是 QObject 子对象链的正规成员，
    所以用 ``childItems()`` 递归比 ``findChild`` 稳）。"""
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _find_named(child, name)
        if found is not None:
            return found
    return None


def _collect_named(item, prefix: str):
    """收集树里所有 objectName 以 ``prefix`` 开头的项（按前缀找一族兄弟项）。"""
    found = []
    if item.objectName().startswith(prefix):
        found.append(item)
    for child in item.childItems():
        found.extend(_collect_named(child, prefix))
    return found


def _prop(obj, path: str):
    """按 ``a.b`` 读 QML 属性（分组属性如 ``border.width`` 也支持）。"""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.property(part)
    return cur


def _wait_stable(key, *, timeout_ms: int = 3000, step_ms: int = 120,
                 repeat: int = 2) -> bool:
    """等 ``key()`` 的取值连续 ``repeat`` 拍不变。

    ``key`` 传一个返回可比较快照的函数（字符串最省事）。QML 的动画是级联的
    （面板挤窄舞台 → 舞台宽度变 → 聚焦比例跟着变 → 相机再动一次），死等一个
    固定时长在机器忙的时候会读到中间值；等「不变」才是稳的。返回是否稳定。
    """
    last = key()
    same = 0
    waited = 0
    while waited < timeout_ms:
        QTest.qWait(step_ms)
        waited += step_ms
        now = key()
        if now == last:
            same += 1
            if same >= repeat:
                return True
        else:
            same = 0
        last = now
    return False


#: 启动画面的**版式项**：objectName -> (x, y, w, h)，单位是设计稿原值
#: （Figma 画布 2984×1679）。QML 侧一律写这些原值再乘 ``k = 卡面宽/2984``，
#: 所以这里按同样的比例验证 —— 改了 QML 却没同步设计稿（或缩放因子被绕过）
#: 时，这条会立刻炸。``None`` = 该字段不按设计稿校验（已改走 Fluent 固定值）。
SPLASH_LAYOUT = {
    "splashLogo": (131.0, 121.0, 184.0, 184.0),
    "splashWordmark": (147.3, 1176.5, 727.7, 113.7),
    "splashArtCard": (1444.0, 121.0, 1448.0, 1438.0),
    "splashTrack": (134.0, None, 1178.0, None),
}

#: 启动画面的 **Fluent 外观项**：(objectName, 属性名, 期望值)。
#: 这些**绝不许**跟着 k 缩放 —— 设计稿的圆角 92 / 描边 7 是比例值，折算到
#: 720 宽的卡面上是 22px / 1.7px，那是 iOS 语汇不是 Fluent（2026-10-01 用户
#: 指令「比例过大了、不符合 Fluent 2 设计语言」）。谁把它们改回乘 k 就会炸。
SPLASH_FLUENT = [
    ("splashTrack", "height", 4),         # Fluent ProgressBar 规格
    ("splashTrack", "radius", 2),
]

#: 挂在**窗口**上的 Fluent 外观项：(属性名, 期望值)。
#: 卡面的圆角 / 描边放这儿，是因为 ``Rectangle.border`` 是**分组属性**、PySide
#: 侧读不到子属性（``Can't find converter for 'QQuickPen*'``），所以 QML 把它们
#: 另挂了一份在窗口上（``cardRadius`` / ``cardBorderWidth``）供这里断言。
SPLASH_WINDOW_FLUENT = [
    ("cardRadius", 8),          # WinUI OverlayCornerRadius
    ("cardBorderWidth", 1),     # Fluent 控件描边
]


def _check_splash(app) -> None:
    app.windows.show_splash()
    # 窗口里的 ``contentRoot`` / ``splashCard`` 是 **anchors.fill / 绑定**定尺寸的，
    # 要等 Qt 跑完第一轮布局才有几何 —— 不等的话它们一律读成 0x0（假失败）。
    QTest.qWait(250)
    splash = app.windows.splash
    check("启动画面已创建", splash is not None)
    if splash is None:
        return

    check("启动画面可见", splash.isVisible())

    content = splash.contentItem()
    card = _find_named(content, "splashCard")
    check("启动画面卡面存在", card is not None)
    if card is None:
        return

    # 比例：卡面高度必须由宽度按设计稿比例算出来，不能写死
    check("卡面按设计稿比例（2984:1679）",
          abs(card.height() / card.width() - 1679 / 2984) < 0.01,
          f"卡面 {card.width():.0f}x{card.height():.0f}"
          f" = {card.height() / card.width():.4f}（期望 {1679 / 2984:.4f}）")

    # 窗口 = 卡面 + 四周阴影边距（阴影得画在卡外，所以窗口比卡面大一圈）
    margin = splash.property("shadowMargin")
    check("窗口 = 卡面 + 四周阴影边距",
          abs(splash.width() - card.width() - 2 * margin) < 1.5
          and abs(splash.height() - card.height() - 2 * margin) < 1.5,
          f"窗口 {splash.width()}x{splash.height()}，"
          f"卡面 {card.width():.0f}x{card.height():.0f}，边距 {margin}")

    # 卡面必须正好落在阴影边距上、描边不能再内缩：这是「描边贴边」那条老坑的
    # 等价防线 —— 以前把 SVG 的 stroke inset 补到描边上，整条边会内移半个线宽，
    # 卡片左右下三条边整条错位（2026-10-01 踩过）。
    check("卡面贴着阴影边距、描边不再内缩",
          abs(card.x() - margin) < 0.6 and abs(card.y() - margin) < 0.6,
          f"卡面在 ({card.x():.1f},{card.y():.1f})，期望 ({margin},{margin})")

    # 居中：基准是 **availableGeometry**（避开任务栏）而不是整屏。边距四边对称，
    # 所以窗口居中 = 卡面居中。
    area = QGuiApplication.primaryScreen().availableGeometry()
    dx = abs((splash.x() + splash.width() // 2) - (area.x() + area.width() // 2))
    dy = abs((splash.y() + splash.height() // 2) - (area.y() + area.height() // 2))
    check("启动画面在可用区居中", dx <= 2 and dy <= 2, f"Δ=({dx}, {dy})")

    # 无边框 + **刻意不登记 RinUI**：登记了 RinUI 会加 WS_CAPTION 并让 DWM 画
    # 系统圆角/阴影，和这儿自绘的 Fluent 卡片打架。
    hwnd = int(splash.winId())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    check("启动画面无标题栏", not (style & 0x00C00000), f"style=0x{style:08X}")
    check("启动画面刻意不登记 RinUI（否则会被加系统边框/阴影）",
          hwnd not in {int(h) for h in app.rinui.theme_manager.windows},
          f"hwnd={hwnd}")

    # 版式：逐项按 k 验证（容差 1.5 逻辑像素）。k 从 QML 侧读，避免两边各写一份。
    k = splash.property("k")
    for name, ref in SPLASH_LAYOUT.items():
        item = _find_named(content, name)
        if item is None:
            check(f"启动画面元素 {name} 存在", False, "没找到该 objectName")
            continue
        got = (item.x(), item.y(), item.width(), item.height())
        want = tuple(v * k if v is not None else None for v in ref)
        worst = max(abs(got[i] - want[i]) for i in range(4) if want[i] is not None)
        shown = ", ".join("—" if v is None else f"{v:.1f}" for v in want)
        check(f"启动画面 {name} 落在设计稿位置", worst <= 1.5,
              f"实际 ({got[0]:.1f},{got[1]:.1f} {got[2]:.1f}x{got[3]:.1f}) "
              f"期望 ({shown})")

    # Fluent 外观项必须是**固定值**，不跟着 k 缩放
    for name, prop, want in SPLASH_FLUENT:
        item = _find_named(content, name)
        got = _prop(item, prop) if item is not None else None
        check(f"启动画面 {name}.{prop} 走 Fluent 固定值",
              got is not None and abs(float(got) - want) < 0.6,
              f"实测 {got}，期望 {want}")
    for prop, want in SPLASH_WINDOW_FLUENT:
        got = splash.property(prop)
        check(f"启动画面 {prop} 走 Fluent 固定值",
              got is not None and abs(float(got) - want) < 0.6,
              f"实测 {got}，期望 {want}")

    # 字阶同样是 Fluent 固定值，不跟着 k 缩放。层级：Title 28 → Body 14 → Caption 12。
    # （版本行一开始对齐到了 bodyLarge 18，用户 2026-10-01 反馈「版本号和开发代号
    #   那一栏的字体大小未免有点大了」→ 收到 body 14。）
    # ``font`` 是 QFont 值类型，PySide 能转；不像 ``border`` 那样是 QObject 分组属性。
    for name, want in (("splashSubtitle", 14), ("splashStageLeft", 12),
                       ("splashStageRight", 12)):
        item = _find_named(content, name)
        font = item.property("font") if item is not None else None
        got = font.pixelSize() if font is not None else None
        check(f"启动画面 {name} 字号走 Fluent 固定值", got == want,
              f"实测 {got}，期望 {want}")

    # 进度条纵向对齐设计稿那条槽的**中线**（高度换成 Fluent 的 4 了，不是顶对齐）
    track = _find_named(content, "splashTrack")
    want_cy = (1459 + 25 / 2) * k
    check("进度条纵向对齐设计稿槽位中线",
          track is not None and abs((track.y() + track.height() / 2) - want_cy) < 1.0,
          "未找到" if track is None else
          f"中线 {track.y() + track.height() / 2:.1f}，期望 {want_cy:.1f}")

    # 进度：后端推 0.6 → 填充条应约为轨道宽的 60%，右侧标签以「60%」开头
    app.backend.setSplashStage(0.60, "创建托盘图标")
    fill = _find_named(content, "splashProgressFill")
    if fill is not None and track is not None and track.width() > 0:
        # 填充条带 220ms 补间，等它走完再断言
        QTest.qWait(320)
        frac = fill.width() / track.width()
        check("启动画面进度条按进度填充", abs(frac - 0.60) < 0.03, f"实测 {frac:.3f}")
    right = _find_named(content, "splashStageRight")
    check("启动画面右侧显示「百分比 + 阶段」",
          right is not None and str(right.property("text")).startswith("60%"),
          "未找到" if right is None else str(right.property("text")))

    # 生命周期：淡出结束后窗口要被**真正收掉**（那张 1717×1640 的插画常驻不划算）
    app.windows.hide_splash()
    QTest.qWait(700)
    check("启动画面淡出后被回收", app.windows.splash is None,
          "仍有残留实例" if app.windows.splash is not None else "")


# ------------------------------------------------------------ 主界面编辑器

def _check_editor(app) -> None:
    """主界面编辑器：懒创建 + 从快捷面板派发 + 交给 RinUI 管 + 只隐藏不销毁。

    2026-10-01 用户指令：「把『外观』改成『主界面』，然后新增一个『主界面编辑器』，
    你先把主界面编辑器的空窗口建出来，并且加上快捷面板的快捷方式」。
    """
    # 目录里必须真有这条，否则面板的「+」里永远不会出现它
    catalog = {
        str(item.get("id")): item
        for item in (app.config.get("quick_panel.shortcut_catalog", []) or [])
    }
    entry = catalog.get("main_editor")
    check(
        "快捷方式目录含「主界面编辑器」且动作是 open_editor",
        entry is not None and str(entry.get("action")) == "open_editor",
        "目录里没有 main_editor" if entry is None else f"action={entry.get('action')}",
    )

    # 懒创建：没点开就一个对象都不建（与设置 / 调试窗口同一条约定）
    check("主界面编辑器懒创建（未打开时不建）", app.windows.editor is None)

    # 走**真实入口**派发：快捷方式 → backend.shortcutTriggered →
    # application._on_shortcut 认 action=open_editor → windows.show_editor()
    accepted = app.backend.activateShortcut("main_editor")
    editor = app.windows.editor
    check(
        "从快捷面板的快捷方式打开主界面编辑器",
        accepted and editor is not None and editor.isVisible(),
        f"accepted={accepted} "
        + ("窗口未创建" if editor is None else f"visible={editor.isVisible()}"),
    )
    if editor is None:
        return

    # ---------------------------------------------------- 正文：顶层窗口舞台
    content_root = editor.contentItem()
    frame = _find_named(content_root, "editorScreenFrame")
    plane = _find_named(content_root, "editorScreenPlane")
    viewport = _find_named(content_root, "editorStageViewport")
    check("编辑器正文是预览舞台（占位块已撤）",
          frame is not None and plane is not None and viewport is not None
          and _find_named(content_root, "editorPlaceholder") is None,
          "屏幕外框 / 平面 / 视口 没找齐" if None in (frame, plane, viewport) else "")
    if frame is None or plane is None or viewport is None:
        app.backend.closeMainEditor()
        return

    # 相机 / 面板都是 220ms 的动画，而且是**级联**的（面板挤窄舞台 → 舞台宽度变 →
    # 聚焦比例跟着变 → 相机再动一次）。死等一个固定时长会在机器忙的时候读到动画
    # 中间值（真踩过：读到 1.743 而不是 1.783 —— 差 40ms 的行程），所以这里一律
    # 等「这一串值连续两拍不变」，比 qWait 靠谱。面板 / 暗罩还没取到时先只看相机。
    inspector = None
    dim = None

    def _camera_key() -> str:
        key = (f"{plane.x():.2f}|{plane.y():.2f}|{plane.scale():.5f}"
               f"|{viewport.width():.1f}")
        if inspector is not None:
            key += f"|{inspector.x():.1f}|{float(dim.property('opacity') or 0):.3f}"
        return key

    def _settle() -> None:
        _wait_stable(_camera_key)

    QTest.qWait(300)  # contentItem 里的绑定要等第一轮布局才拿得到几何
    _settle()

    info = app.backend.presentationScreen
    check(
        "舞台平面 = 放映显示器的 1:1 坐标系",
        int(plane.width()) == int(info["width"])
        and int(plane.height()) == int(info["height"]),
        f"plane={plane.width():.0f}x{plane.height():.0f} screen={info}",
    )

    # 全景态：整屏等比装进视口（长边贴合）。相机有三件套（比例 / 位移 / 平移偏移），
    # 这里复算的是「默认态」那一支 —— QML 里是副本，漂了两边的取景就不一样。
    fit = min(viewport.width() / info["width"], viewport.height() / info["height"])
    check(
        "默认停在全景态（没选中组件、面板收起）",
        str(editor.property("selectedCorner")) == ""
        and editor.property("editing") is False,
        f"selectedCorner={editor.property('selectedCorner')!r} "
        f"editing={editor.property('editing')}",
    )
    scale = plane.scale()
    check(
        "全景比例 = 整屏等比装进舞台",
        abs(scale - fit) <= 1e-3,
        f"scale={scale:.4f} fit={fit:.4f}",
    )
    # 面板收起时的舞台宽度 —— 后面用它验「面板是挤窄舞台而不是浮在上面」
    stage_width_closed = viewport.width()
    check(
        "屏幕外框跟着相机走（位置与尺寸都取自平面）",
        abs(frame.x() - plane.x()) <= 1
        and abs(frame.y() - plane.y()) <= 1
        and abs(frame.width() - round(info["width"] * scale)) <= 1
        and abs(frame.height() - round(info["height"] * scale)) <= 1,
        f"frame=({frame.x():.0f},{frame.y():.0f}) {frame.width()}x{frame.height()} "
        f"plane=({plane.x():.0f},{plane.y():.0f}) scale={scale:.4f}",
    )

    # 每个 enabled 的角落都得有一只副本 —— 少一只就是「主界面」显示不全
    corner_cfg = app.config.get("presentation.corners", {}) or {}
    enabled = [n for n in CORNERS if (corner_cfg.get(n) or {}).get("enabled")]
    preview_docks = _collect_named(plane, "editorPreviewDock_")
    got = sorted(d.objectName()[len("editorPreviewDock_"):] for d in preview_docks)
    check(
        "预览里的控制条与配置里启用的角落一一对应",
        got == sorted(enabled),
        f"预览={got} 配置={sorted(enabled)}",
    )

    # 位置：与 windows.py::_position_dock **同一份公式**（含 shadowMargin 扣减、
    # 贴边基准是整屏而非工作区）。这边复算一遍是因为 QML 里那份是副本 ——
    # 两边一旦漂了，编辑器和真机摆出来的位置就不一样。
    margin_x = int(app.config.get("presentation.margin_x", 20))
    margin_y = int(app.config.get("presentation.margin_y", 20))
    worst = 0.0
    for dock in preview_docks:
        corner = dock.objectName()[len("editorPreviewDock_"):]
        align = CORNERS.get(corner)
        if align is None or dock.width() <= 0 or dock.height() <= 0:
            continue
        horizontal, vertical = align
        shadow = int(dock.property("shadowMargin") or 0)
        if horizontal == "left":
            x = margin_x - shadow
        elif horizontal == "center":
            x = round((plane.width() - dock.width()) / 2)
        else:
            x = plane.width() - dock.width() - margin_x + shadow
        if vertical == "top":
            y = margin_y - shadow
        elif vertical == "middle":
            y = round((plane.height() - dock.height()) / 2)
        else:
            y = plane.height() - dock.height() - margin_y + shadow
        worst = max(worst, abs(dock.x() - x), abs(dock.y() - y))
    check(
        "预览控制条落在角落（算法与 windows.py::_position_dock 同源）",
        worst <= 1.0,
        f"最大偏差 {worst:.2f}px",
    )

    shield = _find_named(viewport, "editorStageShield")
    check(
        "视口有鼠标屏蔽（点控制条不会真的翻页）",
        # 挂在**视口**上而不是平面上：输入坐标因此是「视口坐标」，
        # 拖动平移才不会被相机自身的位移抵消（见 QML 里的说明）。
        shield is not None
        and abs(shield.width() - viewport.width()) <= 1
        and abs(shield.height() - viewport.height()) <= 1,
        "屏蔽层没挂在视口上 / 没铺满视口" if shield is None else
        f"shield={shield.width():.0f}x{shield.height():.0f} "
        f"viewport={viewport.width():.0f}x{viewport.height():.0f}",
    )

    # ------------------------------------------------------- 编辑态：聚焦 + 面板
    # 2026-10-01 用户指令：「做『编辑态』适应 主界面编辑器的缩放，先默认就整体匹配
    # 界面的比例，点到那个组件再聚焦，然后从右侧展开居右的组件设置面板」。
    #
    # 下面这些常量**与 ui/Luminalium/Lumi.qml 的「主界面编辑器」一节同源**
    # （那边是权威），改一处要改两处。
    PANEL_W = 340
    PANEL_HEADER_H = 56
    BACK_BUTTON = 40
    FOCUS_PAD_X, FOCUS_PAD_Y = 72, 56
    FOCUS_MAX = 2.0
    ZOOM_MAX = 4.0
    DIM_OPACITY = 0.34
    DIM_HOLE_PAD = 6
    RING_WIDTH, RING_GAP = 2, 4
    # RinUI 的 ``themes/utils.qml::Utils.windowDragArea`` —— ``FluentWindowBase`` 用它
    # 把 ``contentArea`` 四周内缩，那圈是窗口的拖动 / 缩放热区，QML 内容默认盖不到。
    WINDOW_DRAG_AREA = 5

    inspector = _find_named(content_root, "editorInspectorPanel")
    footer = _find_named(content_root, "editorInspectorFooter")
    dim = _find_named(content_root, "editorDimMask")
    ring = _find_named(content_root, "editorSelectionRing")
    check(
        "舞台有暗罩 / 选中框，右侧有设置面板与下部常驻条",
        None not in (inspector, footer, dim, ring),
        f"panel={inspector is not None} footer={footer is not None} "
        f"dim={dim is not None} ring={ring is not None}",
    )
    if None in (inspector, footer, dim, ring):
        app.backend.closeMainEditor()
        return

    check(
        "全景态下面板收起、暗罩不显示",
        not inspector.isVisible()
        and float(dim.property("opacity") or 0) <= 0.002
        and not ring.isVisible(),
        f"panelVisible={inspector.isVisible()} dimOpacity={dim.property('opacity')} "
        f"ringVisible={ring.isVisible()}",
    )

    # 挑一条预览里的控制条当编辑对象（不写死角落名：用户配置里开着哪条就用哪条；
    # 树序 = 配置的角落顺序，第一条通常是下中工具栏）
    target = preview_docks[0]
    corner_name = str(target.objectName()[len("editorPreviewDock_"):])
    shadow = int(target.property("shadowMargin") or 0)
    sx = target.x() + shadow
    sy = target.y() + shadow
    sw = max(target.width() - shadow * 2, 1)
    sh = max(target.height() - shadow * 2, 1)

    # 命中测试：点控制条正中要认得出是哪一条；点屏幕正中（那里没有控制条）要认不出
    hit = str(editor.dockAt(sx + sw / 2, sy + sh / 2))
    miss = str(editor.dockAt(info["width"] / 2, info["height"] / 2))
    check(
        "点画面里的控制条能认出是哪一条",
        hit == corner_name and miss == "",
        f"命中={hit!r}（期望 {corner_name!r}）空白处={miss!r}",
    )

    editor.setProperty("selectedCorner", corner_name)
    _settle()  # 相机 220ms + 面板 220ms + 一轮布局

    check(
        "点中组件后进入编辑态",
        editor.property("editing") is True,
        f"editing={editor.property('editing')} corner={corner_name}",
    )

    # 聚焦比例：把选中项（+取景留白）装进视口，钳制在 [fitScale, 2×]。
    # ⚠️ 这里的「全景比例」要用**面板展开后**的视口重算 —— 面板挤窄舞台之后
    #    fitScale 本身也变小了（它是「整屏装进当前视口」）。
    fit_now = min(viewport.width() / info["width"], viewport.height() / info["height"])
    want = min((viewport.width() - FOCUS_PAD_X * 2) / sw,
               (viewport.height() - FOCUS_PAD_Y * 2) / sh)
    want = max(fit_now, min(want, FOCUS_MAX))
    check(
        "聚焦按「选中项装满视口」放大（上限 2×、下限不小于全景）",
        plane.scale() > fit_now + 1e-3 and abs(plane.scale() - want) <= 1e-3,
        f"scale={plane.scale():.4f} 期望={want:.4f}"
        f"（展开面板后的全景 {fit_now:.4f}；未展开时 {fit:.4f}）",
    )

    # 落点：把选中项的中心摆到视口中央，再按「画面比视口大才允许越界」钳制 ——
    # 所以贴边的控制条（下中 / 左右中）会被顶住、只有一个轴精确居中。
    # 这里**逐轴复算** QML 里那份公式（与下面「控制条落在角落」同一个路子：
    # QML 侧是副本，漂了两边的取景就不一样）。
    def _expected_origin(content: float, view: float, base: float) -> float:
        if content <= view:
            return (view - content) / 2
        return min(0.0, max(view - content, base))

    scale = plane.scale()
    base_x = viewport.width() / 2 - (sx + sw / 2) * scale
    base_y = viewport.height() / 2 - (sy + sh / 2) * scale
    want_x = _expected_origin(info["width"] * scale, viewport.width(), base_x)
    want_y = _expected_origin(info["height"] * scale, viewport.height(), base_y)
    check(
        "聚焦取景落点 = 「选中项居中 → 越界钳制」的解析解",
        abs(plane.x() - want_x) <= 1.5 and abs(plane.y() - want_y) <= 1.5,
        f"plane=({plane.x():.1f},{plane.y():.1f}) 期望=({want_x:.1f},{want_y:.1f}) "
        f"居中轴 x={abs(base_x - want_x) <= 1.5} y={abs(base_y - want_y) <= 1.5}",
    )

    # 暗罩：**铺满面板左边的整块区域**，选中项周围留洞。
    # 2026-10-01 用户指令：「左边的压暗你应该占满左半边啊而不是留一圈亚克力」——
    # 所以它还挂在窗口坐标里（不在 planeLayer 里），左右沿一路顶到窗口边 /
    # 设置面板边，视口四周那圈留白也得压上。
    top = _find_named(dim, "editorDimTop")
    bottom = _find_named(dim, "editorDimBottom")
    left = _find_named(dim, "editorDimLeft")
    right = _find_named(dim, "editorDimRight")
    check(
        "非选中区域压了一层暗罩",
        dim.isVisible() and abs(float(dim.property("opacity")) - DIM_OPACITY) <= 0.02,
        f"visible={dim.isVisible()} opacity={dim.property('opacity')}",
    )
    # RinUI 的 ``Utils.windowDragArea``：内容区四周被它内缩了 5px，暗罩要比内容区
    # 再往外撑这么多才顶得到窗口边（否则贴边留一圈 5px 没压暗的亚克力）。
    DRAG = 5
    check(
        "暗罩铺满面板左边的整块区域（一路顶到窗口边，不留一圈亚克力）",
        abs(dim.x() - (-DRAG)) <= 1
        and abs((dim.x() + dim.width()) - inspector.x()) <= 1
        and abs(dim.y()) <= 1
        and abs(dim.height() - (inspector.height() + DRAG)) <= 1,
        f"dim=({dim.x():.0f},{dim.y():.0f}) {dim.width():.0f}x{dim.height():.0f} "
        f"panel.x={inspector.x():.0f} "
        f"内容区={inspector.width():.0f}x{inspector.height():.0f}",
    )

    # 洞：几何在**窗口坐标**里复算 —— 取景矩形活在 1:1 屏幕坐标系里，要经相机
    # （planeLayer 的比例与位移）+ 视口偏移换过来，各边外扩「描边间隙 + 洞留白」，
    # 最后夹进视口（手动放大到 400% 时洞会比视口还宽）。
    hole_pad = DIM_HOLE_PAD + RING_GAP
    view_x = viewport.x() + DRAG
    view_y = viewport.y()
    raw_x = view_x + plane.x() + sx * plane.scale() - hole_pad
    raw_y = view_y + plane.y() + sy * plane.scale() - hole_pad
    hole_x = max(view_x, raw_x)
    hole_y = max(view_y, raw_y)
    hole_w = max(0.0, min(view_x + viewport.width(),
                          raw_x + sw * plane.scale() + hole_pad * 2) - hole_x)
    hole_h = max(0.0, min(view_y + viewport.height(),
                          raw_y + sh * plane.scale() + hole_pad * 2) - hole_y)
    check(
        "暗罩在选中项处留出了洞（四块矩形拼出中间挖空，且夹在视口内）",
        None not in (top, bottom, left, right)
        and abs(top.width() - dim.width()) <= 1
        and abs(top.height() - hole_y) <= 1
        and abs(left.x() + left.width() - hole_x) <= 1
        and abs(left.height() - hole_h) <= 1
        and abs(bottom.y() - (hole_y + hole_h)) <= 1,
        "没找齐四块" if None in (top, bottom, left, right) else
        f"top={top.x():.0f},{top.y():.0f},{top.width():.0f},{top.height():.0f} "
        f"left={left.x():.0f},{left.y():.0f},{left.width():.0f},{left.height():.0f} "
        f"bottom.y={bottom.y():.0f} 期望洞=({hole_x:.0f},{hole_y:.0f},"
        f"{hole_w:.0f},{hole_h:.0f})",
    )

    # 选中描边：几何跟着相机，宽度不跟着缩放（画在视口坐标里）
    # ⚠️ ``border.width`` 是分组属性，PySide 侧读不到（没有 QQuickPen* 的转换器）
    #    —— QML 里另存了 ``ringBorderWidth`` / ``ringBorderColor`` 给自检读。
    check(
        "选中项套着强调色描边（位置跟着相机、宽度不随缩放）",
        ring.isVisible()
        and abs(ring.x() - (plane.x() + sx * plane.scale() - RING_GAP)) <= 1.5
        and abs(ring.y() - (plane.y() + sy * plane.scale() - RING_GAP)) <= 1.5
        and abs(ring.width() - (sw * plane.scale() + RING_GAP * 2)) <= 1.5
        and abs(float(ring.property("ringBorderWidth")) - RING_WIDTH) <= 0.01
        and str(ring.property("ringBorderColor").name()).lower()
            == str(app.backend.accent).lower(),
        f"ring=({ring.x():.1f},{ring.y():.1f}) {ring.width():.1f}x{ring.height():.1f} "
        f"border={ring.property('ringBorderWidth')} "
        f"color={ring.property('ringBorderColor')} accent={app.backend.accent}",
    )

    # 面板是**挤窄舞台**：舞台宽度整整少了 ``PANEL_W``，而且面板左沿就贴在
    # 舞台右沿之后（不是浮在舞台上面盖住一块）。
    # 用「收面板时的舞台宽」当基准而不是 ``editor.width() - 32``：内容区还被
    # RinUI 的 ``Utils.windowDragArea`` 左右各内缩 5px。
    check(
        "右侧设置面板滑出，并把舞台挤窄（不是浮在舞台上面）",
        inspector.isVisible()
        and abs(inspector.width() - PANEL_W) <= 1
        and abs(viewport.width() - (stage_width_closed - PANEL_W)) <= 2
        and viewport.x() + viewport.width() <= inspector.x() + 1,
        f"panel={inspector.x():.1f}+{inspector.width():.1f} "
        f"viewport={viewport.x():.1f}+{viewport.width():.0f} "
        f"（面板收起时 {stage_width_closed:.0f}）",
    )

    # 面板结构（2026-10-01 用户指令：「右侧的设置面板应该是实色背景，组件信息就放在
    # 右侧设置面板的下部始终置着展示：工具栏 318x62，上面的信息不要了，缩放的话也是
    # 放在下部置着，右侧面板其他地方是用来排设置项的」）。
    surface = _find_named(content_root, "editorInspectorSurface")
    body = _find_named(content_root, "editorInspectorBody")
    surface_color = surface.property("color") if surface is not None else None
    check(
        "设置面板是**实色**底（不透出背后的亚克力）",
        surface_color is not None and surface_color.alpha() == 255,
        "没找到底板" if surface is None else f"color={surface_color}",
    )

    # 底板要**一路铺到窗口边**（2026-10-01 用户截屏指出右沿/下沿那圈亮带）：
    # 内容区被 RinUI 内缩了 ``windowDragArea`` 5px，底板不往外撑就会露出那圈窗口
    # 背景（亚克力）。留 1px 是窗口 ``background`` 的描边。
    bleed = float(inspector.property("edgeBleed"))
    right_edge = surface.mapToScene(QPointF(float(surface.width()), 0.0)).x()
    bottom_edge = surface.mapToScene(QPointF(0.0, float(surface.height()))).y()
    check(
        "面板底板铺到窗口边（盖住右侧/下侧那圈窗口拖动热区）",
        abs(bleed - (WINDOW_DRAG_AREA - 1)) <= 0.01
        and abs(right_edge - (editor.width() - 1)) <= 1.5
        and abs(bottom_edge - (editor.height() - 1)) <= 1.5,
        f"bleed={bleed} right={right_edge:.1f} bottom={bottom_edge:.1f} "
        f"window={editor.width():.0f}x{editor.height():.0f}",
    )
    check(
        "组件信息与缩放**常驻**在面板下部（贴底，不跟着设置项滚动）",
        abs(footer.y() + footer.height() - inspector.height()) <= 1
        and abs(footer.width() - inspector.width()) <= 1
        and _find_named(footer, "editorZoomRow") is not None
        and _find_named(footer, "editorInspectorName") is not None,
        f"footer=({footer.x():.0f},{footer.y():.0f}) "
        f"{footer.width():.0f}x{footer.height():.0f} "
        f"panel={inspector.width():.0f}x{inspector.height():.0f}",
    )
    # 面板顶部导航（2026-10-01 用户指令：「（右上角那个 ×）加大移到左边改为返回按钮」，
    # 同时把顶部那块「设置项」标题 + 占位文案「删掉」）。
    nav = _find_named(content_root, "editorInspectorNav")
    back = _find_named(content_root, "editorInspectorBack")
    stale = {
        name: _find_named(content_root, name) is not None
        for name in ("editorInspectorHeader", "editorInspectorTitle",
                     "editorViewBar", "editorInspectorClose",
                     "editorInspectorPlaceholder")
    }
    check(
        "面板顶部是导航条（旧的标题行 / 视图栏 / 右上角 × / 设置项占位全撤）",
        nav is not None and back is not None
        and abs(nav.y()) <= 1
        and abs(nav.width() - inspector.width()) <= 1
        and abs(nav.height() - PANEL_HEADER_H) <= 1
        and not any(stale.values()),
        f"nav={nav is not None} back={back is not None} "
        + " ".join(f"{k}={v}" for k, v in stale.items()),
    )
    check(
        "返回键已加大并挪到面板左上（40 > 原来那枚 × 的 32）",
        back.isVisible()
        and abs(back.width() - BACK_BUTTON) <= 1
        and abs(back.height() - BACK_BUTTON) <= 1
        and back.x() < inspector.width() / 2
        and abs(back.y() + back.height() / 2 - nav.height() / 2) <= 1,
        f"back=({back.x():.1f},{back.y():.1f}) "
        f"{back.width():.0f}x{back.height():.0f} "
        f"nav={nav.width():.0f}x{nav.height():.0f}",
    )
    check(
        "面板中部整块留给设置项（顶到导航条下沿、压住常驻条上沿）",
        body is not None
        and abs(body.y() - (nav.y() + nav.height())) <= 1
        and abs(body.y() + body.height() - footer.y()) <= 1,
        f"body={None if body is None else (body.y(), body.height())} "
        f"nav.bottom={nav.y() + nav.height():.1f} footer.y={footer.y():.1f}",
    )

    name_label = _find_named(content_root, "editorInspectorName")
    size_label = _find_named(content_root, "editorInspectorSize")
    zoom_label = _find_named(content_root, "editorZoomLabel")
    check(
        "常驻条写着被点中的组件名与自身尺寸（如「工具栏 318 × 62」）",
        name_label is not None and str(name_label.property("text")) != ""
        and size_label is not None
        and str(size_label.property("text")) == f"{round(sw)} × {round(sh)}",
        f"name={None if name_label is None else name_label.property('text')!r} "
        f"size={None if size_label is None else size_label.property('text')!r} "
        f"期望尺寸={round(sw)} × {round(sh)}",
    )
    check(
        "常驻条百分比 = 相机比例（屏幕坐标系 1:1，100% 即真实像素）",
        zoom_label is not None
        and str(zoom_label.property("text")) == f"{round(plane.scale() * 100)}%",
        f"label={None if zoom_label is None else zoom_label.property('text')!r} "
        f"scale={plane.scale():.4f}",
    )

    # ----------------------------------------------------- 手动档位 / 平移钳制
    editor.setProperty("autoScale", False)
    editor.setProperty("manualScale", 1.0)
    _settle()
    check(
        "手动档位接管相机（100% = 真实像素大小）",
        abs(plane.scale() - 1.0) <= 1e-3,
        f"scale={plane.scale():.4f}",
    )

    editor.setProperty("manualScale", 99.0)
    _settle()
    check(
        "手动档位有上限钳制",
        plane.scale() <= ZOOM_MAX + 1e-6,
        f"scale={plane.scale():.4f}（上限 {ZOOM_MAX}）",
    )

    editor.setProperty("panDX", 99999.0)
    editor.setProperty("panDY", 99999.0)
    _settle()
    check(
        "拖动平移被钳制（画面不许从视口里拖出空档）",
        plane.x() <= 0.5 and plane.y() <= 0.5,
        f"plane=({plane.x():.1f},{plane.y():.1f})",
    )

    # ---------------------------------------------------------------- 退出编辑态
    editor.clearSelection()  # 走真实出口（面板 × / Esc 也调它）
    _settle()
    check(
        "退出编辑态：面板收起、暗罩消失、比例回到全景",
        editor.property("selectedCorner") == ""
        and not inspector.isVisible()
        and float(dim.property("opacity") or 0) <= 0.002
        and abs(plane.scale() - fit) <= 1e-3,
        f"panelVisible={inspector.isVisible()} dimOpacity={dim.property('opacity')} "
        f"scale={plane.scale():.4f} fit={fit:.4f}",
    )

    # --------------------------------------------- 真机点击链路（合成鼠标事件）
    # ``dockAt`` 只验了寻址；这一条走完整链路：
    # 窗口上的鼠标按下 → MouseArea → 命中测试 → 选中 → 相机聚焦 / 面板展开。
    # （点控制条**不能**真的去翻 PPT —— 屏蔽层就是为了这个，见 QML 注释。）
    origin = viewport.mapToItem(content_root, QPointF(0, 0))

    def _click_viewport(vx: float, vy: float) -> None:
        QTest.mouseClick(editor, Qt.LeftButton, Qt.NoModifier,
                         QPoint(int(round(origin.x() + vx)), int(round(origin.y() + vy))))

    _click_viewport(plane.x() + (sx + sw / 2) * plane.scale(),
                    plane.y() + (sy + sh / 2) * plane.scale())
    _settle()
    check(
        "在窗口上真的点一下控制条 → 进入编辑态",
        str(editor.property("selectedCorner")) == corner_name
        and editor.property("editing") is True,
        f"selectedCorner={editor.property('selectedCorner')!r}（期望 {corner_name!r}）",
    )

    _click_viewport(viewport.width() / 2, viewport.height() / 2)
    _settle()
    check(
        "点画面空白处 → 回到全景（不会卡在编辑态）",
        str(editor.property("selectedCorner")) == ""
        and editor.property("editing") is False
        and abs(plane.scale() - fit) <= 1e-3,
        f"selectedCorner={editor.property('selectedCorner')!r} "
        f"scale={plane.scale():.4f} fit={fit:.4f}",
    )

    # 快捷键：Esc 退出编辑态、Ctrl+= / Ctrl+- 调档、Ctrl+0 回自动档
    # （``Shortcut`` 不是 ``Item``，在 ``FluentWindowBase`` 里得包一层宿主 Item ——
    #  包错的话这里会直接抛「Cannot assign QObject to QQuickItem* list」。）
    _click_viewport(plane.x() + (sx + sw / 2) * plane.scale(),
                    plane.y() + (sy + sh / 2) * plane.scale())
    _settle()

    # 真机拖动平移：合成「按下 → 移动 → 抬起」，画面要跟着走**同样的距离**。
    # 这条是冲着「自己拖自己」的经典坑去的：屏蔽层跟着 planeLayer 一起缩放平移，
    # 用 ``mouse.x`` 算增量会被自身的位移抵消掉，表现为画面**半速跟手**
    # —— 所以 QML 里走场景坐标（``scenePosition``）。
    before_x, before_y = plane.x(), plane.y()
    from_x = int(round(origin.x() + viewport.width() / 2))
    from_y = int(round(origin.y() + viewport.height() / 2))
    QTest.mousePress(editor, Qt.LeftButton, Qt.NoModifier, QPoint(from_x, from_y))
    QTest.mouseMove(editor, QPoint(from_x + 60, from_y + 40))
    QTest.mouseRelease(editor, Qt.LeftButton, Qt.NoModifier,
                       QPoint(from_x + 60, from_y + 40))
    _settle()
    check(
        "拖动平移 1:1 跟手（不是半速，也没被吞掉）",
        abs(plane.x() - before_x - 60) <= 3 and abs(plane.y() - before_y - 40) <= 3,
        f"位移=({plane.x() - before_x:.1f},{plane.y() - before_y:.1f}) 期望=(60,40)",
    )

    # ⚠️ QML 的 ``Shortcut`` 默认 context 是 ``WindowShortcut`` —— 窗口**不活跃**
    #    时按键进不来（自检是在后台跑的，窗口偶尔拿不到焦点，实测偶发漏一次）。
    #    所以先 ``requestActivate()``，必要时再补一次。
    for _attempt in range(3):
        editor.requestActivate()
        QTest.keyClick(editor, Qt.Key_Escape)
        _settle()
        if str(editor.property("selectedCorner")) == "":
            break
    check(
        "Esc 退出编辑态",
        str(editor.property("selectedCorner")) == "",
        f"selectedCorner={editor.property('selectedCorner')!r} active={editor.isActive()}",
    )

    # ------------------------------------------------------------ 亚克力背景
    check(
        "编辑器窗口声明了 RinUI 的按窗口 backdrop 钩子",
        editor.property("backdropEnabled") is True,
        f"backdropEnabled={editor.property('backdropEnabled')}",
    )
    check(
        "亚克力已打到窗口句柄上",
        editor.property("acrylicActive") is True,
        f"acrylicActive={editor.property('acrylicActive')}",
    )
    # 回读 DWM 属性 —— 「调用没抛异常」不等于「系统真的记下了」。
    # 截屏只能看「像不像」，这一条能看「是不是」。
    # ``DWMWA_SYSTEMBACKDROP_TYPE`` = 38，``DWMSBT_TRANSIENTWINDOW`` = 3（Acrylic）。
    backdrop = ctypes.c_int(-1)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(int(editor.winId())), ctypes.c_uint(38),
        ctypes.byref(backdrop), ctypes.sizeof(backdrop),
    )
    check(
        "DWM 回读确认背景材质 = Acrylic(3)",
        backdrop.value == 3,
        f"回读 {backdrop.value}（0=None 2=Mica 3=Acrylic 4=Tabbed）",
    )
    plate = _find_named(content_root, "editorTitleBarPlate")
    title_height = float(editor.property("titleBarHeight") or 0)
    check(
        "标题栏有不透明底板（「除标题栏外才是亚克力」的那一条）",
        plate is not None and title_height > 0
        and abs(plate.height() - title_height) <= 0.6
        and plate.y() == 0,
        "没找到底板" if plate is None else
        f"plate={(plate.x(), plate.y(), plate.width(), plate.height())} "
        f"titleBarHeight={title_height}",
    )

    area = QGuiApplication.primaryScreen().availableGeometry()
    check(
        "主界面编辑器位于屏幕内",
        area.left() <= editor.x()
        and editor.x() + editor.width() <= area.right() + 1
        and area.top() <= editor.y()
        and editor.y() + editor.height() <= area.bottom() + 1,
        f"pos=({editor.x()},{editor.y()}) "
        f"size={editor.width()}x{editor.height()} area={area}",
    )

    # 与设置 / 调试窗口同一条约定：由 RinUI 接管（否则没有系统阴影 / 圆角 / Snap，
    # 而且 WS_CAPTION 会露一条原生标题栏压在自绘标题栏上）
    hwnd = int(editor.winId())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    filter_hwnds = {int(h) for h in app.rinui.win_event_filter.hwnds.values()}
    theme_hwnds = {int(h) for h in app.rinui.theme_manager.windows}
    check(
        "主界面编辑器已交给 RinUI 管（WS_CAPTION|WS_THICKFRAME + 名单）",
        bool(style & 0x00C00000)
        and bool(style & 0x00040000)
        and hwnd in filter_hwnds
        and hwnd in theme_hwnds,
        f"style=0x{style:08X} hwnd={hwnd} "
        f"filter={'Y' if hwnd in filter_hwnds else 'N'} "
        f"theme={'Y' if hwnd in theme_hwnds else 'N'}",
    )

    app.backend.closeMainEditor()
    check("主界面编辑器可关闭", not editor.isVisible())
    app.windows.show_editor()
    check(
        "编辑器只隐藏不销毁（再开复用同一实例）",
        app.windows.editor is editor and editor.isVisible(),
        "实例被重建了" if app.windows.editor is not editor else "",
    )
    app.backend.closeMainEditor()

    # 导航改名：字面量容易改一半（改了导航没改页面，或反过来），所以两头都钉
    settings = app.windows.settings
    items = settings.property("navigationItems") if settings is not None else None
    # ⚠️ ``navigationItems`` 是 QML 的 ``property var``，PySide 侧拿到的是
    # **QJSValue**，不能直接迭代（会抛 ``TypeError: object is not iterable``）。
    # 而 QTimer 槽里抛出的异常不会退出事件循环 —— 表现为进程挂着不动、日志也停了，
    # 排查方向很容易跑偏（2026-10-01 真踩到）。这里统一转成 Python 对象。
    if hasattr(items, "toVariant"):
        items = items.toVariant()
    rows = [i for i in (items or []) if hasattr(i, "get")]
    titles = [str(row.get("title")) for row in rows]
    pages = [str(row.get("page")) for row in rows]
    check(
        "设置导航含「主界面」且指向 MainInterface.qml",
        "主界面" in titles and any("MainInterface.qml" in p for p in pages),
        f"titles={titles}",
    )
    check("设置导航已无「外观」项", "外观" not in titles, f"titles={titles}")


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
        #
        # ⚠️ 这里的容差（24 / 40）本来是给「定位时窗口几何还没稳定」兜底的：
        # 面板**第一次 show() 之前**，Qt 报的几何是 387x453（带无边框窗口的
        # resize 边框余量），而 QML 声明的是 375x440，于是定位用的尺寸快照比
        # 最终尺寸大十几像素。2026-10-01 已在 `windows.py::_position_panel`
        # 里改成读 QML 的 `panelWidth` / `panelHeight`（根因修复），首次弹窗
        # 现在直接用 375x440 算位置。容差保留作安全网。
        center_x = panel.x() + panel.width() // 2
        horiz_ok = (
            abs(center_x - cursor.x()) <= 24
            or panel.x() <= area.left() + 40
            or panel.x() + panel.width() >= area.right() - 40
        )
        # 纵向第三条是「翻转到光标上方后被夹到屏幕上边」的合法结果：
        # 光标在屏幕下半、面板 440 高 + 30 偏移上下都塞不下时，`_position_panel`
        # 会把它贴到顶边（y = area.top() + margin）。缺这一条就会在光标靠近
        # 屏幕中部偏下时假失败。
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
            top_gap = dock.y()
            near_left = left_gap <= 64
            near_right = right_gap <= 64
            near_bottom = bottom_gap <= 64
            if corner.startswith("middle"):
                # 竖版两侧翻页：贴左右边 + **垂直居中**（上下余量对称）
                expected_vertical = abs(top_gap - bottom_gap) <= 2
            else:
                expected_vertical = near_bottom
            if corner.endswith("center"):
                # 居中：左右余量对称（后面还有一条专门的居中断言，这里只兜底）
                expected_horizontal = abs(left_gap - right_gap) <= 2
            else:
                expected_horizontal = near_left if corner.endswith("left") else near_right
            check(
                f"控制条 {corner} 贴角",
                expected_horizontal and expected_vertical,
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
        for corner, edge in (("middle_left", "left"), ("middle_right", "right")):
            dock = app.windows._docks.get(corner)
            if dock is None:
                continue
            shadow = int(dock.property("shadowMargin") or 0)
            visual_h = (dock.x() + shadow if edge == "left"
                        else geom.width() - (dock.x() + dock.width() - shadow))
            check(
                f"竖版翻页 pill {corner} 视觉贴边距离 = 配置的水平边距",
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

        # ---- 开发中水印（开发者开关，不进设置页）----
        wm_item = overlay.property("watermarkItem")
        check(
            "开发水印已挂到顶层窗口（左下角）",
            wm_item is not None and wm_item.isVisible(),
            str(type(wm_item).__name__ if wm_item is not None else None),
        )
        check("开发水印开关 = 配置 app.dev_watermark",
              app.backend.devWatermark == (app.config.get("app.dev_watermark") is not False),
              f"backend={app.backend.devWatermark} config={app.config.get('app.dev_watermark')}")
        if app.windows._region_mode and wm_item is not None:
            # 区域塑形模式下，水印若没被算进区域就会整块被裁掉（踩过思路盲区）
            wm_local = app.windows._watermark_rect_local()
            rects = app.windows._dock_rects_local()
            covered = False
            if wm_local is not None:
                from PySide6.QtCore import QRect as _QRect
                wr = _QRect(*wm_local)
                covered = any(wr.intersects(_QRect(*r)) for r in rects)
            check("开发水印在窗口区域内（区域塑形下可见）", covered,
                  f"wm={wm_local} rects={len(rects)}")

        # ---- 工具栏恒横向（下中部）+ 翻页栏独立在两侧（默认：竖版）----
        corners_cfg = app.config.get("presentation.corners", {}) or {}
        center_groups = (corners_cfg.get("bottom_center") or {}).get("groups", [])
        check("工具栏在下中部且不含翻页组",
              "tools" in center_groups and "pager" not in center_groups,
              str(center_groups))
        # 竖版两侧（middle_*）与底部横版（bottom_*）二选一，同时开会四个翻页栏
        side_on = [(corners_cfg.get(c) or {}).get("enabled", False)
                   for c in ("middle_left", "middle_right")]
        bottom_on = [(corners_cfg.get(c) or {}).get("enabled", False)
                     for c in ("bottom_left", "bottom_right")]
        check("翻页栏形态二选一（竖版两侧 或 底部横版，不并存）",
              any(side_on) != any(bottom_on),
              f"middle={side_on} bottom={bottom_on}")
        for corner in ("middle_left", "middle_right"):
            check(f"{corner} 翻页组",
                  ((corners_cfg.get(corner) or {}).get("groups", [])) == ["pager"],
                  str((corners_cfg.get(corner) or {}).get("groups", [])))
        cdock = app.windows._docks.get("bottom_center")
        ldock = app.windows._docks.get("middle_left")
        rdock = app.windows._docks.get("middle_right")
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
            "两侧翻页 pill 等大且是竖版（同一套组件，宽 < 高）",
            ldock is not None and rdock is not None
            and abs(rdock.height() - ldock.height()) <= 1
            and abs(rdock.width() - ldock.width()) <= 1
            and ldock.width() < ldock.height()
            and rdock.x() > ldock.x(),
            f"left={ldock.width() if ldock else '?'}x{ldock.height() if ldock else '?'} "
            f"right={rdock.width() if rdock else '?'}x{rdock.height() if rdock else '?'}",
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
                "竖版翻页 pill = 横版 pill 转置（62×180，同一行账：4+44+8+68+8+44+4）",
                ldock.width() - lshadow * 2 == 62 and ldock.height() - lshadow * 2 == 180,
                f"{ldock.width() - lshadow * 2}x{ldock.height() - lshadow * 2}",
            )
            check(
                "CW2 同款渐变边框高光已开（翻页 pill）",
                ldock.property("highlightEnabled") is True
                and ldock.property("highlightRingVisible") is True,
                f"enabled={ldock.property('highlightEnabled')} "
                f"ring={ldock.property('highlightRingVisible')}",
            )
            check(
                "竖版翻页 pill 垂直居中（上下余量对称）",
                abs(ldock.y() - (geom.height() - ldock.height() - ldock.y())) <= 2,
                f"y={ldock.y()} h={ldock.height()} screen={geom.height()}",
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

        # ---- 多软件族（kind）路由：照 Luminalium 1 的 ppt / wps / yozo 三分 ----
        # 这是「换台电脑就控制不了」的主因：判不出族就选不对快捷键通道，
        # 给 WPS 下 PowerPoint 专属的 MSO 命令只会白等一轮。
        kind_cases = [
            ("screenClass", "POWERPNT.EXE", "演示文稿1", "ppt"),
            ("wppSlideShowWindowClass", "wpp.exe", "x", "wps"),
            ("WPP SlideShow Window 8.0", "wps.exe", "x", "wps"),
            ("YozoSlideShow", "yozopg.exe", "x", "yozo"),
            ("SomeUnknownClass", "powerpnt.exe", "x", "ppt"),  # 类名不认识时靠进程名
        ]
        kind_bad = [
            (cls, proc, wanted, ppt_controller._kind_from_window(cls, proc, title))
            for cls, proc, title, wanted in kind_cases
            if ppt_controller._kind_from_window(cls, proc, title) != wanted
        ]
        check(
            "软件族判定（类名 → 进程名，PowerPoint / WPS / 永中）",
            not kind_bad,
            f"错误 {len(kind_bad)} 例: {kind_bad}" if kind_bad else
            "，".join(f"{c}->{ppt_controller._kind_from_window(c, p, t)}"
                      for c, p, t, _w in kind_cases),
        )
        # 各族**必须有**的快捷键：Pen 只有 ppt/wps 有（Ctrl+P），
        # 永中只发它认得的 E/A —— 给永中发 Ctrl+P 是无效动作。
        check(
            "快捷键通道按族区分（永中不发 Ctrl+P）",
            all(v["arrow"] == ord("A") and v["eraser"] == ord("E")
                for v in ppt_controller.KIND_TOOL_SHORTCUTS.values())
            and "pen" in ppt_controller.KIND_TOOL_SHORTCUTS["ppt"]
            and "pen" in ppt_controller.KIND_TOOL_SHORTCUTS["wps"]
            and "pen" not in ppt_controller.KIND_TOOL_SHORTCUTS["yozo"],
            str({k: {n: chr(v) for n, v in t.items()}
                 for k, t in ppt_controller.KIND_TOOL_SHORTCUTS.items()}),
        )
        # 指针重试阶梯必须与 L1 逐字一致（省掉重试 = 笔/橡皮切换时好时坏的根源）
        check(
            "指针切换重试阶梯 = Luminalium 1 原值",
            ppt_controller.L1_POINTER_RETRY_DELAYS == (0.0, 0.08, 0.16, 0.28),
            str(ppt_controller.L1_POINTER_RETRY_DELAYS),
        )
        # 指针语义必须与 COM 的 PpSlideShowPointerType 对齐（arrow=1 pen=2 eraser=3）
        check(
            "工具 -> 指针类型映射 = PpSlideShowPointerType",
            (ppt_controller.TOOL_TO_POINTER["none"],
             ppt_controller.TOOL_TO_POINTER["arrow"],
             ppt_controller.TOOL_TO_POINTER["pen"],
             ppt_controller.TOOL_TO_POINTER["eraser"]) == (0, 1, 2, 3),
            str(ppt_controller.TOOL_TO_POINTER),
        )
        # 墨迹调色板必须与 L1 的 InkColorPicker 网格逐格一致：这张表是**坐标表**
        # （行 0/1、列 0..9），少一格或多一格都会让键盘走位整体错位、点错颜色。
        palette_source = (ROOT / "ui" / "Luminalium" / "Lumi.qml").read_text(encoding="utf-8")
        palette_body = palette_source.split("readonly property var inkPalette:", 1)[-1].split("]", 1)[0]
        palette = [token.strip().strip('"') for token in palette_body.replace("[", "").split(",")
                   if token.strip().startswith('"')]
        expected_palette = [
            "#FFFFFF", "#000000", "#E7E6E6", "#44546A", "#4472C4",
            "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47",
            "#C00000", "#FF0000", "#FFFF00", "#92D050", "#00B050",
            "#00B0F0", "#0070C0", "#002060", "#7030A0",
        ]
        check(
            "墨迹调色板 = L1 InkColorPicker 网格（顺序即行列坐标）",
            [c.upper() for c in palette] == expected_palette,
            f"{len(palette)} 色" + ("" if [c.upper() for c in palette] == expected_palette
                                    else f"，期望 {len(expected_palette)} 色"),
        )
        # 切指针前必须先把放映窗口拉到前台 —— PowerPoint 的 View.PointerType
        # 只对前台放映窗口生效，漏这一步「橡皮点了没反应」（2026-09-25 用户报障）。
        # 用源码断言：set_pointer 内出现 focus_slideshow_window 调用。
        ctrl_src = (ROOT / "app" / "ppt_controller.py").read_text(encoding="utf-8")
        set_pointer_body = ctrl_src.split("def set_pointer(", 1)[-1].split("def ", 1)[0]
        check(
            "切指针前先拉放映窗口到前台（L1 _focus_slideshow_window）",
            "focus_slideshow_window(" in set_pointer_body,
            "set_pointer 缺少 focus_slideshow_window 前置调用",
        )
        check(
            "前台激活辅助函数存在",
            hasattr(ppt_controller, "focus_slideshow_window"),
            "缺少 focus_slideshow_window",
        )
        # 页码刷新必须走轻量路径（跳过描述 / 墨迹色两次诊断读），否则命令后
        # 页码要多等一个 COM 周期，观感就是「页码识别迟钝」。
        refresh_body = ctrl_src.split("def _refresh_snapshot(", 1)[-1].split("def ", 1)[0]
        check(
            "_refresh_snapshot 支持轻量刷新（light）",
            "light: bool = False" in refresh_body and "if light:" in refresh_body,
            "缺少 light 参数分支",
        )
        # 轻量刷新走 read_position（只读当前页），不重读总页数 —— 总页数在场内是常量
        check(
            "COM 后端提供轻量页码读 read_position",
            hasattr(ppt_controller._ComBackend, "read_position"),
            "缺少 _ComBackend.read_position",
        )
        # ⚠️ SlideShowWindows 绝不能直接属性访问：动态绑定下它会抛 AttributeError
        # （真机日志里刷屏的那条），必须走 getattr 安全取 + _safe_count。
        # 这条断言锁住「不许再写回 app.SlideShowWindows.Count」。
        # 先剔除 docstring / 注释，只留下真正的代码文本再断言。
        import io as _io
        import tokenize as _tokenize
        code_parts = []
        for _tok in _tokenize.generate_tokens(_io.StringIO(ctrl_src).readline):
            if _tok.type not in (_tokenize.STRING, _tokenize.COMMENT):
                code_parts.append(_tok.string)
        code_only = " ".join(code_parts)
        check(
            "无 bare `app.SlideShowWindows` 直接访问（必须 getattr 兜底）",
            "app.SlideShowWindows" not in code_only,
            "又出现了直接属性访问，动态绑定下会抛 AttributeError",
        )
        check(
            "SlideShowWindows 改用 _slideshow_windows() 取集合",
            "_slideshow_windows(" in ctrl_src and "_safe_count(" in ctrl_src,
            "缺少 _slideshow_windows / _safe_count",
        )
        # 取不到集合时要能换一个新引用再试（半吊子 COM 引用重取常可修好）
        check(
            "_attached 支持 force_refresh（换新引用补救）",
            "force_refresh" in ctrl_src,
            "缺少 force_refresh 参数",
        )

        # ---- 设置窗口（懒创建）----
        check("设置窗口尚未创建", app.windows.settings is None)
        app.windows.show_settings()
        settings = app.windows.settings
        check("设置窗口已创建", settings is not None)
        if settings is not None:
            # 设置窗口的水印：FluentWindow 内容走 default property
            # （freeContainter），匿名 QML 类型的 type 名是 QQuickItem，
            # 只能用「自定义属性 shown」来认它。断言它在窗口边界内 ——
            # 曾把 leftMargin 用成 navigationView.width（那是整窗宽度的
            # 内部项），水印被推到窗口外只剩一条边（2026-09-25）。
            def _find_wm(item):
                for child in item.childItems():
                    if child.property("shown") is not None:
                        return child
                    found = _find_wm(child)
                    if found is not None:
                        return found
                return None

            wm_st = _find_wm(settings.contentItem())
            check(
                "设置窗口水印存在且在窗口边界内",
                wm_st is not None
                and wm_st.x() >= 0
                and wm_st.x() + wm_st.width() <= settings.width()
                and wm_st.y() + wm_st.height() <= settings.height(),
                "未找到" if wm_st is None else
                f"pos=({wm_st.x()},{wm_st.y()}) size={wm_st.width()}x{wm_st.height()}",
            )
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
            # Win32 原生边框：**2026-09-30 起由 RinUI 接管**，不再自己摘 flags。
            #
            # RinUI 的窗口外观全靠两处 Win32 侧代码：WinEventFilter 处理
            # WM_NCCALCSIZE（把非客户区压掉 → 视觉上只剩 RinUI 自绘标题栏）＋
            # 处理 WM_NCHITTEST（8px resize 边框 / 拖动）；ThemeManager 按 hwnd
            # 逐个设 DWM 属性（阴影 / 圆角 / 暗色 / backdrop）。两份名单都只在
            # launcher.load() 那一刻确定，Python 侧另建的窗口必须靠
            # WindowManager._attach_to_rinui 补登记。
            #
            # 所以这里断言的是「三件事同时成立」：style 必须带
            # WS_CAPTION|WS_THICKFRAME（DWM 阴影与系统 resize 的前提）＋ hwnd 必须
            # 在 WinEventFilter 与 ThemeManager 的名单里（否则前者没人压非客户区，
            # 后者没有阴影/圆角）。只满足前一半就是当初那个 bug：CAPTION 加上却
            # 没人处理，真的画出一条原生标题栏压在自绘标题栏上。
            settings_hwnd = int(settings.winId())
            user32b = ctypes.windll.user32
            style = user32b.GetWindowLongW(settings_hwnd, -16) & 0xFFFFFFFF
            filter_hwnds = {int(h) for h in app.rinui.win_event_filter.hwnds.values()}
            theme_hwnds = {int(h) for h in app.rinui.theme_manager.windows}
            corner = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                settings_hwnd, ctypes.c_uint(33), ctypes.byref(corner), ctypes.sizeof(corner)
            )
            check(
                "设置窗口已交给 RinUI 管（WS_CAPTION|WS_THICKFRAME）",
                bool(style & 0x00C00000) and bool(style & 0x00040000),
                f"style=0x{style:08X} WS_CAPTION={'Y' if style & 0x00C00000 else 'N'} "
                f"WS_THICKFRAME={'Y' if style & 0x00040000 else 'N'}",
            )
            check(
                "设置窗口在 WinEventFilter / ThemeManager 名单里",
                settings_hwnd in filter_hwnds and settings_hwnd in theme_hwnds,
                f"hwnd={settings_hwnd} filter={'Y' if settings_hwnd in filter_hwnds else 'N'} "
                f"theme={'Y' if settings_hwnd in theme_hwnds else 'N'}",
            )
            check(
                "设置窗口有 DWM 圆角（corner_preference=Round）",
                corner.value == 2,
                f"corner={corner.value}（0=Default / 2=Round）",
            )
            app.backend.settingsCloseRequested.emit()
            check("设置窗口可关闭", not settings.isVisible())

            # 打开指定设置页（快捷方式「放映控制」走的路径）
            app.windows.show_settings("settings/Presentation.qml")
            check("能跳到指定设置页", settings.isVisible())
            app.backend.settingsCloseRequested.emit()

        # ---- 调试窗口（隐藏入口：设置标题连点 10 次）----
        # 调试项 2026-09-30 从设置导航移出、改成独立窗口，入口是压在 RinUI 标题
        # 文本上的一块透明热区。热区位置靠「返回按钮 40 + 间距 16 + 图标 16 +
        # 间距 16 = 88」推算 —— RinUI 一旦改内边距，热区就会点不到标题文字，
        # 所以这里把几何关系钉成断言；否则表现为「连点没反应」且**没有任何报错**。
        def _find_item(item, predicate):
            for child in item.childItems():
                if predicate(child):
                    return child
                found = _find_item(child, predicate)
                if found is not None:
                    return found
            return None

        def _origin(window, item):
            point = item.mapToItem(window.contentItem(), QPointF(0, 0))
            return point.x(), point.y()

        if settings is not None:
            app.windows.show_settings()
            hotspot = _find_item(
                settings.contentItem(),
                lambda it: it.objectName() == "debugTitleHotspot",
            )
            check(
                "调试入口热区存在（压在标题文本上）",
                hotspot is not None,
                "" if hotspot is not None else "未找到 objectName=debugTitleHotspot 的项",
            )
            # 标题文字有**两个**候选：TitleBar 自带的那个（``titleEnabled: false``
            # 下不可见，但 ``text`` 仍等于窗口标题）和 NavigationBar 真正画出来的
            # 那个。必须带可见性筛选，否则会锚到那个隐形的上去。
            title_text = _find_item(
                settings.contentItem(),
                lambda it: it.property("text") == settings.property("title")
                and it.isVisible(),
            )
            if hotspot is not None and title_text is not None:
                hx, _hy = _origin(settings, hotspot)
                tx, _ty = _origin(settings, title_text)
                check(
                    "调试入口热区完整盖住标题文本",
                    hx <= tx and hx + hotspot.width() >= tx + title_text.width(),
                    f"hotspot x=[{hx:.0f},{hx + hotspot.width():.0f}] "
                    f"title x=[{tx:.0f},{tx + title_text.width():.0f}]",
                )
                # 同时不能压到左边的返回按钮，否则导航回退会被热区吃掉
                host = settings.property("titleBarLeadingHost")
                host_x = _origin(settings, host)[0] if host is not None else 0.0
                check(
                    "调试入口热区避开返回按钮（40 宽）",
                    hx >= host_x + 40,
                    f"hotspot.x={hx:.0f} 返回按钮右边缘={host_x + 40:.0f}",
                )
                # 真鼠标事件也要能落到热区上 —— 位置对不代表 MouseArea 真收得到：
                # 标题行压在它上层，全靠「Text 不吃鼠标事件」穿透过来。
                QTest.mouseClick(
                    settings,
                    Qt.LeftButton,
                    Qt.NoModifier,
                    QPoint(int(tx + 8), int(_ty + 8)),
                )
                check(
                    "真实鼠标点击落到标题热区上",
                    settings.property("debugTitleTapCount") == 1,
                    f"count={settings.property('debugTitleTapCount')}",
                )
            else:
                check("调试入口热区完整盖住标题文本", False, "热区或标题文本缺失")

            # 连点 10 次才开：补到 9 次仍不该有任何动静
            for _ in range(8):
                QMetaObject.invokeMethod(settings, "registerDebugTitleTap")
            check(
                "标题连点 9 次仍不开调试窗口",
                settings.property("debugTitleTapCount") == 9 and app.windows.debug is None,
                f"count={settings.property('debugTitleTapCount')}",
            )
            QMetaObject.invokeMethod(settings, "registerDebugTitleTap")
            debug_win = app.windows.debug
            check(
                "标题连点 10 次打开调试窗口",
                debug_win is not None and debug_win.isVisible(),
                "窗口未创建" if debug_win is None else f"visible={debug_win.isVisible()}",
            )
            if debug_win is not None:
                area = QGuiApplication.primaryScreen().availableGeometry()
                inside = (
                    area.left() <= debug_win.x()
                    and debug_win.x() + debug_win.width() <= area.right() + 1
                    and area.top() <= debug_win.y()
                    and debug_win.y() + debug_win.height() <= area.bottom() + 1
                )
                check(
                    "调试窗口位于屏幕内",
                    inside,
                    f"pos=({debug_win.x()},{debug_win.y()}) "
                    f"size={debug_win.width()}x{debug_win.height()} area={area}",
                )
                # 不能与设置窗口**完全**重合：屏幕窄的时候并排本就放不下，
                # 但至少要有偏移，否则看起来像「设置窗口被替换掉了」
                check(
                    "调试窗口与设置窗口错开（不完全重合）",
                    (debug_win.x(), debug_win.y()) != (settings.x(), settings.y()),
                    f"settings=({settings.x()},{settings.y()}) "
                    f"debug=({debug_win.x()},{debug_win.y()})",
                )
                # 调试窗口与设置窗口同一条约定：由 RinUI 接管（见上面那段长注释）
                debug_hwnd = int(debug_win.winId())
                style_b = (
                    ctypes.windll.user32.GetWindowLongW(debug_hwnd, -16) & 0xFFFFFFFF
                )
                filter_hwnds_b = {int(h) for h in app.rinui.win_event_filter.hwnds.values()}
                theme_hwnds_b = {int(h) for h in app.rinui.theme_manager.windows}
                check(
                    "调试窗口已交给 RinUI 管（WS_CAPTION|WS_THICKFRAME + 名单）",
                    bool(style_b & 0x00C00000)
                    and bool(style_b & 0x00040000)
                    and debug_hwnd in filter_hwnds_b
                    and debug_hwnd in theme_hwnds_b,
                    f"style=0x{style_b:08X} hwnd={debug_hwnd} "
                    f"filter={'Y' if debug_hwnd in filter_hwnds_b else 'N'} "
                    f"theme={'Y' if debug_hwnd in theme_hwnds_b else 'N'}",
                )
                app.backend.closeDebugWindow()
                check("调试窗口可关闭", not debug_win.isVisible())
            app.backend.settingsCloseRequested.emit()

        # ---- 主界面编辑器（独立窗口，入口是快捷面板的快捷方式）----
        # 放在快捷方式增删之前：那段会临时改动「已启用快捷方式」列表，
        # 先跑这条能确保它读到的是配置原样。
        _check_editor(app)

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

        # ---- 启动画面（设计稿「启动画面 Dark / Light」的还原）----
        # 真机里它由 ``application.run()`` 拉起；smoke 不走 run()（直接 exec），
        # 所以这里手动跑一遍完整生命周期。放在最后，免得那 1080×608 的卡片
        # 一直盖在屏幕上影响别的检查。
        _check_splash(app)
        # 收尾（统计失败数 / 退出事件循环）统一由 run_checks_guarded 的
        # ``finally`` 负责 —— 这里再写一遍只会在抛异常时被跳过，反而留坑。

    def run_checks_guarded() -> None:
        """跑一遍自检，**无论成败都退出事件循环**。

        自检里任何一步抛异常都不能让进程挂在 ``exec()`` 里 —— QTimer 槽里抛出的
        异常不会终止事件循环（PySide 只打一份 traceback），症状是「进程还在、
        CPU 也不高、日志停在某一句」，看起来像卡死，排查方向很容易跑偏。
        2026-10-01 因为 ``navigationItems`` 拿到 QJSValue 抛过 ``TypeError``，
        正是这个表现。
        """
        nonlocal failures
        try:
            run_checks()
        except Exception:
            traceback.print_exc()
            RESULTS.append("[FAIL] 自检过程抛出异常（见上方 traceback）")
        finally:
            failures = sum(1 for line in RESULTS if line.startswith("[FAIL]"))
            qt_app.quit()

    QTimer.singleShot(900, run_checks_guarded)
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
