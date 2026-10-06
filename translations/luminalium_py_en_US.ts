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
<context>
    <name>ErrorHandler</name>
    <message>
        <source>崩溃报告</source>
        <translation>Crash report</translation>
    </message>
    <message>
        <source>错误报告</source>
        <translation>Error report</translation>
    </message>
    <message>
        <source>程序崩溃了！</source>
        <translation>The program has crashed!</translation>
    </message>
    <message>
        <source>程序出现了一个错误！</source>
        <translation>The program ran into an error!</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个自己无法恢复的问题，不得不停下来。你可以尝试重新启动；如果它反复出现，请把下面的详细信息反馈给我们。</source>
        <translation>{app_name} ran into a problem it could not recover from and had to stop. You can try restarting; if it keeps happening, please send us the details below.</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个问题。程序还可以继续运行，但最好把下面的详细信息反馈给我们，方便我们修掉它。</source>
        <translation>{app_name} ran into a problem. The app can keep running, but please send us the details below so we can fix it.</translation>
    </message>
    <message>
        <source>主线程</source>
        <translation>Main thread</translation>
    </message>
    <message>
        <source>后台线程</source>
        <translation>Background thread</translation>
    </message>
    <message>
        <source>线程 {name}</source>
        <translation>Thread {name}</translation>
    </message>
    <message>
        <source>环境信息</source>
        <translation>Environment</translation>
    </message>
    <message>
        <source>应用版本</source>
        <translation>App version</translation>
    </message>
    <message>
        <source>报告类型</source>
        <translation>Report type</translation>
    </message>
    <message>
        <source>发生时间</source>
        <translation>Time</translation>
    </message>
    <message>
        <source>来源</source>
        <translation>Source</translation>
    </message>
    <message>
        <source>操作系统</source>
        <translation>OS</translation>
    </message>
    <message>
        <source>摘要</source>
        <translation>Summary</translation>
    </message>
    <message>
        <source>堆栈</source>
        <translation>Traceback</translation>
    </message>
    <message>
        <source>未知</source>
        <translation>Unknown</translation>
    </message>
    <message>
        <source>(无)</source>
        <translation>(none)</translation>
    </message>
    <message>
        <source>RuntimeError: 这是一条手动触发的错误报告</source>
        <translation>RuntimeError: This is a manually triggered error report</translation>
    </message>
    <message>
        <source>这条报告来自调试窗口的「手动报错」，程序本身并没有出错。
用途：核对错误报告窗的版式、表情图与主按钮（忽略）。</source>
        <translation>This report came from &quot;Trigger an error&quot; in the debug window; the app did not actually fail.
Purpose: check the layout, emoji, and primary button (&quot;Ignore&quot;) of the error report window.</translation>
    </message>
</context>
<context>
    <name>Plugins</name>
    <!-- 任务 15（2026-10-05）探针条目：验证 Python 侧手工维护的 ts 经
         lrelease 合并后 app.i18n.tr 能命中。保留作回归样例。 -->
    <message>
        <source>演示插件</source>
        <translation>Demo plugin</translation>
    </message>
</context>
<context>
    <name>Settings</name>
    <!-- 任务 7（2026-10-05）：设置窗口导航项从 QML 硬编码搬进 Python
         （app/bridge.py::_BUILTIN_SETTINGS_NAV），标题改走 app.i18n.tr。
         context 沿用原 QML 侧的 Settings，译文从 luminalium_en_US.ts 平移；
         lupdate 重扫后 QML 侧这六条会消失，由本文件承接。 -->
    <message>
        <source>主页</source>
        <translation>Home</translation>
    </message>
    <message>
        <source>通用</source>
        <translation>General</translation>
    </message>
    <message>
        <source>个性化</source>
        <translation>Personalization</translation>
    </message>
    <message>
        <source>主界面</source>
        <translation>Main interface</translation>
    </message>
    <message>
        <!-- 任务 17（2026-10-05）：内建「插件」管理页加入 _BUILTIN_SETTINGS_NAV。 -->
        <source>插件</source>
        <translation>Plugins</translation>
    </message>
    <message>
        <source>关于</source>
        <translation>About</translation>
    </message>
    <message>
        <source>更新</source>
        <translation>Update</translation>
    </message>
</context>
</TS>
