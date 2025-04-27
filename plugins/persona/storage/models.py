from datetime import datetime
from typing import Dict, List, Optional
from tortoise import Model, fields
import pytz
from tzlocal import get_localzone
import uuid

# Get the local timezone from the system
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
        # Convert UTC time to local timezone for display
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

class Memory(Model):
    """记忆模型, 共10个字段"""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    conv_id = fields.CharField(max_length=20, index=True)
    '''group_id or private_id'''

    # api提取部分
    title = fields.CharField(max_length=100)
    content = fields.TextField()
    nodes = fields.ManyToManyField('models.CognitiveNode', related_name='memories')

    # 长期记忆部分
    created_at = fields.DatetimeField(auto_now_add=True)
    last_accessed = fields.DatetimeField(auto_now=True)
    weight = fields.FloatField(default=1.0)
    '''记忆权重，权重太小记忆会被遗忘'''
    metadata = fields.JSONField(default={})
    is_permanent = fields.BooleanField(default=False)
    '''是否为常驻记忆，常驻记忆不会被遗忘(删除)，但仍会被衰减'''
    
    class Meta:
        table = "memories"

class CognitiveNode(Model):
    """认知节点模型, 共5个字段"""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    name = fields.CharField(max_length=100, index=True)
    conv_id = fields.CharField(max_length=20, default='', null=False, index=True)
    '''会话id
    当conv_id存在时, (conv_id, name)唯一
    当conv_id为空字符串时, ('', name)仍然唯一
    '''
    act_lv = fields.FloatField(default=1.0)
    '''激活水平'''
    created_at = fields.DatetimeField(auto_now_add=True)
    last_accessed = fields.DatetimeField(auto_now=True)
    is_permanent = fields.BooleanField(default=False)
    '''是否为常驻节点，常驻节点不会被遗忘(删除)，但仍会被衰减'''
    
    class Meta:
        table = "nodes"
        unique_together = (("conv_id", "name"),)

class Association(Model):
    """认知节点关联模型, 共9个字段"""
    source = fields.ForeignKeyField(
        "models.CognitiveNode", 
        related_name="source_associations",
        on_delete=fields.CASCADE
    )
    target = fields.ForeignKeyField(
        "models.CognitiveNode",
        related_name="target_associations",
        on_delete=fields.CASCADE
    )
    strength = fields.FloatField(default=1.0)
    '''关联强度'''
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "associations"
        unique_together = (("source", "target"),)