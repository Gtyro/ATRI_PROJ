"""
使用Neo4j OGM (neomodel)定义记忆系统的模型
包括:
- Memory(记忆)
- CognitiveNode(认知节点)
- 它们之间的关系
"""

import uuid
import time
from datetime import datetime
from neomodel import (
    StructuredNode, StringProperty, FloatProperty, 
    DateTimeProperty, BooleanProperty, UniqueIdProperty, 
    RelationshipTo, RelationshipFrom, StructuredRel,
    config
)

# 配置在MemoryRepository.initialize()方法中设置
# 正确格式: bolt://user:password@host:port

class NodeMemoryRelationship(StructuredRel):
    """节点与记忆之间的关系"""
    created_at = DateTimeProperty(default=lambda: datetime.now())

class NodeAssociation(StructuredRel):
    """节点之间的关联关系"""
    strength = FloatProperty(default=1.0)
    created_at = DateTimeProperty(default=lambda: datetime.now())
    updated_at = DateTimeProperty(default=lambda: datetime.now())

class Memory(StructuredNode):
    """记忆模型"""
    uid = UniqueIdProperty()
    conv_id = StringProperty(required=True, index=True)
    title = StringProperty(required=True)
    content = StringProperty(required=True)
    created_at = DateTimeProperty(default=lambda: datetime.now())
    last_accessed = DateTimeProperty(default=lambda: datetime.now())
    weight = FloatProperty(default=1.0)
    is_permanent = BooleanProperty(default=False)
    metadata = StringProperty(default="{}")  # JSON存储为字符串
    
    # 关系定义
    nodes = RelationshipTo('CognitiveNode', 'RELATED_TO', model=NodeMemoryRelationship)

    def to_dict(self):
        """转换为字典表示"""
        return {
            'id': self.uid,
            'conv_id': self.conv_id,
            'title': self.title,
            'content': self.content,
            'created_at': self.created_at.timestamp() if self.created_at else time.time(),
            'last_accessed': self.last_accessed.timestamp() if self.last_accessed else time.time(),
            'weight': self.weight,
            'is_permanent': self.is_permanent,
            'metadata': self.metadata
        }

class CognitiveNode(StructuredNode):
    """认知节点模型"""
    uid = UniqueIdProperty()
    name = StringProperty(required=True, index=True)
    conv_id = StringProperty(default='', index=True)
    act_lv = FloatProperty(default=1.0)
    created_at = DateTimeProperty(default=lambda: datetime.now())
    last_accessed = DateTimeProperty(default=lambda: datetime.now())
    is_permanent = BooleanProperty(default=False)
    
    # 关系定义
    memories = RelationshipFrom('Memory', 'RELATED_TO', model=NodeMemoryRelationship)
    associated_nodes = RelationshipTo('CognitiveNode', 'ASSOCIATED_WITH', model=NodeAssociation)

    class Meta:
        # (conv_id, name) 的组合应该是唯一的
        indexes = [
            {'fields': ['conv_id', 'name'], 'unique': True}
        ]
    
    def to_dict(self):
        """转换为字典表示"""
        return {
            'id': self.uid,
            'name': self.name,
            'conv_id': self.conv_id,
            'act_lv': self.act_lv,
            'created_at': self.created_at.timestamp() if self.created_at else time.time(),
            'last_accessed': self.last_accessed.timestamp() if self.last_accessed else time.time(),
            'is_permanent': self.is_permanent
        } 