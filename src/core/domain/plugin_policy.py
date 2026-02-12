"""插件策略模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PluginPolicy:
    """群组 x 插件策略配置。"""

    gid: str
    plugin_name: str
    enabled: bool = True
    ingest_enabled: bool = True
    group_name: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gid": self.gid,
            "plugin_name": self.plugin_name,
            "enabled": self.enabled,
            "ingest_enabled": self.ingest_enabled,
            "group_name": self.group_name,
            "config": self.config,
        }
