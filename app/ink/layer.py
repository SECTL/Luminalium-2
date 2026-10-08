"""自建墨迹层的 QML 类型 ``InkLayer``（``import Luminalium.Ink 1.0``）。

2026-10-07 用户指令：自建批注替代 COM 笔/橡皮（计划 self-ink 第 4 项：渲染核心）。

为什么是 ``QQuickItem`` 自己出场景图节点，而不是 Canvas / QQuickPaintedItem / Shapes：
选型见 ``.omo/notepads/self-ink/learnings.md`` —— Canvas 在 Qt6 忽略 FramebufferObject、
每帧整块上传纹理；PaintedItem 每次 update 整图上传；Shapes 的 CurveRenderer 不支持
自相交路径（手写笔画天天自相交）。三条都扛不住放映时的连续书写，所以这里分两层：

* 干墨迹（已落笔的笔画）：GUI 线程用 QPainter 烘焙进一张本页 QImage（设备像素分辨率），
  经 ``createTextureFromImage`` 交给 ``QSGSimpleTextureNode``。抬笔时只把**这一笔**
  增量画进现有图；翻页 / 撤销 / 重做 / 清屏 / 尺寸或 DPR 变化才整页重烘。
  像素橡皮笔画按列表顺序用 ``CompositionMode_Clear`` 回放（模型头注释第 3 条）。
* 湿墨迹（正在写的这一笔）：``QSGGeometryNode`` + ``QSGVertexColorMaterial``，网格由
  ``tessellate.WetMesh`` 随来点增量追加，外圈 1 设备像素的顶点 alpha 羽化做抗锯齿。
  干湿共用 ``tessellate.radius_of`` 与同一套「圆 + 梯形」形状，抬笔那一帧不跳。
  像素橡皮没有湿网格：擦除时直接在「落笔前的干图副本」上重放已有的擦除轨迹，所见即所得。

线程与所有权（PySide6 下踩一次就是闪退，务必守住）：
1. 场景图节点只在 ``updatePaintNode``（渲染线程，GUI 线程此时阻塞在 sync）里创建和修改。
   GUI 线程只把「新的湿网格字节 / 新的干图」放进 ``_pending_*``，在 ``_lock`` 内交接。
2. 我们创建的 QSGGeometry / 材质 / 纹理 / 节点一律在 self 上持有 Python 引用：PySide 不
   知道场景图还在用它们，丢了引用就被 GC 释放，下一帧渲染线程踩野指针。几何与材质不设
   OwnsGeometry / OwnsMaterial，纹理 ``setOwnsTexture(False)``：所有权留在 Python，避免
   C++ 与 Python 各删一次。``defaultAttributes_ColoredPoint2D()`` 返回的 AttributeSet 也要挂在
   self 上：QSGGeometry 只存它的引用，临时对象回收后顶点颜色读成乱码、渲染线程访问冲突（实测）。
5. 湿几何「清空」不用 ``allocate(0)``，而是留 3 个全零顶点的退化三角形：顶点数归零后节点掉出
   批次，下一笔湿墨迹整条不画（实测）。单个几何节点顶点数超过 65535 时超出部分不画，所以湿网格
   按 ``WET_CHUNK_VERTICES`` 分块到多个节点（共用一份无状态材质）。
3. 场景图失效（窗口隐藏释放资源 / 重建）时 ``sceneGraphInvalidated`` 在渲染线程直连回调，
   在那里丢掉纹理等引用；下次 ``old_node is None`` 时用 ``_shown_*`` 重新上传。
4. 改完几何必须 ``markDirty(DirtyGeometry)``，换纹理 ``DirtyMaterial``，否则渲染器沿用旧批次。

空闲零帧：``update()`` 只在新点到达或模型变化时调用，统一走 ``_request_update``，
每次给 ``_update_requests`` +1，性能 QA 用它证明无输入期间一次都没请求重绘。

输入接线（计划 self-ink 第 5 项）：鼠标 / 触屏 / 平板三种事件在文末「输入接线」节
接进 ``smoothing.StrokeSmoother``，滤波抽稀后喂上面这组 begin/extend/end —— 外部
（QA 合成事件、todo 7 的状态流）也可以绕过事件直调这组 API，两条路同一个模型。
几条定死的取舍：

* arrow 态在事件层再拒一次输入：窗口穿透（WS_EX_TRANSPARENT）是唯一防线，QA
  直投事件、或穿透意外失效时也不能出墨；写到一半切回指针则把手上这笔落掉。
* 触屏只跟第一个触点（指笔画）：多指并发会把滤波状态互相拉扯，先不做多指同书。
  抬笔判定看触点状态（Released）而非 TouchEnd 事件——TouchEnd 只在整组触点全抬时
  才发，多指先抬一根是 TouchUpdate 载着 Released 点来的，只看事件类型笔画会悬挂。
* ``QEventPoint.ellipseDiameters`` 对触屏事件里的**每个**触点都读（含没在画画的
  第二指——手掌擦除要看的恰恰是它），存 ``_last_contact_diameters`` 并回调
  ``_on_contact_sample`` 钩子（第 8 项手掌擦除在这里消费）；驱动不给直径时存 None，
  手掌擦除静默禁用，绝不影响笔画本身。
* 是否压感在落笔那一刻一次性定死（tablet 压力非零 / touch 压力在 0..1 开区间，
  鼠标恒无压感走速度模拟）：中途换语义会把锥度与宽度平滑的状态机搞劈叉。
* ``AA_CompressHighFrequencyEvents`` 的关断在 ``app.ink.configure_input_attributes()``，
  必须在 QApplication 创建前由各入口调用，晚了高回报率设备原始点流就被合并了。

橡皮与手掌擦除（计划第 8 项，2026-10-07）：

* 橡皮子模式 ``eraserMode``（词表跟 presentation.ink.eraser_mode 配置走）：
  ``pixel`` 像素擦除（默认，划过即擦，mode=erase 笔画进撤销栈）、``stroke`` 整笔
  擦除（命中即删整笔，走 model.hit_test + remove_strokes，撤销 = 恢复整笔；
  命中半径与像素橡皮同宽 = eraserWidth 的一半）。不产生笔画、不进湿墨迹。
* 像素橡皮的粗细 ``eraserWidth``（2026-10-08 用户指令：自建批注，配置档
  ``presentation.ink.eraser_widths``）：擦除笔画一律按它取宽，不再跟着
  ``penWidth`` 走 —— 橡皮的本职是快速抹掉一片，笔宽（默认 4px）擦大字标题
  要来回划好几趟。手掌擦除不受影响：它的宽度恒为接触直径（随接触面积走）。
  整笔擦除不画笔画、粗细本无从谈起，但命中半径跟着 ``eraserWidth`` 走，
  保住「命中半径与像素橡皮同宽」这条不变量（两种橡皮手感同一个大小）。
* 手掌擦除：触屏专属，**任意书写工具下**大接触面（直径 ≥ palmThresholdMm 毫米）
  或 ≥3 指同时接触即临时切像素擦除，擦除宽度 = 接触直径，抬起即回原工具 ——
  工具属性全程不动，还原是零成本的。状态切换不进撤销栈，擦除笔画本身与
  像素橡皮同栈（可 undo）。鼠标 / 平板路径永不触发；驱动不报接触直径则整个
  功能静默禁用并记一次日志。参数（开关 / 阈值毫米）由配置经
  palmEraseEnabled / palmThresholdMm 属性进来，毫米→像素的换算用屏幕物理 DPI
  在使用点现算（多屏各自正确）。
"""

from __future__ import annotations

import ctypes
import logging
import math
import threading
from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QEvent, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QColor, QEventPoint, QImage, QMouseEvent, QTabletEvent, QTouchEvent
from PySide6.QtQuick import (
    QQuickItem,
    QQuickWindow,
    QSGGeometry,
    QSGGeometryNode,
    QSGNode,
    QSGSimpleTextureNode,
    QSGTexture,
    QSGVertexColorMaterial,
)

from .model import PageStore, Point, Stroke, StrokeMode
from .smoothing import StrokeSmoother
from .tessellate import VERTEX_SIZE, WetMesh, bake, radius_of

log = logging.getLogger("luminalium.ink")

#: 合法工具名。与控制条 ``tool:<id>`` 动作同一套口径，QML 侧传别的值视为 bug。
TOOLS = ("pen", "eraser", "arrow")
#: 湿墨迹清空时保留的占位顶点数（一个零面积透明三角形），原因见 ``_upload_wet``。
WET_PLACEHOLDER_VERTICES = 3
#: 单个湿墨迹几何节点的顶点上限（3 的倍数，< 65536）。实测一个节点超过 65535 个顶点时，
#: 超出部分不画（5000 点长笔画后四分之一缺失），疑似渲染器按 16 位索引处理；分块后每块都在界内。
WET_CHUNK_VERTICES = 65532


def _device_has_pressure(device: str, pressure: float | None) -> bool:
    """落笔那一刻定整笔是否走压感宽度，中途不改（头注释「是否压感一次性定死」）。

    tablet：压力非零即压感设备（无压感笔恒报 0）。
    touch：0..1 开区间才算——无压感触屏普遍恒报 1.0 或 0，把 1.0 当压感会让整笔
    顶满宽度、还丢了速度锥度。
    mouse：永远速度模拟宽度（smoothing.py 头注释第 3 条）。
    """
    if device == "tablet":
        return pressure is not None and pressure > 0.0
    if device == "touch":
        return pressure is not None and 0.0 < pressure < 1.0
    return False


class InkLayer(QQuickItem):
    toolChanged = Signal()
    penColorChanged = Signal()
    penWidthChanged = Signal()
    #: 像素橡皮粗细变了（2026-10-08 自建批注；控制条橡皮卡片靠它回显选中档）
    eraserWidthChanged = Signal()
    eraserModeChanged = Signal()
    palmParamsChanged = Signal()
    #: 每次模型变动（落笔 / 撤销 / 重做 / 清屏）之后发出，供撤销按钮状态等刷新
    inkChanged = Signal()

    def __init__(self, parent: QQuickItem | None = None) -> None:
        super().__init__(parent)
        # 不打这个旗标，场景图永远不会回调 updatePaintNode —— 自绘节点的前提
        self.setFlag(QQuickItem.ItemHasContents, True)
        self._tool = "arrow"
        self._pen_color = QColor("#FFC000")
        self._pen_width = 4.0
        # 像素橡皮粗细（逻辑 px）。默认值与配置 ``presentation.ink.eraser_default_width``
        # 保持一致：层是懒创建的，用户放映前选的档在 Backend 会话态里，建窗时没人
        # 补推（与 penWidth 同一个读法 —— 会话状态不落配置、不进 _apply_ink_config）。
        self._eraser_width = 18.0

        self.store = PageStore()
        self._page = 0
        self._update_requests = 0

        # ---- GUI 线程状态
        self._image: QImage | None = None
        self._image_key: tuple[int, int, float] | None = None
        self._pts: list[Point] | None = None  # 进行中这一笔（归一化坐标）
        self._mode: StrokeMode = "pen"
        self._color = ""
        self._width = 0.0
        self._wet: WetMesh | None = None
        self._erase_base: QImage | None = None

        # ---- 交接区（_lock 保护）：None 表示「没有新东西」
        self._lock = threading.Lock()
        self._pending_wet: bytes | None = None
        self._pending_dry: QImage | None = None

        # ---- 渲染线程状态（只在 updatePaintNode / 失效回调里碰）
        self._shown_wet = b""
        self._shown_dry: QImage | None = None
        self._root: QSGNode | None = None
        self._dry_node: QSGSimpleTextureNode | None = None
        self._texture: QSGTexture | None = None
        self._wet_node: QSGGeometryNode | None = None
        self._wet_geom: QSGGeometry | None = None
        self._wet_mat: QSGVertexColorMaterial | None = None
        self._wet_attrs = None
        self._wet_nodes: list[QSGGeometryNode] = []
        self._wet_geoms: list[QSGGeometry] = []

        # ---- 输入接线（计划第 5 项）：事件 → StrokeSmoother → begin/extend/end，一笔一滤波器
        # 鼠标按工具开关（arrow=NoButton，见 _set_tool）；触屏恒接收、在处理器里按工具拒绝
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptTouchEvents(True)
        self._smoother: StrokeSmoother | None = None
        self._device: str | None = None  # 在途笔画的设备（mouse/touch/tablet），拦截异设备事件串扰
        self._touch_id = -1  # 正在跟的触点 id（只跟第一个触点）
        self._last_contact_diameters: tuple[float, float] | None = None  # todo 8 手掌擦除消费
        # ---- 橡皮子模式与手掌擦除（计划第 8 项）
        # eraser_mode 词表跟配置走（presentation.ink.eraser_mode）：pixel 像素 / stroke 整笔
        self._eraser_mode = "pixel"
        self._palm_erasing = False  # 手掌擦除进行中：触点临时以像素擦除干活，工具属性不动
        self._palm_erase_enabled = True
        self._palm_threshold_mm = 20.0
        self._palm_no_diameter_logged = False  # 驱动不报直径只记一次日志
        # ---- 工具卡「点空白收起」钩子（2026-10-08 用户报告：自建批注）
        # 笔/橡皮二级卡开着时，落在画布上的第一按要消费成「收起卡片」而不是起笔。
        # 卡片开没开只有控制条知道（QML 侧状态，层够不着），WindowManager 建窗后
        # 把 ``windows._dismiss_tool_cards`` 挂进来；返回 True = 有卡被收起、
        # 这一按不起笔。None（自检直造、窗口侧还没接线）= 老行为，按下直接起笔。
        self.card_dismiss_hook: Callable[[], bool] | None = None

        self.windowChanged.connect(self._on_window_changed)

    # ---------------------------------------------------------------- tool

    def _get_tool(self) -> str:
        return self._tool

    def _set_tool(self, value: str) -> None:
        if value not in TOOLS:
            # 不抛异常：QML 绑定里抛出去只会变成一行难查的警告，还会把旧值留着；
            # 记一条日志、维持原工具更可预期
            log.warning("InkLayer 收到未知工具 %r，保持 %s", value, self._tool)
            return
        if value == self._tool:
            return
        self._tool = value
        # arrow 态不接受任何输入：窗口穿透是唯一防线，事件投递层再关一道
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton if value in ("pen", "eraser") else Qt.MouseButton.NoButton
        )
        if value == "arrow" and self._smoother is not None:
            # 写到一半被切回指针（控制条改道 / 引擎切换）：把手上这笔落掉，别让滤波器
            # 悬挂着吃掉后面的 move 事件
            self._finish_input()
        self.toolChanged.emit()

    tool = Property(str, _get_tool, _set_tool, notify=toolChanged)

    # ------------------------------------------------------------ penColor

    def _get_pen_color(self) -> QColor:
        return QColor(self._pen_color)

    def _set_pen_color(self, value: QColor) -> None:
        color = QColor(value)
        if color == self._pen_color:
            return
        # 只影响下一笔：进行中的笔画在 beginStroke 时已经定了颜色
        self._pen_color = color
        self.penColorChanged.emit()

    penColor = Property(QColor, _get_pen_color, _set_pen_color, notify=penColorChanged)

    # ------------------------------------------------------------ penWidth

    def _get_pen_width(self) -> float:
        return self._pen_width

    def _set_pen_width(self, value: float) -> None:
        width = float(value)
        if width == self._pen_width:
            return
        self._pen_width = width
        self.penWidthChanged.emit()

    penWidth = Property(float, _get_pen_width, _set_pen_width, notify=penWidthChanged)

    # ---------------------------------------------------------- eraserWidth

    def _get_eraser_width(self) -> float:
        return self._eraser_width

    def _set_eraser_width(self, value: float) -> None:
        width = float(value)
        if width == self._eraser_width:
            return
        # 只影响下一笔：进行中的擦除笔画在 beginStroke 时已经定了宽度（同 penWidth）
        self._eraser_width = width
        self.eraserWidthChanged.emit()

    #: 像素橡皮的粗细（逻辑 px，2026-10-08 自建批注）。整笔擦除与手掌擦除都不读它，
    #: 理由见头注释「橡皮与手掌擦除」节。
    eraserWidth = Property(float, _get_eraser_width, _set_eraser_width, notify=eraserWidthChanged)

    # ---------------------------------------------------------- eraserMode

    def _get_eraser_mode(self) -> str:
        return self._eraser_mode

    def _set_eraser_mode(self, value: str) -> None:
        # 词表与 presentation.ink.eraser_mode 一致：pixel 像素 / stroke 整笔
        mode = str(value)
        if mode not in ("pixel", "stroke"):
            log.warning("InkLayer 收到未知橡皮子模式 %r，保持 %s", value, self._eraser_mode)
            return
        if mode == self._eraser_mode:
            return
        self._eraser_mode = mode
        self.eraserModeChanged.emit()

    eraserMode = Property(str, _get_eraser_mode, _set_eraser_mode, notify=eraserModeChanged)

    # ------------------------------------------------- 手掌擦除参数（todo 8）

    def _get_palm_erase_enabled(self) -> bool:
        return self._palm_erase_enabled

    def _set_palm_erase_enabled(self, value: bool) -> None:
        enabled = bool(value)
        if enabled == self._palm_erase_enabled:
            return
        self._palm_erase_enabled = enabled
        self.palmParamsChanged.emit()

    def _get_palm_threshold_mm(self) -> float:
        return self._palm_threshold_mm

    def _set_palm_threshold_mm(self, value: float) -> None:
        mm = max(0.0, float(value))
        if mm == self._palm_threshold_mm:
            return
        self._palm_threshold_mm = mm
        self.palmParamsChanged.emit()

    palmEraseEnabled = Property(bool, _get_palm_erase_enabled, _set_palm_erase_enabled, notify=palmParamsChanged)
    palmThresholdMm = Property(float, _get_palm_threshold_mm, _set_palm_threshold_mm, notify=palmParamsChanged)

    @property
    def currentPage(self) -> int:  # noqa: N802 - 与 Qt 侧命名风格一致
        return self._page

    # ------------------------------------------------------------ 笔画 API

    def _mode_for_tool(self) -> StrokeMode | None:
        if self._palm_erasing:
            # 手掌擦除（计划第 8 项）：临时像素擦除，工具属性不动 —— Q3「抬起即还原」
            return "erase"
        match self._tool:
            case "pen":
                return "pen"
            case "eraser":
                return "erase"
            case _:
                return None

    def _whole_erase(self) -> bool:
        """整笔橡皮生效中（决策 Q3）：eraser 工具 + stroke 子模式。手掌擦除不走这里。"""
        return self._tool == "eraser" and self._eraser_mode == "stroke" and not self._palm_erasing

    def _erase_whole_at(self, points, size: tuple[float, float]) -> None:
        """整笔擦除：划过的路径命中哪笔就删哪笔（模型 remove_strokes 带撤销栈）。

        命中半径与像素橡皮同宽（eraserWidth 直径的一半 —— 2026-10-08 起不再跟
        penWidth，保住「两种橡皮同一个大小」的不变量），归一化按窄边换算
        （model.hit_test 的坐标约定）。没命中就不记操作（remove_strokes 的语义），
        撤销栈里也就不会有「没反应」的一步。
        """
        self._ensure_image()
        radius = radius_of(self._eraser_width, 1.0) / min(size)
        hit: set[int] = set()
        for p in points:
            x, y = float(p[0]), float(p[1])
            hit.update(self.store.hit_test(self._page, x / size[0], y / size[1], radius))
        if hit and self.store.remove_strokes(self._page, hit):
            self._rebake()
            self.inkChanged.emit()

    @Slot(float, float, float)
    def beginStroke(self, x: float, y: float, w: float) -> None:  # noqa: N802
        if self._pts is not None:
            # 上一笔没收到抬笔（事件丢了）：先落掉，别让已写的墨凭空消失
            self.endStroke()
        size = self._size()
        if size is None:
            return
        if self._whole_erase():
            self._erase_whole_at([(x, y, w)], size)
            return
        mode = self._mode_for_tool()
        if mode is None:
            return
        self._ensure_image()
        # 2026-10-08 自建批注：像素擦除按 eraserWidth 取宽（不再跟 penWidth）；
        # 手掌擦除随后会在 _start_palm_erase 里把 _width 覆盖成接触直径。
        self._mode, self._width = mode, self._eraser_width if mode == "erase" else self._pen_width
        self._color = self._pen_color.name(QColor.NameFormat.HexArgb)
        self._pts = [(x / size[0], y / size[1], float(w))]
        if mode == "pen":
            self._wet = WetMesh(self._pen_color, self._dpr())
            self._wet.add(x, y, radius_of(self._width, w))
            self._publish(wet=self._wet.snapshot())
        else:
            self._erase_base = self._image.copy()
            self._publish(dry=self._erase_preview())

    @Slot("QVariantList")
    def extendStroke(self, points: Sequence[Sequence[float]]) -> None:  # noqa: N802
        size = self._size()
        if size is None or not points:
            return
        if self._whole_erase():
            self._erase_whole_at(points, size)
            return
        if self._pts is None:
            return
        for p in points:
            x, y = float(p[0]), float(p[1])
            w = float(p[2]) if len(p) > 2 else 1.0
            self._pts.append((x / size[0], y / size[1], w))
            if self._wet is not None:
                self._wet.add(x, y, radius_of(self._width, w))
        if self._wet is not None:
            self._publish(wet=self._wet.snapshot())
        else:
            self._publish(dry=self._erase_preview())

    @Slot()
    def endStroke(self) -> None:  # noqa: N802
        if self._pts is None:
            return
        stroke = Stroke(points=self._pts, color=self._color, width=self._width, mode=self._mode)
        base = self._erase_base
        self._reset_active()
        self.store.add_stroke(self._page, stroke)
        if self._image is not None and self._image_key == self._target_key():
            if stroke.mode == "erase" and base is not None:
                self._image = base
            # 增量：只把这一笔画进现有干图，不重烘整页
            bake(self._image, stroke, self._size() or (0.0, 0.0))
            self._publish(wet=b"", dry=self._image)
        else:
            self._rebake(wet=b"")
        self.inkChanged.emit()

    @Slot()
    def cancelStroke(self) -> None:  # noqa: N802
        if self._pts is None:
            return
        base = self._erase_base
        self._reset_active()
        if base is not None:
            self._image = base
            self._publish(wet=b"", dry=base)
        else:
            self._publish(wet=b"")

    @Slot(int)
    def setPage(self, page: int) -> None:  # noqa: N802
        self.cancelStroke()
        self._page = int(page)
        self._rebake()

    @Slot(result=bool)
    def clearPage(self) -> bool:  # noqa: N802
        self.cancelStroke()
        return self._after_mutation(self.store.clear_page(self._page))

    @Slot()
    def clearAll(self) -> None:  # noqa: N802
        self.cancelStroke()
        self.store.clear_all()
        self._after_mutation(True)

    @Slot(result=bool)
    def undo(self) -> bool:
        self.cancelStroke()
        return self._after_mutation(self.store.undo(self._page))

    @Slot(result=bool)
    def redo(self) -> bool:
        self.cancelStroke()
        return self._after_mutation(self.store.redo(self._page))

    # ------------------------------------------------------------ GUI 侧内部

    def _after_mutation(self, changed: bool) -> bool:
        if changed:
            self._rebake()
            self.inkChanged.emit()
        return changed

    def _reset_active(self) -> None:
        self._pts = None
        self._wet = None
        self._erase_base = None

    def _dpr(self) -> float:
        win = self.window()
        return win.effectiveDevicePixelRatio() if win is not None else 1.0

    def _size(self) -> tuple[float, float] | None:
        w, h = self.width(), self.height()
        return (w, h) if w > 0 and h > 0 else None

    def _target_key(self) -> tuple[int, int, float] | None:
        size = self._size()
        if size is None:
            return None
        dpr = self._dpr()
        return (math.ceil(size[0] * dpr), math.ceil(size[1] * dpr), dpr)

    def _ensure_image(self) -> None:
        if self._image is None or self._image_key != self._target_key():
            self._rebake()

    def _rebake(self, wet: bytes | None = None) -> None:
        """整页重烘：翻页 / 撤销重做 / 清屏 / 尺寸或 DPR 变化时才走这里。"""
        key, size = self._target_key(), self._size()
        if key is None or size is None:
            self._image, self._image_key = None, None
            return
        image = QImage(key[0], key[1], QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        # 让 QPainter 按逻辑像素画：与湿网格的坐标数字完全一致
        image.setDevicePixelRatio(key[2])
        for stroke in self.store.strokes(self._page):
            bake(image, stroke, size)
        self._image, self._image_key = image, key
        if self._pts is not None:
            # 书写途中尺寸变了：按新尺寸重建进行中这一笔的预览
            if self._mode == "erase":
                self._erase_base = image.copy()
                self._publish(wet=wet, dry=self._erase_preview())
                return
            self._wet = WetMesh(QColor(self._color), key[2])
            for x, y, w in self._pts:
                self._wet.add(x * size[0], y * size[1], radius_of(self._width, w))
            wet = self._wet.snapshot()
        self._publish(wet=wet, dry=image)

    def _erase_preview(self) -> QImage:
        # 在落笔前的干图副本上重放整条擦除轨迹：结果与抬笔后的烘焙逐像素相同
        image = self._erase_base.copy()
        bake(image, Stroke(points=list(self._pts), color=self._color, width=self._width, mode="erase"),
             self._size() or (0.0, 0.0))
        self._image = image
        return image

    def _publish(self, wet: bytes | None = None, dry: QImage | None = None) -> None:
        with self._lock:
            if wet is not None:
                self._pending_wet = wet
            if dry is not None:
                # QImage 隐式共享：之后 GUI 线程再往 _image 上画会自动分离，渲染侧拿到的不变
                self._pending_dry = dry
        self._request_update()

    def _request_update(self) -> None:
        self._update_requests += 1
        self.update()

    def geometryChange(self, new_geometry: QRectF, old_geometry: QRectF) -> None:  # noqa: N802
        super().geometryChange(new_geometry, old_geometry)
        if new_geometry.size() != old_geometry.size() and self._image is not None:
            # 坐标归一化，按新尺寸重烘即可重新对齐
            self._rebake()

    def _on_window_changed(self, win: QQuickWindow | None) -> None:
        if win is not None:
            win.sceneGraphInvalidated.connect(self._on_sg_invalidated, Qt.ConnectionType.DirectConnection)

    def _on_sg_invalidated(self) -> None:
        # 渲染线程、图形上下文仍有效：此时释放纹理最安全；节点已随场景图删除，只丢引用
        self._texture = None
        self._root = self._dry_node = self._wet_node = None
        self._wet_geom = self._wet_mat = self._wet_attrs = None
        self._wet_nodes, self._wet_geoms = [], []

    # ------------------------------------------------------------ 渲染线程

    def updatePaintNode(self, old_node, _data):  # noqa: N802 - Qt 虚函数名
        with self._lock:
            wet, dry = self._pending_wet, self._pending_dry
            self._pending_wet = self._pending_dry = None
        if wet is not None:
            self._shown_wet = wet
        if dry is not None:
            self._shown_dry = dry
        rebuilt = old_node is None or self._root is None
        if rebuilt:
            self._build_nodes()
        if rebuilt or dry is not None:
            self._upload_dry()
        if self._dry_node is not None:
            self._dry_node.setRect(QRectF(0, 0, self.width(), self.height()))
        if rebuilt or wet is not None:
            self._upload_wet()
        return self._root

    def _build_nodes(self) -> None:
        self._texture = None
        self._dry_node = None
        self._root = QSGNode()
        # QSGGeometry 只存 AttributeSet 的引用（C++ 里是 const&）。PySide 把
        # defaultAttributes_ColoredPoint2D() 的返回值包成一个临时 Python 对象，临时对象被回收后
        # 几何拿到的是野指针：顶点颜色读成乱码（实测黄色画成绿色），渲染线程随后访问冲突。
        # 所以属性集必须和几何一样挂在 self 上。
        self._wet_attrs = QSGGeometry.defaultAttributes_ColoredPoint2D()
        # 各分块共用一份材质：颜色在顶点里，材质本身无状态；节点不拥有它，引用留在 self
        self._wet_mat = QSGVertexColorMaterial()
        self._wet_nodes, self._wet_geoms = [], []
        self._add_wet_chunk()

    def _add_wet_chunk(self) -> None:
        geom = QSGGeometry(self._wet_attrs, 0)
        geom.setDrawingMode(QSGGeometry.DrawingMode.DrawTriangles)
        node = QSGGeometryNode()
        node.setGeometry(geom)
        node.setMaterial(self._wet_mat)
        # 追加在末尾：干图节点 prepend 在最前，湿墨迹各块恒在干图之上
        self._root.appendChildNode(node)
        self._wet_geoms.append(geom)
        self._wet_nodes.append(node)
        self._wet_geom, self._wet_node = self._wet_geoms[0], self._wet_nodes[0]

    def _upload_dry(self) -> None:
        img, win = self._shown_dry, self.window()
        if img is None or img.isNull() or win is None:
            return
        tex = win.createTextureFromImage(img, QQuickWindow.CreateTextureOption.TextureHasAlphaChannel)
        if self._dry_node is None:
            node = QSGSimpleTextureNode()
            node.setOwnsTexture(False)
            node.setFiltering(QSGTexture.Filtering.Linear)
            # 干图在下、湿网格在上
            self._root.prependChildNode(node)
            self._dry_node = node
        self._dry_node.setTexture(tex)
        # 先换上新纹理再丢旧引用，旧纹理此时才被释放
        self._texture = tex
        self._dry_node.markDirty(QSGNode.DirtyStateBit.DirtyMaterial)

    def _upload_wet(self) -> None:
        data = self._shown_wet
        count = len(data) // VERTEX_SIZE
        chunks = max(1, math.ceil(count / WET_CHUNK_VERTICES))
        while len(self._wet_geoms) < chunks:
            self._add_wet_chunk()
        for i, (geom, node) in enumerate(zip(self._wet_geoms, self._wet_nodes, strict=True)):
            start = i * WET_CHUNK_VERTICES
            n = min(WET_CHUNK_VERTICES, count - start)
            if n > 0:
                geom.allocate(n)
                # allocate 可能换缓冲区，地址必须在它之后取
                ctypes.memmove(int(geom.vertexData()), data[start * VERTEX_SIZE:(start + n) * VERTEX_SIZE], n * VERTEX_SIZE)
            else:
                # 湿墨迹「清空」不能 allocate(0)：实测（PySide6 6.11 / D3D11）顶点数归零后渲染器把该节点
                # 移出批次，之后再给它新顶点也不再画——第二笔起湿墨迹整条不可见，只有抬笔后的干图出现。
                # 换成 3 个全零顶点：零面积、alpha=0 的退化三角形，什么都不画，但节点留在批次里。
                # 多出来的分块同理：不删节点，只置成占位。
                geom.allocate(WET_PLACEHOLDER_VERTICES)
                ctypes.memset(int(geom.vertexData()), 0, WET_PLACEHOLDER_VERTICES * VERTEX_SIZE)
            node.markDirty(QSGNode.DirtyStateBit.DirtyGeometry)

    # ------------------------------------------------------------ 输入接线（计划第 5 项）

    def event(self, ev: QEvent) -> bool:  # noqa: N802 - Qt 虚函数名
        """触摸与平板事件没有专用虚函数、都从 event() 分派（鼠标走下面的 mouseXxxEvent）。

        只在「能画画」或「有在途笔画要收尾」时消费事件；arrow 态一律放行给基类，
        不白吞事件。``QEvent.Type.TouchCancel``（系统手势抢走）作废这笔。
        """
        et = ev.type()
        if et == QEvent.Type.TouchBegin:
            if self._tool in ("pen", "eraser"):
                return self._touch_begin(ev)
        elif et in (QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            if self._device == "touch":
                return self._touch_step(ev, et)
        elif et == QEvent.Type.TabletPress:
            if self._tool in ("pen", "eraser"):
                self._begin_input("tablet", ev.position().x(), ev.position().y(),
                                  ev.timestamp() * 0.001, ev.pressure())
                return True
        elif et in (QEvent.Type.TabletMove, QEvent.Type.TabletRelease):
            if self._device == "tablet":
                self._tablet_step(ev, et)
                return True
        return super().event(ev)

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if ev.button() == Qt.MouseButton.LeftButton and self._tool in ("pen", "eraser"):
            pos = ev.position()
            self._begin_input("mouse", pos.x(), pos.y(), ev.timestamp() * 0.001, None)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if self._device == "mouse" and self._smoother is not None:
            pos = ev.position()
            self._extend_input(pos.x(), pos.y(), ev.timestamp() * 0.001, None)
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if self._device == "mouse" and self._smoother is not None:
            # 抬笔位置补进点流再收（与平板同）：笔画精确停在松手处，与最后一个 move 有
            # 几像素差时不吃这个差
            pos = ev.position()
            self._extend_input(pos.x(), pos.y(), ev.timestamp() * 0.001, None)
            self._finish_input()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        # 双击的第二次按下被 Qt 换成 MouseButtonDblClick：批注里「点两下」应出两个
        # 圆点，这里按普通 press 处理，别让第二个点凭空消失
        if ev.button() == Qt.MouseButton.LeftButton and self._tool in ("pen", "eraser"):
            self.mousePressEvent(ev)
            return
        super().mouseDoubleClickEvent(ev)

    def _touch_begin(self, ev: QTouchEvent) -> bool:
        self._sample_contacts(ev)
        if self._device == "touch":
            # 已在跟第一个触点：再来 TouchBegin 是第二根手指，不换跟踪目标 ——
            # 但多指聚齐（≥3 指）会触发手掌擦除，触发时把跟踪切到掌面
            if self._tool in ("pen", "eraser") and not self._palm_erasing:
                palm = self._palm_trigger_point(ev)
                if palm is not None:
                    self._finish_input()  # 手上这笔记账，让位给手掌擦除
                    self._start_palm_erase(palm)
            return True
        if self._tool not in ("pen", "eraser"):
            return False
        pts = ev.points()
        # PySide6.11 里 State 是普通枚举、没有旗标运算；起笔点状态就是单值 Pressed
        point = next((p for p in pts if p.state() == QEventPoint.State.Pressed), pts[0] if pts else None)
        if point is None:
            return False
        self._touch_id = point.id()
        self._log_no_diameter_once(point)
        palm = self._palm_trigger_point(ev)
        if palm is not None:
            self._start_palm_erase(palm)
            return True
        pos = point.position()
        self._begin_input("touch", pos.x(), pos.y(), ev.timestamp() * 0.001, point.pressure())
        return True

    def _touch_step(self, ev: QTouchEvent, et: QEvent.Type) -> bool:
        if et == QEvent.Type.TouchCancel:
            # 系统把手势抢走（如边缘滑动识别）：这笔作废，滤波器一起丢
            self._touch_id = -1
            self._palm_erasing = False
            self._cancel_input()
            return True
        point = next((p for p in ev.points() if p.id() == self._touch_id), None)
        self._sample_contacts(ev)
        # 手掌擦除中途触发（大接触面随 Update 落下 / ≥3 指聚齐）：手上这笔记账，切手掌
        if self._tool in ("pen", "eraser") and not self._palm_erasing:
            palm = self._palm_trigger_point(ev)
            if palm is not None:
                self._finish_input()
                self._start_palm_erase(palm)
                return True
        if point is None:
            # 跟丢触点（驱动没送 End）：按抬笔收尾，别让笔画和滤波器悬挂
            self._touch_id = -1
            self._finish_input()
            self._palm_erasing = False
            return True
        pos = point.position()
        t = ev.timestamp() * 0.001
        # 抬笔看触点状态而不是事件类型：TouchEnd 只在整组触点全抬时才发，
        # 多指里先抬一根是 TouchUpdate 载着 Released 状态的点来的（QQuickDeliveryAgent
        # 实测会把合成的部分 TouchEnd 归一成 TouchUpdate），只看 et 笔画就会悬挂
        if et == QEvent.Type.TouchEnd or point.state() == QEventPoint.State.Released:
            self._touch_id = -1
            if self._palm_erasing:
                self._extend_palm(pos.x(), pos.y())
            else:
                self._extend_input(pos.x(), pos.y(), t, point.pressure())
            self._finish_input()
            self._palm_erasing = False
            return True
        if self._palm_erasing:
            self._extend_palm(pos.x(), pos.y())
            return True
        self._extend_input(pos.x(), pos.y(), t, point.pressure())
        return True

    def _tablet_step(self, ev: QTabletEvent, et: QEvent.Type) -> None:
        pos = ev.position()
        if et == QEvent.Type.TabletRelease:
            # 抬笔前的位置未必来过 TabletMove：补一个点再收，笔画精确停在松手处
            self._extend_input(pos.x(), pos.y(), ev.timestamp() * 0.001, ev.pressure())
            self._finish_input()
            return
        if not ev.buttons() & Qt.MouseButton.LeftButton:
            return  # 悬停（笔尖靠近未压下）不画
        self._extend_input(pos.x(), pos.y(), ev.timestamp() * 0.001, ev.pressure())

    def _begin_input(self, device: str, x: float, y: float, t: float, pressure: float | None) -> None:
        if self._tool not in ("pen", "eraser"):
            # arrow 态不接受任何输入（头注释）：投递层关了鼠标，这里再兜 QA 直投事件的底
            return
        if self.card_dismiss_hook is not None and self.card_dismiss_hook():
            # 工具卡正开着：这一按是「点空白收起」，消费掉不起笔（2026-10-08
            # 自建批注）。不落 _device / _smoother，随后的 move / release 自然
            # 走基类放行，不会半路挂出一笔。
            return
        if self._smoother is not None:
            # 上一笔没收到抬笔（事件丢了）：先落掉，别让已写的墨凭空消失
            self._finish_input()
        self._device = device
        self._smoother = StrokeSmoother(has_pressure=_device_has_pressure(device, pressure))
        out = self._smoother.begin(x, y, t, pressure)
        if out:
            self.beginStroke(out[0][0], out[0][1], out[0][2])

    def _extend_input(self, x: float, y: float, t: float, pressure: float | None) -> None:
        if self._smoother is None:
            return
        out = self._smoother.add(x, y, t, pressure)
        if out:
            self.extendStroke(out)

    def _finish_input(self) -> None:
        smoother = self._smoother
        self._smoother = None
        self._device = None
        if smoother is not None:
            out = smoother.end()
            if out:
                self.extendStroke(out)
        # 手掌擦除的笔画没有滤波器，也要在这里收笔 —— endStroke 对无在途笔画是
        # 安全的空操作，不用这里再分情况
        self.endStroke()

    def _cancel_input(self) -> None:
        self._smoother = None
        self._device = None
        self.cancelStroke()

    def _sample_contacts(self, ev: QTouchEvent) -> None:
        """事件里每个触点都过一遍接触样本（含非跟踪的第二指——手掌擦除看的就是它们）。"""
        for p in ev.points():
            self._track_contact(p)

    def _track_contact(self, point: QEventPoint) -> None:
        # 驱动不给直径时是宽高非正的非法 QSizeF：存 None，手掌擦除据此静默禁用
        d = point.ellipseDiameters()
        self._last_contact_diameters = (d.width(), d.height()) if d.width() > 0 and d.height() > 0 else None
        self._on_contact_sample(self._last_contact_diameters, point.pressure())

    def _contact_px(self, point: QEventPoint) -> float:
        """触点接触直径（逻辑 px）；驱动不给直径返回 0。"""
        d = point.ellipseDiameters()
        if d.width() <= 0 or d.height() <= 0:
            return 0.0
        return max(d.width(), d.height())

    def _palm_threshold_px(self) -> float:
        """阈值毫米 → 逻辑 px。拿不到屏幕物理参数返回 0（无法判定 = 不触发）。"""
        if self._palm_threshold_mm <= 0:
            return 0.0
        window = self.window()
        screen = window.screen() if window is not None else None
        if screen is None:
            return 0.0
        px_per_mm = screen.physicalDotsPerInch() / 25.4
        dpr = self._dpr()
        return self._palm_threshold_mm * px_per_mm / (dpr if dpr > 0 else 1.0)

    def _palm_pick(self, samples):
        """手掌判定（纯决策，QA 直接驱动；样本由 _palm_trigger_point 从事件提取）。

        samples: [(id, released, contact_px, x, y)]。触发条件（决策 Q3）：
        任一按下中的触点直径 ≥ 阈值，或同时 ≥3 个接触点。驱动不给直径的触点
        不参与判定 —— 整个手掌擦除对这种驱动静默禁用。命中返回
        (id, x, y, contact_px)，否则 None。
        """
        threshold = self._palm_threshold_px()
        if not self._palm_erase_enabled or threshold <= 0:
            return None
        active = [s for s in samples if not s[1] and s[2] > 0]
        big = [s for s in active if s[2] >= threshold]
        if big:
            s = max(big, key=lambda item: item[2])
            return (s[0], s[3], s[4], s[2])
        if len(active) >= 3:
            s = max(active, key=lambda item: item[2])
            return (s[0], s[3], s[4], s[2])
        return None

    def _palm_trigger_point(self, ev: QTouchEvent) -> QEventPoint | None:
        samples = [(p.id(), p.state() == QEventPoint.State.Released, self._contact_px(p),
                    p.position().x(), p.position().y()) for p in ev.points()]
        hit = self._palm_pick(samples)
        if hit is None:
            return None
        return next((p for p in ev.points() if p.id() == hit[0]), None)

    def _start_palm_erase(self, point: QEventPoint) -> None:
        """进入手掌擦除：像素擦除开一笔，擦除宽度 = 接触直径。

        「抬起即还原原工具」不用做任何事 —— 工具属性全程没动过，``_palm_erasing``
        一撤，_mode_for_tool 就回到原工具的语义。状态切换本身不进撤销栈；
        擦除笔画与普通像素橡皮同栈，undo 一样能撤。
        """
        self._palm_erasing = True
        self._device = "touch"
        self._touch_id = point.id()
        contact = max(self._contact_px(point), 2.0)
        pos = point.position()
        self.beginStroke(pos.x(), pos.y(), 1.0)
        if self._mode == "erase":
            # bake 半径 = stroke.width × w / 2：宽度取接触直径、每点 w 恒 1，
            # 半径即接触直径的一半（跟接触面积走）
            self._width = contact
        else:
            # beginStroke 没进擦除路径（尺寸异常等）：别让旗标悬着
            self._palm_erasing = False
            self._device = None
            self._touch_id = -1

    def _extend_palm(self, x: float, y: float) -> None:
        self.extendStroke([[x, y, 1.0]])

    def _log_no_diameter_once(self, point: QEventPoint) -> None:
        if self._palm_no_diameter_logged or not self._palm_erase_enabled or self._palm_threshold_mm <= 0:
            return
        if self._contact_px(point) > 0:
            return
        self._palm_no_diameter_logged = True
        log.info("触屏驱动不报接触直径，手掌擦除不可用")

    def _on_contact_sample(self, diameters: tuple[float, float] | None, pressure: float | None) -> None:
        """触屏接触样本钩子：第 8 项手掌擦除在这里消费 ellipseDiameters / 压力。

        基类故意不做事——手掌启发式没接上之前，直径只被记录，绝不能影响笔画。
        """
