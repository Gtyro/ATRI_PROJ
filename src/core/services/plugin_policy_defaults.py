"""插件策略默认值与可见性规则。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import nonebot


@dataclass(frozen=True)
class PolicyDefaults:
    enabled: bool
    ingest_enabled: bool
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyMeta:
    manageable: bool
    default_enabled: bool
    supports_ingest: bool
    default_ingest_enabled: bool
    core: bool = False
    default_config: Dict[str, Any] = field(default_factory=dict)
    config_controls: List[Dict[str, Any]] = field(default_factory=list)
    auto_disable_on_inactive: bool = False


# 未显式配置的插件，默认关闭并禁止入库
DEFAULT_POLICY = PolicyDefaults(enabled=False, ingest_enabled=False, config={})


def normalize_plugin_name(plugin: Any) -> Optional[str]:
    module_name = getattr(plugin, "module_name", None)
    if module_name:
        if module_name.startswith("plugins."):
            return module_name.split(".", 1)[1].split(".", 1)[0]
        return module_name.split(".")[-1]
    name = getattr(plugin, "name", None)
    if name:
        return name
    return None


def _extract_extra(plugin: Any) -> Dict[str, Any]:
    metadata = getattr(plugin, "metadata", None)
    if not metadata:
        return {}
    extra = getattr(metadata, "extra", None)
    return extra if isinstance(extra, dict) else {}


def _normalize_controls(policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    controls = policy.get("controls") or policy.get("config_controls") or []
    if not isinstance(controls, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in controls:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key:
            continue
        label = item.get("label") or item.get("name") or key
        if not isinstance(label, str) or not label:
            label = key
        control = {
            "key": key,
            "label": label,
            "type": item.get("type") if isinstance(item.get("type"), str) else "switch",
        }
        target = item.get("target")
        if isinstance(target, str) and target:
            control["target"] = target
        description = item.get("description")
        if isinstance(description, str) and description:
            control["description"] = description
        also_set = item.get("also_set")
        if isinstance(also_set, list):
            extra_keys = [value for value in also_set if isinstance(value, str) and value]
            if extra_keys:
                control["also_set"] = extra_keys
        normalized.append(control)
    return normalized


def _parse_policy_meta(plugin: Any) -> Optional[PolicyMeta]:
    extra = _extract_extra(plugin)
    policy = extra.get("policy")
    if not isinstance(policy, dict):
        return None
    manageable = bool(policy.get("manageable", policy.get("visible", False)))
    default_enabled = bool(policy.get("default_enabled", False))
    supports_ingest = bool(policy.get("supports_ingest", False))
    if supports_ingest and "default_ingest_enabled" not in policy:
        default_ingest_enabled = default_enabled
    else:
        default_ingest_enabled = bool(policy.get("default_ingest_enabled", False))
    core = bool(policy.get("core", False))
    default_config = policy.get("default_config", {})
    if not isinstance(default_config, dict):
        default_config = {}
    config_controls = _normalize_controls(policy)
    auto_disable_on_inactive = bool(policy.get("auto_disable_on_inactive", False))
    return PolicyMeta(
        manageable=manageable,
        default_enabled=default_enabled,
        supports_ingest=supports_ingest,
        default_ingest_enabled=default_ingest_enabled,
        core=core,
        default_config=default_config,
        config_controls=config_controls,
        auto_disable_on_inactive=auto_disable_on_inactive,
    )


def get_auto_disable_plugins() -> List[str]:
    """获取允许在群组不活跃时自动关闭的插件列表。"""
    policy_map = _build_policy_map()
    return sorted(
        [name for name, meta in policy_map.items() if meta.auto_disable_on_inactive]
    )


def _build_policy_map() -> Dict[str, PolicyMeta]:
    policy_map: Dict[str, PolicyMeta] = {}
    for plugin in nonebot.get_loaded_plugins():
        name = normalize_plugin_name(plugin)
        if not name:
            continue
        policy_meta = _parse_policy_meta(plugin)
        if policy_meta:
            policy_map[name] = policy_meta
    return policy_map


def get_policy_plugins(*, include_hidden: bool = False) -> List[str]:
    """获取具备策略元信息的插件列表。"""
    policy_map = _build_policy_map()
    if include_hidden:
        return sorted(policy_map.keys())
    return sorted([name for name, meta in policy_map.items() if meta.manageable])


def get_ingest_plugins() -> List[str]:
    """获取支持入库开关的插件列表。"""
    policy_map = _build_policy_map()
    return sorted([name for name, meta in policy_map.items() if meta.supports_ingest])


def get_policy_defaults(plugin_name: str) -> PolicyDefaults:
    """获取指定插件的默认策略。"""
    policy_map = _build_policy_map()
    policy_meta = policy_map.get(plugin_name)
    if not policy_meta:
        return DEFAULT_POLICY
    ingest_enabled = (
        policy_meta.default_ingest_enabled if policy_meta.supports_ingest else False
    )
    return PolicyDefaults(
        enabled=policy_meta.default_enabled,
        ingest_enabled=ingest_enabled,
        config=policy_meta.default_config or {},
    )


def get_visible_plugins(plugin_names: Iterable[str]) -> List[str]:
    """过滤并排序可见插件列表。"""
    visible_set = set(get_policy_plugins())
    return sorted({name for name in plugin_names if name in visible_set})


def build_defaults_payload(plugin_names: Iterable[str]) -> Dict[str, Any]:
    """构造前端需要的默认策略信息。"""
    plugins = {}
    for name in plugin_names:
        defaults = get_policy_defaults(name)
        plugins[name] = {
            "enabled": defaults.enabled,
            "ingest_enabled": defaults.ingest_enabled,
            "config": defaults.config or {},
        }
    return {
        "global": {
            "enabled": DEFAULT_POLICY.enabled,
            "ingest_enabled": DEFAULT_POLICY.ingest_enabled,
            "config": {},
        },
        "plugins": plugins,
    }


def build_policy_meta_payload(plugin_names: Iterable[str]) -> Dict[str, Any]:
    """构造前端需要的插件策略元信息。"""
    policy_map = _build_policy_map()
    payload: Dict[str, Any] = {}
    for name in plugin_names:
        policy_meta = policy_map.get(name)
        if not policy_meta:
            continue
        if not policy_meta.config_controls:
            continue
        payload[name] = {
            "controls": policy_meta.config_controls,
        }
    return payload
