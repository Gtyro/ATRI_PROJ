import pytz
from tortoise import Model, fields
from tzlocal import get_localzone

LOCAL_TZ = get_localzone()

class BasicMessage(Model):
    """基础消息模型"""
    id = fields.IntField(primary_key=True)
    conv_id = fields.CharField(max_length=50, db_index=True)
    user_id = fields.CharField(max_length=50, db_index=True)
    user_name = fields.CharField(max_length=50)
    content = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True, db_index=True)
    is_processed = fields.BooleanField(default=False)
    is_direct = fields.BooleanField(default=False)
    is_bot = fields.BooleanField(default=False)
    metadata = fields.JSONField(default={})

    class Meta:
        table = "basic_message"

    def to_dict(self):
        created_time = self.created_at.replace(tzinfo=pytz.UTC).astimezone(LOCAL_TZ) if self.created_at else None
        return {
            "id": self.id,
            "conv_id": self.conv_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "created_at": created_time,
            "is_processed": self.is_processed,
            "is_direct": self.is_direct,
            "is_bot": self.is_bot,
            "metadata": self.metadata
        }


from plugins.db_core.model_registry import register_model_module

register_model_module("models", "plugins.message_basic.models")
