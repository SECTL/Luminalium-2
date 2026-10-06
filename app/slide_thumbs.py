"""放映页缩略图缓存 —— 页码快速跳转面板上那 41 张「幻灯片画面」。

## 出处：Luminalium 1 的那条链路

L1 的 ``#page-selector`` 里每一页是一张缩略图（``.page-item img``），由
``core/ppt_monitor.py::export_slide_thumbnail`` 产出：

```python
pres.Slides(index).Export(path, "PNG", 320, 180)
```

调用时机也照抄 L1 的两条：

* **点开面板立刻要当前页 ±5**（``requestThumbnailsForRange``）—— 用户眼睛正盯着
  的这几张必须最快到位；
* **其余的在后台以 500ms 一格的节拍慢慢补**（``startBackgroundThumbnailCaching``）
  —— 不能一口气导 41 页，那会把 COM 线程占住，页码跟着手势走这件事就废了。

## L2 这边多加的一段：把圆角烤进 PNG

L1 是 CSS ``border-radius: 8px`` + ``overflow: hidden``，浏览器免费解决。
QML 里要让一张图带上圆角得给**每一张**挂 ``layer.effect: OpacityMask`` ——
41 张图就是 41 个离屏 FBO，代价太大。所以这里在导出之后顺手用 Pillow 把圆角
画进 alpha 通道：**QML 侧那层蒙版就省掉了**，一张圆角图的效果和一个
``Image`` 完全一样。

⚠️ 烤进去的半径是**按导出的 320 宽折算过的**（``_corner_radius``）：
显示尺寸是 236 设计宽，直接烤 8 会比设计意图小一圈。改
``Lumi.dockJumpItemRadius`` / ``dockJumpWidth`` 时这两个常量要跟着改。

## 生命周期

跟着「放映开始 / 结束」走（``set_show``）：

* 开始 → 生成一个**代次号**（``_generation``），把缓存目录整个清掉，URL 表
  复位成全空；
* 结束 → 停掉节拍器、清空队列与 URL 表，**文件留着**（下一场同一份演示多半
  还要用，而目录是按代次号命名的，不会串味）。

代次号还兼任**过期保护**：导出是异步的，上一场的导出结果可能在下一场才回来，
带代次号的文件名可以让「迟到的那一张」被干净地丢掉。
"""

from __future__ import annotations

import logging
import shutil
from collections import deque
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

from . import paths

log = logging.getLogger(__name__)

#: 导出尺寸 —— L1 的 ``Export(path, "PNG", 320, 180)`` 原值（16:9）。
EXPORT_WIDTH = 320
EXPORT_HEIGHT = 180

#: 后台补图的节拍（毫秒）。L1 的 ``_background_thumbnail_timer`` 就是 500。
TICK_MS = 500

#: 点开面板时**立刻**投出去的张数上限。
#:
#: L1 是一次把 ±5 全投出去（11 条 COM 命令），代价是那 11 条排队期间页码不再
#: 更新（L1 的 COM 就在主线程的 QTimer 里，躲不掉）。L2 的 COM 有自己的线程，
#: 但「页码跟着手势走」这条同样值钱，所以先投 3 张把观感撑住，剩下的交给 500ms
#: 的节拍 —— 用户看到的差别是「第 4 张晚半秒」，而页码全程不卡。
BURST = 3

#: 同一页最多试几次。导出失败会把页码放回「可以再要」的状态（不然它会永远空着），
#: 但真导不出来时（比如软件不支持 ``Slides(i).Export``）不该每滚一下就重投一轮。
MAX_ATTEMPTS = 3

#: 设计单位下的卡片尺寸与圆角（对应 ``Lumi.dockJumpWidth`` - 2×``dockJumpPadding``
#: 与 ``Lumi.dockJumpItemRadius``）。
DESIGN_CARD_WIDTH = 236
DESIGN_CORNER_RADIUS = 8


def _corner_radius() -> int:
    """按导出宽度折算出的烤角半径。"""
    return max(1, round(DESIGN_CORNER_RADIUS * EXPORT_WIDTH / DESIGN_CARD_WIDTH))


def round_corners(source: Path, target: Path, radius: Optional[int] = None) -> bool:
    """把 ``source`` 的四个角画圆后写到 ``target``（返回值 = 成功与否）。

    失败**不算错误**：一张方角缩略图远比一个空卡片好，所以拿不到 Pillow 就
    直接把原图搬过去。
    """
    radius = _corner_radius() if radius is None else radius
    try:
        from PIL import Image, ImageDraw

        with Image.open(source) as raw:
            image = raw.convert("RGBA")
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, image.size[0] - 1, image.size[1] - 1),
                radius=radius,
                fill=255,
            )
            image.putalpha(mask)
            image.save(target, "PNG", optimize=True)
        return True
    except Exception:
        log.debug("缩略图烤圆角失败，退回方角原图", exc_info=True)
        try:
            shutil.copyfile(source, target)
            return True
        except Exception:
            log.debug("缩略图搬运失败", exc_info=True)
            return False


class SlideThumbCache(QObject):
    """放映页缩略图的请求队列 + 磁盘缓存。

    ``urls`` 是 QML 直接读的那份表（``Backend.thumbUrls``）：**索引 = 页码 - 1**，
    空串 = 还没就绪。每次有一条落地就发 ``urlsChanged``。
    """

    urlsChanged = Signal()

    def __init__(self, controller, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._urls: List[str] = []
        self._requested: set[int] = set()
        self._attempts: dict[int, int] = {}
        self._pending: deque[int] = deque()
        # ⚠️ 走 ``paths.slide_thumb_dir()``（每次构造时解析）而不是模块级常量：
        # 它要跟随 ``LUMINALIUM_DATA_DIR`` 的覆盖 —— 这个类是应用里唯一会**主动
        # 整目录删文件**的地方，自检 / 探针跑起来绝不能去动用户真实数据目录。
        self._dir = paths.slide_thumb_dir()
        self._generation = 0
        self._live = False

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._pump)

        ready = getattr(controller, "thumbnailReady", None)
        if ready is not None:
            ready.connect(self._on_ready)

    # ------------------------------------------------------------------ 查询

    @property
    def urls(self) -> List[str]:
        """当前这场放映的缩略图表（``file:///…``；空串 = 还没好）。"""
        return list(self._urls)

    @property
    def directory(self) -> Path:
        return self._dir

    # ------------------------------------------------------------ 放映生命周期

    def set_show(self, active: bool, total: int) -> None:
        """放映开始 / 结束 / 页数变化时由 bridge 调（每个状态快照都会经过这里）。"""
        total = max(0, int(total or 0))
        if not active or total <= 0:
            if self._live:
                log.debug("缩略图缓存：放映结束，清空队列（%d 张）", len(self._urls))
            self._live = False
            self._stop()
            self._pending.clear()
            self._requested.clear()
            self._attempts.clear()
            if self._urls:
                self._urls = []
                self.urlsChanged.emit()
            return

        if not self._live:
            # 新一场：换代次号 + 清目录（上一场的文件按旧代次号命名，不会被读到）
            self._live = True
            self._generation += 1
            self._purge()
            self._requested.clear()
            self._attempts.clear()
            self._pending.clear()
            self._urls = [""] * total
            self.urlsChanged.emit()
            log.debug("缩略图缓存：新一场放映（%d 页，代次 %d）", total, self._generation)
            return

        if total != len(self._urls):
            # 同一场里页数变了（换了一份演示 / 刚读到总页数）—— 保住已有的，
            # 只把表伸缩到新长度
            if total > len(self._urls):
                self._urls.extend([""] * (total - len(self._urls)))
            else:
                del self._urls[total:]
            self.urlsChanged.emit()

    def clear(self) -> None:
        """删掉缓存目录并复位（退出 / 诊断用）。"""
        self._stop()
        self._pending.clear()
        self._requested.clear()
        self._attempts.clear()
        self._live = False
        self._purge()
        if self._urls:
            self._urls = []
            self.urlsChanged.emit()

    # ---------------------------------------------------------------- 请求

    def request(self, start: int, end: int, burst: int = BURST) -> None:
        """要 ``[start, end]`` 这一段（1-based，闭区间）的缩略图。

        已经在队列里 / 已经拿到的不会重复要。``burst`` 张**立刻**投出去
        （用户正盯着的那些），其余的排在最前面，按 500ms 一格的节拍补。
        """
        if not self._live:
            return
        total = len(self._urls)
        if total <= 0:
            return
        lo = max(1, int(min(start, end)))
        hi = min(total, int(max(start, end)))
        if hi < lo:
            return

        fresh = [p for p in range(lo, hi + 1)
                 if p not in self._requested
                 and self._attempts.get(p, 0) < MAX_ATTEMPTS]
        if not fresh:
            return
        for page in fresh:
            self._requested.add(page)
            self._attempts[page] = self._attempts.get(page, 0) + 1
        # 插到队首（并按页码顺序），让「刚点开面板要的那几页」排在后台补图之前
        self._pending.extendleft(reversed(fresh))

        urgent = min(max(0, int(burst)), len(fresh))
        for _ in range(urgent):
            self._dispatch()
        if self._pending:
            self._timer.start()

    # ---------------------------------------------------------------- 内部

    def _pump(self) -> None:
        """节拍器：一格投一张；队列空了就停表。"""
        if not self._live:
            self._stop()
            return
        if not self._dispatch():
            self._stop()

    def _dispatch(self) -> bool:
        while self._pending:
            page = self._pending.popleft()
            if page < 1 or page > len(self._urls) or self._urls[page - 1]:
                continue  # 越界（页数缩了）或已经有了 —— 丢掉
            raw = self._dir / f"{self._generation}-{page}-raw.png"
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                log.debug("缩略图目录建不出来：%s", self._dir, exc_info=True)
                return False
            if self._controller.export_slide_thumbnail(
                page, str(raw), EXPORT_WIDTH, EXPORT_HEIGHT
            ):
                return True
            # 投都投不出去（控制器没接上 / 已停）：把它放开 —— 不然这一页会被
            # 永远记成「已经要过了」，再也没人去补
            self._requested.discard(page)
        return False

    def _on_ready(self, index: int, path: str) -> None:
        """一条导出**结束**（COM 线程发过来，在主线程执行）。

        ⚠️ ``path`` 为空串 = 这次没导出来（见 ``ppt_controller._cmd_export``）。
        这种情况**必须**把页码从「已请求」里放出来：不放的话它会被永远记成
        「已经要过了」，那一张就再也没人去补了（症状是面板上固定空着一格）。
        重试上限 ``MAX_ATTEMPTS`` —— 真导不出来（比如 WPS 不支持
        ``Slides(i).Export``）时不该每滚一下就重投一轮。
        """
        index = int(index)
        raw = Path(path) if path else None
        if not self._live or index < 1 or index > len(self._urls):
            if raw is not None:
                self._unlink(raw)
            return
        if raw is None:
            self._requested.discard(index)
            log.debug("第 %d 页缩略图导出失败（已尝试 %d 次）",
                      index, self._attempts.get(index, 0))
            return
        # 代次号不匹配 = 上一场迟到的结果，丢掉（文件名里带着它自己的代次号）
        if not raw.name.startswith(f"{self._generation}-"):
            self._unlink(raw)
            return

        final = self._dir / f"{self._generation}-{index}.png"
        if not round_corners(raw, final):
            self._unlink(raw)
            self._requested.discard(index)
            return
        self._unlink(raw)

        url = QUrl.fromLocalFile(str(final)).toString()
        if self._urls[index - 1] != url:
            self._urls[index - 1] = url
            self.urlsChanged.emit()
        if not self._pending:
            self._stop()

    def _stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def _purge(self) -> None:
        """清空缓存目录（只碰自己那个子目录）。"""
        try:
            if self._dir.exists():
                shutil.rmtree(self._dir, ignore_errors=True)
        except Exception:
            log.debug("清理缩略图目录失败：%s", self._dir, exc_info=True)

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            log.debug("删临时缩略图失败：%s", path, exc_info=True)
