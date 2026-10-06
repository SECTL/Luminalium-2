<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ja_JP">
<!--
  Luminalium 2 日本語訳（Python 側）。

  Python 侧没有 lupdate 可扫的 tr() 调用（文案走 app/i18n.py::tr(context, source)
  手工标注），所以这个文件**手工维护**，lupdate 不会碰它 —— 与 QML 侧的
  luminalium_ja_JP.ts 分开存放就是为了这个。

  重新生成 .qm:
      .venv/Scripts/pyside6-lrelease.exe translations/luminalium_py_ja_JP.ts -qm translations/luminalium_py_ja_JP.qm
-->
<context>
    <name>Splash</name>
    <message>
        <source>初始化</source>
        <translation>初期化中</translation>
    </message>
    <message>
        <source>创建托盘图标</source>
        <translation>トレイアイコンの作成</translation>
    </message>
    <message>
        <source>启动放映探测</source>
        <translation>スライドショー検出の開始</translation>
    </message>
    <message>
        <source>就绪</source>
        <translation>準備完了</translation>
    </message>
    <message>
        <source>正在进行启动后操作</source>
        <translation>起動後の処理を実行中</translation>
    </message>
</context>
<context>
    <name>Tray</name>
    <message>
        <source>打开快捷面板</source>
        <translation>クイックパネルを開く</translation>
    </message>
    <message>
        <source>设置</source>
        <translation>設定</translation>
    </message>
    <message>
        <source>显示/隐藏放映控制条（手动）</source>
        <translation>コントロールバーの表示/非表示（手動）</translation>
    </message>
    <message>
        <source>诊断信息（写入日志）</source>
        <translation>診断情報（ログに書き込む）</translation>
    </message>
    <message>
        <source>退出</source>
        <translation>終了</translation>
    </message>
</context>
<context>
    <name>Overflow</name>
    <message>
        <source>上一页</source>
        <translation>前のスライド</translation>
    </message>
    <message>
        <source>下一页</source>
        <translation>次のスライド</translation>
    </message>
    <message>
        <source>退出放映</source>
        <translation>スライドショーの終了</translation>
    </message>
</context>
<context>
    <name>App</name>
    <message>
        <source>诊断信息</source>
        <translation>診断情報</translation>
    </message>
    <message>
        <source>已写入 logs/luminalium.log</source>
        <translation>logs/luminalium.log に書き込みました</translation>
    </message>
</context>
<context>
    <name>ErrorHandler</name>
    <message>
        <source>崩溃报告</source>
        <translation>クラッシュレポート</translation>
    </message>
    <message>
        <source>错误报告</source>
        <translation>エラーレポート</translation>
    </message>
    <message>
        <source>程序崩溃了！</source>
        <translation>プログラムがクラッシュしました！</translation>
    </message>
    <message>
        <source>程序出现了一个错误！</source>
        <translation>プログラムでエラーが発生しました！</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个自己无法恢复的问题，不得不停下来。你可以尝试重新启动；如果它反复出现，请把下面的详细信息反馈给我们。</source>
        <translation>{app_name} で自力では回復できない問題が発生し、停止せざるを得ませんでした。再起動してみてください。繰り返し発生する場合は、以下の詳細を報告してください。</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个问题。程序还可以继续运行，但最好把下面的详细信息反馈给我们，方便我们修掉它。</source>
        <translation>{app_name} で問題が発生しました。アプリは引き続き動作しますが、修正のため以下の詳細を報告していただけると助かります。</translation>
    </message>
    <message>
        <source>主线程</source>
        <translation>メインスレッド</translation>
    </message>
    <message>
        <source>后台线程</source>
        <translation>バックグラウンドスレッド</translation>
    </message>
    <message>
        <source>线程 {name}</source>
        <translation>スレッド {name}</translation>
    </message>
    <message>
        <source>环境信息</source>
        <translation>環境情報</translation>
    </message>
    <message>
        <source>应用版本</source>
        <translation>アプリのバージョン</translation>
    </message>
    <message>
        <source>报告类型</source>
        <translation>レポートの種類</translation>
    </message>
    <message>
        <source>发生时间</source>
        <translation>発生日時</translation>
    </message>
    <message>
        <source>来源</source>
        <translation>発生元</translation>
    </message>
    <message>
        <source>操作系统</source>
        <translation>OS</translation>
    </message>
    <message>
        <source>摘要</source>
        <translation>概要</translation>
    </message>
    <message>
        <source>堆栈</source>
        <translation>スタックトレース</translation>
    </message>
    <message>
        <source>未知</source>
        <translation>不明</translation>
    </message>
    <message>
        <source>(无)</source>
        <translation>(なし)</translation>
    </message>
    <message>
        <source>RuntimeError: 这是一条手动触发的错误报告</source>
        <translation>RuntimeError: 手動で発生させたエラーレポートです</translation>
    </message>
    <message>
        <source>这条报告来自调试窗口的「手动报错」，程序本身并没有出错。
用途：核对错误报告窗的版式、表情图与主按钮（忽略）。</source>
        <translation>このレポートはデバッグウィンドウの「手動エラー」から出力されたもので、アプリ自体は正常です。
用途：エラーレポートウィンドウのレイアウト・絵文字・主ボタン（無視）の確認。</translation>
    </message>
</context>
<context>
    <name>Settings</name>
    <!-- 任务 7（2026-10-05）：设置窗口导航项从 QML 硬编码搬进 Python
         （app/bridge.py::_BUILTIN_SETTINGS_NAV），标题改走 app.i18n.tr。
         context 沿用原 QML 侧的 Settings，译文从 luminalium_ja_JP.ts 平移；
         lupdate 重扫后 QML 侧这六条会消失，由本文件承接。 -->
    <message>
        <source>主页</source>
        <translation>ホーム</translation>
    </message>
    <message>
        <source>通用</source>
        <translation>全般</translation>
    </message>
    <message>
        <source>个性化</source>
        <translation>パーソナライズ</translation>
    </message>
    <message>
        <source>主界面</source>
        <translation>メイン画面</translation>
    </message>
    <message>
        <source>关于</source>
        <translation>バージョン情報</translation>
    </message>
    <message>
        <source>更新</source>
        <translation>更新</translation>
    </message>
</context>
</TS>
