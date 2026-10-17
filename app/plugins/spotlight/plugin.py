"""聚光灯插件 —— 全屏压暗遮罩 + 跟随光标的圆形光斑。

2026-10-06 用户指令「做一个……聚光灯」落地。形态：一块全屏半透明黑遮罩
盖住光标所在显示器，光标位置挖出一个圆形「光斑」——遮罩窗口本身是
2026-10-06 随本插件加进 ``app/windows.py`` 的**叠加窗口**家族
（``WindowManager.register_overlay`` → ``RegisteredOverlay``），与放映
顶层窗口同族：无边框、置顶、不抢焦点、区域塑形镂空。Python 本模块只管
「跟谁走 / 多大」，每拍把光斑（窗口局部逻辑坐标）经句柄 ``set_hole``
喂给窗口管理器塑形。

交互设计（为什么不学 ZoomIt 用滚轮 / Esc）：

* 窗口带 ``Qt.WindowDoesNotAcceptFocus``，**从不抢焦点** —— 方向键 / 滚轮
  仍归放映窗口，讲课不被打断；代价是本窗口收不到键盘事件，Esc 退出与
  滚轮调大小都无从谈起（滚轮消息在现代 Windows 上发给**焦点窗口**）。
* 退出通道：光斑遮罩**吃点击**（遮罩上的控件才可点），顶部常驻一枚
  「✕」胶囊按钮直接关；快捷面板磁贴与放映控制条动作同样可开关。
* 大小调整：遮罩上的 − / ＋ 按钮，或键盘 ``+`` / ``-``（含小键盘）——
  键盘用 ``GetAsyncKeyState`` 全局轮询，不依赖焦点。调整是**会话级**的，
  不写回配置（默认值走设置页的滑条）。

2026-10-08 修复「✕ 按钮被光斑吞掉」：光斑跟光标走，光标一靠近顶部胶囊，
胶囊就掉进镂空里被 ``SetWindowRgn`` 一起裁掉，主退出路径断。现在 QML 侧
胶囊把自身几何经 ``plugin:spotlight:pill-rect:<x>,<y>,<w>,<h>`` 上报，
本模块存为 ``_pill_rect``，每次 ``set_hole`` 都把它作为**保留矩形**带上 ——
窗口管理器塑形时镂空算完再把这个矩形 ``RGN_OR`` 补回，任何光斑位置下
胶囊都可见可点。

2026-10-08 跨屏粘滞迁移：早期激活时按光标定屏后就把 ``_screen`` 锁死，
光标跑到另一块屏，光斑只能贴边傻等（双屏教室是常态，「关了重开」不是
答案）。现在每拍比对 ``screenAt(光标)`` 与 ``_screen``：不同就计数、
相同就清零，连续 ``_SCREEN_MIGRATE_TICKS`` 拍（25ms×12≈300ms）稳定停
在另一屏才把整只遮罩迁过去（``RegisteredOverlay.move_to_screen``），
圆心归新屏中心、半径按新屏短边重算。迟滞计数是为屏边缘抖动 —— 交界
处来回晃几拍不该搬一次家；单屏环境 ``screenAt`` 恒等于 ``_screen``，
计数器天然不触发。

设置：遮罩浓度 ``plugins.spotlight.dim``（0–85）、光斑大小
``plugins.spotlight.radius``（屏宽短边的百分比，6–70），都经设置页滑条
实时生效（浓度是 QML 直接绑设置键，大小经 side_effect 改本模块并立即
重设光斑）。
"""

from __future__ import annotations

import ctypes
import logging
import time
from typing import Any, Optional

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QCursor, QGuiApplication

from ...paths import UI_DIR
from ... import i18n

log = logging.getLogger(__name__)

META = {
    "id": "spotlight",
    "name": "聚光灯",
    "version": "1.0.0",
    "category": "utility",
    "icon": "ic_fluent_flashlight_20_regular",
}

#: ``plugins.spotlight.*`` 默认值：遮罩浓度（alpha %）与光斑半径（占光标屏
#: 短边的百分比）。
DEFAULTS = {"dim": 60, "radius": 24}

#: 光斑半径的百分比上下限（屏短边的 %）—— 太小找不着、太大就是手电筒。
_RADIUS_MIN_PERCENT = 6
_RADIUS_MAX_PERCENT = 70
_RADIUS_STEP_PERCENT = 2

#: 轮询光标的节拍（毫秒）。25ms 与放映顶层窗口的命中轮询同款：肉眼跟手
#: 且 CPU 占用可忽略（一拍一次 GetCursorPos + 一次区域重算）。
_POLL_INTERVAL_MS = 25

#: 跨屏迁移的迟滞阈值（轮询拍数）。光标在屏边缘抖动（交界处两块屏之间
#: 来回晃几拍）不该把整块遮罩反复搬家 —— 连续 12 拍（25ms×12≈300ms）
#: 稳定停在另一屏上才认定用户真的换了屏。
_SCREEN_MIGRATE_TICKS = 12

#: 键盘 ``+`` / ``-``（VK_OEM_PLUS / VK_OEM_MINUS）与小键盘 ``+`` / ``-``
#: （VK_ADD / VK_SUBTRACT）的虚拟键码。
_VK_OEM_PLUS = 0xBB
_VK_OEM_MINUS = 0xBD
_VK_ADD = 0x6B
_VK_SUBTRACT = 0x6D

_overlay_handle: Optional[Any] = None
_poll_timer: Optional[Any] = None

#: 遮罩是否开着（轮询器只在这时跑）
_active = False
#: 光斑当前所在屏（激活时按光标定屏；之后光标跨屏稳定停留约 300ms
#: 即粘滞迁移过去，见模块头注释 2026-10-08 跨屏条目）
_screen: Optional[Any] = None
#: 光标连续停留在另一块屏上的拍数（回到本屏即清零；阈值见
#: ``_SCREEN_MIGRATE_TICKS``）
_screen_migrate_ticks = 0
#: 光斑圆心（屏幕局部逻辑坐标）；初始 = 屏幕中心，之后跟光标
_center = QPoint(0, 0)
_radius_percent = 24
_radius_px = 0.0

#: QML 控制胶囊上报的自身几何 ``(x, y, w, h)``（窗口局部逻辑坐标）。
#: 塑形时作为保留矩形补回（理由见模块头注释 2026-10-08 条目）；
#: 未上报时为 None —— 塑形照常，只是退回「胶囊可能被裁」的旧行为，不炸。
_pill_rect: Optional[tuple[int, int, int, int]] = None

#: ``+`` / ``-`` 键状态（边沿触发 + 按住连调）
_plus_prev = False
_minus_prev = False
_last_adjust = 0.0


def _key_down(vk: int) -> bool:
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:  # pragma: no cover - 非 Windows / 句柄异常
        return False


def _apply_radius() -> None:
    """按百分比算像素半径并立即重设光斑（会话级调整，不写配置）。"""
    global _radius_px
    if _screen is None:
        return
    geometry = _screen.geometry()
    short_side = min(geometry.width(), geometry.height())
    _radius_px = short_side * _radius_percent / 100.0
    if _overlay_handle is not None and _active:
        _overlay_handle.set_hole(
            _center.x(), _center.y(), _radius_px,
            [_pill_rect] if _pill_rect else None,
        )


def _adjust_radius(delta: int) -> None:
    global _radius_percent
    _radius_percent = max(
        _RADIUS_MIN_PERCENT,
        min(_RADIUS_MAX_PERCENT, _radius_percent + delta),
    )
    _apply_radius()


def _migrate_to_screen(screen) -> None:
    """把遮罩迁到 ``screen``：换屏、圆心归新屏中心、半径按新屏重算。

    半径是「屏短边的百分比」，换屏后短边可能不同，必须经
    :func:`_apply_radius` 重算；它内部那次 ``set_hole`` 照常带上胶囊
    保留矩形，迁移不丢塑形上下文（计数器清零，防止落地第一拍又触发）。
    """
    global _screen, _center, _screen_migrate_ticks
    old_name = _screen.name() if _screen is not None else "?"
    _screen = screen
    geometry = screen.geometry()
    _center = QPoint(geometry.width() // 2, geometry.height() // 2)
    _screen_migrate_ticks = 0
    if _overlay_handle is not None:
        _overlay_handle.move_to_screen(screen)
    _apply_radius()
    log.info("聚光灯遮罩已迁到屏幕 %s（原 %s）", screen.name(), old_name)


def _poll() -> None:
    """轮询节拍：光斑跟光标 + 跨屏粘滞迁移 + 全局 ``+`` / ``-`` 调大小。

    光标在本屏：照常跟手。光标到了另一块屏：先计数不搬 —— 屏边缘抖动
    （交界处来回晃）会把遮罩反复搬家，连续 ``_SCREEN_MIGRATE_TICKS`` 拍
    （≈300ms）都停在新屏上才迁移；未满阈值时圆心照旧夹回本屏贴边等着。
    单屏环境 ``screenAt`` 恒等于 ``_screen``，计数器天然不触发。
    """
    global _plus_prev, _minus_prev, _last_adjust, _center
    global _screen, _screen_migrate_ticks

    if _screen is None:
        return
    cursor = QCursor.pos()
    hovered = QGuiApplication.screenAt(cursor)
    # QScreen 的 == 按底层指针判等（PySide 对 QObject 的约定），同一台
    # 显示器每次 screenAt 拿到的都是同一对象，直接比即可
    if hovered is not None and hovered != _screen:
        _screen_migrate_ticks += 1
        if _screen_migrate_ticks >= _SCREEN_MIGRATE_TICKS:
            _migrate_to_screen(hovered)
    else:
        _screen_migrate_ticks = 0

    geometry = _screen.geometry()
    x = cursor.x() - geometry.left()
    y = cursor.y() - geometry.top()
    x = max(0, min(geometry.width(), x))
    y = max(0, min(geometry.height(), y))
    _center = QPoint(x, y)
    if _overlay_handle is not None:
        _overlay_handle.set_hole(
            x, y, _radius_px,
            [_pill_rect] if _pill_rect else None,
        )

    now = time.monotonic()
    plus = _key_down(_VK_OEM_PLUS) or _key_down(_VK_ADD)
    minus = _key_down(_VK_OEM_MINUS) or _key_down(_VK_SUBTRACT)
    # 边沿触发立刻响应一档，按住则每 250ms 连调一档（与系统按键重复感一致）
    if plus and (not _plus_prev or now - _last_adjust >= 0.25):
        _adjust_radius(+_RADIUS_STEP_PERCENT)
        _last_adjust = now
    elif minus and (not _minus_prev or now - _last_adjust >= 0.25):
        _adjust_radius(-_RADIUS_STEP_PERCENT)
        _last_adjust = now
    _plus_prev = plus
    _minus_prev = minus


def _show_overlay() -> None:
    global _active, _screen, _center, _screen_migrate_ticks
    screen = QGuiApplication.screenAt(QCursor.pos()) \
        or QGuiApplication.primaryScreen()
    if screen is None:
        return
    _screen = screen
    _screen_migrate_ticks = 0
    geometry = screen.geometry()
    _center = QPoint(geometry.width() // 2, geometry.height() // 2)
    _overlay_handle.show()
    _apply_radius()
    _active = True
    if _poll_timer is not None:
        _poll_timer.start()
    log.info("聚光灯已开启（屏幕 %s，半径 %d%%）", screen.name(), _radius_percent)


def _hide_overlay() -> None:
    global _active
    _active = False
    if _poll_timer is not None:
        _poll_timer.stop()
    if _overlay_handle is not None:
        _overlay_handle.hide()
    log.info("聚光灯已关闭")


def _on_action(action: str) -> None:
    """``plugin:spotlight:`` 前缀动作：开关 / 大小（遮罩上的按钮也走这里）。"""
    if action == "plugin:spotlight:toggle":
        if _active:
            _hide_overlay()
        else:
            _show_overlay()
    elif action == "plugin:spotlight:close":
        if _active:
            _hide_overlay()
    elif action == "plugin:spotlight:bigger":
        if _active:
            _adjust_radius(+_RADIUS_STEP_PERCENT)
    elif action == "plugin:spotlight:smaller":
        if _active:
            _adjust_radius(-_RADIUS_STEP_PERCENT)
    elif action.startswith("plugin:spotlight:pill-rect:"):
        # 动作后缀带参（插件开发指南约定）：QML 胶囊上报自身几何，
        # 逗号分隔 4 个整数；非法负载只记日志，不动旧值
        global _pill_rect
        try:
            parts = [int(float(v))
                     for v in action.rsplit(":", 1)[1].split(",")]
        except ValueError:
            parts = []
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            _pill_rect = (parts[0], parts[1], parts[2], parts[3])
        else:
            log.info("聚光灯收到非法胶囊几何: %s", action)
    else:
        log.info("聚光灯收到未知动作: %s", action)


def _on_radius_setting(config, key, value) -> None:
    """「光斑大小」设置的 side_effect：实时改会话值（不回写配置）。"""
    global _radius_percent
    _radius_percent = max(
        _RADIUS_MIN_PERCENT, min(_RADIUS_MAX_PERCENT, int(value))
    )
    if _active:
        _apply_radius()


def register(ctx) -> None:
    """磁贴 / 控制条动作 / 设置页 / 两个设置键 / 叠加窗口 / 轮询器。"""
    global _overlay_handle, _poll_timer, _radius_percent

    def tr(source: str) -> str:
        return i18n.tr("spotlight", source)

    # ⚠️ META["name"] 在这里才翻译（时序理由见 timer_l1/plugin.py 同日注释）：
    # 模块 import 跑在翻译器安装之前，import 期的 i18n.tr 只能回中文原文。
    META["name"] = tr("聚光灯")

    ctx.add_shortcut(
        "spotlight_panel", tr("聚光灯"), "ic_fluent_flashlight_20_regular",
        "plugin:spotlight:toggle",
    )
    ctx.add_action_handler("plugin:spotlight:", _on_action)
    ctx.add_dock_action(
        "plugin:spotlight:toggle", tr("聚光灯"),
        "ic_fluent_flashlight_20_regular",
        tooltip=tr("开启 / 关闭聚光灯遮罩"),
    )
    ctx.add_settings_page(
        "spotlight_page", tr("聚光灯"), "SpotlightSettings.qml",
        "ic_fluent_flashlight_20_regular",
    )

    config = ctx._backend._config
    _radius_percent = max(
        _RADIUS_MIN_PERCENT,
        min(_RADIUS_MAX_PERCENT, int(config.get("plugins.spotlight.radius", 24))),
    )
    # 浓度 QML 直读设置键即可（settingsChanged 会推重读），不用 side_effect；
    # 大小 Python 侧要做像素换算，side_effect 跟一手。
    ctx.register_setting(
        "plugins_spotlight_dim", "plugins.spotlight.dim",
    )
    ctx.register_setting(
        "plugins_spotlight_radius", "plugins.spotlight.radius",
        side_effect=_on_radius_setting,
    )

    # 叠加窗口（遮罩本体；创建 / 全屏 / 塑形在 app/windows.py）
    _overlay_handle = ctx.register_overlay(
        "spotlight", UI_DIR / "plugins" / "spotlight" / "SpotlightOverlay.qml",
        label=tr("聚光灯遮罩"),
    )

    _poll_timer = QTimer()
    _poll_timer.setInterval(_POLL_INTERVAL_MS)
    _poll_timer.timeout.connect(_poll)
    log.info("聚光灯插件已注册")
