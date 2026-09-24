"""配置读写。

设计要点：

* ``config/default_config.json`` 是默认值的唯一来源；
* 用户改动写入 ``config/config.json``，仅在键值与默认值不同时落盘；
* 采用「点号路径」访问：``config.get("presentation.corners.bottom_left.enabled")``；
* 支持 ``changed`` 回调，便于 QML 侧实时刷新。
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

    def __init__(self, user_file: Optional[str] = None) -> None:
        self._listeners: List[Callable[[str, Any], None]] = []
        # USER_CONFIG_FILE 既是读取来源也是落盘目标；
        # 传入自定义路径时两者一起改（此前两个字段写反了：
        # Config() 会读用户配置但 save() 直接 return，改动永远不落盘）。
        self._user_file = USER_CONFIG_FILE if user_file is None else user_file
        self._path_override = self._user_file

        self._defaults: Dict[str, Any] = self._read_json(DEFAULT_CONFIG_FILE, required=True)
        user_data = self._read_json(self._user_file) or {}
        self._data: Dict[str, Any] = _deep_merge(self._defaults, user_data)

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
            with open(target, "w", encoding="utf-8") as handle:
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
