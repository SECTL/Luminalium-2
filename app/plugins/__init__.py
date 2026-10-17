"""Luminalium 2 插件系统 —— 插件包入口。

``PLUGINS`` 是**显式启用的正式插件注册表**（插件 id 列表）。刻意做成
手工维护的列表而不是目录扫描：显式枚举能让启用集合一眼可查，避免
「丢个文件夹进 plugins/ 就默默生效」的隐式行为（2026-10-05 插件系统
计划 Wave 1 决定）。表内重复 id 会在 ``loader._formal_ids`` 处启动硬失败。

2026-10-06 起「目录扫描禁令」的范围明确为**仅约束 ``app/plugins/`` 包内**：
用户经设置页显式导入的外部插件落在数据根的 ``plugins/`` 目录（见
``app/plugins/external.py``），由 loader 扫描加载 —— 那是用户的显式动作，
不违反本条。内部新增正式插件仍然走这张表。

调试插件约定（Wave 3 任务 11）：``app/plugins/`` 下目录名以单下划线
``_`` 开头且含 ``plugin.py`` 的目录（``_demo`` / ``_demo_dep`` 等验收夹具）
**永不进此表**，只在 ``loader.load_plugins(..., include_debug=True)`` 时
追加加载（门控来源是 ``app.debug`` 配置键，默认关）。
"""

# 正式插件（2026-10-06 用户指令：计时器 / 小黑板 / 聚光灯首批落地）。
# 2026-10-17 计时器定为 Lmn-copy HTML 版原样移植（WebView，见
# ``timer/plugin.py`` 头注释），id 仍是 ``timer``。当日曾一度改挂 RinUI
# 重写的 ``timer_l1``（只有 QML 侧与这张表，Python 插件始终没建起来，
# 启动即 ModuleNotFoundError），用户拍板「留 HTML 版的那套」后整套撤回。
# 那段实现在提交 74e102d 里；哪天要翻回来，先把 app/plugins/timer_l1/
# 补全再动这张表。
PLUGINS: list[str] = ["timer", "blackboard", "spotlight"]
