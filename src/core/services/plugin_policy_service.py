"""插件策略服务。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.domain import PluginPolicy
from src.core.ports import PluginPolicyStore


class PluginPolicyService:
    """群组 x 插件策略服务。"""

    def __init__(
        self,
        store: PluginPolicyStore,
        *,
        default_enabled: bool = True,
        default_ingest_enabled: bool = True,
    ) -> None:
        self.store = store
        self.default_enabled = default_enabled
        self.default_ingest_enabled = default_ingest_enabled

    def _apply_defaults(self, policy: PluginPolicy) -> PluginPolicy:
        enabled = self.default_enabled if policy.enabled is None else bool(policy.enabled)
        ingest_enabled = (
            self.default_ingest_enabled
            if policy.ingest_enabled is None
            else bool(policy.ingest_enabled)
        )
        config = policy.config or {}
        return PluginPolicy(
            gid=policy.gid,
            plugin_name=policy.plugin_name,
            enabled=enabled,
            ingest_enabled=ingest_enabled,
            group_name=policy.group_name,
            config=config,
        )

    async def get_policy(
        self,
        gid: str,
        plugin_name: str,
        *,
        group_name: Optional[str] = None,
    ) -> PluginPolicy:
        policy = await self.store.get_policy(gid, plugin_name, group_name=group_name)
        return self._apply_defaults(policy)

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
        policy = await self.store.set_policy(
            gid,
            plugin_name,
            enabled=enabled,
            ingest_enabled=ingest_enabled,
            config=config,
            group_name=group_name,
        )
        return self._apply_defaults(policy)

    async def list_policies(
        self,
        *,
        plugin_name: Optional[str] = None,
        gids: Optional[List[str]] = None,
    ) -> List[PluginPolicy]:
        policies = await self.store.list_policies(plugin_name=plugin_name, gids=gids)
        return [self._apply_defaults(policy) for policy in policies]

    async def ensure_policies(
        self,
        groups: List[Dict[str, Any]],
        plugin_names: List[str],
    ) -> None:
        """确保群组 x 插件策略存在（用于初始化默认值）。"""
        if not groups or not plugin_names:
            return

        gids = [str(group.get("group_id") or group.get("gid") or "") for group in groups]
        gids = [gid for gid in gids if gid]
        if not gids:
            return

        existing = await self.store.list_policies(gids=gids)
        existing_keys = {(policy.gid, policy.plugin_name) for policy in existing}

        for group in groups:
            gid = str(group.get("group_id") or group.get("gid") or "")
            if not gid:
                continue
            group_name = group.get("group_name") or group.get("name") or gid
            for plugin_name in plugin_names:
                if (gid, plugin_name) in existing_keys:
                    continue
                await self.store.set_policy(
                    gid=gid,
                    plugin_name=plugin_name,
                    group_name=group_name,
                )

    async def is_enabled(
        self,
        gid: str,
        plugin_name: str,
        *,
        group_name: Optional[str] = None,
    ) -> bool:
        policy = await self.get_policy(gid, plugin_name, group_name=group_name)
        return policy.enabled

    async def is_ingest_enabled(
        self,
        gid: str,
        plugin_name: str,
        *,
        group_name: Optional[str] = None,
    ) -> bool:
        policy = await self.get_policy(gid, plugin_name, group_name=group_name)
        return policy.ingest_enabled
