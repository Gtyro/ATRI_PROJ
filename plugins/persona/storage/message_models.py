"""消息队列模型兼容导入路径。"""

from plugins.db_core.model_registry import register_model_module
from src.infra.db.tortoise.message_models import MessageQueue

register_model_module("models", "src.infra.db.tortoise.message_models")

__all__ = ["MessageQueue"]