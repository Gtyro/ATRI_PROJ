import inspect
import sys

from nonebot.plugin import PluginMetadata

from plugins.db_core.model_registry import register_model_module
from src.core.services.persona_policy_flags import (
    DEFAULT_PERSONA_POLICY_CONFIG,
    LLM_ACTIVE_REPLY_ENABLED_KEY,
    LLM_PASSIVE_REPLY_ENABLED_KEY,
    LLM_TOPIC_EXTRACT_ENABLED_KEY,
)
from src.core.persona_runtime_mode import should_use_script_mode

# 确保短期记忆模型在db_core初始化时已注册
register_model_module("models", "src.infra.db.tortoise.message_models")


# 判断当前代码是否在脚本模式下执行
def is_running_as_script():
    """检测代码是否在脚本模式下运行而非作为插件导入"""
    main_module = sys.modules['__main__']
    main_file = getattr(main_module, '__file__', '')
    stack = inspect.stack()
    # 启动器可以位于 scripts/，但 runpy 执行的真正入口仍是 bot.py。
    # 只把实际入口位于 scripts/ 的场景视为脚本导入；保留 adapter 调用栈保护。
    return should_use_script_mode(
        main_file,
        (frame.filename for frame in stack),
        (
            frame.filename
            for frame in stack
            if frame.frame.f_globals.get('__name__') == '__main__'
        ),
    )

# 只有在非脚本模式下才导入完整的插件功能
if not is_running_as_script():
    from .plugin import *
    __all__ = []
else:
    # 仅导出迁移脚本所需的最小模块和函数
    from src.infra.db.neo4j.memory_models import CognitiveNode, Memory, NodeAssociation
    from src.infra.db.neo4j.memory_repository import MemoryRepository
    from src.infra.db.tortoise.message_models import MessageQueue
    from src.infra.db.tortoise.message_repository import MessageRepository
    from .utils.config import check_config, load_config, save_config

    __all__ = ["load_config", "check_config", "save_config", "MemoryRepository", "MessageRepository", "MessageQueue", "Memory", "CognitiveNode", "NodeAssociation"]

# 插件元信息
__plugin_meta__ = PluginMetadata(
    name="Persona",
    description="具有自主意识和记忆能力的智能系统",
    usage="自动记忆和回复群消息",
    type="application",
    homepage="https://github.com/username/ATRI_PROJ",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": True,
            "default_enabled": False,
            "supports_ingest": True,
            "default_ingest_enabled": False,
            "core": True,
            "default_config": DEFAULT_PERSONA_POLICY_CONFIG,
            "controls": [
                {
                    "key": "ingest_enabled",
                    "label": "短期记忆",
                    "type": "switch",
                    "target": "ingest",
                },
                {
                    "key": LLM_TOPIC_EXTRACT_ENABLED_KEY,
                    "label": "长期记忆",
                    "type": "switch",
                },
                {
                    "key": LLM_PASSIVE_REPLY_ENABLED_KEY,
                    "label": "被动回复",
                    "type": "switch",
                },
                {
                    "key": LLM_ACTIVE_REPLY_ENABLED_KEY,
                    "label": "主动回复",
                    "type": "switch",
                },
            ],
        }
    },
)
