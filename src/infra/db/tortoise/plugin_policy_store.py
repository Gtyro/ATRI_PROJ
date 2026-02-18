"""插件策略的 Tortoise ORM 存储实现。"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.infra.db.tortoise.plugin_models import GroupPluginPolicy
from src.core.domain import PluginPolicy
from src.core.ports import PluginPolicyStore
from src.core.services.plugin_policy_defaults import PolicyDefaults, get_policy_defaults


class TortoisePluginPolicyStore(PluginPolicyStore):
    """基于 Tortoise ORM 的插件策略存储。"""

    def __init__(
        self,
        model: Any = GroupPluginPolicy,
        default_policy_provider: Optional[Callable[[str], PolicyDefaults]] = None,
    ) -> None:
        self.model = model
        self.default_policy_provider = default_policy_provider or get_policy_defaults

    def _build_defaults(self, gid: str, plugin_name: str, group_name: Optional[str]) -> Dict[str, Any]:
        defaults = self.default_policy_provider(plugin_name)
        normalized_name = self._normalize_group_name(group_name, gid)
        return {
            "name": normalized_name,
            "enabled": defaults.enabled,
            "ingest_enabled": defaults.ingest_enabled,
            "policy_config": defaults.config or {},
        }

    def _normalize_group_name(self, group_name: Optional[str], gid: str) -> str:
        name = group_name or gid
        max_length = getattr(self.model._meta.fields_map.get("name"), "max_length", 50)
        if max_length and len(name) > max_length:
            return name[:max_length]
        return name

    async def get_policy(
        self,
        gid: str,
        plugin_name: str,
        *,
        group_name: Optional[str] = None,
    ) -> PluginPolicy:
        defaults = self._build_defaults(gid, plugin_name, group_name)
        policy, created = await self.model.get_or_create(
            gid=gid,
            plugin_name=plugin_name,
            defaults=defaults,
        )
        if group_name:
            normalized_name = self._normalize_group_name(group_name, gid)
            if policy.name != normalized_name:
                policy.name = normalized_name
            await policy.save()
        if created:
            policy = await self.model.get(id=policy.id)
        return PluginPolicy(
            gid=policy.gid,
            plugin_name=policy.plugin_name,
            enabled=policy.enabled,
            ingest_enabled=policy.ingest_enabled,
            group_name=policy.name,
            config=policy.policy_config or {},
        )

    async def set_policy(
        self,
        gid: str,
        plugin_name: str,
        *,
        enabled: Optional[bool] = None,
        ingest_enabled: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None,
        group_name: Optional[str] = None,
    ) -> PluginPolicy:
        policy = await self._ensure_policy(gid, plugin_name, group_name=group_name)
        changed = False

        if enabled is not None:
            policy.enabled = bool(enabled)
            changed = True
        if ingest_enabled is not None:
            policy.ingest_enabled = bool(ingest_enabled)
            changed = True
        if config is not None:
            policy.policy_config = config
            changed = True
        if group_name:
            normalized_name = self._normalize_group_name(group_name, gid)
            if policy.name != normalized_name:
                policy.name = normalized_name
            changed = True

        if changed:
            await policy.save()

        return PluginPolicy(
            gid=policy.gid,
            plugin_name=policy.plugin_name,
            enabled=policy.enabled,
            ingest_enabled=policy.ingest_enabled,
            group_name=policy.name,
            config=policy.policy_config or {},
        )

    async def list_policies(
        self,
        *,
        plugin_name: Optional[str] = None,
        gids: Optional[List[str]] = None,
    ) -> List[PluginPolicy]:
        query = self.model.all()
        if plugin_name:
            query = query.filter(plugin_name=plugin_name)
        if gids:
            query = query.filter(gid__in=gids)
        items = await query
        return [
            PluginPolicy(
                gid=item.gid,
                plugin_name=item.plugin_name,
                enabled=item.enabled,
                ingest_enabled=item.ingest_enabled,
                group_name=item.name,
                config=item.policy_config or {},
            )
            for item in items
        ]

    async def _ensure_policy(
        self,
        gid: str,
        plugin_name: str,
        *,
        group_name: Optional[str] = None,
    ) -> Any:
        defaults = self._build_defaults(gid, plugin_name, group_name)
        policy, _ = await self.model.get_or_create(
            gid=gid,
            plugin_name=plugin_name,
            defaults=defaults,
        )
        if group_name:
            normalized_name = self._normalize_group_name(group_name, gid)
            if policy.name != normalized_name:
                policy.name = normalized_name
            await policy.save()
        return policy
