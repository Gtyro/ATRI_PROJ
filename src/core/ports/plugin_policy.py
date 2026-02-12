"""插件策略存储端口定义。"""

from typing import Any, Dict, List, Optional, Protocol

from src.core.domain import PluginPolicy


class PluginPolicyStore(Protocol):
    async def get_policy(
        self,
        gid: str,
        plugin_name: str,
        *,
        group_name: Optional[str] = None,
    ) -> PluginPolicy:
        ...

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
        ...

    async def list_policies(
        self,
        *,
        plugin_name: Optional[str] = None,
        gids: Optional[List[str]] = None,
    ) -> List[PluginPolicy]:
        ...
