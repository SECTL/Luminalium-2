"""课件续页（app/page_memory.py）的离线自测 —— 只验逻辑，不碰 COM / 不碰用户数据。

用法（仓库根目录）::

    .venv\\Scripts\\python.exe -X utf8 tools/page_memory_selftest.py

为什么单独一个脚本而不是塞进 ``smoke.py``：本模块的判据（过期 / 越界 /
「一页没翻就不覆盖」）全是**时间与页码的组合**，用真放映去凑这些场景既慢又
不稳（要真开 PowerPoint、真等 21 天）。这里直接造状态快照，几毫秒跑完。

落盘一律写临时目录（``tempfile``），**绝不碰** ``data/page_memory.json``。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QCoreApplication  # noqa: E402

from app.page_memory import (  # noqa: E402
    FORMAT_VERSION,
    KEEP_DAYS_DEFAULT,
    PageMemory,
    deck_key,
)
from app.ppt_controller import PresentationState  # noqa: E402

FAILURES = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAILURES
    mark = "OK  " if ok else "FAIL"
    print(f"[{mark}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES += 1


class FakeConfig:
    """只认 ``presentation.page_memory.*`` 三个键的假配置。"""

    def __init__(self, enabled: bool = True, keep_days: int = KEEP_DAYS_DEFAULT) -> None:
        self.enabled = enabled
        self.keep_days = keep_days

    def get(self, path: str, default=None):
        if path == "presentation.page_memory.enabled":
            return self.enabled
        if path == "presentation.page_memory.keep_days":
            return self.keep_days
        return default


def state(active: bool, page: int = 0, total: int = 0) -> PresentationState:
    return PresentationState(active=active, slide_index=page, slide_total=total)


def new_memory(tmp: Path, config=None, name: str = "memory.json") -> PageMemory:
    """造一个落在临时目录里的 PageMemory（并**真的从那里载入**已有记录）。

    ⚠️ 必须用构造参数 ``file_path`` 指定临时文件，**不能**构造完再改 ``_file``：
    ``_load`` 在构造里就跑，默认构造会读**用户真实**的
    ``data/page_memory.json``，而它在筛掉过期条目时还会顺手 ``_save()`` ——
    那一下就把用户的真实文件重写了（2026-11-08 真机验证时踩到过，
    仓库根冒出过一条自检记录）。
    """
    return PageMemory(config or FakeConfig(), file_path=tmp / name)


def main() -> int:
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    del app

    tmp = Path(tempfile.mkdtemp(prefix="lumi_page_memory_"))
    path_a = r"D:\课件\第一章.pptx"
    path_b = r"D:\课件\第二章.pptx"

    # ---------------------------------------------------------------- 键归一
    check("路径键不区分大小写与斜杠方向",
          deck_key(r"D:\课件\A.PPTX", "") == deck_key("d:/课件/a.pptx", ""))
    check("路径缺失时退文件名（大小写不敏感）",
          deck_key("", "测试课件.pptx") == deck_key("", "测试课件.PPTX"))
    check("有路径时以路径为准（同名不同目录不撞键）",
          deck_key(r"D:\A\课件.pptx", "课件.pptx") != deck_key(r"D:\B\课件.pptx", "课件.pptx"))
    check("两样都缺 → 空键（调用方据此不记忆）", deck_key("", "") == "")

    # ---------------------------------------------------------------- 新场 + 翻页
    memory = new_memory(tmp)
    memory.observe(state(True, 1, 10))
    memory._adopt_deck(path_a, "第一章.pptx")
    snap = memory.snapshot()
    check("首次进场没有记录 → 卡片不出现", snap["visible"] is False)
    check("首次进场已认出课件", snap["identified"] is True)

    memory.observe(state(True, 5, 10))
    memory.observe(state(False))
    entry = memory._entries.get(deck_key(path_a, ""))
    check("翻到第 5 页后退出 → 记住第 5 页", entry is not None and entry["page"] == 5,
          f"entry={entry}")
    check("退出后落盘", (tmp / "memory.json").exists())

    # ---------------------------------------------------------------- 命中
    memory2 = new_memory(tmp)
    memory2.observe(state(True, 1, 10))
    memory2._adopt_deck(path_a, "第一章.pptx")
    snap = memory2.snapshot()
    check("同一课件再放映 → 卡片出现", snap["visible"] is True)
    check("卡片显示上次的第 5 页", snap["page"] == 5, f"page={snap['page']}")
    check("卡片显示文件名", snap["name"] == "第一章.pptx", f"name={snap['name']!r}")

    # 翻页后卡片上的页码**不能**跟着当前页走（2026-11-08 预览抓到的 bug）
    memory2.observe(state(True, 6, 10))
    check("翻页后卡片仍显示上次的 5（不是当前页 6）",
          memory2.snapshot()["page"] == 5, f"page={memory2.snapshot()['page']}")

    # ---------------------------------------------------------------- 一页没翻就退出
    # 第一步：**真的翻页**到第 5 页并退出，建起「上次停在第 5 页」这条记忆。
    # ⚠️ 早先这里直接 ``observe(True, 5, 10)`` 然后退出 —— 那条断言是**假通过**：
    # ``_moved`` 还是 False，按设计根本不会写盘，断言之所以绿是因为内存表里
    # 已经躺着上一个测试块留下的「第 5 页」。C++ 版自检（每块重建临时文件）
    # 2026-11-09 把这条抓了出来，这里一并修正。
    memory3 = new_memory(tmp)
    memory3.observe(state(True, 1, 10))
    memory3._adopt_deck(path_a, "第一章.pptx")
    memory3.observe(state(True, 5, 10))
    memory3.observe(state(False))
    entry = memory3._entries.get(deck_key(path_a, ""))
    check("翻页后退出 → 记住第 5 页（一页没翻那组的基线）",
          entry is not None and entry["page"] == 5, f"entry={entry}")

    # 第二步：同一课件再放映，**一页没翻**就退出 → 不该覆盖「第 5 页」。
    memory3.observe(state(True, 5, 10))
    memory3._adopt_deck(path_a, "第一章.pptx")
    memory3.observe(state(False))
    entry = memory3._entries.get(deck_key(path_a, ""))
    check("进场后一页没翻就退出 → 不覆盖旧记录",
          entry is not None and entry["page"] == 5, f"entry={entry}")

    # 翻一圈又回到第 1 页：那是真实落点，要记
    memory3.observe(state(True, 5, 10))
    memory3._adopt_deck(path_a, "第一章.pptx")
    memory3.observe(state(True, 1, 10))
    memory3.observe(state(False))
    entry = memory3._entries.get(deck_key(path_a, ""))
    check("翻回第 1 页也记（真实落点）", entry is not None and entry["page"] == 1,
          f"entry={entry}")

    # ---------------------------------------------------------------- 越界
    memory4 = new_memory(tmp)
    key_a = deck_key(path_a, "")
    memory4._entries[key_a] = {"path": path_a, "name": "第一章.pptx",
                               "page": 40, "total": 40, "at": time.time()}
    memory4._save()
    memory4.observe(state(True, 1, 10))
    memory4._adopt_deck(path_a, "第一章.pptx")
    check("记忆页码超出当前总页数 → 不提示",
          memory4.snapshot()["visible"] is False)

    # ---------------------------------------------------------------- 过期
    memory5 = new_memory(tmp, FakeConfig(keep_days=21))
    memory5._entries[key_a] = {"path": path_a, "name": "第一章.pptx", "page": 3,
                               "total": 10, "at": time.time() - 22 * 86400}
    memory5._save()
    memory5.observe(state(True, 1, 10))
    memory5._adopt_deck(path_a, "第一章.pptx")
    check("超过 21 天 → 不提示", memory5.snapshot()["visible"] is False)
    check("过期条目在读取时被清掉", key_a not in memory5._entries)

    memory6 = new_memory(tmp, FakeConfig(keep_days=0))
    memory6._entries[key_a] = {"path": path_a, "name": "第一章.pptx", "page": 3,
                               "total": 10, "at": time.time() - 365 * 86400}
    memory6._save()
    memory6.observe(state(True, 1, 10))
    memory6._adopt_deck(path_a, "第一章.pptx")
    check("keep_days=0 → 永不过期", memory6.snapshot()["visible"] is True)

    # ---------------------------------------------------------------- 总开关
    memory7 = new_memory(tmp, FakeConfig(enabled=False))
    memory7._entries[key_a] = {"path": path_a, "name": "第一章.pptx", "page": 3,
                               "total": 10, "at": time.time()}
    memory7._save()
    memory7.observe(state(True, 1, 10))
    memory7._adopt_deck(path_a, "第一章.pptx")
    check("总开关关掉 → 卡片不出现", memory7.snapshot()["visible"] is False)

    # ---------------------------------------------------------------- 收起 / 已跳转
    memory8 = new_memory(tmp)
    memory8._entries[key_a] = {"path": path_a, "name": "第一章.pptx", "page": 7,
                               "total": 10, "at": time.time()}
    memory8._save()
    memory8.observe(state(True, 1, 10))
    memory8._adopt_deck(path_a, "第一章.pptx")
    check("命中 → 可见", memory8.snapshot()["visible"] is True)

    memory8.mark_resumed()
    snap = memory8.snapshot()
    check("点过跳转 → resumed=True 且卡片仍在", snap["resumed"] is True and snap["visible"])
    memory8.dismiss()
    check("点 × 收起 → 本场不再出现", memory8.snapshot()["visible"] is False)
    memory8.observe(state(False))
    memory8.observe(state(True, 1, 10))
    memory8._adopt_deck(path_a, "第一章.pptx")
    check("下一场重新出现（收起只管本场）", memory8.snapshot()["visible"] is True)

    # ---------------------------------------------------------------- 已经在那一页了
    # 2026-11-09 用户指令：「若当前页数已经是所记忆的上一次放映页数，那么就不
    # 显示卡片」。场景：放映软件自己记住了上次的页（PowerPoint 就会从停的那页
    # 起），或者用户手动翻到了那一页 —— 这时再提示「点这里跳到第 N 页」是
    # 没有意义的一下，卡片只剩遮挡。
    memory11 = new_memory(tmp)
    memory11._entries[key_a] = {"path": path_a, "name": "第一章.pptx", "page": 7,
                                "total": 10, "at": time.time()}
    memory11._save()
    memory11.observe(state(True, 7, 10))       # 进场就在第 7 页
    memory11._adopt_deck(path_a, "第一章.pptx")
    snap = memory11.snapshot()
    check("进场页 == 记忆页 → 卡片不出现",
          snap["visible"] is False and snap["alreadyThere"] is True,
          f"visible={snap['visible']} alreadyThere={snap['alreadyThere']}")
    memory11.observe(state(True, 6, 10))       # 翻走
    snap = memory11.snapshot()
    check("翻走之后卡片重新出现",
          snap["visible"] is True and snap["alreadyThere"] is False,
          f"visible={snap['visible']} alreadyThere={snap['alreadyThere']}")
    memory11.observe(state(True, 7, 10))       # 又翻回来
    snap = memory11.snapshot()
    check("再翻回记忆页 → 卡片再次收起",
          snap["visible"] is False and snap["alreadyThere"] is True,
          f"visible={snap['visible']} alreadyThere={snap['alreadyThere']}")
    # COM 读空（current=0）时 ``_page`` **保留上一拍的值**（`observe` 里
    # ``if page > 0`` 的保护）—— 页码偶发读空是常态，不能据此判定「换页了」，
    # 所以 alreadyThere 跟着上一拍走，仍然为真。这条是**行为记录**，不是缺陷。
    memory11.observe(state(True, 0, 10))
    snap = memory11.snapshot()
    check("COM 读空时沿用上一拍的页（alreadyThere 仍为真）",
          snap["alreadyThere"] is True and snap["current"] == 7,
          f"alreadyThere={snap['alreadyThere']} current={snap['current']}")

    # ---------------------------------------------------------------- 两份课件各记各的
    memory9 = new_memory(tmp)
    memory9.observe(state(True, 1, 10))
    memory9._adopt_deck(path_a, "第一章.pptx")
    memory9.observe(state(True, 4, 10))
    memory9.observe(state(False))
    memory9.observe(state(True, 1, 20))
    memory9._adopt_deck(path_b, "第二章.pptx")
    memory9.observe(state(True, 12, 20))
    memory9.observe(state(False))
    first = memory9._entries.get(deck_key(path_a, ""))
    second = memory9._entries.get(deck_key(path_b, ""))
    check("两份课件各记各的",
          first is not None and first["page"] == 4
          and second is not None and second["page"] == 12,
          f"a={first and first['page']} b={second and second['page']}")

    # ---------------------------------------------------------------- 落盘格式 / 损坏容忍
    raw = json.loads((tmp / "memory.json").read_text(encoding="utf-8"))
    check("落盘带版本号", raw.get("version") == FORMAT_VERSION, f"version={raw.get('version')}")
    (tmp / "memory.json").write_text("{ 这不是 JSON", encoding="utf-8")
    broken = new_memory(tmp)
    check("记忆文件损坏 → 按空表处理，不抛", broken._entries == {})

    # ---------------------------------------------------------------- 清除
    memory10 = new_memory(tmp)
    memory10._entries[key_a] = {"path": path_a, "name": "第一章.pptx", "page": 2,
                                "total": 10, "at": time.time()}
    memory10._save()
    memory10.observe(state(True, 1, 10))
    memory10._adopt_deck(path_a, "第一章.pptx")
    memory10.forget_current()
    check("忘掉当前课件", key_a not in memory10._entries)
    memory10.clear()
    check("清空全部", memory10._entries == {})

    print("=" * 44)
    print(f"失败 {FAILURES} 项")
    print("=" * 44)
    return 0 if FAILURES == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
