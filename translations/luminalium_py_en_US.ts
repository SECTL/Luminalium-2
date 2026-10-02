<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US">
<!--
  Luminalium 2 English translations (Python side).

  Python 侧没有 lupdate 可扫的 tr() 调用（文案走 app/i18n.py::tr(context, source)
  手工标注），所以这个文件**手工维护**，lupdate 不会碰它 —— 与 QML 侧的
  luminalium_en_US.ts 分开存放就是为了这个。

  重新生成 .qm:
      .venv/Scripts/pyside6-lrelease.exe translations/luminalium_py_en_US.ts -qm translations/luminalium_py_en_US.qm
-->
<context>
    <name>Splash</name>
    <message>
        <source>初始化</source>
        <translation>Initializing</translation>
    </message>
    <message>
        <source>创建托盘图标</source>
        <translation>Creating tray icon</translation>
    </message>
    <message>
        <source>启动放映探测</source>
        <translation>Starting slideshow detection</translation>
    </message>
    <message>
        <source>就绪</source>
        <translation>Ready</translation>
    </message>
    <message>
        <source>正在进行启动后操作</source>
        <translation>Running post-start tasks</translation>
    </message>
</context>
<context>
    <name>Tray</name>
    <message>
        <source>打开快捷面板</source>
        <translation>Open quick panel</translation>
    </message>
    <message>
        <source>设置</source>
        <translation>Settings</translation>
    </message>
    <message>
        <source>显示/隐藏放映控制条（手动）</source>
        <translation>Show/Hide control bar (manual)</translation>
    </message>
    <message>
        <source>诊断信息（写入日志）</source>
        <translation>Diagnostics (write to log)</translation>
    </message>
    <message>
        <source>退出</source>
        <translation>Exit</translation>
    </message>
</context>
<context>
    <name>Overflow</name>
    <message>
        <source>上一页</source>
        <translation>Previous slide</translation>
    </message>
    <message>
        <source>下一页</source>
        <translation>Next slide</translation>
    </message>
    <message>
        <source>退出放映</source>
        <translation>Exit slideshow</translation>
    </message>
</context>
<context>
    <name>App</name>
    <message>
        <source>诊断信息</source>
        <translation>Diagnostics</translation>
    </message>
    <message>
        <source>已写入 logs/luminalium.log</source>
        <translation>Written to logs/luminalium.log</translation>
    </message>
</context>
</TS>
