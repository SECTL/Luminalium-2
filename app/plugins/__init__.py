"""Luminalium 2 插件系统 —— 插件包入口。

``PLUGINS`` 是**显式启用的正式插件注册表**（插件 id 列表）。刻意做成
手工维护的列表而不是目录扫描：显式枚举能让启用集合一眼可查，避免
「丢个文件夹进 plugins/ 就默默生效」的隐式行为（2026-10-05 插件系统
计划 Wave 1 决定）。表内重复 id 会在 ``loader._formal_ids`` 处启动硬失败。

调试插件约定（Wave 3 任务 11）：``app/plugins/`` 下目录名以单下划线
``_`` 开头且含 ``plugin.py`` 的目录（``_demo`` / ``_demo_dep`` 等验收夹具）
**永不进此表**，只在 ``loader.load_plugins(..., include_debug=True)`` 时
追加加载（门控来源是 ``app.debug`` 配置键，默认关）。
"""

# 当前无任何正式插件（_demo 调试夹具组在 Wave 3 任务 12 落地，不进此表）。
PLUGINS: list[str] = []
