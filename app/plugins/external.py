"""Luminalium 2 插件系统 —— 外部导入插件（用户插件目录的发现 / 导入 / 卸载）。

2026-10-06 用户指令「给插件系统添加外部导入插件功能」落地。设计决策：

1. **落点在可写数据根**：外部插件一律拷贝进 ``data_dir() / "plugins"``，
   源文件（用户手里的文件夹 / zip）保持原样。开发环境数据根 = 项目根，
   打包后 = exe 同级目录（``app/paths.py`` 的便携模式约定），所以导入的
   插件跟用户配置 / 日志一样跨启动持久化。
   ⚠️ 这里必须是**函数**而不是模块级常量：``data_dir()`` 跟随
   ``LUMINALIUM_DATA_DIR`` 环境变量覆盖（smoke / 自检靠它把用户数据重定向到
   临时目录），常量写法会在导入那一刻把路径钉死（``paths.cache_dir`` 的
   注释里有完整论证）。

2. **导入即拷贝、重启生效**：导入做三件事——校验（含模块顶层代码执行，
   见下）、拷贝进用户插件目录、返回结果；本进程内**不做**任何注册
   （注册表在启动期末冻结，没有运行期插拔这条路，与启用 / 禁用同语义）。
   下次启动 ``loader`` 扫描用户插件目录并按 ``plugins.<id>.enabled`` 加载。

3. **校验 = 执行**：META 校验没法静态做（Python 没有「只 import 不执行
   顶层代码」的办法），所以导入时会真正运行一遍 ``plugin.py`` 的顶层代码
   （``META`` / ``DEFAULTS`` 常量与 import；``register(ctx)`` **不会**被调）。
   这与「插件本来就要在本机运行」是同一信任级别，但 UI 文案里必须把
   「导入即运行」讲清楚，提醒用户只导入可信来源。

4. **命名空间**：外部插件经合成包 ``lumi_user_plugins.<id>.plugin`` 导入
   （模块对象手工塞 ``sys.modules``，``__path__`` 指向用户插件目录）。
   好处：外部插件可以用相对导入 / 同目录兄弟模块（``from . import
   helper``），且与内建插件的 ``app.plugins.<id>`` 命名空间完全隔离，
   不会互相遮蔽。目录名即插件 id，所以 id 必须是合法的 Python 包名段。

5. **id 规则**：``^[a-z][a-z0-9_]*$`` 且不以 ``_`` 开头（``_`` 前缀是
   内部调试夹具的保留约定）、不得与内建正式插件 / 调试插件 / 已装外部
   插件撞名 —— id 同时是目录名、动作动词前缀、设置键前缀、配置路径段，
   五处命名空间共用一个 id（见 ``docs/plugin-development.md``）。

6. **zip 支持**：接受 ``plugin.py`` 位于压缩包根或唯一一级子目录内的 zip；
   解压到临时目录校验后再拷贝。解压逐条目做 zip-slip 防护（条目解析路径
   必须留在目标目录内），不信任压缩包里的 ``..`` 路径。

7. **自包含契约**：外部 ``plugin.py`` 必须自包含（顶层不用相对导入）——
   校验探针以独立模块执行它，没有包上下文；兄弟模块经合成包导入在
   真正加载期可用，但顶层相对导入会让校验直接失败。内建插件范例
   （``_demo``）本来就是单文件形态。
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Dict, Optional, Tuple

from ..paths import data_dir

log = logging.getLogger(__name__)

__all__ = [
    "user_plugins_dir",
    "discover",
    "import_plugin_module",
    "is_external",
    "install_from_path",
    "uninstall",
    "validate_module",
]

#: 外部插件的合成包名（``sys.modules`` 键，不对应真实目录）。
_NAMESPACE_PACKAGE = "lumi_user_plugins"

#: 合法插件 id：小写字母开头，只含小写字母 / 数字 / 下划线，不以 ``_`` 开头。
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_MODULE_CONTRACT = (
    "META（含与目录名一致的 id）与可调用的 register(ctx)"
)


def user_plugins_dir() -> Path:
    """外部插件的安装目录（可写数据根下的 ``plugins/``）。

    返回函数而不是常量，跟随 ``LUMINALIUM_DATA_DIR`` 覆盖；**不主动创建**
    （创建只发生在真正安装插件时，避免给每个启动流程塞一个空目录）。
    """
    return data_dir() / "plugins"


# ----------------------------------------------------------------- 发现


def discover() -> Dict[str, Path]:
    """扫描用户插件目录，返回 ``{id: 插件目录}``。

    目录名即插件 id；没有 ``plugin.py`` 的目录跳过（半截安装 / 用户手放的
    杂物），``_`` 前缀目录跳过（那是 ``app/plugins/`` 下调试夹具的保留
    约定，外部不走这条路）。扫描失败按空目录处理，不让外部插件机制
    拖垮启动。
    """
    base = user_plugins_dir()
    found: Dict[str, Path] = {}
    try:
        children = sorted(base.iterdir())
    except OSError:  # 目录不存在 / 权限问题：视为无外部插件
        return found
    for child in children:
        if not child.is_dir():
            continue
        name = child.name
        if not _ID_PATTERN.match(name):
            if not name.startswith((".", "_")) and name != "__pycache__":
                log.warning("外部插件目录名不合法，已跳过: %s", name)
            continue
        if not (child / "plugin.py").is_file():
            log.warning("外部插件 %s 缺少 plugin.py，已跳过", name)
            continue
        found[name] = child
    return found


def is_external(plugin_id: str) -> bool:
    """该 id 是否是已安装的外部插件（设置页「删除」按钮的判据）。"""
    return plugin_id in discover()


# ----------------------------------------------------------------- 导入


def _ensure_namespace_package() -> None:
    """把合成包 ``lumi_user_plugins`` 登记进 ``sys.modules``（幂等）。

    ``__path__`` 指向用户插件目录 —— 之后 ``importlib.import_module(
    "lumi_user_plugins.<id>.plugin")`` 就能从那里找子模块，外部插件的
    相对导入 / 兄弟模块导入也一并可用。
    """
    existing = sys.modules.get(_NAMESPACE_PACKAGE)
    root = str(user_plugins_dir())
    if existing is not None:
        # 目录可能在进程内第一次安装插件时才创建，跟着刷新一遍 __path__
        if list(existing.__path__) != [root]:
            existing.__path__ = [root]
        return
    spec = importlib.util.spec_from_loader(
        _NAMESPACE_PACKAGE, None, is_package=True
    )
    package = importlib.util.module_from_spec(spec)
    package.__path__ = [root]
    sys.modules[_NAMESPACE_PACKAGE] = package


def import_plugin_module(plugin_id: str) -> ModuleType:
    """导入已安装的外部插件 ``<id>/plugin.py``（不调 ``register``）。"""
    _ensure_namespace_package()
    return importlib.import_module(f"{_NAMESPACE_PACKAGE}.{plugin_id}.plugin")


def validate_module(module: ModuleType) -> str:
    """校验插件模块的形状，返回 ``META.id``；不合法抛 ``ValueError``。

    内建与外部插件共用一份契约：``META`` 必须是 dict 且 ``META.id`` 是
    非空字符串（与目录名一致由调用方比对；``_`` 前缀等命名细则只约束
    外部插件，见 ``install_from_path``），``register`` 必须可调用；
    ``depends``（若声明）必须是 ``list[str]``。
    """
    meta = getattr(module, "META", None)
    if not isinstance(meta, dict):
        raise ValueError(f"插件缺少 META dict: {meta!r}")
    plugin_id = meta.get("id")
    if not isinstance(plugin_id, str) or not plugin_id:
        raise ValueError(f"META.id 必须是非空字符串: {plugin_id!r}")
    depends = meta.get("depends", [])
    if not isinstance(depends, list) or not all(isinstance(d, str) for d in depends):
        raise ValueError(f"META.depends 必须是 list[str]: {depends!r}")
    if not callable(getattr(module, "register", None)):
        raise ValueError("缺少可调用的 register(ctx)")
    return plugin_id


# ----------------------------------------------------------------- 安装


def _copy_tree(src: Path, dst: Path) -> None:
    """拷贝插件目录，跳过 ``__pycache__`` 与 ``*.pyc``（导入缓存不带走）。"""

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]

    shutil.copytree(src, dst, ignore=_ignore)


def _locate_plugin_root(base: Path) -> Path:
    """在 ``base``（目录或 zip 解压目录）里找 ``plugin.py`` 的所在目录。

    支持两种布局：``base/plugin.py``（压缩包根就是插件）与
    ``base/<唯一一级子目录>/plugin.py``（压缩包里包了一层目录）。两种都
    不满足时抛 ``ValueError``。
    """
    if (base / "plugin.py").is_file():
        return base
    try:
        children = [c for c in base.iterdir() if c.is_dir()]
    except OSError as exc:
        raise ValueError(f"无法读取目录: {exc}") from exc
    candidates = [c for c in children if (c / "plugin.py").is_file()]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError(
            "压缩包里有多个含 plugin.py 的目录，无法判断插件根: "
            + ", ".join(c.name for c in candidates)
        )
    raise ValueError("没找到 plugin.py（插件根目录必须直接包含 plugin.py）")


def _extract_zip(zip_path: Path, target: Path) -> None:
    """解压插件 zip 到 ``target``，逐条目做 zip-slip 防护。"""
    target_resolved = target.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = (target / member.filename).resolve()
            if target_resolved not in member_path.parents and member_path != target_resolved:
                raise ValueError(f"压缩包条目越界（疑似 zip-slip）: {member.filename}")
        archive.extractall(target)


def _probe_meta_id(plugin_root: Path) -> str:
    """把候选插件 import 一遍做校验（**会执行 plugin.py 顶层代码**）。

    探针模块名用一次性前缀，不进 ``lumi_user_plugins`` 命名空间 ——
    校验失败时进程里不会留下半装的插件模块；校验通过后真正加载走的是
    命名空间包，重新执行一遍顶层代码（幂等插件才配当插件，常量声明天然
    幂等）。``register(ctx)`` 在探针与后续加载里都**不会**被调。
    """
    plugin_py = plugin_root / "plugin.py"
    probe_name = f"_lumi_plugin_probe_{plugin_root.name}"
    sys.modules.pop(probe_name, None)
    spec = importlib.util.spec_from_file_location(probe_name, plugin_py)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法为 {plugin_py} 构造导入规格")
    module = importlib.util.module_from_spec(spec)
    sys.modules[probe_name] = module
    try:
        spec.loader.exec_module(module)
        return validate_module(module)
    finally:
        sys.modules.pop(probe_name, None)


def install_from_path(source: str) -> Tuple[bool, str]:
    """把一个插件目录 / zip 安装进用户插件目录。

    流程：定位插件根 → 探针校验（执行顶层代码，拿 ``META.id``）→
    查 id 冲突（内建正式 / 内部调试 / 已装外部）→ 拷贝进
    ``user_plugins_dir()``。任何一步失败都不落一个字节的盘，返回
    ``(False, 人话原因)``。
    """
    src = Path(source)
    if not src.exists():
        return False, "路径不存在"
    temp_dir: Optional[Path] = None
    try:
        if src.is_file():
            if src.suffix.lower() != ".zip":
                return False, "只支持导入文件夹或 .zip 插件包"
            temp_dir = Path(tempfile.mkdtemp(prefix="lumi-plugin-import-"))
            try:
                _extract_zip(src, temp_dir)
            except zipfile.BadZipFile:
                return False, "这不是有效的 zip 插件包"
            plugin_root = _locate_plugin_root(temp_dir)
        elif src.is_dir():
            plugin_root = _locate_plugin_root(src)
        else:
            return False, "路径既不是文件夹也不是文件"

        plugin_id = _probe_meta_id(plugin_root)
        if not _ID_PATTERN.match(plugin_id):
            return False, (
                f"插件 id「{plugin_id}」不合法（须匹配 {_ID_PATTERN.pattern!r}，"
                "且不能以 _ 开头），请修改 META.id 后重试"
            )

        reserved = _reserved_ids()
        if plugin_id in reserved:
            return False, f"id「{plugin_id}」与现有插件冲突，请修改 META.id 后重试"

        base = user_plugins_dir()
        base.mkdir(parents=True, exist_ok=True)
        target = base / plugin_id
        if target.exists():
            return False, f"插件「{plugin_id}」已安装（如需覆盖请先在列表里删除）"
        _copy_tree(plugin_root, target)
        log.info("外部插件已安装: %s -> %s", plugin_id, target)
        return True, f"插件「{plugin_id}」已导入，重启应用后生效"
    except ValueError as exc:
        return False, str(exc)
    except ImportError as exc:
        # 探针顶层代码缺依赖 / 用了相对导入（探针模块没有包上下文，插件
        # 约定 plugin.py 自包含）。不是本模块的 bug，给用户看人话就行。
        return False, f"插件代码导入失败：{exc}"
    except Exception as exc:
        # 插件顶层代码什么都可能抛 —— 故障隔离到这里，绝不让导入动作
        # 打死设置窗口进程（OSError 之类也一并收进人话）。
        log.warning("外部插件安装失败: %s", exc, exc_info=True)
        return False, f"插件校验失败：{exc}"
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _reserved_ids() -> set:
    """不允许外部插件占用的 id：内建正式插件 + 内部调试插件目录。"""
    from . import PLUGINS

    reserved = set(PLUGINS)
    base = Path(__file__).resolve().parent
    try:
        for child in base.iterdir():
            if child.is_dir() and child.name.startswith("_") \
                    and not child.name.startswith("__") \
                    and (child / "plugin.py").is_file():
                reserved.add(child.name)
    except OSError:
        pass
    return reserved


# ----------------------------------------------------------------- 卸载


def uninstall(plugin_id: str) -> Tuple[bool, str]:
    """删除一个外部插件的安装目录（原始来源文件不受影响）。"""
    if not _ID_PATTERN.match(plugin_id or ""):
        return False, "非法的插件 id"
    base = user_plugins_dir()
    target = (base / plugin_id).resolve()
    # 防越权：只删用户插件目录**直接子目录**，别的路径一律拒绝
    if target.parent != base.resolve() or base.resolve() not in target.parents:
        return False, "插件路径越界，已拒绝删除"
    if not target.is_dir():
        return False, f"插件「{plugin_id}」未安装"
    try:
        shutil.rmtree(target)
    except OSError as exc:
        log.warning("外部插件卸载失败: %s", exc, exc_info=True)
        return False, f"删除失败：{exc}"
    log.info("外部插件已卸载: %s", plugin_id)
    return True, f"插件「{plugin_id}」已删除，重启应用后生效"
