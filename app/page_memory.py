"""课件续页 —— 按课件文件记住「上次讲到第几页」，下次放映接着讲。

## 它解决的事

一节课讲到第 8 页下课，下节课重新打开同一份课件，放映软件总是从第 1 页起。
这个模块把「哪个课件停在哪一页」记在本机，下次放映同一份课件时由**右下角**的
续页卡片提示「上次停在第 8 页 · 点这里跳过去」，点一下就走 ``GotoSlide``。

## 三条硬约束（功能边界，改之前先读）

1. **只读，不写回课件**。课件身份只经 COM 读 ``Presentation.FullName``（回退
   ``Name``），绝不调 ``Save`` / ``SaveAs`` / ``Export`` 到原路径 —— 用户的原话是
   「只读不改，课件原样，一个字都不动」。
2. **不联网，只存本机**。落盘位置是 ``paths.page_memory_file()``（数据根下的
   一个 JSON），不走任何网络路径。
3. **历史留 N 天**（``presentation.page_memory.keep_days``，默认 21）。过期条目在
   读取时按时间戳筛掉并顺手写回 —— 不另开清理定时器，托盘常驻应用里没有比
   「用到时顺手清」更省事的做法。

## 为什么落 ``data_dir()`` 而不是 ``cache_dir()``

``cache/`` 是「可随时删」的运行期缓存，``slide_thumbs`` 每换一场放映就
``rmtree`` 自己的子目录。21 天的记忆放那儿，迟早被一次「顺手统一清理」连带删掉。
路径写成函数（``paths.page_memory_file``）而不是模块级常量，是为了跟随
``LUMINALIUM_DATA_DIR`` 的覆盖 —— 自检 / 探针跑起来不能碰用户真实数据。

## 数据从哪来（两条流在这里汇合）

* **放映状态**：``PptController.stateChanged`` 每翻一页一条（``PresentationState``
  的 ``slide_index`` / ``slide_total`` / ``active``）。这是**页码**的唯一来源。
* **课件身份**：``PptController.deckReady(path, name)``，只在进入放映边沿由 COM
  线程读一次。``PresentationState`` 里**没有**这个字段，也**不建议**往里加 ——
  那条链是 7 个基本类型位置参数的跨线程信号，加字段要同步改 4 处签名与
  ``tools/`` 下十几处构造点，而身份只需要「进场时读一次」，走独立信号干净得多。

⚠️ 两条流的**到达顺序不固定**：窗口探测（400ms）通常先送出 ``active=True``，
COM 那侧的身份要晚一拍。所以会话态先攒着，``deckReady`` 到了再查记忆、再决定
卡片显不显示 —— 反过来（身份先到）也能对上，``_adopt_deck`` 是幂等的。

## 与 QML 的接口

``Backend`` 读 :meth:`PageMemory.snapshot` 出 ``pageMemory`` 属性（一个 dict），
本模块只发 ``changed`` 让 QML 重读。**不往 config 里写任何键** —— 记忆是运行期
状态，``config.json`` 只存用户设定（smoke 的 iron-off 场景对那份文件做字节级
对比，多写一个键就是假失败）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from . import paths

log = logging.getLogger(__name__)

#: 记忆默认保留天数（``presentation.page_memory.keep_days``）。
KEEP_DAYS_DEFAULT = 21

#: 翻页后多久落一次盘。翻页是「每页一条状态」，逐条写盘等于把磁盘写放大到
#: 翻页节奏上，而且那一拍播放器正在渲染新的一页 —— 攒 1.5 秒写一次足够，
#: 真正的兜底是「退出放映边沿」与 :meth:`PageMemory.flush`。
WRITE_DEBOUNCE_MS = 1500

#: 落盘格式版本。将来改结构时按它迁移；读到不认识的值就整份丢弃重建
#: （记忆是可再生的辅助数据，不值得为它写迁移代码）。
FORMAT_VERSION = 1

#: 自检 / 探针的**落盘隔离**环境变量。
#:
#: 为什么需要它：``tools/smoke.py`` 会拉起**完整应用**（``LuminaliumApplication``
#: → 装配期就构造 :class:`PageMemory` → ``_load()`` 立刻读真实
#: ``data/page_memory.json``，筛掉过期条目时还会写回）。smoke 拿到 ``app`` 时
#: 构造早就完成了，改 ``_file`` 已经晚了 —— 2026-11-08 两次把自检记录写进
#: 仓库根（内容是 ``D:\\课件\\自检课件.pptx``）。
#:
#: 所以给一条**在应用构造之前**就能设的通道：环境变量指向一个目录，
#: :class:`PageMemory` 就用那个目录下的 ``page_memory.json``。
#: ⚠️ 不用 ``LUMINALIUM_DATA_DIR``：那会把整份 config / logs 一起挪走，
#: smoke 要验的正是真实 config 的字节级一致性。
_ISOLATION_ENV = "LUMINALIUM_PAGE_MEMORY_DIR"


def deck_key(path: str, name: str) -> str:
    """课件身份键 —— 稳定、与大小写无关、可以直接当 JSON 的 key。

    Windows 路径不区分大小写，同一个文件可能以 ``D:\\课件\\A.pptx`` 与
    ``d:/课件/a.pptx`` 两种写法出现，所以先归一（反斜杠换正斜杠 + 全小写）。
    再取 sha1 前 16 位当键：路径本身可能很长（中文 + 多层目录），拿它当 key
    既占地方又不好读；原始路径另存在条目里，排查时照旧看得见。

    拿不到路径时退 ``name``（``Presentation.Name``），再拿不到就用空串 ——
    调用方（:meth:`PageMemory._adopt_deck`）遇到空键**不记忆**，宁可不生效也
    不要把所有课件混成一条。
    """
    raw = (path or "").strip().replace("\\", "/").lower()
    if not raw:
        raw = (name or "").strip().lower()
    if not raw:
        return ""
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


class PageMemory(QObject):
    """课件页数记忆的读写与过期管理。

    ``changed`` 是唯一的对外信号：卡片显隐 / 文案有任何变化都发它，QML 侧
    重读 ``Backend.pageMemory``。**不逐字段发信号** —— 一张卡片上就那么几行字，
    整份重发比维护六条信号简单。
    """

    changed = Signal()

    def __init__(
        self,
        config,
        controller=None,
        parent: Optional[QObject] = None,
        persist: bool = True,
        file_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        #: 落盘目标。``persist=False`` 的宿主（``tools/preview.py``）不碰磁盘：
        #: 预览跑在用户真实数据根上，为了一张假卡片写一条假记录不划算。
        #:
        #: ``file_path`` 是给**自检**用的显式覆盖（``tools/smoke.py`` 把它指到
        #: 临时目录）。⚠️ 必须在**构造时**给，不能构造完再改 ``_file``：
        #: ``_load`` 在构造里就跑，它会读（并在筛掉过期条目时**写回**）真实
        #: ``data/page_memory.json`` —— 2026-11-08 真机验证时就因此把一条自检
        #: 记录写进了用户数据根（仓库根冒出 ``page_memory.json``）。
        self._persist = bool(persist)
        if file_path is not None:
            self._file = Path(file_path)
        elif os.environ.get(_ISOLATION_ENV):
            # 自检 / 探针的隔离通道（见 ``_ISOLATION_ENV`` 的说明）
            self._file = Path(os.environ[_ISOLATION_ENV]).expanduser() / "page_memory.json"
        elif self._persist:
            self._file = paths.page_memory_file()
        else:
            self._file = Path(os.devnull)
        #: ``{键: {"path", "name", "page", "total", "at"}}``
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._load()

        # ---- 会话态（一场放映一份，退出即清）----
        self._active = False
        self._key = ""
        self._name = ""
        self._path = ""
        self._page = 0
        self._total = 0
        #: 进场那一刻的页码，以及「本场有没有真的翻过页」。两个一起用：
        #: **只有走开过才更新记忆** —— 否则「打开课件看一眼、一页没翻就退出」
        #: 会把「上次停在第 8 页」改写成第 1 页，那正是这张卡片存在的意义被抹掉
        #: 的方式（2026-11-08 预览里抓到的坑）。翻过之后就一直记（哪怕最后又翻回
        #: 第 1 页 —— 那就是用户真实的落点）。
        self._page_at_entry = 0
        self._moved = False
        #: 本场命中的记忆条目（没命中 / 已过期 / 越界时为 ``None``）。这是**副本**，
        #: 不会随本场翻页而变 —— 卡片显示的永远是「上一场停在哪」。
        self._recorded: Optional[Dict[str, Any]] = None
        #: 用户点过「跳过去」没有 —— 卡片底部那行文案据此切换。
        self._resumed = False
        #: 用户点 × 收起过没有 —— 本场内不再弹。
        self._dismissed = False

        self._dirty = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(WRITE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save)

        if controller is not None:
            self.attach(controller)

    # ---------------------------------------------------------------- 装配

    def attach(self, controller) -> None:
        """接上 ``PptController`` 的两条流（duck-typing，自检可换假实现）。

        ``stateChanged`` 一定有；``deckReady`` 是 2026-11-08 新加的，老宿主
        （或只造了半个控制器的探针）没有它 —— 缺了就退化成「记不住课件身份」，
        不报错。
        """
        states = getattr(controller, "stateChanged", None)
        if states is not None:
            states.connect(self.observe)
        deck = getattr(controller, "deckReady", None)
        if deck is not None:
            deck.connect(self._adopt_deck)
        else:  # pragma: no cover - 只有自检用的假控制器会走到
            log.debug("控制器没有 deckReady 信号，页数记忆将不区分课件")

    # ------------------------------------------------------------ 状态入口

    def observe(self, state) -> None:
        """每一条放映状态快照都经过这里（``bridge.apply_state`` 同款时机）。

        只做「更新会话态 + 决定要不要落盘」，不做 IO —— 这个槽每翻一页跑一次。
        """
        active = bool(getattr(state, "active", False))
        page = int(getattr(state, "slide_index", 0) or 0)
        total = int(getattr(state, "slide_total", 0) or 0)

        if not active:
            if self._active:
                self._active = False
                # 退出边沿：这一页就是「上次停在哪」，立刻落盘，不等防抖。
                # 判据是 ``_moved``（本场真翻过页）而不是「页码 != 进场页」：
                # 翻了一圈又回到第 1 页也是真实落点，同样要记。
                if self._moved and self._page > 0:
                    self._commit(force=True)
                self._reset_session()
                self.changed.emit()
            return

        became_active = not self._active
        self._active = True
        if became_active:
            # 新一场：上一场的命中 / 收起 / 已跳转状态一律作废。课件身份也先
            # 清空 —— 等 deckReady 重新给，避免拿上一份课件的键去记这一场。
            self._reset_session()
        if page > 0:
            self._page = page
        if total > 0:
            self._total = total
        if became_active:
            self._page_at_entry = self._page
            # 卡片这时还出不来（没有课件身份），但页码区已经要能读到当前值
            self.changed.emit()
        elif page > 0 and self._key:
            if page != self._page_at_entry:
                self._moved = True
            if self._moved:
                self._remember_current()
            # ⚠️ 翻页也要喊一声（2026-11-09）：``visible`` 现在含
            # ``alreadyThere``（当前页 == 记忆页就不提示），而当前页每翻一次都变
            # —— 不发 ``changed`` 的话 QML 的 ``Backend.pageMemory`` 绑定永远停在
            # 进场那一拍，卡片该消失时不消失（真机实测过）。
            self.changed.emit()

    def _reset_session(self) -> None:
        self._key = ""
        self._name = ""
        self._path = ""
        self._page_at_entry = 0
        self._moved = False
        self._recorded = None
        self._resumed = False
        self._dismissed = False

    # ------------------------------------------------------------ 课件身份

    def _adopt_deck(self, path: str, name: str) -> None:
        """COM 线程送来课件身份（放映进场时读一次）。幂等。"""
        path = str(path or "").strip()
        name = str(name or "").strip()
        key = deck_key(path, name)
        if not key:
            # 读不到身份（WPS / 永中 / COM 连不上）：不记忆，也不弹卡片。
            # 静默降级 —— 日志留一条，真机排查时能看出「为什么没生效」。
            log.debug("课件续页：拿不到课件身份，本场不记忆")
            return
        if key == self._key:
            return
        previous_key = self._key
        if previous_key and self._page > 0:
            # 同一场里换了课件：先把上一份的页码结掉，别把它记到新的键上
            self._commit(force=True)
        self._key = key
        self._name = name or Path(path).name if (name or path) else ""
        self._path = path
        self._recorded = self._lookup(key)
        self._resumed = False
        self._dismissed = False
        # ⚠️ 这里**不**调 ``_remember_current()``（2026-11-08 预览里抓到的真 bug）：
        # 那一手会把「刚进场时的当前页」写进 ``_entries[key]`` —— 而 ``_recorded``
        # 指向的正是同一个 dict，于是卡片上的「上次停在第 N 页」立刻变成**这一场
        # 的当前页**（刚打开时就是第 1 页），记录时间也刷成「刚刚」。
        # 记忆只在两个时机更新：用户真的翻页（``observe`` 里 page 变化）与退出
        # 放映（``observe`` 的 active=False 分支强制落盘）。
        if self._recorded is not None:
            log.info(
                "课件续页：命中记忆 %s 第 %s 页（记录于 %s）",
                self._name or key,
                self._recorded.get("page"),
                self._format_time(self._recorded.get("at")),
            )
        self.changed.emit()

    # ------------------------------------------------------------ 记忆读写

    def _remember_current(self) -> None:
        """把当前页写进内存表并排一次防抖落盘（不立刻写）。"""
        if not self._key or self._page <= 0:
            return
        entry = self._entries.get(self._key) or {}
        entry.update({
            "path": self._path,
            "name": self._name,
            "page": int(self._page),
            "total": int(self._total),
            "at": time.time(),
        })
        self._entries[self._key] = entry
        self._dirty = True
        self._save_timer.start()

    def _commit(self, force: bool = False) -> None:
        """把当前页立刻记进内存表；``force`` 时顺带立刻落盘。"""
        if not self._key or self._page <= 0:
            return
        self._remember_current()
        if force:
            self._save()

    def _lookup(self, key: str) -> Optional[Dict[str, Any]]:
        """查一条记忆并做**有效性判定**；无效返回 ``None``。

        三条判据：

        * 过期（超过 ``keep_days``）—— 过期条目顺手从表里删掉；
        * 页码越界（``page > total``，课件被删过页）—— 不提示，否则点了会跳到
          不存在的页；
        * 总页数读不到（``total == 0``，COM 还没回）时**放行** —— 页码本身是
          有效的，等下一拍总页数到了也不会再变。
        """
        entry = self._entries.get(key)
        if not entry:
            return None
        page = int(entry.get("page") or 0)
        if page <= 0:
            return None
        keep_days = self._keep_days()
        at = float(entry.get("at") or 0)
        if keep_days > 0 and at > 0 and (time.time() - at) > keep_days * 86400:
            log.info("课件续页：记忆已过期（%s 天），丢弃", keep_days)
            self._entries.pop(key, None)
            self._dirty = True
            self._save_timer.start()
            return None
        total = int(entry.get("total") or 0)
        live_total = int(self._total or 0)
        if live_total > 0 and page > live_total:
            log.info("课件续页：记忆页码 %s 超出当前总页数 %s，不提示", page, live_total)
            return None
        del total  # 只在上面那条越界判据里用到（记忆里的 total 作参考，不参与比较）
        # ⚠️ 返回**副本**：``_entries[key]`` 会在本场翻页时被 ``_remember_current``
        # 就地更新（那是「这一场停在哪」），而卡片要显示的是「**上一场**停在哪」。
        # 不复制的话两个语义会挤在同一个 dict 上，卡片上的页码会跟着当前页乱跳
        # （2026-11-08 预览里抓到的第一个 bug）。
        return dict(entry)

    def _keep_days(self) -> int:
        try:
            value = int(self._config.get("presentation.page_memory.keep_days",
                                         KEEP_DAYS_DEFAULT))
        except (TypeError, ValueError):
            return KEEP_DAYS_DEFAULT
        return max(0, value)

    def _enabled(self) -> bool:
        """总开关（``presentation.page_memory.enabled``，默认开）。

        每次现读配置、不另存一份 —— 与 ``application._ink_engine`` 同一个理由：
        配置只有一处来源，设置页改完下一次状态快照就按新值走。
        """
        value = self._config.get("presentation.page_memory.enabled", True)
        return value is not False

    # ------------------------------------------------------------ 对外查询

    def snapshot(self) -> Dict[str, Any]:
        """QML 读的那份数据（``Backend.pageMemory``）。"""
        recorded = self._recorded
        page = int((recorded or {}).get("page") or 0)
        total = int((recorded or {}).get("total") or 0)
        at = float((recorded or {}).get("at") or 0)
        # 「已经在那儿了」：这一场的当前页 == 记忆里那一页。
        #
        # 2026-11-09 用户指令：「若当前页数已经是所记忆的上一次放映页数，那么就
        # 不显示卡片」。场景：放映软件记住了上次的页（PowerPoint 自己就会从
        # 停的那页起），或者用户手动翻到了那一页 —— 这时再提示「点这里跳到第
        # N 页」是**没有意义的一下**，卡片只剩遮挡。
        #
        # ⚠️ 只在 ``self._page > 0`` 时判：COM 还没读到页码时 ``_page`` 是 0，
        # 不能因为「0 != 8」就当成「不在那一页」而放行 —— 反过来也不能因为
        # 「0 == 0」就误判成已经在（page > 0 已经挡掉了记忆页码为 0 的情况）。
        already_there = bool(page > 0 and int(self._page) == page)
        visible = bool(
            self._enabled()
            and self._active
            and recorded is not None
            and page > 0
            and not self._dismissed
            and not already_there
        )
        return {
            "visible": visible,
            # 记忆里的页码 / 总页数（卡片正文用）
            "page": page,
            "total": total,
            # 当前这场放映的实时页码 / 总页数（卡片上那行「正在放映 · 共 N 页」）
            "current": int(self._page),
            "currentTotal": int(self._total),
            # 当前页就是记忆那一页 → 卡片不该出现（诊断 / 自检用）
            "alreadyThere": already_there,
            # 课件文件名（卡片标题）
            "name": str((recorded or {}).get("name") or self._name or ""),
            # 距记录时刻过了多少秒（QML 侧翻成「刚刚 / N 分钟前」）
            "ageSeconds": max(0.0, time.time() - at) if at > 0 else 0.0,
            # 用户点过「跳过去」没有 —— 底部那行文案据此切换
            "resumed": bool(self._resumed),
            # 本场有没有认出课件（设置页 / 诊断用）
            "identified": bool(self._key),
        }

    # ------------------------------------------------------------ 卡片交互

    def mark_resumed(self) -> None:
        """用户点了「点这里跳过去」。卡片不收起，只把底部文案切掉。"""
        if self._resumed:
            return
        self._resumed = True
        self.changed.emit()

    def dismiss(self) -> None:
        """用户点了 × / 「知道了」—— 本场内不再弹。"""
        if self._dismissed:
            return
        self._dismissed = True
        self.changed.emit()

    def forget_current(self) -> None:
        """忘掉当前课件的记忆（设置页「清除记录」用）。"""
        if not self._key:
            return
        self._entries.pop(self._key, None)
        self._recorded = None
        self._dirty = True
        self._save()
        self.changed.emit()

    def clear(self) -> None:
        """清空全部记忆（设置页「清除全部记录」用）。"""
        if not self._entries:
            return
        self._entries.clear()
        self._recorded = None
        self._dirty = True
        self._save()
        self.changed.emit()

    # ------------------------------------------------------------ 落盘

    def _load(self) -> None:
        if not self._persist:
            return
        try:
            with open(self._file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            log.warning("课件续页：记忆文件读不出来，按空表处理（%s）", self._file,
                        exc_info=True)
            return
        if not isinstance(data, dict) or int(data.get("version") or 0) != FORMAT_VERSION:
            log.info("课件续页：记忆文件版本不认识，丢弃重建")
            return
        entries = data.get("entries")
        if not isinstance(entries, dict):
            return
        keep_days = self._keep_days()
        now = time.time()
        kept: Dict[str, Dict[str, Any]] = {}
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            try:
                at = float(entry.get("at") or 0)
                page = int(entry.get("page") or 0)
            except (TypeError, ValueError):
                continue
            if page <= 0:
                continue
            if keep_days > 0 and at > 0 and (now - at) > keep_days * 86400:
                continue
            kept[str(key)] = {
                "path": str(entry.get("path") or ""),
                "name": str(entry.get("name") or ""),
                "page": page,
                "total": int(entry.get("total") or 0),
                "at": at,
            }
        self._entries = kept
        if len(kept) != len(entries):
            log.info("课件续页：载入 %d 条记忆（另有 %d 条已过期）",
                     len(kept), len(entries) - len(kept))
            self._dirty = True
            self._save()
        else:
            log.debug("课件续页：载入 %d 条记忆", len(kept))

    def _save(self) -> None:
        """整份重写（先写临时文件再 ``os.replace``，中途崩了不会留下半个 JSON）。"""
        if not self._persist or not self._dirty:
            return
        self._save_timer.stop()
        payload = {
            "version": FORMAT_VERSION,
            "entries": self._entries,
        }
        temp = self._file.with_suffix(".json.tmp")
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            # ``newline="\n"``：与 ``config.Config.save`` 同一条 —— CRLF 会让
            # 「文件没变」的字节级断言假失败（构建与自检都按文本比对过）。
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp, self._file)
            self._dirty = False
        except OSError:
            log.warning("课件续页：记忆写盘失败（%s）", self._file, exc_info=True)
            try:
                if temp.exists():
                    temp.unlink()
            except OSError:  # pragma: no cover - 清理失败不值得再报
                pass

    def flush(self) -> None:
        """退出应用 / 退出放映时把还没落盘的尾巴写掉。"""
        if self._active:
            if self._moved and self._page > 0:
                self._commit(force=True)
            elif self._dirty:
                self._save()
        elif self._dirty:
            self._save()

    @staticmethod
    def _format_time(value) -> str:
        try:
            at = float(value or 0)
        except (TypeError, ValueError):
            return "?"
        if at <= 0:
            return "?"
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(at))
