"""开发用：把更新页这一轮的文案改动同步进 en_US / ja_JP 的 .ts。

2026-10-05「一比一复刻 ClassIsland 排版」那轮改了 ``ui/settings/Update.qml``
与新拆出的 ``ui/settings/UpdateSettingsTab.qml``，对应几条 ``qsTr`` 文案变了。
**不用 lupdate 重扫**：它会把本轮没碰的 170 多条一起标成 obsolete 清掉
（实测 ``-no-obsolete`` 报 "Removed 173 obsolete entries"），那是别人的活。

所以这里做**外科手术**：按 ``<source>`` 精确匹配，删掉已不存在的条目、
改掉字面量变了的、新增新增的。``Update`` 段的 ``<location>`` 行号会过期 ——
Qt 按 source 匹配翻译，行号只是给人看的提示，不影响运行（下次跑 lupdate
自然会刷新），所以不动它们。

跑法：``.venv\\Scripts\\python.exe tools\\_sync_update_ts.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 随本轮改动**删除**的文案（原页面里已不存在）。
REMOVED = [
    "未找到当前版本的更新日志。",   # 「查看更新日志」对话框整块删了
    "查看更新日志",
    "真棒，您已更新到最新版本！",  # 换成原版文案
    "下载并安装",                  # 换成原版的「下载更新」
    "更新时发生错误，请检查您的网络连接并重试。",  # 拆成标题 + 正文
]

#: 新增文案。
ADDED: dict[str, dict[str, str]] = {
    "出错了": {
        "en_US": "Something went wrong",
        "ja_JP": "エラーが発生しました",
    },
    "更新时发生网络错误，请检查您的网络连接。": {
        "en_US": "A network error occurred while updating. Please check your "
                 "network connection.",
        "ja_JP": "更新中にネットワークエラーが発生しました。ネットワーク接続を"
                 "確認してください。",
    },
    "下载更新": {
        "en_US": "Download update",
        "ja_JP": "更新をダウンロード",
    },
    "已经是最新版啦，真棒，夸夸你哦♪": {
        "en_US": "You're on the latest version. Great job!",
        "ja_JP": "すでに最新バージョンです。すごい！",
    },
    "还没有检查过更新。": {
        "en_US": "No update check yet.",
        "ja_JP": "まだ更新を確認していません。",
    },
    "检查没能完成，请检查网络后重试。": {
        "en_US": "The check couldn't complete. Please check your network and "
                 "try again.",
        "ja_JP": "確認を完了できませんでした。ネットワークを確認して、もう一度"
                 "お試しください。",
    },
}

MESSAGE_RE = re.compile(
    r"    <message>\n(?:.*?\n)*?    </message>\n"
)


def patch(path: Path, lang: str) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8")
    removed = 0
    added = 0

    # ---- 1. 删已不存在的条目
    for source in REMOVED:
        pattern = re.compile(
            r"    <message>\n(?:(?!    </message>).)*?"
            r"<source>" + re.escape(source) + r"</source>\n"
            r"(?:(?!    </message>).)*?    </message>\n",
            re.S,
        )
        text, n = pattern.subn("", text)
        removed += n

    # ---- 2. 追加新增条目（塞进 <name>Update</name> 那个 context 末尾）
    m = re.search(r"(<name>Update</name>\n)", text)
    if not m:
        print(f"  [WARN] {path.name} 里找不到 <name>Update</name>，跳过新增")
        return removed, added, 0

    block = []
    for source, translations in ADDED.items():
        tr = translations.get(lang, "")
        if not tr:
            continue
        block.append(
            "    <message>\n"
            f"        <source>{source}</source>\n"
            f"        <translation>{tr}</translation>\n"
            "    </message>\n"
        )
        added += 1

    if block:
        # 插到该 context 的 </context> 之前
        start = m.end()
        end = text.index("</context>", start)
        text = text[:end] + "".join(block) + text[end:]

    path.write_text(text, encoding="utf-8")
    return removed, added, len(ADDED)


def main() -> int:
    for lang in ("en_US", "ja_JP"):
        path = ROOT / "translations" / f"luminalium_{lang}.ts"
        if not path.exists():
            print(f"跳过（不存在）: {path}")
            continue
        removed, added, total = patch(path, lang)
        print(f"{path.name}: 删除 {removed} 条，新增 {added}/{total} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
