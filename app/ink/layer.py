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
  像素橡皮没有湿网格：擦除时在「落笔前的干图副本」上增量烘擦除轨迹的已确认段
  （P0-3 起每批只烘新增段，见 ``_erase_preview``），所见即所得。

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

2026-10-09 **橡皮幻影**（用户指令：「点下去就有一个模拟橡皮擦的 UI 出现」，
希沃白板同款）：层只在输入流里维护 ``eraserGhostVisible/X/Y/Size`` 四个
只读属性 —— 像素 / 整笔橡皮起笔即出现、跟随触点、收笔（含 TouchCancel
作废）即隐，尺寸 = 擦除宽度；手掌擦除尺寸跟接触直径。层**不画**这个 UI：
幻影浮在墨迹之上，而层的干湿烘焙管线只管墨迹，再塞一层视觉只会把 SG
交接搞复杂；``ui/ink/EraserGhost.qml`` 绑这四个属性渲染，放映叠加层与
小黑板两个宿主各挂一份。

2026-10-10 **橡皮擦鼠标/触控适配**（用户指令：「做个有关自建批注的橡皮擦适配，
如果用户点击了橡皮擦工具并且用的是鼠标，那么不管鼠标移动到哪里[除非是软件的胶囊]，
始终显示橡皮擦。但是如果是触控，那么就只有按下去的时候才显示」）：
层开启 ``setAcceptHoverEvents(True)``，通过事件类型精准区分指针设备态
（鼠标 hover/move vs 触屏 TouchBegin/Update/End）。
* 鼠标态：选中 eraser 工具后在画布移动（hover 或按下拖动）始终显示 EraserGhost，
  抬起按键不隐藏；离开画布或进入软件胶囊区域即隐；从胶囊移回画布即恢复。
* 触控态：严格遵守「按下才显示、抬起即隐藏」——TouchBegin 显现，TouchEnd/Released
  即隐，手指悬空不显。
* 胶囊排除机制：双重保障。一是 ``capsule_hit_hook``（供放映模式 WindowManager
  挂放映控制条及弹出卡片的全局/局部矩形），二是 ``excludedItems`` 属性（供 QML
  宿主如小黑板挂 ``[capsule, fullScreenButton, chalkPaletteCard]`` 等浮层控件，
  内部走 ``mapToItem`` 坐标判定），坐标落在胶囊内时强制隐藏橡皮擦且不吃笔画输入。
  起笔排除统一收口在 ``_begin_input`` 入口（2026-10-18 plugin-audit B1：此前
  只接鼠标路径，触屏/触笔在胶囊上会隔空起笔误画；鼠标路径 mousePressEvent 的
  预检保留——它要先放行基类再返回，行为不变）。

2026-10-10 **自建批注触控体验调优**（用户反馈『触控模式下体验感还是有点不好』）：
* ``_begin_input`` 构造 ``StrokeSmoother`` 时传入 ``device=device``，触控专属高密度抽稀
  （4px / 8ms）、更高快划响应、起笔饱满度（0.75）、温和速度变细（0.18）全链路生效；
* 抬笔防倒钩：触控离屏终点在近程内顺滑收拢，禁止向离开跳变点拉折线；
* 防顿笔误擦：单指书写中途顿笔下压不草率切橡皮，需达 1.35x 手掌裕度或掌面/多指落下才切。

2026-10-29 **触控审计修复**（完整报告在仓库根 ``TOUCH-AUDIT-2026-10-29.md``）：
* **阈值单位定案**：``physicalDotsPerInch`` 与 ``ellipseDiameters`` 同为
  device-independent 单位，毫米换算**不再除 dpr**（见 ``_px_per_mm``）—— 旧实现在
  4K@150% 一体机上把 20mm 折成 ≈14mm，指腹用力即撞手掌阈值（顿笔误擦回归），
  自检的旧断言也把错误固化了，一并改正。
* **起笔槽仲裁**：起笔触点达掌缘尺度（≥阈值）且误起笔小而新（≤4 点、≤400ms）时，
  随后落下的指尖接管书写并作废误起笔（``_takeover_palm_start_worth_it``）——
  「掌缘先搭屏 + 手指后写字」旧实现会让指尖全程写不出墨；正常书写触点不受
  第二指影响（既有语义）。
* **掌擦收尾续写**：掌面抬起 / 跟丢后，仍按着的指尖无缝接管为新一笔
  （``_resume_after_palm``），不再要求全部抬手重按。
* **抬笔点离群判定**（``_release_is_noise``）：触控抬笔瞬间反向 ≥12px 的指腹
  形变跳变不喂滤波（防 10~37px 倒钩），方向连续的收笔补点照常喂。
* **接触直径物理上限**（80mm 等效，``_contact_axes``）：驱动按 himetric 上报
  接触面积时不再「每一按都判手掌、幻影糊满屏」；**触控橡皮物理下限**
  （12mm 等效，仅触控路径抬 ``_stroke_eraser_width``）；eraserWidth 属性夹取 [4,200]。
* **≥3 指判掌擦加 280mm 空间跨度约束**（``_three_finger_plausible``）：两只手
  各指一处 / 水渍幽灵点不再在屏幕另一头凭空开擦。
* **会话态复位**：``cancelStroke``（翻页 / 撤销 / 清屏 / TouchCancel 的公共入口）
  与 ``abort_input``（窗口隐藏 / 抑制，由 WindowManager 调）复位
  ``_device/_touch_id/_palm_erasing/_smoother`` —— 触点 id 小整数循环复用，
  跨场残态曾表现为「下一场首触无墨」「橡皮跟着手指跑」。
* **整笔擦除命中改双轴半径**（``model.hit_test`` rx/ry）：屏幕空间命中带回正圆，
  与幻影 / 橡皮宽度三者一致。

2026-11-01 **scaleWithSize**（C++ 版先有、Python 侧回植）：改尺寸时墨迹跟不跟着
缩放。点按按 0..1 归一化存、笔宽按逻辑 px 存，重烘时位置按横竖两个倍率拉伸、
宽度不动 —— 像素橡皮与笔迹的覆盖关系随之改变，擦净处会露出月牙形残片
（小黑板实测：默认窗口里画了又擦净，最大化后冒出「神秘笔迹」）。

* ``true``（缺省，放映叠加层）= 按当前尺寸重新展开，墨迹随画面缩放。横竖倍率
  不同时位置被拉伸、宽度不动，覆盖关系会变 —— 放映窗口尺寸基本不变，不踩。
* ``false``（小黑板）= 归一化基准锁在首次烘焙时的尺寸（``_locked_map_size``），
  之后改尺寸只多出 / 裁掉画布边缘，已画的东西原地不动、覆盖关系逐像素不变。

归一化 / 反归一化一律走 ``_map_size()``，``_size()`` 只管「层有没有尺寸」与
「当前几何」。运行期从 false 切回 true，墨迹按当前尺寸重新展开（会跳一下）。
"""

from __future__ import annotations

import ctypes
import logging
import math
import threading
from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QEvent, QPointF, QRect, QRectF, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QCursor,
    QEventPoint,
    QHoverEvent,
    QImage,
    QInputDevice,
    QMouseEvent,
    QTabletEvent,
    QTouchEvent,
)
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
from .tessellate import FEATHER_DEVICE_PX, VERTEX_SIZE, WetMesh, bake, radius_of

log = logging.getLogger("luminalium.ink")

#: 合法工具名。与控制条 ``tool:<id>`` 动作同一套口径，QML 侧传别的值视为 bug。
TOOLS = ("pen", "eraser", "arrow")
#: 湿墨迹清空时保留的占位顶点数（一个零面积透明三角形），原因见 ``_upload_wet``。
WET_PLACEHOLDER_VERTICES = 3
#: 单个湿墨迹几何节点的顶点上限（3 的倍数，< 65536）。实测一个节点超过 65535 个顶点时，
#: 超出部分不画（5000 点长笔画后四分之一缺失），疑似渲染器按 16 位索引处理；分块后每块都在界内。
WET_CHUNK_VERTICES = 65532
#: 干图纹理分块边长（设备像素，意图 496）。干图不再是一张整图纹理，而是切成
#: TILE×TILE 的网格、每块一个 QSGSimpleTextureNode；_publish 携带脏矩形时只重建
#: 与之相交的块（局部擦除通常只动 1~4 块），上传量正比脏面积而非满页。
#: 取 512（意图 521 实测复测二选一定稿，256 vs 512 同机同 session 对照）：
#: - 持续擦除 churn 两者都贴近静止上限（4K 设备px 下 512≈195fps/82%、256≈212fps/90%，
#:   差距在 jank 阈值之上无感），不随分辨率显著退化，均满足「churn≥static 七成」判据；
#: - 关键差异在 full 重烘离散事件（翻页/undo/清屏/尺寸变，须重建全部 tile）：块越少则
#:   逐块 createTextureFromImage 次数越少，512 显著占优 —— 4K 整图重传 55.5fps/18ms
#:   vs 256 的 22.5fps/44ms（~2x），resize p90 86ms vs 103ms。
#: 512 下 4K(3840x2160) = 8x5=40 块、单块 ~1MiB；256 下同屏 15x9=135 块。
#: 擦除脏区(橡皮直径 ~60 设备px)通常只碰 1~2 块，full 重烘块数又不致太多。
DRY_TILE_DEVICE_PX = 512
#: physicalDotsPerInch 的合理夹取范围（P2-5，见 _palm_threshold_px 注释）。
_PALM_DPI_CLAMP_MIN = 48.0
_PALM_DPI_CLAMP_MAX = 480.0
#: 接触直径的物理合理性上限（毫米等效，2026-10-29 触控审计 #9）：两轴任一超过
#: 它即按「无直径」处理。国产一体机驱动有把接触面积按 himetric 上报的
#: （1200「px」实为 12mm），无上限会把每一按都判成手掌、橡皮幻影糊满屏。
_CONTACT_CAP_MM = 80.0
#: 触控橡皮的物理下限（毫米等效，2026-10-29 触控审计 #11）：逻辑 px 定宽的
#: 橡皮在 4K 一体机上比指腹还小（18px ≈ 9mm），看得见擦不动。
_TOUCH_ERASER_FLOOR_MM = 12.0
#: ≥3 指判掌擦的空间跨度上限（毫米等效，2026-10-29 审计 #15）：三个触点彼此
#: 散布超过一手掌跨度更像「两只手各指一处」/ 水渍幽灵点，不判掌擦。
_PALM_SPAN_MM = 280.0
#: 手掌擦除圆直径相对接触【短轴】的最大放大倍数（2026-10-31 掌擦精度，fact 515）：
#: 掌缘小鱼际接触是细长椭圆（如 50x15mm，长短轴比 ~3.3）；引擎只支持圆盘 stamp，
#: 旧实现擦除圆直径 = 接触【长轴】→ 短轴方向单边过擦 (长-短)/2（50x15 时达 17.5mm，
#: 擦除面积较真实接触椭圆多 235%）。把擦除圆直径夹到 min(长轴, 短轴×此倍数)：
#: 近圆接触（掌根肉垫，长短轴比 ≤ 此值）完全不受影响；细长掌缘的过擦收敛，代价是
#: 长轴方向轻微欠擦——掌擦是抹擦手势，长轴方向由轨迹扫掠补偿。此值是精度/覆盖的
#: 折中档位，纯几何推定，最终手感需实机标定（见 fact 515）。只影响掌擦擦除【宽度】，
#: 不动手掌【判定】（判定仍用长轴 _contact_px，接侧缘贴屏）。
_PALM_ERASE_MAX_ASPECT = 2.0
#: 抬笔点离群判定的最小跳变距离（逻辑 px，2026-10-29 审计 #20）：低于它视为
#: 正常收笔补点，照常喂滤波。
_RELEASE_JUMP_MIN_PX = 12.0


def _vertex_data_bytes(geom: QSGGeometry):
    """geom.vertexData() 的可写字节视图（P2-3）。

    PySide6 各版本返回类型不一致：memoryview、int（缓冲地址）、shiboken 的
    VoidPtr（实测 6.11，支持 int() 取地址）。memoryview 统一 cast 成字节视图
    直接切片写；int / VoidPtr 走 ctypes.memmove/memset。
    """
    vd = geom.vertexData()
    if isinstance(vd, memoryview):
        return vd.cast("B") if vd.format != "B" or vd.itemsize != 1 else vd
    return vd


def _blit_vertex_data(geom: QSGGeometry, payload: bytes) -> None:
    """把 payload 拷进几何顶点缓冲（_upload_wet 增量重传用）。"""
    vd = _vertex_data_bytes(geom)
    if isinstance(vd, memoryview):
        vd[:len(payload)] = payload
    else:
        ctypes.memmove(int(vd), payload, len(payload))


def _clear_vertex_data(geom: QSGGeometry, byte_len: int) -> None:
    """顶点缓冲清零（占位退化三角形用）。"""
    vd = _vertex_data_bytes(geom)
    if isinstance(vd, memoryview):
        vd[:byte_len] = bytes(byte_len)
    else:
        ctypes.memset(int(vd), 0, byte_len)


def _is_real_mouse(ev) -> bool:
    """判定是否为真实物理鼠标事件。过滤掉系统或 Qt 从触屏/触控笔派生的合成事件。"""
    try:
        if hasattr(ev, "source") and ev.source() != Qt.MouseEventSource.MouseEventNotSynthesized:
            return False
    except Exception:
        pass
    try:
        if hasattr(ev, "deviceType"):
            dt = ev.deviceType()
            if dt in (
                QInputDevice.DeviceType.TouchScreen,
                QInputDevice.DeviceType.Stylus,
                QInputDevice.DeviceType.Airbrush,
            ):
                return False
    except Exception:
        pass
    return True


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
    #: 橡皮幻影（2026-10-09 用户指令：点下橡皮要有「模拟橡皮擦」的 UI 跟着
    #: 触点走，希沃白板同款）。可见性 / 位置 / 尺寸任一变化发出，QML 侧
    #: ``ui/ink/EraserGhost.qml`` 纯绑定渲染，层本身不画这个 UI。
    eraserGhostChanged = Signal()
    #: 排除控件列表变动（2026-10-10 自建批注：小黑板等 QML 宿主注册胶囊等浮层）
    excludedItemsChanged = Signal()
    #: 改尺寸时墨迹跟不跟着缩放（2026-11-01 从 C++ 版回植，见头注释 scaleWithSize 节）
    scaleWithSizeChanged = Signal()
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

        # 归一化换算基准（2026-11-01 从 C++ 版回植，语义见头注释 scaleWithSize 节）。
        # True = 恒取当前尺寸；False = 锁在首次烘焙时的尺寸（``_locked_map_size``）。
        self._scale_with_size = True
        self._locked_map_size: tuple[float, float] | None = None

        # ---- GUI 线程状态
        self._image: QImage | None = None
        self._image_key: tuple[int, int, float] | None = None
        self._pts: list[Point] | None = None  # 进行中这一笔（归一化坐标）
        self._mode: StrokeMode = "pen"
        self._color = ""
        self._width = 0.0
        self._wet: WetMesh | None = None
        self._erase_base: QImage | None = None
        # 像素橡皮增量预览（P0-3 Option A）：_erase_work 是「落笔前干图副本」上的工作图，
        # 每批只烘新增段；_erase_cursor 是 _pts 里已烘到的点下标（下一个待烘段从它起），
        # _erase_cursor_key 记录已烘口径 (width, color)，变化即回退全量重放（见 _erase_preview）
        self._erase_work: QImage | None = None
        self._erase_cursor: int = -1
        self._erase_cursor_key: tuple[float, str] | None = None
        # 整笔擦除手势的命中累积（P1-1）：手势期间只记账笔画 id（去重），抬笔
        # endStroke 一次性 remove_strokes、提交单个 _RemoveOp；None = 无手势在途
        self._stroke_erase_hits: set[int] | None = None

        # ---- 交接区（_lock 保护）：None 表示「没有新东西」。
        # 湿网格是增量交接（P2-1）：(start, data) = 「把 _shown_wet 从 start 字节起
        # 替换为 data」；data 为空 b"" 表示清空。GUI 线程只交新增段，消整条网格的
        # 每帧全量拷贝（WetMesh.snapshot 的返回值直接就是它）。
        self._lock = threading.Lock()
        self._pending_wet: tuple[int, bytes] | None = None
        self._pending_dry: QImage | None = None
        # 干图脏矩形交接（意图 496）：_pending_dry_rect = 本帧干图改动的设备像素包围盒，
        # 只重建与之相交的 tile；_pending_dry_full=True 表示整图改动（重烘/翻页/undo/
        # 清屏/尺寸变 或 调用方未给脏矩形）须重建所有 tile。一帧内多次 _publish 的脏矩形
        # 取并集（渲染侧只应用最后那张 _shown_dry，但它已含本帧全部累积改动，并集即覆盖
        # 所有被改过的 tile）；任一次 full 则本帧 full。
        self._pending_dry_rect: QRect | None = None
        self._pending_dry_full: bool = False

        # ---- 渲染线程状态（只在 updatePaintNode / 失效回调里碰）
        self._shown_wet = b""
        self._shown_dry: QImage | None = None
        self._root: QSGNode | None = None
        # 干图 tile 网格（意图 496）：_dry_tiles[i] 是第 i 块的 QSGSimpleTextureNode，
        # _dry_textures[i] 是它当前持有的 QSGTexture（节点不拥有、引用留这里，换纹理时
        # 先挂新的再丢旧引用）。_dry_cols/_dry_rows/_dry_img_w/_dry_img_h/_dry_img_dpr
        # 记录网格是按哪张图的尺寸/DPR 建的，图尺寸变了就整网格重建。
        self._dry_tiles: list[QSGSimpleTextureNode] = []
        self._dry_textures: list[QSGTexture | None] = []
        self._dry_cols = 0
        self._dry_rows = 0
        self._dry_img_w = 0
        self._dry_img_h = 0
        self._dry_img_dpr = 0.0
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
        # 开启鼠标 hover 事件（2026-10-10 自建批注：鼠标移动时显示橡皮幻影）
        self.setAcceptHoverEvents(True)
        self._pointer_device: str = "mouse"  # 最近一次活跃指针设备（mouse/touch/tablet）
        self._mouse_hovering: bool = False   # 鼠标光标当前是否在 Item 区域内
        self._smoother: StrokeSmoother | None = None
        self._device: str | None = None  # 在途笔画的设备（mouse/touch/tablet），拦截异设备事件串扰
        self._touch_id = -1  # 正在跟的触点 id（只跟第一个触点）
        # 起笔槽仲裁参照（2026-10-29 触控审计 #3）：起笔触点的接触尺度与起笔时刻。
        # 起笔触点达到掌缘尺度（≥阈值）且误起笔还小而新时，随后落下的指尖接管
        # 书写并作废误起笔 ——「掌缘先搭屏 + 手指后写字」是课堂常态，旧实现会把
        # 指尖当第二根手指吞掉、怎么动都不出墨。正常书写触点（接触 < 阈值）不受
        # 影响：第二指落下依旧不换目标。
        self._touch_contact_px = 0.0
        self._touch_begin_ms = 0.0
        # 本笔橡皮宽度（逻辑 px）：默认跟 eraserWidth 属性，触控路径在 _begin_input
        # 里抬高到物理下限（2026-10-29 审计 #11，见 _touch_eraser_floor_px）
        self._stroke_eraser_width: float = self._eraser_width
        # 手掌擦除给 beginStroke 的宽度覆盖（接触直径），用一次即清
        # （2026-10-29 审计 #15：旧实现先按 eraserWidth 起笔再覆盖宽度，
        # 起手那一帧会先烘出一个 18px 小圆点闪一下）
        self._stroke_width_override: float | None = None
        # 抬笔跳变防倒钩的参照点（2026-10-29 审计 #20）：触控路径最后喂给滤波的
        # 位置与该段方向；释放点与其反向大跳时只用于判定抬手、不喂滤波
        self._last_feed_x = 0.0
        self._last_feed_y = 0.0
        self._last_feed_dx = 0.0
        self._last_feed_dy = 0.0
        self._last_contact_diameters: tuple[float, float] | None = None  # todo 8 手掌擦除消费
        self._palm_bad_diameter_logged = False  # 驱动直径超物理合理范围只记一次
        # ---- 橡皮子模式与手掌擦除（计划第 8 项）
        # eraser_mode 词表跟配置走（presentation.ink.eraser_mode）：pixel 像素 / stroke 整笔
        self._eraser_mode = "pixel"
        self._palm_erasing = False  # 手掌擦除进行中：触点临时以像素擦除干活，工具属性不动
        self._palm_erase_enabled = True
        self._palm_threshold_mm = 20.0
        self._palm_no_diameter_logged = False  # 驱动不报直径只记一次日志
        # ---- 橡皮幻影状态（2026-10-09，消费方是 QML EraserGhost，见信号注释）
        self._ghost_visible = False
        self._ghost_x = 0.0
        self._ghost_y = 0.0
        self._ghost_size = 0.0
        # ---- 工具卡「点空白收起」钩子（2026-10-08 用户报告：自建批注）
        # 笔/橡皮二级卡开着时，落在画布上的第一按要消费成「收起卡片」而不是起笔。
        # 卡片开没开只有控制条知道（QML 侧状态，层够不着），WindowManager 建窗后
        # 把 ``windows._dismiss_tool_cards`` 挂进来；返回 True = 有卡被收起、
        # 这一按不起笔。None（自检直造、窗口侧还没接线）= 老行为，按下直接起笔。
        self.card_dismiss_hook: Callable[[], bool] | None = None
        # ---- 胶囊与悬浮控件碰撞排除（2026-10-10 用户指令：自建批注橡皮擦适配）
        # 鼠标落在软件胶囊/浮层上时隐藏橡皮且不落笔。
        # 外部钩子（放映模式由 WindowManager 挂入）+ QML 排除列表（小黑板等挂入）
        self.capsule_hit_hook: Callable[[float, float], bool] | None = None
        self._excluded_items: list = []

        # 已挂 sceneGraphInvalidated 的窗口（P1-5）：换窗先 disconnect 旧连接，
        # 否则旧窗口场景图失效时会把当前窗口的 _root/_texture 清空
        self._sg_window: QQuickWindow | None = None
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
        if value == "arrow" and (self._smoother is not None or self._palm_erasing or self._pts is not None):
            # 写到一半被切回指针（控制条改道 / 引擎切换）：把手上这笔落掉，别让滤波器
            # 悬挂着吃掉后面的 move 事件。手掌擦除没有滤波器（_smoother 为 None 但
            # _palm_erasing/_pts 在途），同样要收尾，否则切 arrow 后会隐形继续擦。
            # 只在确有在途输入时才调 _finish_input：无输入时它的 else 分支会清
            # _mouse_hovering 并 _set_ghost(False)，破坏「鼠标悬停时切 eraser 立即
            # 显示幻影」的既有行为（见下方联动分支）。
            self._finish_input()
            self._palm_erasing = False
            self._device = None
            self._touch_id = -1
        # 工具切换联动橡皮擦显示（2026-10-10）：
        if value != "eraser":
            self._set_ghost(False)
        elif self._pointer_device == "mouse" and self._mouse_hovering:
            window = self.window()
            if window is not None:
                try:
                    cursor_pos = self.mapFromGlobal(QCursor.pos())
                    self._update_mouse_ghost(cursor_pos.x(), cursor_pos.y())
                except Exception:
                    pass
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
        # 合法性夹取（2026-10-29 触控审计 #17）：宿主把 penWidth*6 算成 0 /
        # 负数 / 超大值时，0.5px 的擦除面配 12px 幻影会让人以为「橡皮坏了」
        width = min(200.0, max(4.0, width))
        if width == self._eraser_width:
            return
        # 只影响下一笔：进行中的擦除笔画在 beginStroke 时已经定了宽度（同 penWidth）
        self._eraser_width = width
        self._stroke_eraser_width = width
        # 若鼠标模式下当前橡皮擦正显示，实时同步尺寸（2026-10-10）
        if self._ghost_visible and self._pointer_device == "mouse":
            self._set_ghost(True, self._ghost_x, self._ghost_y, self._eraser_width)
        return width
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

    # ------------------------------------------------- 橡皮幻影（2026-10-09）
    # 只读属性四件套：按下橡皮（含手掌擦除）期间可见并跟随触点，尺寸 =
    # 擦除宽度（手掌 = 接触直径）。层不画这个 UI —— QML EraserGhost 绑它们渲染，
    # 放映叠加层与小黑板两个宿主零接线成本之外的各自一份声明。
    def _get_eraser_ghost_visible(self) -> bool:
        return self._ghost_visible

    def _get_eraser_ghost_x(self) -> float:
        return self._ghost_x

    def _get_eraser_ghost_y(self) -> float:
        return self._ghost_y

    def _get_eraser_ghost_size(self) -> float:
        return self._ghost_size

    eraserGhostVisible = Property(bool, _get_eraser_ghost_visible, notify=eraserGhostChanged)
    eraserGhostX = Property(float, _get_eraser_ghost_x, notify=eraserGhostChanged)
    eraserGhostY = Property(float, _get_eraser_ghost_y, notify=eraserGhostChanged)
    eraserGhostSize = Property(float, _get_eraser_ghost_size, notify=eraserGhostChanged)

    def _set_ghost(self, visible: bool, x: float | None = None,
                   y: float | None = None, size: float | None = None) -> None:
        """更新幻影状态，任一变化才发信号（移动期每点都调，别把 QML 刷成跑马）。"""
        changed = False
        if visible != self._ghost_visible:
            self._ghost_visible = visible
            changed = True
        if x is not None and x != self._ghost_x:
            self._ghost_x = x
            changed = True
        if y is not None and y != self._ghost_y:
            self._ghost_y = y
            changed = True
        if size is not None and size != self._ghost_size:
            self._ghost_size = size
            changed = True
        if changed:
            self.eraserGhostChanged.emit()

    # ------------------------------------------------- excludedItems（2026-10-10）
    # 供小黑板等 QML 宿主注册悬浮胶囊等浮层控件。鼠标落在这些控件上时不显橡皮也不落笔。
    def _get_excluded_items(self) -> list:
        return self._excluded_items

    def _set_excluded_items(self, val) -> None:
        items = list(val) if val else []
        if items != self._excluded_items:
            self._excluded_items = items
            self.excludedItemsChanged.emit()

    excludedItems = Property("QVariantList", _get_excluded_items, _set_excluded_items, notify=excludedItemsChanged)

    def _is_in_capsule(self, x: float, y: float) -> bool:
        """检查局部坐标 (x, y) 是否落在任何胶囊或排除控件内。"""
        if self.capsule_hit_hook is not None:
            try:
                if self.capsule_hit_hook(x, y):
                    return True
            except Exception:
                log.debug("capsule_hit_hook 执行异常", exc_info=True)
        if self._excluded_items:
            pt = QPointF(x, y)
            for item in self._excluded_items:
                if item is not None and getattr(item, "isVisible", lambda: False)():
                    try:
                        local_pt = self.mapToItem(item, pt)
                        if 0 <= local_pt.x() <= item.width() and 0 <= local_pt.y() <= item.height():
                            return True
                    except Exception:
                        pass
        return False

    def _update_mouse_ghost(self, x: float, y: float) -> None:
        """鼠标移动/悬停时刷新橡皮擦显示状态与位置。"""
        if self._tool != "eraser" and not self._palm_erasing:
            if self._ghost_visible:
                self._set_ghost(False)
            return
        if self._is_in_capsule(x, y):
            if self._ghost_visible:
                self._set_ghost(False)
            return
        self._set_ghost(True, x, y, self._eraser_width)

    def hoverEnterEvent(self, ev: QHoverEvent) -> None:  # noqa: N802 - Qt 虚函数名
        # 互斥防御：若触控/数位板正在画线中，或事件不是真实物理鼠标派生，忽略，不篡改鼠标状态
        if self._device in ("touch", "tablet") or not _is_real_mouse(ev):
            super().hoverEnterEvent(ev)
            return
        self._pointer_device = "mouse"
        self._mouse_hovering = True
        pos = ev.position()
        self._update_mouse_ghost(pos.x(), pos.y())
        super().hoverEnterEvent(ev)

    def hoverMoveEvent(self, ev: QHoverEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if self._device in ("touch", "tablet") or not _is_real_mouse(ev):
            super().hoverMoveEvent(ev)
            return
        self._pointer_device = "mouse"
        self._mouse_hovering = True
        pos = ev.position()
        self._update_mouse_ghost(pos.x(), pos.y())
        super().hoverMoveEvent(ev)

    def hoverLeaveEvent(self, ev: QHoverEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if not _is_real_mouse(ev):
            super().hoverLeaveEvent(ev)
            return
        self._mouse_hovering = False
        # 鼠标离开画布（或进入上层被遮挡的胶囊），未在按压擦除时隐藏橡皮
        if self._smoother is None:
            self._set_ghost(False)
        super().hoverLeaveEvent(ev)

    @property
    def currentPage(self) -> int:  # noqa: N802 - 与 Qt 侧命名风格一致
        return self._page

    # --------------------------------------------- scaleWithSize（2026-11-01）
    # C++ 版先有、Python 侧回植。理由与取舍见文件头「scaleWithSize」一节：
    # 点按 0..1 归一化存、笔宽按逻辑 px 存，改尺寸重烘时位置按横竖两个倍率拉伸、
    # 宽度不动 —— 像素橡皮与笔迹的覆盖关系随之改变，擦净处会露出月牙形残片
    # （小黑板实测：默认窗口里擦净，最大化后冒出「神秘笔迹」）。

    def _get_scale_with_size(self) -> bool:
        return self._scale_with_size

    def _set_scale_with_size(self, value: bool) -> None:
        on = bool(value)
        if on == self._scale_with_size:
            return
        # 在途笔画的点按旧基准归一化，换基准后后半截会错位：先收掉（翻页同款）
        self.cancelStroke()
        self._scale_with_size = on
        if on:
            self._locked_map_size = None
            if self._image is not None:
                self._rebake()  # 按当前尺寸重新展开
        elif self._image is not None:
            # 已有干图 = 墨迹正按当前尺寸摆着：就地锁住，画面不跳。还没烘过就等
            # _rebake 首次烘焙时再锁 —— QML 声明期层还没布局，此刻的尺寸靠不住
            self._locked_map_size = self._size()
        self.scaleWithSizeChanged.emit()

    scaleWithSize = Property(bool, _get_scale_with_size, _set_scale_with_size,
                             notify=scaleWithSizeChanged)

    def _map_size(self) -> tuple[float, float] | None:
        """归一化坐标 ↔ 逻辑像素的换算基准。

        ``scaleWithSize`` 为真时就是当前尺寸；为假时是 ``_locked_map_size``
        （首次烘焙时锁定）。层还没有尺寸返回 None。

        首次烘焙顺带锁基准（``scaleWithSize=false`` 且尚未锁定时）：QML 声明期
        层还没布局，那时读到的尺寸不可信 —— 第一次真正烘图才是可靠时点。
        """
        size = self._size()
        if size is None:
            return None
        if not self._scale_with_size and self._locked_map_size is None:
            self._locked_map_size = size
        if not self._scale_with_size and self._locked_map_size is not None:
            return self._locked_map_size
        return size

    # ------------------------------------------------- canUndo / canRedo
    # 2026-10-08 小黑板搬到 InkLayer（用户指令：照搬叠加层自建批注）：撤销 /
    # 重做按钮的 enabled 要绑层的真操作栈，QML 侧此前自己维护快照栈。
    # 只读 + notify=inkChanged：每次落笔 / 撤销 / 重做 / 清屏都会发 inkChanged，
    # 按钮态随每一次模型变动刷新，不需要独立的变更信号。

    def _get_can_undo(self) -> bool:
        return self.store.can_undo(self._page)

    def _get_can_redo(self) -> bool:
        return self.store.can_redo(self._page)

    canUndo = Property(bool, _get_can_undo, notify=inkChanged)
    canRedo = Property(bool, _get_can_redo, notify=inkChanged)

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
        """整笔擦除：手势期间只累积命中笔画 id（去重），抬笔（endStroke）一次性
        remove_strokes、提交单个 _RemoveOp（P1-1：撤销粒度 = 手势而非事件批 ——
        一笔划过 N 条，一次 undo 全恢复）。

        命中半径与像素橡皮同宽（本笔橡皮宽度 ``_stroke_eraser_width`` 的半径 ——
        2026-10-08 起不再跟 penWidth，保住「两种橡皮同一个大小」的不变量）。
        归一化换算按两轴各自折算（2026-10-29 触控审计 #12：旧实现除以窄边，
        屏幕上命中带是 16:9 的椭圆，横向「隔空擦掉」、纵向擦不到）。抬笔时没
        命中就不记操作（remove_strokes 的语义），撤销栈里也就不会有「没反应」
        的一步。已明示的取舍（Plan P1-1）：被划中的笔画在手势期间不再即时消失，
        抬笔才删。
        """
        if self._stroke_erase_hits is None:
            self._stroke_erase_hits = set()
        radius = radius_of(self._stroke_eraser_width, 1.0)
        rx, ry = radius / size[0], radius / size[1]
        hits = self._stroke_erase_hits
        for p in points:
            x, y = float(p[0]), float(p[1])
            # 已命中的 id 传给 hit_test 剪枝（P2-4）：候选集里被划中过的笔画
            # 不再重复做精确距离计算，长手势后期扫描量随命中数收敛
            hits.update(self.store.hit_test(self._page, x / size[0], y / size[1], rx, ry, exclude=hits))

    @Slot(float, float, float)
    def beginStroke(self, x: float, y: float, w: float) -> None:  # noqa: N802
        if self._pts is not None:
            # 上一笔没收到抬笔（事件丢了）：先落掉，别让已写的墨凭空消失
            self.endStroke()
        # 手掌擦除的宽度覆盖（接触直径）用一次即清；无覆盖时擦除按本笔橡皮
        # 宽度（默认 = eraserWidth 属性，触控路径已被 _begin_input 抬到物理下限）
        width_override = self._stroke_width_override
        self._stroke_width_override = None
        size = self._map_size()
        if size is None:
            # 失败路径显式复位 _mode（P1-4）：上一笔是擦除时残留的 erase 会让
            # 幻影判定误认为这一笔在擦除
            self._mode = "pen"
            return
        # 新手势：整笔擦除的命中累积（P1-1）从零开始
        self._stroke_erase_hits = None
        if self._whole_erase():
            self._erase_whole_at([(x, y, w)], size)
            # 橡皮幻影（P1-4 起判定收口到 beginStroke 成功路径）：整笔擦除不产生
            # 笔画，尺寸 = 本笔橡皮宽度（与命中半径同宽的不变量）
            self._set_ghost(True, x, y, self._stroke_eraser_width)
            return
        mode = self._mode_for_tool()
        if mode is None:
            self._mode = "pen"
            return
        self._ensure_image()
        # 2026-10-08 自建批注：像素擦除按橡皮宽度取宽（不再跟 penWidth）。
        # 2026-10-29 触控审计 #15：手掌擦除的接触直径经 _stroke_width_override
        # 在起笔前就位 —— 旧实现先按 eraserWidth 起笔再覆盖宽度，起手那一帧
        # 会先烘出一个 18px 小圆点闪一下、还多触发一次全量重放。
        self._mode, self._width = mode, (
            width_override if width_override is not None
            else self._stroke_eraser_width if mode == "erase"
            else self._pen_width
        )
        self._color = self._pen_color.name(QColor.NameFormat.HexArgb)
        self._pts = [(x / size[0], y / size[1], float(w))]
        if mode == "pen":
            self._wet = WetMesh(self._pen_color, self._dpr())
            self._wet.add(x, y, radius_of(self._width, w))
            self._publish(wet=self._wet.snapshot())
        else:
            self._erase_base = self._image.copy()
            _img, _dirty = self._erase_preview()
            self._publish(dry=_img, dry_rect=_dirty)
            # 橡皮幻影（2026-10-09）：按下即出现，尺寸 = 这一笔的擦除宽度。
            # 放在成功路径里（P1-4）：beginStroke 因尺寸异常等失败时不再被
            # _begin_input 里残留的 _mode 误触发
            self._set_ghost(True, x, y, self._width)

    @Slot("QVariantList")
    def extendStroke(self, points: Sequence[Sequence[float]]) -> None:  # noqa: N802
        size = self._map_size()
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
            _img, _dirty = self._erase_preview()
            self._publish(dry=_img, dry_rect=_dirty)

    @Slot()
    def endStroke(self) -> None:  # noqa: N802
        hits = self._stroke_erase_hits
        self._stroke_erase_hits = None
        if hits and self.store.remove_strokes(self._page, hits):
            # 整笔擦除手势收尾（P1-1）：手势期间累积的命中一次删除，单个 _RemoveOp
            self._rebake()
            self.inkChanged.emit()
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
            bake(self._image, stroke, self._map_size() or (0.0, 0.0))
            # 抬笔脏矩形 = 这一笔的设备像素包围盒（意图 496）：擦除笔先 _image=base
            # 复原再整笔烘，像素改动仍限于本笔路径 ± 半径，bbox 恒包住；只重建相交 tile。
            self._publish(wet=(0, b""), dry=self._image,
                          dry_rect=self._stroke_dirty_rect(stroke.points, stroke.width))
        else:
            self._rebake(wet=(0, b""))
        self.inkChanged.emit()

    @Slot()
    def cancelStroke(self) -> None:  # noqa: N802
        # 整笔擦除手势作废：丢弃累积的命中（P1-1），无论有无在途笔画都要清
        self._stroke_erase_hits = None
        # 触控会话态一并复位（2026-10-29 触控审计 #16）：翻页 / 撤销 / 清屏 /
        # TouchCancel 都经这里作废在途笔画，不复位的话掌擦幻影会继续跟手、
        # 陈旧 _device/_touch_id 会把下一场（或撤销后）的新 TouchBegin 当
        # 「第二根手指」吞掉（触点 id 小整数循环复用时更会复活幽灵擦除）。
        # 复位幂等：_cancel_input / abort_input 里还会再清一遍。
        self._palm_erasing = False
        self._touch_id = -1
        self._smoother = None
        self._device = None
        # 笔画作废即隐幻影（审计 #16）：旧实现在「掌擦途中翻页」时幻影一直
        # 跟手飘到抬笔，擦除却什么也不掉
        self._set_ghost(False)
        if self._pts is None:
            return
        base = self._erase_base
        self._reset_active()
        if base is not None:
            self._image = base
            self._publish(wet=(0, b""), dry=base)
        else:
            self._publish(wet=(0, b""))

    def abort_input(self) -> None:
        """作废在途输入会话（2026-10-29 触控审计 #8）：窗口隐藏 / 抑制 / 引擎
        切换时由 WindowManager 调用。

        只清会话态与在途笔画（含幻影），不动已落账数据 —— 下一场放映首触
        不会吃到陈旧触点 id（Windows 触点 id 小整数循环复用，残 id 会复活
        幽灵掌擦或把新 TouchBegin 当「第二根手指」吞掉）。
        """
        self._touch_id = -1
        self._palm_erasing = False
        self._mouse_hovering = False
        self._cancel_input()

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
        self._erase_work = None
        self._erase_cursor = -1
        self._erase_cursor_key = None
        self._stroke_erase_hits = None

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

    def _rebake(self, wet: tuple[int, bytes] | None = None) -> None:
        """整页重烘：翻页 / 撤销重做 / 清屏 / 尺寸或 DPR 变化时才走这里。"""
        key, size = self._target_key(), self._size()
        if key is None or size is None:
            self._image, self._image_key = None, None
            return
        image = QImage(key[0], key[1], QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        # 让 QPainter 按逻辑像素画：与湿网格的坐标数字完全一致
        image.setDevicePixelRatio(key[2])
        # 归一化走换算基准：ensureImage_ 可能刚触发首次烘焙并锁定它（scaleWithSize=false）
        map_size = self._map_size() or size
        for stroke in self.store.strokes(self._page):
            bake(image, stroke, map_size)
        self._image, self._image_key = image, key
        if self._pts is not None:
            # 书写途中尺寸变了：按新尺寸重建进行中这一笔的预览
            if self._mode == "erase":
                self._erase_base = image.copy()
                # 换了底图（尺寸/DPR 变了）：工作图与游标一并作废，下一批回退全量重放
                self._erase_work = None
                self._erase_cursor = -1
                # 整页重烘：整张干图都变了（新尺寸/DPR），走 full（忽略增量脏矩形）
                _img, _ = self._erase_preview()
                self._publish(wet=wet, dry=_img)
                return
            self._wet = WetMesh(QColor(self._color), key[2])
            for x, y, w in self._pts:
                self._wet.add(x * map_size[0], y * map_size[1], radius_of(self._width, w))
            wet = self._wet.snapshot()
        self._publish(wet=wet, dry=image)

    def _erase_preview(self) -> tuple[QImage, QRect | None]:
        # 像素橡皮预览，增量烘焙（P0-3 Option A）：每批 extendStroke 只把「上一确认点
        # → 新点」的新增段烘进工作图，消掉此前每批 base.copy() + 全路径重放。
        # 已知可接受差异：分段 Clear 在接缝圆盘处的亚像素 AA 与整笔单次烘焙不同
        # （瞬态、不可辨）；endStroke 仍按整笔一次 bake 提交（layer.py 抬笔路径不动），
        # 抬笔结果与全量重烘逐像素一致 —— ink_eraser_selftest 的等价性护栏盯这条。
        # 返回 (工作图, 脏矩形)：脏矩形 = 本次新烘段的设备像素包围盒（意图 496，供
        # _upload_dry 只重建相交 tile）；无新段则空 QRect（本帧干图未变、不传任何 tile）。
        pts = self._pts
        if pts is None or not pts:
            return self._image, QRect()
        if self._erase_work is None:
            if self._erase_base is None:
                return self._image, QRect()
            # 新一笔（或 _rebake 换底图后）：从落笔前干图副本起步，整条待烘
            self._erase_work = self._erase_base.copy()
            self._erase_cursor = 0
            self._erase_cursor_key = (self._width, self._color)
        elif self._erase_cursor_key != (self._width, self._color):
            # (width, color) 中途变了：增量段与已烘部分口径不一致，回退为一次全量
            # 重放并重置游标，旧口径痕迹不残留。起因是手掌擦除 —— _start_palm_erase
            # 在 beginStroke 之后才把 _width 从 eraserWidth 覆盖成接触直径，首点已按
            # 旧宽烘过（新口径圆盘覆盖同点位旧口径圆盘，全量重放即可对齐抬笔结果）。
            self._erase_work = self._erase_base.copy()
            self._erase_cursor = 0
            self._erase_cursor_key = (self._width, self._color)
        dirty: QRect = QRect()
        if self._erase_cursor == 0 or self._erase_cursor < len(pts) - 1:
            # 脏矩形取本次实际烘的这一段点（含重置后的整条重放：游标=0 时即全段）。
            # 新口径圆盘覆盖旧口径同点位：bbox(新段, 当前宽) 恒包住两者差异区。
            seg = list(pts[self._erase_cursor:])
            bake(self._erase_work,
                 Stroke(points=seg, color=self._color, width=self._width, mode="erase"),
                 self._map_size() or (0.0, 0.0))
            self._erase_cursor = len(pts) - 1
            dirty = self._stroke_dirty_rect(seg, self._width)
        self._image = self._erase_work
        return self._erase_work, dirty

    def _stroke_dirty_rect(self, points: Sequence[Sequence[float]], width: float) -> QRect:
        """把一段笔画点（归一化 0..1）+ 逻辑宽度算成设备像素脏矩形包围盒（意图 496）。

        供 _publish 做 tile 局部更新：只重建与该矩形相交的 tile。矩形按「本段最大半径
        + 羽化带 + 1px AA 余量」向外扩，再逐边向外取整并夹到当前干图设备像素范围内，
        确保覆盖 bake 实际触碰的全部像素（宁可多框一块 tile，不可漏像素留残影）。
        无当前干图 / 无尺寸 / 无点时返回空 QRect（视为本帧无 tile 改动）。
        """
        img, size = self._image, self._size()
        if img is None or size is None or not points:
            return QRect()
        w_log, h_log = size
        dpr = img.devicePixelRatio() or 1.0
        rmax = max(radius_of(width, p[2] if len(p) > 2 else 1.0) for p in points)
        pad = rmax + (FEATHER_DEVICE_PX / dpr) + 1.0  # 逻辑像素
        xs = [p[0] * w_log for p in points]
        ys = [p[1] * h_log for p in points]
        dx0 = max(0, math.floor((min(xs) - pad) * dpr))
        dy0 = max(0, math.floor((min(ys) - pad) * dpr))
        dx1 = min(img.width(), math.ceil((max(xs) + pad) * dpr))
        dy1 = min(img.height(), math.ceil((max(ys) + pad) * dpr))
        if dx1 <= dx0 or dy1 <= dy0:
            return QRect()
        return QRect(dx0, dy0, dx1 - dx0, dy1 - dy0)

    #: _publish 的 dry_rect 省略时的哨兵：表示「整图改动」（调用方没有脏矩形信息，
    #: 如重烘/翻页/undo/清屏/尺寸变 或 perf 的 reupload 基线），须重建全部 tile。
    _DRY_FULL = object()

    def _publish(self, wet: tuple[int, bytes] | None = None, dry: QImage | None = None,
                 dry_rect: object = _DRY_FULL) -> None:
        with self._lock:
            if wet is not None:
                # 一帧内可能多次交接（悬笔收尾后立刻起笔等）：增量段必须合并进
                # 未消费的 pending —— 只留最后一个会丢掉中间的新段（P2-1 增量
                # 语义下与旧全量覆盖行为不等价）。合并公式：渲染侧应用
                # ``shown[:s1] + d1[:s2-s1] + d2`` 与逐个应用等价（s2 >= s1 恒成立，
                # len(d1) >= s2-s1 由 buffer 只追加保证）；清空消息 (0, b"") 直接覆盖。
                pending = self._pending_wet
                if pending is not None and wet[0] > pending[0]:
                    self._pending_wet = (pending[0], pending[1][:wet[0] - pending[0]] + wet[1])
                else:
                    self._pending_wet = wet
            if dry is not None:
                # QImage 隐式共享：之后 GUI 线程再往 _image 上画会自动分离，渲染侧拿到的不变
                self._pending_dry = dry
                # 脏矩形合并（意图 496）：整图(_DRY_FULL/None) 一旦出现本帧即 full；
                # 否则把本次设备像素脏矩形并进 pending（空/无效矩形并集为 no-op，
                # 表示本次没有 tile 被改）。渲染侧只用最后那张 _shown_dry，但它已累积
                # 本帧全部像素改动，并集即覆盖所有被改过的 tile。
                if dry_rect is self._DRY_FULL or dry_rect is None:
                    self._pending_dry_full = True
                elif not self._pending_dry_full:
                    r = dry_rect if isinstance(dry_rect, QRect) else QRect()
                    self._pending_dry_rect = (
                        r if self._pending_dry_rect is None else self._pending_dry_rect.united(r)
                    )
        self._request_update()

    def _request_update(self) -> None:
        self._update_requests += 1
        self.update()

    def geometryChange(self, new_geometry: QRectF, old_geometry: QRectF) -> None:  # noqa: N802
        super().geometryChange(new_geometry, old_geometry)
        if self._image is not None and self._target_key() != self._image_key:
            # 尺寸或 DPR 变了（_target_key 两者都含，P1-6：此前只比尺寸，跨屏
            # DPR 变化 + 纯移动时不会重烘）：坐标归一化，按新口径重烘即可重新对齐
            self._rebake()

    def _on_window_changed(self, win: QQuickWindow | None) -> None:
        old = self._sg_window
        if old is not None and old is not win:
            # 换窗先断开旧连接（P1-5）：DirectConnection 挂在旧窗口上，旧窗口
            # 场景图失效时回调会把当前窗口正在用的 _root/_texture 清空
            try:
                old.sceneGraphInvalidated.disconnect(self._on_sg_invalidated)
            except (RuntimeError, TypeError):
                pass  # 未连接（如窗口先一步销毁）不算错
        self._sg_window = win
        if win is not None and win is not old:
            win.sceneGraphInvalidated.connect(self._on_sg_invalidated, Qt.ConnectionType.DirectConnection)

    def _on_sg_invalidated(self) -> None:
        # 渲染线程、图形上下文仍有效：此时释放纹理最安全；节点已随场景图删除，只丢引用
        self._root = self._wet_node = None
        self._wet_geom = self._wet_mat = self._wet_attrs = None
        self._wet_nodes, self._wet_geoms = [], []
        # 干图 tile 网格一并作废（意图 496）：丢纹理引用 + 清网格尺寸，下次重建
        self._dry_tiles, self._dry_textures = [], []
        self._dry_cols = self._dry_rows = self._dry_img_w = self._dry_img_h = 0
        self._dry_img_dpr = 0.0

    # ------------------------------------------------------------ 渲染线程

    def updatePaintNode(self, old_node, _data):  # noqa: N802 - Qt 虚函数名
        with self._lock:
            wet, dry = self._pending_wet, self._pending_dry
            dry_rect, dry_full = self._pending_dry_rect, self._pending_dry_full
            self._pending_wet = self._pending_dry = None
            self._pending_dry_rect, self._pending_dry_full = None, False
        changed_from = 0
        if wet is not None:
            start, data = wet
            if data:
                # 增量交接（P2-1）：data 从 _shown_wet 的 start 字节起替换
                # （新段 + 新笔尖），start 之前的字节本帧没变
                self._shown_wet = self._shown_wet[:start] + data
                changed_from = start
            else:
                self._shown_wet = b""
        if dry is not None:
            self._shown_dry = dry
        rebuilt = old_node is None or self._root is None
        if rebuilt:
            self._build_nodes()
        if rebuilt or dry is not None:
            # 节点重建 或 整图改动(dry_full) 或 本帧缺脏矩形 → 全部 tile 重建；
            # 否则只重建与 dry_rect 相交的 tile（意图 496）。tile 的矩形在建格时
            # 按干图设备像素/DPR 一次定好，不再每帧 setRect（整图拉伸由重烘兜底）。
            self._upload_dry(None if (rebuilt or dry_full) else dry_rect)
        if rebuilt or wet is not None:
            # 重建节点后所有 chunk 都是新的，从 0 全量上传；否则只传 changed_from 起
            self._upload_wet(0 if rebuilt else changed_from)
        return self._root

    def _build_nodes(self) -> None:
        # 干图 tile 网格作废（意图 496）：新 _root 下旧 tile 节点已失效，丢引用 +
        # 清网格尺寸，_upload_dry 下次会按当前干图尺寸整格重建
        self._dry_tiles, self._dry_textures = [], []
        self._dry_cols = self._dry_rows = self._dry_img_w = self._dry_img_h = 0
        self._dry_img_dpr = 0.0
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

    def _upload_dry(self, dirty_rect: QRect | None = None) -> None:
        """干图上传（意图 496）：干图切成 DRY_TILE_DEVICE_PX 网格、每块一个纹理节点。

        dirty_rect=None → 全部 tile 重传（节点重建 / 整图改动 / 本帧缺脏矩形）；
        给设备像素 QRect → 只重建与之相交的 tile（局部擦除通常只动 1~4 块）。
        干图尺寸或 DPR 变了则整格重建。上传量正比脏面积而非满页。
        """
        img, win = self._shown_dry, self.window()
        if img is None or img.isNull() or win is None:
            return
        iw, ih = img.width(), img.height()
        dpr = img.devicePixelRatio() or 1.0
        if (not self._dry_tiles or self._dry_img_w != iw
                or self._dry_img_h != ih or self._dry_img_dpr != dpr):
            self._rebuild_dry_grid(img, win, iw, ih, dpr)
            return
        # 脏矩形缺失 / 空 / 无效 → 全部重传；否则只碰相交 tile
        full = not isinstance(dirty_rect, QRect) or dirty_rect.isEmpty()
        tile = DRY_TILE_DEVICE_PX
        for r in range(self._dry_rows):
            for c in range(self._dry_cols):
                dx, dy = c * tile, r * tile
                dw, dh = min(tile, iw - dx), min(tile, ih - dy)
                if not full and not QRect(dx, dy, dw, dh).intersects(dirty_rect):
                    continue
                self._upload_dry_tile(img, win, r * self._dry_cols + c, dx, dy, dw, dh, dpr)

    def _rebuild_dry_grid(self, img: QImage, win, iw: int, ih: int, dpr: float) -> None:
        """首次 / 尺寸或 DPR 变化时整格重建：移除旧 tile 节点，按新尺寸建格并全量上传。"""
        for node in self._dry_tiles:
            self._root.removeChildNode(node)
        self._dry_tiles, self._dry_textures = [], []
        tile = DRY_TILE_DEVICE_PX
        cols, rows = max(1, math.ceil(iw / tile)), max(1, math.ceil(ih / tile))
        self._dry_cols, self._dry_rows = cols, rows
        self._dry_img_w, self._dry_img_h, self._dry_img_dpr = iw, ih, dpr
        for r in range(rows):
            for c in range(cols):
                dx, dy = c * tile, r * tile
                dw, dh = min(tile, iw - dx), min(tile, ih - dy)
                node = QSGSimpleTextureNode()
                node.setOwnsTexture(False)
                node.setFiltering(QSGTexture.Filtering.Linear)
                # tile 逻辑矩形 = 设备像素 / dpr：相邻块边界精确衔接、无缝
                node.setRect(QRectF(dx / dpr, dy / dpr, dw / dpr, dh / dpr))
                # 干图在下、湿网格在上：各 tile prepend 到 root 最前（湿块都 append 在后，恒在上）
                self._root.prependChildNode(node)
                self._dry_tiles.append(node)
                self._dry_textures.append(None)
                self._upload_dry_tile(img, win, len(self._dry_tiles) - 1, dx, dy, dw, dh, dpr)

    def _upload_dry_tile(self, img: QImage, win, idx: int,
                         dx: int, dy: int, dw: int, dh: int, dpr: float) -> None:
        """重建单块 tile 纹理：从干图扣出该块设备像素子图，建纹理挂到对应节点。"""
        sub = img.copy(QRect(dx, dy, dw, dh))  # 设备像素子图；隐式共享 detach 成独立缓冲
        tex = win.createTextureFromImage(sub, QQuickWindow.CreateTextureOption.TextureHasAlphaChannel)
        node = self._dry_tiles[idx]
        node.setTexture(tex)
        # 先挂新纹理再丢旧引用，旧纹理此时才被释放
        self._dry_textures[idx] = tex
        node.markDirty(QSGNode.DirtyStateBit.DirtyMaterial)

    def _upload_wet(self, changed_from: int = 0) -> None:
        data = self._shown_wet
        count = len(data) // VERTEX_SIZE
        chunks = max(1, math.ceil(count / WET_CHUNK_VERTICES))
        while len(self._wet_geoms) < chunks:
            self._add_wet_chunk()
        # 只重传新增段可能落进的 chunk（P2-2）：changed_from 之前的字节本帧没变，
        # 未变 chunk 跳过 allocate/memmove，渲染结果与全量重传逐字节一致。
        # 节点重建 / 清空时 changed_from=0，等价于全量上传。
        chunk_bytes = WET_CHUNK_VERTICES * VERTEX_SIZE
        first = min(changed_from // chunk_bytes, chunks - 1)
        for i in range(first, len(self._wet_geoms)):
            geom, node = self._wet_geoms[i], self._wet_nodes[i]
            start = i * WET_CHUNK_VERTICES
            n = min(WET_CHUNK_VERTICES, count - start)
            if n > 0:
                geom.allocate(n)
                # allocate 可能换缓冲区，写入必须在它之后
                _blit_vertex_data(geom, data[start * VERTEX_SIZE:(start + n) * VERTEX_SIZE])
            else:
                # 湿墨迹「清空」不能 allocate(0)：实测（PySide6 6.11 / D3D11）顶点数归零后渲染器把该节点
                # 移出批次，之后再给它新顶点也不再画——第二笔起湿墨迹整条不可见，只有抬笔后的干图出现。
                # 换成 3 个全零顶点：零面积、alpha=0 的退化三角形，什么都不画，但节点留在批次里。
                # 多出来的分块同理：不删节点，只置成占位。
                geom.allocate(WET_PLACEHOLDER_VERTICES)
                _clear_vertex_data(geom, WET_PLACEHOLDER_VERTICES * VERTEX_SIZE)
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
                handled = self._touch_begin(ev)
                if handled:
                    # ⚠️ 必须显式 accept：Qt Quick 的触摸投递是「谁 accept 谁拿
                    # grab」，只 return True 不算接受。不 accept 时后续
                    # TouchUpdate/TouchEnd 不保证回到本层 —— 真机症状：手指
                    # 按下再放开后橡皮幻影停在原位置（收笔/隐藏整段丢失）。
                    # 合成测试直接 sendEvent 给 item 会绕过 grab，故长期没测出。
                    ev.accept()
                return handled
        elif et in (QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            # 门放宽到「有在跟的触点」（2026-10-29 触控审计 #3/#4）：起笔槽被
            # 掌缘尺度触点占住、还没落墨时 _device 仍是 None，但后续 Update
            # 必须进 _touch_step 才能完成「指尖接管 / 掌抬指续写」的仲裁
            if self._device == "touch" or self._touch_id >= 0:
                handled = self._touch_step(ev, et)
                if handled:
                    ev.accept()  # 同理：保持 grab，别让 Qt 合成鼠标事件
                return handled
        elif et == QEvent.Type.TabletPress:
            # 互斥防御（P1-7，对齐 mousePressEvent 的语义）：鼠标/触控有在途笔画时
            # 忽略并消费，不让平板按下打断其他设备正在进行的笔画
            if self._device in ("mouse", "touch"):
                ev.accept()
                return True
            if self._tool in ("pen", "eraser"):
                self._begin_input("tablet", ev.position().x(), ev.position().y(),
                                  ev.timestamp() * 0.001, ev.pressure())
                ev.accept()
                return True
        elif et in (QEvent.Type.TabletMove, QEvent.Type.TabletRelease):
            if self._device == "tablet":
                self._tablet_step(ev, et)
                ev.accept()
                return True
        return super().event(ev)

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        # 互斥防御：若当前正在处理 touch 或 tablet 笔画，忽略（避免合成鼠标事件打断触控）
        if self._device in ("touch", "tablet"):
            ev.accept()
            return
        # 若是触屏/触笔派生的合成鼠标事件，忽略，不篡改鼠标状态
        if not _is_real_mouse(ev):
            ev.accept()
            return
        if ev.button() == Qt.MouseButton.LeftButton and self._tool in ("pen", "eraser"):
            self._pointer_device = "mouse"
            self._mouse_hovering = True
            pos = ev.position()
            # 若落在排除的胶囊内，不进自建批注输入（2026-10-10）
            if self._is_in_capsule(pos.x(), pos.y()):
                super().mousePressEvent(ev)
                return
            self._begin_input("mouse", pos.x(), pos.y(), ev.timestamp() * 0.001, None)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if self._device in ("touch", "tablet"):
            ev.accept()
            return
        if not _is_real_mouse(ev):
            ev.accept()
            return
        if self._device == "mouse" and self._smoother is not None:
            self._pointer_device = "mouse"
            self._mouse_hovering = True
            pos = ev.position()
            self._extend_input(pos.x(), pos.y(), ev.timestamp() * 0.001, None)
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 - Qt 虚函数名
        if self._device in ("touch", "tablet"):
            ev.accept()
            return
        if not _is_real_mouse(ev):
            ev.accept()
            return
        if self._device == "mouse" and self._smoother is not None:
            self._pointer_device = "mouse"
            self._mouse_hovering = True
            # 抬笔位置补进点流再收（与平板同）：笔画精确停在松手处，与最后一个 move 有
            # 几像素差时不吃这个差
            pos = ev.position()
            self._extend_input(pos.x(), pos.y(), ev.timestamp() * 0.001, None)
            # 抬笔实际坐标传给 _finish_input（P1-3）：胶囊判定用事件坐标，不用 ghost 坐标
            self._finish_input(pos.x(), pos.y())
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
        # 设备互斥：如果鼠标或其他设备正在书写中，不抢占当前笔画
        if self._device is not None and self._device != "touch":
            return False
        self._pointer_device = "touch"
        self._mouse_hovering = False
        self._sample_contacts(ev)
        if self._device == "touch":
            # 已在跟第一个触点：再来 TouchBegin 是第二根手指，不换跟踪目标 ——
            # 但多指聚齐（≥3 指）或大掌缘落下会触发手掌擦除，触发时把跟踪切到掌面
            if self._tool in ("pen", "eraser") and not self._palm_erasing:
                palm = self._palm_trigger_point(ev)
                if palm is not None and self._should_trigger_palm(palm, ev):
                    self._finish_input()  # 手上这笔记账，让位给手掌擦除
                    self._start_palm_erase(palm)
            return True
        if self._tool not in ("pen", "eraser"):
            return False
        pts = ev.points()
        # PySide6.11 里 State 是普通枚举、没有旗标运算；起笔点状态就是单值 Pressed
        # 起笔槽仲裁（2026-10-29 触控审计 #3）：多指同落时挑接触最小的当指尖，
        # 别拿 pts[0] 当起笔点 —— 顺序由驱动决定，掌缘排在前面就会「落笔画细线」
        pressed = [p for p in pts if p.state() == QEventPoint.State.Pressed]
        point = min(pressed, key=self._contact_px) if pressed else (pts[0] if pts else None)
        if point is None:
            return False
        self._touch_id = point.id()
        self._log_no_diameter_once(point)
        # 单指画笔起笔保护：未达到真正手掌肉垫尺度不切擦除，保证正常画笔出墨
        palm = self._palm_trigger_point(ev)
        if palm is not None and self._should_trigger_palm(palm, ev):
            self._start_palm_erase(palm)
            return True
        pos = point.position()
        self._touch_contact_px = self._contact_px(point)
        self._touch_begin_ms = float(ev.timestamp())
        self._begin_input("touch", pos.x(), pos.y(), ev.timestamp() * 0.001, point.pressure())
        return True

    def _touch_step(self, ev: QTouchEvent, et: QEvent.Type) -> bool:
        self._pointer_device = "touch"
        self._mouse_hovering = False
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
            if palm is not None and self._should_trigger_palm(palm, ev):
                self._finish_input()
                self._start_palm_erase(palm)
                return True
        # 起笔槽仲裁（2026-10-29 触控审计 #3）：起笔触点是掌缘尺度而误起笔还
        # 小而新时，新落下的指尖接管书写并作废误起笔。条件细节见
        # :meth:`_takeover_palm_start_worth_it` —— 正常书写触点不受影响：
        # 第二指落下依旧不换目标（既有 test 4 语义）。
        if (self._tool in ("pen", "eraser") and not self._palm_erasing
                and self._device == "touch"):
            takeover = self._pick_smallest_new_pressed(ev)
            if (takeover is not None and self._is_fingertip_contact(takeover)
                    and self._takeover_palm_start_worth_it(ev)):
                self._cancel_input()  # 掌缘误起笔：小而新，整笔作废不留墨点
                self._touch_id = takeover.id()
                pos = takeover.position()
                self._begin_input("touch", pos.x(), pos.y(),
                                  ev.timestamp() * 0.001, takeover.pressure())
                return True
        if point is None:
            # 跟丢触点（驱动没送 End）：按抬笔收尾，别让笔画和滤波器悬挂
            self._touch_id = -1
            was_palm = self._palm_erasing
            self._finish_input()
            self._palm_erasing = False
            if was_palm:
                self._resume_after_palm(ev)
            return True
        pos = point.position()
        t = ev.timestamp() * 0.001
        # 抬笔看触点状态而不是事件类型：TouchEnd 只在整组触点全抬时才发，
        # 多指里先抬一根是 TouchUpdate 载着 Released 状态的点来的（QQuickDeliveryAgent
        # 实测会把合成的部分 TouchEnd 归一成 TouchUpdate），只看 et 笔画就会悬挂
        if et == QEvent.Type.TouchEnd or point.state() == QEventPoint.State.Released:
            self._touch_id = -1
            was_palm = self._palm_erasing
            if was_palm:
                self._extend_palm(pos.x(), pos.y())
            elif not self._release_is_noise(pos):
                # 抬笔点离群判定（2026-10-29 触控审计 #20）：抬笔瞬间指腹形变的
                # 侧向大跳变只用于判定抬手、不喂滤波，笔画停在滤波处 —— 旧实现
                # 会拉出 10~37px 的「倒钩」。正常快笔 / 折线方向连续，不受影响
                self._extend_input(pos.x(), pos.y(), t, point.pressure())
            self._finish_input()
            self._palm_erasing = False
            if was_palm:
                # 掌擦收尾后仍按着的指尖无缝续写（审计 #4）：旧实现 _device 归 None
                # 后剩余手指的 Update 连 _touch_step 都进不去，必须全部抬手重按
                self._resume_after_palm(ev)
            return True
        if self._palm_erasing and self._tool not in ("pen", "eraser"):
            # 防线（P0-2）：手掌擦除进行中工具被切走（如 arrow），按 TouchEnd 语义
            # 收尾，别让擦除在隐形状态下继续吃后续 TouchUpdate
            self._touch_id = -1
            self._finish_input()
            self._palm_erasing = False
            return True
        if self._palm_erasing:
            self._extend_palm(pos.x(), pos.y())
            return True
        self._extend_input(pos.x(), pos.y(), t, point.pressure())
        self._update_feed_reference(pos.x(), pos.y())
        return True

    # ---- 触控槽仲裁与抬笔防倒钩的纯决策助手（2026-10-29 触控审计 #3/#4/#20）

    def _pick_smallest_new_pressed(self, ev: QTouchEvent) -> QEventPoint | None:
        """事件里新落下的（Pressed 且非当前跟踪）触点，按接触尺度取最小者。"""
        cands = [p for p in ev.points()
                 if p.state() == QEventPoint.State.Pressed and p.id() != self._touch_id]
        if not cands:
            return None
        return min(cands, key=self._contact_px)

    def _is_fingertip_contact(self, point: QEventPoint) -> bool:
        """触点是否够「指尖」尺度（长轴 < 手掌阈值）；拿不到阈值（无屏幕参数）
        视为真 —— 与掌擦「无法判定不触发」对偶，仲裁放行保持旧行为。"""
        threshold = self._palm_threshold_px()
        if threshold <= 0:
            return True
        return self._contact_px(point) < threshold

    def _takeover_palm_start_worth_it(self, ev: QTouchEvent) -> bool:
        """掌缘误起笔是否值得让位给新落下的指尖（2026-10-29 触控审计 #3）。

        三个条件都满足才让位：起笔触点达到掌缘尺度（≥阈值）、误起笔还小
        （≤4 点）、且还新（≤400ms）——「掌缘先搭屏、指尖随后落下写字」时，
        掌缘那几笔是误起笔，作废掉不留墨点。起笔触点本来就小（正常指尖
        书写）时恒不让位 —— 第二指落下不打断书写；误起笔已经写长（用户真
        在用大面积接触书写 / 驱动不报直径时接触恒 0）也恒不让位，落账后
        由指尖另起一笔。
        """
        threshold = self._palm_threshold_px()
        if threshold <= 0 or self._touch_contact_px < threshold:
            return False
        if self._pts is not None and len(self._pts) > 4:
            return False
        return float(ev.timestamp()) - self._touch_begin_ms <= 400.0

    def _resume_after_palm(self, ev: QTouchEvent) -> None:
        """掌擦结束后把仍按着的指尖接管为新一笔（2026-10-29 触控审计 #4）。

        「手掌搭屏擦一段 + 食指继续写」不用抬手重按。只接管指尖尺度的触点
        （剩下的还是掌面就不接管，等它们抬起走自然收尾）。
        """
        if self._tool not in ("pen", "eraser") or self._smoother is not None:
            return
        cands = [p for p in ev.points() if p.state() != QEventPoint.State.Released]
        if not cands:
            return
        cand = min(cands, key=self._contact_px)
        if not self._is_fingertip_contact(cand):
            return
        self._touch_id = cand.id()
        pos = cand.position()
        self._begin_input("touch", pos.x(), pos.y(),
                          ev.timestamp() * 0.001, cand.pressure())

    def _update_feed_reference(self, x: float, y: float) -> None:
        """记录最后喂给滤波的触控位置与该段方向（抬笔离群判定的参照系）。"""
        dx, dy = x - self._last_feed_x, y - self._last_feed_y
        if dx or dy:
            self._last_feed_dx, self._last_feed_dy = dx, dy
        self._last_feed_x, self._last_feed_y = x, y

    def _release_is_noise(self, pos) -> bool:
        """抬笔点是否为指腹形变噪点（2026-10-29 触控审计 #20，仅触控路径）。

        距上次喂点 ≥ :data:`_RELEASE_JUMP_MIN_PX` 且方向与前段夹角超过 90°
        （点积 < 0）才算：抬笔瞬间电容屏的离屏质心漂移是「反向大跳」；
        正常收笔补点距离近、快笔 / 折线方向连续，都照常喂。起笔即抬
        （无前段方向）点积为 0，不算噪点 —— 点击出点不受影响。
        """
        dx, dy = pos.x() - self._last_feed_x, pos.y() - self._last_feed_y
        if dx * dx + dy * dy < _RELEASE_JUMP_MIN_PX * _RELEASE_JUMP_MIN_PX:
            return False
        return dx * self._last_feed_dx + dy * self._last_feed_dy < 0.0

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
        self._pointer_device = device
        if self._tool not in ("pen", "eraser"):
            # arrow 态不接受任何输入（头注释）：投递层关了鼠标，这里再兜 QA 直投事件的底
            return
        if self.card_dismiss_hook is not None and self.card_dismiss_hook():
            # 工具卡正开着：这一按是「点空白收起」，消费掉不起笔（2026-10-08
            # 自建批注）。不落 _device / _smoother，随后的 move / release 自然
            # 走基类放行，不会半路挂出一笔。
            # 收卡检查在胶囊检查之前（O6 顺序统一，2026-10-28）：原「先胶囊后
            # 收卡」在卡开着且按点落进胶囊时既不收卡也不起笔，卡继续挡着 ——
            # 与收卡机制「卡开着的第一按恒收起」的整体语义（黑板弹层吞噬层
            # 同款，P2-7）不一致。收卡后同样不落输入态，胶囊保护照旧生效。
            return
        if self._is_in_capsule(x, y):
            # 胶囊 / 排除控件内不起笔（2026-10-18 plugin-audit B1 统一到入口）：
            # 这道检查此前只接在 mousePressEvent（2026-10-10），触屏/触笔
            # 直达 _begin_input，落在胶囊上会隔空起笔误画。不落 _device /
            # _smoother，随后的 move / release 自然走基类放行，不会半路
            # 挂出一笔。鼠标路径 mousePressEvent 的预检保留（它要先放行
            # 基类再返回，行为不变），这里对三路兜底。
            return
        if self._smoother is not None:
            # 上一笔没收到抬笔（事件丢了）：先落掉，别让已写的墨凭空消失
            self._finish_input()
        self._device = device
        # 本笔橡皮宽度：默认跟 eraserWidth 属性；触控路径抬高到物理下限
        # （2026-10-29 触控审计 #11，见 _touch_eraser_floor_px）
        self._stroke_eraser_width = self._eraser_width
        if device == "touch" and self._tool == "eraser":
            floor = self._touch_eraser_floor_px()
            if floor > self._stroke_eraser_width:
                self._stroke_eraser_width = floor
        # 抬笔离群判定的参照系从本笔起点重新计（2026-10-29 审计 #20）
        self._last_feed_x, self._last_feed_y = x, y
        self._last_feed_dx = self._last_feed_dy = 0.0
        self._smoother = StrokeSmoother(device=device, has_pressure=_device_has_pressure(device, pressure))
        out = self._smoother.begin(x, y, t, pressure)
        if out:
            self.beginStroke(out[0][0], out[0][1], out[0][2])
        # 橡皮幻影不再在这里判定（P1-4）：旧逻辑读 _mode / _whole_erase，而
        # beginStroke 失败（尺寸异常、smoother 没出点）时 _mode 残留上一笔的
        # erase 会误显幻影。判定已移入 beginStroke 成功路径。手掌擦除不走
        # _begin_input，_start_palm_erase 自己维护幻影。

    def _extend_input(self, x: float, y: float, t: float, pressure: float | None) -> None:
        if self._smoother is None:
            return
        out = self._smoother.add(x, y, t, pressure)
        if out:
            self.extendStroke(out)
        if self._ghost_visible:
            self._set_ghost(True, x, y)

    def _finish_input(self, x: float | None = None, y: float | None = None) -> None:
        smoother = self._smoother
        device = self._device
        self._smoother = None
        self._device = None
        # 抬笔后的橡皮擦显示判定（2026-10-10 用户指令：鼠标移动始终显示，触控按下才显示）：
        # 触控与平板笔：按下去才显示，抬起即隐藏；
        # 鼠标：如果是橡皮擦工具且仍在画布上且不在胶囊内，抬起后保持橡皮擦显示。
        # 胶囊判定用抬笔事件的实际坐标（P1-3）：ghost 从未显示时 _ghost_x/_ghost_y
        # 停在 (0,0)，拿陈旧坐标判胶囊会把「抬笔点在胶囊内」误判成可显示（或反之）；
        # ghost 坐标仅作显示用途。鼠标路径由 mouseReleaseEvent 传入实际抬笔点。
        if device == "mouse":
            gx = self._ghost_x if x is None else x
            gy = self._ghost_y if y is None else y
            if (self._tool == "eraser" or self._palm_erasing) and self._mouse_hovering and not self._is_in_capsule(gx, gy):
                self._set_ghost(True, gx, gy, self._eraser_width)
            else:
                self._set_ghost(False)
        else:
            self._mouse_hovering = False
            self._set_ghost(False)
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
        self._set_ghost(False)
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

    def _contact_axes(self, point: QEventPoint) -> tuple[float, float] | None:
        """接触椭圆两轴（逻辑 px），缺失 / 不可信返回 None。

        「不可信」的判据（2026-10-29 触控审计 #9）：任一轴超过
        :data:`_CONTACT_CAP_MM` 毫米等效像素 —— 驱动把接触面积按 himetric
        上报时数值会大一个数量级，无上限的长轴会让每一按都判成手掌、
        橡皮幻影糊满屏。超限按「驱动不报直径」同款处理（掌擦静默禁用，
        绝不影响笔画本身），只记一次日志。
        """
        d = point.ellipseDiameters()
        w, h = d.width(), d.height()
        if w <= 0 or h <= 0:
            return None
        px_per_mm = self._px_per_mm()
        if px_per_mm > 0:
            cap = _CONTACT_CAP_MM * px_per_mm
            if w > cap or h > cap:
                if not self._palm_bad_diameter_logged:
                    self._palm_bad_diameter_logged = True
                    log.info(
                        "触屏驱动上报的接触直径超出物理合理范围（%.0fx%.0f 逻辑 px，"
                        "上限 %.0f），按无直径处理",
                        w, h, cap,
                    )
                return None
        return (w, h)

    def _contact_px(self, point: QEventPoint) -> float:
        """触点接触尺度（长轴，逻辑 px）；驱动不给 / 不可信返回 0。

        手掌【判定】用长轴：判定看「最大延伸」才接得住侧缘贴屏（椭圆 40x12mm）。
        擦除【宽度】另见 :meth:`_palm_erase_width_px`（2026-10-31 fact 515：旧实现
        擦除也用长轴，细长掌缘短轴方向大幅过擦；现按短轴限幅）。
        """
        axes = self._contact_axes(point)
        return 0.0 if axes is None else max(axes)

    def _palm_erase_width_px(self, point: QEventPoint) -> float:
        """手掌擦除圆直径（逻辑 px）：按接触【短轴】限幅，收敛细长掌缘的过擦。

        引擎只支持圆盘 stamp，擦除区域必是圆。接触是 长轴×短轴 的椭圆；用长轴做
        圆直径会在短轴方向过擦 (长-短)/2（50x15mm 掌缘达 17.5mm，面积多 235%，
        2026-10-31 量化见 fact 515 / data/tasks/9/i501/palm_overerase_measure.py）。
        夹到 min(长轴, 短轴×:data:`_PALM_ERASE_MAX_ASPECT`)：
          · 近圆接触（长短轴比 ≤ 倍数，如掌根 45x30mm）→ 不变（仍用长轴）；
          · 细长掌缘（如 50x15mm，比 3.3）→ 夹到 短轴×2 = 30mm，短轴过擦从 17.5→7.5mm。
        长轴方向由此略欠擦，交给抹擦轨迹扫掠补偿（掌擦恒为拖动手势）。
        拿不到两轴（驱动不报 / 超物理上限）时回退到旧口径（长轴 = _contact_px），
        行为不变。幻影尺寸在 beginStroke 里统一 = 擦除宽度（self._width），自动跟随。
        """
        axes = self._contact_axes(point)
        if axes is None:
            return self._contact_px(point)
        long_ax, short_ax = max(axes), min(axes)
        return min(long_ax, short_ax * _PALM_ERASE_MAX_ASPECT)

    def _px_per_mm(self) -> float:
        """屏幕物理密度（逻辑 px/mm）；拿不到屏幕返回 0（调用方自行降级）。

        单位对齐（2026-10-29 触控审计 #2 定案，别改回去）：Qt 文档明示
        ``QScreen.physicalDotsPerInch`` 是 **device-independent dots/inch**、
        ``QEventPoint.ellipseDiameters`` 是 **logical pixels** —— 两端本已同
        单位，换算链条里**不再乘除 dpr**。旧实现在这里多除一次 dpr，
        4K@150% 一体机的「20mm」实效只有 ≈14mm，指腹用力就撞手掌阈值
        （顿笔误擦回归），且自检把错误断言固化了。夹取范围见 P2-5。
        """
        window = self.window()
        screen = window.screen() if window is not None else None
        if screen is None:
            return 0.0
        dpi = min(_PALM_DPI_CLAMP_MAX, max(_PALM_DPI_CLAMP_MIN, screen.physicalDotsPerInch()))
        return dpi / 25.4

    def _palm_threshold_px(self) -> float:
        """阈值毫米 → 逻辑 px。拿不到屏幕物理参数返回 0（无法判定 = 不触发）。

        换算经 :meth:`_px_per_mm`（单位对齐的定案说明在那边）；夹紧后
        20mm 阈值折算约 37.8~378 逻辑 px。注意 1080p 一体机上
        ``physicalDotsPerInch`` 可能被 HORZSIZE 虚报（恒 ≈96 或夹到 48），
        阈值会偏大（漏擦掌缘）——宁可漏擦不能误擦，标定功能留待配置侧。
        """
        if self._palm_threshold_mm <= 0:
            return 0.0
        px_per_mm = self._px_per_mm()
        if px_per_mm <= 0:
            return 0.0
        return self._palm_threshold_mm * px_per_mm

    def _touch_eraser_floor_px(self) -> float:
        """触控橡皮的物理下限（逻辑 px）；拿不到物理参数返回 0 = 不设下限。

        2026-10-29 触控审计 #11：橡皮宽度按配置的逻辑 px 走，4K 一体机上
        默认 18px ≈ 9mm，比指腹（12~18mm）还小，幻影被手指完全遮住、
        擦除带比指腹窄，「看不见也擦不动」。触控路径把本笔宽度抬到
        :data:`_TOUCH_ERASER_FLOOR_MM` 毫米等效（上限 60px 兜 absurd DPI），
        鼠标 / 平板路径不受影响。
        """
        px_per_mm = self._px_per_mm()
        if px_per_mm <= 0:
            return 0.0
        return min(60.0, _TOUCH_ERASER_FLOOR_MM * px_per_mm)

    def _palm_pick(self, samples):
        """手掌判定（纯决策，QA 直接驱动；样本由 _palm_trigger_point 从事件提取）。

        samples: [(id, released, contact_px, x, y)]。触发条件（决策 Q3）：
        任一按下中的触点直径 ≥ 阈值，或同时 ≥3 个按下触点。无直径的触点
        （contact_px=0，驱动不报）不参与「大接触面」判定，但计入 ≥3 指分支
        （P1-10：无直径驱动的多指误触也能进掌擦，命中者的 contact_px=0 由
        _start_palm_erase 的 max(contact, 2.0) 兜底成 2px 微擦而非画线）。
        命中返回 (id, x, y, contact_px)，否则 None。
        """
        threshold = self._palm_threshold_px()
        if not self._palm_erase_enabled or threshold <= 0:
            return None
        pressed = [s for s in samples if not s[1]]
        big = [s for s in pressed if s[2] >= threshold]
        if big:
            s = max(big, key=lambda item: item[2])
            return (s[0], s[3], s[4], s[2])
        if len(pressed) >= 3 and self._three_finger_plausible(pressed):
            s = max(pressed, key=lambda item: item[2])
            return (s[0], s[3], s[4], s[2])
        return None

    def _three_finger_plausible(self, pressed) -> bool:
        """≥3 指分支的空间约束（2026-10-29 触控审计 #15）。

        三个触点彼此散布超过 :data:`_PALM_SPAN_MM`（一手掌跨度）时，更像
        「两只手各指一处」/ 水渍油污的幽灵触点 —— 不判掌擦，否则会在
        「最大接触点」（可能在屏幕另一头）凭空开擦掉无关板书。拿不到
        px/mm（无窗口 / 自检替身）时不设限，保持旧行为。
        """
        px_per_mm = self._px_per_mm()
        if px_per_mm <= 0:
            return True
        xs = [s[3] for s in pressed]
        ys = [s[4] for s in pressed]
        span = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        return span <= _PALM_SPAN_MM * px_per_mm

    def _palm_trigger_point(self, ev: QTouchEvent) -> QEventPoint | None:
        samples = [(p.id(), p.state() == QEventPoint.State.Released, self._contact_px(p),
                    p.position().x(), p.position().y()) for p in ev.points()]
        hit = self._palm_pick(samples)
        if hit is None:
            return None
        return next((p for p in ev.points() if p.id() == hit[0]), None)

    def _should_trigger_palm(self, palm: QEventPoint, ev: QTouchEvent) -> bool:
        """判定触点是否满足手掌擦除触发条件（解剖学与单指保护）。

        2026-10-10 用户反馈：单指触控使用画笔时有概率误触发手掌擦除变成橡皮擦。
        根因与人体解剖学：
        成年人食指/拇指用力下压或斜向指腹书写时，接触椭圆长轴常可达 18~28mm，
        极易触碰默认 20mm 阈值边界。而人体真正手掌（掌缘小鱼际/掌根肉垫）接触
        长轴普遍在 36~60mm 以上。
        因此分流保护：
        1. 多指抹擦：活跃接触点（排除 Released）≥3 个，坚决触发手掌；
        2. 书写途中新触点落下：当前已有单指书写（_device == "touch" 且 _touch_id >= 0），
           新触点 palm.id() != self._touch_id 且达到阈值 × 1.35 裕度（P1-2：指腹
           用力下压可达 18~28mm，贴着基础阈值的新触点不草率切掌），判定为掌缘贴屏，切手掌；
        3. 单指/书写触点自身：如果仅有 1~2 个接触点，且触发点为当前触点自身
           （或起笔时该单一触点）：
           接触直径必须达到真正手掌肉垫尺度（>= threshold * 1.75，约 35mm 以上）才允许触发；
           若未达到（< threshold * 1.75），坚决不触发，确保单指画笔 100% 稳定出墨。
        """
        thresh_px = self._palm_threshold_px()
        if thresh_px <= 0 or not self._palm_erase_enabled:
            return False

        active_pts = [p for p in ev.points() if p.state() != QEventPoint.State.Released]

        # 规则 1：多指聚齐抹擦（≥3 个活跃触点）
        if len(active_pts) >= 3:
            return True

        # 规则 2：书写途中新触点落下（掌缘肉垫贴屏，触点 id 与当前正在书写的触点不同）。
        # 加 1.35x 裕度（P1-2，与头注释「防顿笔误擦」口径一致）：指腹用力下压
        # 接触长轴可达 18~28mm，贴着基础阈值的新触点不该草率切掌擦
        if self._device == "touch" and self._touch_id >= 0 and palm.id() != self._touch_id:
            return self._contact_px(palm) >= thresh_px * 1.35

        # 规则 3：单点触控或自身触点（起笔或单指书写中）
        # 必须达到真正肉垫/掌根尺度（1.75x 阈值，~35mm 以上），绝对防止单指用力顿笔误切橡皮
        palm_px = self._contact_px(palm)
        return palm_px >= thresh_px * 1.75

    def _start_palm_erase(self, point: QEventPoint) -> None:
        """进入手掌擦除：像素擦除开一笔，擦除宽度 = 接触直径按短轴限幅（fact 515）。

        「抬起即还原原工具」不用做任何事 —— 工具属性全程没动过，``_palm_erasing``
        一撤，_mode_for_tool 就回到原工具的语义。状态切换本身不进撤销栈；
        擦除笔画与普通像素橡皮同栈，undo 一样能撤。
        """
        self._palm_erasing = True
        self._device = "touch"
        self._pointer_device = "touch"
        self._touch_id = point.id()
        contact = max(self._palm_erase_width_px(point), 2.0)
        pos = point.position()
        # 擦除宽度 = 接触直径按短轴限幅（2026-10-31 fact 515，见 _palm_erase_width_px：
        # 旧实现用长轴 → 细长掌缘短轴方向过擦 (长-短)/2），经覆盖参数在 beginStroke
        # 内就位（2026-10-29 审计 #15：不再「先按 eraserWidth 起笔再覆盖」，起手帧
        # 不会闪小圆点）；bake 半径 = stroke.width × w / 2：宽度取限幅后直径、每点 w
        # 恒 1，半径即其一半。幻影尺寸同宽（beginStroke 设 self._width），自动跟随。
        self._stroke_width_override = contact
        self.beginStroke(pos.x(), pos.y(), 1.0)
        if self._mode != "erase":
            # beginStroke 没进擦除路径（尺寸异常等）：别让旗标悬着
            self._palm_erasing = False
            self._device = None
            self._touch_id = -1

    def _extend_palm(self, x: float, y: float) -> None:
        self.extendStroke([[x, y, 1.0]])
        if self._ghost_visible:
            self._set_ghost(True, x, y)

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
