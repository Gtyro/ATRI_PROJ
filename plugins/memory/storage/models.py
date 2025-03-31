from tortoise import Model, fields
import time

# 定义Tortoise ORM模型
class Memory(Model):
    """记忆模型"""
    id = fields.CharField(max_length=36, primary_key=True)
    conv_id = fields.CharField(max_length=20, index=True)
    '''group_id or private_id'''
    topic = fields.CharField(max_length=128)
    summary = fields.TextField()
    entities = fields.TextField()
    '''以JSON格式存储的实体列表'''
    start_time = fields.CharField(max_length=20)
    end_time = fields.CharField(max_length=20)
    involved_users = fields.TextField()
    created_at = fields.FloatField()
    last_accessed = fields.FloatField()
    weight = fields.FloatField(default=1.0)
    '''记忆权重，太小记忆会被遗忘'''
    metadata = fields.TextField()
    class Meta:
        table = "memories"
        table_description = "存储记忆的核心表"

    def __str__(self):
        return f"{self.conv_id}:{self.topic[:20]}"


class MemoryEntity(Model):
    """记忆实体模型 - 表示记忆中的概念、对象或实体"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True, index=True)
    '''实体名称，全局唯一'''
    memory = fields.ForeignKeyField('models.Memory', related_name='memory_entities')
    '''记忆外键'''
    created_at = fields.FloatField(default=time.time)
    
    class Meta:
        table = "memory_entities"
        table_description = "记忆中的实体，用于快速检索"

    def __str__(self):
        return self.name


class MemoryAssociation(Model):
    """记忆关联模型 - 表示实体之间的关联关系"""
    id = fields.IntField(pk=True)
    source = fields.ForeignKeyField('models.MemoryEntity', related_name='outgoing_associations')
    target = fields.ForeignKeyField('models.MemoryEntity', related_name='incoming_associations')
    source_name = fields.CharField(max_length=100, null=True)
    '''源实体名称，便于直接查看'''
    target_name = fields.CharField(max_length=100, null=True)
    '''目标实体名称，便于直接查看'''
    strength = fields.FloatField(default=0.5)
    '''关联强度'''
    created_at = fields.FloatField()
    updated_at = fields.FloatField()

    class Meta:
        table = "memory_associations"
        table_description = "实体之间的关联关系"
        unique_together = (("source_id", "target_id"),)

    def __str__(self):
        return f"{self.source_name}->{self.target_name} ({self.strength:.2f})"


class MessageQueueItem(Model):
    """消息队列项模型"""
    id = fields.CharField(pk=True, max_length=36)
    user_id = fields.CharField(max_length=36)
    user_name = fields.CharField(max_length=36)
    '''用户昵称，只有接收消息时能获取'''
    content = fields.TextField()
    is_direct = fields.BooleanField(default=False)
    '''消息是否是发给机器人的'''
    is_me = fields.BooleanField(default=False)
    '''消息是否是机器人发的'''
    conv_id = fields.CharField(max_length=30, null=True, index=True)
    '''会话ID'''
    created_at = fields.FloatField(index=True)
    processed = fields.BooleanField(default=False)
    '''是否已用api处理'''
    metadata = fields.TextField(default="{}")
    '''存储额外元数据，如回复关系等'''

    class Meta:
        table = "message_queue"
        table_description = "消息处理队列"

    def __str__(self):
        return f"{self.user_id}:{self.user_name}:{self.content[:20]}"