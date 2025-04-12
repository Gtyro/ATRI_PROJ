from .core.persona_system import PersonaSystem
from .plugin import *

__all__ = ["PersonaSystem"]

# 插件元信息
__plugin_meta__ = {
    "name": "Persona",
    "description": "具有自主意识和记忆能力的智能系统",
    "usage": "自动记忆和回复群消息",
    "type": "application",
    "homepage": "https://github.com/username/ATRI_PROJ",
    "supported_adapters": {"~all"},
} 