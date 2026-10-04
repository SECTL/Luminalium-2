"""回声洞（Echo Cave）—— 随机句子来源。

Luminalium 1 的回声洞从**本地服务**取随机句子
（``http://127.0.0.1:28423/api/echo-cave?mode=random&limit=1``，返回
``{"success": true, "documents": [{"content": "..."}]}``）。本项目照搬那条链路，
另外**自带一份句子池作离线兜底**：先问本地服务，拿不到就从池子里随机取一条。

为什么要有兜底：那个服务是 L1 那套附带的，L2 用户机器上大概率没在跑。没有兜底
的话「点击取句」永远只会显示「获取失败」—— 交互壳子还在、内容永远是错的，比不做
还难看。localhost 上**没有监听时连接会被立刻拒绝**（不是等超时），所以先问一句的
代价约等于零，界面不会卡。

⚠️ 这个模块只负责「拿一条句子」，不碰 Qt：取句在后台线程里跑，见
``bridge.Backend.requestEchoCave``。
"""

from __future__ import annotations

import json
import logging
import random
import socket
import threading
import urllib.request

log = logging.getLogger(__name__)

#: L1 回声洞本地服务的地址。拆成两段是为了给 :func:`warm_up` 预热用 ——
#: 预热要的是「主机 + 端口」，不是整条 URL。
HOST = "127.0.0.1"
PORT = 28423

#: L1 回声洞本地服务的取句接口。协议与 L1 完全一致，将来若 L1 的服务在跑，
#: L2 直接复用同一份内容，不需要另做适配。
REMOTE_URL = f"http://{HOST}:{PORT}/api/echo-cave?mode=random&limit=1"

#: 单次请求超时（秒）。正常 Windows 上「端口没人听」是**立刻**返回
#: ``ConnectionRefusedError`` 的，这个值只兜「端口开着但对端不回」。
REMOTE_TIMEOUT = 0.4

#: 本进程内「本地服务不可用」的记忆。
#:
#: 没有它的话，**每一次点击**都要先把连接试穿一遍才轮到兜底池 —— 端口关闭时
#: 通常是瞬时的，但在被防火墙丢包 / 沙箱拦网的环境里会一直耗到超时，用户就会
#: 觉得「点了没反应」。判定失败一次之后本进程不再重试：L1 的服务要么在跑
#: （那第一次就成功了），要么整场都不会突然起来。
_remote_unavailable = False

#: 离线兜底句子池。
#:
#: 口径：回声洞是一面「留言墙」，句子的调子应当**安静、温和、有点光**，不是
#: 产品文案也不是报错提示。这里都是原创短句，不引用任何已有作品。
SENTENCES: tuple[str, ...] = (
    "所有的回声，都是很久以前的某个人在替现在的你说话。",
    "你听见的那一声，其实是自己走过去时留下的。",
    "洞壁很凉，但光是从上面下来的。",
    "有人在很深的夜里也点亮过这里，只是你不知道。",
    "说话吧，石头会记住，风会带走。",
    "每一个回声都在说：你来过，而且被听见了。",
    "慢一点也没关系，回声本来就要走一段路。",
    "如果今天很难，就把这句话留在这里，明天再来取。",
    "洞穴不评价声音好不好听，它只是把它送回来。",
    "你留下的句子，会在某个陌生人的屏幕上亮一下。",
    "有些话说不出口，那就交给回声。",
    "洞里没有白天黑夜，只有有人来和没人来。",
    "我们都在往深处走，也都在往光亮的地方走。",
    "回声不会消失，它只是走得比你远一点。",
    "谢谢你路过这里，也谢谢你没有把灯关掉。",
    "把想说的话说完，洞会替你把沉默收好。",
    "每一次回响，都是一次轻轻的应答。",
    "你不需要喊得很大声，这里很安静。",
    "石壁上有旧年的刻痕，也有你今天新添的那一道。",
    "光落进洞口的时候，整个洞都在发亮。",
    "这里是回声洞，请随意留下你的声音。",
    "如果没人回应你，那就让回声来吧。",
    "走到洞底的人，都带回了一句自己想听的话。",
    "你说的话，已经变成这里的一部分了。",
)


def remote_sentence(timeout: float = REMOTE_TIMEOUT) -> str:
    """向本地回声洞服务要一条随机句子。

    任何异常（连不上 / 超时 / 结构不对 / 内容为空）都**安静地返回空串**，
    由调用方转去兜底池 —— 取句失败不该让用户看到 traceback。

    ⚠️ **必须绕开系统代理**：本机装了代理（``HTTP_PROXY`` 环境变量或系统代理）
    时，``urlopen`` 会把 ``127.0.0.1`` 的请求也塞给代理，结果是本地服务明明
    在跑却永远取不到句。这里显式用空 ``ProxyHandler`` 建 opener，保证是直连。
    """
    global _remote_unavailable

    if _remote_unavailable:
        return ""

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(REMOTE_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - 取句是尽力而为，任何失败都走兜底
        _remote_unavailable = True
        log.debug("回声洞本地服务不可用，本进程改用内置句子池", exc_info=True)
        return ""

    if not isinstance(payload, dict) or not payload.get("success"):
        return ""
    documents = payload.get("documents") or []
    if not documents:
        return ""
    content = documents[0].get("content") if isinstance(documents[0], dict) else ""
    return str(content or "").strip()


def random_sentence() -> str:
    """从内置句子池里随机取一条（池子为空则返回空串）。"""
    return random.choice(SENTENCES) if SENTENCES else ""


def fetch_sentence() -> str:
    """取一条句子：先问本地服务，失败则用内置池。"""
    return remote_sentence() or random_sentence()


def warm_up() -> None:
    """预热 socket 栈（后台线程，启动时调一次，见 ``application``）。

    ⚠️ 为什么需要这个「多余」的调用：Windows 上**进程内第一次** socket / DNS
    调用会被 Winsock 惰性初始化、杀软挂钩或（沙箱 / 防火墙环境下的）拦网拖住，
    而且这笔一次性开销**记在第一个碰网络的线程头上**。实测在 Qt 进程里，第一次
    ``getaddrinfo`` 从**后台线程**调用要 **3.0s**，同样的调用在主线程只要 0.01s。

    不预热的话，这笔账就落在用户**第一次点回声洞**上 —— 现象正是
    ``echo_cave`` 顶部注释里想避免的「点了没反应」（而且因为取句在后台线程，
    界面还会一直停在「获取中...」）。启动时先让一个用完即走的线程去摸一下，
    把账提前结掉。

    对本来就没有这笔开销的机器，这个线程瞬间结束，等于不存在；失败也无所谓 ——
    它只是预热，取句路径自己会兜底。
    """

    def probe() -> None:
        try:
            # 要**整条**走一遍（解析 + 连接），只做其中一步是热不透的：
            # 实测只 ``getaddrinfo`` 的话，真正取句时仍要再等 ~2s。
            with socket.create_connection((HOST, PORT), timeout=REMOTE_TIMEOUT):
                pass
        except Exception:  # noqa: BLE001 - 端口没人听就是常态，预热失败不影响任何功能
            log.debug("socket 预热失败（忽略）", exc_info=True)

    threading.Thread(target=probe, name="echo-cave-warmup", daemon=True).start()
