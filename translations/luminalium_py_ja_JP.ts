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
</TS>
