"""开发用：端到端自检。

不依赖 PowerPoint，直接注入一个假的放映状态来验证：

1. 托盘可用
2. 快捷面板能显示，且按**光标位置**摆放并夹取在屏幕内
3. 放映控制条能按角落显示 / 隐藏，且位置贴角（工具栏下中；翻页栏
   按配置在屏幕两侧垂直居中（竖版）或左下 / 右下（横版））；遮罩的几何
   跟着**放映窗口**走、放映窗口不在前台时**临时隐去**（2026-10-06 用户指令）
4. 设置窗口（懒创建）能打开、**默认尺寸够大且更宽**（0.64 / 0.68，按真机屏幕
   复算公式）、居中且在屏幕内；调试窗口（隐藏入口 = 设置标题
   连点 10 次）的热区盖得住标题文本、点够次数能开、与设置窗口并排不重叠
5. 快捷方式增删 / 排序与设置项读写能落回配置；「通用」页的**「托盘」整组与
   「失去焦点时收起」已按用户指令删除**（2026-10-01 第二轮：「托盘整组连着相关的
   逻辑和代码一块删掉」/「失焦收起作为默认行为」），且覆盖 UI / ``SETTING_PATHS`` /
   默认配置 / 源码残留四层守卫
5b. 设置页**增减**（2026-10-01 第四轮用户指令：「把外观那一块除了界面语言改到新的
   个性化 / 删除放映设置页面」；2026-10-06 又一轮：「把应用是跟随系统还是亮色
   暗色移到通用，个性化先只留强调色」）：「应用主题」最终落在**「通用」页**
   （含卡内下拉、选中项跟着配置走），「个性化」页只剩「强调色」一张卡
   （含 8 个色板圆点 + 当前色标记）；「通用」页共 4 张卡；
   「放映」页**整页删除** —— 导航层 / 页面层 / 文件层 / 源码残留四层守卫；
   快捷方式目录里的 ``presentation`` 项随页面一起删（否则成了死链）
5c. 「通用 → 启动 → 开机自启」（2026-10-04 用户指令：「打开之后程序会随操作系统
   启动而启动，关闭也必须有效无误」）：卡与开关在、开关回显的是**注册表实际状态**
   （不是 ``config.json`` 里的影子值）、``SETTING_PATHS`` 里有 ``autostart``；
   并且**真的开关一次本机注册表** —— 开 → ``HKCU\\...\\Run`` 里出现 ``Luminalium2``
   且命令行指向本工程入口；关 → 那个值**被删掉**（不是写空串）；再真实鼠标点一下
   开关，证明 QML ``onToggled`` 真接上了后端。⚠️ 动的是开发机真实注册表，测完
   原样还原（``_restore_run_value``）并断言无副作用
6. 配置读取与日志写入正常
7. 启动画面（设计稿还原）：按 2984:1679 比例居中、无标题栏且**刻意不登记 RinUI**、
   各元素落在设计稿位置（按 ``k = 宽/2984`` 缩放）、描边贴住外沿、进度填充与
   淡出后的回收
8. 主界面编辑器（独立窗口）：懒创建、能从快捷面板的快捷方式派发打开、
   交给 RinUI 管、只隐藏不销毁；设置导航里「外观」已改名「主界面」，
   且「主界面」页里有推广卡「编辑主界面的新方式」（左图 + 右文 + 右下按钮，
   按钮能真的把编辑器叫起来）；「主界面」页的「缩放大小」滑块（2026-10-05
   用户指令）能把顶层窗口里的组件按倍率放大 / 缩小（``presentation.scale``）
9. 编辑器的**顶层窗口预览舞台**：舞台平面 = 放映显示器 1:1 坐标系、外框跟着
   相机、控制条副本与配置里启用的角落一一对应且位置与
   ``windows.py::_position_dock`` 同源、预览层有鼠标屏蔽、亚克力已打到窗口
   句柄上、标题栏有不透明底板
10. 编辑器的**编辑态**（2026-10-01 用户指令）：默认全景（整屏等比 + 面板收起）、
   点中一条控制条 → 聚焦放大并居中 / **面板左边整块**压暗罩（铺满、不留一圈
   亚克力）/ 选中项套强调色描边 / 右侧滑出**实色**设置面板并挤窄舞台（组件信息
   **常驻在下部**，其余留给设置项）、手动档位与平移钳制、退出后回到全景；
   设置项跟着组件走（工具栏 = 显示按钮文本；翻页组件 = 翻页组件位置，竖版两侧
   中间 / 横版两侧下部二选一，切形态时预览与真机一起换、编辑对象跟着挪）；
   设置项区是**平铺**版式（名称独占一行、控件排在下面，一个 ``SettingCard`` 都没有
   —— 2026-10-01 第五轮用户指令 + Win11 截屏）；缩放缓是预览区**右上角**的浮出层
   （圆角矩形、不是药丸 —— 第六 / 七轮用户指令）；面板的**细边全员可见且按主题翻**
   （第七轮用户指令「暗色模式适配有点问题」查出来的：黑基描边压在深色面板上会消失）
11. 设置页「关于」的**流光英雄区**（L1 同款）：英雄区高 320、Logo 四层齐全、
    **页面不带大标题**（头部塌成 0）、流光的自转**真的在动**（⚠️ ``RotationAnimator``
    在本环境静默失效）、呼吸缩放落在 1.0~1.1、Logo 星心亮度贴近 L1 参考图
    （拦 ``DropShadow`` 重复绘制）
12. 设置页「关于」的**应用信息卡**（照 Class Widgets 2 的关于页主卡做的）：
    卡在、右栏徽章 = ``Backend.appChannel`` 且版本行含 ``devCodename``、三条内容
    项（仓库 / 反馈 / 依赖）齐全并默认展开、**「开源许可」项已按用户指令删掉**、
    **仓库地址在打开按钮左边且是等宽字体**、**依赖与参考的标题与链接同列上下排**
    （后两条是用户指定的版式，改错了截图未必看得出）
13. 设置页「关于」的**回声洞**（照 L1 ``#echo-cave-item`` 复刻的有状态机交互）：
    初始提示语且「复制」藏着 → 点击进「获取中...」→ 后端异步取句 → **打字机**
    逐字打完（50ms/字）后「复制」才出现 → 点「复制」把**完整句子**送进剪贴板
    （不是中途前缀）。⚠️ 走的是真实入口（MouseArea → requestSentence），不是
    直接调函数 —— 否则验不到「复制按钮压在 MouseArea 上」的层级。
    等取句的预算给到 15s：本环境下**进程内第一次**网络调用会被拖住几秒，而那笔
    一次性开销记在第一个碰网络的线程头上（正好是取句线程）。``echo_cave.warm_up()``
    已在启动时把大头提前结掉，这里再留余量防慢机器 / 沙箱假失败
14. 设置页「关于」的**诊断信息**（ClassIsland 那版：独立一张卡 + 只读文本框弹窗）：
    入口是**页面上的独立 ``SettingCard``**（自带 chevron，且**不得**再挂在
    ``aboutAppCard`` 里 —— 2026-10-04 用户指令「移出程序信息那一栏」）→ 点开是
    ``Rin.Dialog``，有「加载中...」态（验标签与 ``dialog.loading`` 的绑定，不去抢
    那几十毫秒的窗口）→ 正文是**只读多行文本框**（2026-10-04 用户指令「dialog
    内套文本框」；必须是 ``Rin.ScrollableTextArea`` —— ``Rin.TextArea`` 不会滚，
    用户指令「滚不动」），``readOnly`` 且 ``enabled`` 仍为真，``contentItem`` 是
    内容溢出的 ``Flickable``（写 ``contentY`` 认账才算「能滚」），
    内容 = 采集到的 ``Key: Value`` 逐行、条数与字段数一致、含 ``AppVersion`` →
    对话框比 RinUI 默认上限 600 更宽（用户指令「宽度不够宽」）→
    footer 是 RinUI 的**标准底栏 ``Rin.DialogButtonBox``**（2026-10-04 用户指令
    「RinUI 的 dialog 是有标准样式的」；裸 ``RowLayout`` 不算），里面的
    「复制全部」复制出同一份文本（**与文本框逐字一致**）且按钮回显「已复制」→
    **等它真的关掉**（模态遮罩不撤会吃掉后面「真鼠标点击」那几项）。
    文本口径与 ClassIsland ``GetDiagnosticInfo()`` 对齐（2026-10-04 用户指令
    「内容也和 ClassIsland 的那种诊断信息统一」）：**英文 PascalCase 键 + 原始值，
    不做中文映射** —— 所以这里断言的是 ``SystemOsVersion: `` 这种行，而不是
    旧版的「系统类型: 」。
    ⚠️ 对话框本体是 ``QQC2.Popup``（QObject 而非 Item），必须按 QObject 树找，
    且要从**窗口**往下找（``contentItem`` 那条链上没有 QML 对象）；
    ``property var`` 读回来是 ``QJSValue``，要过 ``_js_list`` 才能当 list 用
15. 设置窗口标题栏的**版本号**（2026-10-04 用户指令「在设置的三大键左侧显示程序
    的版本号」）：挂在 ``titleBarHost``（RinUI ``TitleBar`` 里那块 ``fillWidth``
    的中间区，夹在导航标题与三个窗口按钮之间），文案 = ``Backend.appVersion``，
    几何上必须落在三个 ``CtrlBtn`` 的**左边**（按钮本身没有 objectName，按类名
    找），    且**不得越过 ``titleBarHost`` 的右缘** —— 那块带 ``clip: true``，
    负的 ``rightMargin`` 会把版本号裁成 ``26.0`` 半截
16. 插件断言组（2026-10-06 插件系统计划 Wave 4 任务 13，9 项）：铁律直测 /
    夹具磁贴 / 夹具 dock 动作 / 夹具设置页 / 夹具编辑器组 / 故障隔离 /
    孤儿容忍 / 禁用过滤 / 依赖断言。**全部跑在子进程**（本脚本
    ``--plugin-scenario`` 模式 + 临时用户配置），主进程保持 ``app.debug``
    关，既有 15 项断言零改动也零回归。**清理责任**：每个场景的临时配置
    目录用完 ``rmtree``；故障隔离注入的坏插件 ``app/plugins/_smoke_bad/``
    用完必须整目录删除（含 ``__pycache__``，留在盘上会被调试插件发现
    机制当成常驻插件）；铁律的白名单键 ``plugins._demo.note`` 只落在
    临时配置里，真 ``config/config.json`` 全程不被碰。详见下方
    「插件断言组」一节的注释。

用法::

    .venv\\Scripts\\python.exe tools\\smoke.py

内部入口（插件断言组用，正常人别直接调）::

    .venv\\Scripts\\python.exe -X utf8 tools\\smoke.py --plugin-scenario <场景名>
    .venv\\Scripts\\python.exe tools\\smoke.py --self-test   # 离线自检（不开窗口）
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import (  # noqa: E402
    Q_ARG,
    QMetaObject,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QTimer,
    qInstallMessageHandler,
)
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtGui import QColor, QCursor, QGuiApplication  # noqa: E402

import app.config as app_config  # noqa: E402
import app.paths as app_paths  # noqa: E402
from app import ppt_controller  # noqa: E402
from app import autostart  # noqa: E402
# 模块本身也要（遮罩「智能跟随」自检要临时替换模块里的 ``_foreground_window``）
from app import windows as win_mod  # noqa: E402
from app.application import LuminaliumApplication  # noqa: E402
from app.bridge import SETTING_PATHS  # noqa: E402
from app.paths import DEFAULT_CONFIG_FILE  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402
from app.windows import CORNERS, _dwm_cloaked  # noqa: E402

RESULTS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")


def _hex(value) -> str:
    """把 QML 回来的颜色统一成 ``#RRGGBB``（大写）。

    ⚠️ QML 里声明成 ``property color`` 的东西，经 PySide 取回来是 **QColor**，
    ``str()`` 出来长这样：``PySide6.QtGui.QColor.fromRgbF(1.000000, ...)`` ——
    直接与 ``"#FFC000"`` 比会**恒不相等**（看着像「点击没生效」，其实是字符串
    形态不对）。所以比对颜色一律先过这里。
    """
    if value is None:
        return ""
    try:
        name = QColor(value).name()  # QColor(QColor) 是拷贝构造，也吃字符串
    except (TypeError, ValueError):
        return str(value).upper()
    return name.upper() if name.startswith("#") else str(value).upper()


# ------------------------------------------------------------------ 启动画面

def _find_named(item, name):
    """在 QQuickItem 树里按 objectName 找一项（QML 的 Item 不是 QObject 子对象链的正规成员，
    所以用 ``childItems()`` 递归比 ``findChild`` 稳）。"""
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _find_named(child, name)
        if found is not None:
            return found
    return None


def _segment_current_index(dock):
    """读工具分段当前选中页（走 dock 上的镜像属性 ``segmentCurrentIndex``）。

    ⚠️ QML 那边挂了一份镜像到根 Item 上（见 ``PresentationDock``）。

    ⚠️⚠️ **别写 ``property(...) or -1``**：``0 or -1`` 在 Python 里是 ``-1``
    （``0`` 是 falsy）—— 分段选中第 0 页时会被读成 -1，断言变成恒成立的假绿。
    必须显式判``None``。
    """
    value = dock.property("segmentCurrentIndex")
    return -1 if value is None else int(value)


def _wait_named(item, name: str, timeout_ms: int = 4000, step_ms: int = 50):
    """轮询等一项出现（超时返回 ``None``）。

    ⚠️ 为什么必须轮询而不是 ``qWait`` 固定时长：RinUI 的
    ``NavigationView.push`` 是**异步**的（内部 ``stackView.replace`` + 转场，
    且被 ``pushInProgress`` 串行化）。窗口刚 ``show()`` 时初始页（Home）的转场
    还没跑完，后面的 push 会一直挂在 ``Qt.callLater`` 重试队列里 —— 实测要
    **0.6~2s** 才落地（视窗先稳定一拍再 push 会快很多）。钉死 500ms 会随机
    假失败：症状是「页面整个不存在」，看着像 QML 崩了，其实只是还没切过去。
    """
    waited = 0
    while waited <= timeout_ms:
        found = _find_named(item, name)
        if found is not None:
            return found
        QTest.qWait(step_ms)
        waited += step_ms
    return None


def _find_object(root, name: str):
    """在 **QObject** 树里按 ``objectName`` 找对象（含 ``Popup`` 这类非 Item）。

    ⚠️ 为什么不能只用 :func:`_find_named`：``Rin.Dialog`` 底子是
    ``QQC2.Popup`` —— 它是 ``QObject`` 而**不是** ``QQuickItem``，不在
    ``childItems()`` 那棵树里（``_find_named`` 因此永远找不到它）。而它的
    ``contentItem`` / ``footer`` 虽然真是 Item，却被挂在窗口的 overlay 下，
    也不在页面子树里。所以对话框本体按 QObject 找，内部控件再从它的
    ``contentItem`` / ``footer`` 往下找。
    """
    if root is None:
        return None
    found = root.findChild(QObject, name)
    return found


def _wait_property(item, name: str, predicate, timeout_ms: int = 4000,
                   step_ms: int = 50):
    """轮询等某个属性满足条件，返回它最后一次读到的值（超时也返回）。

    ⚠️ ``step_ms`` 别调大。``QTest.qWait`` 会**攥着 GIL** 转（PySide6 没在它
    外面放锁），而这里等的东西有不少是**纯 Python 后台线程**的产物（诊断采集
    ``app/diagnostics.py``、回声洞取句）。步长一大，worker 就只能趁每次循环那点
    字节码间隙蹭时间片 —— 实测把步长从 50ms 调到 600ms，本机 130ms 就能采完的
    诊断信息拖到 6s+ 还没回来（``tools/scroll_probe.py`` 里留了对照）。50ms 这
    一档正好：主线程每轮松一次手，worker 攒够时间把活干完。
    """
    waited = 0
    value = None
    while waited <= timeout_ms:
        value = item.property(name)
        if predicate(value):
            return value
        QTest.qWait(step_ms)
        waited += step_ms
    return value


def _wait_position_settled(read_value, timeout_ms: int = 3000, step_ms: int = 100,
                           stable_ms: int = 300, eps: float = 2.0):
    """轮询等一个几何量（如 y）停稳，返回 ``(最后一次值, 是否沉淀)``。

    连续 ``stable_ms`` 内相邻采样 |Δ| < ``eps`` 即视为沉淀；超时返回最后一次
    读到的值（调用方负责在输出里注明「沉淀等待超时」）。

    ⚠️ 为什么需要它（2026-10-05 banner y 竞态）：``paintedWidth > 0`` 只说明
    图画出来了，**不代表布局停稳** —— 页面入场转场还在跑时 y 一直在动，一等
    paintedWidth 就量会拿到动画中间态（同代码同机四次量出 267/313/366/385）。
    ``step_ms`` 保持 100：与 ``_wait_property`` 同理，``QTest.qWait`` 攥着
    GIL，步长再大会饿死纯 Python 后台线程。
    """
    waited = 0
    stable = 0
    last = read_value()
    while waited < timeout_ms:
        QTest.qWait(step_ms)
        waited += step_ms
        value = read_value()
        if abs(value - last) < eps:
            stable += step_ms
            if stable >= stable_ms:
                return value, True
        else:
            stable = 0
        last = value
    return last, False


def _wait_text(item, expected: str, timeout_ms: int = 1500, step_ms: int = 20) -> bool:
    """轮询等 ``text`` 属性等于 ``expected``（用于抓一闪而过的加载态）。"""
    waited = 0
    while waited <= timeout_ms:
        if str(item.property("text")) == expected:
            return True
        QTest.qWait(step_ms)
        waited += step_ms
    return False


def _field_of(field, key: str) -> str:
    """从 QML 回传的 ``{"key":..., "value":...}`` 里取一个值（dict / 对象都认）。"""
    try:
        return str(field.get(key, ""))
    except AttributeError:
        return str(getattr(field, key, ""))


def _ancestor_named(item, name: str):
    """沿 ``parentItem()`` 往上找第一个 ``objectName`` 命中的祖先（含自身）。

    用来验**结构归属**：「某项必须 / 不得挂在某张卡里面」这种断言只看
    ``_find_named`` 是不够的 —— 它在树里找得到，但看不出来是挂在谁下面。
    """
    node = item
    while node is not None:
        if node.objectName() == name:
            return node
        node = node.parentItem()
    return None


def _js_list(value):
    """把 QML ``property var`` 读回来的东西统一成 Python ``list``。

    ⚠️ 从 QObject 上直接 ``property("fields")`` 读 ``property var`` 拿到的是
    **``QJSValue``**（不是 list、也不是 dict），直接 ``list()`` 会抛
    ``TypeError: QJSValue object is not iterable``；``bool()`` 更糟 —— 它对任何
    QJSValue 都返回 True，看着像「已经拿到数据了」，其实是空的。必须先
    ``toVariant()`` 转成 Python 对象再判断。
    """
    if value is None:
        return []
    to_variant = getattr(value, "toVariant", None)
    if callable(to_variant):
        try:
            value = to_variant()
        except Exception:  # noqa: BLE001 - 转不动就当作空
            return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _collect_named(item, prefix: str):
    """收集树里所有 objectName 以 ``prefix`` 开头的项（按前缀找一族兄弟项）。"""
    found = []
    if item.objectName().startswith(prefix):
        found.append(item)
    for child in item.childItems():
        found.extend(_collect_named(child, prefix))
    return found


def _next_visible_right(item, reference):
    """在 ``item`` 所在的 Layout 行里找它的**右邻居**（下一个可见、有宽度的兄弟）。

    用来量「A 在 B 左边」这种版式。``Rin.SettingItem`` 的右栏是个 ``RowLayout``：
    ``item``（如仓库地址那个 ``Text``）是它的孩子，而「打开按钮」
    （``SettingItem`` 的 ``actionIcon``）是**那个 RowLayout 的兄弟**。所以先上跳
    两级，再在同一行里挑 ``x`` 落在该 RowLayout 右边缘之后、且离它最近的那个。

    ⚠️ 不能直接读 ``SettingItem.actionIcon`` —— 它是 QML 专有类型
    （``Icon_QMLTYPE_*``），Python 侧 ``property("actionIcon")`` 会抛
    ``RuntimeError: Can't find converter for 'Icon_QMLTYPE_17*'``（实测）。
    """
    if item is None or reference is None:
        return None
    row = item.parentItem()                        # 右栏 RowLayout
    line = row.parentItem() if row is not None else None   # 外层 RowLayout
    if line is None:
        return None
    edge = row.mapToItem(reference, 0, 0).x() + row.width() - 1
    best = None
    best_x = None
    for sibling in line.childItems():
        if sibling is row or not sibling.isVisible() or sibling.width() <= 0:
            continue
        sx = sibling.mapToItem(reference, 0, 0).x()
        if sx < edge:
            continue
        if best_x is None or sx < best_x:
            best, best_x = sibling, sx
    return best


def _find_text(item, text: str):
    """按 ``text`` 找一项 Text（``SettingCard`` 内部的标题 / 说明没有 objectName）。

    ⚠️ 必须过滤 ``isVisible()``：同名文案在别处也有（RinUI 的标题栏、隐藏探针），
    拿错了会让断言看着像通过。
    """
    for child in item.childItems():
        try:
            value = child.property("text")
        except (AttributeError, RuntimeError):  # pragma: no cover - 非 Text 项
            value = None
        if value == text and child.isVisible():
            return child
        found = _find_text(child, text)
        if found is not None:
            return found
    return None


def _scan_symbols(symbols, roots, skip=()):
    """在源码里扫「已删除符号」的残留引用（静态守卫，返回 ``文件:行:符号`` 列表）。

    删设置项时最容易漏的是「UI 删了、后端还在读」，或者「代码删了、引用还在」。
    只扫 ``.py`` / ``.qml`` / ``.json``，跳过 ``__pycache__`` 与 ``skip`` 里的文件
    （调用方要把**自己**排掉：待扫符号的字面量就写在调用处，否则永远自命中）。
    命中即失败，用来拦「重新加回来」。
    """
    skipped = {Path(item).resolve() for item in skip}
    hits = []
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            if (path.suffix not in (".py", ".qml", ".json")
                    or "__pycache__" in path.parts or not path.is_file()):
                continue
            if path.resolve() in skipped:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                for symbol in symbols:
                    if symbol in line:
                        hits.append(
                            f"{path.relative_to(ROOT).as_posix()}:{lineno}:{symbol}"
                        )
    return hits


def _collect_type(item, type_name: str):
    """收集树里所有**类型名**以 ``type_name`` 开头的项（如 ``SettingCard``）。

    用来验「某一页上还剩几个设置项」—— 设置项搬走 / 删除之后，光看某一项
    存不存在不够（搬走的和留下的可能重名），得看整页的数量。
    """
    found = []
    try:
        name = item.metaObject().className()
    except (AttributeError, RuntimeError):  # pragma: no cover
        name = ""
    if name.startswith(type_name):
        found.append(item)
    for child in item.childItems():
        found.extend(_collect_type(child, type_name))
    return found


def _prop(obj, path: str):
    """按 ``a.b`` 读 QML 属性（分组属性如 ``border.width`` 也支持）。"""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.property(part)
    return cur


def _run_value():
    """原样读 ``HKCU\\...\\Run`` 里的开机自启值（没有则 ``None``）。

    ⚠️ 这是**本机真实注册表**：自检里会真的开关一次开机自启，用完必须原样
    还原（见 :func:`_restore_run_value`），别把开发机的启动项改坏。
    直接读注册表而不是走 ``autostart.is_enabled()``，是为了能断言
    「关闭之后值**被删掉**了」—— ``is_enabled`` 只给一个 bool，看不出
    「值还在、只是被任务管理器禁用」这种半吊子状态。
    """
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, autostart.RUN_KEY_PATH, 0, winreg.KEY_READ
        ) as key:
            return winreg.QueryValueEx(key, autostart.VALUE_NAME)[0]
    except FileNotFoundError:
        return None


def _restore_run_value(previous) -> None:
    """把自启值还原成 ``previous``（``None`` = 本来就没有 → 删掉）。"""
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, autostart.RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
    ) as key:
        if previous is None:
            try:
                winreg.DeleteValue(key, autostart.VALUE_NAME)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, autostart.VALUE_NAME, 0, winreg.REG_SZ, previous)


def _wait_stable(key, *, timeout_ms: int = 3000, step_ms: int = 120,
                 repeat: int = 2) -> bool:
    """等 ``key()`` 的取值连续 ``repeat`` 拍不变。

    ``key`` 传一个返回可比较快照的函数（字符串最省事）。QML 的动画是级联的
    （面板挤窄舞台 → 舞台宽度变 → 聚焦比例跟着变 → 相机再动一次），死等一个
    固定时长在机器忙的时候会读到中间值；等「不变」才是稳的。返回是否稳定。
    """
    last = key()
    same = 0
    waited = 0
    while waited < timeout_ms:
        QTest.qWait(step_ms)
        waited += step_ms
        now = key()
        if now == last:
            same += 1
            if same >= repeat:
                return True
        else:
            same = 0
        last = now
    return False


#: 启动画面的**版式项**：objectName -> (x, y, w, h)，单位是设计稿原值
#: （Figma 画布 2984×1679）。QML 侧一律写这些原值再乘 ``k = 卡面宽/2984``，
#: 所以这里按同样的比例验证 —— 改了 QML 却没同步设计稿（或缩放因子被绕过）
#: 时，这条会立刻炸。``None`` = 该字段不按设计稿校验（已改走 Fluent 固定值）。
SPLASH_LAYOUT = {
    "splashLogo": (131.0, 121.0, 184.0, 184.0),
    # wordmark 宽度按**素材本身**走：现用的是 1024×114 的轮廓 SVG
    # （``resources/splash/wordmark_*.svg`` 的 viewBox，QML 侧 1023.13×113.7
    # 就是它的等比缩放）。这里原先写 727.7 —— 那是上一版素材的宽度，换素材时
    # 漏改了，这条断言因此一直失败（2026-10-01 对齐）。
    "splashWordmark": (147.3, 1176.5, 1023.13, 113.7),
    "splashArtCard": (1444.0, 121.0, 1448.0, 1438.0),
    "splashTrack": (134.0, None, 1178.0, None),
}

#: 启动画面的 **Fluent 外观项**：(objectName, 属性名, 期望值)。
#: 这些**绝不许**跟着 k 缩放 —— 设计稿的圆角 92 / 描边 7 是比例值，折算到
#: 720 宽的卡面上是 22px / 1.7px，那是 iOS 语汇不是 Fluent（2026-10-01 用户
#: 指令「比例过大了、不符合 Fluent 2 设计语言」）。谁把它们改回乘 k 就会炸。
SPLASH_FLUENT = [
    ("splashTrack", "height", 4),         # Fluent ProgressBar 规格
    ("splashTrack", "radius", 2),
]

#: 挂在**窗口**上的 Fluent 外观项：(属性名, 期望值)。
#: 卡面的圆角 / 描边放这儿，是因为 ``Rectangle.border`` 是**分组属性**、PySide
#: 侧读不到子属性（``Can't find converter for 'QQuickPen*'``），所以 QML 把它们
#: 另挂了一份在窗口上（``cardRadius`` / ``cardBorderWidth``）供这里断言。
SPLASH_WINDOW_FLUENT = [
    ("cardRadius", 8),          # WinUI OverlayCornerRadius
    ("cardBorderWidth", 1),     # Fluent 控件描边
]


def _check_splash(app) -> None:
    app.windows.show_splash()
    # 窗口里的 ``contentRoot`` / ``splashCard`` 是 **anchors.fill / 绑定**定尺寸的，
    # 要等 Qt 跑完第一轮布局才有几何 —— 不等的话它们一律读成 0x0（假失败）。
    QTest.qWait(250)
    splash = app.windows.splash
    check("启动画面已创建", splash is not None)
    if splash is None:
        return

    check("启动画面可见", splash.isVisible())

    content = splash.contentItem()
    card = _find_named(content, "splashCard")
    check("启动画面卡面存在", card is not None)
    if card is None:
        return

    # 比例：卡面高度必须由宽度按设计稿比例算出来，不能写死
    check("卡面按设计稿比例（2984:1679）",
          abs(card.height() / card.width() - 1679 / 2984) < 0.01,
          f"卡面 {card.width():.0f}x{card.height():.0f}"
          f" = {card.height() / card.width():.4f}（期望 {1679 / 2984:.4f}）")

    # 窗口 = 卡面 + 四周阴影边距（阴影得画在卡外，所以窗口比卡面大一圈）
    margin = splash.property("shadowMargin")
    check("窗口 = 卡面 + 四周阴影边距",
          abs(splash.width() - card.width() - 2 * margin) < 1.5
          and abs(splash.height() - card.height() - 2 * margin) < 1.5,
          f"窗口 {splash.width()}x{splash.height()}，"
          f"卡面 {card.width():.0f}x{card.height():.0f}，边距 {margin}")

    # 卡面必须正好落在阴影边距上、描边不能再内缩：这是「描边贴边」那条老坑的
    # 等价防线 —— 以前把 SVG 的 stroke inset 补到描边上，整条边会内移半个线宽，
    # 卡片左右下三条边整条错位（2026-10-01 踩过）。
    check("卡面贴着阴影边距、描边不再内缩",
          abs(card.x() - margin) < 0.6 and abs(card.y() - margin) < 0.6,
          f"卡面在 ({card.x():.1f},{card.y():.1f})，期望 ({margin},{margin})")

    # 居中：基准是 **availableGeometry**（避开任务栏）而不是整屏。边距四边对称，
    # 所以窗口居中 = 卡面居中。
    area = QGuiApplication.primaryScreen().availableGeometry()
    dx = abs((splash.x() + splash.width() // 2) - (area.x() + area.width() // 2))
    dy = abs((splash.y() + splash.height() // 2) - (area.y() + area.height() // 2))
    check("启动画面在可用区居中", dx <= 2 and dy <= 2, f"Δ=({dx}, {dy})")

    # 无边框 + **刻意不登记 RinUI**：登记了 RinUI 会加 WS_CAPTION 并让 DWM 画
    # 系统圆角/阴影，和这儿自绘的 Fluent 卡片打架。
    hwnd = int(splash.winId())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    check("启动画面无标题栏", not (style & 0x00C00000), f"style=0x{style:08X}")
    check("启动画面刻意不登记 RinUI（否则会被加系统边框/阴影）",
          hwnd not in {int(h) for h in app.rinui.theme_manager.windows},
          f"hwnd={hwnd}")

    # 版式：逐项按 k 验证（容差 1.5 逻辑像素）。k 从 QML 侧读，避免两边各写一份。
    k = splash.property("k")
    for name, ref in SPLASH_LAYOUT.items():
        item = _find_named(content, name)
        if item is None:
            check(f"启动画面元素 {name} 存在", False, "没找到该 objectName")
            continue
        got = (item.x(), item.y(), item.width(), item.height())
        want = tuple(v * k if v is not None else None for v in ref)
        worst = max(abs(got[i] - want[i]) for i in range(4) if want[i] is not None)
        shown = ", ".join("—" if v is None else f"{v:.1f}" for v in want)
        check(f"启动画面 {name} 落在设计稿位置", worst <= 1.5,
              f"实际 ({got[0]:.1f},{got[1]:.1f} {got[2]:.1f}x{got[3]:.1f}) "
              f"期望 ({shown})")

    # Fluent 外观项必须是**固定值**，不跟着 k 缩放
    for name, prop, want in SPLASH_FLUENT:
        item = _find_named(content, name)
        got = _prop(item, prop) if item is not None else None
        check(f"启动画面 {name}.{prop} 走 Fluent 固定值",
              got is not None and abs(float(got) - want) < 0.6,
              f"实测 {got}，期望 {want}")
    for prop, want in SPLASH_WINDOW_FLUENT:
        got = splash.property(prop)
        check(f"启动画面 {prop} 走 Fluent 固定值",
              got is not None and abs(float(got) - want) < 0.6,
              f"实测 {got}，期望 {want}")

    # 字阶同样是 Fluent 固定值，不跟着 k 缩放。层级：Title 28 → Body 14 → Caption 12。
    # （版本行一开始对齐到了 bodyLarge 18，用户 2026-10-01 反馈「版本号和开发代号
    #   那一栏的字体大小未免有点大了」→ 收到 body 14。）
    # ``font`` 是 QFont 值类型，PySide 能转；不像 ``border`` 那样是 QObject 分组属性。
    for name, want in (("splashSubtitle", 14), ("splashStageLeft", 12),
                       ("splashStageRight", 12)):
        item = _find_named(content, name)
        font = item.property("font") if item is not None else None
        got = font.pixelSize() if font is not None else None
        check(f"启动画面 {name} 字号走 Fluent 固定值", got == want,
              f"实测 {got}，期望 {want}")

    # 进度条纵向对齐设计稿那条槽的**中线**（高度换成 Fluent 的 4 了，不是顶对齐）
    track = _find_named(content, "splashTrack")
    want_cy = (1459 + 25 / 2) * k
    check("进度条纵向对齐设计稿槽位中线",
          track is not None and abs((track.y() + track.height() / 2) - want_cy) < 1.0,
          "未找到" if track is None else
          f"中线 {track.y() + track.height() / 2:.1f}，期望 {want_cy:.1f}")

    # 进度：后端推 0.6 → 填充条应约为轨道宽的 60%，右侧标签以「60%」开头
    app.backend.setSplashStage(0.60, "创建托盘图标")
    fill = _find_named(content, "splashProgressFill")
    if fill is not None and track is not None and track.width() > 0:
        # 填充条带 220ms 补间，等它走完再断言
        QTest.qWait(320)
        frac = fill.width() / track.width()
        check("启动画面进度条按进度填充", abs(frac - 0.60) < 0.03, f"实测 {frac:.3f}")
    right = _find_named(content, "splashStageRight")
    check("启动画面右侧显示「百分比 + 阶段」",
          right is not None and str(right.property("text")).startswith("60%"),
          "未找到" if right is None else str(right.property("text")))

    # 生命周期：淡出结束后窗口要被**真正收掉**（那张 1717×1640 的插画常驻不划算）
    app.windows.hide_splash()
    QTest.qWait(700)
    check("启动画面淡出后被回收", app.windows.splash is None,
          "仍有残留实例" if app.windows.splash is not None else "")


# ------------------------------------------------------------ 主界面编辑器

def _check_editor(app) -> None:
    """主界面编辑器：懒创建 + 从快捷面板派发 + 交给 RinUI 管 + 只隐藏不销毁。

    2026-10-01 用户指令：「把『外观』改成『主界面』，然后新增一个『主界面编辑器』，
    你先把主界面编辑器的空窗口建出来，并且加上快捷面板的快捷方式」。
    """
    # 目录里必须真有这条，否则面板的「+」里永远不会出现它
    catalog = {
        str(item.get("id")): item
        for item in (app.config.get("quick_panel.shortcut_catalog", []) or [])
    }
    entry = catalog.get("main_editor")
    check(
        "快捷方式目录含「主界面编辑器」且动作是 open_editor",
        entry is not None and str(entry.get("action")) == "open_editor",
        "目录里没有 main_editor" if entry is None else f"action={entry.get('action')}",
    )

    # 懒创建：没点开就一个对象都不建（与设置 / 调试窗口同一条约定）
    check("主界面编辑器懒创建（未打开时不建）", app.windows.editor is None)

    # 走**真实入口**派发：快捷方式 → backend.shortcutTriggered →
    # application._on_shortcut 认 action=open_editor → windows.show_editor()
    accepted = app.backend.activateShortcut("main_editor")
    editor = app.windows.editor
    check(
        "从快捷面板的快捷方式打开主界面编辑器",
        accepted and editor is not None and editor.isVisible(),
        f"accepted={accepted} "
        + ("窗口未创建" if editor is None else f"visible={editor.isVisible()}"),
    )
    if editor is None:
        return

    # ---------------------------------------------------- 正文：顶层窗口舞台
    content_root = editor.contentItem()
    frame = _find_named(content_root, "editorScreenFrame")
    plane = _find_named(content_root, "editorScreenPlane")
    viewport = _find_named(content_root, "editorStageViewport")
    check("编辑器正文是预览舞台（占位块已撤）",
          frame is not None and plane is not None and viewport is not None
          and _find_named(content_root, "editorPlaceholder") is None,
          "屏幕外框 / 平面 / 视口 没找齐" if None in (frame, plane, viewport) else "")
    if frame is None or plane is None or viewport is None:
        app.backend.closeMainEditor()
        return

    # 相机 / 面板都是 220ms 的动画，而且是**级联**的（面板挤窄舞台 → 舞台宽度变 →
    # 聚焦比例跟着变 → 相机再动一次）。死等一个固定时长会在机器忙的时候读到动画
    # 中间值（真踩过：读到 1.743 而不是 1.783 —— 差 40ms 的行程），所以这里一律
    # 等「这一串值连续两拍不变」，比 qWait 靠谱。面板 / 暗罩还没取到时先只看相机。
    inspector = None
    dim = None

    def _camera_key() -> str:
        key = (f"{plane.x():.2f}|{plane.y():.2f}|{plane.scale():.5f}"
               f"|{viewport.width():.1f}")
        if inspector is not None:
            key += f"|{inspector.x():.1f}|{float(dim.property('opacity') or 0):.3f}"
        return key

    def _settle() -> None:
        _wait_stable(_camera_key)

    def _nudge_editor() -> None:
        """把编辑器窗口再抬起来催一次曝光。

        ⚠️ QML 的动画由**渲染循环**推进 —— 窗口没被暴露（被别的窗口盖住 / 桌面切走）
        时动画会**卡住**在中间值上，于是「值连续两拍不变」当场成立，``_settle()``
        会心满意足地返回一个**中间值**。实测偶发一次：手动档位那条读到
        ``scale=0.5989``（目标 1.0），紧接着的平移钳制读到 ``plane=(0.0,36.5)``
        （期望 ≤0.5），复跑又是全绿 —— 典型的曝光问题，不是产品坏了。
        """
        editor.raise_()
        editor.requestActivate()
        QTest.qWait(120)

    def _wait_cam(predicate, *, timeout_ms: int = 3000, step_ms: int = 120) -> bool:
        """轮询到 ``predicate()`` 成立（超时返回最后一拍的结果）。

        相机那几条**不能**只靠 ``_settle()``：它等的是「不变」，动画卡住时同样满足。
        这里等的是**目标值**，中途还会抬一次窗口催曝光（见 ``_nudge_editor``）。
        """
        waited = 0
        nudged = False
        while waited <= timeout_ms:
            if predicate():
                return True
            QTest.qWait(step_ms)
            waited += step_ms
            if not nudged and waited >= timeout_ms // 2:
                nudged = True
                _nudge_editor()
        return predicate()

    QTest.qWait(300)  # contentItem 里的绑定要等第一轮布局才拿得到几何
    _settle()

    info = app.backend.presentationScreen
    check(
        "舞台平面 = 放映显示器的 1:1 坐标系",
        int(plane.width()) == int(info["width"])
        and int(plane.height()) == int(info["height"]),
        f"plane={plane.width():.0f}x{plane.height():.0f} screen={info}",
    )

    # 全景态：整屏等比装进视口（长边贴合）。相机有三件套（比例 / 位移 / 平移偏移），
    # 这里复算的是「默认态」那一支 —— QML 里是副本，漂了两边的取景就不一样。
    fit = min(viewport.width() / info["width"], viewport.height() / info["height"])
    check(
        "默认停在全景态（没选中组件、面板收起）",
        str(editor.property("selectedCorner")) == ""
        and editor.property("editing") is False,
        f"selectedCorner={editor.property('selectedCorner')!r} "
        f"editing={editor.property('editing')}",
    )
    _wait_cam(lambda: abs(float(plane.scale()) - fit) <= 1e-3)
    scale = plane.scale()
    check(
        "全景比例 = 整屏等比装进舞台",
        abs(scale - fit) <= 1e-3,
        f"scale={scale:.4f} fit={fit:.4f}",
    )
    # 面板收起时的舞台宽度 —— 后面用它验「面板是挤窄舞台而不是浮在上面」
    stage_width_closed = viewport.width()
    check(
        "屏幕外框跟着相机走（位置与尺寸都取自平面）",
        abs(frame.x() - plane.x()) <= 1
        and abs(frame.y() - plane.y()) <= 1
        and abs(frame.width() - round(info["width"] * scale)) <= 1
        and abs(frame.height() - round(info["height"] * scale)) <= 1,
        f"frame=({frame.x():.0f},{frame.y():.0f}) {frame.width()}x{frame.height()} "
        f"plane=({plane.x():.0f},{plane.y():.0f}) scale={scale:.4f}",
    )

    # 每个 enabled 的角落都得有一只副本 —— 少一只就是「主界面」显示不全
    corner_cfg = app.config.get("presentation.corners", {}) or {}
    enabled = [n for n in CORNERS if (corner_cfg.get(n) or {}).get("enabled")]
    preview_docks = _collect_named(plane, "editorPreviewDock_")
    got = sorted(d.objectName()[len("editorPreviewDock_"):] for d in preview_docks)
    check(
        "预览里的控制条与配置里启用的角落一一对应",
        got == sorted(enabled),
        f"预览={got} 配置={sorted(enabled)}",
    )

    # 位置：与 windows.py::_position_dock **同一份公式**（含 shadowMargin 扣减、
    # 贴边基准是整屏而非工作区）。这边复算一遍是因为 QML 里那份是副本 ——
    # 两边一旦漂了，编辑器和真机摆出来的位置就不一样。
    margin_x = int(app.config.get("presentation.margin_x", 20))
    margin_y = int(app.config.get("presentation.margin_y", 20))
    worst = 0.0
    for dock in preview_docks:
        corner = dock.objectName()[len("editorPreviewDock_"):]
        align = CORNERS.get(corner)
        if align is None or dock.width() <= 0 or dock.height() <= 0:
            continue
        horizontal, vertical = align
        shadow = int(dock.property("shadowMargin") or 0)
        if horizontal == "left":
            x = margin_x - shadow
        elif horizontal == "center":
            x = round((plane.width() - dock.width()) / 2)
        else:
            x = plane.width() - dock.width() - margin_x + shadow
        if vertical == "top":
            y = margin_y - shadow
        elif vertical == "middle":
            y = round((plane.height() - dock.height()) / 2)
        else:
            y = plane.height() - dock.height() - margin_y + shadow
        worst = max(worst, abs(dock.x() - x), abs(dock.y() - y))
    check(
        "预览控制条落在角落（算法与 windows.py::_position_dock 同源）",
        worst <= 1.0,
        f"最大偏差 {worst:.2f}px",
    )

    shield = _find_named(viewport, "editorStageShield")
    check(
        "视口有鼠标屏蔽（点控制条不会真的翻页）",
        # 挂在**视口**上而不是平面上：输入坐标因此是「视口坐标」，
        # 拖动平移才不会被相机自身的位移抵消（见 QML 里的说明）。
        shield is not None
        and abs(shield.width() - viewport.width()) <= 1
        and abs(shield.height() - viewport.height()) <= 1,
        "屏蔽层没挂在视口上 / 没铺满视口" if shield is None else
        f"shield={shield.width():.0f}x{shield.height():.0f} "
        f"viewport={viewport.width():.0f}x{viewport.height():.0f}",
    )

    # ------------------------------------------------------- 编辑态：聚焦 + 面板
    # 2026-10-01 用户指令：「做『编辑态』适应 主界面编辑器的缩放，先默认就整体匹配
    # 界面的比例，点到那个组件再聚焦，然后从右侧展开居右的组件设置面板」。
    #
    # 下面这些常量**与 ui/Luminalium/Lumi.qml 的「主界面编辑器」一节同源**
    # （那边是权威），改一处要改两处。
    PANEL_W = 340
    #: 面板下部常驻条的高度（2026-10-01 第六轮：缩放缓搬走后 84 → 48）。
    PANEL_FOOTER_H = 48
    #: 面板左沿中线那枚**圆按钮**的直径（收起面板）。
    PANEL_HANDLE = 40
    #: 预览区上那枚悬浮缩放缓：底板高度 / 圆角、离视口的**视觉**距离、投影余量。
    #: 圆角 8 = Fluent 的 ``OverlayCornerRadius``（2026-10-01 第七轮用户指令
    #: 「不该是大圆角」—— 早先是 ``height / 2`` 的药丸）。
    ZOOM_BAR_H = 40
    ZOOM_BAR_RADIUS = 8
    ZOOM_BAR_MARGIN = 16
    FLOAT_SHADOW_MARGIN = 14
    FOCUS_PAD_X, FOCUS_PAD_Y = 72, 56
    FOCUS_MAX = 2.0
    ZOOM_MAX = 4.0
    DIM_OPACITY = 0.34
    DIM_HOLE_PAD = 6
    RING_WIDTH, RING_GAP = 2, 4
    # RinUI 的 ``themes/utils.qml::Utils.windowDragArea`` —— ``FluentWindowBase`` 用它
    # 把 ``contentArea`` 四周内缩，那圈是窗口的拖动 / 缩放热区，QML 内容默认盖不到。
    WINDOW_DRAG_AREA = 5

    inspector = _find_named(content_root, "editorInspectorPanel")
    footer = _find_named(content_root, "editorInspectorFooter")
    dim = _find_named(content_root, "editorDimMask")
    ring = _find_named(content_root, "editorSelectionRing")
    check(
        "舞台有暗罩 / 选中框，右侧有设置面板与下部常驻条",
        None not in (inspector, footer, dim, ring),
        f"panel={inspector is not None} footer={footer is not None} "
        f"dim={dim is not None} ring={ring is not None}",
    )
    if None in (inspector, footer, dim, ring):
        app.backend.closeMainEditor()
        return

    check(
        "全景态下面板收起、暗罩不显示",
        not inspector.isVisible()
        and float(dim.property("opacity") or 0) <= 0.002
        and not ring.isVisible(),
        f"panelVisible={inspector.isVisible()} dimOpacity={dim.property('opacity')} "
        f"ringVisible={ring.isVisible()}",
    )

    # 挑一条预览里的控制条当编辑对象（不写死角落名：用户配置里开着哪条就用哪条；
    # 树序 = 配置的角落顺序，第一条通常是下中工具栏）
    target = preview_docks[0]
    corner_name = str(target.objectName()[len("editorPreviewDock_"):])
    shadow = int(target.property("shadowMargin") or 0)
    sx = target.x() + shadow
    sy = target.y() + shadow
    sw = max(target.width() - shadow * 2, 1)
    sh = max(target.height() - shadow * 2, 1)

    # 命中测试：点控制条正中要认得出是哪一条；点屏幕正中（那里没有控制条）要认不出
    hit = str(editor.dockAt(sx + sw / 2, sy + sh / 2))
    miss = str(editor.dockAt(info["width"] / 2, info["height"] / 2))
    check(
        "点画面里的控制条能认出是哪一条",
        hit == corner_name and miss == "",
        f"命中={hit!r}（期望 {corner_name!r}）空白处={miss!r}",
    )

    # 进入编辑态（走 QML 的真接口 ``selectCorner``，与鼠标点选同一个入口）。
    #
    # ⚠️ 这一步**偶发**失败（实测约二十次里一次）：``selectedCorner`` 会在设完之后
    # 的某一拍被清成 ""，随后成片的编辑态断言跟着失败，而前面的「命中测试」还好好的
    # —— 说明确实发生了一次真实的清空，不是读到了中间值（``_settle`` 已经排除后者）。
    # 清空的唯一出口是 ``clearSelection()``（``refreshFromConfig`` / ``onVisibleChanged``
    # 都会调它），但挂了 QML 侧 console 诊断连跑十几次也复现不到。
    # 处理办法与下面「Esc 退出编辑态」那条相同：确认一次，没生效就再来一拍
    # （最多 3 次），并把重试次数写进失败详情 —— 根因找出来之前先别让它变成假失败。
    for _attempt in range(3):
        editor.selectCorner(corner_name)
        _settle()  # 相机 220ms + 面板 220ms + 一轮布局
        if editor.property("editing") is True:
            break

    check(
        "点中组件后进入编辑态",
        editor.property("editing") is True,
        f"editing={editor.property('editing')} corner={corner_name} "
        f"selectedCorner={editor.property('selectedCorner')!r} 尝试={_attempt + 1}",
    )

    # 聚焦比例：把选中项（+取景留白）装进视口，钳制在 [fitScale, 2×]。
    # ⚠️ 这里的「全景比例」要用**面板展开后**的视口重算 —— 面板挤窄舞台之后
    #    fitScale 本身也变小了（它是「整屏装进当前视口」）。
    fit_now = min(viewport.width() / info["width"], viewport.height() / info["height"])
    want = min((viewport.width() - FOCUS_PAD_X * 2) / sw,
               (viewport.height() - FOCUS_PAD_Y * 2) / sh)
    want = max(fit_now, min(want, FOCUS_MAX))
    check(
        "聚焦按「选中项装满视口」放大（上限 2×、下限不小于全景）",
        plane.scale() > fit_now + 1e-3 and abs(plane.scale() - want) <= 1e-3,
        f"scale={plane.scale():.4f} 期望={want:.4f}"
        f"（展开面板后的全景 {fit_now:.4f}；未展开时 {fit:.4f}）",
    )

    # 落点：把选中项的中心摆到视口中央。
    # 2026-10-01（第八轮）用户指令：「我希望聚焦的时候其实那个组件可以在预览区的
    # 正中间，无论是否靠近边界」—— 位移钳制从此在**编辑态额外放宽**（允许的区间里
    # 恒含「取景目标居中」那一点），于是贴边的控制条（下中那条）也精确居中，
    # 代价是画面会往左上越出去一截、视口里露出没画面的留白。
    # 这里**逐轴复算** QML 里那份公式（与下面「控制条落在角落」同一个路子：
    # QML 侧是副本，漂了两边的取景就不一样）。
    def _expected_origin(content: float, view: float, base: float) -> float:
        """``clampOriginX/Y`` 的解析解（编辑态那支）。"""
        if content <= view:
            lo = hi = (view - content) / 2
        else:
            lo, hi = view - content, 0.0
        lo, hi = min(lo, base), max(hi, base)   # 第八轮：编辑态恒含「居中」
        return min(hi, max(lo, base))

    scale = plane.scale()
    base_x = viewport.width() / 2 - (sx + sw / 2) * scale
    base_y = viewport.height() / 2 - (sy + sh / 2) * scale
    want_x = _expected_origin(info["width"] * scale, viewport.width(), base_x)
    want_y = _expected_origin(info["height"] * scale, viewport.height(), base_y)

    # 用户真正要的是「组件落在预览区正中」—— 单独守一条，因为上面那条解析解是
    # **自检自己复算的公式**：QML 那边要是整体改了（比如又把钳制收紧），只要自检
    # 跟着漂就一起变绿。这条拿「组件可见表面的中心在视口里的落点」直接对，
    # 与公式怎么写无关。等目标值（不是等「不变」——动画会卡在中间值）。
    def _centered() -> bool:
        s = plane.scale()
        return (abs(plane.x() + (sx + sw / 2) * s - viewport.width() / 2) <= 1.5
                and abs(plane.y() + (sy + sh / 2) * s - viewport.height() / 2) <= 1.5)

    _wait_cam(_centered)
    check(
        "聚焦取景落点 = 「选中项居中 → 越界钳制」的解析解",
        abs(plane.x() - want_x) <= 1.5 and abs(plane.y() - want_y) <= 1.5,
        f"plane=({plane.x():.1f},{plane.y():.1f}) 期望=({want_x:.1f},{want_y:.1f}) "
        f"居中轴 x={abs(base_x - want_x) <= 1.5} y={abs(base_y - want_y) <= 1.5}",
    )
    check(
        "聚焦把组件摆到预览区**正中**（贴边的下中工具栏也精确居中）",
        _centered(),
        f"组件中心=({plane.x() + (sx + sw / 2) * plane.scale():.1f},"
        f"{plane.y() + (sy + sh / 2) * plane.scale():.1f}) "
        f"视口中心=({viewport.width() / 2:.1f},{viewport.height() / 2:.1f}) "
        f"角={corner_name} 屏幕内=({sx:.0f},{sy:.0f}) {sw:.0f}x{sh:.0f} "
        f"scale={plane.scale():.4f}",
    )

    # 暗罩：**铺满面板左边的整块区域**，选中项周围留洞。
    # 2026-10-01 用户指令：「左边的压暗你应该占满左半边啊而不是留一圈亚克力」——
    # 所以它还挂在窗口坐标里（不在 planeLayer 里），左右沿一路顶到窗口边 /
    # 设置面板边，视口四周那圈留白也得压上。
    check(
        "非选中区域压了一层暗罩",
        dim.isVisible() and abs(float(dim.property("opacity")) - DIM_OPACITY) <= 0.02,
        f"visible={dim.isVisible()} opacity={dim.property('opacity')}",
    )
    # RinUI 的 ``Utils.windowDragArea``：内容区四周被它内缩了 5px，暗罩要比内容区
    # 再往外撑这么多才顶得到窗口边（否则贴边留一圈 5px 没压暗的亚克力）。
    DRAG = 5
    check(
        "暗罩铺满面板左边的整块区域（一路顶到窗口边，不留一圈亚克力）",
        abs(dim.x() - (-DRAG)) <= 1
        and abs((dim.x() + dim.width()) - inspector.x()) <= 1
        and abs(dim.y()) <= 1
        and abs(dim.height() - (inspector.height() + DRAG)) <= 1,
        f"dim=({dim.x():.0f},{dim.y():.0f}) {dim.width():.0f}x{dim.height():.0f} "
        f"panel.x={inspector.x():.0f} "
        f"内容区={inspector.width():.0f}x{inspector.height():.0f}",
    )

    # 洞：几何在**窗口坐标**里复算 —— 取景矩形活在 1:1 屏幕坐标系里，要经相机
    # （planeLayer 的比例与位移）+ 视口偏移换过来，各边外扩「描边间隙 + 洞留白」，
    # 最后夹进视口（手动放大到 400% 时洞会比视口还宽）。
    #
    # 2026-10-01（第八轮）用户指令：「我希望压暗附近的时候不要只是粗略的矩形排除，
    # 而是除了那个组件以外的全压暗」。洞不再是**四块 Rectangle 拼的矩形**，而是
    # ``Shape`` + ``ShapePath``（``OddEvenFill``）挖出来的**圆角矩形**。
    # 守三件事：
    #   ① 边界的**外扩公式**没变（组件 + 描边间隙 + 洞留白，再夹进视口）；
    #   ② 圆角 = **短边一半** —— 与选中描边同一套几何（描边半径也是短边一半），
    #      于是两者同心；半径恰好等于「描边半径 + 洞留白」；
    #   ③ 圆角**真的生效** —— 早先的矩形洞半径恒为 0，这条就是它的反面。
    dim_shape = _find_named(dim, "editorDimShape")
    stale_dims = {name: _find_named(dim, name) is not None
                  for name in ("editorDimTop", "editorDimBottom",
                               "editorDimLeft", "editorDimRight")}
    hole_pad = DIM_HOLE_PAD + RING_GAP
    view_x = viewport.x() + DRAG
    view_y = viewport.y()
    raw_x = view_x + plane.x() + sx * plane.scale() - hole_pad
    raw_y = view_y + plane.y() + sy * plane.scale() - hole_pad
    hole_x = max(view_x, raw_x)
    hole_y = max(view_y, raw_y)
    hole_w = max(0.0, min(view_x + viewport.width(),
                          raw_x + sw * plane.scale() + hole_pad * 2) - hole_x)
    hole_h = max(0.0, min(view_y + viewport.height(),
                          raw_y + sh * plane.scale() + hole_pad * 2) - hole_y)
    check(
        "暗罩在选中项处留出了洞（外扩公式不变、夹在视口内，四块矩形的旧拼法已撤）",
        dim_shape is not None and not any(stale_dims.values())
        and abs(float(dim.property("holeX")) - hole_x) <= 1
        and abs(float(dim.property("holeY")) - hole_y) <= 1
        and abs(float(dim.property("holeW")) - hole_w) <= 1
        and abs(float(dim.property("holeH")) - hole_h) <= 1,
        f"shape={dim_shape is not None} "
        + " ".join(f"{k}={v}" for k, v in stale_dims.items())
        + f" 洞=({float(dim.property('holeX')):.0f},{float(dim.property('holeY')):.0f},"
        f"{float(dim.property('holeW')):.0f},{float(dim.property('holeH')):.0f}) "
        f"期望=({hole_x:.0f},{hole_y:.0f},{hole_w:.0f},{hole_h:.0f})",
    )

    # 圆角：与选中描边同一套几何 —— 描边半径是「短边一半」，洞再往外多一圈
    # ``DIM_HOLE_PAD``，所以期望 ``ring.radius + DIM_HOLE_PAD``。两个数都从活着的
    # 控件上读（不写死像素），谁单方面改了圆角这条就红。
    dim_radius = 0.0 if dim_shape is None else float(dim_shape.property("holeRadius") or 0)
    ring_radius = float(ring.property("radius") or 0)
    check(
        "暗罩的洞是**组件自己的形状**（圆角 = 短边一半的胶囊，与选中描边同心）",
        dim_shape is not None
        and hole_w > 0 and hole_h > 0
        and abs(dim_radius - min(hole_w, hole_h) / 2) <= 0.6
        and abs(dim_radius - (ring_radius + DIM_HOLE_PAD)) <= 1.5
        and dim_radius > 1,
        "没找到挖洞的 Shape" if dim_shape is None else
        f"洞半径={dim_radius:.1f} 期望={min(hole_w, hole_h) / 2:.1f}"
        f"（描边半径 {ring_radius:.1f} + 洞留白 {DIM_HOLE_PAD} "
        f"= {ring_radius + DIM_HOLE_PAD:.1f}） 洞={hole_w:.0f}x{hole_h:.0f}",
    )

    # 选中描边：几何跟着相机，宽度不跟着缩放（画在视口坐标里）
    # ⚠️ ``border.width`` 是分组属性，PySide 侧读不到（没有 QQuickPen* 的转换器）
    #    —— QML 里另存了 ``ringBorderWidth`` / ``ringBorderColor`` 给自检读。
    check(
        "选中项套着强调色描边（位置跟着相机、宽度不随缩放）",
        ring.isVisible()
        and abs(ring.x() - (plane.x() + sx * plane.scale() - RING_GAP)) <= 1.5
        and abs(ring.y() - (plane.y() + sy * plane.scale() - RING_GAP)) <= 1.5
        and abs(ring.width() - (sw * plane.scale() + RING_GAP * 2)) <= 1.5
        and abs(float(ring.property("ringBorderWidth")) - RING_WIDTH) <= 0.01
        and str(ring.property("ringBorderColor").name()).lower()
            == str(app.backend.accent).lower(),
        f"ring=({ring.x():.1f},{ring.y():.1f}) {ring.width():.1f}x{ring.height():.1f} "
        f"border={ring.property('ringBorderWidth')} "
        f"color={ring.property('ringBorderColor')} accent={app.backend.accent}",
    )

    # 面板是**挤窄舞台**：舞台宽度整整少了 ``PANEL_W``，而且面板左沿就贴在
    # 舞台右沿之后（不是浮在舞台上面盖住一块）。
    # 用「收面板时的舞台宽」当基准而不是 ``editor.width() - 32``：内容区还被
    # RinUI 的 ``Utils.windowDragArea`` 左右各内缩 5px。
    check(
        "右侧设置面板滑出，并把舞台挤窄（不是浮在舞台上面）",
        inspector.isVisible()
        and abs(inspector.width() - PANEL_W) <= 1
        and abs(viewport.width() - (stage_width_closed - PANEL_W)) <= 2
        and viewport.x() + viewport.width() <= inspector.x() + 1,
        f"panel={inspector.x():.1f}+{inspector.width():.1f} "
        f"viewport={viewport.x():.1f}+{viewport.width():.0f} "
        f"（面板收起时 {stage_width_closed:.0f}）",
    )

    # 面板结构（2026-10-01 用户指令：「右侧的设置面板应该是实色背景，组件信息就放在
    # 右侧设置面板的下部始终置着展示：工具栏 318x62，上面的信息不要了，缩放的话也是
    # 放在下部置着，右侧面板其他地方是用来排设置项的」）。
    surface = _find_named(content_root, "editorInspectorSurface")
    body = _find_named(content_root, "editorInspectorBody")
    surface_color = surface.property("color") if surface is not None else None
    check(
        "设置面板是**实色**底（不透出背后的亚克力）",
        surface_color is not None and surface_color.alpha() == 255,
        "没找到底板" if surface is None else f"color={surface_color}",
    )

    # 底板要**一路铺到窗口边**（2026-10-01 用户截屏指出右沿/下沿那圈亮带）：
    # 内容区被 RinUI 内缩了 ``windowDragArea`` 5px，底板不往外撑就会露出那圈窗口
    # 背景（亚克力）。留 1px 是窗口 ``background`` 的描边。
    bleed = float(inspector.property("edgeBleed"))
    right_edge = surface.mapToScene(QPointF(float(surface.width()), 0.0)).x()
    bottom_edge = surface.mapToScene(QPointF(0.0, float(surface.height()))).y()
    check(
        "面板底板铺到窗口边（盖住右侧/下侧那圈窗口拖动热区）",
        abs(bleed - (WINDOW_DRAG_AREA - 1)) <= 0.01
        and abs(right_edge - (editor.width() - 1)) <= 1.5
        and abs(bottom_edge - (editor.height() - 1)) <= 1.5,
        f"bleed={bleed} right={right_edge:.1f} bottom={bottom_edge:.1f} "
        f"window={editor.width():.0f}x{editor.height():.0f}",
    )
    check(
        "组件信息**常驻**在面板下部（贴底，不跟着设置项滚动）",
        abs(footer.y() + footer.height() - inspector.height()) <= 1
        and abs(footer.width() - inspector.width()) <= 1
        and abs(footer.height() - PANEL_FOOTER_H) <= 1
        and _find_named(footer, "editorFooterInfoRow") is not None
        and _find_named(footer, "editorInspectorName") is not None,
        f"footer=({footer.x():.0f},{footer.y():.0f}) "
        f"{footer.width():.0f}x{footer.height():.0f}（期望高 {PANEL_FOOTER_H}）"
        f"panel={inspector.width():.0f}x{inspector.height():.0f}",
    )

    # ------------------------------------------------- 预览区上的悬浮缩放缓
    # 2026-10-01（第六轮）用户指令：「缩放作为一个悬浮组件放在左侧的主界面预览
    # 区域」。原先缩放缓长在面板下部常驻条里（与组件信息同一块），现在整块搬去
    # 预览区。这里守四件事：**位置**（预览区**右上角**、离视口上沿 / 右沿各 16）、
    # **形状**（圆角矩形而**不是药丸** —— 第七轮用户指令「不该是大圆角」）、
    # **归属**（不再是面板 / 常驻条的孩子）、**层序**（在暗罩之上、面板之下）。
    zoom_bar = _find_named(content_root, "editorZoomBar")
    zoom_surface = _find_named(content_root, "editorZoomBarSurface")
    check(
        "缩放缓成了预览区上的**浮出层**（不再长在面板下部常驻条里）",
        zoom_bar is not None and zoom_surface is not None
        and zoom_bar.isVisible()
        and _find_named(footer, "editorZoomRow") is None
        and _find_named(footer, "editorZoomLabel") is None
        and _find_named(inspector, "editorZoomRow") is None,
        f"bar={zoom_bar is not None} surface={zoom_surface is not None} "
        f"常驻条里还有缩放={_find_named(footer, 'editorZoomRow') is not None}",
    )
    if zoom_bar is not None and zoom_surface is not None:
        # 几何：底板落在**视口右上角**，离上沿 / 右沿各 16（视觉距离，组件盒子
        # 外面那圈投影余量已经在调用方扣掉了）。
        vs_x = viewport.mapToItem(content_root, 0, 0).x()
        vs_y = viewport.mapToItem(content_root, 0, 0).y()
        bar_x = zoom_bar.mapToItem(content_root, 0, 0).x()
        bar_y = zoom_bar.mapToItem(content_root, 0, 0).y()
        surf_x = zoom_surface.mapToItem(content_root, 0, 0).x()
        surf_y = zoom_surface.mapToItem(content_root, 0, 0).y()
        check(
            "缩放缓压在预览区**右上角**：离视口上沿 / 右沿各一个边距",
            abs((surf_x + zoom_surface.width())
                - (vs_x + viewport.width() - ZOOM_BAR_MARGIN)) <= 1.5
            and abs(surf_y - (vs_y + ZOOM_BAR_MARGIN)) <= 1.5
            and abs(zoom_surface.height() - ZOOM_BAR_H) <= 1
            # 组件盒子 = 底板 + 四周一圈投影余量（摆放时按它扣，见组件头注释）；
            # 这条把那套约定也钉住 —— 少了它，「margin 是视觉距离」就无从验起。
            and abs((zoom_bar.width() - zoom_surface.width())
                    - FLOAT_SHADOW_MARGIN * 2) <= 1
            and bar_x + zoom_bar.width() <= vs_x + viewport.width() + 1
            and bar_y >= vs_y - 1,
            f"底板=({surf_x:.1f},{surf_y:.1f}) {zoom_surface.width():.0f}x"
            f"{zoom_surface.height():.0f} 视口=({vs_x:.1f},{vs_y:.1f}) "
            f"{viewport.width():.0f}x{viewport.height():.0f} "
            f"（期望右上角内缩 {ZOOM_BAR_MARGIN}）",
        )
        # 形状（2026-10-01 第七轮用户指令「不该是大圆角」）：早先是 ``height / 2``
        # 的**药丸**。这里既钉住「就是 8」也钉住「不是胶囊」这件事本身 —— 后者是
        # 用户真正的意图，前者只是当前取值。
        zoom_radius = float(zoom_surface.property("radius") or 0)
        check(
            "缩放缓是**圆角矩形**而不是药丸（圆角 8，远小于高的一半）",
            abs(zoom_radius - ZOOM_BAR_RADIUS) <= 0.5
            and zoom_radius <= zoom_surface.height() / 2 - 8,
            f"radius={zoom_radius:.1f} 高={zoom_surface.height():.0f} "
            f"（药丸会是 {zoom_surface.height() / 2:.0f}）",
        )
        check(
            "缩放缓的层序对：在编辑态暗罩之上、右侧面板之下",
            abs(float(zoom_bar.property("z")) - 12) <= 0.01
            and 12 > float(dim.property("z"))
            and 12 < float(inspector.property("z")),
            f"zoom.z={zoom_bar.property('z')} dim.z={dim.property('z')} "
            f"panel.z={inspector.property('z')}",
        )

    # 面板顶部导航（2026-10-01 用户指令：「（右上角那个 ×）加大移到左边改为返回
    # 按钮」→ 同日第六轮又改口：「把返回按钮删掉 加一个圆按钮放在侧面板的中部」）。
    # 于是顶部那条 ``inspectorNav``（只有一枚返回键 + 一条分隔线）**整条撤掉**，
    # 出口换成圆心压在面板左沿、垂直居中的圆按钮。
    nav = _find_named(content_root, "editorInspectorNav")
    back = _find_named(content_root, "editorInspectorBack")
    handle = _find_named(content_root, "editorInspectorHandle")
    stale = {
        name: _find_named(content_root, name) is not None
        for name in ("editorInspectorHeader", "editorInspectorTitle",
                     "editorViewBar", "editorInspectorClose",
                     "editorInspectorPlaceholder", "editorInspectorNavEdge",
                     "editorInspectorBackIcon")
    }
    check(
        "面板已无顶部导航条与返回键（旧的标题行 / 视图栏 / 右上角 × / 占位一并撤）",
        nav is None and back is None and not any(stale.values()),
        f"nav={nav is not None} back={back is not None} "
        + " ".join(f"{k}={v}" for k, v in stale.items()),
    )
    check(
        "出口改成**面板左沿中线**上的圆按钮（正圆 + 圆心压在左沿上）",
        handle is not None
        and handle.isVisible()
        and abs(handle.width() - PANEL_HANDLE) <= 1
        and abs(handle.height() - PANEL_HANDLE) <= 1
        and abs(handle.width() - handle.height()) <= 1
        and abs(handle.x() + handle.width() / 2) <= 1
        and abs((handle.y() + handle.height() / 2) - inspector.height() / 2) <= 1,
        f"handle={None if handle is None else (handle.x(), handle.y())} "
        f"{None if handle is None else handle.width():.0f}x"
        f"{None if handle is None else handle.height():.0f} "
        f"面板高 {inspector.height():.0f}（中线 {inspector.height() / 2:.0f}）",
    )
    check(
        "设置项区顶到面板上沿（导航条撤掉后不再有 56px 的头部空档）",
        body is not None
        and abs(body.y()) <= 1
        and abs(body.y() + body.height() - footer.y()) <= 1,
        f"body={None if body is None else (body.y(), body.height())} "
        f"footer.y={footer.y():.1f}",
    )

    # ------------------------------------------------ 暗色模式适配：细边（2026-10-01 第七轮）
    # 用户指令：「感觉整体的编辑器对暗色模式适配有点问题」。
    #
    # 查出来的根因是**边线在深色下全员消失**：面板左沿 / 常驻条分隔线 / 圆按钮描边 /
    # 缩放缓描边用的是 ``cardBorderColor``、屏幕框用的是 ``controlBorderColor``，
    # 而 RinUI 的**深色档把这两个都定义成「黑 9~10%」**（``themes/dark.qml``）——
    # 黑边压在 #303030 的面板 / #2C2C2C 的亚克力上，等于没有。浅色档看不出问题，
    # 所以只有拿深色预览图逐像素扫才露馅（面板左沿本该是 #414141，实测 #2B2B2B）。
    #
    # 现在五处一律走 ``Lumi.hairline``（主题的 ``dividerBorderColor``：深色**白**
    # 8.37% / 浅色**黑** 8.03%）。这里守两件事：
    #   ① **五处同源** —— 谁要是单独换回一个「深色下会消失」的令牌就红；
    #   ② **基色按主题翻** —— 深色档必须是**白基**、浅色档必须是**黑基**。
    #      ② 是钉住根因的那一条：它不看当前渲染，两个主题下都成立（深色档跑就查
    #      白基、浅色档跑就查黑基），所以不必中途切主题就能拦住回归。
    def _blend_over(fore, back):
        """把半透明的前景色压到后景上（等效实色）。"""
        alpha = fore.alphaF()
        return QColor.fromRgbF(
            fore.redF() * alpha + back.redF() * (1 - alpha),
            fore.greenF() * alpha + back.greenF() * (1 - alpha),
            fore.blueF() * alpha + back.blueF() * (1 - alpha))

    def _luminance(color):
        return (0.2126 * color.redF() + 0.7152 * color.greenF()
                + 0.0722 * color.blueF())

    screen_frame = _find_named(content_root, "editorScreenFrame")
    panel_edge = _find_named(content_root, "editorInspectorEdge")
    footer_edge = _find_named(content_root, "editorFooterEdge")
    hairlines = {
        "屏幕框": None if screen_frame is None
        else screen_frame.property("frameBorderColor"),
        "面板左沿": None if panel_edge is None else panel_edge.property("color"),
        "常驻条分隔线": None if footer_edge is None else footer_edge.property("color"),
        "面板圆按钮": None if handle is None else handle.property("handleBorderColor"),
        "缩放缓": None if zoom_surface is None
        else zoom_surface.property("surfaceBorderColor"),
    }
    missing = [name for name, value in hairlines.items() if value is None]
    values = [QColor(value) for value in hairlines.values() if value is not None]
    dark_now = bool(app.rinui.theme_manager.is_dark_theme())
    hairline = values[0] if values else QColor(0, 0, 0, 0)
    # 基色判定：深色档细边必须是**白基**（黑基在深色面板上等于没有），浅色档反之。
    # ⚠️ PySide 的浮点取色器叫 ``redF()/greenF()/blueF()``（没有 ``rF()``）。
    channels = {"r": "redF", "g": "greenF", "b": "blueF"}
    toward = ((lambda ch: getattr(hairline, ch)() > 0.9) if dark_now
              else (lambda ch: getattr(hairline, ch)() < 0.1))
    base_ok = all(toward(channels[ch]) for ch in "rgb")
    # 压到面板底色上还得真的看得出来（方向对 + 幅度够）。
    panel_bg = surface.property("color") if surface is not None else QColor("#808080")
    delta = _luminance(_blend_over(hairline, panel_bg)) - _luminance(panel_bg)
    check(
        "编辑器细边五处同源、且**按主题翻基色**（深色白基 / 浅色黑基）",
        not missing
        and len({value.rgba() for value in values}) == 1
        and base_ok
        and 0.03 <= hairline.alphaF() <= 0.25
        and (delta >= 0.03 if dark_now else delta <= -0.03),
        ("缺部件：" + ", ".join(missing)) if missing else
        f"{hairline.name()} alpha={hairline.alphaF():.3f} "
        f"主题={'dark' if dark_now else 'light'} "
        f"（期望{'白' if dark_now else '黑'}基）"
        f" 压面板底色的亮度差={delta:+.3f}"
        + ("" if len({v.rgba() for v in values}) == 1 else " ⚠️ 五处不同源"),
    )

    # ---------------------------------------------------- 平铺版式（2026-10-01 第五轮）
    # 用户指令（附 Win11「设置 → 通知」截屏）：「主界面编辑器的组件设置内容其实
    # 不应该用常规的设置卡，而是类似图片的这种平铺设置名称和 dropdown / 开关 / 选项」。
    #
    # 这条守的是**版式的本质**，不是某一项的措辞：
    #   · 面板里不能再有 ``Rin.SettingCard``（那是「左标题 / 右控件」的两栏卡）；
    #   · 三项设置都得是 ``InspectorSetting``（名称一行、控件在下一行）。
    # ⚠️ 光照一张预览图看不出「卡片还在但看着像平的」，所以必须按类型数。
    panel_card = _find_named(content_root, "editorInspectorPanel")
    flat_items = _collect_type(panel_card, "InspectorSetting") if panel_card else []
    check(
        "编辑器设置面板已改成平铺式：一个 SettingCard 都没有、三个 InspectorSetting 就位",
        panel_card is not None
        and len(_collect_type(panel_card, "SettingCard")) == 0
        and len(flat_items) == 3,
        f"SettingCard={len(_collect_type(panel_card, 'SettingCard')) if panel_card else '?'} "
        f"InspectorSetting={len(flat_items)}（期望 3：显示按钮文本 / 退出键样式 / 翻页组件位置）",
    )

    # 设置项跟着选中的组件走（2026-10-01 用户指令：「工具栏新增设置项『显示按钮文本』，
    # 打开后，将在按钮旁边显示按钮的名称文本」）。
    labels_item = _find_named(content_root, "editorSettingButtonLabels")
    labels_switch = _find_named(content_root, "editorSettingButtonLabelsSwitch")
    selected_groups = ((corner_cfg.get(corner_name) or {}).get("groups") or [])
    selected_is_toolbar = any(
        g in selected_groups for g in ("tools", "actions", "exit"))
    check(
        "选中工具栏时面板里出现「显示按钮文本」设置项（且带开关）",
        labels_item is not None and labels_switch is not None
        and labels_item.isVisible() is selected_is_toolbar,
        f"项={labels_item is not None} switch={labels_switch is not None} "
        f"visible={None if labels_item is None else labels_item.isVisible()} "
        f"该角落是工具栏={selected_is_toolbar}（groups={selected_groups}）",
    )
    if labels_item is not None and labels_switch is not None and selected_is_toolbar:
        # 名称在**控件上面**（这是「平铺」与「两栏卡」唯一的结构差别，也最容易
        # 在改版式时改漏 —— 卡片换掉、名字还留在右边）。
        # ⚠️ 量坐标要在 ``content_root`` 坐标系里比：一个是 Rin.Text、一个是 Switch，
        #    没有共同父级。
        title_label = _find_text(labels_item, "显示按钮文本")
        title_pos = (None if title_label is None
                     else title_label.mapToItem(content_root, QPointF(0, 0)))
        switch_pos = labels_switch.mapToItem(content_root, QPointF(0, 0))
        check(
            "「显示按钮文本」名称排在开关**上面**、两者左对齐（平铺版式）",
            title_pos is not None
            and title_pos.y() + title_label.height() <= switch_pos.y() + 1
            and abs(title_pos.x() - switch_pos.x()) <= 1,
            f"名称 y={None if title_pos is None else round(title_pos.y())} "
            f"x={None if title_pos is None else round(title_pos.x())} "
            f"| 开关 y={switch_pos.y():.0f} x={switch_pos.x():.0f}",
        )
        # 开关自带的状态字（``checkedText`` / ``uncheckedText``）必须是中文：
        # 默认那对是 ``qsTr("On") / qsTr("Off")``，本项目没有翻译文件，会直接
        # 显示成英文（第一版就并排出现了「Off 关」两个状态字）。
        check(
            "开关的状态字是中文「开 / 关」（不是 RinUI 默认的 On / Off）",
            str(labels_switch.property("checkedText")) == "开"
            and str(labels_switch.property("uncheckedText")) == "关",
            f"checkedText={labels_switch.property('checkedText')!r} "
            f"uncheckedText={labels_switch.property('uncheckedText')!r}",
        )

    # 退出键样式（2026-10-01 用户指令：从设置 → 放映页搬进「主界面编辑器里的
    # 工具栏设置」）。它与「显示按钮文本」同属工具栏一组，所以显隐条件一致。
    exit_item = _find_named(content_root, "editorSettingExitStyle")
    exit_combo = _find_named(content_root, "editorSettingExitStyleCombo")
    check(
        "选中工具栏时面板里出现「退出键样式」（从放映页搬来，带下拉）",
        exit_item is not None and exit_combo is not None
        and exit_item.isVisible() is selected_is_toolbar,
        f"项={exit_item is not None} combo={exit_combo is not None} "
        f"visible={None if exit_item is None else exit_item.isVisible()} "
        f"该角落是工具栏={selected_is_toolbar}",
    )
    if exit_item is not None and exit_combo is not None and selected_is_toolbar:
        # 版式：平铺之后标题独占一行，不会被挤成两行；但下拉仍得宽到选项文字
        # 不截断（「红色（Luminalium 1）」是两项里最长的选项文字）。
        exit_title = _find_text(exit_item, "退出键样式")
        combo_text = exit_combo.property("contentItem")
        typed_width = float(
            (combo_text.property("contentWidth") if combo_text is not None else 0) or 0
        )
        check(
            "「退出键样式」标题一行放得下、下拉宽到选项文字不截断",
            exit_title is not None
            and int(exit_title.property("lineCount") or 0) <= 1
            and typed_width > 0
            and typed_width + 36 <= exit_combo.width() + 1,
            f"标题行数={None if exit_title is None else exit_title.property('lineCount')} "
            f"下拉={exit_combo.width():.0f} 其中文字需 {typed_width:.0f}",
        )

        # 走**真实入口**（``Backend.setSetting``）：写配置 + 广播，预览与真机
        # 控制条同时变（两项都是直径 44 的圆，只能靠暴露的填充 / 图标色区分）。
        prev_exit = app.config.get("presentation.exit.style")
        other_exit = "danger" if (prev_exit or "default") != "danger" else "default"
        fill_before = str(target.property("exitFillColor"))
        app.backend.setSetting("presentation_exit_style", other_exit)
        _settle()
        check(
            f"切「退出键样式」写进配置并同步到控制条（{prev_exit} → {other_exit}）",
            str(app.config.get("presentation.exit.style")) == other_exit
            and int(exit_combo.property("currentIndex"))
            == (1 if other_exit == "danger" else 0)
            and str(target.property("exitStyle")) == other_exit
            and str(target.property("exitFillColor")) != fill_before,
            f"配置={app.config.get('presentation.exit.style')!r} "
            f"下拉={exit_combo.property('currentIndex')} "
            f"控制条={target.property('exitStyle')!r} "
            f"填充={target.property('exitFillColor')}（原 {fill_before}）",
        )

        app.backend.setSetting("presentation_exit_style", prev_exit)
        _settle()
        check(
            "「退出键样式」已还原（自检不留副作用）",
            str(app.config.get("presentation.exit.style")) == prev_exit
            and str(target.property("exitFillColor")) == fill_before,
            f"配置={app.config.get('presentation.exit.style')!r} "
            f"填充={target.property('exitFillColor')}（原 {fill_before}）",
        )

    name_label = _find_named(content_root, "editorInspectorName")
    size_label = _find_named(content_root, "editorInspectorSize")
    zoom_label = _find_named(content_root, "editorZoomLabel")
    mode_label = _find_named(content_root, "editorZoomMode")
    check(
        "常驻条写着被点中的组件名与自身尺寸（如「工具栏 318 × 62」）",
        name_label is not None and str(name_label.property("text")) != ""
        and size_label is not None
        and str(size_label.property("text")) == f"{round(sw)} × {round(sh)}",
        f"name={None if name_label is None else name_label.property('text')!r} "
        f"size={None if size_label is None else size_label.property('text')!r} "
        f"期望尺寸={round(sw)} × {round(sh)}",
    )
    check(
        "悬浮缩放缓的百分比 = 相机比例（屏幕坐标系 1:1，100% 即真实像素）",
        zoom_label is not None and zoom_label.isVisible()
        and str(zoom_label.property("text")) == f"{round(plane.scale() * 100)}%",
        f"label={None if zoom_label is None else zoom_label.property('text')!r} "
        f"scale={plane.scale():.4f}",
    )
    check(
        "悬浮缩放缓写着当前档位（自动适应 / 手动档位）",
        mode_label is not None and mode_label.isVisible()
        and str(mode_label.property("text"))
        == ("自动适应" if bool(editor.property("autoScale")) else "手动档位"),
        f"mode={None if mode_label is None else mode_label.property('text')!r} "
        f"autoScale={editor.property('autoScale')}",
    )

    # ---------------------------------------------- 显示按钮文本（工具栏设置项）
    # 走**内存改配置 + reload_from_config** 的成对用法（``persist=False``），不落盘。
    # 打开后按钮从「直径 44 的圆」变成「图标 + 名称」的胶囊，整条控制条按文字
    # 宽度撑宽 —— 真机侧 ``windows.py::_load_docks`` 挂了 widthChanged → 重摆，
    # 所以这里也顺带验「宽度真的变了」（否则可能只是标签画在圆外面）。
    labels_before = _collect_named(target, "dockButtonLabel")
    width_before = target.width()
    check(
        "默认不带名称文本（标签项都在，只是不显示）",
        bool(labels_before) and not any(lab.isVisible() for lab in labels_before),
        f"标签数={len(labels_before)} "
        f"可见={sum(1 for lab in labels_before if lab.isVisible())}",
    )

    prev_labels = app.config.get("presentation.buttons.show_labels")
    app.config.set("presentation.buttons.show_labels", True, persist=False)
    app.backend.reload_from_config()
    _settle()

    labels_after = _collect_named(target, "dockButtonLabel")
    shown = [lab for lab in labels_after if lab.isVisible()]
    shown_texts = [str(lab.property("text")) for lab in shown]
    # 翻页 pill 的两个圆钮也带着（空的）标签槽 —— 它们是**故意**不参与这个开关的
    # （见 Lumi / 配置里 show_labels 的说明），所以判据是「有名字的都得显示」，
    # 而不是「所有标签都得显示」。
    named = [lab for lab in labels_after if str(lab.property("text")) != ""]
    tools_cfg = app.config.get("presentation.tools", []) or []
    tool_labels = {str(t.get("label")) for t in tools_cfg}
    check(
        "打开后每个有名字的按钮旁边都出现名称文本（且都不是空的）",
        bool(named) and all(lab.isVisible() for lab in named)
        and len(named) == len(shown) and all(text for text in shown_texts),
        f"有名字的标签={len(named)} 可见={len(shown)} 文本={shown_texts}",
    )
    check(
        "翻页 pill 不参与这个开关（保持「小、聚拢」的形态）",
        all(str(lab.property("text")) == "" for lab in labels_after
            if not lab.isVisible()),
        f"未显示但有文本的标签="
        f"{[str(lab.property('text')) for lab in labels_after if not lab.isVisible()]}",
    )
    if selected_is_toolbar:
        check(
            "文本取的是按钮自己的名字（工具的 label，不是 tooltip 那种长文案）",
            tool_labels.issubset(set(shown_texts)),
            f"工具名={sorted(tool_labels)} 屏幕上={sorted(set(shown_texts))}",
        )
    check(
        "名称文本把控制条撑宽（不是把字挤在原来的圆里）",
        target.width() > width_before + 40,
        f"宽度 {width_before:.0f} → {target.width():.0f}",
    )

    app.config.set("presentation.buttons.show_labels", prev_labels, persist=False)
    app.backend.reload_from_config()
    _settle()
    check(
        "关掉后回到纯图标形态（宽度还原、自检不留副作用）",
        not any(lab.isVisible() for lab in _collect_named(target, "dockButtonLabel"))
        and abs(target.width() - width_before) <= 1,
        f"宽度={target.width():.0f}（原 {width_before:.0f}）",
    )

    # ----------------------------------------------------- 手动档位 / 平移钳制
    # ⚠️ 这三条等的是**目标值**而不是「不再变化」：动画卡在中间值时「不变」同样成立
    # （见 ``_wait_cam`` / ``_nudge_editor`` 的说明），实测偶发假失败过。
    editor.setProperty("autoScale", False)
    editor.setProperty("manualScale", 1.0)
    _settle()
    _wait_cam(lambda: abs(float(plane.scale()) - 1.0) <= 1e-3)
    check(
        "手动档位接管相机（100% = 真实像素大小）",
        abs(plane.scale() - 1.0) <= 1e-3,
        f"scale={plane.scale():.4f}",
    )

    editor.setProperty("manualScale", 99.0)
    _settle()
    _wait_cam(lambda: float(plane.scale()) <= ZOOM_MAX + 1e-6)
    check(
        "手动档位有上限钳制",
        plane.scale() <= ZOOM_MAX + 1e-6,
        f"scale={plane.scale():.4f}（上限 {ZOOM_MAX}）",
    )

    editor.setProperty("panDX", 99999.0)
    editor.setProperty("panDY", 99999.0)
    _settle()
    _wait_cam(lambda: plane.x() <= 0.5 and plane.y() <= 0.5)
    check(
        "拖动平移被钳制（画面不许从视口里拖出空档）",
        plane.x() <= 0.5 and plane.y() <= 0.5,
        f"plane=({plane.x():.1f},{plane.y():.1f})",
    )

    # ---------------------------------------------------------------- 退出编辑态
    editor.clearSelection()  # 走真实出口（面板左沿那枚圆按钮 / Esc 也调它）
    _settle()
    _wait_cam(lambda: abs(float(plane.scale()) - fit) <= 1e-3)
    check(
        "退出编辑态：面板收起、暗罩消失、比例回到全景",
        editor.property("selectedCorner") == ""
        and not inspector.isVisible()
        and float(dim.property("opacity") or 0) <= 0.002
        and abs(plane.scale() - fit) <= 1e-3,
        f"panelVisible={inspector.isVisible()} dimOpacity={dim.property('opacity')} "
        f"scale={plane.scale():.4f} fit={fit:.4f}",
    )

    # --------------------------------------------- 真机点击链路（合成鼠标事件）
    # ``dockAt`` 只验了寻址；这一条走完整链路：
    # 窗口上的鼠标按下 → MouseArea → 命中测试 → 选中 → 相机聚焦 / 面板展开。
    # （点控制条**不能**真的去翻 PPT —— 屏蔽层就是为了这个，见 QML 注释。）
    origin = viewport.mapToItem(content_root, QPointF(0, 0))

    def _click_viewport(vx: float, vy: float) -> None:
        QTest.mouseClick(editor, Qt.LeftButton, Qt.NoModifier,
                         QPoint(int(round(origin.x() + vx)), int(round(origin.y() + vy))))

    def _select_dock() -> int:
        """点画面里那条控制条 → 进编辑态；返回用掉的尝试次数（0 = 没成）。

        ⚠️ 这一步会撞上「选中被打回全景」那个偶发（见上面 ``selectCorner`` 的
        说明），所以照原样重试 3 次。
        """
        for attempt in range(3):
            _click_viewport(plane.x() + (sx + sw / 2) * plane.scale(),
                            plane.y() + (sy + sh / 2) * plane.scale())
            _settle()
            if str(editor.property("selectedCorner")) == corner_name:
                return attempt + 1
        return 0

    select_attempts = _select_dock()
    check(
        "在窗口上真的点一下控制条 → 进入编辑态",
        select_attempts > 0 and editor.property("editing") is True,
        f"selectedCorner={editor.property('selectedCorner')!r}（期望 {corner_name!r}）"
        f" 尝试={select_attempts}",
    )

    # ⚠️ 2026-10-01（第八轮）：聚焦之后被选中的那条**就落在预览区正中**（用户要的
    #    就是它），所以「点正中央」不再是一处空白 —— 会命中控制条、留在编辑态。
    #    改成**找一个真的空白点**（上/左/右三边贴内沿各试几个位置），并用 ``dockAt``
    #    反查确认 —— 寻址的权威在 QML 侧，别让自检自己猜哪儿是空的。
    def _blank_viewport_point():
        for vy, vx in ((28.0, viewport.width() / 2),
                       (28.0, 40.0),
                       (viewport.height() - 28.0, viewport.width() / 2),
                       (viewport.height() / 2, 40.0)):
            if str(editor.dockAt((vx - plane.x()) / plane.scale(),
                                 (vy - plane.y()) / plane.scale())) == "":
                return vx, vy
        return None

    blank = _blank_viewport_point()
    check(
        "（前置）给「点空白」挑的点确实不压在控制条上",
        blank is not None,
        "" if blank is not None else
        f"视口 {viewport.width():.0f}x{viewport.height():.0f} 里找不到空白点"
        f"（控制条占满了？target={corner_name}）",
    )
    if blank is not None:
        _click_viewport(*blank)
        _settle()
    check(
        "点画面空白处 → 回到全景（不会卡在编辑态）",
        blank is not None
        and str(editor.property("selectedCorner")) == ""
        and editor.property("editing") is False
        and abs(plane.scale() - fit) <= 1e-3,
        f"点={None if blank is None else (round(blank[0]), round(blank[1]))} "
        f"selectedCorner={editor.property('selectedCorner')!r} "
        f"scale={plane.scale():.4f} fit={fit:.4f}",
    )

    # ---- 面板左沿那枚圆按钮（2026-10-01 第六轮）
    # 它**一半悬在舞台上**（``x: -width/2``），「点在它的中心」正好压在
    # 「面板 ↔ 舞台」这条边界上 —— 必须由面板那一层接住（面板 ``z: 20``），
    # 不能穿到底下的舞台屏蔽层去：穿过去动作看着一样（都是回全景），链路其实不同，
    # 而且意味着这枚按钮的一半是**点不着**的。
    select_attempts = _select_dock()
    handle_item = _find_named(content_root, "editorInspectorHandle")
    if select_attempts > 0 and handle_item is not None:
        hp = handle_item.mapToItem(
            content_root,
            QPointF(handle_item.width() / 2, handle_item.height() / 2))
        QTest.mouseClick(editor, Qt.LeftButton, Qt.NoModifier,
                         QPoint(int(round(hp.x())), int(round(hp.y()))))
        _settle()
    check(
        "点面板左沿的圆按钮 → 退出编辑态（与 Esc 同一个出口）",
        select_attempts > 0
        and str(editor.property("selectedCorner")) == ""
        and editor.property("editing") is False,
        f"selectedCorner={editor.property('selectedCorner')!r} "
        f"handle={handle_item is not None} 进编辑态尝试={select_attempts}",
    )

    # 快捷键：Esc 退出编辑态、Ctrl+= / Ctrl+- 调档、Ctrl+0 回自动档
    # （``Shortcut`` 不是 ``Item``，在 ``FluentWindowBase`` 里得包一层宿主 Item ——
    #  包错的话这里会直接抛「Cannot assign QObject to QQuickItem* list」。）
    _click_viewport(plane.x() + (sx + sw / 2) * plane.scale(),
                    plane.y() + (sy + sh / 2) * plane.scale())
    _settle()

    # 真机拖动平移：合成「按下 → 移动 → 抬起」，画面要跟着走**同样的距离**。
    # 这条是冲着「自己拖自己」的经典坑去的：屏蔽层跟着 planeLayer 一起缩放平移，
    # 用 ``mouse.x`` 算增量会被自身的位移抵消掉，表现为画面**半速跟手**
    # —— 所以 QML 里走场景坐标（``scenePosition``）。
    before_x, before_y = plane.x(), plane.y()
    from_x = int(round(origin.x() + viewport.width() / 2))
    from_y = int(round(origin.y() + viewport.height() / 2))
    QTest.mousePress(editor, Qt.LeftButton, Qt.NoModifier, QPoint(from_x, from_y))
    QTest.mouseMove(editor, QPoint(from_x + 60, from_y + 40))
    QTest.mouseRelease(editor, Qt.LeftButton, Qt.NoModifier,
                       QPoint(from_x + 60, from_y + 40))
    _settle()
    check(
        "拖动平移 1:1 跟手（不是半速，也没被吞掉）",
        abs(plane.x() - before_x - 60) <= 3 and abs(plane.y() - before_y - 40) <= 3,
        f"位移=({plane.x() - before_x:.1f},{plane.y() - before_y:.1f}) 期望=(60,40)",
    )

    # ⚠️ QML 的 ``Shortcut`` 默认 context 是 ``WindowShortcut`` —— 窗口**不活跃**
    #    时按键进不来（自检是在后台跑的，窗口偶尔拿不到焦点，实测偶发漏一次）。
    #    所以先 ``requestActivate()``，必要时再补一次。
    for _attempt in range(3):
        editor.requestActivate()
        QTest.keyClick(editor, Qt.Key_Escape)
        _settle()
        if str(editor.property("selectedCorner")) == "":
            break
    check(
        "Esc 退出编辑态",
        str(editor.property("selectedCorner")) == "",
        f"selectedCorner={editor.property('selectedCorner')!r} active={editor.isActive()}",
    )

    # ------------------------------------------------------------ 亚克力背景
    check(
        "编辑器窗口声明了 RinUI 的按窗口 backdrop 钩子",
        editor.property("backdropEnabled") is True,
        f"backdropEnabled={editor.property('backdropEnabled')}",
    )
    check(
        "亚克力已打到窗口句柄上",
        editor.property("acrylicActive") is True,
        f"acrylicActive={editor.property('acrylicActive')}",
    )
    # 回读 DWM 属性 —— 「调用没抛异常」不等于「系统真的记下了」。
    # 截屏只能看「像不像」，这一条能看「是不是」。
    # ``DWMWA_SYSTEMBACKDROP_TYPE`` = 38，``DWMSBT_TRANSIENTWINDOW`` = 3（Acrylic）。
    backdrop = ctypes.c_int(-1)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(int(editor.winId())), ctypes.c_uint(38),
        ctypes.byref(backdrop), ctypes.sizeof(backdrop),
    )
    check(
        "DWM 回读确认背景材质 = Acrylic(3)",
        backdrop.value == 3,
        f"回读 {backdrop.value}（0=None 2=Mica 3=Acrylic 4=Tabbed）",
    )
    plate = _find_named(content_root, "editorTitleBarPlate")
    title_height = float(editor.property("titleBarHeight") or 0)
    check(
        "标题栏有不透明底板（「除标题栏外才是亚克力」的那一条）",
        plate is not None and title_height > 0
        and abs(plate.height() - title_height) <= 0.6
        and plate.y() == 0,
        "没找到底板" if plate is None else
        f"plate={(plate.x(), plate.y(), plate.width(), plate.height())} "
        f"titleBarHeight={title_height}",
    )

    area = QGuiApplication.primaryScreen().availableGeometry()
    check(
        "主界面编辑器位于屏幕内",
        area.left() <= editor.x()
        and editor.x() + editor.width() <= area.right() + 1
        and area.top() <= editor.y()
        and editor.y() + editor.height() <= area.bottom() + 1,
        f"pos=({editor.x()},{editor.y()}) "
        f"size={editor.width()}x{editor.height()} area={area}",
    )

    # 与设置 / 调试窗口同一条约定：由 RinUI 接管（否则没有系统阴影 / 圆角 / Snap，
    # 而且 WS_CAPTION 会露一条原生标题栏压在自绘标题栏上）
    hwnd = int(editor.winId())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    filter_hwnds = {int(h) for h in app.rinui.win_event_filter.hwnds.values()}
    theme_hwnds = {int(h) for h in app.rinui.theme_manager.windows}
    check(
        "主界面编辑器已交给 RinUI 管（WS_CAPTION|WS_THICKFRAME + 名单）",
        bool(style & 0x00C00000)
        and bool(style & 0x00040000)
        and hwnd in filter_hwnds
        and hwnd in theme_hwnds,
        f"style=0x{style:08X} hwnd={hwnd} "
        f"filter={'Y' if hwnd in filter_hwnds else 'N'} "
        f"theme={'Y' if hwnd in theme_hwnds else 'N'}",
    )

    # 设置项跟着选中的组件走：挑一条**没有工具栏区块**的控制条（翻页 pill），
    # 面板里那块「显示按钮文本」必须收起来 —— 它是工具栏的设置项。
    pager_corner = next(
        (name for name in enabled
         if not any(g in ((corner_cfg.get(name) or {}).get("groups") or [])
                    for g in ("tools", "actions", "exit"))),
        None,
    )
    if pager_corner is not None:
        editor.setProperty("selectedCorner", pager_corner)
        _settle()
        check(
            "选中翻页组件时工具栏的设置项收起（设置项跟着组件走）",
            labels_item is not None and not labels_item.isVisible(),
            f"corner={pager_corner} "
            f"visible={None if labels_item is None else labels_item.isVisible()}",
        )
        editor.clearSelection()
        _settle()

    # -------------------------------------------------- 翻页组件位置（翻页组件设置项）
    # 2026-10-01 用户指令：「翻页组件新增设置项『翻页组件位置』，可选翻页组件是
    # 竖版两侧中间 还是横板两侧下部」。两种形态**二选一**（同时开会变成四个翻页栏），
    # 写的是 ``presentation.pager.position``，后端顺带开关 corners 那四个角 ——
    # 真实生效的仍是 corners，所以两边都得验。
    PAGER_SIDE = ("middle_left", "middle_right")
    PAGER_BOTTOM = ("bottom_left", "bottom_right")
    PAGER_COUNTERPART = {
        "middle_left": "bottom_left", "middle_right": "bottom_right",
        "bottom_left": "middle_left", "bottom_right": "middle_right",
    }
    position_item = _find_named(content_root, "editorSettingPagerPosition")
    position_side = _find_named(content_root, "editorSettingPagerPositionSide")
    position_bottom = _find_named(content_root, "editorSettingPagerPositionBottom")
    check(
        "面板里有「翻页组件位置」设置项（且是两条平铺选项，不是下拉）",
        position_item is not None
        and position_side is not None and position_bottom is not None,
        f"项={position_item is not None} 选项={position_side is not None}"
        f"/{position_bottom is not None}",
    )

    if position_item is not None and pager_corner is not None:
        editor.setProperty("selectedCorner", pager_corner)
        _settle()
        check(
            "选中翻页组件时出现「翻页组件位置」（工具栏那项仍然收起）",
            position_item.isVisible() and not labels_item.isVisible(),
            f"corner={pager_corner} 位置项={position_item.isVisible()} "
            f"文本项={labels_item.isVisible()}",
        )

        # 版式（2026-10-01 第五轮改平铺）：名称一行、两条选项排在它下面，
        # 且**选项文字不能截断** —— 平铺之后宽度不再由卡片右栏挤出来，
        # 但也因此没有「右栏最小宽度」兜底，窄面板下更容易被压掉字。
        # ⚠️ 量截断看 ``width() >= implicitWidth()``：``RadioButton`` 换掉
        #    ``contentItem`` 之后没有 ``contentWidth`` 可读（``ComboBox`` 才有）。
        pager_title = _find_text(position_item, "翻页组件位置")
        title_pos = (None if pager_title is None
                     else pager_title.mapToItem(content_root, QPointF(0, 0)))
        options = [o for o in (position_side, position_bottom) if o is not None]
        option_pos = [o.mapToItem(content_root, QPointF(0, 0)) for o in options]
        check(
            "「翻页组件位置」名称在上、两条选项在下且左对齐、文字都没被压掉",
            pager_title is not None
            and int(pager_title.property("lineCount") or 0) <= 1
            and len(options) == 2
            and all(o.width() + 1 >= o.implicitWidth() for o in options)
            and all(pos.y() >= title_pos.y() + pager_title.height() - 1
                    for pos in option_pos)
            and all(abs(pos.x() - title_pos.x()) <= 1 for pos in option_pos),
            f"标题行数={None if pager_title is None else pager_title.property('lineCount')} "
            f"选项宽=" + "/".join(
                f"{o.width():.0f}>={o.implicitWidth():.0f}" for o in options),
        )

        prev_position = str(app.config.get("presentation.pager.position") or "side")
        # ⚠️ ``corner_cfg`` 是配置里那份**活的** dict，开关一改它就跟着变 ——
        #    「还原后是否回到原样」必须拿切换**之前**的快照比。
        prev_pager_on = [c for c in PAGER_SIDE + PAGER_BOTTOM
                         if (corner_cfg.get(c) or {}).get("enabled")]
        other_position = "bottom" if prev_position != "bottom" else "side"
        want_on = PAGER_BOTTOM if other_position == "bottom" else PAGER_SIDE
        want_off = PAGER_SIDE if other_position == "bottom" else PAGER_BOTTOM

        # 走**真实入口**（``Backend.setSetting``）：它负责连带开关四个角落，
        # 并让 ``windows.py::rebuild_docks`` 重建真机控制条。
        app.backend.setSetting("presentation_pager_position", other_position)
        _settle()

        corners_now = app.config.get("presentation.corners") or {}
        on_now = [c for c in PAGER_SIDE + PAGER_BOTTOM
                  if (corners_now.get(c) or {}).get("enabled")]
        check(
            "切形态连带开关四个角落（二选一 —— 同时开就是四个翻页栏）",
            sorted(on_now) == sorted(want_on),
            f"position={other_position} 开着的角落={sorted(on_now)} 期望={sorted(want_on)}",
        )

        check(
            "两条选项跟着切过去（选中的那枚就是屏幕上那种形态）",
            bool(position_side.property("checked"))
            == (other_position != "bottom")
            and bool(position_bottom.property("checked"))
            == (other_position == "bottom"),
            f"竖版选项 checked={position_side.property('checked')} "
            f"横版选项 checked={position_bottom.property('checked')} "
            f"期望 position={other_position!r}",
        )

        # 预览副本跟着换（竖版 SidePager ↔ 横版 pill，是两个不同的 QML 组件）
        preview_now = [str(d.objectName()[len("editorPreviewDock_"):])
                       for d in _collect_named(plane, "editorPreviewDock_")]
        check(
            "预览里的翻页组件跟着换形态（新形态出现、旧形态消失）",
            all(c in preview_now for c in want_on)
            and not any(c in preview_now for c in want_off),
            f"预览={sorted(preview_now)} 期望含={sorted(want_on)} "
            f"不该出现={sorted(want_off)}",
        )

        # 真机侧：换的是 QML 组件，光挪位置不够 —— 必须整批重建
        live_now = sorted(app.windows._docks)
        expect_live = sorted(
            name for name in CORNERS
            if (corners_now.get(name) or {}).get("enabled"))
        check(
            "真机侧控制条按新的角落重建（不是只挪位置）",
            live_now == expect_live,
            f"真机={live_now} 期望={expect_live}",
        )

        # 编辑对象还在：换形态只是把它挪到对应角落，面板不该收起来
        moved = PAGER_COUNTERPART.get(pager_corner, "")
        check(
            "换形态后编辑对象跟着挪到对应角落（面板没有收起来）",
            str(editor.property("selectedCorner")) == moved
            and inspector.isVisible(),
            f"selectedCorner={editor.property('selectedCorner')!r} 期望={moved!r} "
            f"panel={inspector.isVisible()}",
        )
        check(
            "挪过去的还是同一只翻页组件（组件名没变成工具栏）",
            str(_find_named(content_root, "editorInspectorName").property("text"))
            == "翻页组件",
            f"name={_find_named(content_root, 'editorInspectorName').property('text')!r}",
        )

        # 还原（走同一条真实入口），确认自检不留副作用
        app.backend.setSetting("presentation_pager_position", prev_position)
        _settle()
        corners_back = app.config.get("presentation.corners") or {}
        preview_back = [str(d.objectName()[len("editorPreviewDock_"):])
                        for d in _collect_named(plane, "editorPreviewDock_")]
        check(
            "还原后角落开关 / 预览 / 配置都回到原样（自检不留副作用）",
            str(app.config.get("presentation.pager.position")) == prev_position
            and [c for c in PAGER_SIDE + PAGER_BOTTOM
                 if (corners_back.get(c) or {}).get("enabled")] == prev_pager_on
            and sorted(preview_back) == sorted(enabled),
            f"position={app.config.get('presentation.pager.position')!r} "
            f"预览={sorted(preview_back)} 原样={sorted(enabled)}",
        )

        editor.clearSelection()
        _settle()

    app.backend.closeMainEditor()
    check("主界面编辑器可关闭", not editor.isVisible())
    app.windows.show_editor()
    check(
        "编辑器只隐藏不销毁（再开复用同一实例）",
        app.windows.editor is editor and editor.isVisible(),
        "实例被重建了" if app.windows.editor is not editor else "",
    )
    app.backend.closeMainEditor()

    # 导航改名：字面量容易改一半（改了导航没改页面，或反过来），所以两头都钉
    settings = app.windows.settings
    items = settings.property("navigationItems") if settings is not None else None
    # ⚠️ ``navigationItems`` 是 QML 的 ``property var``，PySide 侧拿到的是
    # **QJSValue**，不能直接迭代（会抛 ``TypeError: object is not iterable``）。
    # 而 QTimer 槽里抛出的异常不会退出事件循环 —— 表现为进程挂着不动、日志也停了，
    # 排查方向很容易跑偏（2026-10-01 真踩到）。这里统一转成 Python 对象。
    if hasattr(items, "toVariant"):
        items = items.toVariant()
    rows = [i for i in (items or []) if hasattr(i, "get")]
    titles = [str(row.get("title")) for row in rows]
    pages = [str(row.get("page")) for row in rows]
    check(
        "设置导航含「主界面」且指向 MainInterface.qml",
        "主界面" in titles and any("MainInterface.qml" in p for p in pages),
        f"titles={titles}",
    )
    check("设置导航已无「外观」项", "外观" not in titles, f"titles={titles}")
    # 2026-10-01（第四轮）：新建「个性化」页承接主题 / 强调色；「放映」页删除。
    # 导航是这两件事唯一的外部引用点，字面量最容易改一半（删了页面没删导航项，
    # 表现是点进去一片空白 / 控制台报找不到 qml），所以两头都钉。
    check(
        "设置导航含「个性化」且指向 Personalization.qml",
        "个性化" in titles and any("Personalization.qml" in p for p in pages),
        f"titles={titles}",
    )
    check(
        "设置导航已无「放映」项、也不剩 Presentation.qml 路径",
        "放映" not in titles and not any("Presentation.qml" in p for p in pages),
        f"titles={titles} pages={pages}",
    )


# ============================================================ 插件断言组
#
# 2026-10-06 插件系统计划 Wave 4 任务 13：9 项插件断言，追加在既有 15 项
# 之后，既有断言零改动。
#
# 为什么全部跑在**子进程**（本脚本 ``--plugin-scenario`` 模式）：
#
# * registry 是模块级单例、``load_plugins`` 末尾冻结 —— 同进程第二次装配
#   直接抛（任务 12 的 QA 头注释实锤）；禁用 / 孤儿 / 坏插件场景的启动
#   配置互斥，只能各开一个进程；
# * 主进程保持 ``app.debug`` 关：``_demo`` 的全部贡献（磁贴 / 设置导航 /
#   dock 工具与动作 / 编辑器组 / 设置键）一项都不进主进程，既有断言
#   不可能被插件贡献「顶」出假失败；
# * 子进程用**临时用户配置**（环境变量 ``LUMI_SMOKE_USER_CONFIG`` 重定向
#   ``paths.USER_CONFIG_FILE`` 与 ``config.USER_CONFIG_FILE`` 两处 ——
#   前者是 loader 阶段一/二的动态查找点，后者是 Config 构造读写的
#   导入时绑定，漏一个就会读写真 ``config/config.json``），真用户配置
#   全程不被碰。
#
# 铁律白名单方案（任务简给定二选一，这里选「白名单 + 结构对比」）：
# ``_demo_dep`` 注册时经总线让 ``_demo`` 写 ``plugins._demo.note="ping"``
# （任务 12 的总线验收载体），退出时 ``quit() → config.save()`` 会把它
# 落盘 —— 这是夹具的**预期写入**而非违规。所以：
#
# * debug 开（iron）：断言「除 ``plugins._demo.note`` 外结构一致」+
#   「该键确为 'ping'」（把预期写入本身也钉死）；
# * debug 关（iron-off）：连这笔写入都没有，断言**字节完全一致**
#   （临时配置按 ``Config.save()`` 同款序列化写入，字节对比才成立）。
#
# 清理责任（谁动这组断言谁负责）：
#
# * 临时配置目录：每个场景一个 ``tempfile.mkdtemp``，``finally`` 里
#   ``rmtree``；
# * 坏插件 ``app/plugins/_smoke_bad/``：故障隔离场景前由父进程注入、
#   ``finally`` 里整目录删除（含 ``__pycache__``）—— 留在盘上会被
#   loader 的调试目录发现机制当成常驻调试插件；
# * 白名单键 ``plugins._demo.note`` 只写进临时配置，随临时目录删除，
#   真 ``config/config.json`` 不需要任何「测后还原」。
#
# 子进程协议：场景函数经 :func:`_pcheck` 把断言写成
# ``SMOKE-PLUGIN|PASS/FAIL|标签|详情`` 标记行进 stdout，父进程
# （:func:`_check_plugin_suite`）逐行解析、镜像进 ``RESULTS``；
# 子进程退出码非零 / 零标记一律算该场景失败。

#: 故障隔离场景注入的坏插件 id（目录名 = 插件 id，``_`` 前缀才会被
#: 调试发现机制捡到）。
BAD_PLUGIN_ID = "_smoke_bad"
BAD_PLUGIN_DIR = ROOT / "app" / "plugins" / BAD_PLUGIN_ID
BAD_PLUGIN_SOURCE = (
    '"""smoke 任务 13 故障隔离夹具：register 必抛。'
    '由 tools/smoke.py 临时注入，用完即删，勿提交。"""\n'
    "\n"
    f'META = {{"id": "{BAD_PLUGIN_ID}"}}\n'
    "\n"
    "\n"
    "def register(ctx):\n"
    '    raise RuntimeError("smoke 注入的故意故障（任务 13 故障隔离断言）")\n'
)

#: 场景子进程断言标记行的格式（详情里的 ``|`` 与换行在 :func:`_pcheck`
#: 侧已转义，这里按三段切）。
_SCENARIO_MARKER = re.compile(r"^SMOKE-PLUGIN\|(PASS|FAIL)\|([^|]*)\|(.*)$")

#: 铁律白名单：夹具总线的预期写入键（见本节头注释的「铁律白名单方案」）。
IRON_WHITELIST = frozenset({"plugins._demo.note"})

_MISSING = object()

_PSCENARIO_FAILURES = 0


def _pcheck(label: str, ok: bool, detail: str = "") -> None:
    """场景子进程的断言出口：打一行标记进 stdout（父进程按行解析）。"""
    global _PSCENARIO_FAILURES
    safe = str(detail).replace("\n", " ").replace("|", "/") if detail else ""
    print(f"SMOKE-PLUGIN|{'PASS' if ok else 'FAIL'}|{label}|{safe}", flush=True)
    if not ok:
        _PSCENARIO_FAILURES += 1


def _flatten_config(obj, prefix: str = "") -> dict:
    """把嵌套 dict 拍平成 ``点号路径 -> 叶子值``（空 dict / 非 dict 都算叶子）。"""
    if isinstance(obj, dict) and obj:
        out = {}
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten_config(value, path))
        return out
    return {prefix: obj}


def _config_diff_except(before_bytes: bytes, after_bytes: bytes, whitelist=()):
    """结构对比两份 config：除 ``whitelist`` 里的点号路径外必须完全一致。

    :return: ``(ok, detail, whitelisted)`` —— ok = 无白名单外差异；detail
        是白名单外差异的简述；whitelisted 是白名单键在 after 里的实际值
        （调用方据此断言预期写入，如 ``note == "ping"``）。

    为什么不比字节：``Config.save()`` 会整文件重写，键序随默认层合并
    顺序走 —— 临时配置的初始字节是我们写的、落盘字节是 Config 写的，
    即使内容等价字节也未必相同；拍平后比结构才是「落没落成」的语义。
    debug 关的场景没有这笔重写问题，直接比字节（见 ``iron-off``）。
    """
    try:
        before = json.loads(before_bytes.decode("utf-8"))
        after = json.loads(after_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return False, f"配置不是合法 JSON: {exc}", {}
    flat_before = _flatten_config(before)
    flat_after = _flatten_config(after)
    diffs = []
    whitelisted = {}
    for path in sorted(set(flat_before) | set(flat_after)):
        if path in whitelist:
            whitelisted[path] = flat_after.get(path)
            continue
        old = flat_before.get(path, _MISSING)
        new = flat_after.get(path, _MISSING)
        if old != new:
            diffs.append(f"{path}: {old!r} -> {new!r}")
    return (not diffs), "; ".join(diffs[:6]), whitelisted


def _write_temp_config(path, initial: dict) -> bytes:
    """写临时用户配置并返回写入的字节。

    序列化与 ``Config.save()`` 同款（``json.dumps(..., indent=2)``、无尾
    换行）—— debug 关的铁律断言要做**字节级**对比，格式不同必然假失败。
    """
    data = json.dumps(initial, ensure_ascii=False, indent=2).encode("utf-8")
    Path(path).write_bytes(data)
    return data


def _inject_bad_plugin() -> None:
    """注入「register 必抛」的坏插件（故障隔离场景用）。用完必须
    :func:`_remove_bad_plugin` —— 见本节头注释的清理责任。"""
    BAD_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    (BAD_PLUGIN_DIR / "__init__.py").write_text("", encoding="utf-8")
    (BAD_PLUGIN_DIR / "plugin.py").write_text(BAD_PLUGIN_SOURCE, encoding="utf-8")


def _remove_bad_plugin() -> None:
    """把注入的坏插件整个删掉（``__pycache__`` 在目录内，一并带走）。"""
    shutil.rmtree(BAD_PLUGIN_DIR, ignore_errors=True)


def _run_plugin_scenario(name: str, config_path, timeout_s: int = 300):
    """开一个子进程跑插件场景，返回 ``(CompletedProcess | None, 错误简述)``。

    子进程 = 本脚本的 ``--plugin-scenario`` 模式：场景函数与父进程共享
    ``_wait_named`` / ``_wait_property`` 等全部辅助。``-X utf8`` 必须带
    （GBK 控制台下 RinUI 的中文资源名会炸，见
    ``.memory/topics/rinui-gbk-crash.md``）。stderr 并进 stdout，场景
    失败时父进程能从输出尾部看到 traceback。
    """
    env = dict(os.environ)
    env["LUMI_SMOKE_USER_CONFIG"] = str(config_path)
    cmd = [
        sys.executable, "-X", "utf8",
        str(Path(__file__).resolve()), "--plugin-scenario", name,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return None, f"子进程超过 {timeout_s}s 未退出"
    except OSError as exc:
        return None, f"子进程拉起失败: {exc}"
    return proc, ""


def _parse_scenario_output(data) -> list:
    """从子进程输出里提取 ``SMOKE-PLUGIN|...`` 标记行，返回
    ``[(标签, 是否通过, 详情), ...]``（非标记行全部忽略）。"""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    out = []
    for line in str(data).splitlines():
        match = _SCENARIO_MARKER.match(line.strip())
        if match:
            out.append((match.group(2), match.group(1) == "PASS", match.group(3)))
    return out


def _plugin_scenario_configs() -> dict:
    """各场景的临时用户配置初始内容（只写非默认值键，与真实用户文件同构）。"""
    return {
        # 铁律直测（debug 开）：无交互启动即退，白名单外结构必须一致。
        "iron": {"app": {"debug": True}},
        # 铁律直测（debug 关）：无任何插件加载，退出后字节必须完全一致。
        "iron-off": {"probe": {"marker": "keep-me"}},
        # 夹具全链路（磁贴 / dock / 设置页 / 编辑器组 / 依赖断言）。
        # 把 _demo_group 挂进下中部的 groups：编辑器检查器渲染的是「选中角
        # 各组 inspector_items 的并集」，夹具开关由此可见可点（只写临时
        # 配置，真配置不受影响）。
        "full": {
            "app": {"debug": True},
            "presentation": {
                "corners": {
                    "bottom_center": {
                        "enabled": True,
                        "groups": ["tools", "actions", "exit", "_demo_group"],
                    }
                }
            },
        },
        # 故障隔离：坏插件由父进程在启动前注入到 app/plugins/_smoke_bad/。
        "fault": {"app": {"debug": True}},
        # 孤儿容忍：手写的「不存在」残留 —— 组名（组件）与磁贴 id 各一，
        # 模拟用户手改 config / 插件卸载后的配置残留。
        "orphan": {
            "app": {"debug": True},
            "presentation": {
                "corners": {
                    "bottom_center": {"enabled": True, "groups": ["_ghost_group"]}
                }
            },
            "quick_panel": {"shortcuts": ["settings", "_ghost_tile"]},
        },
        # 禁用过滤：_demo 禁用后，_demo_dep 应因依赖缺失被连带跳过。
        "disabled": {
            "app": {"debug": True},
            "plugins": {"_demo": {"enabled": False}},
        },
    }


def _check_plugin_suite() -> None:
    """插件断言组（9 项）：逐场景开子进程跑，把子进程断言镜像进 RESULTS。"""
    for name, initial in _plugin_scenario_configs().items():
        tmp = Path(tempfile.mkdtemp(prefix=f"lumi-smoke-plugin-{name}-"))
        try:
            cfg = tmp / "config.json"
            _write_temp_config(cfg, initial)
            if name == "fault":
                _inject_bad_plugin()
            proc, error = _run_plugin_scenario(name, cfg)
            if proc is None:
                check(f"插件场景 {name} 子进程在时限内完成", False, error)
                continue
            markers = _parse_scenario_output(proc.stdout)
            meta_ok = proc.returncode == 0 and bool(markers)
            detail = ""
            if not meta_ok:
                tail = (proc.stdout or b"").decode(
                    "utf-8", errors="replace")[-300:].replace("\n", " ")
                detail = (f"exit={proc.returncode} 标记数={len(markers)} "
                          f"输出尾部={tail!r}")
            check(f"插件场景 {name} 子进程正常跑完", meta_ok, detail)
            for label, ok, marker_detail in markers:
                check(f"插件/{label}", ok, marker_detail)
        finally:
            # 清理责任（本节头注释）：坏插件与临时目录都必须还原 / 删除，
            # 与单个场景的成败无关。
            if name == "fault":
                _remove_bad_plugin()
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------- 场景子进程（内部入口）


class _LogTap(logging.Handler):
    """把 ``app.*`` 日志收进内存列表（场景断言「错误入日志 / 注册顺序」用）。"""

    def __init__(self, sink: list) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record) -> None:
        try:
            self._sink.append((record.levelno, record.getMessage()))
        except Exception:  # noqa: BLE001 - 日志探针绝不能影响被测进程
            pass


class _ScenarioCtx:
    """场景子进程上下文：临时配置重定向、启动前字节、日志 / Qt 消息探针。"""

    def __init__(self) -> None:
        self.config_path = os.environ.get("LUMI_SMOKE_USER_CONFIG", "")
        self.before_bytes = b""
        if self.config_path:
            # 两处重定向缺一不可：loader 阶段一/二动态读
            # ``paths.USER_CONFIG_FILE``，而 ``Config`` 读的是自己模块里
            # import 时绑定的 ``USER_CONFIG_FILE``。
            app_paths.USER_CONFIG_FILE = self.config_path
            app_config.USER_CONFIG_FILE = self.config_path
            self.before_bytes = Path(self.config_path).read_bytes()
        self.logs: list = []
        self.qt_messages: list = []
        logging.getLogger("app").addHandler(_LogTap(self.logs))
        # 默认级别 INFO 已够用（注册顺序 / 跳过原因 / register 异常分别是
        # INFO / WARNING / ERROR）；不去动 root 级别 —— ``setup_logging``
        # 随后会按配置重设，设了也会被盖掉。
        qInstallMessageHandler(
            lambda _mode, _context, message: self.qt_messages.append(str(message))
        )


def _scenario_iron(app, ctx: _ScenarioCtx) -> None:
    """铁律直测（debug 开）：**无交互**启动即退；字节对比在进程尾部做
    （``quit() → config.save()`` 把防抖落盘的账结掉之后）。"""
    QTest.qWait(500)  # 让装配 / 总线写入全部落定再退


def _scenario_iron_off(app, ctx: _ScenarioCtx) -> None:
    """铁律直测（debug 关）：零插件加载、零写入，退出后字节必须一致。"""
    QTest.qWait(500)


def _scenario_full(app, ctx: _ScenarioCtx) -> None:
    """夹具全链路：依赖断言 + 磁贴 + dock 动作 + 设置页 + 编辑器组。"""
    backend = app.backend

    # ---- ⑨ 依赖断言（拓扑序 + 总线端到端）----
    messages = [message for _level, message in ctx.logs]

    def _log_index(target: str) -> int:
        for index, message in enumerate(messages):
            if message == target:
                return index
        return -1

    demo_at = _log_index("插件已加载: _demo（调试）")
    dep_at = _log_index("插件已加载: _demo_dep（调试）")
    _pcheck(
        "依赖断言：_demo_dep 在 _demo 之后注册（日志序）",
        0 <= demo_at < dep_at,
        f"_demo 在第 {demo_at} 条、_demo_dep 在第 {dep_at} 条",
    )
    note = backend.settings.get("plugins__demo_note")
    _pcheck(
        "依赖断言：总线把 plugins._demo.note 置为 ping",
        note == "ping",
        f"note={note!r}",
    )

    # ---- ② 夹具磁贴 ----
    tile = next(
        (item for item in backend.availableShortcutItems
         if str(item.get("id")) == "_demo_panel"),
        None,
    )
    _pcheck(
        "夹具磁贴：目录含 _demo_panel（标题 / 动作形状对齐注册）",
        tile is not None
        and tile.get("title") == "演示"
        and tile.get("action") == "plugin:_demo:open",
        str(tile),
    )
    accepted = backend.activateShortcut("_demo_panel")
    handle = app.windows._registered_windows.get("demo")
    QTest.qWait(400)
    arrived = handle is not None and handle.is_visible()
    _pcheck(
        "夹具磁贴：activateShortcut 受理并到达夹具处理器（夹具窗口已 show）",
        accepted and arrived,
        f"accepted={accepted} 窗口可见={arrived}",
    )
    # 恢复现场：夹具窗口关回（只藏不销毁），免得压住后面的设置页 / 编辑器。
    backend.triggerAction("plugin:_demo:close")
    QTest.qWait(200)

    # ---- ③ 夹具 dock 动作 ----
    # 放映态强制激活：沿用主自检的 ``inject_state`` 手法（不依赖真 PowerPoint）。
    app.ppt.inject_state(
        PresentationState(active=True, slide_index=1, slide_total=2)
    )
    QTest.qWait(300)
    pres = backend.presentationConfig  # dock 工具 / 动作模型的数据源
    action_ids = {str(a.get("id")) for a in pres.get("actions", [])}
    tool_ids = {str(t.get("id")) for t in pres.get("tools", [])}
    overlay = app.windows.overlay
    _pcheck(
        "夹具 dock：放映态下模型含 plugin:_demo:ping / plugin:_demo:tool",
        "plugin:_demo:ping" in action_ids
        and "plugin:_demo:tool" in tool_ids
        and overlay is not None and overlay.isVisible(),
        f"actions={sorted(action_ids)} tools={sorted(tool_ids)} "
        f"overlay可见={overlay.isVisible() if overlay is not None else None}",
    )
    # 非放映态触发仍分发（``plugin:`` 特权前缀在 state.active 门控之前）。
    app.ppt.inject_state(PresentationState(active=False))
    QTest.qWait(200)
    backend.setSetting("plugins__demo_note", "reset")  # 排除总线同值干扰
    backend.triggerAction("plugin:_demo:ping")
    QTest.qWait(200)
    note = backend.settings.get("plugins__demo_note")
    _pcheck(
        "夹具 dock 动作：非放映态 plugin: 门控旁路仍分发到夹具处理器",
        note == "ping",
        f"note={note!r}（triggerAction 前已 reset）",
    )

    # ---- ④ 夹具设置页 ----
    nav = backend.settingsNavItems
    demo_nav = [
        item for item in nav
        if str(item.get("page", "")).endswith("ui/plugins/_demo/DemoSettings.qml")
    ]
    _pcheck(
        "夹具设置页：settingsNavItems 含 _demo 项（标题透传）",
        len(demo_nav) == 1 and demo_nav[0].get("title") == "演示插件",
        str(nav),
    )
    app.windows.show_settings("plugins/_demo/DemoSettings.qml")
    settings = app.windows.settings
    page = (
        _wait_named(settings.contentItem(), "DemoSettings", 8000)
        if settings is not None else None
    )
    card = (
        _find_named(settings.contentItem(), "demoFlagCard")
        if settings is not None else None
    )
    qml_errors = [
        message for message in ctx.qt_messages
        if "DemoSettings" in message
        and ("Error" in message or "error" in message or "Cannot" in message)
    ]
    _pcheck(
        "夹具设置页：show_settings 跳页成功且无 QML 错误",
        page is not None and card is not None and not qml_errors,
        f"page={page is not None} card={card is not None} QML错误={qml_errors[:3]}",
    )
    backend.settingsCloseRequested.emit()
    QTest.qWait(200)

    # ---- ⑤ 夹具编辑器组 ----
    group_names = {str(g.get("name")) for g in backend.presentationGroups}
    _pcheck(
        "夹具编辑器组：presentationGroups 含 _demo_group",
        "_demo_group" in group_names,
        f"groups={sorted(group_names)}",
    )
    accepted = backend.activateShortcut("main_editor")
    editor = app.windows.editor
    QTest.qWait(800)
    _pcheck(
        "夹具编辑器组：编辑器经快捷方式打开",
        accepted and editor is not None and editor.isVisible(),
        f"accepted={accepted} "
        + ("窗口未创建" if editor is None else f"visible={editor.isVisible()}"),
    )
    if editor is not None:
        # 与主自检同款重试：selectedCorner 偶发被清（根因未明，见 _check_editor
        # 里的调查注释），确认一次没生效就再来一拍。
        for _attempt in range(3):
            editor.selectCorner("bottom_center")
            QTest.qWait(700)
            if editor.property("editing") is True:
                break
        item = _wait_named(
            editor.contentItem(), "editorInspectorItem_plugins__demo_flag", 8000
        )
        switch = _find_named(
            editor.contentItem(), "editorInspectorSwitch_plugins__demo_flag"
        )
        _pcheck(
            "夹具编辑器组：选中含 _demo_group 的角后检查器开关渲染",
            item is not None and switch is not None and switch.isVisible(),
            f"item={item is not None} switch={switch is not None} 尝试={_attempt + 1}",
        )
        if switch is not None:
            # 检查器是 Flickable：夹具开关排在并集末尾，先滚到底再点
            # （主自检「开机自启」那条踩过「窗口外的卡片点了没反应」的坑）。
            body = _find_named(editor.contentItem(), "editorInspectorBody")
            if body is not None:
                overflow = float(body.property("contentHeight") or 0) - body.height()
                if overflow > 0:
                    body.setProperty("contentY", overflow)
                    QTest.qWait(300)
            spot = switch.mapToScene(
                QPointF(switch.width() / 2, switch.height() / 2)
            )
            QTest.mouseClick(
                editor, Qt.LeftButton, Qt.NoModifier,
                QPoint(int(spot.x()), int(spot.y())),
            )
            QTest.qWait(300)
        flag = backend.settings.get("plugins__demo_flag")
        _pcheck(
            "夹具编辑器组：翻转开关后 plugins._demo.flag 落盘且类型 bool",
            flag is True,
            f"flag={flag!r}",
        )
        # 「重启后读回」：进程内不能再装配第二次（注册表冻结），这里等价为
        # 落盘后用全新 Config 实例读同一文件 —— 读的就是重启后会读到的字节。
        app.config.save()
        reread = app_config.Config(user_file=str(ctx.config_path))
        value = reread.get("plugins._demo.flag")
        _pcheck(
            "夹具编辑器组：重启后读回类型保持（JSON true → Python bool）",
            value is True and type(value) is bool,
            f"读回={value!r}（{type(value).__name__}）",
        )
        backend.closeMainEditor()
        QTest.qWait(200)


def _scenario_fault(app, ctx: _ScenarioCtx) -> None:
    """故障隔离：register 必抛的坏插件不拖垮应用，错误入日志。"""
    from app.plugins import loader as plugin_loader

    report = {entry["id"]: entry for entry in plugin_loader.loaded_plugins()}
    bad = report.get(BAD_PLUGIN_ID, {})
    _pcheck(
        "故障隔离：坏插件 register 异常被捕获并跳过（清单列明原因）",
        bad.get("loaded") is False and "register 异常" in str(bad.get("reason")),
        str(bad),
    )
    avail = {str(item.get("id")) for item in app.backend.availableShortcutItems}
    _pcheck(
        "故障隔离：应用启动成功且其余插件照常（_demo_panel 目录在）",
        app.backend is not None and "_demo_panel" in avail,
        f"目录={sorted(avail)}",
    )
    errors = [
        message for level, message in ctx.logs
        if level >= logging.ERROR and BAD_PLUGIN_ID in message
    ]
    _pcheck(
        "故障隔离：register 异常已写入日志（log.exception）",
        bool(errors),
        errors[0] if errors else "未捕到 ERROR 记录",
    )


def _scenario_orphan(app, ctx: _ScenarioCtx) -> None:
    """孤儿容忍：不存在的组名 / 磁贴 id 只告警不崩，编辑器与面板照开。"""
    warnings = [
        message for level, message in ctx.logs
        if level >= logging.WARNING and "孤儿组" in message
    ]
    _pcheck(
        "孤儿容忍：不存在的组名记 warning 且孤儿角落被跳过（不崩）",
        bool(warnings),
        warnings[0] if warnings else "未捕到「孤儿组」warning",
    )
    # 开编辑器 + 开面板：抛异常会被 guarded 兜底成 FAIL，能跑到断言即证明无异常。
    app.windows.show_editor()
    QTest.qWait(600)
    editor_ok = app.windows.editor is not None and app.windows.editor.isVisible()
    app.windows.show_panel()
    QTest.qWait(400)
    panel_ok = app.windows.panel is not None and app.windows.panel.isVisible()
    app.windows.hide_panel()
    app.windows.hide_editor()
    _pcheck(
        "孤儿容忍：开编辑器 + 开面板均无异常（未知磁贴 id 被丢弃）",
        editor_ok and panel_ok,
        f"editor={editor_ok} panel={panel_ok}",
    )


def _scenario_disabled(app, ctx: _ScenarioCtx) -> None:
    """禁用过滤：_demo 禁用后全部贡献缺席，_demo_dep 依赖缺失连带跳过。"""
    from app.plugins import loader as plugin_loader

    backend = app.backend
    nav_absent = not any(
        "_demo" in str(item.get("page", "")) for item in backend.settingsNavItems
    )
    catalog = {str(item.get("id")) for item in backend.availableShortcutItems}
    pres = backend.presentationConfig
    dock_absent = not any(
        str(t.get("id", "")).startswith("plugin:_demo")
        for t in pres.get("tools", [])
    ) and not any(
        str(a.get("id", "")).startswith("plugin:_demo")
        for a in pres.get("actions", [])
    )
    group_names = {str(g.get("name")) for g in backend.presentationGroups}
    setting_keys = [str(k) for k in backend.settings]
    window_absent = "demo" not in app.windows._registered_windows
    _pcheck(
        "禁用过滤：_demo 全部贡献缺席（导航 / 磁贴 / dock / 编辑器组 / "
        "设置键 / 窗口）",
        nav_absent
        and "_demo_panel" not in catalog
        and dock_absent
        and "_demo_group" not in group_names
        and not any(k.startswith("plugins__demo") for k in setting_keys)
        and window_absent,
        f"导航含demo={not nav_absent} 磁贴={'_demo_panel' in catalog} "
        f"dock缺席={dock_absent} 组={sorted(group_names)} "
        f"设置键={[k for k in setting_keys if 'demo' in k]}",
    )
    report = {entry["id"]: entry for entry in plugin_loader.loaded_plugins()}
    demo_entry = report.get("_demo", {})
    dep_reason = str(report.get("_demo_dep", {}).get("reason") or "")
    _pcheck(
        "禁用过滤：_demo 标记禁用未加载，_demo_dep 因依赖缺失被跳过",
        demo_entry.get("enabled") is False
        and not demo_entry.get("loaded")
        and "依赖不可用" in dep_reason,
        f"_demo={demo_entry} _demo_dep.reason={dep_reason!r}",
    )
    warnings = [
        message for level, message in ctx.logs
        if level >= logging.WARNING and "_demo_dep" in message
    ]
    _pcheck(
        "禁用过滤：跳过因果链已写入 warning 日志",
        bool(warnings),
        warnings[0] if warnings else "未捕到 _demo_dep 的 warning",
    )


#: 场景名 -> 场景函数。每个场景一个独立子进程（注册表冻结约束，见本节头注释）。
_PLUGIN_SCENARIOS = {
    "iron": _scenario_iron,
    "iron-off": _scenario_iron_off,
    "full": _scenario_full,
    "fault": _scenario_fault,
    "orphan": _scenario_orphan,
    "disabled": _scenario_disabled,
}


def _plugin_scenario_main(scenario: str) -> int:
    """子进程模式：用临时用户配置启动完整应用，跑一个插件场景。"""
    fn = _PLUGIN_SCENARIOS.get(scenario)
    if fn is None:
        _pcheck(f"场景名 {scenario!r} 已登记", False,
                f"可选: {sorted(_PLUGIN_SCENARIOS)}")
        return 2
    ctx = _ScenarioCtx()
    if not ctx.config_path:
        _pcheck("临时用户配置已由 LUMI_SMOKE_USER_CONFIG 指定", False, "环境变量缺失")
        return 2
    app = LuminaliumApplication(sys.argv)

    def guarded() -> None:
        try:
            fn(app, ctx)
        except Exception:
            traceback.print_exc()
            _pcheck("场景执行过程未抛异常", False,
                    traceback.format_exc().splitlines()[-1])
        finally:
            # quit() 内含 config.save()：铁律直测要靠它把防抖落盘的账结掉。
            app.quit()

    QTimer.singleShot(900, guarded)
    code = app.qt_app.exec()
    app.ppt.shutdown()

    # 铁律的字节 / 结构对比必须落在 quit() 的 save() 之后，所以在事件循环
    # 退出后做（场景函数体内是什么都没做的「无交互」段）。
    if scenario == "iron":
        after = Path(ctx.config_path).read_bytes()
        ok, detail, whitelisted = _config_diff_except(
            ctx.before_bytes, after, whitelist=IRON_WHITELIST
        )
        _pcheck(
            "铁律直测（debug 开）：除白名单键 plugins._demo.note 外配置零落盘",
            ok, detail,
        )
        _pcheck(
            "铁律直测（debug 开）：白名单键确为总线预期写入 note='ping'",
            whitelisted.get("plugins._demo.note") == "ping",
            repr(whitelisted),
        )
    elif scenario == "iron-off":
        after = Path(ctx.config_path).read_bytes()
        same = after == ctx.before_bytes
        _pcheck(
            "铁律直测（debug 关）：config 字节完全一致（零插件零写入）",
            same,
            "" if same else f"{len(ctx.before_bytes)}B -> {len(after)}B",
        )

    print(f"SMOKE-PLUGIN-END|{_PSCENARIO_FAILURES}", flush=True)
    return 1 if _PSCENARIO_FAILURES or code != 0 else 0


def _offline_self_test() -> int:
    """插件断言组的离线自检：**不建 Qt 应用、不开窗口**，只验纯辅助逻辑。

    覆盖：临时配置写入的字节形态（与 ``Config.save()`` 同款）、白名单
    diff、坏插件注入 / 清理、场景输出解析。依赖真窗口的断言不在这里验
    —— 它们的写法对照的是上方既有的 ``_wait_named`` / ``check`` 模式，
    运行验证留给解锁后的全量 smoke。
    """
    failures = 0

    def t(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"[{'PASS' if ok else 'FAIL'}] {label}"
              + (f" — {detail}" if detail and not ok else ""))
        if not ok:
            failures += 1

    tmp = Path(tempfile.mkdtemp(prefix="lumi-smoke-selftest-"))
    try:
        # 1) 临时配置写入 + 原样读回
        cfg = tmp / "config.json"
        data = _write_temp_config(cfg, {"probe": {"marker": "keep-me"}})
        t("临时配置写入后读回字节一致", cfg.read_bytes() == data)
        t(
            "临时配置序列化与 Config.save() 同款（indent=2 / 无尾换行）",
            data == json.dumps(
                {"probe": {"marker": "keep-me"}}, ensure_ascii=False, indent=2
            ).encode("utf-8"),
        )

        # 2) 白名单 diff
        after = json.dumps(
            {"probe": {"marker": "keep-me"}, "plugins": {"_demo": {"note": "ping"}}},
            ensure_ascii=False, indent=2,
        ).encode("utf-8")
        ok, detail, whitelisted = _config_diff_except(
            data, after, whitelist=IRON_WHITELIST
        )
        t(
            "白名单 diff：唯一差异是白名单键时判通过并回收其值",
            ok and whitelisted.get("plugins._demo.note") == "ping",
            detail,
        )
        bad = json.dumps(
            {"probe": {"marker": "changed"}, "plugins": {"_demo": {"note": "ping"}}},
            ensure_ascii=False, indent=2,
        ).encode("utf-8")
        ok2, detail2, _ = _config_diff_except(data, bad, whitelist=IRON_WHITELIST)
        t(
            "白名单 diff：白名单外的改动必须被抓出来",
            not ok2 and "probe.marker" in detail2,
            detail2,
        )
        ok3, _, _ = _config_diff_except(data, b"{broken", whitelist=IRON_WHITELIST)
        t("白名单 diff：坏 JSON 返回失败而不是抛异常", not ok3)

        # 3) 坏插件注入 / 清理（清理责任的直测：用完必须还原）
        _inject_bad_plugin()
        plugin_file = BAD_PLUGIN_DIR / "plugin.py"
        t(
            "坏插件注入：目录与 plugin.py 就位、META.id 与目录名一致",
            plugin_file.is_file()
            and (BAD_PLUGIN_DIR / "__init__.py").is_file()
            and f'"id": "{BAD_PLUGIN_ID}"'
            in plugin_file.read_text(encoding="utf-8"),
        )
        _remove_bad_plugin()
        t("坏插件清理：整个目录（含 __pycache__）已删除", not BAD_PLUGIN_DIR.exists())

        # 4) 场景输出解析
        sample = (
            "噪音行\n"
            "SMOKE-PLUGIN|PASS|标签甲|\n"
            "SMOKE-PLUGIN|FAIL|标签乙|详情含 竖线/已转义\n"
            "SMOKE-PLUGIN-END|1\n"
        )
        parsed = _parse_scenario_output(sample)
        t(
            "场景输出解析：只认标记行、PASS/FAIL/详情三段正确",
            parsed == [("标签甲", True, ""), ("标签乙", False, "详情含 竖线/已转义")],
            str(parsed),
        )
    finally:
        _remove_bad_plugin()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n离线自检失败项: {failures}")
    return 1 if failures else 0


def _scenario_from_argv():
    """内部入口解析：``--self-test`` / ``--plugin-scenario <名>``；都不是返回 None。"""
    args = sys.argv[1:]
    if "--self-test" in args:
        return "self-test"
    if "--plugin-scenario" in args:
        index = args.index("--plugin-scenario")
        return args[index + 1] if index + 1 < len(args) else ""
    return None


def main() -> int:
    scenario = _scenario_from_argv()
    if scenario == "self-test":
        return _offline_self_test()
    if scenario is not None:
        return _plugin_scenario_main(scenario)
    app = LuminaliumApplication(sys.argv)
    qt_app = app.qt_app

    failures = 0

    def run_checks() -> None:
        nonlocal failures

        check("系统托盘可用", app.tray.available)
        # 2026-10-01（第二轮）用户指令删掉了「常驻托盘」/「托盘提示文字」两个开关：
        # 托盘是**恒定行为**（`_boot_tray` 恒 show、tooltip 取 `app.name`），
        # 所以这里真的把它显示出来看，别再写恒 True 的假断言。
        app.tray.show()
        QTest.qWait(150)
        tray_icon = app.tray._tray
        check(
            "托盘已显示（「常驻托盘」开关已删，恒常驻）",
            bool(tray_icon.isVisible()),
            f"visible={tray_icon.isVisible()}",
        )
        check(
            "托盘提示文字取 app.name（「托盘提示文字」开关已删）",
            tray_icon.toolTip() == str(app.config.get("app.name")),
            f"tooltip={tray_icon.toolTip()!r} "
            f"app.name={app.config.get('app.name')!r}",
        )
        expected_docks = [
            name
            for name, settings in (app.config.get("presentation.corners", {}) or {}).items()
            # 配置里有 "//" 开头的注释键（值是字符串），要跳过
            if isinstance(settings, dict) and settings.get("enabled", False)
        ]
        check(
            f"顶层窗口与 {len(expected_docks)} 条控制条已创建",
            app.windows.overlay is not None
            and set(app.windows._docks) == set(expected_docks),
            str(list(app.windows._docks)),
        )

        # ---- 面板显隐与定位 ----
        # 光标必须在 show_panel() **之前**取：面板按「弹出那一刻」的光标定位，
        # 之后真鼠标一动，断言就会拿新位置跟旧面板比（真机踩过：光标中途
        # 移动 500px → 假失败）。
        cursor = QCursor.pos()
        app.windows.show_panel()
        panel = app.windows.panel
        check("快捷面板可见", panel.isVisible())
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        inside = (
            area.left() <= panel.x()
            and panel.x() + panel.width() <= area.right() + 1
            and area.top() <= panel.y()
            and panel.y() + panel.height() <= area.bottom() + 1
        )
        check(
            "面板位于屏幕内",
            inside,
            f"panel=({panel.x()},{panel.y()},{panel.width()}x{panel.height()}) area={area}",
        )
        # 光标锚定：水平居中对齐光标（除非贴到屏幕边），纵向要么在光标下方要么整个在光标上方。
        #
        # ⚠️ 这里的容差（24 / 40）本来是给「定位时窗口几何还没稳定」兜底的：
        # 面板**第一次 show() 之前**，Qt 报的几何是 387x453（带无边框窗口的
        # resize 边框余量），而 QML 声明的是 375x440，于是定位用的尺寸快照比
        # 最终尺寸大十几像素。2026-10-01 已在 `windows.py::_position_panel`
        # 里改成读 QML 的 `panelWidth` / `panelHeight`（根因修复），首次弹窗
        # 现在直接用 375x440 算位置。容差保留作安全网。
        center_x = panel.x() + panel.width() // 2
        horiz_ok = (
            abs(center_x - cursor.x()) <= 24
            or panel.x() <= area.left() + 40
            or panel.x() + panel.width() >= area.right() - 40
        )
        # 纵向第三条是「翻转到光标上方后被夹到屏幕上边」的合法结果：
        # 光标在屏幕下半、面板 440 高 + 30 偏移上下都塞不下时，`_position_panel`
        # 会把它贴到顶边（y = area.top() + margin）。缺这一条就会在光标靠近
        # 屏幕中部偏下时假失败。
        vert_ok = (
            panel.y() >= cursor.y()
            or panel.y() + panel.height() <= cursor.y()
            or panel.y() <= area.top() + 12
        )
        check(
            "面板贴着光标弹出（不是甩到屏幕另一头）",
            horiz_ok and vert_ok,
            f"cursor=({cursor.x()},{cursor.y()}) panel=({panel.x()},{panel.y()})",
        )
        app.windows.hide_panel()
        check("面板可隐藏", not panel.isVisible())

        # ---- 模拟进入放映：顶层窗口全屏 + 控制条贴角 ----
        app.ppt.inject_state(
            PresentationState(active=True, slide_index=26, slide_total=41)
        )
        overlay = app.windows.overlay
        screen = QGuiApplication.primaryScreen()
        geom = screen.geometry()
        # 定位基准是**整屏**几何，不是避开任务栏的 availableGeometry：
        # 放映时任务栏被放映窗口盖住，用户眼里的基准就是屏幕边缘，
        # 而 Windows 的工作区照样把任务栏算掉（本机差 48px）→ 纵向会凭空
        # 多出一个任务栏的高度。这里用整屏复算，才能抓到这类静默偏差。
        check(
            "顶层窗口全屏显示",
            overlay is not None and overlay.isVisible()
            and overlay.width() == geom.width() and overlay.height() == geom.height(),
            f"overlay={overlay.width()}x{overlay.height()} screen={geom.width()}x{geom.height()}",
        )
        for corner, dock in app.windows._docks.items():
            left_gap = dock.x()
            right_gap = geom.width() - (dock.x() + dock.width())
            bottom_gap = geom.height() - (dock.y() + dock.height())
            top_gap = dock.y()
            near_left = left_gap <= 64
            near_right = right_gap <= 64
            near_bottom = bottom_gap <= 64
            if corner.startswith("middle"):
                # 竖版两侧翻页：贴左右边 + **垂直居中**（上下余量对称）
                expected_vertical = abs(top_gap - bottom_gap) <= 2
            else:
                expected_vertical = near_bottom
            if corner.endswith("center"):
                # 居中：左右余量对称（后面还有一条专门的居中断言，这里只兜底）
                expected_horizontal = abs(left_gap - right_gap) <= 2
            else:
                expected_horizontal = near_left if corner.endswith("left") else near_right
            check(
                f"控制条 {corner} 贴角",
                expected_horizontal and expected_vertical,
                f"pos=({dock.x()},{dock.y()}) size={dock.width()}x{dock.height()} "
                f"gap=({left_gap},{right_gap},{bottom_gap})",
            )

        # ---- 视觉贴边距离 = 配置里的 margin（对齐 Luminalium 1 的 20px）----
        # 控制条窗口尺寸含投影余量，屏幕上量到的距离必须把这部分扣掉。
        # 这里按实际属性复算，防止「margin 被投影余量吃掉」这类静默偏差
        # （64px 的贴角容差抓不到这种错）。
        margin_x = int(app.windows._config.get("presentation.margin_x", 20))
        margin_y = int(app.windows._config.get("presentation.margin_y", 20))
        cdock = app.windows._docks.get("bottom_center")
        if cdock is not None:
            shadow = int(cdock.property("shadowMargin") or 0)
            visual_bottom = geom.height() - (cdock.y() + cdock.height() - shadow)
            check(
                "工具栏视觉贴边距离 = 配置的垂直边距",
                abs(visual_bottom - margin_y) <= 1,
                f"视觉={visual_bottom} 期望={margin_y} shadow={shadow}",
            )

            # ================================================================
            # 笔的选单（2026-10-01 用户指令）
            # ================================================================
            # 用户指令原话：「顶层窗口的工具栏的 Segmented 默认工具不应该是鼠标
            # 指针吗？并且当目前工具已经是笔的时候弹出如图的选单，图片的只供参考，
            # 实际的颜色列表要更多更丰富」
            def _click_dock_item(item) -> None:
                """在**真机顶层窗口**上点控制条里的一个项。

                坐标经 ``mapToScene`` 换成窗口坐标 —— 顶层窗口整屏铺开，容器
                原点就是窗口原点，所以 scene 坐标直接就是 ``QTest`` 要的坐标。
                ⚠️ 窗口是 ``WS_EX_TRANSPARENT`` 的整窗穿透，但 ``QTest`` 是**直接
                投递**事件、不走 Win32 命中测试，所以照样能点（区域塑形也一样）。
                """
                center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                QTest.mouseClick(overlay, Qt.LeftButton, Qt.NoModifier,
                                 QPoint(int(round(center.x())), int(round(center.y()))))
                QTest.qWait(90)

            def _nudge_top() -> None:
                """把顶层窗口抬起来催一次曝光（动画由渲染循环推进，同
                ``_nudge_editor`` 的教训：窗口不被暴露时动画会卡在中间值）。"""
                overlay.raise_()
                overlay.requestActivate()
                QTest.qWait(120)

            def _wait_reveal(target: float, *, timeout_ms: int = 2500) -> bool:
                """等笔选单的**进出场动画**走完（``reveal`` 到位）。

                选单现在是 Fluent 2 的 flyout 动效（滑入 250ms / 淡出 167ms），
                ``_click_dock_item`` 只等 90ms —— 不等它就半路读几何，会拿到
                动画中间值（「摆放」那类断言首当其冲）。这里等的是**目标值**，
                中途抬一次窗口催曝光。
                """
                def there() -> bool:
                    v = palette.property("reveal")
                    # ⚠️ 容差必须 **≤** ``visible`` 的阈值（``reveal > 0.001`` 才在画），
                    # 否则淡出半路就放行、紧跟着的 ``isVisible() is False`` 当场红。
                    # 原值 0.004 仍然比 0.001 松 —— 2026-10-06 实测在
                    # ``reveal=0.00119`` 处被放行，断言假红（「再点一下『笔』→
                    # 选单收起」）。动画的终点值是**精确的** 0 / 1（``Behavior``
                    # 直接落到目标值），所以贴到阈值上等没有风险。
                    return v is not None and abs(float(v) - target) <= 0.001

                waited = 0
                nudged = False
                while waited <= timeout_ms:
                    if there():
                        return True
                    QTest.qWait(60)
                    waited += 60
                    if not nudged and waited >= timeout_ms // 2:
                        nudged = True
                        _nudge_top()
                return there()

            arrow_item = _find_named(cdock, "dockTool_arrow")
            pen_item = _find_named(cdock, "dockTool_pen")
            palette = _find_named(cdock, "penPalette")
            card = _find_named(cdock, "penPaletteCard")
            check(
                "（前置）工具栏上有指针 / 笔分页，且笔选单组件已挂上",
                None not in (arrow_item, pen_item, palette, card),
                f"arrow={arrow_item} pen={pen_item} palette={palette} card={card}",
            )
            # ① 默认工具必须是**鼠标指针**。原来初值是 ``pen``：控制条一出来就
            #    高亮着「笔」，用户得先点一下指针才能正常放映 —— 等于把「默认
            #    什么都不做」变成了「默认在书写」。
            check(
                "默认工具 = 鼠标指针（不是笔）",
                app.backend.activeTool == "arrow"
                and arrow_item is not None and arrow_item.property("checked") is True
                and pen_item is not None and pen_item.property("checked") is False,
                f"activeTool={app.backend.activeTool!r} "
                f"arrow.checked={arrow_item.property('checked') if arrow_item else None} "
                f"pen.checked={pen_item.property('checked') if pen_item else None}",
            )
            # ② 第一下点「笔」是**切工具**（选单不弹）；已经切过去了再点一下才弹。
            _click_dock_item(pen_item)
            check(
                "点「笔」第一下只切工具，不弹选单",
                app.backend.activeTool == "pen"
                and palette.property("opened") is False
                and pen_item.property("checked") is True,
                f"activeTool={app.backend.activeTool!r} "
                f"opened={palette.property('opened')}",
            )
            _click_dock_item(pen_item)
            opened_settled = _wait_reveal(1.0)
            check(
                "工具已经是笔时再点一下 → 弹出选单（且进出场动画走完）",
                palette.property("opened") is True and palette.isVisible()
                and opened_settled,
                f"opened={palette.property('opened')} visible={palette.isVisible()} "
                f"reveal={palette.property('reveal')}",
            )
            # Fluent 2 化的守卫：圆角、动画、高光 —— 都钉在真机上
            check(
                "选单卡片圆角 = 8（Fluent 2 的 Overlay/Flyout 档，不是自造的 14）",
                abs(float(card.property("effectiveRadius")) - 8) <= 0.01,
                f"radius={card.property('effectiveRadius')}",
            )
            check(
                "选单进出场是动画不是硬切（reveal 从 0 驱动到 1）",
                palette.property("reveal") is not None and opened_settled
                and float(palette.property("reveal")) >= 0.98,
                f"reveal={palette.property('reveal')}",
            )
            # 2026-10-02 用户指令：「颜色选单这个场景就不需要高光了」——
            # 渐变边框高光只留在工具栏底板上，选单保持素净（反面守卫）。
            highlight = _find_named(cdock, "penPaletteHighlight")
            check(
                "选单**不带**渐变边框高光（那是工具栏底板的材质）",
                highlight is None,
                "" if highlight is None else "penPaletteHighlight 还挂着",
            )
            # 笔分页上那圈「选项开着」的提示环（整窗穿透、选单又没有关闭按钮，
            # 用户唯一的退路就是「再点一下这个工具」——得有东西告诉他）
            ring = _find_named(pen_item, "segmentExpandedRing")
            check(
                "选单开着时笔分页描一圈（提示「再点一下能关」）",
                ring is not None and ring.property("visible") is True,
                "" if ring is None else f"visible={ring.property('visible')}",
            )

            # ---- 摆放：贴在工具栏**上方**，左沿与底板左沿对齐 ----
            # ⚠️ 坐标取的是 ``penPaletteCard``（卡片**本体**那个 Rectangle），
            #    它本身就摆在组件的 ``shadowMargin`` 处 —— 所以它的 mapToItem
            #    落点已经是「卡片表面」，别再扣一次投影余量。
            pad_bar = float(cdock.property("shadowMargin") or 0)      # 底板投影余量
            card_pos = card.mapToItem(cdock, QPointF(0, 0))
            card_left = card_pos.x()                                 # 卡片表面左沿
            card_bottom = card_pos.y() + card.height()                # 卡片表面底边
            check(
                "选单落在工具栏上方（不压条、也不飘远），左沿与底板对齐",
                0 < pad_bar - card_bottom <= 20
                and abs(card_left - pad_bar) <= 1,
                f"卡片底={card_bottom:.1f} 底板上沿={pad_bar:.1f} "
                f"卡片左={card_left:.1f} 期望={pad_bar:.1f}",
            )

            # ---- 色板：格子数 / 排列都从配置来 ----
            tiles = _collect_named(cdock, "penSwatchTile")
            want_colors = len(app.config.get("presentation.pen.palette") or [])
            per_row = int(app.config.get("presentation.pen.columns") or 0)
            same_row = {round(t.y()) for t in tiles[:per_row]} if per_row else set()
            check(
                "色板格子数 = 配置里的色数（选单不是画死的）",
                len(tiles) == want_colors and want_colors >= 12,
                f"格子={len(tiles)} 配置={want_colors}",
            )
            check(
                "色板按配置的列数排行（每行 columns 格）",
                per_row > 1 and len(same_row) == 1
                and len(tiles) > per_row
                and round(tiles[per_row].y()) > round(tiles[0].y()),
                f"列={per_row} 首行 y={sorted(same_row)} "
                f"第二行首格 y={round(tiles[per_row].y()) if len(tiles) > per_row else None}",
            )
            # ---- Fluent 2 的 hover 态：划过色点要有一圈淡环 ----
            hover_tile = next((t for t in tiles if not t.property("swatchSelected")),
                              tiles[0] if tiles else None)
            hover_ring = (_find_named(hover_tile, "penSwatchHoverRing")
                          if hover_tile is not None else None)
            if hover_tile is not None:
                hc = hover_tile.mapToScene(
                    QPointF(hover_tile.width() / 2, hover_tile.height() / 2))
                # hover 事件偶发不生成（enter 只在「位置变化」时派发；窗口
                # 曝光时序 / 前一次点击残留位置都可能让它丢一拍）—— 每拍
                # 重发一次 mouseMove，最多等 300ms。
                hover_settled = False
                for _ in range(10):
                    QTest.mouseMove(overlay,
                                    QPoint(int(round(hc.x())), int(round(hc.y()))))
                    if hover_tile.property("hovered") is True:
                        hover_settled = True
                        break
                    QTest.qWait(30)
            check(
                "色点 hover 有一圈淡环（Fluent 2 的 hover 态，划过不再毫无反馈）",
                hover_tile is not None and hover_ring is not None
                and hover_settled
                and hover_ring.property("visible") is True,
                "" if hover_tile is not None and hover_ring is not None
                else f"tile={hover_tile} ring={hover_ring} "
                     f"hovered={hover_tile.property('hovered') if hover_tile else None}",
            )
            # ---- Fluent 2 的分区：分隔线 + 预览次级底板 + Caption 小标题 ----
            divider = _find_named(cdock, "penPaletteDivider")
            preview_surface = _find_named(cdock, "penPalettePreviewSurface")
            title_color = _find_named(cdock, "penPaletteTitleColor")
            title_font = (title_color.property("font")
                          if title_color is not None else None)
            check(
                "两段之间有 1px 分隔线、预览有自己的次级底板（Fluent 2 分区）",
                divider is not None and divider.height() == 1
                and preview_surface is not None
                and abs(float(preview_surface.property("radius")) - 4) <= 0.01,
                f"divider={divider} 高={divider.height() if divider else None} "
                f"预览底板={preview_surface} "
                f"radius={preview_surface.property('radius') if preview_surface else None}",
            )
            check(
                "小标题是 Caption 档（12px，Fluent 2 的分段标题）",
                title_font is not None and title_font.pixelSize() == 12,
                f"pixelSize={title_font.pixelSize() if title_font else None}",
            )
            # ---- 选中色：后端是唯一依据 ----
            # 还没选过 → 配置里的 ``pen.default`` 预点亮（否则弹出来一格都不亮，
            # 而「预览」却画着一条有颜色的笔迹，看着自相矛盾）
            default_color = str(app.config.get("presentation.pen.default") or "").upper()
            selected = [t for t in tiles if t.property("swatchSelected")]
            preview = _find_named(cdock, "penPalettePreview")
            check(
                "没选过颜色时预点亮配置里的默认色（且预览与它同色）",
                app.backend.penColor == ""
                and len(selected) == 1
                and _hex(selected[0].property("swatchColor")) == default_color
                and _hex(preview.property("strokeColor")) == default_color,
                f"penColor={app.backend.penColor!r} default={default_color} "
                f"选中={[_hex(t.property('swatchColor')) for t in selected]} "
                f"预览={_hex(preview.property('strokeColor'))}",
            )
            # 点一格色点：QML → 后端（penColor）→ 应用层（actionTriggered）
            targets = [t for t in tiles
                       if _hex(t.property("swatchColor")) == "#EC4899"]
            fired = []

            def _collect_action(action, _sink=fired):
                _sink.append(str(action))

            app.backend.actionTriggered.connect(_collect_action)
            try:
                if targets:
                    _click_dock_item(targets[0])
            finally:
                app.backend.actionTriggered.disconnect(_collect_action)
            selected = [t for t in tiles if t.property("swatchSelected")]
            ring_visible = [
                bool(_find_named(t, "penSwatchRing").property("visible"))
                for t in tiles
            ]
            check(
                "点色点 → 选中的只有那一格（带环），预览笔迹同色",
                len(targets) == 1 and len(selected) == 1
                and sum(ring_visible) == 1
                and _hex(selected[0].property("swatchColor")) == "#EC4899"
                and _hex(preview.property("strokeColor")) == "#EC4899",
                f"候选={len(targets)} "
                f"选中={[_hex(t.property('swatchColor')) for t in selected]} "
                f"带环={sum(ring_visible)} "
                f"预览={_hex(preview.property('strokeColor'))}",
            )
            check(
                "色点把颜色送到应用层（actionTriggered 走 pen_color）",
                any(str(a).upper() == "PEN_COLOR:#EC4899" for a in fired),
                f"发出={fired}",
            )

            # ---- 命中矩形 / 窗口区域：选单必须被圈进去 ----
            # 这是**整条链上最容易漏的一环**：顶层窗口被 SetWindowRgn 裁成「只有
            # 控制条几块」，卡片浮在 dock 包围盒之外 —— 不进区域就既不画也点不动
            # （点击直接穿透到 PowerPoint，在幻灯片上乱画一笔）。
            rect = cdock.property("interactiveRect")
            center = QPointF(card_pos.x() + card.width() / 2,
                             card_pos.y() + card.height() / 2)
            scene_center = cdock.mapToScene(center)
            covered = [
                r for r in app.windows._dock_rects_local()
                if r[0] <= scene_center.x() <= r[0] + r[2]
                and r[1] <= scene_center.y() <= r[1] + r[3]
            ]
            check(
                "选单被算进 interactiveRect（否则会被区域塑形裁掉、点不动）",
                rect.x() <= center.x() <= rect.x() + rect.width()
                and rect.y() <= center.y() <= rect.y() + rect.height()
                and rect.y() < pad_bar,   # 上沿必须探到条上面去
                f"rect=({rect.x():.0f},{rect.y():.0f},{rect.width():.0f},"
                f"{rect.height():.0f}) 卡片中心=({center.x():.0f},{center.y():.0f})",
            )
            check(
                "区域塑形的矩形里有一块盖住了选单（真机上它才画得出来）",
                bool(covered),
                f"卡片中心(scene)=({scene_center.x():.0f},{scene_center.y():.0f}) "
                f"区域块={app.windows._dock_rects_local()}",
            )
            # ⚠️ 账面对还不够：``_update_overlay_region`` 的「没变就短路」曾用
            # **外接 box** 当判据 —— 选单的块完全落在既有块的外接矩形**内部**
            # （左右竖版翻页块比卡片顶更靠上），box 纹丝不动 → 被当成「区域没变」，
            # 卡片那块从未进过 Win32 区域，账面对、屏幕上整块画不出来
            # （2026-10-01 用户实锤「颜色选单会被截断」）。判据已换成 rects 本身
            # （``_last_region_rects``）；这条守卫钉的是「已应用的矩形与账面
            # **逐项一致**」—— 比 box 会少三块、被裁时整块缺失，都会红。
            applied = app.windows._last_region_rects
            check(
                "选单的块已实际应用到 Win32 区域（已应用矩形 = 账面，逐项一致）",
                applied is not None
                and applied == tuple(tuple(r) for r in app.windows._dock_rects_local()),
                f"已应用={applied} 账面={app.windows._dock_rects_local()}",
            )

            # ---- 关闭：再点一下「笔」/ 点别的工具 / 换工具 ----
            _click_dock_item(pen_item)
            closed_settled = _wait_reveal(0.0)
            closed_rect = cdock.property("interactiveRect")
            check(
                "再点一下「笔」→ 选单收起（淡出动画走完、命中矩形缩回条本身）",
                palette.property("opened") is False and closed_settled
                and not palette.isVisible()
                and closed_rect.y() >= pad_bar - 1,
                f"opened={palette.property('opened')} "
                f"reveal={palette.property('reveal')} "
                f"visible={palette.isVisible()} rect.y={closed_rect.y():.0f}",
            )
            _click_dock_item(pen_item)
            _click_dock_item(arrow_item)
            _wait_reveal(0.0)
            check(
                "切到别的工具 → 选单自动收起（它属于「笔」这个工位）",
                palette.property("opened") is False
                and app.backend.activeTool == "arrow",
                f"opened={palette.property('opened')} "
                f"activeTool={app.backend.activeTool!r}",
            )
            # 回到默认档，别给后面的断言留状态（笔色本身留着就行：它只影响选单
            # 的回显，没有别的断言读它；``setPenColor`` 也不收空串）
            app.backend.selectTool("arrow")
            check(
                "（收尾）工具回到默认档（指针）",
                app.backend.activeTool == "arrow"
                and palette.property("opened") is False,
                f"activeTool={app.backend.activeTool!r} "
                f"opened={palette.property('opened')}",
            )

            # ================================================================
            # 放大镜的选单（2026-10-06 用户指令）
            # ================================================================
            # 用户指令原话：「新增工具『放大镜』，打开之后在工具栏上方弹出放大镜
            # 选项和上下左右移位的选项，他们在一个面板之内。至于这个放大要调用
            # 演示软件的缩放功能」。
            zoom_button = _find_named(cdock, "dockZoomButton")
            zoom_panel = _find_named(cdock, "zoomPanel")
            zoom_card = _find_named(cdock, "zoomPanelCard")
            check(
                "（前置）条上有独立的「放大镜」圆钮，且选单组件已挂上",
                None not in (zoom_button, zoom_panel, zoom_card),
                f"button={zoom_button} panel={zoom_panel} card={zoom_card}",
            )
            # 2026-10-06 用户指令：「放大镜不应当以 Segmented 内排版」。这里把
            # 「它不在分段里」钉住：分段只剩指针 / 笔 / 橡皮三页，且树里不再
            # 有 ``dockTool_zoom`` 这一项 —— 否则改着改着又会回到分段里去。
            check(
                "放大镜**不排进 Segmented**：分段里没有它这一页，它是独立圆钮",
                _find_named(cdock, "dockTool_zoom") is None
                # ``or -1`` 陷阱：页数是 3（falsy 的是 0，这里安全），但仍显式判
                # None，免得以后页数变成 0 时读成 -1 还能「碰巧」通过
                and cdock.property("segmentItemCount") is not None
                and int(cdock.property("segmentItemCount")) == 3,
                f"分段页数={cdock.property('segmentItemCount')} "
                f"dockTool_zoom={_find_named(cdock, 'dockTool_zoom')}",
            )
            # ⚠️⚠️ 这条是本轮那个 bug 的**根因**所在，单独钉住：「放大镜不占
            #    activeTool」。它一度靠 ``activeTool == "zoom"`` 表达，而 QML 分段
            #    的 ``currentIndex`` 绑定读的就是这个值 ——「分段里没有这一页」
            #    被翻译成「指针那一页」，点一下放大镜就把工具切回指针、连带把刚
            #    弹的面板收掉，全程零报错。现在状态在独立的 ``zoomActive`` 上，
            #    ``activeTool`` 回到只取 pen / eraser / arrow。
            check(
                "放大镜**不占** activeTool（它是独立的 zoomActive 布尔）",
                app.backend.activeTool in ("pen", "eraser", "arrow")
                and app.backend.zoomActive is False,
                f"activeTool={app.backend.activeTool!r} "
                f"zoomActive={app.backend.zoomActive}",
            )
            # 槽签名守卫：`@Slot()` 是**零参数**签名，QML 那边
            # `setZoomActive(false)` 传的实参会被静默丢掉 → 进来的一直是默认
            # `True`，「关」变成「再开一次」，撞上 `value == self._zoom_active`
            # 当场 return，状态卡住且不发信号。症状是「点了没反应」+ 零报错，
            # 本轮真踩过（2026-10-06，①②都 PASS 就第三态永远红）。
            # 这里直接从 Python 侧调，绕开 QML 那一层，只验签名本身。
            _zoom_sig_ok = True
            try:
                app.backend.setZoomActive(True)
                app.backend.setZoomActive(False)
                _zoom_sig_ok = app.backend.zoomActive is False
            finally:
                app.backend.setZoomActive(False)
            check(
                "setZoomActive 的槽签名收得到 false（`@Slot(bool)`，不是 `@Slot()`）",
                _zoom_sig_ok,
                f"签名不收参数时 QML 的 false 会被丢掉 → zoomActive="
                f"{app.backend.zoomActive}",
            )

            zoom_fired = []

            def _collect_zoom(action, _sink=zoom_fired):
                _sink.append(str(action))

            def _wait_zoom_reveal(target: float, *, timeout_ms: int = 2500) -> bool:
                """等放大镜选单的进出场动画走完（与 ``_wait_reveal`` 同一条理由）。"""
                waited = 0
                while waited <= timeout_ms:
                    v = zoom_panel.property("reveal")
                    if v is not None and abs(float(v) - target) <= 0.001:
                        return True
                    QTest.qWait(60)
                    waited += 60
                    if waited >= timeout_ms // 2:
                        _nudge_top()
                return False

            # ① 点一下 = 开放大镜 **+ 直接弹出选单**。
            #    （它是条上一枚独立的开关，没有分段那种「当前分页」的语义，
            #    也就没有「二次点击才弹选单」那层习惯。）
            #
            #    记住点击前分段选中的是哪一页 —— 下面要断言它**没动**。这条单列
            #    是因为「点了放大镜面板刚弹出来就没了」这个 bug（2026-10-06）当时
            #    只表现为面板消失，不报错，混在① 里看不出是哪一步坏的。
            segment_index_before = _segment_current_index(cdock)
            tool_before_zoom = app.backend.activeTool
            app.backend.actionTriggered.connect(_collect_zoom)
            try:
                _click_dock_item(zoom_button)
            finally:
                app.backend.actionTriggered.disconnect(_collect_zoom)
            zoom_open_settled = _wait_zoom_reveal(1.0)
            check(
                "点一下「放大镜」= 开放大镜并弹出选单（缩放 + 移位在同一块面板里）",
                app.backend.zoomActive is True
                and zoom_button.property("active") is True
                and zoom_panel.property("opened") is True
                and zoom_open_settled
                and zoom_panel.isVisible(),
                f"zoomActive={app.backend.zoomActive} "
                f"active={zoom_button.property('active')} "
                f"opened={zoom_panel.property('opened')} "
                f"reveal={zoom_panel.property('reveal')} "
                f"visible={zoom_panel.isVisible()}",
            )
            check(
                "放大镜不是指针类型：开它不发 tool:（不该去写 PointerType，"
                "也不该动分段选中的那一页）",
                not [a for a in zoom_fired if str(a).startswith("tool:")],
                f"发出={zoom_fired}",
            )
            # 顺带守住「分段不该被放大镜带跑」：开放大镜之后，分段里选中的
            # 仍应是刚才那一页**且指针没变**（放大镜不改指针）。
            #
            # ⚠️ 这里必须比对**具体那一页 + 指针本身**，不能只数页数
            #    （2026-10-06 的 bug 就是页数照样是 3、但 ``currentIndex`` 被
            #    绑定拉回了 0 → ``onCurrentIndexChanged`` → 工具真切回「指针」
            #    → 面板被顺手收掉）。
            segment_index_after = _segment_current_index(cdock)
            check(
                "开放大镜**不动**分段的选中页与指针（笔照样是笔）",
                segment_index_after == segment_index_before
                and app.backend.zoomActive is True
                and app.backend.activeTool == tool_before_zoom,
                f"点击前={segment_index_before} 点击后={segment_index_after} "
                f"指针={tool_before_zoom!r}→{app.backend.activeTool!r} "
                f"zoomActive={app.backend.zoomActive}",
            )

            # ② 版式：两段（缩放 / 移位）在同一张卡里，且**等宽**（左右沿齐平）。
            titles = [_find_named(zoom_panel, n) for n in
                      ("zoomPanelTitleZoom", "zoomPanelTitlePan")]
            zoom_row = _find_named(zoom_panel, "zoomPanelZoomRow")
            pan_grid = _find_named(zoom_panel, "zoomPanelPanGrid")
            divider_item = _find_named(zoom_panel, "zoomPanelDivider")
            check(
                "两段标题（缩放 / 移位）都在同一张卡片里",
                all(t is not None for t in titles) and divider_item is not None,
                f"标题={titles} 分隔线={divider_item}",
            )
            check(
                "缩放那行与移位十字等宽（两段左右沿天然齐平）",
                zoom_row is not None and pan_grid is not None
                and abs(float(zoom_row.property("width"))
                        - float(pan_grid.property("width"))) <= 1,
                f"row={zoom_row.property('width') if zoom_row else None} "
                f"grid={pan_grid.property('width') if pan_grid else None}",
            )

            # ③ 七枚按钮都得在，且每枚都接上了「发 op」这条路 —— 版式对但按钮
            #    没接线是最容易漏的一环（面板能画出来，点了没反应）。
            button_ops = (
                ("zoomBtn_in", "in"), ("zoomBtn_out", "out"),
                ("zoomBtn_reset", "reset"), ("zoomBtn_up", "up"),
                ("zoomBtn_down", "down"), ("zoomBtn_left", "left"),
                ("zoomBtn_right", "right"),
            )
            missing = [n for n, _ in button_ops if _find_named(zoom_panel, n) is None]
            check(
                "缩放三枚 + 移位四枚按钮都在",
                not missing,
                f"缺={missing}",
            )
            app.backend.actionTriggered.connect(_collect_zoom)
            try:
                if not missing:
                    _click_dock_item(_find_named(zoom_panel, "zoomBtn_in"))
            finally:
                app.backend.actionTriggered.disconnect(_collect_zoom)
            check(
                "点「放大」→ 走到应用层（actionTriggered 走 zoom:in）",
                "zoom:in" in zoom_fired,
                f"发出={zoom_fired}",
            )

            # ③b 横向落点：**卡片中心线对准那枚圆钮的中心线**
            #（2026-10-06 用户指令「要改成对齐圆钮」）。笔选单那条「左沿与底板
            #对齐」在这里**不适用** —— 圆钮在条的中间，照旧的话面板偏在它左边
            # 100px 出头，看着不像从这枚钮里出来的。
            #    ⚠️ 两边都要换算到**同一个坐标系**再比中心：``zoom_card`` 在面板
            #    里、圆钮在 bar 里、``interactiveRect`` 是 dock 局部 —— 一律用
            #    ``mapToItem(cdock, …)``。
            zcard_c = zoom_card.mapToItem(cdock, QPointF(0, 0))
            zcard_mid = zcard_c.x() + zoom_card.width() / 2
            zoom_btn_mid = (zoom_button.mapToItem(cdock, QPointF(0, 0)).x()
                            + zoom_button.width() / 2)
            check(
                "放大镜选单横向对齐圆钮（中心线对中心线，不是贴底板左沿）",
                abs(zcard_mid - zoom_btn_mid) <= 1.0,
                f"卡片中心={zcard_mid:.1f} 圆钮中心={zoom_btn_mid:.1f} "
                f"差={zcard_mid - zoom_btn_mid:+.1f}",
            )

            # ④ 命中矩形 / 窗口区域：选单必须被圈进去（与笔选单同一条铁律）。
            #    ⚠️ 坐标必须先换算到 **dock 局部**：``zoom_card.x()/y()`` 是
            #    **面板内**坐标（卡片挂在 zoomPanel 下），而 ``interactiveRect``
            #    是 dock 局部坐标 —— 直接拿来比会得出「没被圈进去」的假红
            #    （面板浮在条上方，卡片 y 在 dock 里是负数，2026-10-06 踩过）。
            zcard_pos = zoom_card.mapToItem(cdock, QPointF(0, 0))
            z_rect = cdock.property("interactiveRect")
            z_center = QPointF(zcard_pos.x() + zoom_card.width() / 2,
                               zcard_pos.y() + zoom_card.height() / 2)
            z_scene = cdock.mapToScene(z_center)
            z_covered = [
                r for r in app.windows._dock_rects_local()
                if r[0] <= z_scene.x() <= r[0] + r[2]
                and r[1] <= z_scene.y() <= r[1] + r[3]
            ]
            check(
                "放大镜选单被算进 interactiveRect（否则会被区域塑形裁掉、点不动）",
                z_rect.x() <= z_center.x() <= z_rect.x() + z_rect.width()
                and z_rect.y() <= z_center.y() <= z_rect.y() + z_rect.height()
                and z_rect.y() < pad_bar,
                f"rect=({z_rect.x():.0f},{z_rect.y():.0f},{z_rect.width():.0f},"
                f"{z_rect.height():.0f}) 卡片中心=({z_center.x():.0f},"
                f"{z_center.y():.0f})",
            )
            check(
                "区域塑形的矩形里有一块盖住了放大镜选单",
                bool(z_covered),
                f"卡片中心(scene)=({z_scene.x():.0f},{z_scene.y():.0f}) "
                f"区域块={app.windows._dock_rects_local()}",
            )
            z_applied = app.windows._last_region_rects
            check(
                "放大镜选单的块已实际应用到 Win32 区域（逐项一致）",
                z_applied is not None
                and z_applied == tuple(tuple(r) for r in app.windows._dock_rects_local()),
                f"已应用={z_applied} 账面={app.windows._dock_rects_local()}",
            )

            # ⑤ 收起的两条路：再点一下「放大镜」/ 换工具。
            _click_dock_item(zoom_button)
            zoom_closed = _wait_zoom_reveal(0.0)
            check(
                "再点一下「放大镜」→ 选单收起（淡出走完、命中矩形缩回条本身）",
                zoom_panel.property("opened") is False and zoom_closed
                and not zoom_panel.isVisible()
                and cdock.property("interactiveRect").y() >= pad_bar - 1
                # 收起面板**不等于**退出放大镜：那枚圆钮还亮着。这是合法状态 ——
                # 用户只是不需要那块面板了，图照样放大着（缩放由 PPT 自己记着）。
                and app.backend.zoomActive is True
                and zoom_button.property("active") is True,
                f"opened={zoom_panel.property('opened')} "
                f"reveal={zoom_panel.property('reveal')} "
                f"visible={zoom_panel.isVisible()} "
                f"zoomActive={app.backend.zoomActive} "
                f"active={zoom_button.property('active')}",
            )
            # 再点一下圆钮**关掉**放大镜（不是只收面板），再点分段把它叫回来。
            _click_dock_item(zoom_button)
            _wait_zoom_reveal(1.0)
            check(
                "再点一下「放大镜」→ 退出放大镜（圆钮的选中态也灭）",
                app.backend.zoomActive is False
                and zoom_button.property("active") is False
                and zoom_panel.property("opened") is False,
                f"zoomActive={app.backend.zoomActive} "
                f"active={zoom_button.property('active')} "
                f"opened={zoom_panel.property('opened')}",
            )
            _click_dock_item(zoom_button)
            _wait_zoom_reveal(1.0)
            _click_dock_item(arrow_item)
            _wait_zoom_reveal(0.0)
            check(
                "切到别的工具 → 放大镜整个关掉（它属于「放大镜」这个工位）",
                zoom_panel.property("opened") is False
                and app.backend.zoomActive is False
                and zoom_button.property("active") is False
                and app.backend.activeTool == "arrow",
                f"opened={zoom_panel.property('opened')} "
                f"zoomActive={app.backend.zoomActive} "
                f"active={zoom_button.property('active')} "
                f"activeTool={app.backend.activeTool!r}",
            )
            check(
                "（收尾）工具回到默认档（指针），放大镜选单收起",
                app.backend.activeTool == "arrow"
                and app.backend.zoomActive is False
                and zoom_panel.property("opened") is False,
                f"activeTool={app.backend.activeTool!r} "
                f"zoomActive={app.backend.zoomActive} "
                f"opened={zoom_panel.property('opened')}",
            )

            # ---- 「显示按钮文本」在**真机控制条**上也生效，并且会重新摆位 ----
            # 编辑器预览里那条单独验过（见 _check_editor）；这里验真实那条：
            # 名字一多整条就变宽，宽度变了若不重摆，居中的那条会按**旧宽度**
            # 停在偏掉的位置（``_load_docks`` 挂了 widthChanged →
            # ``_schedule_reposition``）。走内存改配置（``persist=False``），不落盘。
            labels_prev = app.config.get("presentation.buttons.show_labels")
            plain_width = float(cdock.width())
            app.config.set("presentation.buttons.show_labels", True, persist=False)
            app.backend.reload_from_config()
            _wait_stable(
                lambda: f"{cdock.width():.1f}|{cdock.x():.1f}|{cdock.y():.1f}")
            wide = float(cdock.width())
            shown_names = [
                str(lab.property("text"))
                for lab in _collect_named(cdock, "dockButtonLabel")
                if lab.isVisible()
            ]
            check(
                "真机工具栏也按名称文本撑宽（与编辑器预览同一条路径）",
                wide > plain_width + 40 and bool(shown_names),
                f"宽度 {plain_width:.0f} → {wide:.0f} 文本={shown_names}",
            )
            check(
                "撑宽之后重新摆位（居中那条仍然左右对称）",
                abs((geom.width() - wide) // 2 - cdock.x()) <= 1,
                f"x={cdock.x()} 期望={(geom.width() - wide) // 2} "
                f"（条宽 {wide:.0f}，屏幕 {geom.width()}）",
            )
            app.config.set("presentation.buttons.show_labels", labels_prev,
                           persist=False)
            app.backend.reload_from_config()
            _wait_stable(lambda: f"{cdock.width():.1f}|{cdock.x():.1f}")
            check(
                "关掉后真机控制条回到原尺寸原位（自检不留副作用）",
                abs(float(cdock.width()) - plain_width) <= 1
                and abs(cdock.x() - (geom.width() - plain_width) // 2) <= 1,
                f"宽度={float(cdock.width()):.0f}（原 {plain_width:.0f}）x={cdock.x()}",
            )
        for corner, edge in (("middle_left", "left"), ("middle_right", "right")):
            dock = app.windows._docks.get(corner)
            if dock is None:
                continue
            shadow = int(dock.property("shadowMargin") or 0)
            visual_h = (dock.x() + shadow if edge == "left"
                        else geom.width() - (dock.x() + dock.width() - shadow))
            check(
                f"竖版翻页 pill {corner} 视觉贴边距离 = 配置的水平边距",
                abs(visual_h - margin_x) <= 1,
                f"视觉={visual_h} 期望={margin_x} shadow={shadow}",
            )

        # ---- 可见性三要素（「放映时看不见控制条」的根因守卫）----
        # Qt 为了给顶层透明窗口画逐像素 alpha，自己给窗口加了 WS_EX_LAYERED
        # 并走 UpdateLayeredWindow。剥掉这个 bit、或额外调
        # SetLayeredWindowAttributes，都会让窗口「存在但不画」——踩过两次。
        user32 = ctypes.windll.user32
        hwnd = int(overlay.winId())
        style = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
        check(
            "保留 Qt 自带的 WS_EX_LAYERED（透明渲染通道）",
            bool(style & 0x00080000),
            f"exstyle=0x{style:08X}",
        )
        check("Win32 层面窗口可见", bool(user32.IsWindowVisible(hwnd)))
        check("DWM 未把窗口披风化（cloaked=0）", _dwm_cloaked(hwnd) == 0,
              f"cloaked={_dwm_cloaked(hwnd)}")

        # ---- 穿透：首选区域塑形（系统级），兜底才是整窗 WS_EX_TRANSPARENT ----
        if app.windows._region_mode:
            scale = app.windows._region_scale or 1.0
            gdi32 = ctypes.windll.gdi32
            hrgn = gdi32.CreateRectRgn(0, 0, 0, 0)
            got = user32.GetWindowRgn(hwnd, hrgn)
            bdock = app.windows._docks.get("bottom_center")
            hit_rect = app.windows._dock_global_rect(bdock)
            origin = overlay.position()

            def in_region(point) -> bool:
                return bool(gdi32.PtInRegion(
                    hrgn,
                    int((point.x() - origin.x()) * scale),
                    int((point.y() - origin.y()) * scale),
                ))

            center_dock = QPoint(hit_rect.x() + hit_rect.width() // 2,
                                 hit_rect.y() + hit_rect.height() // 2)
            check("区域塑形已挂到窗口上", got != 0)
            check("控制条在区域内（可点击）", in_region(center_dock))
            check(
                "屏幕其它位置在区域外（鼠标落到放映窗口）",
                not in_region(QPoint(geom.width() // 2, 60)),
            )
            gdi32.DeleteObject(hrgn)
        else:
            check(
                "兜底模式：整窗 WS_EX_TRANSPARENT 已开启",
                bool(style & 0x20),
                f"exstyle=0x{style:08X}",
            )
            bdock = app.windows._docks.get("bottom_center")
            hit_rect = app.windows._dock_global_rect(bdock)
            app.windows._update_overlay_hit(hit_rect.center())
            style = user32.GetWindowLongW(hwnd, -20)
            check("光标悬到工具栏上收回穿透", not (style & 0x20), f"rect={hit_rect}")
            app.windows._update_overlay_hit(QPoint(geom.width() // 2, 100))
            style = user32.GetWindowLongW(hwnd, -20)
            check("离开工具栏恢复穿透", bool(style & 0x20))

        check("页码已同步", app.backend.slideIndex == 26 and app.backend.slideTotal == 41,
              f"{app.backend.slideIndex}/{app.backend.slideTotal}")

        # ---- 开发中水印（开发者开关，不进设置页）----
        wm_item = overlay.property("watermarkItem")
        check(
            "开发水印已挂到顶层窗口（左下角）",
            wm_item is not None and wm_item.isVisible(),
            str(type(wm_item).__name__ if wm_item is not None else None),
        )
        check("开发水印开关 = 配置 app.dev_watermark",
              app.backend.devWatermark == (app.config.get("app.dev_watermark") is not False),
              f"backend={app.backend.devWatermark} config={app.config.get('app.dev_watermark')}")
        if app.windows._region_mode and wm_item is not None:
            # 区域塑形模式下，水印若没被算进区域就会整块被裁掉（踩过思路盲区）
            wm_local = app.windows._watermark_rect_local()
            rects = app.windows._dock_rects_local()
            covered = False
            if wm_local is not None:
                from PySide6.QtCore import QRect as _QRect
                wr = _QRect(*wm_local)
                covered = any(wr.intersects(_QRect(*r)) for r in rects)
            check("开发水印在窗口区域内（区域塑形下可见）", covered,
                  f"wm={wm_local} rects={len(rects)}")

        # ---- 遮罩「智能跟随」两件套（2026-10-06 用户指令）----
        # ① 几何跟着放映窗口走；② 放映窗口不在前台时临时隐去。
        # 上面注入的状态没有放映窗口（window_handle=0）→ 遮罩恒整屏、从不隐去，
        # 前面那些整屏贴角断言正是建立在这个前提上。这里用 ``Progman``
        # （铺满桌面的 explorer 桌面窗口、**跨进程**）演一次「全屏放映」。
        progman = int(user32.FindWindowW("Progman", None) or 0)
        check("Progman 窗口可用（跟随 / 前台自检的前置条件）", bool(progman))
        if progman:
            base_rect = app.windows._overlay_rect
            check("无放映窗口时遮罩恒整屏（旧行为不变）", base_rect == geom,
                  f"{base_rect} vs {geom}")
            app.ppt.inject_state(
                PresentationState(active=True, slide_index=26, slide_total=41,
                                  window_handle=progman)
            )
            QTest.qWait(700)
            check(
                "遮罩跟随放映窗口：铺满显示器 → 吸附成整屏矩形",
                app.windows._overlay_rect == geom,
                f"{app.windows._overlay_rect} vs {geom}",
            )
            ex_style = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
            check(
                "放映窗口不在前台 → 临时隐去（淡出 + 整窗穿透，不是 hide）",
                app.windows._suppressed is True
                and overlay.property("suppressed") is True
                and overlay.isVisible() and bool(ex_style & 0x20),
                f"suppressed={app.windows._suppressed} "
                f"QML={overlay.property('suppressed')} "
                f"visible={overlay.isVisible()} exstyle=0x{ex_style:08X}",
            )
            # 把「前台」指到放映窗口自己 → 必须立刻恢复。用判据本身而不是去抢
            # 真前台（``requestActivate`` 在本环境抢不到，会变成假失败）。
            _fg_hook = win_mod._foreground_window
            try:
                win_mod._foreground_window = lambda: progman
                app.windows._watch_overlay()
                QTest.qWait(200)
                ex_style = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
                check(
                    "放映窗口回到前台 → 自动恢复（穿透位收回）",
                    app.windows._suppressed is False
                    and overlay.property("suppressed") is False
                    and not (ex_style & 0x20),
                    f"suppressed={app.windows._suppressed} "
                    f"QML={overlay.property('suppressed')} exstyle=0x{ex_style:08X}",
                )
            finally:
                win_mod._foreground_window = _fg_hook
            app.ppt.inject_state(
                PresentationState(active=True, slide_index=26, slide_total=41)
            )
            QTest.qWait(700)
            check(
                "跟随 / 前台自检已还原（状态与几何回到无窗口形态）",
                app.windows._suppressed is False
                and app.windows._overlay_rect == base_rect,
                f"suppressed={app.windows._suppressed} "
                f"rect={app.windows._overlay_rect} 期望={base_rect}",
            )

        # ---- 工具栏恒横向（下中部）+ 翻页栏独立在两侧（默认：竖版）----
        corners_cfg = app.config.get("presentation.corners", {}) or {}
        center_groups = (corners_cfg.get("bottom_center") or {}).get("groups", [])
        check("工具栏在下中部且不含翻页组",
              "tools" in center_groups and "pager" not in center_groups,
              str(center_groups))
        # 竖版两侧（middle_*）与底部横版（bottom_*）二选一，同时开会四个翻页栏
        side_on = [(corners_cfg.get(c) or {}).get("enabled", False)
                   for c in ("middle_left", "middle_right")]
        bottom_on = [(corners_cfg.get(c) or {}).get("enabled", False)
                     for c in ("bottom_left", "bottom_right")]
        check("翻页栏形态二选一（竖版两侧 或 底部横版，不并存）",
              any(side_on) != any(bottom_on),
              f"middle={side_on} bottom={bottom_on}")
        for corner in ("middle_left", "middle_right"):
            check(f"{corner} 翻页组",
                  ((corners_cfg.get(corner) or {}).get("groups", [])) == ["pager"],
                  str((corners_cfg.get(corner) or {}).get("groups", [])))
        cdock = app.windows._docks.get("bottom_center")
        ldock = app.windows._docks.get("middle_left")
        rdock = app.windows._docks.get("middle_right")
        check(
            "工具栏恒横向（宽大于高）",
            cdock is not None and cdock.width() > cdock.height(),
            f"center={cdock.width()}x{cdock.height()}",
        )
        check(
            "工具栏水平居中（左右余量对称）",
            cdock is not None
            and abs(cdock.x() - (geom.width() - cdock.width() - cdock.x())) <= 2,
            f"x={cdock.x()} w={cdock.width()} screen={geom.width()}",
        )
        check(
            "两侧翻页 pill 等大且是竖版（同一套组件，宽 < 高）",
            ldock is not None and rdock is not None
            and abs(rdock.height() - ldock.height()) <= 1
            and abs(rdock.width() - ldock.width()) <= 1
            and ldock.width() < ldock.height()
            and rdock.x() > ldock.x(),
            f"left={ldock.width() if ldock else '?'}x{ldock.height() if ldock else '?'} "
            f"right={rdock.width() if rdock else '?'}x{rdock.height() if rdock else '?'}",
        )
        # ---- 尺寸档位 = Luminalium 1 的实装值（防止比例被悄悄改回参考稿那套）----
        # 这些值之间的**关系**才是设计语言：按钮直径 = 内容高 = 条高 − 上下内边距×2，
        # 圆角拉满成胶囊，翻页 pill 的留白只有 4（工具条是 8）。
        # 嵌套弧线必须**同心**：外壳帽半径 − 分段帽半径 = 外壳左内边距，
        # 圆心不对齐时弧间空隙宽窄不一，看起来像条诡异的空槽（真机踩过）。
        if cdock is not None:
            cshadow = int(cdock.property("shadowMargin") or 0)
            bar_h = cdock.property("contentHeight") + cdock.property("surfacePaddingY") * 2
            check(
                "控制条档位 = 放大档（条高 62 / 按钮 44 / 图标 22 / 间距 4）",
                bar_h == 62
                and cdock.property("contentHeight") == 44
                and cdock.property("hitSize") == 44
                and cdock.property("iconSize") == 22
                and cdock.property("buttonSpacing") == 4,
                f"条高={bar_h} 内容高={cdock.property('contentHeight')} "
                f"按钮={cdock.property('hitSize')} 图标={cdock.property('iconSize')} "
                f"间距={cdock.property('buttonSpacing')}",
            )
            check(
                "底板是全圆胶囊（圆角 = 条高/2）",
                abs(cdock.property("pillRadius") - bar_h / 2) <= 0.5,
                f"pillRadius={cdock.property('pillRadius')} 期望={bar_h / 2}",
            )
            check(
                "CW2 同款渐变边框高光已开（工具栏）",
                cdock.property("highlightEnabled") is True
                and cdock.property("highlightRingVisible") is True,
                f"enabled={cdock.property('highlightEnabled')} "
                f"ring={cdock.property('highlightRingVisible')}",
            )
            check(
                "竖向分隔线 = 放大档（1×28、两侧各 4）",
                cdock.property("dividerWidth") == 1
                and cdock.property("dividerHeight") == 28
                and cdock.property("dividerGap") == 4,
                f"{cdock.property('dividerWidth')}×{cdock.property('dividerHeight')} "
                f"gap={cdock.property('dividerGap')}",
            )
            # ---- 工具分段：胶囊容器 + 圆形分页（RinUI Segmented 基类）----
            tools_count = len(app.config.get("presentation.tools") or [])
            check(
                "工具分段已接入（分页数 = 配置的 tools 数）",
                cdock.property("segmentItemCount") == tools_count and tools_count > 0,
                f"items={cdock.property('segmentItemCount')} 配置={tools_count}",
            )
            check(
                "分页真的进了 TabBar 容器（count = 配置数，Repeater 接线成立）",
                cdock.property("segmentPageCount") == tools_count,
                f"tabCount={cdock.property('segmentPageCount')} 配置={tools_count}",
            )
            check(
                "分段容器是圆的（胶囊圆角 = 内容高/2）",
                abs(cdock.property("segmentPillRadius") - 44 / 2) <= 0.5,
                f"segmentPillRadius={cdock.property('segmentPillRadius')} 期望=22",
            )
            check(
                "嵌套弧线同心（外壳帽圆心 = 分段帽圆心：paddingX + 22 == 31）",
                cdock.property("surfacePaddingX") + cdock.property("segmentPillRadius")
                == cdock.property("pillRadius"),
                f"paddingX={cdock.property('surfacePaddingX')} + segR="
                f"{cdock.property('segmentPillRadius')} vs shellR={cdock.property('pillRadius')}",
            )
            check(
                "工具栏尺寸（扣除投影余量）",
                cdock.width() - cshadow * 2 > 0 and cdock.height() - cshadow * 2 == 62,
                f"{cdock.width() - cshadow * 2}x{cdock.height() - cshadow * 2}",
            )
        if ldock is not None:
            lshadow = int(ldock.property("shadowMargin") or 0)
            check(
                "竖版翻页 pill = 横版 pill 转置（62×180，同一行账：4+44+8+68+8+44+4）",
                ldock.width() - lshadow * 2 == 62 and ldock.height() - lshadow * 2 == 180,
                f"{ldock.width() - lshadow * 2}x{ldock.height() - lshadow * 2}",
            )
            check(
                "CW2 同款渐变边框高光已开（翻页 pill）",
                ldock.property("highlightEnabled") is True
                and ldock.property("highlightRingVisible") is True,
                f"enabled={ldock.property('highlightEnabled')} "
                f"ring={ldock.property('highlightRingVisible')}",
            )
            check(
                "竖版翻页 pill 垂直居中（上下余量对称）",
                abs(ldock.y() - (geom.height() - ldock.height() - ldock.y())) <= 2,
                f"y={ldock.y()} h={ldock.height()} screen={geom.height()}",
            )

        # ---- 切「翻页组件位置」：当着放映画面把真机控制条**整批重建** ----
        # 这个设置项最容易翻车的就是这一段：换形态不只是挪位置，而是换一整套 QML
        # 组件（SidePager ↔ PresentationDock），必须销毁重建；而且顶层窗口是按
        # 控制条矩形塑形的，形状变了穿透区域也得跟着重算（旧区域留着 = 新的翻页栏
        # 点不动）。编辑器那边（``_check_editor``）只验了「配置 / 预览 / 重建调用」，
        # 真机这一侧得在这儿顶着放映态验。
        pager_prev = str(app.config.get("presentation.pager.position") or "side")
        pager_other = "bottom" if pager_prev != "bottom" else "side"
        swap_on = ("bottom_left", "bottom_right") if pager_other == "bottom" \
            else ("middle_left", "middle_right")

        def _check_live_pagers(shape: str, label: str) -> None:
            left = app.windows._docks.get(swap_on[0])
            right = app.windows._docks.get(swap_on[1])
            if left is None or right is None:
                check(label, False, f"{swap_on} 没建出来（真机={sorted(app.windows._docks)}）")
                return
            if shape == "bottom":
                same_axis = abs(left.y() - right.y()) <= 1
                crossed = left.width() > left.height() and right.width() > right.height()
                axis = f"y=({left.y():.0f},{right.y():.0f})"
            else:
                same_axis = abs(
                    left.y() - (geom.height() - left.height() - left.y())) <= 2
                crossed = left.height() > left.width() and right.height() > right.width()
                axis = f"左边距={left.y():.0f}/对侧={geom.height() - left.height() - left.y():.0f}"
            check(
                label,
                sorted(app.windows._docks) == sorted(["bottom_center", *swap_on])
                and same_axis and crossed
                and left.x() < right.x(),
                f"真机={sorted(app.windows._docks)} {axis} "
                f"左={left.width():.0f}x{left.height():.0f}",
            )

        app.backend.setSetting("presentation_pager_position", pager_other)
        QTest.qWait(150)  # 重建 + 重摆是同步的，给区域塑形一拍
        _check_live_pagers(
            "bottom" if pager_other == "bottom" else "side",
            "切形态后真机控制条整批重建（新形态就位：横版宽>高 / 竖版高>宽）",
        )
        region_rects = app.windows._dock_rects_local()
        if app.windows._region_mode:
            check(
                "区域塑形按重建后的矩形重算（新的翻页栏照样点得动）",
                app.windows._last_region_rects
                == tuple(tuple(r) for r in region_rects) and len(region_rects) >= 3,
                f"已应用={app.windows._last_region_rects} "
                f"期望={tuple(tuple(r) for r in region_rects)}",
            )

        app.backend.setSetting("presentation_pager_position", pager_prev)
        QTest.qWait(150)
        swap_on = ("bottom_left", "bottom_right") if pager_prev == "bottom" \
            else ("middle_left", "middle_right")
        _check_live_pagers(
            "bottom" if pager_prev == "bottom" else "side",
            "还原后真机控制条回到原形态（自检不留副作用）",
        )

        # ---- 模拟退出放映：顶层窗口整体隐藏 ----
        app.ppt.inject_state(PresentationState(active=False))
        check(
            "退出放映后顶层窗口隐藏",
            app.windows.overlay is not None and not app.windows.overlay.isVisible(),
        )

        # ---- 手动显示：探测认不出放映窗口时的兜底（托盘菜单走这条路）----
        app.windows.toggle_docks_manual()
        check(
            "手动可显示控制条（不依赖探测）",
            app.windows.overlay is not None and app.windows.overlay.isVisible(),
        )
        app.windows.toggle_docks_manual()
        check("手动可再次隐藏控制条", not app.windows.overlay.isVisible())

        # ---- 探测规则来自配置（改配置即改探测，不写死在代码里）----
        check(
            "放映窗口类名白名单已从配置加载",
            "screenclass" in ppt_controller.SLIDESHOW_WINDOW_CLASSES,
            str(sorted(ppt_controller.SLIDESHOW_WINDOW_CLASSES)),
        )
        check(
            "放映进程名白名单已从配置加载",
            "POWERPNT.EXE" in ppt_controller.SLIDESHOW_PROCESS_NAMES,
            str(sorted(ppt_controller.SLIDESHOW_PROCESS_NAMES)),
        )
        # 回归守卫：GetClassNameW 不支持「传 NULL 查长度」，写错会静默返回
        # 空串 —— 窗口类探测整条链路失效，而日志上只表现为「没检测到放映」。
        named = [c for _h, c, *_ in ppt_controller._enum_windows() if c]
        check(
            "窗口类名探测可用（GetClassName 未静默失效）",
            len(named) > 0,
            f"{len(named)} 个窗口取到类名，例: {named[:3]}",
        )

        # ---- 多软件族（kind）路由：照 Luminalium 1 的 ppt / wps / yozo 三分 ----
        # 这是「换台电脑就控制不了」的主因：判不出族就选不对快捷键通道，
        # 给 WPS 下 PowerPoint 专属的 MSO 命令只会白等一轮。
        kind_cases = [
            ("screenClass", "POWERPNT.EXE", "演示文稿1", "ppt"),
            ("wppSlideShowWindowClass", "wpp.exe", "x", "wps"),
            ("WPP SlideShow Window 8.0", "wps.exe", "x", "wps"),
            ("YozoSlideShow", "yozopg.exe", "x", "yozo"),
            ("SomeUnknownClass", "powerpnt.exe", "x", "ppt"),  # 类名不认识时靠进程名
        ]
        kind_bad = [
            (cls, proc, wanted, ppt_controller._kind_from_window(cls, proc, title))
            for cls, proc, title, wanted in kind_cases
            if ppt_controller._kind_from_window(cls, proc, title) != wanted
        ]
        check(
            "软件族判定（类名 → 进程名，PowerPoint / WPS / 永中）",
            not kind_bad,
            f"错误 {len(kind_bad)} 例: {kind_bad}" if kind_bad else
            "，".join(f"{c}->{ppt_controller._kind_from_window(c, p, t)}"
                      for c, p, t, _w in kind_cases),
        )
        # 各族**必须有**的快捷键：Pen 只有 ppt/wps 有（Ctrl+P），
        # 永中只发它认得的 E/A —— 给永中发 Ctrl+P 是无效动作。
        check(
            "快捷键通道按族区分（永中不发 Ctrl+P）",
            all(v["arrow"] == ord("A") and v["eraser"] == ord("E")
                for v in ppt_controller.KIND_TOOL_SHORTCUTS.values())
            and "pen" in ppt_controller.KIND_TOOL_SHORTCUTS["ppt"]
            and "pen" in ppt_controller.KIND_TOOL_SHORTCUTS["wps"]
            and "pen" not in ppt_controller.KIND_TOOL_SHORTCUTS["yozo"],
            str({k: {n: chr(v) for n, v in t.items()}
                 for k, t in ppt_controller.KIND_TOOL_SHORTCUTS.items()}),
        )
        # 指针重试阶梯必须与 L1 逐字一致（省掉重试 = 笔/橡皮切换时好时坏的根源）
        check(
            "指针切换重试阶梯 = Luminalium 1 原值",
            ppt_controller.L1_POINTER_RETRY_DELAYS == (0.0, 0.08, 0.16, 0.28),
            str(ppt_controller.L1_POINTER_RETRY_DELAYS),
        )
        # 指针语义必须与 COM 的 PpSlideShowPointerType 对齐 —— **官方表**：
        # 0=None 1=Arrow 2=Pen 3=AlwaysHidden 4=AutoArrow **5=Eraser**。
        # ⚠️ 这条守卫曾把错的旧值（eraser=3）钉成「正确」，真机「切橡皮没光标、
        # 行为像指针」就是它放行的 —— 3 是 AlwaysHidden，PowerPoint 把指针藏了。
        # 教训：钉常量之前先对官方文档，别对着当时的实现对个爽。（2026-10-02 修正）
        check(
            "工具 -> 指针类型映射 = PpSlideShowPointerType（官方表，橡皮=5）",
            (ppt_controller.TOOL_TO_POINTER["none"],
             ppt_controller.TOOL_TO_POINTER["arrow"],
             ppt_controller.TOOL_TO_POINTER["pen"],
             ppt_controller.TOOL_TO_POINTER["eraser"]) == (0, 1, 2, 5),
            str(ppt_controller.TOOL_TO_POINTER),
        )
        # 清屏的「补发 E」：``View.EraseDrawing()`` 是**隐藏**墨迹（已知 bug，
        # 下一笔会把隐藏 undo 回来 —— 用户实锤「清屏后再写新东西旧残余显形」；
        # 键盘 E 才是真删）。PowerPoint 族 COM 擦除后必须补发一次 E。
        # 真机行为进不了 smoke，这里钉源码形态：``clear_screen`` 要把 kind
        # 传进 COM 线程、``_cmd_clear`` 里要有「PPT 族补发按键」这一步。
        clear_src = (ROOT / "app" / "ppt_controller.py").read_text(encoding="utf-8")
        clear_body = clear_src.split("def _cmd_clear", 1)[-1].split("\n    def ", 1)[0]
        kind_passed = 'self._com.request("clear", int(hwnd or 0), self._state.kind)' \
            in clear_src
        clear_ok = (kind_passed
                    and "kind == APP_KIND_PPT" in clear_body
                    and "send_slideshow_key(VK_ERASE" in clear_body)
        check(
            "清屏在 PowerPoint 族补发键盘 E（EraseDrawing 只是隐藏墨迹）",
            clear_ok,
            "" if clear_ok else
            ("clear_screen 未传 kind" if not kind_passed
             else "_cmd_clear 里找不到「PPT 族补发 E」"),
        )
        # 笔选单的色板：2026-10-01 起**配置是唯一来源**（选单从
        # ``presentation.pen.palette`` 建格子，QML 里那张 ``inkPalette`` 已删）。
        # 前 20 色仍是 PowerPoint 自己的 InkColorPicker 网格 —— 改坏了「看着
        # 没错、选出来与 PowerPoint 原生调色板对不上」，所以照样逐格钉住。
        _default_cfg = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
        pen_cfg = _default_cfg.get("presentation", {}).get("pen", {}) or {}
        palette = [str(c).upper() for c in (pen_cfg.get("palette") or [])]
        expected_palette = [
            # 第 1 行：Office 主题色
            "#FFFFFF", "#000000", "#E7E6E6", "#44546A", "#4472C4",
            "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47",
            # 第 2 行：Office 标准色
            "#C00000", "#FF0000", "#FF8C00", "#FFFF00", "#92D050",
            "#00B050", "#00B0F0", "#0070C0", "#002060", "#7030A0",
            # 第 3 行：扩展档（鲜艳色）
            "#FF5B5B", "#FF9F45", "#FFE066", "#7CE38B", "#2FBF71",
            "#38BDF8", "#6366F1", "#A855F7", "#EC4899", "#14B8A6",
        ]
        check(
            "笔选单色板 = 30 色（3 行 Office 主题色 + 标准色 + 扩展档）",
            palette == expected_palette,
            f"{len(palette)} 色" + ("" if palette == expected_palette
                                    else f"，期望 {len(expected_palette)} 色"),
        )
        # 色板必须**整除列数**：``columns`` 就是选单网格的列数（``Grid.columns``），
        # 30 色配 10 列 = 整整三行；写成 9 列会余出一行零头（最后一行稀稀拉拉）。
        pen_columns = int(pen_cfg.get("columns") or 0)
        check(
            "色板能被列数整除（网格排得满行）",
            pen_columns > 0 and len(palette) % pen_columns == 0
            and len(palette) // pen_columns >= 2,
            f"{len(palette)} 色 / {pen_columns} 列",
        )
        # 预点亮的默认色必须是色板里的一格 —— 否则选单一弹出来，没有任何一格
        # 带着选中环，而「预览」却是一条有颜色的笔迹，看着自相矛盾。
        check(
            "默认选中色在色板里（选单弹出来有一格带环）",
            str(pen_cfg.get("default", "")).upper() in palette,
            f"default={pen_cfg.get('default')!r}",
        )
        # 切指针前必须先把放映窗口拉到前台 —— PowerPoint 的 View.PointerType
        # 只对前台放映窗口生效，漏这一步「橡皮点了没反应」（2026-09-25 用户报障）。
        # 用源码断言：set_pointer 内出现 focus_slideshow_window 调用。
        ctrl_src = (ROOT / "app" / "ppt_controller.py").read_text(encoding="utf-8")
        set_pointer_body = ctrl_src.split("def set_pointer(", 1)[-1].split("def ", 1)[0]
        check(
            "切指针前先拉放映窗口到前台（L1 _focus_slideshow_window）",
            "focus_slideshow_window(" in set_pointer_body,
            "set_pointer 缺少 focus_slideshow_window 前置调用",
        )
        check(
            "前台激活辅助函数存在",
            hasattr(ppt_controller, "focus_slideshow_window"),
            "缺少 focus_slideshow_window",
        )
        # 页码刷新必须走轻量路径（跳过描述 / 墨迹色两次诊断读），否则命令后
        # 页码要多等一个 COM 周期，观感就是「页码识别迟钝」。
        refresh_body = ctrl_src.split("def _refresh_snapshot(", 1)[-1].split("def ", 1)[0]
        check(
            "_refresh_snapshot 支持轻量刷新（light）",
            "light: bool = False" in refresh_body and "if light:" in refresh_body,
            "缺少 light 参数分支",
        )
        # 轻量刷新走 read_position（只读当前页），不重读总页数 —— 总页数在场内是常量
        check(
            "COM 后端提供轻量页码读 read_position",
            hasattr(ppt_controller._ComBackend, "read_position"),
            "缺少 _ComBackend.read_position",
        )
        # ⚠️ SlideShowWindows 绝不能直接属性访问：动态绑定下它会抛 AttributeError
        # （真机日志里刷屏的那条），必须走 getattr 安全取 + _safe_count。
        # 这条断言锁住「不许再写回 app.SlideShowWindows.Count」。
        # 先剔除 docstring / 注释，只留下真正的代码文本再断言。
        import io as _io
        import tokenize as _tokenize
        code_parts = []
        for _tok in _tokenize.generate_tokens(_io.StringIO(ctrl_src).readline):
            if _tok.type not in (_tokenize.STRING, _tokenize.COMMENT):
                code_parts.append(_tok.string)
        code_only = " ".join(code_parts)
        check(
            "无 bare `app.SlideShowWindows` 直接访问（必须 getattr 兜底）",
            "app.SlideShowWindows" not in code_only,
            "又出现了直接属性访问，动态绑定下会抛 AttributeError",
        )
        check(
            "SlideShowWindows 改用 _slideshow_windows() 取集合",
            "_slideshow_windows(" in ctrl_src and "_safe_count(" in ctrl_src,
            "缺少 _slideshow_windows / _safe_count",
        )
        # 取不到集合时要能换一个新引用再试（半吊子 COM 引用重取常可修好）
        check(
            "_attached 支持 force_refresh（换新引用补救）",
            "force_refresh" in ctrl_src,
            "缺少 force_refresh 参数",
        )

        # ---- 设置窗口（懒创建）----
        check("设置窗口尚未创建", app.windows.settings is None)
        app.windows.show_settings()
        settings = app.windows.settings
        check("设置窗口已创建", settings is not None)
        if settings is not None:
            # 设置窗口的水印：FluentWindow 内容走 default property
            # （freeContainter），匿名 QML 类型的 type 名是 QQuickItem，
            # 只能用「自定义属性 shown」来认它。断言它在窗口边界内 ——
            # 曾把 leftMargin 用成 navigationView.width（那是整窗宽度的
            # 内部项），水印被推到窗口外只剩一条边（2026-09-25）。
            def _find_wm(item):
                for child in item.childItems():
                    if child.property("shown") is not None:
                        return child
                    found = _find_wm(child)
                    if found is not None:
                        return found
                return None

            wm_st = _find_wm(settings.contentItem())
            check(
                "设置窗口水印存在且在窗口边界内",
                wm_st is not None
                and wm_st.x() >= 0
                and wm_st.x() + wm_st.width() <= settings.width()
                and wm_st.y() + wm_st.height() <= settings.height(),
                "未找到" if wm_st is None else
                f"pos=({wm_st.x()},{wm_st.y()}) size={wm_st.width()}x{wm_st.height()}",
            )
        if settings is not None:
            area = QGuiApplication.primaryScreen().availableGeometry()
            inside = (
                area.left() <= settings.x()
                and settings.x() + settings.width() <= area.right() + 1
                and area.top() <= settings.y()
                and settings.y() + settings.height() <= area.bottom() + 1
            )
            check(
                "设置窗口位于屏幕内",
                settings.isVisible() and inside,
                f"pos=({settings.x()},{settings.y()}) size={settings.width()}x{settings.height()}",
            )
            # 默认尺寸（2026-10-01 用户指令「默认尺寸宽高大一些，横纵比例大一些」）：
            # 口径在 ``config/default_config.json`` 的 ``settings`` 段（0.64 / 0.68，
            # 硬下限 1000 / 640）。这里按**同一套公式**拿真机屏幕尺寸复算一遍，
            # 确认 QML 的绑定真的吃到了配置 —— 只断言「比 900 宽」这种弱条件拦不住
            # 「改了配置没生效」。
            #
            # ⚠️ 容差 ±16 是因为 ``QWindow::width()`` 在 Windows 上把**不可见 resize
            # 边框**也算了进来，比 QML 里 ``width`` 大一圈。实测（本机 DPR 1.75）：
            # 请求 1000×700 → 实际 1013×713、请求 1400×900 → 实际 1413×913，恒 +13
            # —— **不是** QML 没吃到配置（QML 侧表达式实测就是 1123.2×671.16）。
            # 口径若被改回 0.5/0.6，偏差是 200+，照样炸。
            screen_size = settings.screen().geometry()
            sw, sh = screen_size.width(), screen_size.height()
            exp_w = min(sw - 80, max(1000, sw * 0.64))
            exp_h = min(sh - 120, max(640, sh * 0.68))
            size_ok = (abs(settings.width() - exp_w) <= 16
                       and abs(settings.height() - exp_h) <= 16)
            check(
                "设置窗口默认尺寸更大、更宽（0.64 / 0.68）",
                size_ok,
                "" if size_ok else (
                    f"实测 {settings.width():.0f}x{settings.height():.0f} "
                    f"期望 {exp_w:.0f}x{exp_h:.0f}（屏幕 {sw}x{sh}）"
                ),
            )
            # Win32 原生边框：**2026-09-30 起由 RinUI 接管**，不再自己摘 flags。
            #
            # RinUI 的窗口外观全靠两处 Win32 侧代码：WinEventFilter 处理
            # WM_NCCALCSIZE（把非客户区压掉 → 视觉上只剩 RinUI 自绘标题栏）＋
            # 处理 WM_NCHITTEST（8px resize 边框 / 拖动）；ThemeManager 按 hwnd
            # 逐个设 DWM 属性（阴影 / 圆角 / 暗色 / backdrop）。两份名单都只在
            # launcher.load() 那一刻确定，Python 侧另建的窗口必须靠
            # WindowManager._attach_to_rinui 补登记。
            #
            # 所以这里断言的是「三件事同时成立」：style 必须带
            # WS_CAPTION|WS_THICKFRAME（DWM 阴影与系统 resize 的前提）＋ hwnd 必须
            # 在 WinEventFilter 与 ThemeManager 的名单里（否则前者没人压非客户区，
            # 后者没有阴影/圆角）。只满足前一半就是当初那个 bug：CAPTION 加上却
            # 没人处理，真的画出一条原生标题栏压在自绘标题栏上。
            settings_hwnd = int(settings.winId())
            user32b = ctypes.windll.user32
            style = user32b.GetWindowLongW(settings_hwnd, -16) & 0xFFFFFFFF
            filter_hwnds = {int(h) for h in app.rinui.win_event_filter.hwnds.values()}
            theme_hwnds = {int(h) for h in app.rinui.theme_manager.windows}
            corner = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                settings_hwnd, ctypes.c_uint(33), ctypes.byref(corner), ctypes.sizeof(corner)
            )
            check(
                "设置窗口已交给 RinUI 管（WS_CAPTION|WS_THICKFRAME）",
                bool(style & 0x00C00000) and bool(style & 0x00040000),
                f"style=0x{style:08X} WS_CAPTION={'Y' if style & 0x00C00000 else 'N'} "
                f"WS_THICKFRAME={'Y' if style & 0x00040000 else 'N'}",
            )
            check(
                "设置窗口在 WinEventFilter / ThemeManager 名单里",
                settings_hwnd in filter_hwnds and settings_hwnd in theme_hwnds,
                f"hwnd={settings_hwnd} filter={'Y' if settings_hwnd in filter_hwnds else 'N'} "
                f"theme={'Y' if settings_hwnd in theme_hwnds else 'N'}",
            )
            check(
                "设置窗口有 DWM 圆角（corner_preference=Round）",
                corner.value == 2,
                f"corner={corner.value}（0=Default / 2=Round）",
            )
            # 设置首页（2026-10-05 用户指令「设置的主页参考一下 Class Widgets 2
            # …… 一比一复刻」）：通栏横幅 + 大标题 + 警告 InfoBar + 两张 220×128
            # 的链接卡（CW2 的 ``Component card``）。初始页就是 Home，趁窗口还
            # 开着查树。
            #
            # ⚠️ 横幅是**异步**加载的（4.2MB / 4628×2512 的 PNG）：``Image`` 有
            # ``asynchronous: true``，这里等它真的画出来（``paintedWidth > 0``）再断言，
            # 否则会拿到「图在、但还没画」的假失败。
            banner = _wait_named(settings.contentItem(), "homeBannerImage")
            banner_src = ""
            banner_y = -1
            banner_settled = True
            painted_w = 0
            if banner is not None:
                painted_w = _wait_property(banner, "paintedWidth",
                                           lambda value: value > 0, timeout_ms=6000)
                banner_src = banner.property("source").toString()
                # 2026-10-05 banner y 竞态修复：paintedWidth>0 只说明图画出来了，
                # 页面入场转场可能还在跑，立刻量 y 会拿到动画中间态（四次运行量出
                # 267/313/366/385）。先等位置沉淀（连续 300ms |Δy|<2）再读；
                # 超时 3s 用最后一次值，并在下方输出里注明。
                banner_y, banner_settled = _wait_position_settled(
                    lambda: banner.mapToItem(settings.contentItem(), 0, 0).y())
            banner_ok = (
                banner is not None
                and banner.isVisible()
                # 2026-10-05：首页横幅已切到通栏专用的 banner-wide.png
                # （Home.qml 头注释），banner.png 旧图保留在 resources/ 里，
                # 两个名字都认，语义不变（「横幅真的挂上并画出来了」）。
                and banner_src.endswith(("banner.png", "banner-wide.png"))
                and painted_w > 100
                # 「横幅在内容区顶部」——只拦「图没挂上」和「掉到卡片区去了」
                # （卡片区在 y≈510+）。⚠️ 2026-10-05：bound 由 280 放宽到 500，
                # 依据探针实据（.omo/evidence/smoke-banner-probe.py）：窗口
                # 2026-10-01 按用户指令放大（0.68 高比）后标题栏+页头开销变大，
                # 真窗口沉淀值实测 y≈385（曝光+激活状态下 5s 零漂移），旧 280
                # 是按旧小窗口写的（当时实测 y≈90）。断言语义不变：拦的是
                # 「掉进卡片区」，500 仍紧贴在 510 之下。
                and 0 <= banner_y < 500
            )
            check(
                "设置首页挂了 banner.png 通栏横幅（且真的画出来了）",
                banner_ok,
                ("" if banner_ok else (
                    f"banner={'无' if banner is None else '有'} "
                    f"visible={banner is not None and banner.isVisible()} "
                    f"src={banner_src!r} paintedWidth={painted_w:.0f} y={banner_y:.0f}"
                )) + ("" if banner_settled else "（沉淀等待超时，取最后一次值）"),
            )

            # 大标题在横幅上（CW2：Typography.Title 的「Home」，leftMargin 56 /
            # topMargin 38）；页面本体不带 title，头部塌成 0。
            page_root = _find_named(settings.contentItem(), "Home")
            page_title = page_root.property("title") if page_root is not None else None
            banner_title = _find_named(settings.contentItem(), "homeBannerTitle")
            title_ok = (
                page_title == ""
                and banner_title is not None
                and banner_title.isVisible()
                and str(banner_title.property("text")) == "主页"
            )
            check(
                "设置首页大标题压在横幅上（页面本体不带标题）",
                title_ok,
                "" if title_ok else (
                    f"page title={page_title!r} "
                    f"banner title={'无' if banner_title is None else banner_title.property('text')!r}"
                ),
            )

            # 警告 InfoBar（CW2 主页同款 Severity.Warning；``closable`` 用默认
            # 的 true —— CW2 也没写这一项，右上角关闭按钮是它交互的一部分）。
            info_bar = _find_named(settings.contentItem(), "homeWarningBanner")
            check(
                "设置首页挂了警告信息条",
                info_bar is not None and info_bar.isVisible()
                and info_bar.property("closable") is True,
                "未找到" if info_bar is None else
                f"visible={info_bar.isVisible()} closable={info_bar.property('closable')}",
            )

            # 两张 220×128 链接卡（GitHub / 反馈），点击整卡开外链 —— 链接与
            # 「关于」页同一份口径。⚠️ 自检**不真点**：那会真的拉起浏览器。
            card_urls = []
            for index in range(2):
                card = _find_named(settings.contentItem(), f"homeLinkCard{index}")
                if card is not None:
                    card_urls.append(str(card.property("linkUrl")))
            cards_ok = (
                len(card_urls) == 2
                and card_urls[0].endswith("/SECTL/Luminalium-2")
                and card_urls[1].endswith("/SECTL/Luminalium-2/issues/new/choose")
            )
            check(
                "设置首页有两张链接卡（仓库 / 反馈）",
                cards_ok,
                f"urls={card_urls}",
            )

            app.backend.settingsCloseRequested.emit()
            check("设置窗口可关闭", not settings.isVisible())

            # 打开指定设置页（``open_settings:<相对路径>`` 那条路径 —— 快捷方式
            # 「设置」就是这么落到 ``settings/Home.qml`` 的）。
            #
            # ⚠️ 这里**必须**用 ``_wait_named`` 等页面真的换过来，再关窗：
            # ① push 是异步的，固定时长会假失败（见 ``_wait_named`` 注释）；
            # ② 别在 push 还没落地时就把窗口隐藏 —— 转场靠渲染推进，窗口一隐，
            #    初始页的转场就悬着，后面那次 push 会被拖到很久之后才生效
            #    （2026-10-01 这一条把「关于页英雄区」整段自检拖挂）。
            #
            # 2026-10-01（第四轮）拿**新建的「个性化」页**跑这条：它最年轻、
            # 最可能因为路径写错 / 少了 import 而整页加载失败（那种失败在这一条
            # 里表现为「窗口可见但没切页」，比渲染一张图更容易看出来）。
            app.windows.show_settings("settings/Personalization.qml")
            QTest.qWait(120)  # 先让窗口出一帧，push 才走得动
            page_switched = _wait_named(settings.contentItem(), "Personalization") is not None
            check(
                "能跳到指定设置页（页面真的换过来了）",
                settings.isVisible() and page_switched,
                # detail 无论成败都会打印，所以只在失败时给「为什么」
                "" if (settings.isVisible() and page_switched) else (
                    "窗口可见但没切页" if settings.isVisible() else "窗口不可见"
                ),
            )
            app.backend.settingsCloseRequested.emit()

        # ---- 设置页「关于」的流光英雄区（2026-10-01 用户指令）----
        #
        # 这里两个坑都踩过，而且**都不报错、预览图上也只能靠肉眼比**，所以
        # 各钉一条断言：
        #   ① ``RotationAnimator`` 在本环境里**静默不动**（渲染线程动画拿不到
        #      渲染帧；同一个窗口里 ``NumberAnimation`` 正常走）→ 不钉的话
        #      「流光」就是一张静图；
        #   ② Qt5Compat 的 ``DropShadow { source: X }`` 会把 X **也画一遍**
        #      （输出 = X + 影子，和 ``Glow`` 同行为）→ Logo 直接亮一倍；
        #   ③ 设置页跳转是**异步**的（``NavigationView.push`` 挂在
        #      ``Qt.callLater`` 上，实测 0.6~2s 才落地）→ 固定 ``qWait`` 会
        #      假失败成「页面整个不存在」。
        # 详见 ``GlassLogo.qml`` / ``AuroraFlow.qml`` 的头注释，探针在
        # ``J:/tmp/l1probe/``（probe_anim4.py 是 Animator 的隔离实验，
        # probe_grabs.py 是逐层 grabToImage 量 alpha，
        # probe_about4.py 是 push 落地时间的四组对照）。
        app.windows.show_settings("settings/About.qml")
        page_st = settings.contentItem()
        # 同「能跳到指定设置页」：push 是异步的，轮询等页面落地（实测 0.6~2s）
        hero_st = _wait_named(page_st, "aboutHero")
        aurora_st = _find_named(page_st, "aboutAurora")
        logo_st = _find_named(page_st, "aboutLogo")
        check(
            "关于页英雄区存在且高 = Lumi.aboutHeroHeight",
            hero_st is not None and round(hero_st.height()) == 320,
            "未找到" if hero_st is None else f"height={hero_st.height()}",
        )
        missing_st = [
            n for n in ("aboutLogoMask", "aboutLogoBefore", "aboutLogoSheen",
                        "aboutLogoGlowShape")
            if _find_named(page_st, n) is None
        ]
        check(
            "关于页 Logo 四层齐全（蒙版 / ::before / ::after / 光晕形状）",
            not missing_st,
            f"缺 {missing_st}",
        )
        # 英雄区**右下角**的 YUNOFACTORY 署名字标（2026-10-05 用户指令）。
        # 与 Logo 同一套「混色」（``GlassLogo`` 的两层白渐变按剪影蒙形），钉四件事：
        #   ① 混色那两层在（``::before`` / ``::after``）；
        #   ② 光晕与整体投影**刻意关掉** —— 模糊半径按 248 的 Logo 配的，压在
        #      150×23 的字标上糊成一团，且容器外撑的 3σ 会越过英雄区的圆角；
        #   ③ ``layerPrefix`` 分开了。两个实例内部的 ``objectName`` 本来一模一样，
        #      重名之后上面那条「Logo 四层」按名字找会翻到字标那几层上 ——
        #      **找得到**，只是量错了东西，所以这条得钉住前缀本身；
        #   ④ 真的贴右下角（量坐标，不能只看 ``visible``）。
        credit_st = _find_named(page_st, "aboutCredits")
        check(
            "关于页英雄区右下角有署名字标（YUNOFACTORY）",
            credit_st is not None,
            "" if credit_st is not None else "未找到 aboutCredits",
        )
        if credit_st is not None:
            c_layers = [n for n in ("aboutCreditsMask", "aboutCreditsBefore",
                                    "aboutCreditsSheen")
                        if _find_named(page_st, n) is None]
            c_plain = (credit_st.property("glowEnabled") is False
                       and credit_st.property("shadowEnabled") is False)
            c_prefix = (credit_st.property("layerPrefix") == "aboutCredits"
                        and logo_st is not None
                        and logo_st.property("layerPrefix") == "aboutLogo")
            check(
                "字标：混色两层在 / 光晕与投影关掉 / objectName 前缀与 Logo 分开",
                not c_layers and c_plain and c_prefix,
                "" if (not c_layers and c_plain and c_prefix) else (
                    f"缺层={c_layers} 光晕开启={not c_plain} 前缀={c_prefix}"
                ),
            )
            # 贴角：右下各留 ``Lumi.aboutCreditsMargin``。两处都从**页面**坐标系
            # 量（hero 与字标各自 mapToItem 到 page），免得被各自的父级偏置换算；
            # 转场期间整页平移，两个点同进同出，差值不受影响。
            c_br = credit_st.mapToItem(page_st, QPointF(float(credit_st.width()),
                                                        float(credit_st.height())))
            h_br = hero_st.mapToItem(page_st, QPointF(float(hero_st.width()),
                                                      float(hero_st.height())))
            gap_r, gap_b = h_br.x() - c_br.x(), h_br.y() - c_br.y()
            want_gap = 20  # Lumi.aboutCreditsMargin
            # 顺带钉住宽高比（素材 4687:734）—— 拉变形在预览图上看着也「对」。
            want_ratio = 4687 / 734
            got_ratio = credit_st.width() / max(1e-6, credit_st.height())
            ok_gap = abs(gap_r - want_gap) <= 1.5 and abs(gap_b - want_gap) <= 1.5
            ok_ratio = abs(got_ratio - want_ratio) <= 0.02
            check(
                "字标贴在英雄区右下角（右边距 = 下边距 = 20，且不拉变形）",
                ok_gap and ok_ratio,
                "" if (ok_gap and ok_ratio) else (
                    f"右边距={gap_r:.1f} 下边距={gap_b:.1f}（期望 {want_gap}）"
                    f" 宽高比={got_ratio:.3f}（期望 {want_ratio:.3f}）"
                ),
            )
        # 等页面滑入转场收尾：转场期间 ``mapToItem`` 的坐标还在动，
        # 后面按星心坐标取像素会取到隔壁。
        QTest.qWait(300)

        # 页面**不带**大标题（2026-10-01 用户指令「把关于大标题去掉」）。
        # ``FluentPage`` 的头部高度 = ``title !== "" ? 36 + 44 : 0``，所以
        # 「去掉标题」必须是「头部一起塌成 0」——只清空 ``title`` 而留着 80px
        # 空白是另一种观感，别混。左侧导航里的「关于」项是另一回事，照旧有。
        #
        # ⚠️ 页面根要按 **``About``** 找，不能按 ``FluentPage`` 找：
        # ``NavigationView.asyncPush`` 会 ``stackView.replace(..., {objectName:
        # <文件名>})``，把页面根的 objectName **覆盖**成文件名；树里那个叫
        # ``FluentPage`` 的其实是 ``Page.contentItem``（没有 ``title``/``header``
        # 属性，按它取属性只会拿到 ``None``，看起来像「标题还在」）。
        fp_st = _find_named(page_st, "About")
        hdr_st = fp_st.property("header") if fp_st is not None else None
        page_title = fp_st.property("title") if fp_st is not None else None
        no_title = (fp_st is not None and page_title == ""
                    and hdr_st is not None and round(hdr_st.height()) == 0)
        check(
            "关于页没有页面大标题（头部一起塌成 0）",
            no_title,
            "" if no_title else (
                f"页面根={'未找到' if fp_st is None else 'About'} "
                f"title={page_title!r} "
                f"header高={None if hdr_st is None else hdr_st.height()}"
            ),
        )
        if aurora_st is not None:
            # 25s 一圈 → 1.5s 应该走 ~21.6°；只要求「明显在动」。
            # ⚠️ 但**不能只采两拍**：QML 动画由渲染循环推进，设置窗口一旦被遮挡 /
            # 没被系统暴露，时钟就走得极慢（实测读到 3.6°→6.1°，看着像「动画坏了」，
            # 其实只是没曝光）—— 与相机那几处同一个坑。所以这里改成轮询「等到真的
            # 动了」，中途抬窗催曝光（``_nudge_*`` 同款做法）。换成 ``RotationAnimator``
            # 的话角度永远不动，轮询超时后照样 FAIL，拦截力不变。
            a0 = float(aurora_st.property("angle"))
            a1 = a0
            waited = 0
            while waited < 5000 and abs(a1 - a0) <= 5.0:
                QTest.qWait(250)
                waited += 250
                a1 = float(aurora_st.property("angle"))
                if waited % 1250 == 0:  # 催一次曝光（遮挡时渲染循环会卡住）
                    settings.raise_()
                    settings.requestActivate()
            check(
                "流光的自转真的在走（⚠️ 别换回 RotationAnimator）",
                abs(a1 - a0) > 5.0,
                f"{a0:.1f}° → {a1:.1f}° / {waited / 1000:.2f}s（1.5s 期望 ≈ 21.6°）",
            )
            spread_st = float(aurora_st.property("spread"))
            check(
                "流光的呼吸缩放落在 1.0 ~ 1.1",
                0.999 <= spread_st <= 1.101,
                f"spread={spread_st:.4f}",
            )
        if logo_st is not None and aurora_st is not None:
            # 星心亮度基准来自 L1 参考图（见 GlassLogo.qml 头注释的「自检基准」）。
            # 容差 45 足够拦住「重复绘制」那种 +70/通道 的偏差，又不会被主题或
            # 强调色的小改动碰倒。
            dpr_st = settings.devicePixelRatio()
            shot_st = settings.grabWindow()
            dark_st = app.rinui.theme_manager.is_dark_theme()
            base_st = (124, 131, 163) if dark_st else (234, 234, 243)
            ctr = logo_st.mapToItem(page_st,
                                    QPointF(logo_st.width() / 2,
                                            logo_st.height() / 2))
            got_st = shot_st.pixelColor(int(ctr.x() * dpr_st),
                                        int(ctr.y() * dpr_st)).getRgb()[:3]
            check(
                "Logo 星心亮度贴近 L1 参考（拦「重复绘制 → 亮一倍」）",
                all(abs(got_st[i] - base_st[i]) <= 45 for i in range(3)),
                f"实测 {got_st} 参考 {base_st} "
                f"主题={'dark' if dark_st else 'light'}",
            )
        # ---- 关于页的**内容卡**（2026-10-01 用户指令「参考 Class Widgets 2 的
        #      关于界面的那个设置卡，填充关于界面的内容」）----
        #
        # 版式照 CW2 的主卡（``SettingExpander`` + 一串 ``SettingItem``），内容
        # 换成本项目的真实信息（MIT / Qt 系 / Seirai Haraguchi 署名）。四条各钉
        # 一件事：
        #   ① ``Rin.SettingExpander`` 是**本项目第一次用**的组件，RinUI 升级把
        #      它改没了的话这条会先炸；
        #   ② 头部右栏的徽章 / 版本号**来自后端**（``Backend.appChannel`` /
        #      ``appVersion`` / ``devCodename``），写死的会在升版本或换渠道后
        #      过期。用户口径：徽章**只**分 Dev / Release，开发代号跟版本号后面
        #      的括号里；
        #   ③ 折叠区默认展开（关于页进来就是来看这些的）;
        #   ④ 两条被用户逐字指定的版式：「仓库地址在打开按钮的左边（等宽字体）」、
        #      「依赖与参考的标题和内容上下换行」—— 都是**布局方向**，改错了在
        #      截图上也未必一眼看出，所以直接量坐标。
        app_card_st = _find_named(page_st, "aboutAppCard")
        check(
            "关于页有应用信息卡（SettingExpander）",
            app_card_st is not None,
            "" if app_card_st is not None else "未找到 aboutAppCard",
        )
        ver_st = _find_named(page_st, "aboutVersionText")
        badge_st = _find_named(page_st, "aboutChannelBadge")
        got_ver = ver_st.property("text") if ver_st is not None else ""
        got_badge = badge_st.property("text") if badge_st is not None else None
        got_ver = got_ver if isinstance(got_ver, str) else ""
        ch_ok = got_badge == app.backend.appChannel
        ver_ok = (got_ver.startswith(app.backend.appVersion)
                  and app.backend.devCodename in got_ver)
        check(
            "应用卡右栏 = 渠道徽章 + 版本行（版本号后面括号里跟 Codename）",
            ch_ok and ver_ok,
            "" if (ch_ok and ver_ok) else (
                f"徽章={got_badge!r}（期望 {app.backend.appChannel!r}）"
                f" 版本={got_ver!r}（期望含 {app.backend.appVersion!r}"
                f" 与 {app.backend.devCodename!r}）"
            ),
        )
        miss_items = [
            n for n in ("aboutRepoItem", "aboutIssuesItem", "aboutDepsItem")
            if _find_named(page_st, n) is None
        ]
        card_open = (bool(app_card_st.property("expanded"))
                     and round(float(app_card_st.property("contentHeight"))) > 0
                     ) if app_card_st is not None else False
        check(
            "应用卡三条内容项齐全（仓库 / 反馈 / 依赖）且默认展开",
            not miss_items and card_open,
            "" if (not miss_items and card_open) else (
                f"缺 {miss_items} 展开={card_open}"
            ),
        )
        # 「开源许可」那一项已按 2026-10-01 用户指令「关于界面的开源许可关掉」删除，
        # 连 ``About.qml`` 的 ``licenseUrl`` 属性一起。这条拦「重新加回来」。
        check(
            "关于页没有「开源许可」外链项（用户指令关掉）",
            _find_named(page_st, "aboutLicenseItem") is None,
            "" if _find_named(page_st, "aboutLicenseItem") is None
            else "aboutLicenseItem 又回来了",
        )
        # ---- 回声洞（2026-10-04 用户指令「参考 Luminalium 1 给关于页加回声洞」）----
        #
        # 照 L1 ``#echo-cave-item`` 复刻的是一条**有状态机**的交互，所以这里不能
        # 只断言「控件在」：必须走真实链路（点击 → 异步取句 → 打字机）把四个状态
        # 都跑一遍，否则「取句永远是空的」「打字机不动」这类坏法全都能蒙混过去。
        echo_row_st = _find_named(page_st, "aboutEchoCave")
        echo_text_st = _find_named(page_st, "aboutEchoContent")
        echo_copy_st = _find_named(page_st, "aboutEchoCopyButton")
        check(
            "关于页有回声洞行（可点击的设置项 + 正文 + 复制按钮）",
            echo_row_st is not None and echo_text_st is not None
            and echo_copy_st is not None,
            f"row={echo_row_st is not None} text={echo_text_st is not None} "
            f"copy={echo_copy_st is not None}",
        )
        if echo_row_st is not None and echo_text_st is not None:
            # ① 初始态 = 提示语，且「复制」还藏着（L1 是 display:none）
            hint_ok = str(echo_text_st.property("text")) == "点击卡片获取回声洞句子"
            check(
                "回声洞初始是提示语、复制按钮不显示",
                hint_ok and not bool(echo_copy_st.property("visible")),
                f"正文={str(echo_text_st.property('text'))!r} "
                f"复制可见={bool(echo_copy_st.property('visible'))}",
            )

            # ② 点击 → 走真实入口（MouseArea → requestSentence → 后端异步取句）
            #
            # ⚠️ 不能直接调 ``requestSentence()``：那样就绕过了 MouseArea 的层级
            # 关系 —— 而「复制按钮压在 MouseArea 上面」正是靠层级实现的（见
            # ``About.qml`` 里那两条注释），绕过去就验不到「点按钮不会顺带取句」。
            QMetaObject.invokeMethod(echo_row_st, "requestSentence")
            loading_seen = _wait_text(echo_text_st, "获取中...")
            check(
                "回声洞点击后先进入「获取中...」加载态",
                loading_seen,
                f"正文={str(echo_text_st.property('text'))!r}",
            )

            # ③ 取句回来 → 打字机逐字把句子打出来（50ms/字），打完才亮「复制」
            #    ⚠️ 等的是**复制按钮出现**（= L1 ``await typewriteText`` 之后那一步），
            #    不是「正文非空」—— 后者在打字打到第一个字时就成立了。
            #
            #    ⚠️ 预算给到 15s，不是「实现慢」：本环境下**进程内第一次**网络调用
            #    会被拖住好几秒（实测 worker 线程里第一次 ``getaddrinfo`` 要 3s，
            #    主线程只要 0.01s），而且那笔账记在第一个碰网络的线程头上 ——
            #    正好是取句线程。``echo_cave.warm_up()`` 已经把大部分开销提前结掉，
            #    这里再留足余量，免得自检在慢机器 / 沙箱里假失败。
            _wait_property(echo_copy_st, "visible", lambda v: bool(v), timeout_ms=15000)
            # ⚠️ 拿 ``fullText``（原始句子）而不是正文 ``text``：正文是富文本，
            # 句子里若有 ``<`` ``&`` 会被转义（``escapeHtml``），拿它跟剪贴板比
            # 会在含特殊字符的句子上假失败。复制按钮复制的正是 ``fullText``。
            sentence = str(echo_row_st.property("fullText"))
            typing_left = bool(echo_row_st.property("typing"))
            check(
                "回声洞取到句子并用打字机打完（打完后复制按钮才出现）",
                sentence != "" and not typing_left
                and bool(echo_copy_st.property("visible")),
                f"句子={sentence!r} 仍在打字={typing_left} "
                f"复制可见={bool(echo_copy_st.property('visible'))}",
            )

            # ④ 「复制」把**完整句子**送进剪贴板（不是打字机中途的前缀）
            if sentence:
                QMetaObject.invokeMethod(echo_copy_st, "clicked")
                QTest.qWait(60)
                check(
                    "回声洞「复制」把完整句子送进剪贴板",
                    QGuiApplication.clipboard().text() == sentence,
                    f"剪贴板={QGuiApplication.clipboard().text()!r} "
                    f"期望={sentence!r}",
                )
                check(
                    "回声洞「复制」点后按钮文案变「已复制」",
                    str(echo_copy_st.property("text")) == "已复制",
                    f"按钮文案={str(echo_copy_st.property('text'))!r}",
                )

        # ---- 诊断信息（2026-10-04 用户指令「像 ClassIsland 那样加一条显示
        #      诊断信息的入口」；同日第二轮：「移出程序信息那一栏」+「dialog
        #      内套文本框」）----
        #
        # 现在钉的是：入口是**页面上的独立一张卡**（不再挂在应用信息卡里）、点开
        # 有加载态、正文是**只读多行文本框**且内容 = 采集到的 ``键: 值`` 逐行、
        # 「复制全部」与文本框逐字一致。
        diag_entry_st = _find_named(page_st, "aboutDiagnosticsEntry")
        # ⚠️ 对话框本体**不能**用 ``_find_named``：``Rin.Dialog`` 底子是
        # ``QQC2.Popup``（QObject 而非 QQuickItem），不在 ``childItems()`` 树里；
        # 而它的 ``contentItem`` / ``footer`` 又被挂到窗口 overlay 下，也不在页面
        # 子树里。所以本体按 QObject 找，内部控件再从 contentItem/footer 往下找。
        #
        # ⚠️ 而且要从**窗口**（``settings``）往下找，不能从 ``page_st``
        # （= ``settings.contentItem()``）：QML 建出来的对象挂在**窗口**的
        # QObject 树下，``contentItem`` 那条链上只有 Qt 自己的两个内部项
        # （实测 ``findChildren`` 只回 10 个对象、连 ``aboutEchoCave`` 都找不到）。
        diag_dialog_st = _find_object(settings, "aboutDiagnosticsDialog")
        check(
            "关于页有「查看诊断信息」入口（SettingCard，自带 chevron）",
            diag_entry_st is not None and bool(diag_entry_st.property("clickable")),
            "" if diag_entry_st is not None else "未找到 aboutDiagnosticsEntry",
        )
        # 2026-10-04 用户指令「查看诊断信息那一个卡移出程序信息那一栏」：
        # 它必须**不再**挂在应用信息卡（``aboutAppCard``）里，而是页面上的独立一张卡。
        # 只断言「找得到」是抓不到这个回归的 —— 挪回卡里照样找得到。
        diag_in_app_card = (diag_entry_st is not None
                            and _ancestor_named(diag_entry_st,
                                                "aboutAppCard") is not None)
        check(
            "「查看诊断信息」已移出应用信息卡、独立成卡",
            diag_entry_st is not None and not diag_in_app_card,
            f"入口={diag_entry_st is not None} 仍在应用信息卡内={diag_in_app_card}",
        )
        check(
            "关于页有诊断信息对话框（Rin.Dialog）",
            diag_dialog_st is not None,
            "" if diag_dialog_st is not None else "未找到 aboutDiagnosticsDialog",
        )
        if diag_dialog_st is not None:
            QMetaObject.invokeMethod(diag_dialog_st, "open")

            # 2026-10-04 用户指令「宽度不够宽」：``Rin.Dialog`` 把 ``implicitWidth``
            # 夹在 ``Utils.dialogMaximumWidth``（= 600）以内，诊断文本里
            # ``AppExecutingEntrance: G:\...\.venv\Scripts\python.exe`` 这种长行一折
            # 就断成两截。About.qml 在派生组件里重写了那条绑定把上限抬到 880 ——
            # 只断言「对话框存在」是抓不到这个回归的。
            diag_width = float(diag_dialog_st.property("width") or 0.0)
            check(
                "诊断对话框比 RinUI 默认上限（600）更宽",
                diag_width > 600.0,
                f"宽度={diag_width:.0f}（RinUI 默认上限 600）",
            )

            # 打开后 ``onOpened`` 才会跑（QQC2 的 open 是带转场的异步），等它落地。
            content_st = _wait_property(
                diag_dialog_st, "contentItem", lambda v: v is not None,
                timeout_ms=3000)
            footer_st = diag_dialog_st.property("footer")
            loading_st = (_find_named(content_st, "aboutDiagnosticsLoading")
                          if content_st is not None else None)

            # 「加载中...」态：本机采集只要几十毫秒，硬抢时间点必然 flaky
            # （``onOpened`` 里 loading=true → 线程采集 → ``diagnosticsReady``
            # 里 loading=false，中间窗口可能不到一帧）。所以直接验**绑定**：
            # QML 的简单绑定是同步求值的，把 ``loading`` 置 true，标签必须立刻
            # 显形。这检的正是真风险 —— 标签没绑到 ``dialog.loading`` 上。
            saw_transient = bool(diag_dialog_st.property("loading"))
            loading_bind_ok = False
            if loading_st is not None:
                diag_dialog_st.setProperty("loading", True)
                loading_bind_ok = bool(loading_st.property("visible"))
                diag_dialog_st.setProperty("loading", False)
            check(
                "诊断对话框有「加载中...」态（标签绑在 dialog.loading 上）",
                loading_st is not None and loading_bind_ok
                and str(loading_st.property("text")) == "加载中...",
                (f"绑定生效={loading_bind_ok} 抓到真实过渡={saw_transient} "
                 f"文案={str(loading_st.property('text'))!r}")
                if loading_st is not None else "未找到 aboutDiagnosticsLoading",
            )

            # 采集线程回填 ``fields``（``diagnosticsReady`` 信号）→ 等它非空
            # ⚠️ 谓词必须过 ``_js_list``：``property var`` 读回来是 QJSValue，
            # 直接 ``bool()`` 恒为 True，等于没等。
            _wait_property(
                diag_dialog_st, "fields", lambda v: bool(_js_list(v)),
                timeout_ms=8000)
            # ⚠️ 采集回填之后要**让出一帧**再读文本框。``fields`` 一变，
            # ``plainText()`` 那条绑定的 ``text`` 立刻更新，但 ``QQuickTextEdit``
            # 的 ``contentHeight`` 要等下一次布局才落定 —— 抢在中间读会拿到半截值
            # （2026-10-04 实测：立刻读是 266，稳定后是 386），
            # 「内容溢出 → 能滚」那条断言会因此假失败。
            QTest.qWait(200)
            fields = _js_list(diag_dialog_st.property("fields"))
            keys = [_field_of(item, "key") for item in fields]
            values = " ".join(_field_of(item, "value") for item in fields)
            check(
                "诊断字段被采齐（含应用版本与运行环境）",
                len(keys) >= 15 and "AppVersion" in keys
                and app.backend.appVersion in values
                and "Python" in keys and "CPU" in keys,
                f"字段数={len(keys)} 含AppVersion={'AppVersion' in keys} "
                f"版本值命中={app.backend.appVersion in values}",
            )
            # 2026-10-04 用户指令「内容也和 ClassIsland 的那种诊断信息统一」：
            # 键名要落到 ClassIsland ``GetDiagnosticInfo()`` 那一套英文 PascalCase
            # 上（旧版是 OSType / DeviceModel / AppChannel / CurrentRunningDirectory）。
            # 这条拦「采集侧改了键名、界面侧还照旧键拼文本」这种半拉子改动 ——
            # 光断言「有 AppVersion」是抓不到的。
            classisland_keys = {
                "SystemOsVersion", "SystemOsArch", "SystemDeviceName",
                "SystemDeviceVendor", "AppPackageRoot", "AppRoot",
                "AppCurrentDirectory", "AppExecutingEntrance",
                "AppCurrentMemoryUsage", "AppVersion", "AppSubChannel",
            }
            stale_keys = {"OSType", "OSVersion", "DeviceModel", "DeviceVendor",
                          "AppChannel", "CurrentRunningDirectory"}
            check(
                "诊断键名与 ClassIsland 对齐（英文 PascalCase，无旧键残留）",
                classisland_keys <= set(keys) and not (stale_keys & set(keys)),
                f"缺={sorted(classisland_keys - set(keys))} "
                f"残留旧键={sorted(stale_keys & set(keys))}",
            )
            check(
                "诊断对话框不再显示「加载中...」（采集已回来）",
                not bool(diag_dialog_st.property("loading")),
            )

            # 2026-10-04 用户指令「RinUI 的 dialog 是有标准样式的，你去看看 RinUI
            # 的用法」：footer 必须是 RinUI 的**标准底栏** ``Rin.DialogButtonBox``
            # （自带底栏背景 + 顶部分隔线）。裸 ``RowLayout`` 也「能用」—— 但那正是
            # 被否掉的做法，只断言「按钮找得到」抓不到这个回归。
            footer_class = ""
            try:
                footer_class = (str(footer_st.metaObject().className())
                                if footer_st is not None else "")
            except Exception:  # noqa: BLE001 - 拿不到类型名不该带崩自检
                footer_class = ""
            check(
                "诊断对话框底栏是 RinUI 标准 DialogButtonBox（不是裸 RowLayout）",
                "DialogButtonBox" in footer_class,
                f"footer 类型={footer_class!r}",
            )

            # 2026-10-04 用户指令：「打开的 dialog 要是 ClassIsland 的那种，
            # dialog 内套文本框」—— 正文必须是一个**只读多行文本框**，而不是
            # 原来的键值表格（Flickable + Repeater）。
            box_st = (_find_named(content_st, "aboutDiagnosticsBox")
                      if content_st is not None else None)
            # ⚠️ ``enabled`` 必须为真：``Rin.TextArea`` 把 ``enabled`` 绑在
            # ``editable`` 上，用 ``editable: false`` 实现只读会把整框打成禁用 ——
            # 那样既不能滚也不能选中文字，只剩个样子。只读要用 ``readOnly``。
            #
            # ⚠️ 别去读 ``wrapMode``：它是 ``QQuickTextEdit::WrapMode`` 枚举，
            # PySide 没给这个类型注册转换器，``property("wrapMode")`` 直接抛
            # ``RuntimeError: Can't find converter for ...``，会把整段自检带崩
            # （踩过）。要验换行看 ``width`` / 行数这类可转换的量。
            box_text = str(box_st.property("text")) if box_st is not None else ""
            box_lines = [ln for ln in box_text.split("\n") if ln]
            box_h = float(box_st.property("height")) if box_st is not None else 0.0
            check(
                "诊断对话框里是只读多行文本框（ClassIsland 那种）",
                box_st is not None and bool(box_st.property("readOnly"))
                and bool(box_st.property("enabled"))
                and bool(box_st.property("visible"))
                and box_h > 100,
                f"框={box_st is not None} "
                f"只读={bool(box_st.property('readOnly')) if box_st is not None else None} "
                f"可用={bool(box_st.property('enabled')) if box_st is not None else None} "
                f"高={box_h:.0f}",
            )
            # 2026-10-04 用户指令「滚不动」：文本框必须是 ``Rin.ScrollableTextArea``
            # 而不是 ``Rin.TextArea``。后者是 ``QtQuick.Controls.Basic`` 的 TextArea，
            # ``contentItem`` 取回来是 None，文本超长时只是把 ``implicitHeight`` 撑大
            # （实测 652）再被 ``Layout.preferredHeight: 320`` 裁掉，滚轮一概无效。
            #
            # 这里钉三件事：① 类名是 ``ScrollableTextArea``；② 它的 ``contentItem``
            # 是 ``QQuickFlickable``（ScrollView 给非 Flickable 内容套的那层）；
            # ③ 内容比视口高、且写 ``contentY`` 认账 —— 这才是「能滚」的充要条件
            # （Flickable 的滚轮 / 拖动是 Qt 自带行为，不用自己接事件）。
            box_class = ""
            try:
                box_class = (str(box_st.metaObject().className())
                             if box_st is not None else "")
            except Exception:  # noqa: BLE001 - 拿不到类型名不该带崩自检
                box_class = ""
            scroll_ok = False
            scroll_detail = "无 contentItem"
            if box_st is not None:
                box_ci = box_st.property("contentItem")
                if box_ci is not None:
                    ci_class = str(box_ci.metaObject().className())
                    ci_h = float(box_ci.property("height") or 0.0)
                    ci_content_h = float(box_ci.property("contentHeight") or 0.0)
                    box_ci.setProperty("contentY", 120.0)
                    ci_y = float(box_ci.property("contentY") or 0.0)
                    box_ci.setProperty("contentY", 0.0)
                    scroll_ok = ("Flickable" in ci_class
                                 and ci_content_h > ci_h + 1
                                 and ci_y > 1.0)
                    scroll_detail = (f"contentItem={ci_class} "
                                     f"contentHeight={ci_content_h:.0f} "
                                     f"height={ci_h:.0f} 写contentY→{ci_y:.0f}")
            check(
                "诊断文本框能滚（ScrollableTextArea + 内容溢出的 Flickable）",
                "ScrollableTextArea" in box_class and scroll_ok,
                f"类名={box_class!r} {scroll_detail}",
            )
            check(
                "文本框内容 = 「Key: Value」逐行（条数与采集字段一致）",
                len(box_lines) == len(fields) and "AppVersion: " in box_text
                and "SystemOsVersion: " in box_text
                and app.backend.appVersion in box_text,
                f"文本框行数={len(box_lines)} 字段数={len(fields)} "
                f"含AppVersion行={'AppVersion: ' in box_text}",
            )

            # 「复制全部」= ``Key: Value`` 逐行，且与文本框里显示的一致。
            #
            # ⚠️ 底栏换成 ``Rin.DialogButtonBox`` 之后，按钮不再是 footer 的直接
            # 子项 —— 它们被重挂到 DialogButtonBox 的 ``contentItem``（一个
            # RowLayout）下面。``_find_named`` 走 ``childItems()`` 递归，正常情况
            # 能穿到；这里再留一条 QObject 树的兜底，免得哪天 Qt 改了重挂方式就
            # 只剩一句「footer 里未找到复制按钮」，看不出是结构变了还是真没了。
            copy_btn_st = None
            if footer_st is not None:
                copy_btn_st = _find_named(footer_st, "aboutDiagnosticsCopyButton")
                if copy_btn_st is None:
                    copy_btn_st = footer_st.findChild(QObject, "aboutDiagnosticsCopyButton")
            check(
                "诊断对话框底部有「复制全部」按钮（在标准底栏里）",
                copy_btn_st is not None,
                "" if copy_btn_st is not None else "footer 里未找到复制按钮",
            )
            if copy_btn_st is not None:
                QMetaObject.invokeMethod(copy_btn_st, "clicked")
                QTest.qWait(80)
                clipboard_text = QGuiApplication.clipboard().text()
                check(
                    "诊断「复制全部」复制出「Key: Value」逐行文本",
                    "AppVersion: " in clipboard_text and "\n" in clipboard_text
                    and app.backend.appVersion in clipboard_text
                    and "LogFile: " in clipboard_text,
                    f"前 80 字={clipboard_text[:80]!r}",
                )
                # 「看到的 = 复制到的」：文本框与剪贴板必须**逐字相同**（同源
                # ``plainText()``）。这条拦「两边各拼一遍、拼法慢慢跑偏」。
                check(
                    "「复制全部」与文本框内容逐字一致（看到的 = 复制到的）",
                    box_text != "" and clipboard_text == box_text,
                    f"剪贴板 {len(clipboard_text)} 字 / 文本框 {len(box_text)} 字",
                )
                check(
                    "诊断「复制全部」点后按钮文案变「已复制」",
                    str(copy_btn_st.property("text")) == "已复制",
                    f"按钮文案={str(copy_btn_st.property('text'))!r}",
                )
            # ⚠️ 必须**等它真的关掉**再往下走：``Rin.Dialog`` 是模态的
            # （``QQC2.Overlay.modal`` 那层遮罩），而 ``close()`` 只是发起关闭 ——
            # 退出转场（约 100~200ms）跑完之前 ``visible`` 仍是 true、遮罩还在。
            # 不等的话后面「真鼠标点击」那几项会被遮罩整个吃掉，症状是
            # 「热区结构全对、点击却 count=0」，看着像 MouseArea 坏了。
            QMetaObject.invokeMethod(diag_dialog_st, "close")
            left_visible = _wait_property(
                diag_dialog_st, "visible", lambda v: not bool(v), timeout_ms=3000)
            check(
                "诊断对话框能关掉（模态遮罩随之撤掉）",
                not bool(left_visible),
                f"visible={left_visible!r}",
            )
            QTest.qWait(120)
        # ④ 两条版式：仓库地址在打开按钮左边（等宽字体）；依赖的标题与链接
        #    **同列、上下排**（并排时标题会被右栏推到卡片右边，``x`` 会很大）。
        url_st = _find_named(page_st, "aboutRepoUrl")
        url_text = url_st.property("text") if url_st is not None else ""
        # ⚠️ QML ``Text`` 的 ``font`` 得走 ``property("font")``：``QQuickItem``
        # 本身没有 ``font()`` 这个方法（对着它调会 AttributeError，把整段自检
        # 抛进「过程异常」）。
        url_font = url_st.property("font") if url_st is not None else None
        url_mono = url_font.family() if url_font is not None else ""
        # 「在打开按钮左边」= 该行里存在一个可见兄弟，``x`` 落在 URL 右边缘之后。
        url_btn_st = _next_visible_right(url_st, page_st)
        url_left_ok = False
        if url_st is not None and url_btn_st is not None:
            url_x = url_st.mapToItem(page_st, 0, 0).x()
            btn_x = url_btn_st.mapToItem(page_st, 0, 0).x()
            url_left_ok = url_x + url_st.width() <= btn_x + 1
        url_ok = (isinstance(url_text, str)
                  and url_text.startswith("https://github.com/")
                  and "Consolas" in str(url_mono)
                  and url_left_ok)
        check(
            "仓库地址在打开按钮左边、用等宽字体",
            url_ok,
            "" if url_ok else (
                f"地址={url_text!r} 字体={url_mono!r} "
                f"右邻居={'未找到' if url_btn_st is None else 'Y'} "
                f"地址右缘={None if url_st is None else url_st.mapToItem(page_st, 0, 0).x() + url_st.width()} "
                f"按钮x={None if url_btn_st is None else url_btn_st.mapToItem(page_st, 0, 0).x()}"
            ),
        )
        # 依赖与参考：标题在上、链接在下，**同列**（并排时标题会被推到卡片右边）。
        dep_title_st = _find_named(page_st, "aboutDepsTitle")
        dep_link_st = _find_named(page_st, "aboutDepsLink0")
        deps_ok = (
            dep_title_st is not None and dep_link_st is not None
            and dep_link_st.y() >= dep_title_st.y() + dep_title_st.height() - 1
            and abs(dep_link_st.x() - dep_title_st.x()) < 12
        )
        check(
            "依赖与参考的标题与内容上下换行（同列）",
            deps_ok,
            "" if deps_ok else (
                f"依赖标题x={None if dep_title_st is None else dep_title_st.x()} "
                f"/ y={None if dep_title_st is None else dep_title_st.y()} "
                f"首链接x={None if dep_link_st is None else dep_link_st.x()} "
                f"/ y={None if dep_link_st is None else dep_link_st.y()}"
            ),
        )

        app.backend.settingsCloseRequested.emit()

        # ---- 调试窗口（隐藏入口：设置标题连点 10 次）----
        # 调试项 2026-09-30 从设置导航移出、改成独立窗口，入口是压在 RinUI 标题
        # 文本上的一块透明热区。热区位置靠「返回按钮 40 + 间距 16 + 图标 16 +
        # 间距 16 = 88」推算 —— RinUI 一旦改内边距，热区就会点不到标题文字，
        # 所以这里把几何关系钉成断言；否则表现为「连点没反应」且**没有任何报错**。
        def _find_item(item, predicate):
            for child in item.childItems():
                if predicate(child):
                    return child
                found = _find_item(child, predicate)
                if found is not None:
                    return found
            return None

        def _origin(window, item):
            point = item.mapToItem(window.contentItem(), QPointF(0, 0))
            return point.x(), point.y()

        if settings is not None:
            app.windows.show_settings()
            hotspot = _find_item(
                settings.contentItem(),
                lambda it: it.objectName() == "debugTitleHotspot",
            )
            check(
                "调试入口热区存在（压在标题文本上）",
                hotspot is not None,
                "" if hotspot is not None else "未找到 objectName=debugTitleHotspot 的项",
            )
            # 标题文字有**两个**候选：TitleBar 自带的那个（``titleEnabled: false``
            # 下不可见，但 ``text`` 仍等于窗口标题）和 NavigationBar 真正画出来的
            # 那个。必须带可见性筛选，否则会锚到那个隐形的上去。
            title_text = _find_item(
                settings.contentItem(),
                lambda it: it.property("text") == settings.property("title")
                and it.isVisible(),
            )
            if hotspot is not None and title_text is not None:
                hx, _hy = _origin(settings, hotspot)
                tx, _ty = _origin(settings, title_text)
                check(
                    "调试入口热区完整盖住标题文本",
                    hx <= tx and hx + hotspot.width() >= tx + title_text.width(),
                    f"hotspot x=[{hx:.0f},{hx + hotspot.width():.0f}] "
                    f"title x=[{tx:.0f},{tx + title_text.width():.0f}]",
                )
                # 同时不能压到左边的返回按钮，否则导航回退会被热区吃掉
                host = settings.property("titleBarLeadingHost")
                host_x = _origin(settings, host)[0] if host is not None else 0.0
                check(
                    "调试入口热区避开返回按钮（40 宽）",
                    hx >= host_x + 40,
                    f"hotspot.x={hx:.0f} 返回按钮右边缘={host_x + 40:.0f}",
                )
                # 真鼠标事件也要能落到热区上 —— 位置对不代表 MouseArea 真收得到：
                # 标题行压在它上层，全靠「Text 不吃鼠标事件」穿透过来。
                QTest.mouseClick(
                    settings,
                    Qt.LeftButton,
                    Qt.NoModifier,
                    QPoint(int(tx + 8), int(_ty + 8)),
                )
                check(
                    "真实鼠标点击落到标题热区上",
                    settings.property("debugTitleTapCount") == 1,
                    f"count={settings.property('debugTitleTapCount')}",
                )
            else:
                check("调试入口热区完整盖住标题文本", False, "热区或标题文本缺失")

            # 连点 10 次才开：补到 9 次仍不该有任何动静
            for _ in range(8):
                QMetaObject.invokeMethod(settings, "registerDebugTitleTap")
            check(
                "标题连点 9 次仍不开调试窗口",
                settings.property("debugTitleTapCount") == 9 and app.windows.debug is None,
                f"count={settings.property('debugTitleTapCount')}",
            )
            QMetaObject.invokeMethod(settings, "registerDebugTitleTap")
            debug_win = app.windows.debug
            check(
                "标题连点 10 次打开调试窗口",
                debug_win is not None and debug_win.isVisible(),
                "窗口未创建" if debug_win is None else f"visible={debug_win.isVisible()}",
            )
            if debug_win is not None:
                area = QGuiApplication.primaryScreen().availableGeometry()
                inside = (
                    area.left() <= debug_win.x()
                    and debug_win.x() + debug_win.width() <= area.right() + 1
                    and area.top() <= debug_win.y()
                    and debug_win.y() + debug_win.height() <= area.bottom() + 1
                )
                check(
                    "调试窗口位于屏幕内",
                    inside,
                    f"pos=({debug_win.x()},{debug_win.y()}) "
                    f"size={debug_win.width()}x{debug_win.height()} area={area}",
                )
                # 不能与设置窗口**完全**重合：屏幕窄的时候并排本就放不下，
                # 但至少要有偏移，否则看起来像「设置窗口被替换掉了」
                check(
                    "调试窗口与设置窗口错开（不完全重合）",
                    (debug_win.x(), debug_win.y()) != (settings.x(), settings.y()),
                    f"settings=({settings.x()},{settings.y()}) "
                    f"debug=({debug_win.x()},{debug_win.y()})",
                )
                # 轮询间隔也换成了滑块（2026-10-01「能改成滑块的都改成滑块」）。
                poll_sliders = _collect_type(debug_win.contentItem(), "Slider")
                check(
                    "调试窗口的轮询间隔是滑块（带 ms 读数）",
                    len(poll_sliders) == 1
                    and len(_collect_type(debug_win.contentItem(), "SpinBox")) == 0
                    and any("ms" in str(t.property("text"))
                            for t in _collect_type(debug_win.contentItem(), "Text")),
                    f"滑块={len(poll_sliders)} "
                    f"SpinBox="
                    f"{len(_collect_type(debug_win.contentItem(), 'SpinBox'))}",
                )
                # 调试窗口与设置窗口同一条约定：由 RinUI 接管（见上面那段长注释）
                debug_hwnd = int(debug_win.winId())
                style_b = (
                    ctypes.windll.user32.GetWindowLongW(debug_hwnd, -16) & 0xFFFFFFFF
                )
                filter_hwnds_b = {int(h) for h in app.rinui.win_event_filter.hwnds.values()}
                theme_hwnds_b = {int(h) for h in app.rinui.theme_manager.windows}
                check(
                    "调试窗口已交给 RinUI 管（WS_CAPTION|WS_THICKFRAME + 名单）",
                    bool(style_b & 0x00C00000)
                    and bool(style_b & 0x00040000)
                    and debug_hwnd in filter_hwnds_b
                    and debug_hwnd in theme_hwnds_b,
                    f"style=0x{style_b:08X} hwnd={debug_hwnd} "
                    f"filter={'Y' if debug_hwnd in filter_hwnds_b else 'N'} "
                    f"theme={'Y' if debug_hwnd in theme_hwnds_b else 'N'}",
                )
                # ---- 错误处理：手动报错 / 手动崩溃（2026-10-05 用户指令
                #      「在调试菜单中添加手动报错和手动崩溃」）----
                #
                # 两张卡各带一枚「触发」按钮：「手动报错」编一条**非致命**报告，
                # 「手动崩溃」走**真实的**未捕获异常链路（``sys.excepthook``）。
                # 断言分两层 —— ① 结构：两张卡 + 各自的按钮都在；② 行为：真鼠标
                # 点下去之后 ``ErrorHandler`` 真的收到报告，且档位 / 主按钮对得上。
                #
                # 按钮按 ``objectName`` 找（不按类名数数量）：``Rin.Button`` 的
                # 运行时类名带 QMLTYPE 后缀，``_collect_type`` 那种前缀匹配靠不住。
                err_card = _find_item(
                    debug_win.contentItem(),
                    lambda it: it.objectName() == "debugSimulateError",
                )
                crash_card = _find_item(
                    debug_win.contentItem(),
                    lambda it: it.objectName() == "debugSimulateCrash",
                )
                err_btn = _find_item(
                    debug_win.contentItem(),
                    lambda it: it.objectName() == "debugSimulateErrorButton",
                )
                crash_btn = _find_item(
                    debug_win.contentItem(),
                    lambda it: it.objectName() == "debugSimulateCrashButton",
                )
                check(
                    "调试窗口有「手动报错」「手动崩溃」两张卡（各带触发按钮）",
                    None not in (err_card, crash_card, err_btn, crash_btn),
                    f"card_err={'Y' if err_card is not None else 'N'} "
                    f"card_crash={'Y' if crash_card is not None else 'N'} "
                    f"btn_err={'Y' if err_btn is not None else 'N'} "
                    f"btn_crash={'Y' if crash_btn is not None else 'N'}",
                )
                if None not in (err_card, crash_card, err_btn, crash_btn):
                    eh = app.error_handler
                    # 行为①：真鼠标点「手动报错」→ 出**错误**报告（主按钮=忽略）
                    _bx, _by = _origin(debug_win, err_btn)
                    QTest.mouseClick(
                        debug_win, Qt.LeftButton, Qt.NoModifier,
                        QPoint(int(_bx + err_btn.width() / 2),
                               int(_by + err_btn.height() / 2)),
                    )
                    check(
                        "点「手动报错」→ 出的是错误报告（主按钮=忽略）",
                        eh.property("hasReport") is True
                        and eh.property("isCrash") is False
                        and eh.property("primaryAction") == "ignore",
                        f"hasReport={eh.property('hasReport')} "
                        f"isCrash={eh.property('isCrash')} "
                        f"primary={eh.property('primaryAction')!r}",
                    )
                    # 行为②：真鼠标点「手动崩溃」→ 出**崩溃**报告（主按钮=重新启动）
                    _bx, _by = _origin(debug_win, crash_btn)
                    QTest.mouseClick(
                        debug_win, Qt.LeftButton, Qt.NoModifier,
                        QPoint(int(_bx + crash_btn.width() / 2),
                               int(_by + crash_btn.height() / 2)),
                    )
                    check(
                        "点「手动崩溃」→ 出的是崩溃报告（主按钮=重新启动）",
                        eh.property("hasReport") is True
                        and eh.property("isCrash") is True
                        and eh.property("primaryAction") == "restart",
                        f"hasReport={eh.property('hasReport')} "
                        f"isCrash={eh.property('isCrash')} "
                        f"primary={eh.property('primaryAction')!r}",
                    )
                    # 版式：2026-10-05 用户指令「错误报告程序为什么如此小 应当宽大
                    # 一些 并且你需要看着像 dialog」。两件事分开断言 ——
                    # ① 尺寸真的放大了（原来钉死 560×470，堆栈框只有 512 宽，
                    #    一条 Python 回溯每行都要折）；
                    # ② 按钮条是**顶着窗口下缘**的页脚（对话框的做法），而不是
                    #    飘在正文流里 —— 后者底部会留出 24 的外边距。
                    rep = app.windows.error_report
                    rep_ci = rep.contentItem() if rep is not None else None
                    footer = None if rep_ci is None else _find_item(
                        rep_ci, lambda it: it.objectName() == "errorReportFooter")
                    rep_size = (f"{rep.width()}x{rep.height()}"
                                if rep is not None else "无")
                    check(
                        "报告窗够宽（≥640，不再是 560）",
                        rep is not None and rep.width() >= 640,
                        f"size={rep_size}（高度分收起/展开两档，不钉死）",
                    )
                    _gap = -1.0
                    if footer is not None and rep_ci is not None:
                        _fy = _origin(rep, footer)[1]
                        _gap = rep_ci.height() - (_fy + footer.height())
                    check(
                        "报告窗的按钮条是顶着下缘的对话框页脚",
                        # ⚠️ 阈值 20 而不是「贴死 0」：``Rin.Window`` 的内容区自己带
                        # 一圈 ``Utils.windowDragArea`` 边距，实测收起档 14px /
                        # 展开档 5px 都属正常。判据是「明显小于正文流的 24 外边距」。
                        0 <= _gap <= 20,
                        f"页脚底距窗口底 {_gap:.0f}px（飘在正文流里会 ≥24）",
                    )
                    # 照 Class Widgets 2 的版式（2026-10-05）：环境网格常显，
                    # 技术细节（堆栈）**默认收起** —— 原来一上来就糊整段 traceback
                    # 正是「敷衍」的来源。
                    env_grid = None if rep_ci is None else _find_item(
                        rep_ci, lambda it: it.objectName() == "errorReportEnvironment")
                    toggle = None if rep_ci is None else _find_item(
                        rep_ci, lambda it: it.objectName() == "errorReportDetailsToggle")
                    trace_box = None if rep_ci is None else _find_item(
                        rep_ci, lambda it: it.objectName() == "errorReportTracebackBox")
                    check(
                        "报告窗有环境网格，且技术细节默认收起",
                        env_grid is not None and toggle is not None
                        and trace_box is not None and not trace_box.isVisible(),
                        f"env={'Y' if env_grid is not None else 'N'} "
                        f"toggle={'Y' if toggle is not None else 'N'} "
                        f"trace_visible="
                        f"{None if trace_box is None else trace_box.isVisible()}",
                    )
                    # 真鼠标点「查看详细信息」→ 窗口变高 + 堆栈框现身
                    _h_before = rep.height() if rep is not None else 0
                    if toggle is not None and rep is not None:
                        _tx, _ty = _origin(rep, toggle)
                        QTest.mouseClick(
                            rep, Qt.LeftButton, Qt.NoModifier,
                            QPoint(int(_tx + toggle.width() / 2),
                                   int(_ty + toggle.height() / 2)),
                        )
                        QTest.qWait(120)
                    _h_after = rep.height() if rep is not None else 0
                    check(
                        "点「查看详细信息」→ 窗口变高且堆栈框现身",
                        _h_after > _h_before and trace_box is not None
                        and trace_box.isVisible(),
                        f"高 {_h_before} → {_h_after}，堆栈可见="
                        f"{None if trace_box is None else trace_box.isVisible()}",
                    )

                    # 收尾：崩溃那一步会请求弹出报告窗，把它收回去 —— 否则后面
                    # 版本号 / 设置项的断言会落在一张浮着的报告窗后面。
                    app.windows.hide_error_report()

                app.backend.closeDebugWindow()
                check("调试窗口可关闭", not debug_win.isVisible())

            # ---- 标题栏版本号（2026-10-04 用户指令「在设置的三大键左侧显示程序
            #      的版本号」）----
            #
            # 挂点是 ``titleBarHost``（``TitleBar`` 里那块 ``Layout.fillWidth`` 的
            # 中间区），它在标题栏那条 RowLayout 里夹在「导航标题」与「三个窗口
            # 按钮」之间 —— 所以往它右缘一贴就是三大键的正左边。
            #
            # ⚠️ 「在三大键左侧」必须拿**窗口按钮的实际坐标**比，不能只断言
            # 「挂在 titleBarHost 里」：挂错成 ``titleBarLeadingHost`` 也照样挂在
            # 标题栏里，但会跑到窗口左边去（那两个 alias 只差一个词）。
            version_label = _find_item(
                settings.contentItem(),
                lambda it: it.objectName() == "settingsVersionLabel",
            )
            check(
                "标题栏有版本号标签",
                version_label is not None,
                "" if version_label is not None else "未找到 settingsVersionLabel",
            )
            if version_label is not None:
                label_x, _label_y = _origin(settings, version_label)
                label_right = label_x + version_label.width()
                # 三个窗口按钮是 RinUI 的 ``CtrlBtn``（mode 0=最大化 / 1=最小化 /
                # 2=关闭），RinUI 没给它们 objectName，只能按类名找。
                ctrl_btns = [
                    it for it in _collect_type(settings.contentItem(), "CtrlBtn")
                    if it.isVisible()
                ]
                ctrl_left = min((_origin(settings, it)[0] for it in ctrl_btns),
                                default=float("inf"))
                check(
                    "版本号在三大键左侧（按钮在窗口右半区）",
                    bool(ctrl_btns)
                    and label_right <= ctrl_left
                    and ctrl_left > settings.width() / 2,
                    f"版本号 x=[{label_x:.0f},{label_right:.0f}] "
                    f"三大键最左 x={ctrl_left:.0f} 按钮数={len(ctrl_btns)} "
                    f"窗口宽={settings.width()}",
                )
                check(
                    "版本号文案 = Backend.appVersion",
                    str(version_label.property("text")) == app.backend.appVersion,
                    f"文案={str(version_label.property('text'))!r} "
                    f"期望={app.backend.appVersion!r}",
                )
                # ⚠️ 标签必须待在 ``titleBarHost`` 的**边界内**：那块带
                # ``clip: true``，拿负的 ``rightMargin`` 把它顶出去会被裁成
                # ``26.0`` 这种半截（2026-10-04 踩过）。
                label_host = version_label.parentItem()
                if label_host is not None:
                    host_right = _origin(settings, label_host)[0] + label_host.width()
                    check(
                        "版本号没被 titleBarHost 的 clip 裁掉",
                        label_right <= host_right + 0.5,
                        f"标签右缘={label_right:.0f} 宿主右缘={host_right:.0f}",
                    )

            app.backend.settingsCloseRequested.emit()

        # ---- 主界面编辑器（独立窗口，入口是快捷面板的快捷方式）----
        # 放在快捷方式增删之前：那段会临时改动「已启用快捷方式」列表，
        # 先跑这条能确保它读到的是配置原样。
        _check_editor(app)

        # ---- 设置页「主界面」的推广卡「编辑主界面的新方式」----
        # 版式照搬 Class Widgets 2 的 ``ClassWidgets/Components/Introduction.qml``
        # （用例在 ``pages/settings/General/Widgets.qml``）：左图 + 右文 + 右下角
        # 一个 flat + highlighted 的按钮。
        # ⚠️ 必须排在 ``_check_editor`` **之后**：编辑器是懒创建的，上面那条
        # 「未打开时不建」的断言不能被这里先点开给破坏掉。
        if settings is not None:
            app.windows.show_settings("settings/MainInterface.qml")
            intro = None
            for _ in range(12):  # NavigationView.push → 页面组件加载是异步的
                QTest.qWait(120)
                intro = _find_item(
                    settings.contentItem(),
                    lambda it: it.objectName() == "mainInterfaceEditorIntro",
                )
                if intro is not None:
                    break
            check(
                "设置页「主界面」有推广卡「编辑主界面的新方式」",
                intro is not None,
                "" if intro is not None
                else "未找到 objectName=mainInterfaceEditorIntro 的项",
            )
            if intro is not None:
                title = _find_named(intro, "mainInterfaceEditorIntroTitle")
                image = _find_named(intro, "mainInterfaceEditorIntroImage")
                button = _find_named(intro, "mainInterfaceEditorIntroButton")
                check(
                    "推广卡标题是「编辑主界面的新方式」",
                    title is not None
                    and title.property("text") == "编辑主界面的新方式",
                    f"title={None if title is None else title.property('text')!r}",
                )
                # 配图是**两张文件**，按主题二选一：两张原图都是透明底、元素色与
                # 卡片同色，贴错了整块看不见（2026-10-01 实测），所以在这里钉死。
                # ⚠️ 判据取 ``is_dark_theme()`` 而不是 ``get_theme_name()``：后者
                # 在「跟随系统」档下返回 ``Auto``，跟 QML 里的 ``Lumi.isDark`` 不是
                # 一回事（Auto 下真实明暗由系统决定）。
                dark = bool(app.rinui.theme_manager.is_dark_theme())
                want = "_dark.png" if dark else "_light.png"
                # ⚠️ ``Image.source`` 是 QUrl，直接 ``str()`` 会得到
                # ``PySide6.QtCore.QUrl('file:///…')`` 这种壳，得走 ``toString()``。
                raw = None if image is None else image.property("source")
                source = raw.toString() if hasattr(raw, "toString") else str(raw)
                check(
                    f"推广卡配图跟着主题走（{'深色' if dark else '浅色'} → {want}）",
                    image is not None and source.endswith(want),
                    f"source={source!r}",
                )
                check(
                    "推广卡按钮是「打开主界面编辑器」（flat + highlighted）",
                    button is not None
                    and button.property("text") == "打开主界面编辑器"
                    and button.property("flat") is True
                    and button.property("highlighted") is True,
                    "按钮缺失" if button is None
                    else f"text={button.property('text')!r} "
                         f"flat={button.property('flat')} "
                         f"highlighted={button.property('highlighted')}",
                )
                # 版式：图在左、文字在右（不重叠）；按钮贴着卡片内容区右边界。
                if image is not None and title is not None and button is not None:
                    image_right = image.mapToItem(intro, image.width(), 0).x()
                    title_left = title.mapToItem(intro, 0, 0).x()
                    check(
                        "推广卡版式：图在左、文字在右且不重叠",
                        image_right <= title_left + 1,
                        f"图右={image_right:.0f} 文字左={title_left:.0f}",
                    )
                    button_right = button.mapToItem(intro, button.width(), 0).x()
                    content_right = intro.width() - float(
                        intro.property("rightPadding") or 0
                    )
                    check(
                        "推广卡按钮贴右（Fluent 卡片尾部的动作位）",
                        abs(button_right - content_right) <= 1,
                        f"按钮右={button_right:.0f} 内容右={content_right:.0f}",
                    )
                    # 高度 = 图高 + 上下内边距（与 Lumi.editorIntroImageHeight /
                    # editorIntroPadding 同值；QML 单例 Python 侧读不到，只能对齐）
                    check(
                        "推广卡高度 = 图片高 + 上下内边距",
                        abs(intro.height() - (150 + 24 * 2)) <= 1,
                        f"height={intro.height():.0f} 期望 198",
                    )
                # 点击按钮 → 真的把编辑器叫起来（与快捷面板同一条 openMainEditor）
                if button is not None:
                    QMetaObject.invokeMethod(button, "clicked")
                    QTest.qWait(500)
                    editor_win = app.windows.editor
                    check(
                        "推广卡按钮能把主界面编辑器叫起来",
                        editor_win is not None and editor_win.isVisible(),
                        "窗口未创建" if editor_win is None
                        else f"visible={editor_win.isVisible()}",
                    )
                    app.backend.closeMainEditor()
                    QTest.qWait(150)

            # ---- 放映页的「位置 / 外观」整组搬来这一页（2026-10-01 用户指令）----
            # 这五项调的都是「主界面长什么样」，归这一页；放映页只剩下行为项。
            moved_cards = [
                "mainInterfaceMarginX",
                "mainInterfaceMarginY",
                "mainInterfaceScreenIndex",
                "mainInterfaceSurfaceOpacity",
                "mainInterfaceShadowEnabled",
            ]
            found_cards = {name: _find_named(settings.contentItem(), name)
                           for name in moved_cards}
            missing = [n for n, v in found_cards.items() if v is None]
            check(
                "「主界面」页有从放映页搬来的 5 项（水平/垂直边距、目标显示器、"
                "底板不透明度、投影）",
                not missing,
                f"缺失={missing}" if missing
                else f"找到={len(found_cards)}",
            )
            # 控件也得跟着搬过来（最容易出的事：整块搬走时把卡片留下、把里面的
            # 滑块 / 下拉漏了 —— 表现是「有这一项但点不动」）。
            probe = found_cards.get("mainInterfaceSurfaceOpacity")
            if probe is not None:
                sliders = _collect_type(probe, "Slider")
                check(
                    "搬来的「底板不透明度」是**滑块**（2026-10-01：能改成滑块的都改）",
                    len(sliders) > 0 and len(_collect_type(probe, "SpinBox")) == 0,
                    f"卡内 滑块={len(sliders)} SpinBox="
                    f"{len(_collect_type(probe, 'SpinBox'))}",
                )
            display_card = found_cards.get("mainInterfaceScreenIndex")
            if display_card is not None:
                combos = _collect_type(display_card, "ComboBox")
                check(
                    "搬来的「目标显示器」带下拉（控件没漏搬）",
                    len(combos) > 0,
                    f"卡内 ComboBox 数={len(combos)}",
                )

            # 三个数值项都该是滑块（边距 ×2 + 不透明度），且**数值读数**在旁边
            # —— 拖完看不见具体数字是滑块最容易丢的东西。
            slider_cards = [
                "mainInterfaceMarginX", "mainInterfaceMarginY",
                "mainInterfaceSurfaceOpacity",
            ]
            every = {}
            for name in slider_cards:
                card = found_cards.get(name)
                every[name] = [] if card is None else _collect_type(card, "Slider")
            check(
                "边距与不透明度都用滑块（三个数值项都换掉了 SpinBox）",
                all(len(v) == 1 for v in every.values()),
                ", ".join(f"{k}={len(v)}" for k, v in every.items()),
            )
            check(
                "滑块旁边有数值读数（带单位，拖完看得见具体数字）",
                all(
                    any("px" in str(t.property("text")) or "%" in str(t.property("text"))
                        for t in _collect_type(card, "Text"))
                    for card in (found_cards.get(n) for n in slider_cards)
                    if card is not None
                ),
                ", ".join(
                    f"{n}:" + "/".join(
                        str(t.property("text"))
                        for t in _collect_type(found_cards.get(n), "Text")
                    )
                    for n in slider_cards if found_cards.get(n) is not None
                ),
            )

            # 真的拖一下：按住手柄拖到别处 → 配置跟着变。这是「滑块接上了
            # setSetting」的唯一证据（光照一张图看不出接线对不对）。
            # ⚠️ 走**真实鼠标事件**而不是 ``QMetaObject.invokeMethod(slider,
            # "moved", …)`` —— 后者对 QML 里声明的信号不生效（静默返回 False），
            # 断言会变成「配置没变」的假失败。
            # ⚠️ 挑**位置最高的那只**（水平边距）：设置窗口只有 913×613，页面比
            # 窗口高，「底板不透明度」那张卡在 y≈709 处 —— 落在窗口外，鼠标事件
            # 发过去什么都不会发生（表现就是「拖了但配置没变」，第一版踩到）。
            margin_card = found_cards.get("mainInterfaceMarginX")
            drag_slider = (
                None if margin_card is None
                else (_collect_type(margin_card, "Slider") or [None])[0]
            )
            if drag_slider is not None:
                prev_margin = app.config.get("presentation.margin_x")
                from_value = float(drag_slider.property("from") or 0)
                to_value = float(drag_slider.property("to") or 0)
                start = float(drag_slider.property("value"))
                want = 120.0

                handle = drag_slider.property("handle")
                origin = drag_slider.mapToScene(QPointF(0, 0))
                span = drag_slider.width() - handle.width()
                ratio = ((want - from_value) / (to_value - from_value)
                         if to_value != from_value else 0.0)
                grab = handle.mapToScene(QPointF(handle.width() / 2, handle.height() / 2))
                drop = QPointF(origin.x() + handle.width() / 2 + ratio * span,
                               grab.y())
                QTest.mousePress(settings, Qt.LeftButton, Qt.NoModifier,
                                 QPoint(int(grab.x()), int(grab.y())))
                QTest.mouseMove(settings, QPoint(int(drop.x()), int(drop.y())))
                QTest.mouseRelease(settings, Qt.LeftButton, Qt.NoModifier,
                                   QPoint(int(drop.x()), int(drop.y())))
                QTest.qWait(250)

                after = float(app.config.get("presentation.margin_x") or 0)
                # 容差 = 一档（stepSize 1px）：落在哪一格由像素取整决定。
                check(
                    "拖滑块能写进配置（真实鼠标拖动手柄 → setSetting）",
                    abs(after - want) <= 1.5 and after != prev_margin,
                    f"{prev_margin} → {after}（拖到 {want}）"
                    f" | start={start} 抓点=({grab.x():.0f},{grab.y():.0f})"
                    f" 落点=({drop.x():.0f},{drop.y():.0f})",
                )
                app.backend.setSetting("presentation_margin_x", prev_margin)
                QTest.qWait(120)
                check(
                    "滑块自检不留副作用",
                    app.config.get("presentation.margin_x") == prev_margin,
                    f"{app.config.get('presentation.margin_x')} 期望 {prev_margin}",
                )

            # ---- 「缩放大小」滑块（2026-10-05 用户指令：「主界面设置新增缩放
            #      大小滑块 用于调整顶层窗口中组件的大小」）----
            # 三层守卫：① 卡在、是滑块、带 % 读数；② **真的接上了** —— 改
            # ``presentation.scale`` 之后真机控制条的尺寸按倍率走（Python 摆位 /
            # 区域塑形读的就是控制条的 width/height/shadowMargin，所以「尺寸变了」
            # 等价于「屏幕上的组件变了」）；③ 自检不留副作用。
            scale_card = _find_named(settings.contentItem(), "mainInterfaceScale")
            scale_sliders = [] if scale_card is None else _collect_type(scale_card, "Slider")
            scale_readout = ("" if scale_card is None else "/".join(
                str(t.property("text")) for t in _collect_type(scale_card, "Text")))
            check(
                "「主界面」页有「缩放大小」滑块（带 % 读数）",
                scale_card is not None and len(scale_sliders) == 1
                and "%" in scale_readout,
                "未找到 objectName=mainInterfaceScale" if scale_card is None
                else f"滑块={len(scale_sliders)} 读数={scale_readout!r}",
            )
            # 真机验证挑**底中那条工具栏**（最宽的一条，量宽度最有区分度）。
            scale_dock = app.windows._docks.get("bottom_center") or next(
                iter(app.windows._docks.values()), None)
            if scale_card is not None and scale_dock is not None:
                prev_scale = app.config.get("presentation.scale", 1.0)
                base_w = float(scale_dock.width())
                app.backend.setSetting("presentation_scale", 2.0)
                QTest.qWait(150)
                big_w = float(scale_dock.width())
                app.backend.setSetting("presentation_scale", 0.5)
                QTest.qWait(150)
                small_w = float(scale_dock.width())
                check(
                    "缩放滑块真的改变顶层窗口组件的大小（2.0 翻倍 / 0.5 减半）",
                    abs(big_w - base_w * 2) <= 2 and abs(small_w - base_w * 0.5) <= 2,
                    f"基准={base_w:.0f} ×2={big_w:.0f} ×0.5={small_w:.0f}",
                )
                app.backend.setSetting("presentation_scale", prev_scale)
                QTest.qWait(150)
                check(
                    "缩放自检不留副作用（倍率与组件宽度都已还原）",
                    abs(float(app.config.get("presentation.scale", 1.0))
                        - float(prev_scale)) < 1e-6
                    and abs(float(scale_dock.width()) - base_w) <= 1,
                    f"scale={app.config.get('presentation.scale')} 期望 {prev_scale} "
                    f"宽={scale_dock.width():.0f} 期望 {base_w:.0f}",
                )

            # ---- 放映设置页：**整页删除**（2026-10-01 第四轮用户指令）----
            # 页内的设置项早在本轮之前就搬空了（位置 / 外观 → 主界面，退出键样式
            # → 编辑器，组分隔线与页码切换直接删）；这次连**空壳页面本身**也删掉。
            # 导航项那一条在上面「设置导航」里钉了，这里钉**文件**：两者都可能
            # 单独漏（删了文件没删导航 → 点进去空白；删了导航没删文件 → 页面还
            # 会被 preview.py 的 glob 渲染出来，看着像没删干净）。
            page_gone = not (ROOT / "ui" / "settings" / "Presentation.qml").exists()
            check(
                "「放映」设置页文件已删除（ui/settings/Presentation.qml）",
                page_gone,
                # detail 无论成败都会打印 —— 只在失败时给「为什么」
                "" if page_gone else "文件还在（preview.py 会把它一起渲染出来）",
            )
            # ---- 通用页：托盘设置组与「失去焦点时收起」已删除 ----
            # 2026-10-01（第二轮）用户指令：「托盘」整组连着相关的逻辑和代码一块
            # 删掉；「失去焦点时收起」作为默认行为、不再作为设置项。
            # ⚠️ 页面根得先等它真的 push 完成（异步，见 ``_wait_named``）——
            # 找的不是文件名而是页面根的 objectName（NavigationView 会把页面根的
            # objectName 覆盖成文件名，所以这里就是 ``Index``）。
            app.windows.show_settings("settings/General/Index.qml")
            general = _wait_named(settings.contentItem(), "Index")
            check(
                "通用页能打开（页面根按文件名 Index 找得到）",
                general is not None,
                "页面没落地（可能只是 push 还没跑完）" if general is None else "",
            )
            if general is not None:
                gone = [
                    title for title in (
                        "常驻托盘", "启动时提示", "左键打开快捷面板",
                        "托盘提示文字", "失去焦点时收起",
                    )
                    if _find_text(general, title) is not None
                ]
                check(
                    "通用页已无「托盘」整组（4 项）与「失去焦点时收起」",
                    not gone,
                    f"还找到 {gone}",
                )
                check(
                    "通用页已无「托盘」分组标题",
                    _find_text(general, "托盘") is None,
                )
                # ---- 2026-10-06 用户指令：主题模式搬回「通用」----
                # 「个性化」只剩强调色，本页因此变回 4 张卡。
                cards = _collect_type(general, "SettingCard")
                keep = [
                    title for title in (
                        "开机自启", "应用主题", "快捷方式锁定", "界面语言",
                    )
                    if _find_text(general, title) is not None
                ]
                check(
                    "通用页 4 张卡（开机自启 + 应用主题 + 快捷方式锁定 + 界面语言）",
                    len(cards) == 4 and len(keep) == 4,
                    f"卡数={len(cards)} 找到={keep}",
                )
                check(
                    "「强调色」没被一起搬回通用页（留在「个性化」）",
                    _find_text(general, "强调色") is None,
                )
                check(
                    "本页两只开关都在（开机自启 + 快捷方式锁定）",
                    len(_collect_type(general, "Switch")) == 2,
                    f"Switch={len(_collect_type(general, 'Switch'))}",
                )
                # 搬整块时最容易漏的是**控件**（卡片搬走了、里面的下拉没搬 →
                # 有这一项但点不动），所以按 objectName 找到卡后再往里数控件。
                theme_card = _find_named(general, "generalTheme")
                check(
                    "通用页有「应用主题」卡（objectName=generalTheme）",
                    theme_card is not None,
                    "卡片没找到（可能只是 push 还没跑完）" if theme_card is None else "",
                )
                if theme_card is not None:
                    combos = _collect_type(theme_card, "ComboBox")
                    check(
                        "「应用主题」带下拉，且选中项跟着配置走",
                        len(combos) == 1
                        and int(combos[0].property("currentIndex"))
                        == {"auto": 0, "light": 1, "dark": 2}.get(
                            str(app.config.get("app.theme")), 0),
                        f"ComboBox={len(combos)} "
                        f"currentIndex={combos[0].property('currentIndex') if combos else None}"
                        f" theme={app.config.get('app.theme')!r}",
                    )

                # ---- 开机自启（2026-10-04 用户指令）----
                # 「打开之后程序会随操作系统启动而启动，关闭也必须有效无误」。
                # ⚠️ 验的是**注册表本身**而不是配置里那个影子值：光看
                # ``config.json`` 变没变，验不出「关了却没关掉」——
                # 那正是这项最容易坏的地方（值没删干净 / 被任务管理器单独禁用）。
                autostart_card = _find_named(general, "generalAutostart")
                autostart_switch = (
                    None if autostart_card is None
                    else (_collect_type(autostart_card, "Switch") or [None])[0]
                )
                check(
                    "通用页有「开机自启」卡与它的开关",
                    autostart_card is not None and autostart_switch is not None,
                    f"card={autostart_card is not None} "
                    f"switch={autostart_switch is not None}",
                )
                check(
                    "开机自启开关回显注册表实际状态（不是配置里的影子值）",
                    autostart_switch is not None
                    and bool(autostart_switch.property("checked"))
                    == autostart.is_enabled(),
                    "checked="
                    f"{None if autostart_switch is None else autostart_switch.property('checked')}"
                    f" registry={autostart.is_enabled()}",
                )
                check(
                    "SETTING_PATHS 里登记了 autostart（否则 QML 写入会被当未知项丢掉）",
                    "autostart" in SETTING_PATHS,
                )

                prev_entry = _run_value()
                try:
                    app.backend.setSetting("autostart", True)
                    QTest.qWait(150)
                    check(
                        "打开开机自启：真的写进了注册表 Run 键",
                        autostart.is_enabled() and _run_value() is not None,
                        f"is_enabled={autostart.is_enabled()} value={_run_value()!r}",
                    )
                    check(
                        "打开后开关点亮（QML 的 checked 跟得上）",
                        autostart_switch is not None
                        and bool(autostart_switch.property("checked")),
                        "checked="
                        f"{None if autostart_switch is None else autostart_switch.property('checked')}",
                    )
                    check(
                        "写入的命令行指向本工程入口（源码运行 = pythonw + main.py）",
                        "main.py" in str(_run_value() or "")
                        and str(_run_value() or "").startswith('"'),
                        f"value={_run_value()!r}",
                    )

                    app.backend.setSetting("autostart", False)
                    QTest.qWait(150)
                    check(
                        "关闭开机自启：注册表里的值被真的删掉了（不是写空串）",
                        not autostart.is_enabled() and _run_value() is None,
                        f"is_enabled={autostart.is_enabled()} value={_run_value()!r}",
                    )
                    check(
                        "关闭后开关熄灭",
                        autostart_switch is not None
                        and not bool(autostart_switch.property("checked")),
                        "checked="
                        f"{None if autostart_switch is None else autostart_switch.property('checked')}",
                    )

                    # 真实鼠标点一下：上面走的是 Python 入口（``setSetting``），
                    # 绕过了 QML 那一层。点一下才能证明 ``onToggled`` 真接上了
                    # 后端 —— 接线断了的话，界面看着能拨、注册表纹丝不动。
                    # ⚠️ 只在这一页刚 push 完（滚动条在顶部）时点：「开机自启」
                    # 是页面第一张卡，位置够高；页面下半部分的卡片落在窗口外，
                    # 鼠标事件发过去什么都不会发生（主界面那页的滑块踩过这坑）。
                    if (autostart_switch is not None
                            and autostart_switch.isVisible()
                            and autostart_switch.width() > 0):
                        before_click = autostart.is_enabled()
                        spot = autostart_switch.mapToScene(
                            QPointF(autostart_switch.width() / 2,
                                    autostart_switch.height() / 2)
                        )
                        QTest.mouseClick(
                            settings, Qt.LeftButton, Qt.NoModifier,
                            QPoint(int(spot.x()), int(spot.y())),
                        )
                        QTest.qWait(250)
                        check(
                            "鼠标点开关真的改了注册表（QML onToggled → setSetting）",
                            autostart.is_enabled() != before_click,
                            f"{before_click} → {autostart.is_enabled()}"
                            f"（点 ({spot.x():.0f},{spot.y():.0f})）",
                        )
                    else:
                        check("开机自启开关可见可点", False, "开关不在可视区")
                finally:
                    # 无论上面怎么走，都要把开发机的启动项还原回去。
                    # ⚠️ 顺序不能反：``setSetting`` 会写它**自己**的命令行，
                    # 先拨后端状态、再原样还原注册表值，后者才不会又被覆盖掉。
                    app.backend.setSetting("autostart", prev_entry is not None)
                    _restore_run_value(prev_entry)
                    QTest.qWait(120)
                    check(
                        "开机自启自检不留副作用",
                        _run_value() == prev_entry,
                        f"{_run_value()!r} 期望 {prev_entry!r}",
                    )

            # ---- 个性化页：只剩「强调色」（2026-10-06 主题模式搬回「通用」）----
            app.windows.show_settings("settings/Personalization.qml")
            fancy = _wait_named(settings.contentItem(), "Personalization")
            check(
                "个性化页能打开（页面根按文件名 Personalization 找得到）",
                fancy is not None,
                "页面没落地（可能只是 push 还没跑完）" if fancy is None else "",
            )
            if fancy is not None:
                accent_card = _find_named(fancy, "personalizationAccent")
                check(
                    "个性化页只剩「强调色」一张卡",
                    accent_card is not None
                    and len(_collect_type(fancy, "SettingCard")) == 1,
                    f"accent={accent_card is not None} "
                    f"卡数={len(_collect_type(fancy, 'SettingCard'))}",
                )
                check(
                    "「应用主题」已搬去通用页、本页不再有它",
                    _find_text(fancy, "应用主题") is None
                    and _find_named(fancy, "personalizationTheme") is None,
                )
                check(
                    "「界面语言」留在通用页、没被一起搬过来",
                    _find_text(fancy, "界面语言") is None,
                )
                if accent_card is not None:
                    swatches = _collect_type(accent_card, "Clip")
                    # 当前色由「勾 + 描边」标记：勾是色块里的 ``Rin.Icon``，
                    # ``visible`` 绑在 ``Backend.settings.accent === modelData`` 上
                    # —— 数出**恰好一个**可见的勾，就证明色板接上了实时配置
                    # （⚠️ 描边 ``border.width`` 是分组属性，PySide 侧读不到，
                    # 只能靠勾来判）。
                    marked = [
                        s for s in swatches
                        if any(c.isVisible() for c in _collect_type(s, "Icon"))
                    ]
                    check(
                        "「强调色」色板 = 8 个圆点，当前色恰有一个被标记",
                        len(swatches) == 8 and len(marked) == 1,
                        f"圆点={len(swatches)} 标记={len(marked)} "
                        f"accent={app.backend.accent}",
                    )

            app.backend.settingsCloseRequested.emit()
            QTest.qWait(150)

        # ---- 删除项的静态守卫（拦「重新加回来」）----
        # 三层都要干净：QML（上面已按真窗口验过）、SETTING_PATHS、默认配置 + 源码残留。
        stale_keys = [
            key for key in (
                "tray_enabled", "tray_tooltip", "tray_show_on_click",
                "tray_notify_on_start", "panel_hide_on_deactivate",
            )
            if key in SETTING_PATHS
        ]
        check(
            "SETTING_PATHS 已无托盘 / 失焦收起五项",
            not stale_keys,
            f"残留={stale_keys}",
        )
        defaults = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
        quick_panel_defaults = defaults.get("quick_panel") or {}
        check(
            "默认配置已删掉 tray 段与 quick_panel.hide_on_deactivate",
            "tray" not in defaults
            and "hide_on_deactivate" not in quick_panel_defaults,
            f"tray={'tray' in defaults} "
            f"hide_on_deactivate={'hide_on_deactivate' in quick_panel_defaults}",
        )
        stale_refs = _scan_symbols(
            ("tray_enabled", "tray_tooltip", "tray_show_on_click",
             "tray_notify_on_start", "panel_hide_on_deactivate",
             'config.get("tray', "def set_tooltip"),
            roots=(ROOT / "ui", ROOT / "app", ROOT / "config", ROOT / "tools"),
            skip=(Path(__file__),),
        )
        check(
            "源码 / 配置里没有已删托盘设置键、tray 配置读取、set_tooltip 的残留引用",
            not stale_refs,
            "; ".join(stale_refs[:6]),
        )

        # 快捷面板底栏「重启」按钮（2026-10-02 用户指令「重新加载按钮实则应当
        # 是重新启动程序按钮」）：原 id=reload 只重读配置，用户点了没感知。
        # 钉三层源码形态：配置里 id=restart、QML 分发到 requestRestart、
        # Python 侧 _restart 真拉新进程（Popen）—— 缺任何一环都等于「点了没反应」。
        # （defaults 上面「删除项静态守卫」已加载过，直接用。）
        footer_actions = (
            ((defaults.get("quick_panel") or {}).get("footer") or {}).get("actions") or []
        )
        restart_ids = [str(a.get("id")) for a in footer_actions]
        check(
            "快捷面板底栏动作是 restart + exit（不再有 reload）",
            "restart" in restart_ids and "reload" not in restart_ids,
            f"actions={restart_ids}",
        )
        qml_src = (ROOT / "ui" / "QuickPanel.qml").read_text(encoding="utf-8")
        check(
            "QuickPanel.qml 把 restart 分发到 Backend.requestRestart()",
            'actionId === "restart"' in qml_src and "requestRestart()" in qml_src,
            f"restart 分发={'actionId === \"restart\"' in qml_src} "
            f"requestRestart={'requestRestart()' in qml_src}",
        )
        app_src = (ROOT / "app" / "application.py").read_text(encoding="utf-8")
        restart_body = app_src.split("def _restart", 1)[-1].split("\n    def ", 1)[0]
        check(
            "application._restart 真拉起新进程（Popen）再退出，失败不退出",
            "subprocess.Popen(" in restart_body
            and "self.quit()" in restart_body
            and "log.exception" in restart_body,
            f"Popen={'subprocess.Popen(' in restart_body} "
            f"quit={'self.quit()' in restart_body} "
            f"失败兜底={'log.exception' in restart_body}",
        )

        # 已删「放映」设置页的残留引用（2026-10-01 第四轮）。
        # ⚠️ 用**带目录**的字面量 ``settings/Presentation.qml``：不带前缀的话
        # 本函数里的 check 标题也会命中（虽然本文件已在 skip 里，但收窄一点更稳）。
        page_refs = _scan_symbols(
            ("settings/Presentation.qml",),
            roots=(ROOT / "ui", ROOT / "app", ROOT / "config", ROOT / "tools"),
            skip=(Path(__file__),),
        )
        check(
            "源码 / 配置里没有指向已删「放映」页的残留引用",
            not page_refs,
            "; ".join(page_refs[:6]),
        )

        # ---- PpSlideShowPointerType 枚举值（钉官方表）----
        # 2026-10-02 实锤：``PP_POINTER_ERASER`` 曾写成 3 —— 而 3 是
        # **AlwaysHidden**，橡皮 = 5（Microsoft Learn 的
        # ``PpSlideShowPointerType`` 枚举表：0=None 1=Arrow 2=Pen
        # 3=AlwaysHidden 4=AutoArrow 5=Eraser）。症状正是用户报的
        # 「切橡皮后没光标、行为类似指针」。这条守卫钉源码里的字面量，
        # 谁改回 3 立刻红。
        ppt_src = (ROOT / "app" / "ppt_controller.py").read_text(encoding="utf-8")

        def _const_value(name: str):
            for line in ppt_src.splitlines():
                m = re.match(rf"^PP_POINTER_{name}\s*=\s*(\d+)", line)
                if m:
                    return int(m.group(1))
            return None

        pointer_values = {n: _const_value(n) for n in
                          ("NONE", "ARROW", "PEN", "ALWAYS_HIDDEN",
                           "AUTO_ARROW", "ERASER")}
        check(
            "PpSlideShowPointerType 枚举值 = 官方表（橡皮是 5，3 是 AlwaysHidden）",
            pointer_values == {"NONE": 0, "ARROW": 1, "PEN": 2,
                               "ALWAYS_HIDDEN": 3, "AUTO_ARROW": 4,
                               "ERASER": 5},
            f"实际={pointer_values}",
        )

        # ---- 快捷方式增删 / 排序 ----
        backend = app.backend
        before = [item["id"] for item in backend.shortcutItems]
        backend.setShortcutEnabled("update", True)
        after_add = [item["id"] for item in backend.shortcutItems]
        check("能启用快捷方式", "update" in after_add, f"{before} -> {after_add}")
        backend.moveShortcut("update", 0)
        moved = [item["id"] for item in backend.shortcutItems]
        check("能调整快捷方式顺序", moved and moved[0] == "update", str(moved))
        backend.setShortcutEnabled("update", False)
        restored = [item["id"] for item in backend.shortcutItems]
        check("能移除快捷方式", "update" not in restored, str(restored))

        # ---- 设置项读写 ----
        # 注意：这里会把值**持久化**进 config/config.json。所以必须先把原值存下来、
        # 结束时原样写回 —— 曾经写成「测完恢复成写死的 8」，于是把旧默认值钉进了
        # 用户配置，后来把默认改成 20 都不生效（2026-09-25 踩到）。
        original_margin = app.config.get("presentation.margin_x")
        backend.setSetting("presentation_margin_x", 24)
        check("设置项已写入配置",
              app.config.get("presentation.margin_x") == 24,
              str(app.config.get("presentation.margin_x")))
        check("设置项已同步到 QML 视图",
              backend.settings.get("presentation_margin_x") == 24,
              str(backend.settings.get("presentation_margin_x")))
        backend.setSetting("presentation_margin_x", original_margin)
        check("设置项已还原（自检不留副作用）",
              app.config.get("presentation.margin_x") == original_margin,
              f"{original_margin} -> {app.config.get('presentation.margin_x')}")

        # ---- 退出键样式可切换（default ↔ danger，两种版式都是直径 44 的圆）----
        # 这条走**内存改配置 + reload_from_config** 的成对用法（``persist=False``），
        # 不落盘 —— 免得像 margin_x 那样往用户配置里钉一个值。
        # 两种版式尺寸完全一样，只能靠暴露出来的填充色 / 图标色区分。
        exit_dock = app.windows._docks.get("bottom_center")
        if exit_dock is not None:
            prev_style = app.config.get("presentation.exit.style")
            base_fill = str(exit_dock.property("exitFillColor"))
            base_icon = str(exit_dock.property("exitIconColor"))

            other = "danger" if (prev_style or "default") != "danger" else "default"
            app.config.set("presentation.exit.style", other, persist=False)
            app.backend.reload_from_config()
            check(
                f"退出键样式已同步到 QML（{prev_style} → {other}）",
                exit_dock.property("exitStyle") == other,
                str(exit_dock.property("exitStyle")),
            )
            check(
                "两种版式的填充/图标色确实不同（尺寸相同时唯一的区分）",
                str(exit_dock.property("exitFillColor")) != base_fill
                and str(exit_dock.property("exitIconColor")) != base_icon,
                f"{base_fill}/{base_icon} -> "
                f"{exit_dock.property('exitFillColor')}/{exit_dock.property('exitIconColor')}",
            )

            app.config.set("presentation.exit.style", prev_style, persist=False)
            app.backend.reload_from_config()
            check(
                "退出键样式已还原（自检不留副作用）",
                str(exit_dock.property("exitFillColor")) == base_fill,
                f"{base_fill} -> {exit_dock.property('exitFillColor')}",
            )

        # ---- 启动画面（设计稿「启动画面 Dark / Light」的还原）----
        # 真机里它由 ``application.run()`` 拉起；smoke 不走 run()（直接 exec），
        # 所以这里手动跑一遍完整生命周期。放在最后，免得那 1080×608 的卡片
        # 一直盖在屏幕上影响别的检查。
        _check_splash(app)
        # ---- 插件断言组（2026-10-06 插件系统计划 Wave 4 任务 13，9 项）----
        # 全部经子进程跑（原因 / 白名单方案 / 清理责任见上方「插件断言组」
        # 一节注释）。放在**最后**：子进程会各自拉起完整应用实例（真窗口），
        # 不能干扰既有断言；主进程保持 app.debug 关，既有断言零影响。
        _check_plugin_suite()
        # 收尾（统计失败数 / 退出事件循环）统一由 run_checks_guarded 的
        # ``finally`` 负责 —— 这里再写一遍只会在抛异常时被跳过，反而留坑。

    def run_checks_guarded() -> None:
        """跑一遍自检，**无论成败都退出事件循环**。

        自检里任何一步抛异常都不能让进程挂在 ``exec()`` 里 —— QTimer 槽里抛出的
        异常不会终止事件循环（PySide 只打一份 traceback），症状是「进程还在、
        CPU 也不高、日志停在某一句」，看起来像卡死，排查方向很容易跑偏。
        2026-10-01 因为 ``navigationItems`` 拿到 QJSValue 抛过 ``TypeError``，
        正是这个表现。
        """
        nonlocal failures
        try:
            run_checks()
        except Exception:
            traceback.print_exc()
            RESULTS.append("[FAIL] 自检过程抛出异常（见上方 traceback）")
        finally:
            failures = sum(1 for line in RESULTS if line.startswith("[FAIL]"))
            qt_app.quit()

    QTimer.singleShot(900, run_checks_guarded)
    code = qt_app.exec()
    app.ppt.shutdown()

    print("\n================ 自检结果 ================")
    for line in RESULTS:
        print(line)
    print(f"=========================================")
    print(f"失败项: {failures}")
    return 1 if failures or code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
