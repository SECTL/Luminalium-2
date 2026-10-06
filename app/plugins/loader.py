"""Luminalium 2 插件系统 —— 两阶段加载器（装配中枢）。

为什么是两阶段（2026-10-05 插件系统计划 Wave 3 任务 11）：

* **阶段一 ``collect_defaults``** 跑在 ``Config()`` 构造**之前**。Config 的
  默认值注入（``extra_defaults``）只在构造时发生一次，而插件的
  ``plugins.<id>.*`` 默认值必须进默认层才能「可读但不落盘」；所以这一步
  只能在没有 Config、没有 Backend、没有窗口的裸环境里做，产出物是一个
  纯 dict。
* **阶段二 ``load_plugins``** 跑在 Backend + WindowManager 就绪之后、
  信号接线（``application._wire``）之前。设置键注册要 Backend、窗口注册
  要 WindowManager，而注册表必须在信号接线前完备并冻结 —— 接线后的
  消费端假设「读到的就是全量」。

⚠️ 鸡生蛋问题：阶段一判断「插件是否启用」时 Config 尚不存在，而启用
状态本身存在 ``plugins.<id>.enabled`` 配置键里。解法：阶段一直接
``json.load`` 读原始 ``app.paths.USER_CONFIG_FILE``（读不到 / 文件不存在 /
JSON 损坏一律按默认 ``true`` 处理）；阶段二拿到正式 Config 后再复核一遍
（同一份文件、同一默认值，两阶段结论天然一致，复核是防阶段一之后文件
被外部改动的兜底）。**禁用的插件两阶段都跳过** —— 阶段一不注入默认值，
阶段二不 import、不 register、零贡献。

发现机制（计划明令，勿扩展）：

* 正式插件 = ``app.plugins.PLUGINS`` 显式 id 列表（唯一来源，无目录扫描）；
* 调试插件 = ``app/plugins/`` 下目录名以单下划线 ``_`` 开头且含
  ``plugin.py`` 的目录（``_demo`` / ``_demo_dep`` 这类验收夹具），只在
  ``load_plugins(..., include_debug=True)`` 时追加加载，**永不进 PLUGINS**，
  其默认值也不走阶段一注入（调试夹具不该污染正式配置默认层）。

插件模块约定：``app/plugins/<id>/plugin.py`` 暴露 ——

* ``META``: dict，必含 ``"id"``（与目录名一致），可选 ``"depends": list[str]``；
* ``DEFAULTS``: 可选 dict，``plugins.<id>.*`` 的默认值（相对键 → 值）；
* ``register(ctx)``: 加载期回调，经 :class:`~app.plugins.context.PluginContext`
  声明全部贡献。

故障语义：

* PLUGINS 表内重复 id → **启动硬失败**（raise，重复 id 属于装配错误，
  静默放过等于让两个插件抢同一个命名空间）；
* 单插件 import / register 异常 → 捕获 + ``log.exception`` + 跳过该插件
  **及其递归依赖者**，其余插件照常（故障隔离，不拖垮应用）；
* 依赖缺失 / 依赖被禁用 / 依赖加载失败 → 跳过该插件及递归依赖者 +
  ``log.warning`` 列明因果链；循环依赖 → 涉及插件全部跳过 + 告警；
* 全部完成后 ``registry.freeze()`` —— 之后任何 ``add_*`` 抛 RuntimeError。

``enabled`` 改动**重启生效**：本进程内不做动态增删（无 unregister /
热重载，计划明令），切换 UI 由任务 17 的设置页插件管理区提供。
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import paths
from . import context, registry

log = logging.getLogger(__name__)

__all__ = ["collect_defaults", "load_plugins", "loaded_plugins"]

#: 最近一次 ``load_plugins`` 的加载结果清单（任务 17 插件管理区的数据源）。
_report: List[Dict[str, Any]] = []


def loaded_plugins() -> List[Dict[str, Any]]:
    """返回最近一次加载的结果清单（id / META / 启用状态 / 是否加载成功 / 跳过原因）。"""
    return [dict(entry) for entry in _report]


# ---------------------------------------------------------------- 发现与导入


def _formal_ids() -> List[str]:
    """正式插件 id 列表（PLUGINS 显式表）；重复 id 启动硬失败。

    运行时动态读 ``app.plugins.PLUGINS``（不在 import 时固化），测试夹具
    可以 monkeypatch 该表后调用本模块的函数。
    """
    from app.plugins import PLUGINS

    seen: set[str] = set()
    duplicates: List[str] = []
    for pid in PLUGINS:
        if pid in seen and pid not in duplicates:
            duplicates.append(pid)
        seen.add(pid)
    if duplicates:
        raise RuntimeError(
            f"PLUGINS 表内存在重复插件 id: {duplicates}（装配错误，启动硬失败）"
        )
    return list(PLUGINS)


def _discover_debug_ids() -> List[str]:
    """调试插件目录：``_`` 单下划线开头且含 ``plugin.py``（排除 ``__pycache__``）。"""
    base = Path(__file__).resolve().parent
    found: List[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("_") or name.startswith("__"):
            continue
        if (child / "plugin.py").is_file():
            found.append(name)
    return found


def _import_plugin(plugin_id: str) -> Any:
    """导入 ``app.plugins.<id>.plugin`` 并做形状校验，返回模块对象。"""
    module = importlib.import_module(f"app.plugins.{plugin_id}.plugin")
    meta = getattr(module, "META", None)
    if not isinstance(meta, dict) or meta.get("id") != plugin_id:
        raise ValueError(
            f"插件 {plugin_id!r} 的 META 缺失或 META.id 与目录名不一致: {meta!r}"
        )
    depends = meta.get("depends", [])
    if not isinstance(depends, list) or not all(isinstance(d, str) for d in depends):
        raise ValueError(f"插件 {plugin_id!r} 的 META.depends 必须是 list[str]: {depends!r}")
    if not callable(getattr(module, "register", None)):
        raise ValueError(f"插件 {plugin_id!r} 缺少可调用的 register(ctx)")
    return module


def _enabled_from_raw_config(plugin_id: str) -> bool:
    """阶段一专用的启用判定：直接 json.load 原始用户配置文件。

    此时 Config 尚不存在（鸡生蛋问题，见模块头注释）；读不到 / 文件
    不存在 / JSON 损坏一律按默认 ``true``。动态读 ``paths.USER_CONFIG_FILE``
    属性以便测试夹具重定向。
    """
    try:
        with open(paths.USER_CONFIG_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return True
    if not isinstance(raw, dict):
        return True
    value = raw.get("plugins", {})
    if not isinstance(value, dict):
        return True
    entry = value.get(plugin_id, {})
    if not isinstance(entry, dict):
        return True
    return bool(entry.get("enabled", True))


# ---------------------------------------------------------------- 依赖解析


def _find_cycle(remaining: Dict[str, List[str]]) -> Optional[List[str]]:
    """在剩余依赖图里找一个环（DFS 三色标记）；无环返回 None。"""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {pid: WHITE for pid in remaining}
    stack: List[str] = []

    def visit(pid: str) -> Optional[List[str]]:
        color[pid] = GRAY
        stack.append(pid)
        for dep in remaining[pid]:
            if dep not in remaining:
                continue
            if color[dep] == GRAY:
                return stack[stack.index(dep):] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found is not None:
                    return found
        stack.pop()
        color[pid] = BLACK
        return None

    for pid in remaining:
        if color[pid] == WHITE:
            found = visit(pid)
            if found is not None:
                return found
    return None


def _resolve_register_order(
    metas: Dict[str, Dict[str, Any]],
    unavailable: Dict[str, str],
) -> Tuple[List[str], Dict[str, str]]:
    """拓扑排序 + 不可用 / 循环依赖剔除。

    :param metas: 候选插件 ``{id: META}``（已启用且导入成功的集合）。
    :param unavailable: 已知不可用插件的 ``{id: 原因}``（被禁用 / 导入失败），
        用于把因果链写进跳过原因。
    :return: ``(注册顺序, {被跳过 id: 原因})``。被依赖者一定排在依赖者之前。
    """
    remaining: Dict[str, List[str]] = {
        pid: list(meta.get("depends", [])) for pid, meta in metas.items()
    }
    skipped: Dict[str, str] = {}
    while True:
        # 第一遍：剔除依赖不在候选集的插件（缺失 / 被禁用 / 导入失败 /
        # 或依赖自身已被剔除 —— 递归依赖者连带），直到不动点。
        removed = False
        for pid, deps in list(remaining.items()):
            missing = [d for d in deps if d not in remaining]
            if missing:
                chain = "; ".join(
                    f"{d!r} {unavailable.get(d, skipped.get(d, '未在插件清单中'))}"
                    for d in missing
                )
                skipped[pid] = f"依赖不可用（{chain}）"
                del remaining[pid]
                removed = True
        if removed:
            continue
        # 第二遍：无缺失依赖仍可能有环；找到一个环就整环剔除再回头复查
        # （环的依赖者会在下一轮被「依赖不可用」规则连带剔除）。
        cycle = _find_cycle(remaining)
        if cycle is None:
            break
        chain = " -> ".join(cycle)
        for pid in set(cycle):
            if pid in remaining:
                skipped[pid] = f"循环依赖（{chain}）"
                del remaining[pid]

    # 此时剩余图必为 DAG，DFS 出拓扑序（被依赖者先出栈）。
    order: List[str] = []
    done: set[str] = set()

    def emit(pid: str) -> None:
        if pid in done:
            return
        done.add(pid)
        for dep in remaining[pid]:
            emit(dep)
        order.append(pid)

    for pid in remaining:
        emit(pid)
    return order, skipped


# ---------------------------------------------------------------- 阶段一


def collect_defaults() -> Dict[str, Any]:
    """聚合正式插件的 ``plugins.<id>.*`` 默认值（``Config()`` 构造之前调用）。

    遍历 PLUGINS 中**启用**的插件，import 其 ``plugin.py`` 读 ``DEFAULTS``
    并经 ``registry.register_plugin_defaults`` 聚合；每个插件自动补
    ``"enabled": True`` 默认值（并入其 DEFAULTS，插件自身已声明则不覆盖）。
    禁用的插件跳过（默认值也不注入）；导入失败记 ``log.exception`` 并跳过
    （阶段二会再以正式 Config 复核并把失败写进加载清单）。

    幂等：重复调用时已在 registry 里的插件不重复登记（registry 对重复
    id 抛 ValueError）。调试插件（``_`` 前缀目录）不走这里 —— 它们不该
    污染正式配置默认层。
    """
    for pid in _formal_ids():
        if pid in registry.plugin_defaults()["plugins"]:
            continue
        try:
            module = _import_plugin(pid)
        except Exception:
            log.exception("插件 %s 阶段一导入失败，跳过默认值注入", pid)
            continue
        if not _enabled_from_raw_config(pid):
            log.info("插件 %s 已禁用（plugins.%s.enabled=false），跳过默认值注入", pid, pid)
            continue
        defaults = dict(getattr(module, "DEFAULTS", None) or {})
        defaults.setdefault("enabled", True)
        context.register_plugin_defaults(pid, defaults)
        log.info("插件 %s 默认值已聚合: %s", pid, sorted(defaults))
    return registry.plugin_defaults()


# ---------------------------------------------------------------- 阶段二


def load_plugins(backend: Any, windows: Any, *, include_debug: bool = False) -> List[Dict[str, Any]]:
    """实例化 PluginContext 并按拓扑序逐插件调 ``register(ctx)``，最后冻结注册表。

    :param backend: ``Backend`` 实例（设置键注册 + 正式 Config 复核启用态）。
    :param windows: ``WindowManager`` 实例（插件窗口注册）。
    :param include_debug: 是否追加加载 ``_`` 前缀调试插件目录。
    :return: 加载结果清单（同 :func:`loaded_plugins` 的形状）。
    """
    global _report
    formal_ids = _formal_ids()  # 重复 id 在这里 raise（启动硬失败）
    debug_ids = [pid for pid in _discover_debug_ids() if pid not in formal_ids] if include_debug else []

    # Backend 持有正式 Config 的引用（bridge.Backend._config，同仓库内部
    # 通道；loader 与 bridge 同属装配层，不另开 getter）。
    config = backend._config

    report: List[Dict[str, Any]] = []
    metas: Dict[str, Dict[str, Any]] = {}
    modules: Dict[str, Any] = {}
    unavailable: Dict[str, str] = {}

    for pid in formal_ids + debug_ids:
        entry: Dict[str, Any] = {
            "id": pid,
            "meta": None,
            "debug": pid in debug_ids,
            "enabled": True,
            "loaded": False,
            "reason": None,
        }
        report.append(entry)
        # 阶段二复核：与阶段一读的是同一份文件，结论应一致；这里是防
        # 阶段一之后配置被外部改动的兜底（默认 true）。
        if not bool(config.get(f"plugins.{pid}.enabled", True)):
            entry["enabled"] = False
            entry["reason"] = f"已禁用（plugins.{pid}.enabled=false）"
            unavailable[pid] = "被禁用"
            log.info("插件 %s 已禁用，跳过加载", pid)
            continue
        try:
            modules[pid] = _import_plugin(pid)
        except Exception as exc:
            entry["reason"] = f"导入失败: {exc}"
            unavailable[pid] = f"导入失败（{exc}）"
            log.exception("插件 %s 导入失败，跳过（其依赖者将连带跳过）", pid)
            continue
        metas[pid] = modules[pid].META
        entry["meta"] = dict(modules[pid].META)

    order, skipped = _resolve_register_order(metas, unavailable)
    for pid, reason in skipped.items():
        unavailable[pid] = reason
        log.warning("跳过插件 %s：%s", pid, reason)

    context.begin_load()
    failed: set[str] = set()
    by_id = {entry["id"]: entry for entry in report}
    try:
        for pid in order:
            # 依赖在注册阶段失败（运行时才能知道）→ 连带跳过依赖者。
            bad_deps = [d for d in metas[pid].get("depends", []) if d in failed]
            if bad_deps:
                reason = "依赖注册失败（" + ", ".join(repr(d) for d in bad_deps) + "）"
                by_id[pid]["reason"] = reason
                failed.add(pid)
                log.warning("跳过插件 %s：%s", pid, reason)
                continue
            ctx = context.PluginContext(pid, backend, windows)
            try:
                modules[pid].register(ctx)
            except Exception as exc:
                by_id[pid]["reason"] = f"register 异常: {exc}"
                failed.add(pid)
                log.exception("插件 %s register 抛异常，已跳过（其依赖者将连带跳过）", pid)
                continue
            by_id[pid]["loaded"] = True
            log.info("插件已加载: %s%s", pid, "（调试）" if by_id[pid]["debug"] else "")
    finally:
        context.end_load()

    for pid, reason in skipped.items():
        by_id[pid]["reason"] = reason

    registry.freeze()
    loaded_count = sum(1 for entry in report if entry["loaded"])
    log.info(
        "插件加载完成：%d 成功 / %d 跳过 / 共 %d，注册表已冻结",
        loaded_count, len(report) - loaded_count, len(report),
    )
    _report = report
    return report
