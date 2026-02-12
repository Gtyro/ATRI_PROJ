"""
人格系统全局状态管理模块
"""

from src.core.events import get_event_bus
from src.core.services.message_ingestor import MessageIngestor
from src.core.services.plugin_policy_service import PluginPolicyService
from src.infra.db.tortoise.plugin_policy_store import TortoisePluginPolicyStore

# 全局变量
persona_system = None
PERSONA_SYSTEM_ENABLED = False

# 事件总线与消息入口
event_bus = get_event_bus()
message_ingestor = MessageIngestor(event_bus, source="nonebot")
message_subscriber_registered = False

# 插件策略服务
plugin_policy_store = TortoisePluginPolicyStore()
plugin_policy_service = PluginPolicyService(plugin_policy_store)

def is_enabled():
    return PERSONA_SYSTEM_ENABLED