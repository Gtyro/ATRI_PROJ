"""消息队列存储库兼容导入路径。"""

from src.infra.db.tortoise.message_repository import MessageRepository

__all__ = ["MessageRepository"]