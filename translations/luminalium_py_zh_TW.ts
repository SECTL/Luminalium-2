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
<TS version="2.1" language="zh_TW">

<context>
    <name>Splash</name>
    <message>
        <source>初始化</source>
        <translation>初始化</translation>
    </message>
    <message>
        <source>创建托盘图标</source>
        <translation>建立系統匣圖示</translation>
    </message>
    <message>
        <source>启动放映探测</source>
        <translation>啟動放映偵測</translation>
    </message>
    <message>
        <source>就绪</source>
        <translation>就緒</translation>
    </message>
    <message>
        <source>正在进行启动后操作</source>
        <translation>正在執行啟動後的操作</translation>
    </message>
</context>
<context>
    <name>Tray</name>
    <message>
        <source>打开快捷面板</source>
        <translation>開啟快速面板</translation>
    </message>
    <message>
        <source>设置</source>
        <translation>設定</translation>
    </message>
    <message>
        <source>显示/隐藏放映控制条（手动）</source>
        <translation>顯示 / 隱藏放映控制列（手動）</translation>
    </message>
    <message>
        <source>诊断信息（写入日志）</source>
        <translation>診斷資訊（寫入記錄檔）</translation>
    </message>
    <message>
        <source>退出</source>
        <translation>結束</translation>
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
        <translation>結束放映</translation>
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
        <translation>已寫入 logs/luminalium.log</translation>
    </message>
</context>
<context>
    <name>ErrorHandler</name>
    <message>
        <source>崩溃报告</source>
        <translation>崩潰報告</translation>
    </message>
    <message>
        <source>错误报告</source>
        <translation>錯誤報告</translation>
    </message>
    <message>
        <source>程序崩溃了！</source>
        <translation>程式崩潰了！</translation>
    </message>
    <message>
        <source>程序出现了一个错误！</source>
        <translation>程式發生了一個錯誤！</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个自己无法恢复的问题，不得不停下来。你可以尝试重新启动；如果它反复出现，请把下面的详细信息反馈给我们。</source>
        <translation>{app_name} 遇到了一個自己無法修復的問題，不得不停下來。你可以嘗試重新啟動；如果一再發生，請把下面的詳細資訊回報給我們。</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个问题。程序还可以继续运行，但最好把下面的详细信息反馈给我们，方便我们修掉它。</source>
        <translation>{app_name} 遇到了一個問題。程式還可以繼續執行，但最好把下面的詳細資訊回報給我們，方便我們修好它。</translation>
    </message>
    <message>
        <source>主线程</source>
        <translation>主執行緒</translation>
    </message>
    <message>
        <source>后台线程</source>
        <translation>背景執行緒</translation>
    </message>
    <message>
        <source>线程 {name}</source>
        <translation>執行緒 {name}</translation>
    </message>
    <message>
        <source>环境信息</source>
        <translation>環境資訊</translation>
    </message>
    <message>
        <source>应用版本</source>
        <translation>應用程式版本</translation>
    </message>
    <message>
        <source>报告类型</source>
        <translation>報告類型</translation>
    </message>
    <message>
        <source>发生时间</source>
        <translation>發生時間</translation>
    </message>
    <message>
        <source>来源</source>
        <translation>來源</translation>
    </message>
    <message>
        <source>操作系统</source>
        <translation>作業系統</translation>
    </message>
    <message>
        <source>摘要</source>
        <translation>摘要</translation>
    </message>
    <message>
        <source>堆栈</source>
        <translation>堆疊</translation>
    </message>
    <message>
        <source>未知</source>
        <translation>未知</translation>
    </message>
    <message>
        <source>(无)</source>
        <translation>（無）</translation>
    </message>
    <message>
        <source>RuntimeError: 这是一条手动触发的错误报告</source>
        <translation>RuntimeError: 這是一條手動觸發的錯誤報告</translation>
    </message>
    <message>
        <source>这条报告来自调试窗口的「手动报错」，程序本身并没有出错。
用途：核对错误报告窗的版式、表情图与主按钮（忽略）。</source>
        <translation>這份報告來自偵錯視窗的「手動回報錯誤」，程式本身並沒有出錯。
用途：核對錯誤報告視窗的版面、表情圖與主按鈕（忽略）。</translation>
    </message>
</context>
<context>
    <name>Plugins</name>
    
    <message>
        <source>演示插件</source>
        <translation>示範外掛</translation>
    </message>
<message><source>选择插件文件夹</source><translation>選擇外掛資料夾</translation></message><message><source>选择插件包</source><translation>選擇外掛套件</translation></message><message><source>插件包 (*.zip);;所有文件 (*)</source><translation>外掛套件 (*.zip);;所有檔案 (*)</translation></message></context>
<context>
    <name>Settings</name>
    
    <message>
        <source>主页</source>
        <translation>首頁</translation>
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
        <translation>墨跡與標註</translation>
    </message>
    <message>
        
        <source>插件</source>
        <translation>外掛</translation>
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
<context><name>timer_l1</name><message><source>计时器（Luminalium 1）</source><translation>計時器（Luminalium 1）</translation></message><message><source>计时器</source><translation>計時器</translation></message><message><source>打开 / 收起计时器</source><translation>開啟 / 收起計時器</translation></message></context><context><name>blackboard</name><message><source>小黑板</source><translation>小黑板</translation></message><message><source>打开 / 收起小黑板</source><translation>開啟 / 收起小黑板</translation></message></context><context><name>spotlight</name><message><source>聚光灯</source><translation>聚光燈</translation></message><message><source>开启 / 关闭聚光灯遮罩</source><translation>開啟 / 關閉聚光燈遮罩</translation></message><message><source>聚光灯遮罩</source><translation>聚光燈遮罩</translation></message></context></TS>