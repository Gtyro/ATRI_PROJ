"""
记忆系统存储管理模块 - 负责记忆的持久化和检索

该模块实现了记忆的数据库存储、检索和管理功能。
使用Tortoise-ORM作为底层存储引擎，支持SQLite和PostgreSQL。
支持记忆实体、关联和标签。
"""

import json
import math
import time
import logging
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple

from tortoise import Tortoise, fields, run_async
from tortoise.models import Model
from tortoise.expressions import Q
from tortoise.transactions import atomic


# 定义Tortoise ORM模型
class Memory(Model):
    """记忆模型"""
    id = fields.CharField(max_length=36, primary_key=True)
    group_id = fields.CharField(max_length=16, index=True)
    topic = fields.CharField(max_length=128)
    summary = fields.TextField()
    entities = fields.TextField()  # JSON 格式存储实体列表
    start_time = fields.CharField(max_length=20)
    end_time = fields.CharField(max_length=20)
    involved_users = fields.TextField()  # JSON 格式存储参与用户
    last_accessed = fields.FloatField()
    metadata = fields.TextField()  # JSON 格式存储额外元数据
    
    class Meta:
        table = "memories"
        table_description = "存储记忆的核心表"

    def __str__(self):
        return f"{self.group_id}:{self.topic[:20]}"


class MemoryAssociation(Model):
    """记忆关联模型"""
    source = fields.ForeignKeyField('models.Memory', related_name='outgoing_associations')
    target = fields.ForeignKeyField('models.Memory', related_name='incoming_associations')
    strength = fields.FloatField(default=0.5)
    created_at = fields.FloatField()

    class Meta:
        table = "memory_associations"
        table_description = "记忆之间的关联关系"
        unique_together = (("source_id", "target_id"),)

    def __str__(self):
        return f"{self.source_id}->{self.target_id}"


class MemoryTag(Model):
    """记忆标签模型"""
    memory = fields.ForeignKeyField('models.Memory', related_name='tags')
    tag = fields.CharField(max_length=50, index=True)
    # CREATE INDEX idx_memory_tag_tag ON memory_tags (tag);

    class Meta:
        table = "memory_tags"
        table_description = "记忆的标签，用于快速检索"
        unique_together = (("memory_id", "tag"),)

    def __str__(self):
        return f"{self.memory_id}:{self.tag}"


class MessageQueueItem(Model):
    """消息队列项模型"""
    id = fields.CharField(pk=True, max_length=36)
    user_id = fields.CharField(max_length=36)
    content = fields.TextField()
    context = fields.CharField(max_length=100, null=True)
    group_id = fields.CharField(max_length=36, null=True)
    created_at = fields.FloatField(index=True)
    processed = fields.BooleanField(default=False)

    class Meta:
        table = "message_queue"
        table_description = "消息处理队列"

    def __str__(self):
        return f"{self.user_id}:{self.content[:20]}"


class StorageManager:
    """负责记忆数据的持久化存储与检索"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.is_initialized = False
        
    async def initialize(self, use_postgres: bool = False, postgres_config: Dict = None) -> None:
        """初始化数据库连接"""
        if self.is_initialized:
            return
            
        # 配置数据库URL
        if use_postgres and postgres_config:
            # PostgreSQL配置
            user = postgres_config.get('user', 'postgres')
            password = postgres_config.get('password', '')
            host = postgres_config.get('host', 'localhost')
            port = postgres_config.get('port', 5432)
            database = postgres_config.get('database', 'memories')
            
            db_url = f"postgres://{user}:{password}@{host}:{port}/{database}"
        else:
            # SQLite配置
            db_url = f"sqlite://{self.db_path}"
        
        # 初始化Tortoise ORM
        await Tortoise.init(
            db_url=db_url,
            modules={'models': ['plugins.memory.storage']}
        )
        
        # 创建表结构
        await Tortoise.generate_schemas()
        self.is_initialized = True
        logging.info(f"数据库初始化完成: {db_url}")
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self.is_initialized:
            await Tortoise.close_connections()
            self.is_initialized = False
            logging.info("数据库连接已关闭")
    
    @atomic()
    async def add_memory(self, memory_data: Dict) -> str:
        """添加一条记忆"""
        try:
            # 准备数据
            memory_id = memory_data.get("id") or str(uuid.uuid4())
            
            # 创建记忆对象
            memory = await Memory.create(
                id=memory_id,
                user_id=memory_data["user_id"],
                content=memory_data["content"],
                context=memory_data.get("context", "default"),
                type=memory_data.get("type", "general"),
                created_at=memory_data.get("created_at", time.time()),
                last_accessed=memory_data.get("last_accessed", time.time()),
                weight=memory_data.get("weight", 1.0),
                emotion_score=memory_data.get("emotion_score", 0),
                metadata=json.dumps(memory_data.get("metadata", {}), ensure_ascii=False)
            )
            
            # 添加标签
            tags = memory_data.get("tags", [])
            for tag in tags:
                await MemoryTag.create(memory_id=memory_id, tag=tag)
            
            return memory_id
            
        except Exception as e:
            logging.error(f"添加记忆失败: {e}")
            raise
    
    async def get_memory(self, memory_id: str) -> Optional[Dict]:
        """获取单条记忆"""
        try:
            # 查询记忆
            memory = await Memory.filter(id=memory_id).first()
            if not memory:
                return None
                
            # 转换为字典
            result = {
                "id": memory.id,
                "user_id": memory.user_id,
                "content": memory.content,
                "context": memory.context,
                "type": memory.type,
                "created_at": memory.created_at,
                "last_accessed": memory.last_accessed,
                "weight": memory.weight,
                "emotion_score": memory.emotion_score,
                "metadata": memory.metadata,
            }
            
            # 获取标签
            tags = await MemoryTag.filter(memory_id=memory_id).values_list("tag", flat=True)
            result["tags"] = tags
            
            return result
        except Exception as e:
            logging.error(f"获取记忆失败: {e}")
            return None
    
    async def get_user_memories(self, user_id: str, limit: int = 20) -> List[Dict]:
        """获取指定用户的记忆"""
        try:
            # 查询记忆
            memories = await Memory.filter(user_id=user_id).order_by("-created_at").limit(limit)
            
            results = []
            for memory in memories:
                # 转换为字典
                memory_dict = {
                    "id": memory.id,
                    "user_id": memory.user_id,
                    "content": memory.content,
                    "context": memory.context,
                    "type": memory.type,
                    "created_at": memory.created_at,
                    "last_accessed": memory.last_accessed,
                    "weight": memory.weight,
                    "emotion_score": memory.emotion_score,
                    "metadata": memory.metadata,
                }
                
                # 获取标签
                tags = await MemoryTag.filter(memory_id=memory.id).values_list("tag", flat=True)
                memory_dict["tags"] = tags
                
                results.append(memory_dict)
                
            return results
        except Exception as e:
            logging.error(f"获取用户记忆失败: {e}")
            return []
    
    async def get_context_memories(self, context: str, limit: int = 10) -> List[Dict]:
        """获取指定上下文的记忆"""
        try:
            # 查询记忆
            memories = await Memory.filter(context=context).order_by("-created_at").limit(limit)
            
            results = []
            for memory in memories:
                # 转换为字典
                memory_dict = {
                    "id": memory.id,
                    "user_id": memory.user_id,
                    "content": memory.content,
                    "context": memory.context,
                    "type": memory.type,
                    "created_at": memory.created_at,
                    "last_accessed": memory.last_accessed,
                    "weight": memory.weight,
                    "emotion_score": memory.emotion_score,
                    "metadata": memory.metadata,
                }
                
                # 获取标签
                tags = await MemoryTag.filter(memory_id=memory.id).values_list("tag", flat=True)
                memory_dict["tags"] = tags
                
                results.append(memory_dict)
                
            return results
        except Exception as e:
            logging.error(f"获取上下文记忆失败: {e}")
            return []
    
    async def add_to_queue(self, queue_item: Dict) -> str:
        """添加消息到队列"""
        try:
            # 准备数据
            item_id = queue_item.get("id") or str(uuid.uuid4())
            
            # 创建队列项
            await MessageQueueItem.create(
                id=item_id,
                user_id=queue_item["user_id"],
                content=queue_item["content"],
                context=queue_item.get("context"),
                group_id=queue_item.get("group_id"),
                created_at=queue_item.get("created_at", time.time()),
                processed=queue_item.get("processed", False),
            )
            
            return item_id
        except Exception as e:
            logging.error(f"添加队列项失败: {e}")
            raise
    
    async def get_queue_items(self, limit: int = 100) -> List[Dict]:
        """获取队列中的消息"""
        try:
            # 按创建时间排序
            items = await MessageQueueItem.filter(processed=False).order_by("created_at").limit(limit)
            
            # 转换为字典列表
            return [
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "content": item.content,
                    "context": item.context,
                    "group_id": item.group_id,
                    "created_at": item.created_at,
                }
                for item in items
            ]
        except Exception as e:
            logging.error(f"获取队列项失败: {e}")
            return []
    
    async def get_group_queue_items(self, group_id: str) -> List[Dict]:
        """获取特定群组的队列消息
        
        Args:
            group_id: 群组ID或用户ID
            limit: 最大获取条数
            
        Returns:
            该群组/用户的队列消息列表
        """
        try:
            # 获取特定群组的消息，按创建时间排序
            items = await MessageQueueItem.filter(
                processed=False, 
                group_id=group_id
            ).order_by("created_at")
            
            # 转换为字典列表
            return [
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "content": item.content,
                    "context": item.context,
                    "group_id": item.group_id,
                    "created_at": item.created_at
                }
                for item in items
            ]
        except Exception as e:
            logging.error(f"获取群组队列项失败: {e}")
            return []
    
    async def remove_from_queue(self, item_id: str) -> bool:
        """从队列中移除消息"""
        try:
            deleted_count = await MessageQueueItem.filter(id=item_id).delete()
            return deleted_count > 0
        except Exception as e:
            logging.error(f"移除队列项失败: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        try:
            # 获取总数
            total = await MessageQueueItem.filter(processed=False).count()
            
            return {
                "total": total
            }
        except Exception as e:
            logging.error(f"获取队列统计失败: {e}")
            return {"total": 0}
        
    async def _update_cooccurrences(self, entities: List[str], context: str):
        """根据Hebbian规则更新共现关系（纯数据库方案）"""
        current_time = time.time()
        time_window = 300  # 5分钟短期记忆窗口
        
        # 同消息共现更新
        for i in range(len(entities)):
            for j in range(i+1, len(entities)):
                await self._update_pair(entities[i], entities[j], 0.3, current_time, context)

        # 跨消息共现更新：查询最近5分钟的记忆
        recent_memories = await Memory.filter(
            created_at__gte=current_time - time_window
        ).prefetch_related('tags')
        
        # 提取近期实体（去重）
        recent_entities = set()
        for memory in recent_memories:
            recent_entities.update([tag.tag for tag in memory.tags])
        
        # 计算跨消息共现
        for entity in entities:
            # 查找近期出现过的关联实体
            for cached_entity in recent_entities:
                if cached_entity == entity:
                    continue
                
                # 计算共现次数
                cooccur_count = await MemoryTag.filter(
                    Q(memory__created_at__gte=current_time - time_window) &
                    (Q(tag=entity) | Q(tag=cached_entity))
                ).group_by('memory_id').count()
                
                if cooccur_count > 0:
                    strength = 0.5 * (1 + math.log(cooccur_count + 1))
                    await self._update_pair(entity, cached_entity, strength, current_time, context)

    async def _update_pair(self, entity_a: str, entity_b: str, delta: float, timestamp: float, context: str):
        """优化后的关联更新方法"""
        # 查找双向关联
        assoc = await MemoryAssociation.filter(
            Q(source=entity_a, target=entity_b) | 
            Q(source=entity_b, target=entity_a)
        ).first()

        if assoc:
            # 统一更新两个方向的关联
            new_strength = min(assoc.strength + delta, 5.0)
            await MemoryAssociation.filter(
                Q(source=entity_a, target=entity_b) |
                Q(source=entity_b, target=entity_a)
            ).update(
                strength=new_strength,
                created_at=timestamp
            )
        else:
            # 创建双向关联（使用bulk_create提高效率）
            await MemoryAssociation.bulk_create([
                MemoryAssociation(
                    source=entity_a,
                    target=entity_b,
                    strength=1.0 + delta,
                    created_at=timestamp
                ),
                MemoryAssociation(
                    source=entity_b,
                    target=entity_a,
                    strength=1.0 + delta,
                    created_at=timestamp
                )
            ])

    @atomic()
    async def add_conversation_topic(self, group_id: str, topic_data: Dict) -> str:
        """添加一个会话话题"""
        try:
            # 生成话题ID
            topic_id = topic_data.get("id") or str(uuid.uuid4())
            
            # 创建话题记录
            await Memory.create(
                id=topic_id,
                group_id=group_id,
                topic=topic_data.get("topic", "未命名话题"),
                summary=topic_data.get("summary", ""),
                entities=json.dumps(topic_data.get("entities", []), ensure_ascii=False),
                start_time=topic_data.get("start_time", ""),
                end_time=topic_data.get("end_time", ""),
                involved_users=json.dumps(topic_data.get("involved_users", []), ensure_ascii=False),
                last_accessed=topic_data.get("last_accessed", time.time()),
                metadata=json.dumps(topic_data.get("metadata", {}), ensure_ascii=False)
            )
            
            return topic_id
            
        except Exception as e:
            logging.error(f"添加会话话题失败: {e}")
            raise