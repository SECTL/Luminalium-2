"""重新生成翻译文件：lupdate 扫 QML + lrelease 合并出 .qm。

用法（仓库根目录）::

    .venv\\Scripts\\python.exe -X utf8 tools\\update_translations.py

扫描范围与两侧 ts 的分工（2026-10-05 插件系统 Wave 2 任务 15 补记）
-----------------------------------------------------------------

* **QML 侧**：``pyside6-lupdate`` 递归扫 ``ui/`` 整棵树（含
  ``ui/plugins/<插件id>/``——插件界面文案同样是中文硬规约的一部分，
  漏扫会让插件的 ``qsTr`` 静默丢翻译），产出/更新
  ``translations/luminalium_<lang>.ts``。插件 QML 里的文案直接用
  ``qsTr("中文原文")`` 即可，无需任何额外标注。
* **Python 侧**：``translations/luminalium_py_<lang>.ts`` **手工维护，
  本脚本绝不用 lupdate 碰它**（AGENTS.md 明令）。Python 喂给 QML 的
  动态字符串（设置导航标题、快捷磁贴 title、编辑器组 display_name、
  托盘菜单等）走 ``app.i18n.tr(context, source)``，``context`` 与 ts
  里的 ``<name>`` 对应。
* **合并**：``pyside6-lrelease`` 把同一语言的 QML 侧 ts 与 Python 侧 ts
  合成一个 ``luminalium_<lang>.qm``（``app/i18n.py::install_translators``
  只加载这一个文件）。

lupdate 的默认行为（刻意不加 ``-no-obsolete``）
------------------------------------------------

字符串从**仍存在**的源文件中消失时，旧条目在 ts 里标记为
``type="vanished"`` 保留而非删除——译文不丢，字符串日后恢复时译文自动
回来。而**整个源文件被删**时，该文件的条目随 context 整体移除（任务 15
探针 ``ui/plugins/_probe/`` 实测如此）。清理尸体条目是发布前的人工决定，
不在这个日常脚本里做。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_SCRIPTS = ROOT / ".venv" / "Scripts"
TRANSLATIONS = ROOT / "translations"

#: 已有翻译的语言（源语言 zh_CN 不需要 ts）。
LANGUAGES = ("en_US", "ja_JP")

#: lupdate 的扫描根：ui/ 整树递归，天然覆盖 ui/plugins/<id>/。
QML_SOURCES = [ROOT / "ui"]


def _run(exe: str, args: list[str]) -> None:
    cmd = [str(VENV_SCRIPTS / exe), *args]
    print("+", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"{exe} 失败（退出码 {result.returncode}）")


def main() -> None:
    qml_ts = [str(TRANSLATIONS / f"luminalium_{lang}.ts") for lang in LANGUAGES]
    # 一次 lupdate 同时更新全部语言的 QML 侧 ts。
    _run("pyside6-lupdate.exe", [*(str(p) for p in QML_SOURCES), "-ts", *qml_ts])

    for lang in LANGUAGES:
        # lrelease 支持多个 ts 输入合并到同一个 -qm 输出。
        _run(
            "pyside6-lrelease.exe",
            [
                str(TRANSLATIONS / f"luminalium_{lang}.ts"),
                str(TRANSLATIONS / f"luminalium_py_{lang}.ts"),
                "-qm",
                str(TRANSLATIONS / f"luminalium_{lang}.qm"),
            ],
        )
    print("完成：ts 已更新，qm 已重建。")


if __name__ == "__main__":
    sys.exit(main())
