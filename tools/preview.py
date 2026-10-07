"""开发用：把界面离屏渲染成 PNG，便于快速核对版式。

用法::

    .venv\\Scripts\\python.exe tools\\preview.py

输出到 ``preview/``：

- ``quick_panel.png``      —— 快捷面板
- ``top_window.png``       —— 「顶层窗口」（全屏叠加层）+ 内嵌的下中部工具栏与
  屏幕两侧的竖版翻页 pill（预览里用紧凑尺寸代替真实全屏，版式一致）
- ``settings.png``         —— 设置窗口（主页）
- ``splash.png``           —— 启动画面（版式照设计稿「启动画面 Dark / Light」，外观走
  Fluent 2 令牌；用 ``DESIGN_STAGE`` 把进度钉在设计稿那一档，好跟原稿对照版式）
- ``splash_light.png``     —— 同上，浅色版。用 ``LUMI_PREVIEW_THEME=light`` 跑；
  此时别的窗口一律不截图（否则会把上面那些深色预览图覆盖成浅色的）
- ``debug_window.png``     —— 调试窗口（入口是设置标题连点 10 次，不在导航里）
- ``error_report_crash.png`` / ``error_report_error.png`` —— 错误 / 崩溃报告窗
  （``ui/ErrorReport/ErrorReportWindow.qml``）的两档对照：同一张窗，只有文案 /
  表情 / Split Button 的主操作不同（崩溃 = 重新启动，错误 = 忽略）。
  ⚠️ 抓的是**收起**态（堆栈默认藏在「查看详细信息」后面）；``LUMI_PREVIEW_DETAILS=1``
  出展开态，文件名带 ``_details`` 后缀 —— 两档不互相覆盖
- ``main_editor.png``      —— 主界面编辑器（入口是快捷面板的「主界面编辑器」
  快捷方式）。正文是**顶层窗口的完整预览舞台**，抓图前会关掉 ``backdropEnabled``
  以退回兜底底色 —— 离屏抓图看不到 DWM 亚克力层，真机效果得靠实机截屏确认
- ``main_editor_edit.png`` —— 上面那个编辑器停在**编辑态**（``LUMI_PREVIEW_EDIT``
  指定聚焦哪条控制条）
- ``page_*.png``           —— 设置窗口里每个页面单独渲染一张（``NavigationView``
  只有在用户点进去时才创建页面，所以这里用临时宿主窗口把它们全跑一遍）
- ``plugin_demo_settings.png`` / ``plugin_editor_demo.png`` / ``plugin_demo_window.png``
  —— 插件接缝三件套（2026-10-06 插件系统计划 Wave 4 任务 14）：``_demo`` 设置页
  （Loader 宿主）、主界面编辑器选中含 ``_demo_group`` 的角落、``_demo`` 夹具窗口。
  由**子进程**渲染（``LUMI_PREVIEW_PLUGIN_RUN=1``，主进程跑完自动拉起）——
  不同进程的理由见 ``_run_plugin_seams`` 头注释：注册表 freeze 不可逆，且插件
  贡献是读取侧拼进快捷面板 / 设置导航 / 控制条的，同进程加载会把上面那些
  既有预览图（视觉回归的对比基准）污染掉。浅色主题下三件套带 ``_light`` 后缀。

窗口会被放到屏幕外（x = -6000）并强制渲染，因此**不会打扰桌面**，锁屏
（LogonUI 在跑）状态下也能正常出图 —— 离屏渲染不依赖桌面会话（smoke.py
那种真窗口交互才依赖，锁屏必败，别混为一谈）。

环境变量：

- ``LUMI_PREVIEW_THEME=light`` —— 换成浅色主题，且**只**输出启动画面。
- ``LUMI_PREVIEW_ONLY=splash`` —— 保留当前主题但同样只输出启动画面。
- ``LUMI_PREVIEW_PAGE_ONLY=1`` —— 只输出设置页（``page_*.png``），且文件名带
  主题后缀（``page_MainInterface_light.png``）。配 ``LUMI_PREVIEW_THEME=light``
  用来看浅色主题下的页面版式（浅色那档默认只出启动画面）。
- ``LUMI_PREVIEW_PAGE_HEIGHT=<px>`` —— 单页预览（``page_*.png``）的宿主窗口高度，
  默认 940（「主界面」页在 2026-10-01 接收了放映页搬来的 5 张卡之后，640 已经
  截不全 —— 这种「页面比宿主还高」的情况看预览图是**看不出来**的，只能靠
  这个默认值留够）。
- ``LUMI_PREVIEW_PAGE_WIDTH=<px>`` —— 同上，宿主窗口宽度，默认 961 —— 对齐的是
  **真机页面内容列**（不是设置窗口宽度；预览宿主没有左侧导航），见下面
  ``PAGE_WIDTH`` 的推导。太窄会让页面里的并排卡片换行，看着像版式坏了。
- ``LUMI_PREVIEW_EDIT=<corner>`` —— 让主界面编辑器停在**编辑态**并聚焦这个角落
  （如 ``bottom_center``），输出到 ``main_editor_edit.png``。默认输出全景态。
  **配** ``LUMI_PREVIEW_THEME=light`` 时改出编辑器的**浅色**版
  （``main_editor_edit_light.png``，只出这一张）—— 右侧面板 / 面板左沿的圆按钮 /
  预览区上的悬浮缩放缓都取主题色，浅色下的对比度只能靠它核验。
- ``LUMI_PREVIEW_LABELS=1`` —— 打开「显示按钮文本」（``presentation.buttons.
  show_labels``，**只在内存里改、抓完图还原**），控制条按名称文本撑宽。
  输出文件名带 ``_labels`` 后缀，不覆盖常态那两张。
- ``LUMI_PREVIEW_PAGER=side|bottom`` —— 切「翻页组件位置」（``presentation.pager.
  position``，同样只在内存里改、抓完图还原）：side = 竖版两侧中间，bottom = 横版
  两侧下部。输出文件名带 ``_pager_<值>`` 后缀。
- ``LUMI_PREVIEW_SIZES=1`` —— 抓图前打印每个窗口的**实际**尺寸（外加 QML 里声明的
  ``width``/``height``）。两者常常对不上（RinUI 会按内容改写窗口尺寸），量版式时
  以实际尺寸为准；配合 ``debug_window`` 那种「内容变长会不会超出可视区」的判断很省事。
- ``LUMI_PREVIEW_PEN=1`` —— 把工具切到「笔」并**展开笔的选单**（PenPaletteCard），
  输出 ``top_window_pen.png``；``LUMI_PREVIEW_PEN_COLOR`` 指定预点亮的颜色
  （默认 ``#EC4899``，故意跟配置默认的黄色错开，好核对「选中环 + 预览笔迹」）。
- ``LUMI_PREVIEW_PLUGINS=0`` —— 关掉插件接缝三件套的补跑（默认开：常态全量档
  与浅色档跑完后自动起子进程渲染；``_labels`` / ``_pager_*`` / 编辑态 / 笔选单 /
  报告展开这些**对照档**不补跑 —— 插件接缝不受那些开关影响，跑了也是同样的图）。
- ``LUMI_PREVIEW_PLUGIN_RUN=1`` —— 内部标记：本进程即插件接缝子进程，
  只渲染三件套。不要手动用（缺了主进程那套前置就是张空配置）。
- ``LUMI_PREVIEW_ZOOM=1`` —— 把工具切到「放大镜」并**展开放大镜选单**
  （ZoomPanel：缩放 + 四向移位），输出 ``top_window_zoom.png``。
- ``LUMI_PREVIEW_JUMP=1`` —— 把**快速切页面板**（点页码展开的那块）摊开，输出
  ``top_window_jump.png``。页码用 ``main()`` 里注入的那份假状态（第 26 页 / 共 41
  页），所以什么都不用给。这一档会顺手关掉左下角的开发水印 —— 它就画在左翻页条
  那一侧、会盖住面板底行的数字，出图看着像「面板被裁了一行」（2026-10-06 在这上面
  白绕了很久）。配 ``LUMI_PREVIEW_PAGER=side|bottom`` 可以分别看竖版 / 横版两种落点。
- ``LUMI_PREVIEW_THUMBS=0`` —— 关掉快速切页面板的**假缩略图**（默认开）。
  面板上那几十张画面在真机上要走 COM ``Slides(i).Export``，预览进程里没有
  PowerPoint；这里不是塞几张假 URL 糊弄过去，而是拿**真的**
  ``app.slide_thumbs.SlideThumbCache`` 配一个假导出器 —— 队列、代次号、节流、
  Pillow 烤圆角、``file://`` 转换全走真代码，只有「谁来画那张 PNG」换成了本地
  合成图。所以这一档也能证明「QML 那条 Image 路是通的」。

⚠️ 历史坑（2026-10-06 修）：浅色档（``ONLY_SPLASH``）曾在抓完启动画面后
直接 ``return``，既不调 ``qt_app.quit()`` 也不还原主题 —— 进程挂住、
``RinUI/config/rin_ui.json`` 被留在 Light。现在所有档位的还原统一由
``_restore_preview_state`` 在 ``finally`` 里做（见该函数头注释）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
for _path in (str(ROOT), str(TOOLS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
os.chdir(ROOT)

from PySide6.QtCore import QCoreApplication, QObject, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from RinUI import BackdropEffect, RinUIWindow, Theme  # noqa: E402
from RinUI.core.config import RinConfig  # noqa: E402

from app.bridge import Backend  # noqa: E402
from app.config import Config  # noqa: E402
from app.error_handler import ErrorHandler  # noqa: E402
from app.paths import UI_DIR  # noqa: E402
from app.plugins import loader  # noqa: E402
from app.ppt_controller import PresentationState  # noqa: E402
from app.slide_thumbs import SlideThumbCache  # noqa: E402
from app.windows import CORNERS as WM_CORNERS  # noqa: E402
from app.windows import WindowManager  # noqa: E402
from fake_slides import FakeSlideExporter  # noqa: E402

OFFSCREEN_X = -6000
OFFSCREEN_Y = -6000
OUT_DIR = ROOT / "preview"
#: 启动画面预览要钉死的进度：设计稿那张是「60% 创建托盘图标」，照抄好对照。
DESIGN_STAGE = (0.60, "创建托盘图标")
#: 报告窗预览用的样例堆栈（照 ``error_report_*.png`` 里那张参考图的形态）。
REPORT_TRACEBACK = (
    'Traceback (most recent call last):\n'
    '  File "G:\\Dev\\Luminalium-2\\app\\echo_cave.py", line 145, in probe\n'
    '    with socket.create_connection((HOST, PORT), timeout=REMOTE_TIMEOUT):\n'
    '         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n'
    '  File "...\\Lib\\socket.py", line 868, in create_connection\n'
    '    raise exceptions[0]\n'
    '  File "...\\Lib\\socket.py", line 853, in create_connection\n'
    '    sock.connect(sa)\n'
    '    ~~~~~~~~~~~~^^\n'
    'TimeoutError: timed out\n'
)
CORNERS = ("bottom_left", "bottom_center", "bottom_right", "middle_left", "middle_right")

#: 浅色主题（对照设计稿的「启动画面 Light」）。见模块 docstring。
IS_LIGHT = os.environ.get("LUMI_PREVIEW_THEME", "dark").lower().startswith("l")
#: 只渲染设置页（``page_*.png``）。用来核验**浅色主题**下的页面版式 ——
#: 浅色那一版默认只出启动画面（见 ``ONLY_SPLASH``），单独跑这档才看得到页面。
PAGE_ONLY = os.environ.get("LUMI_PREVIEW_PAGE_ONLY", "") not in ("", "0")
#: 主界面编辑器停在编辑态时要聚焦的角落（空 = 全景态）。见模块 docstring。
PREVIEW_EDIT = os.environ.get("LUMI_PREVIEW_EDIT", "").strip()
#: 浅色主题 **+** 编辑态 = 只出编辑器的**浅色**版（``main_editor_edit_light.png``）。
#: 编辑器里的右侧面板、面板左沿的圆按钮、预览区上的悬浮缩放缓都取主题色，
#: 浅色那一档的对比度只能靠这张图核验 —— 浅色主题默认只出启动画面，得单独开口子。
EDITOR_LIGHT = IS_LIGHT and bool(PREVIEW_EDIT)
ONLY_SPLASH = (IS_LIGHT and not PAGE_ONLY and not EDITOR_LIGHT) or os.environ.get(
    "LUMI_PREVIEW_ONLY", "") == "splash"
#: 单页预览的文件名后缀 —— 浅色那次不能把深色的常态图覆盖掉。
THEME_TAG = "light" if IS_LIGHT else "dark"
#: 单页预览的宿主窗口高度。页面长到一屏放不下时调大它（见模块 docstring）。
#: 940 是「最长的那个设置页（主界面）刚好放得下」的档位。
PAGE_HEIGHT = int(os.environ.get("LUMI_PREVIEW_PAGE_HEIGHT", "940") or 940)
#: 单页预览的宿主窗口宽度。默认 **961** —— 对齐的不是「设置窗口有多宽」，而是
#: **真机里页面内容列有多宽**：预览宿主只渲染单个页面（没有左侧导航），所以宿主
#: 宽度要等于真机的**页面宽度**，页面里的卡片版式（尤其是并排的图片 + 文字）才跟
#: 真机一模一样。
#: 推导（2026-10-01 实测，本机屏幕 1755×987 逻辑像素）：
#:   ① 真机窗口宽 = ``min(1755-80, max(1000, 1755*0.64))`` = 1123（``QWindow``
#:      量到 1135，多出的 ~13 是 Windows 不可见 resize 边框）；
#:   ② 真机内容列宽 = **807** —— 用 ``aboutHero`` 量出来（hero 是 ``Layout.fillWidth``，
#:      宽度就等于 ``FluentPage`` 的 ``container``）；
#:   ③ 宿主的左右留白 = 77/侧（在 961 宽的宿主里量过 ``page_About``，hero = 806.9，
#:      与真机 807 差 0.1px）；
#:   → 宿主宽度取 807 + 2×77 = 961。
#: ⚠️ 换显示器 / 改 ``settings.width_ratio`` / 页面 ``horizontalPadding`` 之后这个数
#: 会变，要重量一遍（``J:/tmp/l1probe/probe_page_col.py`` 量真机、
#: ``measure_hero.py`` 量预览图）。
#: 历史值 1000（内容列 846）是「窗口还开 900」那个年代定的，窗口改宽后偏宽 5%，故重算。
PAGE_WIDTH = int(os.environ.get("LUMI_PREVIEW_PAGE_WIDTH", "961") or 961)
#: 控制条「显示按钮文本」的预览开关。**只在内存里改配置**（``persist=False``），
#: 抓完图还原 —— 预览工具不该动用户的 ``config/config.json``。
PREVIEW_LABELS = os.environ.get("LUMI_PREVIEW_LABELS", "") not in ("", "0")
#: 「翻页组件位置」的预览档（side = 竖版两侧中间 / bottom = 横版两侧下部）。
#: 与 ``PREVIEW_LABELS`` 一样只改内存、抓完图还原。见模块 docstring。
PREVIEW_PAGER = os.environ.get("LUMI_PREVIEW_PAGER", "").strip().lower()
if PREVIEW_PAGER not in ("", "side", "bottom"):
    print(f"[WARN] LUMI_PREVIEW_PAGER 只认 side / bottom，收到 {PREVIEW_PAGER!r}，忽略")
    PREVIEW_PAGER = ""
#: 笔的选单（PenPaletteCard）预览：把工具切到「笔」并展开选单，输出
#: ``top_window_pen.png``。同样只改内存。
PREVIEW_PEN = os.environ.get("LUMI_PREVIEW_PEN", "") not in ("", "0")
#: 选单预览里预点亮的颜色（``presentation.pen.default`` 之外另挑一个，
#: 好把「选中环 + 预览笔迹跟着变」一起看掉）。
PREVIEW_PEN_COLOR = os.environ.get("LUMI_PREVIEW_PEN_COLOR", "#EC4899")
#: 报告窗出「查看详细信息」展开那一档（默认收起）
PREVIEW_DETAILS = os.environ.get("LUMI_PREVIEW_DETAILS", "") not in ("", "0")
#: 本进程是否就是插件接缝子进程（主进程拉起的内部标记，见模块 docstring）。
PLUGIN_RUN = os.environ.get("LUMI_PREVIEW_PLUGIN_RUN", "") not in ("", "0")
#: 浅色主题 **+** 笔选单 = 只出那一张（``top_window_pen_light.png``）。
#: 浅色档默认只出启动画面，看选单得单独开口子 —— 与 ``EDITOR_LIGHT`` 同一个理由：
#: 色板底色、描边、小标题都取主题色，浅色下「白点/黑点会不会与底色糊在一起」
#: 只有这张图能核验。
PEN_LIGHT = IS_LIGHT and PREVIEW_PEN
if PEN_LIGHT:
    ONLY_SPLASH = False  # noqa: F811 - 见上：把「浅色只出启动画面」让开
#: 放大镜选单（ZoomPanel）预览：把工具切到「放大镜」并展开选单，输出
#: ``top_window_zoom.png``。同样只改内存。
PREVIEW_ZOOM = os.environ.get("LUMI_PREVIEW_ZOOM", "") not in ("", "0")
#: 浅色主题 **+** 放大镜选单 = 只出那一张（``top_window_zoom_light.png``）。
#: 理由同 ``PEN_LIGHT``：卡片底色 / 描边 / 小标题都取主题色。
ZOOM_LIGHT = IS_LIGHT and PREVIEW_ZOOM
if ZOOM_LIGHT:
    ONLY_SPLASH = False  # noqa: F811 - 见上：把「浅色只出启动画面」让开
#: 快速切页面板（PageJumpPanel，点页码展开的那块）预览：展开面板，输出
#: ``top_window_jump.png``。
#:
#: 页码数据不用管：``main()`` 开头的 ``backend.apply_state`` 已经把
#: ``slideIndex`` / ``slideTotal`` 摆成「第 26 页 / 共 41 页」，面板读的就是它。
#:
#: ⚠️ 展开时会顺手把面板的 ``animate`` 关掉 —— 预览在**屏幕外**建窗口抓帧，
#: ``Behavior`` 的时间轴在那种环境下推进不可靠（面板会停在 ``reveal`` 0、整块
#: 不显示；同一份面板在可见窗口 / 离屏窗口 / TopWindow 宿主里都实测正常，见
#: ``tools/jump_probe.py``）。抓图要的是稳定终态，不是动画中间态。
PREVIEW_JUMP = os.environ.get("LUMI_PREVIEW_JUMP", "") not in ("", "0")
#: 给快速切页面板喂**假缩略图**（默认开，``LUMI_PREVIEW_THUMBS=0`` 关）。
#:
#: ⚠️ 真假要说清楚：绕过去的只有「谁来画那张 PNG」（真机是 COM
#: ``Slides(i).Export``，这里是在本地现画一张合成图）。队列 / 代次号 / 节流 /
#: Pillow 烤圆角 / ``file://`` 转换全走 ``app.slide_thumbs`` 的真代码，
#: 所以这一档同时是那条链路的**端到端验证**。
PREVIEW_THUMBS = PREVIEW_JUMP and os.environ.get(
    "LUMI_PREVIEW_THUMBS", "") not in ("0", "false", "False")
#: 浅色主题 **+** 切页面板 = 只出那一张（``top_window_jump_light.png``）。
#: 理由同 ``PEN_LIGHT``：当前页那块描边是 accent，浅色下读不读得出来只有这张图能核验。
JUMP_LIGHT = IS_LIGHT and PREVIEW_JUMP
if JUMP_LIGHT:
    ONLY_SPLASH = False  # noqa: F811 - 同上
#: 翻页组件位置 → 该形态下**启用**的角落（与 bridge.py 的常量同一份口径）
PAGER_POSITION_CORNERS = {
    "side": ("middle_left", "middle_right"),
    "bottom": ("bottom_left", "bottom_right"),
}


def preview_name(name: str) -> str:
    """给预览图文件名加后缀（``_labels`` / ``_pager_<值>``）。

    这些只是**对照图**，不该把常态那几张覆盖掉（控制条与编辑器两张都要加）。
    """
    stem, ext = os.path.splitext(name)
    if PREVIEW_LABELS:
        stem += "_labels"
    if PREVIEW_PAGER:
        stem += f"_pager_{PREVIEW_PAGER}"
    return stem + ext


def _find_by_name(item, name: str):
    """在 QQuickItem 树里按 objectName 找一项（``smoke.py`` 同名辅助的精简版）。"""
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _find_by_name(child, name)
        if found is not None:
            return found
    return None


def _restore_preview_state(rinui, config, backend, previous_theme: str,
                           previous_effect, labels_previous, pager_previous) -> None:
    """把预览期间的**全局副作用**全部还原。

    ⚠️⚠️ ``setTheme`` / ``setBackdropEffect`` / ``set_theme_color`` 都会**持久化到
    ``RinUI/config/rin_ui.json``**，也就是真机下次启动读的那份。三件事必须还原：

    *主题* —— 浅色那档跑完要切回原值，否则开发机上整个应用的下次启动变成浅色；
    *背景特效* —— 预览要实色底板（``grabWindow`` 拿不到 DWM 合成层）才关成
      ``None_``，跑完必须还原成用户原来选的那档；
    *配置* —— ``show_labels`` / ``pager.position`` 是 ``persist=False`` 的内存改动，
      这里再从source重载一次。

    **必须在 ``finally`` 里调**，不能只放在 ``capture()`` 末尾：``capture()`` 里有
    好几条提前 ``return``（浅色只出启动画面 / 只出设置页 / 编辑器浅色 / 笔选单），
    历史上还原代码就写在最后一条return 之后，于是那些档位**一个都没还原**——
    实测一次跑完 ``LUMI_PREVIEW_THEME=light LUMI_PREVIEW_PAGE_ONLY=1`` 之后，
    ``RinUI/config/rin_ui.json`` 里``current_theme`` 留下了 ``"Light"``
    （项目 ``app.theme`` 是 ``auto``），背景特效也永久变成 ``None``。
    进程被打断（Ctrl+C / 超时被杀）同样会留下这份脏数据。
    """
    if rinui.theme_manager.get_theme_name() != previous_theme:
        rinui.theme_manager.toggle_theme(previous_theme)
        # ⚠️⚠️ 必须显式落盘。``toggle_theme`` 只改内存里的 ``RinConfig``，
        #    真正写文件的是 ``theme_manager.clean_up()`` —— 而它在**进程退出时**
        #    才跑。只调 toggle 的话屏幕上会打印「主题已还原为 Auto」而
        #    ``rin_ui.json`` 里仍是 ``"Light"``：下一轮跑页面预览就会把 Light
        #    当成「原值」还原，深浅两套图的主题就此串味。
        RinConfig.save_config()
        print(f"[OK] 主题已还原并落盘为 {previous_theme}")
    if rinui.theme_manager.get_backdrop_effect() != previous_effect:
        # ⚠️ 走``apply_backdrop_effect``（收str）而不是 ``setBackdropEffect``
        #    （收 ``BackdropEffect`` 枚举）：``get_backdrop_effect()`` 返回的是
        #    **字符串**（直接读 ``RinConfig["backdrop_effect"]``），把它喂给
        #    ``setBackdropEffect`` 会在``.value`` 上抛 AttributeError。
        rinui.theme_manager.apply_backdrop_effect(previous_effect)
        print(f"[OK] 背景特效已还原为 {previous_effect}")
    if PREVIEW_LABELS:
        config.set("presentation.buttons.show_labels", labels_previous,
                   persist=False)
    if PREVIEW_PAGER:
        config.set("presentation.pager.position", pager_previous, persist=False)
        enabled = PAGER_POSITION_CORNERS.get(pager_previous, ())
        for corners in PAGER_POSITION_CORNERS.values():
            for corner in corners:
                config.set(f"presentation.corners.{corner}.enabled",
                           corner in enabled, persist=False)
    if PREVIEW_LABELS or PREVIEW_PAGER:
        backend.reload_from_config()
        print(f"[OK] 预览用的一次性改动已还原"
              f"（show_labels={labels_previous}, pager.position={pager_previous}）")


def _grab_pair(window, name: str):
    """抓两帧、留第二帧，返回 ``(路径, 宽高)`` 或 ``None``。

    ⚠️ ``grabWindow()`` 是同步渲染，但**待处理的场景图更新**（刚被 QML 创建出来
    的项、刚跑完动画写进去的属性）要等下一次同步才会落进画面 —— 于是第一次抓到
    的可能是「还差几块」的那一帧。2026-10-01 实测：第一次跑出来的图里右侧面板、
    面板贴边、暗罩都在，**预览区里那条控制条与底部的悬浮缩放缓整块不见**；
    同一份代码再跑一次就全了。先抓一帧丢掉等于手动把待处理的更新推完。
    """
    try:
        window.grabWindow()
        image = window.grabWindow()
    except RuntimeError as exc:  # 窗口已被 QML 引擎回收
        print(f"[FAIL] {name}: {exc}")
        return None
    if image.isNull():
        print(f"[FAIL] {name}: grabWindow() 返回空图")
        return None
    path = OUT_DIR / name
    image.save(str(path))
    print(f"[OK] {name} -> {path} ({image.width()}x{image.height()})")
    return path


def _apply_page_overrides(hosts) -> set:
    """``LUMI_PREVIEW_SET="objectName,prop,value[;…]"`` —— 抓图前把页面摆到某个状态。

    有些版式只在一个状态里看得到（最典型：「更新设置」那个 Tab 的内容，
    默认选中的是「更新日志」，不切过去就永远抓不到）。页面宿主的底板是登记过的，
    所以这里出的图**可信** —— 比拿未登记宿主的探针截图看配色靠谱。

    ⚠️ 值只做「整数 / 其余当字符串」两档猜测，够用就行；要传别的类型再加。

    返回**被改到**的那些窗口的集合：只有它们才需要加``LUMI_PREVIEW_TAG`` 后缀，
    免得把一个「切了 Tab」的状态名贴到所有页面头上。
    """
    specs = [s.strip() for s in os.environ.get("LUMI_PREVIEW_SET", "").split(";")
             if s.strip()]
    touched: set = set()
    if not specs:
        return touched
    for _name, window in hosts:
        root = window.contentItem()
        for spec in specs:
            parts = [p.strip() for p in spec.split(",")]
            if len(parts) != 3:
                print(f"[WARN] LUMI_PREVIEW_SET 只认 objectName,prop,value，收到 {spec!r}")
                continue
            target_name, prop, raw = parts
            target = _find_by_name(root, target_name)
            if target is None:      # 这个页面里没有该项，正常，跳过
                continue
            value: object = int(raw) if raw.lstrip("-").isdigit() else raw
            target.setProperty(prop, value)
            touched.add(id(window))
            print(f"[SET] {target_name}.{prop} = {value!r}")
    return touched


def _run_page_only(rinui, qt_app, config, backend, previous_theme: str,
                   previous_effect, labels_previous, pager_previous) -> int:
    """``LUMI_PREVIEW_PAGE_ONLY=1`` 的专用短路：只建页面宿主，立刻抓图收工。

    ⚠️ 为什么要单独开一条路：原先这一档只是把 ``capture()`` 的``targets``
    缩到 ``page_*.png``，**前面那一大段建窗口的代码照跑** —— 顶层窗口 + 五个
    角落停靠 + 设置窗 + 启动画面 + 调试窗 + **主界面编辑器** + 报告窗，一个都不
    少。主界面编辑器是整套 UI 里最重的一个（相机动画 + 大量贴图），实测这一档
    单跑要二十多分钟还没出图，最后是被手动杀掉的。

    现在这一档只留必需的：``QuickPanel``（``rinui.load`` 的宿主，主题/Backdrop
    都靠它生效）+ 页面宿主。跑完立刻 ``quit()``，不再等 1.8s 的动画停稳。
    """
    OUT_DIR.mkdir(exist_ok=True)
    hosts = _build_page_hosts(rinui.engine)
    if not hosts:
        print("[FAIL] 一个页面宿主都没建起来")
        return 1

    # 先把页面摆到目标状态（Loader 是同步的，树已经在了），再等它铺完
    touched = _apply_page_overrides(hosts)
    tag = os.environ.get("LUMI_PREVIEW_TAG", "").strip()
    suffix = f"_{tag}" if (tag and touched) else ""

    def shoot() -> None:
        for name, window in hosts:
            extra = suffix if id(window) in touched else ""
            _grab_pair(window, name.replace(".png", f"{extra}_{THEME_TAG}.png"))
        qt_app.quit()

    # 页面都是静态版式，没有级联动画，给 0.6s 让 Loader 把页面铺完即可
    # （比常态那档的 1.8s 短；这里等的不是动画而是首帧合成）。
    # 切过状态的那一档要更久：Tab 内容那个 ``Loader`` 是切过去才构造的。
    QTimer.singleShot(1200 if touched else 600, shoot)
    return qt_app.exec()


def main() -> int:
    if PLUGIN_RUN:
        # 插件接缝子进程：只渲染三件套，主流程的窗口一概不建（见模块 docstring）
        return _run_plugin_seams()
    config = Config()
    # 「显示按钮文本」预览：改内存里的配置（控制条读它），抓完图在 capture() 里还原。
    labels_previous = config.get("presentation.buttons.show_labels")
    if PREVIEW_LABELS:
        config.set("presentation.buttons.show_labels", True, persist=False)
    # 「翻页组件位置」预览：同样只改内存 —— 它连带开关四个角落（真实生效的是
    # corners，所以两边一起改，否则预览里还是旧形态）。
    pager_previous = config.get("presentation.pager.position") or "side"
    if PREVIEW_PAGER:
        config.set("presentation.pager.position", PREVIEW_PAGER, persist=False)
        for corners in PAGER_POSITION_CORNERS.values():
            for corner in corners:
                config.set(f"presentation.corners.{corner}.enabled",
                           corner in PAGER_POSITION_CORNERS[PREVIEW_PAGER],
                           persist=False)

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, qt_app)
    # 编辑器分组注册表登记（2026-10-05 插件系统 Wave 2 任务 9）：编辑器的
    # 组件名 / 图标 / 语义判定改从 ``Backend.presentationGroups`` 读注册表，
    # 而预览不走 ``WindowManager.load_windows``，内建组必须在这里补登记，
    # 否则编辑器会把内建角落当未知组、组件名回落「控制条」。函数体不读
    # ``self`` 状态（幂等，先查再登记），直接以类方法形式调用。
    WindowManager._register_builtin_groups(None)
    backend.apply_state(
        PresentationState(active=True, slide_index=26, slide_total=41)
    )
    # ---- 快速切页面板的缩略图（真 cache + 假导出器，见 PREVIEW_THUMBS）----
    # 必须在 ``apply_state`` **之后**接：真应用里 ``set_show`` 是跟着状态快照走的
    # （见 bridge.apply_state），这里状态刚置好，手动补一次开场。
    if PREVIEW_THUMBS:
        thumbs = SlideThumbCache(FakeSlideExporter(), backend)
        backend.attach_slide_thumbs(thumbs)
        thumbs.set_show(True, 41)
        # burst 拉满：真机上那个 500ms 节流是给 COM 省的，这里的假导出器没有 COM
        # 开销，所以一次投满 —— 抓图前必须全部就位，否则抓到的是「加载中」的样子
        thumbs.request(1, 41, burst=41)
        ready = sum(1 for url in thumbs.urls if url)
        print(f"[THUMBS] 假缩略图 {ready}/{len(thumbs.urls)} -> {thumbs.directory}")
    backend.setSplashStage(*DESIGN_STAGE)
    # 报告窗的数据源。⚠️ 这里**不**调 ``install()`` —— 预览工具不该去接管
    # ``sys.excepthook``（本进程里没有真实异常要报告，接管只会让真报错被吞）。
    error_handler = ErrorHandler(config, qt_app)

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent")))
    # ⚠️ ``setTheme`` 会**持久化到 RinUI/config/rin_ui.json**，所以跑浅色那一版
    # 必须记下原值、截完图再切回去 —— 否则开发机上整个应用的下次启动会变成浅色。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Light if IS_LIGHT else Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    rinui.engine.rootContext().setContextProperty("ErrorHandler", error_handler)
    rinui.load(UI_DIR / "QuickPanel.qml")
    # 预览图不需要 DWM 背景特效，关掉能拿到实色背景（结束后恢复，避免污染用户配置）
    previous_effect = rinui.theme_manager.get_backdrop_effect()
    rinui.setBackdropEffect(BackdropEffect.None_)

    panel = rinui.root_window
    panel.setPosition(OFFSCREEN_X, OFFSCREEN_Y)
    panel.show()

    # 「只出设置页」档：就地短路走 _run_page_only，别再往下建主界面编辑器等
    # 一堆这一档根本不会截图的窗口（实测能拖到二十多分钟出不来图）。
    if PAGE_ONLY:
        try:
            return _run_page_only(rinui, qt_app, config, backend, previous_theme,
                                  previous_effect, labels_previous, pager_previous)
        finally:
            _restore_preview_state(rinui, config, backend, previous_theme,
                                   previous_effect, labels_previous, pager_previous)

    # ---- 顶层窗口（全屏叠加层）+ 内嵌控制条 ----
    # 预览用紧凑尺寸（1100x640）代替真实全屏；定位逻辑与 app/windows.py 一致。
    PREVIEW_W, PREVIEW_H = 1100, 640
    top_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "TopWindow.qml"))
    )
    top_window = None
    if top_component.isError():
        for error in top_component.errors():
            print("TOP WINDOW ERROR:", error.toString())
    else:
        top_window = top_component.createWithInitialProperties({"visible": True})
        if top_window is None:
            print("TOP WINDOW CREATE ERROR")
        else:
            top_window._top_component = top_component  # 持有引用防引擎回收
            top_window.setWidth(PREVIEW_W)
            top_window.setHeight(PREVIEW_H)
            top_window.setPosition(OFFSCREEN_X - 400, OFFSCREEN_Y)
            top_window.show()

    dock_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "PresentationDock.qml"))
    )
    if dock_component.isError():
        for error in dock_component.errors():
            print("DOCK ERROR:", error.toString())
    side_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "presentation" / "SidePager.qml"))
    )
    if side_component.isError():
        for error in side_component.errors():
            print("SIDE PAGER ERROR:", error.toString())

    container = top_window.property("container") if top_window is not None else None
    margin_x = int(config.get("presentation.margin_x", 20))
    margin_y = int(config.get("presentation.margin_y", 20))
    corners_cfg = config.get("presentation.corners", {}) or {}
    for corner in CORNERS:
        if not (corners_cfg.get(corner) or {}).get("enabled", False):
            continue
        # ⚠️ 用哪个组件**必须**问 ``WindowManager._resolve_dock_qml``（注册表驱动），
        # 别在这里按角名前缀自己判 —— 那是本工具曾经自己写的一套判断，
        # 2026-10-07 实测就被它骗了：合并角落（工具栏 + 翻页器拼一个 dock）落
        # middle_left 时它按 ``middle`` 前缀选了 SidePager，图上只剩一个翻页 pill，
        # 工具组整个不出现，而真机跑的是 PresentationDock。
        dock_qml = WindowManager._resolve_dock_qml(
            corner, (corners_cfg.get(corner) or {}).get("groups") or [])
        component = side_component if dock_qml is None or dock_qml.name == "SidePager.qml" else dock_component
        # 摆位用**角落对齐**（middle = 垂直居中），与 ``windows.py::_position_dock``
        # 同源 —— 别拿「用了哪个组件」当代判据，合并角落是竖版 dock。
        vertical = WM_CORNERS.get(corner, ("left", "bottom"))[1] == "middle"
        dock = component.createWithInitialProperties({"corner": corner})
        if dock is None:
            for error in component.errors():
                print(f"DOCK {corner} ERROR:", error.toString())
            continue
        dock._dock_component = component  # 持有引用防引擎回收
        dock.setParentItem(container)
        # 与 windows.py::_position_dock 同语义：margin 是**视觉距离**，
        # 要扣掉控制条自带的投影余量（否则预览里的间距会比真机大 24px）
        shadow = int(dock.property("shadowMargin") or 0)
        if corner.endswith("left"):
            x = margin_x - shadow
        elif corner.endswith("center"):
            x = (PREVIEW_W - dock.width()) // 2
        else:
            x = PREVIEW_W - dock.width() - margin_x + shadow
        if vertical:
            # 竖版：垂直居中（L1 .flipper 默认形态）。⚠️ 判据是角落的**垂直对齐**
            # （middle），不是「用哪个组件」—— 合并角落是竖版 dock，同样居中。
            dock.setY((PREVIEW_H - dock.height()) // 2)
        else:
            dock.setY(PREVIEW_H - dock.height() - margin_y + shadow)
        dock.setX(x)

    # 笔的选单预览：把工具切到「笔」（分段高亮成笔）并展开底中那条工具栏上的
    # 选单 —— 一并设好一个「已选中的颜色」，好把「选中环 + 预览笔迹同色」看掉。
    if PREVIEW_PEN and container is not None:
        backend.selectTool("pen")
        backend.setPenColor(PREVIEW_PEN_COLOR)
        center_dock = _find_by_name(container, "penPalette")
        # 底中那条工具栏才有工具组；找不到就不管（角落配置里没有它）
        if center_dock is not None:
            center_dock.setProperty("opened", True)
        else:
            print("[WARN] 没找到 penPalette（底中工具栏没启用工具组？）")

    # 放大镜选单预览：开放大镜（条上那枚独立圆钮点亮）并展开底中那条
    # 工具栏上的选单 —— 与笔选单同一条路径，只是这一块里是「缩放 + 移位」两段。
    #
    # ⚠️ **一遍就够，不要「先收起再开」**（2026-10-06）。早先这里设两遍，注释写的是
    #    「第一次会被 ``activeToolChanged`` 的处理器收掉」—— 那次诊断错了：收掉面板的
    #    是分段的 ``currentIndex`` 绑定把工具真切回了 ``arrow``，再由那个处理器顺手
    #    ``zoomPanel.opened = false``。放大镜改用独立的 ``setZoomActive`` 之后这条路
    #    已经走不到，但两遍设值仍没必要 —— 留着只会让人以为有顺序依赖。
    if PREVIEW_ZOOM and container is not None:
        backend.setZoomActive(True)
        for dock_item in container.childItems():
            panel_item = _find_by_name(dock_item, "zoomPanel")
            if panel_item is None:
                continue
            # ⚠️ 同 ``PREVIEW_JUMP``：离屏抓帧时 ``Behavior`` 推进不可靠，
            #    关掉动画拿稳定终态。
            panel_item.setProperty("animate", False)
            panel_item.setProperty("opened", True)
        QGuiApplication.processEvents()

    # 快速切页面板预览：点页码展开的那块。横版（``pageJumpPanel``）与竖版
    # （``sidePageJumpPanel``）各有一个实例，**两个都展开** —— 它们的落点不一样
    # （横版往上长、竖版往屏幕内侧长），一张图看不全两种形态。
    #
    # ⚠️ 页码**不注入假数据**：``main()`` 开头的 ``backend.apply_state`` 已经把
    #    ``slideIndex`` / ``slideTotal`` 摆成了「第 26 页 / 共 41 页」，面板读的
    #    就是它。注入反而会打断 QML 侧的绑定，看到的不是真链路。
    #
    # ⚠️ ``animate: false`` 是必须的：预览在屏幕外建窗口抓帧，``Behavior`` 的
    #    时间轴在这种环境下推进不可靠（面板会停在 ``reveal`` 0、整块不显示）。
    #    组件在可见窗口 / 离屏窗口 / TopWindow 宿主里都实测正常 —— 见
    #    ``tools/jump_probe.py``；抓图要的是稳定终态，不是动画中间态。
    if PREVIEW_JUMP and container is not None:
        # ⚠️ 先关掉左下角的**开发水印**：它正好画在左翻页条那一侧的下面，会盖住
        #    面板最底下一行的数字 —— 出图时看起来活像「面板被裁了一行」，而
        #    右侧那块（没被遮）又是完整的，对比之下非常像一个真 bug（2026-10-06
        #    在这上面绕了很久）。这一档要的是干净的面板版式，水印另开一档看。
        watermark = top_window.property("watermarkItem") if top_window is not None else None
        if watermark is not None:
            watermark.setVisible(False)

        expanded = []
        # ⚠️ 逐个 dock 展开，**不能**在 container 上找名字：``_find_by_name`` 只返回
        #    第一个匹配 —— 两个竖条各有一块面板，那样只会展开左边那条。
        for dock_item in container.childItems():
            corner = str(dock_item.property("corner") or "")
            # 底中那条是**工具栏**（groups 里没有 pager）：那个角落没有页码区，
            # 面板实例只是跟着组件建出来的，`total` 是 0 —— 展开只会多出一块空卡片
            if corner.startswith("bottom_center"):
                continue
            for panel_name in ("pageJumpPanel", "sidePageJumpPanel"):
                panel_item = _find_by_name(dock_item, panel_name)
                if panel_item is None:
                    continue
                panel_item.setProperty("animate", False)
                panel_item.setProperty("opened", True)
                expanded.append(f"{corner}:{panel_name}")

                # 抓图前打一行几何：这块面板的坑**全在这一行数字里** ——
                # 卡片高被钳到一张卡（可用高度算错）、面板没贴到窗口边（x/y 算错）、
                # 明明放得下却有滚动条（``viewport`` < ``content``）。
                # 出图之后先看这一行，能省掉「盯着 PNG 猜哪里错了」那一步。
                def _report(it=panel_item, tag=f"{corner}:{panel_name}") -> None:
                    flick_item = _find_by_name(it, "pageJumpFlickable")
                    print(f"[JUMP] {tag} side={it.property('side')} "
                          f"card={it.property('cardWidth'):.0f}x"
                          f"{it.property('cardHeight'):.0f} "
                          f"item={it.property('itemWidth'):.0f}x"
                          f"{it.property('itemHeight'):.0f} "
                          f"content={it.property('contentHeight'):.0f} "
                          f"viewport={it.property('viewportHeight'):.0f} "
                          f"maxW={it.property('maxWidth'):.0f} "
                          f"maxH={it.property('maxHeight'):.0f} "
                          f"rect=({it.property('x'):.0f},"
                          f"{it.property('y'):.0f}) "
                          f"scroll={it.property('scrollable')} "
                          f"thumbs={it.property('readyCount')}/"
                          f"{it.property('total')} "
                          f"contentY="
                          f"{flick_item.property('contentY') if flick_item else '?'}")

                QTimer.singleShot(300, _report)
        print(f"[JUMP] 已展开: {expanded or '（一个都没找到）'}")

    # 设置窗口：默认页由 NavigationView 在 Component.onCompleted 里推入
    settings = None
    settings_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "Settings.qml"))
    )
    if settings_component.isError():
        for error in settings_component.errors():
            print("SETTINGS ERROR:", error.toString())
    else:
        settings = settings_component.createWithInitialProperties({"visible": True})
        if settings is None:
            for error in settings_component.errors():
                print("SETTINGS CREATE ERROR:", error.toString())
        else:
            settings.setPosition(OFFSCREEN_X, OFFSCREEN_Y - 900)
            settings.show()

    # 启动画面：设计稿还原结果。它是个**无边框透明窗口**（刻意不登记 RinUI），
    # 所以只能单独建实例；尺寸由 QML 自己定（设计稿 2984×1679 等比缩到 1080 宽）。
    splash = None
    splash_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "SplashWindow.qml"))
    )
    if splash_component.isError():
        for error in splash_component.errors():
            print("SPLASH ERROR:", error.toString())
    else:
        splash = splash_component.createWithInitialProperties({"visible": True})
        if splash is None:
            for error in splash_component.errors():
                print("SPLASH CREATE ERROR:", error.toString())
        else:
            splash._splash_component = splash_component  # 持有引用防引擎回收
            splash.setPosition(OFFSCREEN_X - 1500, OFFSCREEN_Y)
            splash.show()

    # 调试窗口：隐藏入口（设置窗口标题连点 10 次），与设置窗口同属按需创建，
    # 所以预览里也得单独建一个实例才看得到版式
    debug = None
    debug_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "DebugWindow.qml"))
    )
    if debug_component.isError():
        for error in debug_component.errors():
            print("DEBUG WINDOW ERROR:", error.toString())
    else:
        debug = debug_component.createWithInitialProperties({"visible": True})
        if debug is None:
            for error in debug_component.errors():
                print("DEBUG WINDOW CREATE ERROR:", error.toString())
        else:
            debug._debug_component = debug_component  # 持有引用防引擎回收
            debug.setPosition(OFFSCREEN_X, OFFSCREEN_Y - 1000)
            debug.show()

    # 主界面编辑器：入口是快捷面板的「主界面编辑器」快捷方式，与设置 / 调试窗口
    # 一样是按需创建，预览里同样单独建一个实例。
    #
    # ⚠️ 建完要**关掉** ``backdropEnabled``：编辑器窗口的背景是「整窗透明 +
    # DWM 亚克力」，而离屏抓图（``QQuickWindow.grabWindow``）拿的是 Qt 自己的
    # 渲染结果，**不含 DWM 合成层** —— 不关的话抓到的是透明（白）底板，正文像
    # 浮在半空中。关掉后 QML 会退回 Fluent 的亚克力兜底色，预览才有东西可看。
    # 真机上的亚克力由 ``windows.py::_apply_acrylic`` 负责，与这个开关无关。
    editor = None
    editor_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "MainInterfaceEditor.qml"))
    )
    if editor_component.isError():
        for error in editor_component.errors():
            print("EDITOR ERROR:", error.toString())
    else:
        editor = editor_component.createWithInitialProperties({"visible": True})
        if editor is None:
            for error in editor_component.errors():
                print("EDITOR CREATE ERROR:", error.toString())
        else:
            editor._editor_component = editor_component  # 持有引用防引擎回收
            editor.setProperty("backdropEnabled", False)
            editor.setPosition(OFFSCREEN_X - 1000, OFFSCREEN_Y - 900)
            editor.show()
            # 编辑态预览：钉一个聚焦目标，好核对「聚焦放大 + 暗罩 + 高亮 + 右侧面板」
            # 这一整套编排（相机有 220ms 动画，抓图在 1.8s 后，早就停稳了）。
            #
            # ⚠️ 光钉 ``selectedCorner`` 还不够：窗口摆在屏幕外**从没被暴露过**时，
            # 抓图可能拿到**上一帧**的合成结果 —— 实测偶发过一次
            # ``main_editor_edit.png`` 里右侧面板整块不见了（而同一时刻读
            # ``inspectorReveal`` 明明是 1.0）。抬一次窗口催曝光就稳了，
            # 与 ``smoke.py::_nudge_editor`` 同一个办法。
            if PREVIEW_EDIT:
                editor.setProperty("selectedCorner", PREVIEW_EDIT)
                editor.raise_()
                editor.requestActivate()

    # 错误 / 崩溃报告窗：入口是 ``ErrorHandler`` 捕获到未捕获异常（同样是按需
    # 创建）。一张窗承接两档报告，版式相同、只有文案 / 表情 / 主按钮不同 ——
    # 所以下面抓图时切一次 ``ErrorHandler`` 的状态，出两张对照图。
    #
    # ⚠️ 必须以 ``visible: True`` 建实例再挪到屏幕外（与上面几个窗口一致）。
    # 实测：``visible: False`` 建出来再 ``setPosition(-6000,-6000)`` + ``show()``
    # 的话，窗口**从未被暴露**，``contentItem`` 一直是 0×0 —— 抓到的是一张
    # 所有控件叠在左上角的废图。
    error_report = None
    error_report_component = QQmlComponent(
        rinui.engine,
        QUrl.fromLocalFile(str(UI_DIR / "ErrorReport" / "ErrorReportWindow.qml")),
    )
    if error_report_component.isError():
        for error in error_report_component.errors():
            print("ERROR REPORT WINDOW ERROR:", error.toString())
    else:
        error_report = error_report_component.createWithInitialProperties({"visible": True})
        if error_report is None:
            for error in error_report_component.errors():
                print("ERROR REPORT WINDOW CREATE ERROR:", error.toString())
        else:
            error_report._report_component = error_report_component  # 防引擎回收
            error_report.setPosition(OFFSCREEN_X - 500, OFFSCREEN_Y - 1800)
            error_report.show()

    # 各设置页单独渲染：用临时宿主窗口 + Loader 承载，逐页跑一遍
    page_hosts = _build_page_hosts(rinui.engine)

    OUT_DIR.mkdir(exist_ok=True)

    def capture() -> None:
        splash_name = "splash_light.png" if IS_LIGHT else "splash.png"
        if ONLY_SPLASH:
            # 只出启动画面：别的窗口照旧建着（都摆在屏幕外），但不截图 ——
            # 否则浅色那一版会把上面所有深色预览图覆盖掉。
            targets = [] if splash is None else [(splash_name, splash)]
        elif PAGE_ONLY:
            # 只出设置页（用来核验浅色主题下的页面版式），同样加主题后缀
            targets = [
                (name.replace(".png", f"_{THEME_TAG}.png"), window)
                for name, window in page_hosts
            ]
        elif EDITOR_LIGHT:
            # 浅色主题 + 编辑态：只出编辑器的浅色版（见 ``EDITOR_LIGHT``）
            targets = ([] if editor is None
                       else [("main_editor_edit_light.png", editor)])
        elif PEN_LIGHT or JUMP_LIGHT or ZOOM_LIGHT:
            # 浅色主题 + 某一个浮出层（笔选单 / 放大镜选单 / 快速切页面板）：
            # 只出顶层窗口那一张（见 ``PEN_LIGHT`` / ``ZOOM_LIGHT`` / ``JUMP_LIGHT``）
            targets = ([] if top_window is None else [(
                "top_window_jump_light.png" if JUMP_LIGHT
                else "top_window_zoom_light.png" if ZOOM_LIGHT
                else "top_window_pen_light.png", top_window)])
        else:
            targets = [("quick_panel.png", panel)]
            if top_window is not None:
                # 笔选单那一档单独一个文件名：常态那张（选单收起）要留着对照
                targets.append((
                    preview_name("top_window_jump.png" if PREVIEW_JUMP
                                 else "top_window_zoom.png" if PREVIEW_ZOOM
                                 else "top_window_pen.png" if PREVIEW_PEN
                                 else "top_window.png"),
                    top_window,
                ))
            if settings is not None:
                targets.append(("settings.png", settings))
            if splash is not None:
                targets.append((splash_name, splash))
            if debug is not None:
                targets.append(("debug_window.png", debug))
            if editor is not None:
                targets.append((
                    preview_name("main_editor_edit.png" if PREVIEW_EDIT
                                 else "main_editor.png"),
                    editor,
                ))
            targets += page_hosts

        if os.environ.get("LUMI_PREVIEW_SIZES"):
            for name, window in targets:
                print(f"[SIZE] {name}: {window.width()}x{window.height()} "
                      f"(declared {window.property('width')}x"
                      f"{window.property('height')})")

        for name, window in targets:
            _grab_pair(window, name)

        # 报告窗两档对照图。放在最后：它要**改** ``ErrorHandler`` 的状态（切换
        # 崩溃 / 错误），放在别的窗口抓图之前会把中途状态漏出去。
        # 其余档位（只出启动画面 / 只出设置页 / 浅色）不出这两张，免得覆盖常态图。
        # ⚠️ 提前 return 是安全的：主题 / 背景特效 / 配置的还原统一交给
        # ``_restore_preview_state``（外层 finally），不会重演 2026-10-06 前
        # 「浅色档 return 掉还原代码、进程挂死、主题留在 Light」那个坑。
        if (error_report is None or ONLY_SPLASH or PAGE_ONLY or EDITOR_LIGHT
                or PEN_LIGHT or JUMP_LIGHT):
            return
        # ``LUMI_PREVIEW_DETAILS=1`` → 出「查看详细信息」**展开**那一档
        # （默认收起，见 ``ErrorReportWindow.qml`` 的头注释）。两档都要能目检，
        # 所以文件名带 ``_details`` 后缀，不与常态那两张互相覆盖。
        _suffix = "_details" if PREVIEW_DETAILS else ""
        if PREVIEW_DETAILS:
            error_report.setProperty("detailsExpanded", True)
        for name, kind in (
            (f"error_report_crash{_suffix}.png", "crash"),
            (f"error_report_error{_suffix}.png", "error"),
        ):
            error_handler._capture(
                kind=kind, summary="TimeoutError: timed out",
                traceback_text=REPORT_TRACEBACK,
            )
            # ⚠️ 换报告会把 ``detailsExpanded`` 复位（QML 侧的 Connections），
            # 所以「强制展开」必须在每次 ``_capture`` **之后**再设一次。
            if PREVIEW_DETAILS:
                error_report.setProperty("detailsExpanded", True)
            # 属性是**绑定**在 ``ErrorHandler`` 上的，改完要让事件循环跑一拍，
            # QML 才把新文案 / 新表情 / 新主按钮取回来。
            QCoreApplication.processEvents()
            if _grab_pair(error_report, name) is None:
                continue

        # 主题 / 背景特效 / 配置的还原统一交给 _restore_preview_state（外层 finally），
        # 别在这里再抄一份 —— 历史上就是因为还原代码写在 capture() 的最后一条
        # return 之后，上面那几条提前 return 的档位一个都没还原过。
        qt_app.quit()

    QTimer.singleShot(1800, capture)
    try:
        code = qt_app.exec()
    finally:
        _restore_preview_state(rinui, config, backend, previous_theme,
                               previous_effect, labels_previous, pager_previous)
    # 插件接缝三件套由子进程补渲染（不同进程的理由见 ``_run_plugin_seams``
    # 头注释）。放在主渲染与状态还原**之后**：此刻主题与一次性配置改动都已还原，
    # 子进程自己再切主题互不干扰。
    if _should_render_plugin_seams():
        child_env = dict(os.environ)
        child_env["LUMI_PREVIEW_PLUGIN_RUN"] = "1"
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve())],
            env=child_env,
        )
        if result.returncode != 0:
            print(f"[FAIL] 插件接缝渲染子进程退出码 {result.returncode}")
            return result.returncode or 1
    return code


PAGE_HOST_QML = """import QtQuick
import RinUI as Rin

Rin.Window {
    id: host
    property url pageUrl: ""
    property int hostHeight: 640
    property int hostWidth: 1000

    width: hostWidth
    height: hostHeight
    titleBarHeight: 0
    titleEnabled: false
    closeVisible: false
    minimizeVisible: false
    maximizeVisible: false
    flags: Qt.Tool | Qt.FramelessWindowHint

    Loader {
        id: pageLoader
        objectName: "pageLoader"
        anchors.fill: parent
        anchors.margins: 16
        source: host.pageUrl
    }
}
"""


def _is_page(item) -> bool:
    """这个 QML 根是不是一个「页面」（``Rin.FluentPage`` → ``Page``）。

    ⚠️ 为什么必须挑一挑 ``ui/settings`` 下的 ``*.qml``：那目录里除了整页，还住着
    **Tab 内容**这类片段（``UpdateSettingsTab.qml``），它是要挂在某个页面里的，
    单独塞进 ``Loader`` 时拿不到页面上下文。实测被当整页渲染时，
    ``column`` 的 ``anchors.fill`` 与根 ``implicitHeight`` 之间的环会解出另一个
    值 —— 第一张卡片被撑到 387px（真身 72），两张卡片之间凭空多出 320px 空档，
    图看着像版式坏了，其实页面本身没问题。

    判据用「有没有 ``title`` 属性」：``Page`` 自带 ``title``，普通 ``Item`` 没有。
    """
    meta = item.metaObject()
    return any(meta.property(i).name() == "title"
               for i in range(meta.propertyCount()))


def _build_page_hosts(engine) -> list[tuple[str, object]]:
    """把 ``ui/settings`` 下每个页面塞进一个临时宿主窗口，返回 ``(文件名, 窗口)``。

    宿主 QML **写在 ``preview/`` 里且不删**：``QQmlEngine`` 会给每个 QML 源文件挂
    文件监视器，源文件一旦消失，引擎会判定文档失效并**回收由它创建的全部对象**
    （表现为 ``Internal C++ object already deleted``）。这也是为什么
    ``_probe_boot.qml`` 那种「写完就删」的用法只适合立即读属性的场景。
    """
    OUT_DIR.mkdir(exist_ok=True)
    host_path = OUT_DIR / "_page_host.qml"
    host_path.write_text(PAGE_HOST_QML, encoding="utf-8")

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(host_path)))
    if component.isError():
        for error in component.errors():
            print("PAGE HOST ERROR:", error.toString())
        return []

    hosts: list[tuple[str, object]] = []
    for index, page in enumerate(sorted((UI_DIR / "settings").rglob("*.qml"))):
        window = component.createWithInitialProperties(
            {
                "pageUrl": QUrl.fromLocalFile(str(page)),
                "hostHeight": PAGE_HEIGHT,
                "hostWidth": PAGE_WIDTH,
                "visible": True,
            }
        )
        if window is None:
            for error in component.errors():
                print(f"PAGE {page.name} ERROR:", error.toString())
            continue
        # 持有 component 引用：PySide 中 create() 出来的对象生命周期与组件绑定
        window._host_component = component

        # 挑掉 Tab 内容这类片段（见 ``_is_page`` 的说明）。放在 ``show()`` 之前：
        # 它们本来就不该被暴露，省一次窗口创建/合成。
        loader = window.findChild(QObject, "pageLoader")
        loaded = loader.property("item") if loader is not None else None
        if loaded is None or not _is_page(loaded):
            print(f"[SKIP] {page.name}: 不是整页（Tab 内容/片段），不单独渲染")
            window.close()
            window.deleteLater()
            continue

        window.setPosition(OFFSCREEN_X - index * 900, OFFSCREEN_Y - 1800)
        window.show()
        hosts.append((f"page_{page.stem}.png", window))
    return hosts


class _PreviewWindowStub:
    """``load_plugins`` 的最小窗口管理 stub（参照 task-17-render-list.py）。

    预览不经 ``WindowManager`` 开插件窗口：夹具窗口用组件单独建实例渲染，
    这里只要让 ``ctx.register_window`` 拿到一个能 show/hide 的句柄，
    插件的 ``register()`` 就能跑完。
    """

    class _Handle:
        def show(self) -> None: ...
        def hide(self) -> None: ...

    def register_window(self, name, qml_path, **options):
        return _PreviewWindowStub._Handle()


def _should_render_plugin_seams() -> bool:
    """主进程跑完后是否补跑插件接缝子进程（默认开；对照档不补跑）。

    ``_labels`` / ``_pager_*`` / 编辑态 / 笔选单 / 报告展开都是特定对照档，
    插件接缝不受这些开关影响，补跑只会重复出同样的三张图，跳过。
    """
    if os.environ.get("LUMI_PREVIEW_PLUGINS", "1") in ("", "0"):
        return False
    if os.environ.get("LUMI_PREVIEW_ONLY", "") == "splash":
        return False
    return not (
        PAGE_ONLY or PREVIEW_EDIT or PREVIEW_PEN
        or PREVIEW_LABELS or PREVIEW_PAGER or PREVIEW_DETAILS
    )


def _grab(name: str, window) -> bool:
    """抓两帧留第二帧并保存（与主流程 capture 同款手法，理由见那里的注释）。"""
    try:
        window.grabWindow()
        image = window.grabWindow()
    except RuntimeError as exc:  # 窗口已被 QML 引擎回收
        print(f"[FAIL] {name}: {exc}")
        return False
    if image.isNull():
        print(f"[FAIL] {name}: grabWindow() 返回空图")
        return False
    image.save(str(OUT_DIR / name))
    print(f"[OK] {name} -> {OUT_DIR / name} ({image.width()}x{image.height()})")
    return True


def _run_plugin_seams() -> int:
    """插件接缝三件套渲染（``LUMI_PREVIEW_PLUGIN_RUN=1`` 子进程模式）。

    为什么不并进主流程（2026-10-06 插件系统计划 Wave 4 任务 14）：

    * 注册表是模块级单例，``load_plugins`` 末尾 ``freeze()`` **不可逆** ——
      单进程只能加载一次，加载后冻结；
    * 插件贡献是**读取侧拼接**进主界面的（快捷面板磁贴 / 设置导航项 /
      控制条 tools·actions，见 ``bridge.py`` 头注释），同进程加载后
      ``quick_panel.png`` / ``settings.png`` / ``top_window.png`` /
      ``main_editor.png`` / ``page_Plugins.png`` 全都会多出演示条目 ——
      既有预览图是视觉回归的对比基准，文件名与内容都必须零回归。

    所以主进程照常渲染（零回归由构造保证），三件套在这个子进程里出：

    * ``plugin_demo_settings.png`` —— ``_demo`` 设置页（与 ``page_*`` 同款的
      Loader 宿主；设置键已注册，开关绑定 ``plugins._demo.flag`` 能解析）；
    * ``plugin_editor_demo.png`` —— 主界面编辑器选中 ``bottom_left``（其
      groups 在内存里换成 ``["_demo_group", "pager"]``：``_demo_group`` 在前，
      组件名 / 图标 / 检查器描述符都按演示组件解析；``pager`` 只是让控制条
      有实体可聚焦 —— 空组区块高度为零，取景矩形会塌掉）；
    * ``plugin_demo_window.png`` —— ``_demo`` 夹具窗口（组件直接建实例，
      ``onClosing`` 的动作链路不演示）。

    浅色主题（继承主进程的 ``LUMI_PREVIEW_THEME``）下文件名带 ``_light``
    后缀，不覆盖深色版。锁屏可跑（离屏渲染，窗口摆屏幕外）。
    """
    config = Config()
    # 演示开关置 ON（只改内存）：设置页与编辑器检查器的开关都绑
    # ``plugins._demo.flag``，点亮了好核对「绑定通 + 强调色对」。
    config.set("plugins._demo.flag", True, persist=False)

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    backend = Backend(config, qt_app)
    # 内建组登记（幂等）必须在 load_plugins 之前 —— 加载末尾注册表冻结，
    # 冻结后编辑器再读不到内建组会把内建角落全当未知组。
    WindowManager._register_builtin_groups(None)
    backend.apply_state(
        PresentationState(active=True, slide_index=26, slide_total=41)
    )
    loader.load_plugins(backend, _PreviewWindowStub(), include_debug=True)
    # 编辑器目标的角落换成「演示组件 + 翻页」（只改内存，子进程退出即抛）。
    config.set("presentation.corners.bottom_left.enabled", True, persist=False)
    config.set("presentation.corners.bottom_left.groups",
               ["_demo_group", "pager"], persist=False)
    backend.reload_from_config()

    rinui = RinUIWindow()
    rinui.engine.addImportPath(str(UI_DIR))
    rinui.theme_manager.set_theme_color(str(config.get("app.accent")))
    # setTheme 会持久化 rin_ui.json：抓完图必须切回原值（与主流程同款）。
    previous_theme = rinui.theme_manager.get_theme_name()
    rinui.setTheme(Theme.Light if IS_LIGHT else Theme.Dark)
    rinui.engine.rootContext().setContextProperty("Backend", backend)
    # ⚠️ 必须真 load 一个窗口：RinUI 只在 load() 时把窗口登记进主题管理，
    # 不 load 直接建宿主会拿到「主题没生效」的画面（task-12-preview.py 记过）。
    rinui.load(UI_DIR / "QuickPanel.qml")
    rinui.setBackdropEffect(BackdropEffect.None_)
    rinui.root_window.setPosition(OFFSCREEN_X, OFFSCREEN_Y)
    rinui.root_window.show()

    failed = False

    # ---- _demo 设置页（Loader 宿主，与 _build_page_hosts 同一份宿主 QML）----
    OUT_DIR.mkdir(exist_ok=True)
    host_path = OUT_DIR / "_page_host.qml"
    host_path.write_text(PAGE_HOST_QML, encoding="utf-8")
    host_component = QQmlComponent(rinui.engine, QUrl.fromLocalFile(str(host_path)))
    page_host = None
    if host_component.isError():
        for error in host_component.errors():
            print("PLUGIN PAGE HOST ERROR:", error.toString())
        failed = True
    else:
        page_host = host_component.createWithInitialProperties(
            {
                "pageUrl": QUrl.fromLocalFile(
                    str(UI_DIR / "plugins" / "_demo" / "DemoSettings.qml")
                ),
                "hostHeight": PAGE_HEIGHT,
                "hostWidth": PAGE_WIDTH,
                "visible": True,
            }
        )
        if page_host is None:
            print("PLUGIN PAGE HOST CREATE ERROR")
            failed = True
        else:
            page_host._host_component = host_component  # 持有引用防引擎回收
            page_host.setPosition(OFFSCREEN_X - 1800, OFFSCREEN_Y - 1800)
            page_host.show()

    # ---- 主界面编辑器：选中含 _demo_group 的角落（backdropEnabled 关掉的
    # 理由与主流程相同：离屏抓图拿不到 DWM 亚克力层）----
    editor = None
    editor_component = QQmlComponent(
        rinui.engine, QUrl.fromLocalFile(str(UI_DIR / "MainInterfaceEditor.qml"))
    )
    if editor_component.isError():
        for error in editor_component.errors():
            print("PLUGIN EDITOR ERROR:", error.toString())
        failed = True
    else:
        editor = editor_component.createWithInitialProperties({"visible": True})
        if editor is None:
            for error in editor_component.errors():
                print("PLUGIN EDITOR CREATE ERROR:", error.toString())
            failed = True
        else:
            editor._editor_component = editor_component  # 持有引用防引擎回收
            editor.setProperty("backdropEnabled", False)
            editor.setPosition(OFFSCREEN_X - 1000, OFFSCREEN_Y - 900)
            editor.show()
            editor.setProperty("selectedCorner", "bottom_left")
            # 窗口从没被暴露过时抓图可能拿到上一帧（主流程 PREVIEW_EDIT 同款坑），
            # 抬一次窗口催曝光。
            editor.raise_()
            editor.requestActivate()

    # ---- _demo 夹具窗口（按需创建型窗口在预览里单独建实例，与设置/调试窗同款）----
    demo_window = None
    demo_component = QQmlComponent(
        rinui.engine,
        QUrl.fromLocalFile(str(UI_DIR / "plugins" / "_demo" / "DemoWindow.qml")),
    )
    if demo_component.isError():
        for error in demo_component.errors():
            print("PLUGIN DEMO WINDOW ERROR:", error.toString())
        failed = True
    else:
        demo_window = demo_component.createWithInitialProperties({"visible": True})
        if demo_window is None:
            for error in demo_component.errors():
                print("PLUGIN DEMO WINDOW CREATE ERROR:", error.toString())
            failed = True
        else:
            demo_window._demo_component = demo_component  # 持有引用防引擎回收
            demo_window.setPosition(OFFSCREEN_X - 2400, OFFSCREEN_Y - 1000)
            demo_window.show()

    def capture() -> None:
        nonlocal failed
        suffix = "_light" if IS_LIGHT else ""
        targets = []
        if page_host is not None:
            targets.append((f"plugin_demo_settings{suffix}.png", page_host))
        if editor is not None:
            targets.append((f"plugin_editor_demo{suffix}.png", editor))
        if demo_window is not None:
            targets.append((f"plugin_demo_window{suffix}.png", demo_window))
        for name, window in targets:
            if not _grab(name, window):
                failed = True
        if rinui.theme_manager.get_theme_name() != previous_theme:
            rinui.theme_manager.toggle_theme(previous_theme)
            print(f"[OK] 主题已还原为 {previous_theme}")
        qt_app.exit(1 if failed else 0)

    QTimer.singleShot(1800, capture)
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
