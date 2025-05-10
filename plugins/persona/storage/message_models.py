"""
消息队列模型 - 使用Tortoise ORM
用于短期记忆管理，与Neo4j存储的长期记忆分离
"""

from datetime import datetime
from tortoise import Model, fields
import pytz
from tzlocal import get_localzone

# 获取系统本地时区
LOCAL_TZ = get_localzone()

class MessageQueue(Model):
    """消息队列模型, 共10个字段, 5条必填, 2条自动生成, 3条可选"""
    id = fields.IntField(pk=True)
    conv_id = fields.CharField(max_length=50, index=True)
    user_id = fields.CharField(max_length=50, index=True)
    user_name = fields.CharField(max_length=50)
    content = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    is_processed = fields.BooleanField(default=False)
    '''是否已用api处理'''
    is_direct = fields.BooleanField(default=False)
    '''消息是否是发给机器人的'''
    is_bot = fields.BooleanField(default=False)
    '''消息是否是机器人发的'''
    metadata = fields.JSONField(default={})

    class Meta:
        table = "message_queue"

    def to_dict(self):
        # 将UTC时间转换为本地时区用于显示
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