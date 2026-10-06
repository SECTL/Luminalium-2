"""插件系统验收夹具 ``_demo_dep``（2026-10-05 插件系统计划 Wave 3 任务 12）。

⚠️ **本插件与 ``_demo`` 组成框架验收夹具组，禁止在此实现任何真实功能。**

验收点有两个：

1. **依赖声明与拓扑序**：``META.depends = ["_demo"]`` —— loader 的拓扑排序
   保证 ``_demo`` 先 ``register``（其 ``ctx.subscribe("_demo_dep:hello", …)``
   已就绪），然后才轮到本插件；
2. **总线端到端**：``register`` 里同步 ``publish("_demo_dep:hello", "ping")``，
   ``_demo`` 的订阅处理器把 payload 写进 ``plugins._demo.note``，QA / smoke
   读这个键断言「发布 → 订阅 → 落配置」整条链路。

门控与 ``_demo`` 相同：不进 ``PLUGINS``，只在 ``include_debug=True``
（``app.debug`` 配置键）时加载。``_demo`` 被禁用时，本插件因依赖缺失被
loader 跳过（加载清单与 warning 日志列明因果链）。
"""

from __future__ import annotations

META = {"id": "_demo_dep", "depends": ["_demo"]}


def register(ctx) -> None:
    """注册期发布一条总线消息 —— 此刻 ``_demo`` 的订阅必须已就绪（拓扑序）。"""
    ctx.publish("_demo_dep:hello", "ping")
