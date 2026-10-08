"""配置读写。

设计要点：

* ``config/default_config.json`` 是默认值的唯一来源；
* 用户改动写入 ``config/config.json``，仅在键值与默认值不同时落盘；
* 采用「点号路径」访问：``config.get("presentation.corners.bottom_left.enabled")``；
* 支持 ``changed`` 回调，便于 QML 侧实时刷新。

插件默认值注入（``extra_defaults``）：

* 注入的是「默认层」，时机必须在用户数据合并之前——``save()`` 走 ``_diff``
  只落盘「``_data`` 有而 ``_defaults`` 没有（或不同）」的键，把插件默认值注入
  ``_defaults`` 才能做到既不会落盘污染用户文件，又不会掩盖用户显式改动的语义
  （用户改过的键在 ``_data`` 里与 ``_defaults`` 不同，仍会正常落盘）；
* **列表值一律拒绝注入**：``_deep_merge`` 对列表是整体替换而非递归合并，
  列表型贡献注入默认层后，只要用户配置里出现同路径列表就会被静默吞掉
  且无从察觉；列表型贡献必须改走读取层（``get`` 时合并）处理，因此这里
  遇到列表直接跳过并 ``log.warning``。
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional

from .paths import CONFIG_DIR, DEFAULT_CONFIG_FILE, USER_CONFIG_FILE

log = logging.getLogger(__name__)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """把 ``override`` 合并进 ``base`` 的副本，dict 递归合并，其余直接覆盖。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Config:
    """轻量配置容器。"""

    def __init__(
        self,
        user_file: Optional[str] = None,
        extra_defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._listeners: List[Callable[[str, Any], None]] = []
        # USER_CONFIG_FILE 既是读取来源也是落盘目标；
        # 传入自定义路径时两者一起改（此前两个字段写反了：
        # Config() 会读用户配置但 save() 直接 return，改动永远不落盘）。
        self._user_file = USER_CONFIG_FILE if user_file is None else user_file
        self._path_override = self._user_file

        self._defaults: Dict[str, Any] = self._read_json(DEFAULT_CONFIG_FILE, required=True)
        # 插件默认值注入：必须在用户数据合并之前完成（原因见模块头注释）。
        # 列表值拒绝注入：_deep_merge 对列表是整体替换，注入默认层后会被
        # 用户配置静默吞掉，列表型贡献必须走读取层合并，故跳过并告警。
        if extra_defaults:
            filtered = self._strip_list_values(extra_defaults, prefix="")
            if filtered:
                self._defaults = _deep_merge(self._defaults, filtered)
        user_data = self._read_json(self._user_file) or {}
        self._data: Dict[str, Any] = _deep_merge(self._defaults, user_data)

    @staticmethod
    def _strip_list_values(values: Dict[str, Any], prefix: str) -> Dict[str, Any]:
        """递归剔除 ``extra_defaults`` 中的列表值（含嵌套 dict 内的列表）。

        跳过原因见模块头注释：``_deep_merge`` 对列表整体替换，注入默认层
        会被用户配置静默吞掉。被剔除的路径逐条 ``log.warning``。
        """
        out: Dict[str, Any] = {}
        for key, value in values.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, list):
                log.warning("extra_defaults 中的列表值不允许注入默认层，已跳过: %s", path)
                continue
            if isinstance(value, dict):
                sub = Config._strip_list_values(value, path)
                if sub:
                    out[key] = sub
                continue
            out[key] = value
        return out

    # ------------------------------------------------------------------ io

    @staticmethod
    def _read_json(path, required: bool = False) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            if required:
                raise
            return None
        except (json.JSONDecodeError, OSError) as exc:  # 配置损坏时退回默认值
            log.warning("读取配置失败 %s: %s", path, exc)
            return None

    def save(self) -> None:
        """把与默认值不同的部分写入用户配置。"""
        if self._path_override is None:
            return
        diff = self._diff(self._defaults, self._data)
        target = self._path_override
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            # newline="\n"：文本模式在 Windows 上默认把 \n 写成 \r\n，
            # 同一份内容两次落盘字节就不同 —— smoke 的铁律断言做的是
            # **字节级**对比，「没改任何东西却变了 4 个字节」全是这条
            # 隐式翻译干的（2026-10-06 iron-off 场景实锤）。
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(diff, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            log.warning("写入配置失败 %s: %s", target, exc)

    @classmethod
    def _diff(cls, base: Any, current: Any) -> Any:
        if isinstance(base, dict) and isinstance(current, dict):
            out: Dict[str, Any] = {}
            for key, value in current.items():
                if key not in base:
                    out[key] = value
                else:
                    sub = cls._diff(base[key], value)
                    if sub != {} and not (isinstance(sub, dict) and not sub):
                        out[key] = sub
            return out
        if base == current:
            return {}
        return current

    # --------------------------------------------------------------- access

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, path: str, value: Any, persist: bool = True) -> None:
        parts = path.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if node.get(parts[-1]) == value:
            return
        node[parts[-1]] = value
        for callback in list(self._listeners):
            try:
                callback(path, value)
            except Exception:  # pragma: no cover - 监听器不应影响主流程
                log.exception("配置监听器异常: %s", path)
        if persist:
            self.save()

    def remove(self, path: str, persist: bool = True) -> bool:
        """从用户数据里删掉一个点号路径子树（外部插件卸载时清残留用）。

        只动 ``_data`` 不动 ``_defaults`` —— 被删插件的默认值要等下次启动
        才会从默认层消失，而这正合适：期间 diff 落盘不会把「默认层有、
        用户层没有」的键写出来，用户文件不会留死条目。路径不存在返回
        ``False``（幂等，卸载一个从没改过设置的插件时就是这条空路径）。
        """
        parts = path.split(".")
        node = self._data
        for part in parts[:-1]:
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        if not isinstance(node, dict) or parts[-1] not in node:
            return False
        del node[parts[-1]]
        if persist:
            self.save()
        return True

    def update(self, values: Dict[str, Any], persist: bool = True) -> None:
        for path, value in values.items():
            self.set(path, value, persist=False)
        if persist:
            self.save()

    def on_change(self, callback: Callable[[str, Any], None]) -> None:
        self._listeners.append(callback)

    def as_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)

    def dump(self, keys: Iterable[str]) -> Dict[str, Any]:
        return {key: self.get(key) for key in keys}
