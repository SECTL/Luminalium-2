"""Markdown → 给 QML ``Text.RichText`` 用的 HTML。

2026-10-06 用户指令：设置 → 更新页的「更新日志」里，一旦发布说明插了分辨率
很大的图片（比如 1920×1080 的截图），整块日志会被撑开、把页面里其它元素
挤下去。原因是 ``Text.MarkdownText`` 下图片按**原始像素**铺进文本流：
``Text`` 的 ``contentWidth`` 直接等于图宽（实测一张 2400×1600 的图 →
``contentWidth=2400``），超出列宽的部分被 ``FluentPage`` 的 Flickable 裁掉，
下面的兄弟项被顶出可视区。

**为什么必须换渲染路径**：Markdown 语法里图片不带尺寸，而 Qt 的 markdown
导入器会把行内 HTML **转义**——实测在 Markdown 文本里写
``<img width="300">``，渲出来是 38px 高的一行字面文本，不是图。所以
``MarkdownText`` 下没有任何约束图片尺寸的入口，唯一出路是整份转成 HTML、
改走 ``Text.RichText``，在那里给 ``<img>`` 加宽度上限。

**转换用 Qt 自己的 markdown 导入器**（``QTextDocument.setMarkdown`` →
``toHtml``），不手写解析器：标题 / 列表 / 引用 / 代码块 / 链接这些语义与
原先 ``MarkdownText`` 渲出来的完全一致，不会出现「换 HTML 之后版式变了」。

⚠️ 导出的 HTML 要**剥掉 Qt 写死的外观**，否则会盖掉 QML 侧的设计令牌：

* ``<head>`` 里的 ``<style>`` 块 —— QML 的富文本导入器不认 ``<style>`` 标签；
* ``<body style=" font-family:'…'; font-size:9pt; …">`` —— 会把 9pt 钉死，
  盖掉 ``Rin.Text`` 按主题算出来的字号与字体；
* 链接上那层 ``<span style=" color:#99ecfe;">`` —— 会盖掉 ``Rin.Text`` 的
  ``linkColor``（主题强调色），浅色主题下那点浅蓝几乎看不见。

剥完之后外观完全由 QML 决定（``Rin.Text`` 的 color / font / linkColor），
HTML 只负责结构。

⚠️ **图片尺寸不在这里加**：宽度上限要参照「日志列的实际宽度」，那是 UI 侧的
运行时量（设置窗口宽窄会变）。这里只保证 ``<img>`` 干净（Qt 导出时本来就不带
width/height），由 ``ui/settings/Update.qml`` 在绑定里注入
``style="max-width:100%"``。

⚠️ **转换跑在检查更新的后台线程里**：``QTextDocument`` 不碰任何 GUI 资源，
在非 GUI 线程建与用都是安全的；发布说明动辄几千字，没必要压在 UI 线程上。
"""

from __future__ import annotations

import logging
import re
from html import escape

from PySide6.QtGui import QTextDocument

log = logging.getLogger(__name__)

#: ``<head>`` 整段（里面只有 Qt 的 ``<style>`` 块，QML 富文本不认）。
_HEAD_RE = re.compile(r"<head>.*?</head>", re.S)

#: 文档类型声明行。
_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>", re.I)

#: ``<body style="…">`` —— 整段换成裸 ``<body>``，字体交回 QML。
_BODY_RE = re.compile(r"<body[^>]*>")

#: Qt 给链接套的那层颜色 span：``<a href="…"><span style=" color:#99ecfe;">``。
#: 只剥掉 color 一项，span 本身留着（形态是 Qt 固定输出的，匹配很稳）。
_LINK_COLOR_RE = re.compile(
    r'(<a\s[^>]*>\s*<span style="[^"]*?)\s*color:\s*#[0-9A-Fa-f]{3,8}\s*;'
)


def _plain_fallback(markdown: str) -> str:
    """转换失败时的兜底：按空行分段、整段转义。

    宁可把 Markdown 记号当成字面文本显示（``## 新增`` 原样出现），也不能让
    更新日志整块消失 —— 那是用户唯一能看见「新版改了什么」的地方。
    """
    blocks = re.split(r"\n\s*\n", markdown.strip())
    return "".join(
        f"<p>{escape(block)}</p>" for block in blocks if block.strip()
    )


def to_html(markdown: str) -> str:
    """把 Markdown 转成可直接喂给 ``Text.RichText`` 的 HTML。

    空输入返回空串（QML 侧 ``visible`` 另有绑定，空串不会留下空行）。
    转换抛异常时记日志并退回 :func:`_plain_fallback`。
    """
    text = str(markdown or "")
    if not text.strip():
        return ""
    try:
        document = QTextDocument()
        document.setMarkdown(text)
        html = document.toHtml()
    except Exception:  # noqa: BLE001 - 日志区不能因为一次解析失败就整块消失
        log.exception("Markdown 转 HTML 失败，回退到纯文本")
        return _plain_fallback(text)

    html = _DOCTYPE_RE.sub("", html)
    html = _HEAD_RE.sub("", html)
    html = _BODY_RE.sub("<body>", html)
    html = _LINK_COLOR_RE.sub(r"\1", html)
    return html
