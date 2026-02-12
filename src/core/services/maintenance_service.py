"""维护任务服务。"""

import logging
import time
from typing import Any, Dict, Optional, Union

from ..domain import PersonaConfig
from .plugin_policy_service import PluginPolicyService


class MaintenanceService:
    """负责定时维护与衰减任务。"""

    def __init__(
        self,
        group_config: Any,
        config: Union[PersonaConfig, Dict[str, Any]],
        conversation_service: Any,
        decay_manager: Any,
        plugin_name: str,
        plugin_policy_service: Optional[PluginPolicyService] = None,
    ) -> None:
        self.group_config = group_config
        self.config = config
        self.conversation_service = conversation_service
        self.decay_manager = decay_manager
        self.plugin_name = plugin_name
        self.plugin_policy_service = plugin_policy_service

    def _batch_interval(self) -> int:
        if isinstance(self.config, PersonaConfig):
            return self.config.batch_interval
        if "batch_interval" not in self.config:
            raise ValueError("batch_interval 未配置")
        return int(self.config["batch_interval"])

    async def schedule_maintenance(self) -> None:
        distinct_gids = await self.group_config.get_distinct_group_ids(self.plugin_name)

        for group_id in distinct_gids:
            if self.plugin_policy_service:
                enabled = await self.plugin_policy_service.is_enabled(
                    group_id,
                    self.plugin_name,
                )
                if not enabled:
                    logging.info(f"群组 {group_id} 插件已禁用，跳过维护任务")
                    continue
            gpconfig = await self.group_config.get_config(group_id, self.plugin_name)
            plugin_config = gpconfig.plugin_config or {}

            next_process_time = plugin_config.get("next_process_time", 0)
            if time.time() > next_process_time or logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                await self.conversation_service.process_conversation(f"group_{group_id}", "")

                plugin_config["next_process_time"] = time.time() + self._batch_interval()
                gpconfig.plugin_config = plugin_config
                await gpconfig.save()
            else:
                logging.info(f"群组 {group_id} 未到处理时间，跳过")

        await self.decay_manager.apply_decay()
