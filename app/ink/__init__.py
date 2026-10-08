"""自建墨迹包：QML 类型注册与输入环境收口。

2026-10-07 用户指令：自建批注替代 COM 笔/橡皮。

为什么单独一个 ``register_qml_types()`` 而不是导入即注册：仓库里有三个各自
建引擎的地方（``app/application.py``、``tools/check_qml.py``、``tools/preview.py``），
都得在**第一次加载 QML 之前**显式调用一次 —— 导入副作用式的注册在哪个时机
生效全看谁先 import，排查起来是噩梦。

``configure_input_attributes()`` 是同一套收口纪律的另一条：QApplication 创建
**前后各调一次**（为什么是两次：Qt 6.11/Windows 实测构造期间会把属性翻回
True，而属性是投递时现查的——见函数 docstring），同样由各入口显式调
（谁建 QApplication 谁负责）。

幂等（模块级旗标）：同一进程里重复注册同一 URI/类型会让 Qt 刷警告，而装配
可能被测试脚本重复执行（与 ``_register_builtin_verbs`` 同一个理由）。

URI ``Luminalium.Ink`` 1.0 / 类型名 ``InkLayer`` 是**定死的契约**：
``ui/ink/InkOverlay.qml`` 按这个名字 import，改名要两边一起改。
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtQml import qmlRegisterType

from .layer import InkLayer

QML_URI = "Luminalium.Ink"

_registered = False


def register_qml_types() -> None:
    """把墨迹相关的 Python 类型登记进 QML 类型系统（进程内只做一次）。"""
    global _registered
    if _registered:
        return
    qmlRegisterType(InkLayer, QML_URI, 1, 0, "InkLayer")
    _registered = True


def configure_input_attributes() -> None:
    """关掉高频指针事件的合并压缩（幂等，构造前后各调一次——原因见下）。

    为什么要关：Windows 平台的指针处理里，触屏/笔一帧多个采样（skipped frames /
    pointer history）只在 ``AA_CompressHighFrequencyEvents`` 为 False 时才逐帧派发
    （qtbase ``qwindowspointerhandler.cpp``：touch 只看这个属性，pen 看它和
    ``AA_CompressTabletEvents`` 任一为 False）。压缩开着时高回报率设备一帧只送
    最后一个采样，1€ 滤波和抽稀（smoothing.py）就没米下锅。

    时机（2026-10-07 踩坑实录，Qt 6.11.2 / Windows 实测）：构造**前**设置会被
    推翻 —— QApplication/QGuiApplication 构造期间（平台集成初始化）把该属性
    翻回 True，构造后读回是 True。属性是每次指针事件现查的（不缓存），所以
    **构造之后再调一次**才真正生效。本函数不关心调用顺序、可重复调用：
    各入口在 QApplication 创建前后各调一次，两个位置都兜住。
    """
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_CompressHighFrequencyEvents, False)


__all__ = ["InkLayer", "QML_URI", "configure_input_attributes", "register_qml_types"]
