<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ja_JP">
<!--
  Luminalium 2 日本語訳（QML 側）。

  * 生成方法:
      .venv/Scripts/pyside6-lupdate.exe -recursive ui -ts translations/luminalium_ja_JP.ts -no-obsolete
      .venv/Scripts/pyside6-lrelease.exe translations/luminalium_ja_JP.ts -qm translations/luminalium_ja_JP.qm
  * ⚠️ 本文件只收 QML 的 qsTr() 字符串（lupdate 扫描 ui/ 自动维护）。
    Python 侧的可见文案（托盘菜单 / 启动画面阶段文案 / 溢出菜单）在
    luminalium_py_ja_JP.ts，别混进来 —— lupdate -no-obsolete 会把
    源码里扫不到的条目当「过时」删掉。
-->
<context>
    <name>About</name>
    <message>
        <location filename="../ui/settings/About.qml" line="130"/>
        <source>关于</source>
        <translation>バージョン情報</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="150"/>
        <source>© 2025-2026 Seirai Haraguchi / @SECTL Studio</source>
        <translation>© 2025-2026 Seirai Haraguchi / @SECTL Studio</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="151"/>
        <source>本程序基于 MIT License 获得许可</source>
        <translation>本ソフトウェアは MIT License の下で提供されています</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="168"/>
        <source>（Codename %1）</source>
        <translation>（コードネーム %1）</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="177"/>
        <source>查看本仓库</source>
        <translation>リポジトリを表示</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="195"/>
        <source>反馈问题或功能建议</source>
        <translation>問題の報告・機能の提案</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="196"/>
        <source>在 GitHub 上提交 Issue</source>
        <translation>GitHub で Issue を作成</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="221"/>
        <source>依赖与参考</source>
        <translation>依存ライブラリと参考</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="230"/>
        <source>Qt &amp; Qt Quick</source>
        <translation>Qt &amp; Qt Quick</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="235"/>
        <source>Qt for Python（PySide6）</source>
        <translation>Qt for Python（PySide6）</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="240"/>
        <source>Fluent Design System</source>
        <translation>Fluent Design System</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="245"/>
        <source>RinUI</source>
        <translation>RinUI</translation>
    </message>
    <message>
        <location filename="../ui/settings/About.qml" line="250"/>
        <source>pywin32</source>
        <translation>pywin32</translation>
    </message>
</context>
<context>
    <name>DebugWindow</name>
    <message>
        <location filename="../ui/DebugWindow.qml" line="26"/>
        <source>调试</source>
        <translation>デバッグ</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="64"/>
        <source>诊断</source>
        <translation>診断</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="69"/>
        <source>日志级别</source>
        <translation>ログレベル</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="70"/>
        <source>排查问题时改成 DEBUG，日志写在 logs/luminalium.log</source>
        <translation>問題調査時は DEBUG に変更します。ログは logs/luminalium.log に書き込まれます</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="83"/>
        <source>放映检测轮询间隔</source>
        <translation>スライドショー検出のポーリング間隔</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="86"/>
        <source>越短越跟手，CPU 占用略高</source>
        <translation>短いほど反応が速くなりますが、CPU 使用率はわずかに上がります</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="108"/>
        <source>开发专用</source>
        <translation>開発専用</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="113"/>
        <source>开发中水印</source>
        <translation>開発版ウォーターマーク</translation>
    </message>
    <message>
        <location filename="../ui/DebugWindow.qml" line="114"/>
        <source>每个窗口左下角的「开发中版本」角标；改动在重启后生效</source>
        <translation>各ウィンドウ左下の「開発版」バッジです。変更は再起動後に有効になります</translation>
    </message>
</context>
<context>
    <name>DevWatermark</name>
    <message>
        <location filename="../ui/DevWatermark.qml" line="40"/>
        <source>开发中版本，不代表最终品质</source>
        <translation>開発中のバージョンです。最終品質を表すものではありません</translation>
    </message>
</context>
<context>
    <name>EditorZoomBar</name>
    <message>
        <location filename="../ui/Luminalium/EditorZoomBar.qml" line="183"/>
        <source>自动适应</source>
        <translation>自動フィット</translation>
    </message>
    <message>
        <location filename="../ui/Luminalium/EditorZoomBar.qml" line="183"/>
        <source>手动档位</source>
        <translation>手動ズーム</translation>
    </message>
</context>
<context>
    <name>Home</name>
    <message>
        <location filename="../ui/settings/Home.qml" line="26"/>
        <source>主页</source>
        <translation>ホーム</translation>
    </message>
</context>
<context>
    <name>Index</name>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="31"/>
        <source>通用</source>
        <translation>全般</translation>
    </message>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="37"/>
        <source>快捷面板</source>
        <translation>クイックパネル</translation>
    </message>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="42"/>
        <source>快捷方式锁定</source>
        <translation>ショートカットのロック</translation>
    </message>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="43"/>
        <source>锁定后面板上的「编辑」按钮消失，防止误改</source>
        <translation>ロックするとパネルの「編集」ボタンが消え、誤操作を防げます</translation>
    </message>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="62"/>
        <source>语言</source>
        <translation>言語</translation>
    </message>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="67"/>
        <source>界面语言</source>
        <translation>UI 言語</translation>
    </message>
    <message>
        <location filename="../ui/settings/General/Index.qml" line="68"/>
        <source>切换后需要重新加载应用</source>
        <translation>変更後、アプリの再起動が必要です</translation>
    </message>
</context>
<context>
    <name>MainInterface</name>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="30"/>
        <source>主界面</source>
        <translation>メイン画面</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="86"/>
        <source>编辑主界面的新方式</source>
        <translation>メイン画面を編集する新しい方法</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="91"/>
        <source>右键托盘图标或唤出快捷面板，点「主界面编辑器」即可体验：
点击任意组件聚焦放大，右侧面板里调整它的设置。</source>
        <translation>トレイアイコンを右クリックするか、クイックパネルから「メイン画面エディター」を開いてください：
任意のコンポーネントをクリックしてフォーカスし、右側のパネルで設定を調整できます。</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="101"/>
        <source>打开主界面编辑器</source>
        <translation>メイン画面エディターを開く</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="117"/>
        <source>位置</source>
        <translation>位置</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="124"/>
        <source>水平边距</source>
        <translation>水平マージン</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="125"/>
        <source>控制条距屏幕左右边缘的距离</source>
        <translation>コントロールバーと画面の左右の端との距離</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="146"/>
        <source>垂直边距</source>
        <translation>垂直マージン</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="147"/>
        <source>控制条距屏幕上下边缘的距离，以整屏边缘为准</source>
        <translation>コントロールバーと画面の上下の端との距離（画面全体の端が基準）</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="166"/>
        <source>目标显示器</source>
        <translation>対象ディスプレイ</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="167"/>
        <source>控制条跟着放映窗口走，还是固定在主显示器上</source>
        <translation>コントロールバーをスライドショーウィンドウに追従させるか、メインディスプレイに固定するか</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="172"/>
        <source>跟随放映窗口</source>
        <translation>スライドショーに追従</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="172"/>
        <source>主显示器</source>
        <translation>メインディスプレイ</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="183"/>
        <source>外观</source>
        <translation>外観</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="190"/>
        <source>底板不透明度</source>
        <translation>パネルの不透明度</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="191"/>
        <source>越透明，放映画面透出来越多，边缘高光也越明显</source>
        <translation>透明度が高いほどスライドショーが透けて見え、縁のハイライトも際立ちます</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="211"/>
        <source>阴影</source>
        <translation>影</translation>
    </message>
    <message>
        <location filename="../ui/settings/MainInterface.qml" line="212"/>
        <source>底板下方的柔和投影；纯色背景下关掉更清爽</source>
        <translation>パネルの下に柔らかい影を落とします。無地の背景ではオフのほうがすっきりします</translation>
    </message>
</context>
<context>
    <name>MainInterfaceEditor</name>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="103"/>
        <source>主界面编辑器</source>
        <translation>メイン画面エディター</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="260"/>
        <source>屏幕左下角</source>
        <translation>画面左下</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="261"/>
        <source>屏幕底边居中</source>
        <translation>画面下中央</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="262"/>
        <source>屏幕右下角</source>
        <translation>画面右下</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="263"/>
        <source>屏幕左上角</source>
        <translation>画面左上</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="264"/>
        <source>屏幕顶边居中</source>
        <translation>画面上中央</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="265"/>
        <source>屏幕右上角</source>
        <translation>画面右上</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="266"/>
        <source>屏幕左侧垂直居中</source>
        <translation>画面左・垂直中央</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="267"/>
        <source>屏幕右侧垂直居中</source>
        <translation>画面右・垂直中央</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="339"/>
        <location filename="../ui/MainInterfaceEditor.qml" line="345"/>
        <location filename="../ui/MainInterfaceEditor.qml" line="351"/>
        <source>翻页组件</source>
        <translation>スライド送り</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="343"/>
        <source>工具栏</source>
        <translation>ツールバー</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="346"/>
        <source>控制条</source>
        <translation>コントロールバー</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1283"/>
        <source>显示按钮文本</source>
        <translation>ボタンテキストを表示</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1288"/>
        <source>开</source>
        <translation>オン</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1289"/>
        <source>关</source>
        <translation>オフ</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1311"/>
        <source>退出键样式</source>
        <translation>終了ボタンのスタイル</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1316"/>
        <source>白色</source>
        <translation>白</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1316"/>
        <source>红色（Luminalium 1）</source>
        <translation>赤（Luminalium 1）</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1349"/>
        <source>翻页组件位置</source>
        <translation>スライド送りの位置</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1354"/>
        <source>竖版两侧中间</source>
        <translation>画面左右・垂直中央</translation>
    </message>
    <message>
        <location filename="../ui/MainInterfaceEditor.qml" line="1363"/>
        <source>横版两侧下部</source>
        <translation>画面左右・下部</translation>
    </message>
</context>
<context>
    <name>PenPaletteCard</name>
    <message>
        <location filename="../ui/presentation/PenPaletteCard.qml" line="66"/>
        <source>颜色</source>
        <translation>色</translation>
    </message>
    <message>
        <location filename="../ui/presentation/PenPaletteCard.qml" line="67"/>
        <source>预览</source>
        <translation>プレビュー</translation>
    </message>
</context>
<context>
    <name>Personalization</name>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="30"/>
        <source>个性化</source>
        <translation>パーソナライズ</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="36"/>
        <source>外观</source>
        <translation>外観</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="43"/>
        <source>应用主题</source>
        <translation>アプリのテーマ</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="44"/>
        <source>影响所有窗口与控件的取色</source>
        <translation>すべてのウィンドウとコントロールの配色に影響します</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="49"/>
        <source>跟随系统</source>
        <translation>システムに従う</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="49"/>
        <source>浅色</source>
        <translation>ライト</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="49"/>
        <source>深色</source>
        <translation>ダーク</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="64"/>
        <source>强调色</source>
        <translation>アクセントカラー</translation>
    </message>
    <message>
        <location filename="../ui/settings/Personalization.qml" line="65"/>
        <source>按钮、开关、选中态统一使用这个颜色</source>
        <translation>ボタン・スイッチ・選択状態に共通で使われる色です</translation>
    </message>
</context>
<context>
    <name>PresentationDock</name>
    <message>
        <location filename="../ui/presentation/PresentationDock.qml" line="146"/>
        <source>更多操作</source>
        <translation>その他の操作</translation>
    </message>
    <message>
        <location filename="../ui/presentation/PresentationDock.qml" line="154"/>
        <source>退出放映</source>
        <translation>スライドショーの終了</translation>
    </message>
    <message>
        <location filename="../ui/presentation/PresentationDock.qml" line="427"/>
        <source>上一页</source>
        <translation>前のスライド</translation>
    </message>
    <message>
        <location filename="../ui/presentation/PresentationDock.qml" line="450"/>
        <source>下一页</source>
        <translation>次のスライド</translation>
    </message>
</context>
<context>
    <name>QuickPanel</name>
    <message>
        <location filename="../ui/QuickPanel.qml" line="220"/>
        <source>添加快捷方式</source>
        <translation>ショートカットを追加</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel.qml" line="227"/>
        <source>关闭</source>
        <translation>閉じる</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel.qml" line="237"/>
        <source>都加上了</source>
        <translation>すべて追加済みです</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel.qml" line="238"/>
        <source>所有可用的快捷方式都已经在面板里。</source>
        <translation>追加できるショートカットはすべてパネルにあります。</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel.qml" line="260"/>
        <source>添加</source>
        <translation>追加</translation>
    </message>
</context>
<context>
    <name>SectionHeader</name>
    <message>
        <location filename="../ui/QuickPanel/SectionHeader.qml" line="46"/>
        <source>添加</source>
        <translation>追加</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel/SectionHeader.qml" line="55"/>
        <source>完成</source>
        <translation>完了</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel/SectionHeader.qml" line="55"/>
        <source>编辑</source>
        <translation>編集</translation>
    </message>
</context>
<context>
    <name>Settings</name>
    <message>
        <location filename="../ui/Settings.qml" line="48"/>
        <source>设置</source>
        <translation>設定</translation>
    </message>
    <message>
        <location filename="../ui/Settings.qml" line="101"/>
        <source>主页</source>
        <translation>ホーム</translation>
    </message>
    <message>
        <location filename="../ui/Settings.qml" line="110"/>
        <source>通用</source>
        <translation>全般</translation>
    </message>
    <message>
        <location filename="../ui/Settings.qml" line="119"/>
        <source>个性化</source>
        <translation>パーソナライズ</translation>
    </message>
    <message>
        <location filename="../ui/Settings.qml" line="128"/>
        <source>主界面</source>
        <translation>メイン画面</translation>
    </message>
    <message>
        <location filename="../ui/Settings.qml" line="133"/>
        <source>关于</source>
        <translation>バージョン情報</translation>
    </message>
    <message>
        <location filename="../ui/Settings.qml" line="139"/>
        <source>更新</source>
        <translation>更新</translation>
    </message>
</context>
<context>
    <name>SidePager</name>
    <message>
        <location filename="../ui/presentation/SidePager.qml" line="145"/>
        <source>上一页</source>
        <translation>前のスライド</translation>
    </message>
    <message>
        <location filename="../ui/presentation/SidePager.qml" line="187"/>
        <source>下一页</source>
        <translation>次のスライド</translation>
    </message>
</context>
<context>
    <name>SplashWindow</name>
    <message>
        <location filename="../ui/SplashWindow.qml" line="52"/>
        <source>Luminalium</source>
        <translation>Luminalium</translation>
    </message>
    <message>
        <location filename="../ui/SplashWindow.qml" line="262"/>
        <source>正在启动</source>
        <translation>起動中</translation>
    </message>
</context>
<context>
    <name>TopWindow</name>
    <message>
        <location filename="../ui/presentation/TopWindow.qml" line="36"/>
        <source>顶层窗口</source>
        <translation>トップレベルウィンドウ</translation>
    </message>
</context>
<context>
    <name>TrayShortcuts</name>
    <message>
        <location filename="../ui/QuickPanel/TrayShortcuts.qml" line="41"/>
        <source>快捷方式</source>
        <translation>ショートカット</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel/TrayShortcuts.qml" line="55"/>
        <source>还没有快捷方式</source>
        <translation>ショートカットはまだありません</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel/TrayShortcuts.qml" line="56"/>
        <source>点标题栏的「+」添加。</source>
        <translation>タイトルバーの「+」から追加できます。</translation>
    </message>
    <message>
        <location filename="../ui/QuickPanel/TrayShortcuts.qml" line="131"/>
        <source>移除</source>
        <translation>削除</translation>
    </message>
</context>
<context>
    <name>Update</name>
    <message>
        <location filename="../ui/settings/Update.qml" line="14"/>
        <source>检查更新</source>
        <translation>更新プログラムの確認</translation>
    </message>
</context>
</TS>
