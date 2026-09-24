"""Luminalium 2 —— 桌面快捷控制中枢。

模块划分::

    app.paths           路径常量
    app.config          配置读写
    app.ppt_controller  PPT 控制器（放映探测 / 控制 / 状态广播，独立模块）
    app.bridge          暴露给 QML 的后端对象
    app.tray            托盘常驻
    app.windows         窗口管理（快捷面板 / 顶层窗口）
    app.application     应用装配入口
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
