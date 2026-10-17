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
<TS version="2.1" language="ko_KR">

<context>
    <name>Splash</name>
    <message>
        <source>初始化</source>
        <translation>준비 중</translation>
    </message>
    <message>
        <source>创建托盘图标</source>
        <translation>트레이 아이콘 만들기</translation>
    </message>
    <message>
        <source>启动放映探测</source>
        <translation>프레젠테이션 감지 시작</translation>
    </message>
    <message>
        <source>就绪</source>
        <translation>준비 완료</translation>
    </message>
    <message>
        <source>正在进行启动后操作</source>
        <translation>시작 뒤 작업을 하는 중</translation>
    </message>
</context>
<context>
    <name>Tray</name>
    <message>
        <source>打开快捷面板</source>
        <translation>퀵 패널 열기</translation>
    </message>
    <message>
        <source>设置</source>
        <translation>설정</translation>
    </message>
    <message>
        <source>显示/隐藏放映控制条（手动）</source>
        <translation>프레젠테이션 컨트롤 바 보이기/숨기기(직접)</translation>
    </message>
    <message>
        <source>诊断信息（写入日志）</source>
        <translation>진단 정보(로그에 기록)</translation>
    </message>
    <message>
        <source>退出</source>
        <translation>끝내기</translation>
    </message>
</context>
<context>
    <name>Overflow</name>
    <message>
        <source>上一页</source>
        <translation>이전 페이지</translation>
    </message>
    <message>
        <source>下一页</source>
        <translation>다음 페이지</translation>
    </message>
    <message>
        <source>退出放映</source>
        <translation>프레젠테이션 끝내기</translation>
    </message>
</context>
<context>
    <name>App</name>
    <message>
        <source>诊断信息</source>
        <translation>진단 정보</translation>
    </message>
    <message>
        <source>已写入 logs/luminalium.log</source>
        <translation>logs/luminalium.log에 기록했습니다</translation>
    </message>
</context>
<context>
    <name>ErrorHandler</name>
    <message>
        <source>崩溃报告</source>
        <translation>크래시 보고</translation>
    </message>
    <message>
        <source>错误报告</source>
        <translation>오류 보고</translation>
    </message>
    <message>
        <source>程序崩溃了！</source>
        <translation>프로그램이 멈췄습니다!</translation>
    </message>
    <message>
        <source>程序出现了一个错误！</source>
        <translation>프로그램에 오류가 생겼습니다!</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个自己无法恢复的问题，不得不停下来。你可以尝试重新启动；如果它反复出现，请把下面的详细信息反馈给我们。</source>
        <translation>{app_name}이(가) 스스로 복구할 수 없는 문제를 만나 멈춰야 했습니다. 다시 시작해 볼 수 있습니다. 계속 반복된다면 아래 자세한 정보를 알려 주세요.</translation>
    </message>
    <message>
        <source>{app_name} 遇到了一个问题。程序还可以继续运行，但最好把下面的详细信息反馈给我们，方便我们修掉它。</source>
        <translation>{app_name}에 문제가 생겼습니다. 프로그램은 계속 돌아가지만, 고칠 수 있도록 아래 자세한 정보를 알려 주세요.</translation>
    </message>
    <message>
        <source>主线程</source>
        <translation>주 스레드</translation>
    </message>
    <message>
        <source>后台线程</source>
        <translation>백그라운드 스레드</translation>
    </message>
    <message>
        <source>线程 {name}</source>
        <translation>스레드 {name}</translation>
    </message>
    <message>
        <source>环境信息</source>
        <translation>환경 정보</translation>
    </message>
    <message>
        <source>应用版本</source>
        <translation>앱 버전</translation>
    </message>
    <message>
        <source>报告类型</source>
        <translation>보고 종류</translation>
    </message>
    <message>
        <source>发生时间</source>
        <translation>발생 시각</translation>
    </message>
    <message>
        <source>来源</source>
        <translation>출처</translation>
    </message>
    <message>
        <source>操作系统</source>
        <translation>운영 체제</translation>
    </message>
    <message>
        <source>摘要</source>
        <translation>요약</translation>
    </message>
    <message>
        <source>堆栈</source>
        <translation>스택</translation>
    </message>
    <message>
        <source>未知</source>
        <translation>알 수 없음</translation>
    </message>
    <message>
        <source>(无)</source>
        <translation>(없음)</translation>
    </message>
    <message>
        <source>RuntimeError: 这是一条手动触发的错误报告</source>
        <translation>RuntimeError: 직접 실행한 오류 보고입니다</translation>
    </message>
    <message>
        <source>这条报告来自调试窗口的「手动报错」，程序本身并没有出错。
用途：核对错误报告窗的版式、表情图与主按钮（忽略）。</source>
        <translation>이 보고는 디버그 창의 '오류 보고 실행'에서 온 것이며 프로그램 자체는 문제가 없습니다.
쓰임새: 오류 보고 창의 배치, 그림, 기본 버튼(무시)을 확인하는 용도.</translation>
    </message>
</context>
<context>
    <name>Plugins</name>
    
    <message>
        <source>演示插件</source>
        <translation>데모 플러그인</translation>
    </message>
<message><source>选择插件文件夹</source><translation>플러그인 폴더 고르기</translation></message><message><source>选择插件包</source><translation>플러그인 꾸러미 고르기</translation></message><message><source>插件包 (*.zip);;所有文件 (*)</source><translation>플러그인 꾸러미 (*.zip);;모든 파일 (*)</translation></message></context>
<context>
    <name>Settings</name>
    
    <message>
        <source>主页</source>
        <translation>홈</translation>
    </message>
    <message>
        <source>通用</source>
        <translation>일반</translation>
    </message>
    <message>
        <source>个性化</source>
        <translation>개인 설정</translation>
    </message>
    <message>
        <source>主界面</source>
        <translation>메인 화면</translation>
    </message>
    <message>
        <source>墨迹和批注</source>
        <translation>잉크와 주석</translation>
    </message>
    <message>
        
        <source>插件</source>
        <translation>플러그인</translation>
    </message>
    <message>
        <source>关于</source>
        <translation>정보</translation>
    </message>
    <message>
        <source>更新</source>
        <translation>업데이트</translation>
    </message>
</context>
<context><name>timer_l1</name><message><source>计时器（Luminalium 1）</source><translation>타이머 (Luminalium 1)</translation></message><message><source>计时器</source><translation>타이머</translation></message><message><source>打开 / 收起计时器</source><translation>타이머 열기 / 접기</translation></message></context><context><name>blackboard</name><message><source>小黑板</source><translation>미니 칠판</translation></message><message><source>打开 / 收起小黑板</source><translation>미니 칠판 열기 / 접기</translation></message></context><context><name>spotlight</name><message><source>聚光灯</source><translation>스포트라이트</translation></message><message><source>开启 / 关闭聚光灯遮罩</source><translation>스포트라이트 가림막 켜기 / 끄기</translation></message><message><source>聚光灯遮罩</source><translation>스포트라이트 가림막</translation></message></context></TS>