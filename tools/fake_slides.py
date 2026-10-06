"""合成「幻灯片」图 —— 只给 ``tools/`` 下的预览与探针用。

真机上页码面板里那几十张画面来自 COM ``Slides(i).Export``（见
``app/slide_thumbs.py`` 的头注释），预览 / 探针进程里没有 PowerPoint，所以换成
「现画一张」。⚠️ 绕过去的**只有画图这一步** —— 队列、代次号、节流、Pillow 烤圆角、
``file://`` 转换走的都是 ``app.slide_thumbs`` 的真代码，所以拿它跑出来的图能证明
「QML 那条 Image 路是通的」。

每页换一个色相：翻起来一眼能看出「换到第几页了」，也顺带证明「哪张图来自哪一页」
没有错位。合成图上**故意不画页码** —— 页码是 QML 那一层画的，图上再画一个只会
跟它打架。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

#: 与 ``app/slide_thumbs.EXPORT_WIDTH/HEIGHT`` 同一档（16:9）。
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 180


def write_fake_slide(path: str, page: int, width: int = DEFAULT_WIDTH,
                     height: int = DEFAULT_HEIGHT) -> bool:
    """把第 ``page`` 页画成一张 16:9 的 PNG。失败返回 False（Pillow 没装）。"""
    try:
        import colorsys

        from PIL import Image, ImageDraw
    except Exception:
        return False

    w = max(1, int(width))
    h = max(1, int(height))
    hue = ((int(page) * 37) % 360) / 360.0

    def rgb(saturation: float, value: float) -> tuple[int, int, int]:
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        return (int(r * 255), int(g * 255), int(b * 255))

    image = Image.new("RGB", (w, h), rgb(0.30, 0.26))
    draw = ImageDraw.Draw(image)
    # 一页「幻灯片」的版式：标题条 + 三行正文条
    draw.rectangle([w * 0.08, h * 0.13, w * 0.52, h * 0.24], fill=rgb(0.55, 0.80))
    body = rgb(0.10, 0.72)
    for y, x1 in ((0.38, 0.92), (0.50, 0.76), (0.62, 0.86)):
        draw.rectangle([w * 0.08, h * y, w * x1, h * y + h * 0.055], fill=body)
    image.save(path, "PNG")
    return True


class FakeSlideExporter(QObject):
    """假的 COM 导出器：接口与 ``PptController`` 上那条完全相同。

    真机是 COM 线程异步回信号；这里写完文件就**同步**发 ``thumbnailReady``
    （语义一样，只是把等待抹掉了 —— 工具要的是确定性）。
    """

    thumbnailReady = Signal(int, str)

    def export_slide_thumbnail(self, index: int, path: str,
                               width: int = DEFAULT_WIDTH,
                               height: int = DEFAULT_HEIGHT) -> bool:
        page = int(index)
        if not write_fake_slide(str(path), page, int(width), int(height)):
            return False
        self.thumbnailReady.emit(page, str(path))
        return True
