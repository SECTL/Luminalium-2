"""放大镜（缩放 / 移位）的**离线**诊断 —— 一次把链路三个环节量出来。

为什么要有它：放大镜这条路上「点了没反应」有好几种成因，而且都不报错：

* QML 侧的按钮没接线（面板画得出来，点了什么也不发）；
* ``bridge.zoomSlide`` 到 ``application._on_action`` 的 ``zoom:`` 前缀没接通；
* COM 线程里的 ``_cmd_zoom`` 把这一下**静默丢掉了**（这正是 2026-10-06
  用户报「移位按钮无效」的成因：判据要求「确认已放大」，而确认本身要靠读回值
  变化，读不到就永远确认不了）。

本脚本把三者分开量：**不发按键、不连演示软件**，只把控制层那套决策逻辑跑一遍，
把「遇到什么输入 → 做什么判断 → 发不发键」逐条打印出来。真机上要验按键是否
生效，得看 ``tools/live_probe.py`` / ``tools/smoke.py``。

用法::

    .venv\\Scripts\\python.exe tools\\zoom_probe.py
    .venv\\Scripts\\python.exe tools\\zoom_probe.py --kind wps

⚠️ 它**不启动** ``_ComThread``：直接构造控制器、注入一个假的 ``_com``（只实现
``read_zoom`` + ``request``），这样任何一条路径都不会真的去碰 PowerPoint。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows 控制台默认代码页不是 UTF-8，中文 print 会 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

from app import ppt_controller as pc  # noqa: E402


class _FakeCom:
    """替身 COM 后端：只提供 ``_cmd_zoom`` 用得到的两样。"""

    def __init__(self, zoom: int | None) -> None:
        self.zoom = zoom
        self.commands: list[tuple] = []

    def read_zoom(self):
        return self.zoom

    def request(self, name: str, *args) -> None:
        self.commands.append((name,) + args)

    @property
    def snapshot(self):
        return None


def _install_key_recorder() -> list[str]:
    """把「真的要去发按键」的那两个函数换成记录器。

    ⚠️ 必须在**模块对象**上替换（``pc.send_slideshow_key``）：``_cmd_zoom`` 是从
    模块全局取这两个名字的，替换模块属性才接得住。
    """
    sent: list[str] = []

    def fake_key(vk, hwnd=0):
        sent.append(f"key:{pc.VK_NAMES.get(vk, hex(vk))}")
        return True

    def fake_ctrl_key(vk, hwnd=0):
        sent.append(f"ctrl+{pc.VK_NAMES.get(vk, hex(vk))}")
        return True

    def fake_focus(hwnd):
        return True

    pc.send_slideshow_key = fake_key          # type: ignore[assignment]
    pc.send_slideshow_ctrl_key = fake_ctrl_key  # type: ignore[assignment]
    pc.focus_slideshow_window = fake_focus      # type: ignore[assignment]
    # 别在诊断里真的 sleep（``_cmd_zoom`` 里有等待按键生效的 sleep）
    pc.L1_SHORTCUT_SETTLE_S = 0.0
    return sent


def _controller(com: _FakeCom, kind: str) -> pc._ComThread:
    """造一个**不启动**的 COM 线程对象 —— 只借它那套决策逻辑。

    ⚠️ ``_cmd_zoom`` / ``_zoom_state`` 是 :class:`_ComThread` 的方法（命令都在
    COM 线程里执行），不是 ``PptController`` 的。这里直接构造那个类、但**不调
    ``start()``**，于是它的 ``run()`` 永远不跑，不会有线程真的去碰 COM。
    """
    ctl = pc._ComThread()
    ctl._com = com                     # type: ignore[assignment]
    ctl._zoom_engaged = False
    ctl._zoom_baseline = None
    return ctl


def _run_case(title: str, zoom_readback, baseline, engaged, ops, kind, hwnd=0x1234):
    """一种「读回值 / 判据」组合下，逐个 op 走一遍，打印发出去了什么。"""
    com = _FakeCom(zoom_readback)
    ctl = _controller(com, kind)
    ctl._zoom_baseline = baseline
    ctl._zoom_engaged = engaged

    print(f"\n=== {title} ===")
    print(f"  kind={kind}  read_zoom()={zoom_readback}  baseline={baseline} "
          f"  _zoom_engaged={engaged}")
    for op in ops:
        sent = _install_key_recorder()
        ctl._zoom_engaged = engaged          # 每个 op 从同一个初值出发
        ctl._zoom_baseline = baseline
        # 补放大那一步会让读回值跟着变 —— 模拟「按键真的生效了」
        com.zoom = zoom_readback
        state = ctl._zoom_state()
        ctl._cmd_zoom(hwnd, op, kind)
        print(f"  op={op:<6} 判据={state:<8} → 发出 {sent or ['（什么都没发）']}"
              if state != "fit" else
              f"  op={op:<6} 判据={state:<8} → 先补放大再发 "
              f"{sent or ['（什么都没发）']}")


def _probe_state_machine() -> None:
    """把 ``_zoom_state`` 的三种输入映射逐条摆出来（这是判据本身）。"""
    print("=" * 72)
    print("判据本身：_zoom_state() 的输入 → 输出")
    print("=" * 72)
    cases = [
        ("读回 100（= 基线）", 100, 100, False),
        ("读回 150（≠ 基线）", 150, 100, False),
        ("读回拿不到（None）", None, None, False),
        ("我们发过放大（engaged）", 100, 100, True),
        ("基线还没记上", 150, None, False),
    ]
    for title, readback, baseline, engaged in cases:
        com = _FakeCom(readback)
        ctl = _controller(com, "ppt")
        ctl._zoom_baseline = baseline
        ctl._zoom_engaged = engaged
        print(f"  {title:<24} → {ctl._zoom_state()}")
    print("\n  期望：前两条分别是 fit / zoomed；第三条是 unknown（读不到就按"
          "用户意图发）；\n        第四条是 zoomed（我们自己的动作优先）；"
          "第五条是 unknown（基准没记上不能瞎判 fit）。")


def _probe_dispatch(kind: str) -> None:
    """边界情况：移位按钮在三种判据下各做什么。"""
    ops = ("in", "out", "reset", "up", "down", "left", "right")
    _run_case("① 还没放大（读回 = 基线）→ 移位应当**先补一档放大**再发方向键",
              zoom_readback=100, baseline=100, engaged=False, ops=ops, kind=kind)
    _run_case("② 读不到缩放值 → 移位直接发（没有判据，不能静默吞掉）",
              zoom_readback=None, baseline=None, engaged=False, ops=ops, kind=kind)
    _run_case("③ 用户自己在 PowerPoint 里放大过（读回 ≠ 基线）→ 直接发方向键",
              zoom_readback=150, baseline=100, engaged=False, ops=ops, kind=kind)
    _run_case("④ 我们发过放大 → 移位直接发方向键",
              zoom_readback=150, baseline=100, engaged=True, ops=ops, kind=kind)


def _probe_keymap() -> None:
    print("\n" + "=" * 72)
    print("各族的缩放键位（顺序即尝试顺序）")
    print("=" * 72)
    for kind, table in pc.KIND_ZOOM_KEYS.items():
        for op, keys in table.items():
            pretty = [f"Ctrl+{pc.VK_NAMES.get(vk, hex(vk))}" if ctrl
                      else pc.VK_NAMES.get(vk, hex(vk)) for vk, ctrl in keys]
            print(f"  {kind:<5} {op:<4} → {' / '.join(pretty)}")
    print(f"\n  移位（放大之后）: "
          + " ".join(f"{k}={pc.VK_NAMES.get(v, hex(v))}"
                     for k, v in pc.ZOOM_PAN_KEYS.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description="放大镜控制层离线诊断")
    parser.add_argument("--kind", default="ppt", choices=("ppt", "wps", "yozo"),
                        help="按哪一族跑（影响选的缩放键）")
    args = parser.parse_args()

    _probe_state_machine()
    _probe_keymap()
    _probe_dispatch(args.kind)
    print("\n提示：这里量的是**控制层的决策**（该不该发、发什么键）。"
          "按键在真机上是否生效要看演示软件自己的响应 —— 那部分靠"
          " tools/smoke.py 与实机放映验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
