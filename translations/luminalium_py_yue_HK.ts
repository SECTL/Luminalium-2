<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<!--
  Luminalium 2 English translations (Python side).

  Python 侧没有 lupdate 可扫的 tr() 调用（文案走 app/i18n.py::tr(context, source)
  手工标注），所以这个文件**手工维护**，lupdate 不会碰它 —— 与 QML 侧的
  luminalium_en_US.ts 分开存放就是为了这个。

  重新生成 .qm:
      .venv/Scripts/pyside6-lrelease.exe translations/luminalium_py_en_US.ts -qm translations/luminalium_py_en_US.qm
-->
<TS version="2.1" language="yue_HK">

<context>
    <name>Splash</name>
    <message>
        <source>初始化</source>
        <translation>initial 緊</translation>
    </message>
    <message>
        <source>创建托盘图标</source>
        <translation>開緊 tray icon</translation>
    </message>
    <message>
        <source>启动放映探测</source>
        <translation>開放映偵測</translation>
    </message>
    <message>
        <source>就绪</source>
        <translation>搞掂</translation>
    </message>
    <message>
        <source>正在进行启动后操作</source>
        <translation>做緊開機嗰啲嘢</translation>
    </message>
</context>
<context>
    <name>Tray</name>
    <message>
        <source>打开快捷面板</source>
        <translation>開快捷 panel</translation>
    </message>
    <message>
        <source>设置</source>
        <translation>設定</translation>
    </message>
    <message>
        <source>显示/隐藏放映控制条（手动）</source>
        <translation>show / hide 放映控制條（手動）</translation>
    </message>
    <message>
        <source>诊断信息（写入日志）</source>
        <translation>診斷資訊（寫落 log）</translation>
    </message>
    <message>
        <source>退出</source>
        <translation>走人</translation>
    </message>
</context>
<context>
    <name>Overflow</name>
    <message>
        <source>上一页</source>
        <translation>上一頁</translation>
    </message>
    <message>
        <source>下一页</source>
        <translation>下一頁</translation>
    </message>
    <message>
        <source>退出放映</source>
        <translation>唔播啦收工</translation>
    </message>
</context>
<context>
    <name>App</name>
    <message>
        <source>诊断信息</source>
        <translation>診斷資訊</translation>
    </message>
    <message>
        <source>已写入 logs/luminalium.log</source>
        <translation>寫咗落 logs/luminalium.log</translation>
    </message>
</context>
<context>
    <name>ErrorHandler</name>
    <message>
        <source>崩溃报告</source>
        <translation>crash 報告</translation>
    </message>
    <message>
        <source>错误报告</source>
        <translation>error 報告</translation>
    </message>
    <message>
        <source>程序崩溃了！</source>
        <translation>個 app crash 咗！</translation>
    </message>
    <message>
        <source>程序出现了一个错误！</source>
        <translation>個 app 出咗個 error！</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个自己无法恢复的问题，不得不停下来。你可以尝试重新启动；如果它反复出现，请把下面的详细信息反馈给我们。</source>
        <translation>{app_name} 撞到個自己搞唔掂嘅問題，惟有停低。你可以試吓重新開；如果次次都係咁，就將下面啲詳細資料 send 畀我哋。</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个问题。程序还可以继续运行，但最好把下面的详细信息反馈给我们，方便我们修掉它。</source>
        <translation>{app_name} 出咗個問題。個 app 仲行得落去，不過最好將下面啲詳細資料 send 畀我哋，等我哋修好佢。</translation>
    </message>
    <message>
        <source>主线程</source>
        <translation>main thread</translation>
    </message>
    <message>
        <source>后台线程</source>
        <translation>background thread</translation>
    </message>
    <message>
        <source>线程 {name}</source>
        <translation>thread {name}</translation>
    </message>
    <message>
        <source>环境信息</source>
        <translation>環境資料</translation>
    </message>
    <message>
        <source>应用版本</source>
        <translation>app 版本</translation>
    </message>
    <message>
        <source>报告类型</source>
        <translation>報告類型</translation>
    </message>
    <message>
        <source>发生时间</source>
        <translation>幾時發生</translation>
    </message>
    <message>
        <source>来源</source>
        <translation>邊度嚟</translation>
    </message>
    <message>
        <source>操作系统</source>
        <translation>OS</translation>
    </message>
    <message>
        <source>摘要</source>
        <translation>摘要</translation>
    </message>
    <message>
        <source>堆栈</source>
        <translation>stack</translation>
    </message>
    <message>
        <source>未知</source>
        <translation>唔知</translation>
    </message>
    <message>
        <source>(无)</source>
        <translation>（冇）</translation>
    </message>
    <message>
        <source>RuntimeError: 这是一条手动触发的错误报告</source>
        <translation>RuntimeError: 呢個係手動 trigger 嘅 error 報告</translation>
    </message>
    <message>
        <source>这条报告来自调试窗口的「手动报错」，程序本身并没有出错。
用途：核对错误报告窗的版式、表情图与主按钮（忽略）。</source>
        <translation>呢份報告係 debug 窗嗰粒「手動報錯」整出嚟，個 app 本身冇事。
用嚟對吓 error 報告窗嘅 layout、emoji 圖同主掣（唔理佢）。</translation>
    </message>
</context>
<context>
    <name>Plugins</name>
    
    <message>
        <source>演示插件</source>
        <translation>demo plugin</translation>
    </message>
<message><source>选择插件文件夹</source><translation>揀 plugin folder</translation></message><message><source>选择插件包</source><translation>揀 plugin 包</translation></message><message><source>插件包 (*.zip);;所有文件 (*)</source><translation>plugin 包 (*.zip);;所有 file (*)</translation></message></context>
<context>
    <name>Settings</name>
    
    <message>
        <source>主页</source>
        <translation>主頁</translation>
    </message>
    <message>
        <source>通用</source>
        <translation>一般</translation>
    </message>
    <message>
        <source>个性化</source>
        <translation>個人化</translation>
    </message>
    <message>
        <source>主界面</source>
        <translation>主介面</translation>
    </message>
    <message>
        <source>墨迹和批注</source>
        <translation>筆跡同批註</translation>
    </message>
    <message>
        
        <source>插件</source>
        <translation>plugins</translation>
    </message>
    <message>
        <source>关于</source>
        <translation>關於</translation>
    </message>
    <message>
        <source>更新</source>
        <translation>更新</translation>
    </message>
</context>
<context><name>timer</name><message><source>计时器</source><translation>timer</translation></message><message><source>打开 / 收起计时器</source><translation>開 / 收起 timer</translation></message></context><context><name>blackboard</name><message><source>小黑板</source><translation>細黑板</translation></message><message><source>打开 / 收起小黑板</source><translation>開 / 收起細黑板</translation></message></context><context><name>spotlight</name><message><source>聚光灯</source><translation>聚光燈</translation></message><message><source>开启 / 关闭聚光灯遮罩</source><translation>開 / 閂聚光燈遮罩</translation></message><message><source>聚光灯遮罩</source><translation>聚光燈遮罩</translation></message></context></TS>