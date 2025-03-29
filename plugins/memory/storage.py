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
    context = fields.CharField(max_length=20, index=True) # group_id or private_id
    topic = fields.CharField(max_length=128)
    summary = fields.TextField()
    entities = fields.TextField()  # JSON 格式存储实体列表
    start_time = fields.CharField(max_length=20)
    end_time = fields.CharField(max_length=20)
    involved_users = fields.TextField()  # JSON 格式存储参与用户
    created_at = fields.FloatField()
    last_accessed = fields.FloatField()
    metadata = fields.TextField()  # JSON 格式存储额外元数据
    
    class Meta:
        table = "memories"
        table_description = "存储记忆的核心表"

    def __str__(self):
        return f"{self.context}:{self.topic[:20]}"


class MemoryEntity(Model):
    """记忆实体模型 - 表示记忆中的概念、对象或实体"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True, index=True)  # 实体名称，全局唯一
    memory = fields.ForeignKeyField('models.Memory', related_name='entities')
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
    source_name = fields.CharField(max_length=100, null=True)  # 源实体名称，便于直接查看
    target_name = fields.CharField(max_length=100, null=True)  # 目标实体名称，便于直接查看
    strength = fields.FloatField(default=0.5)  # 关联强度
    created_at = fields.FloatField()  # 创建时间
    updated_at = fields.FloatField()  # 最后更新时间

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
    content = fields.TextField()
    is_tome = fields.BooleanField(default=False)  # 消息是否是发给机器人的
    is_me = fields.BooleanField(default=False)    # 消息是否是机器人发的
    context = fields.CharField(max_length=100, null=True)
    group_id = fields.CharField(max_length=36, null=True)
    created_at = fields.FloatField(index=True)
    processed = fields.BooleanField(default=False)
    metadata = fields.TextField(default="{}")  # 存储额外元数据，如回复关系等

    class Meta:
        table = "message_queue"
        table_description = "消息处理队列"

    def __str__(self):
        return f"{self.user_id}:{self.user_name}:{self.content[:20]}"


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
                context=memory_data.get("context", "default"),
                topic=memory_data.get("topic", ""),
                summary=memory_data.get("summary", ""),
                entities=json.dumps(memory_data.get("entities", []), ensure_ascii=False),
                start_time=memory_data.get("start_time", ""),
                end_time=memory_data.get("end_time", ""),
                involved_users=json.dumps(memory_data.get("involved_users", []), ensure_ascii=False),
                created_at=memory_data.get("created_at", time.time()),
                last_accessed=memory_data.get("last_accessed", time.time()),
                metadata=json.dumps(memory_data.get("metadata", {}), ensure_ascii=False)
            )
            
            # 添加实体
            entities = memory_data.get("tags", [])
            for entity_name in entities:
                if not entity_name:
                    continue
                    
                # 查找或创建实体
                entity = await MemoryEntity.filter(name=entity_name).first()
                if not entity:
                    entity = await MemoryEntity.create(
                        name=entity_name,
                        memory_id=memory_id,
                        created_at=time.time()
                    )
                
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
            
            # 获取实体
            entities = await MemoryEntity.filter(memory_id=memory_id).values_list("name", flat=True)
            result["entities"] = list(entities)
            
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
                
                # 获取实体
                entities = await MemoryEntity.filter(memory_id=memory.id).values_list("name", flat=True)
                memory_dict["entities"] = list(entities)
                
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
                
                # 获取实体
                entities = await MemoryEntity.filter(memory_id=memory.id).values_list("name", flat=True)
                memory_dict["entities"] = list(entities)
                
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

            # 对过长的内容只保留头尾
            if len(queue_item["content"]) > 200:
                queue_item["content"] = queue_item["content"][:100] + "..." + queue_item["content"][-100:]
            
            # 创建队列项
            await MessageQueueItem.create(
                id=item_id,
                user_id=queue_item["user_id"],
                user_name=queue_item["user_name"],
                content=queue_item["content"],
                context=queue_item.get("context"),
                group_id=queue_item.get("group_id"),
                created_at=queue_item.get("created_at", time.time()),
                processed=queue_item.get("processed", False),
                is_tome=queue_item.get("is_tome", False),
                is_me=queue_item.get("is_me", False),
                metadata=json.dumps(queue_item.get("metadata", {}), ensure_ascii=False)
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
                    "user_name": item.user_name,
                    "content": item.content,
                    "context": item.context,
                    "group_id": item.group_id,
                    "created_at": item.created_at,
                    "is_tome": item.is_tome,
                    "is_me": item.is_me,
                }
                for item in items
            ]
        except Exception as e:
            logging.error(f"获取队列项失败: {e}")
            return []
    
    async def get_group_queue_items(self, group_id: str, limit: int = 100) -> List[Dict]:
        """获取特定群组的队列消息
        
        Args:
            group_id: 群组ID或用户ID
            limit: 最大返回条数
            
        Returns:
            该群组/用户的队列消息列表
        """
        try:
            # 获取特定群组的消息，按创建时间排序，限制数量
            items = await MessageQueueItem.filter(
                processed=False, 
                group_id=group_id
            ).order_by("created_at").limit(limit)
            
            # 转换为字典列表
            return [
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "user_name": item.user_name,
                    "content": item.content,
                    "context": item.context,
                    "group_id": item.group_id,
                    "created_at": item.created_at,
                    "is_tome": item.is_tome,
                    "is_me": item.is_me,
                }
                for item in items
            ]
        except Exception as e:
            logging.error(f"获取群组队列项失败: {e}")
            return []
    
    async def remove_from_queue(self, item_ids: List[str]) -> int:
        """批量从队列中移除消息
        
        Args:
            item_ids: 要删除的消息ID列表
            
        Returns:
            成功删除的消息数量
        """
        if not item_ids:
            return 0
            
        try:
            # 使用 id__in 更高效地批量删除
            deleted_count = await MessageQueueItem.filter(id__in=item_ids).delete()
            logging.debug(f"批量删除队列消息成功，共删除 {deleted_count} 条")
            return deleted_count
        except Exception as e:
            logging.error(f"批量移除队列项失败: {e}")
            return 0
    
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
        if not entities or len(entities) < 1:
            logging.debug(f"实体列表为空，跳过更新共现关系")
            return
            
        # 过滤掉空字符串和None
        entities = [e for e in entities if e and isinstance(e, str)]
        if not entities:
            logging.debug(f"过滤后实体列表为空，跳过更新共现关系")
            return
            
        # 记录处理开始
        logging.info(f"开始更新实体共现关系，共{len(entities)}个实体: {entities}")
        
        current_time = time.time()
        time_window = 300  # 5分钟短期记忆窗口
        success_count = 0
        
        try:
            # 同消息共现更新
            for i in range(len(entities)):
                for j in range(i+1, len(entities)):
                    try:
                        await self._update_pair(entities[i], entities[j], 0.3, current_time, context)
                        success_count += 1
                    except Exception as e:
                        logging.error(f"更新实体对失败 ({entities[i]}-{entities[j]}): {e}")
                        # 继续处理其他实体对
                        continue

            # 跨消息共现更新：查询最近5分钟的记忆
            try:
                # 获取最近的实体而不是记忆
                recent_entities = await MemoryEntity.filter(
                    created_at__gte=current_time - time_window
                ).distinct().values_list('name', flat=True)
                
                # 过滤掉当前消息中的实体，避免重复处理
                recent_entities = [e for e in recent_entities if e not in entities]
                
                # 计算跨消息共现
                for entity in entities:
                    for cached_entity in recent_entities:
                        if not entity or not cached_entity or cached_entity == entity:
                            continue
                        
                        try:
                            # 简化共现计算逻辑
                            strength = 0.2  # 跨消息共现强度较低
                            await self._update_pair(entity, cached_entity, strength, current_time, context)
                            success_count += 1
                        except Exception as e:
                            logging.error(f"更新跨消息实体对失败 ({entity}-{cached_entity}): {e}")
                            # 继续处理其他实体对
                            continue
            except Exception as e:
                logging.error(f"获取最近实体失败: {e}")
                # 跳过跨消息更新，但继续函数执行
            
            # 记录处理结果
            logging.info(f"实体关联更新完成，成功处理{success_count}个实体对")
            
        except Exception as e:
            logging.error(f"更新实体共现关系失败: {e}")
            # 不抛出异常，让调用者继续执行
    
    async def _update_pair(self, entity_a: str, entity_b: str, delta: float, timestamp: float, context: str):
        """优化后的关联更新方法，基于唯一实体名称

        Args:
            entity_a: 实体A的名称
            entity_b: 实体B的名称
            delta: 关联强度增量
            timestamp: 时间戳
            context: 上下文
        """
        try:
            # 系统记忆ID，用于存储没有归属的实体
            system_memory_id = f"system_{context}"
            
            # 查找或创建系统记忆
            system_memory = await Memory.filter(id=system_memory_id).first()
            if not system_memory:
                system_memory = await Memory.create(
                    id=system_memory_id,
                    context=context,
                    topic="系统记忆",
                    summary="用于存储系统生成的实体关联",
                    entities="[]",
                    start_time="",
                    end_time="",
                    involved_users="[]",
                    created_at=timestamp,
                    last_accessed=timestamp,
                    metadata="{}"
                )
                
            # 查找或创建实体A
            entity_a_obj = await MemoryEntity.filter(name=entity_a).first()
            if not entity_a_obj:
                entity_a_obj = await MemoryEntity.create(
                    name=entity_a,
                    memory_id=system_memory_id,
                    created_at=timestamp
                )
                
            # 查找或创建实体B
            entity_b_obj = await MemoryEntity.filter(name=entity_b).first()
            if not entity_b_obj:
                entity_b_obj = await MemoryEntity.create(
                    name=entity_b,
                    memory_id=system_memory_id,
                    created_at=timestamp
                )
                
            # 查找已有关联
            assoc = await MemoryAssociation.filter(
                (Q(source_id=entity_a_obj.id) & Q(target_id=entity_b_obj.id)) | 
                (Q(source_id=entity_b_obj.id) & Q(target_id=entity_a_obj.id))
            ).first()

            if assoc:
                # 更新关联强度和时间戳
                new_strength = min(assoc.strength + delta, 5.0)
                await MemoryAssociation.filter(id=assoc.id).update(
                    strength=new_strength,
                    updated_at=timestamp
                )
            else:
                # 创建双向关联
                await MemoryAssociation.bulk_create([
                    MemoryAssociation(
                        source_id=entity_a_obj.id,
                        target_id=entity_b_obj.id,
                        source_name=entity_a,
                        target_name=entity_b,
                        strength=1.0 + delta,
                        created_at=timestamp,
                        updated_at=timestamp
                    ),
                    MemoryAssociation(
                        source_id=entity_b_obj.id,
                        target_id=entity_a_obj.id,
                        source_name=entity_b,
                        target_name=entity_a,
                        strength=1.0 + delta,
                        created_at=timestamp,
                        updated_at=timestamp
                    )
                ])
                logging.debug(f"创建了实体关联: {entity_a} <-> {entity_b}")
        except Exception as e:
            logging.error(f"更新实体关联失败 ({entity_a}-{entity_b}): {e}")
            raise

    @atomic()
    async def add_conversation_topic(self, context: str, topic_data: Dict) -> str:
        """添加一个会话话题"""
        try:
            # 生成话题ID
            topic_id = topic_data.get("id") or str(uuid.uuid4())
            
            # 准备元数据，包含更多可能变动的字段
            metadata = topic_data.get("metadata", {})
            
            # 将不稳定字段或未来可能删除的字段放入metadata
            for field in ["continuation_probability", "emotion_intensity", "emotion_polarity", 
                         "relevance_score", "confidence", "priority"]:
                if field in topic_data:
                    metadata[field] = topic_data[field]
            
            # 当前时间戳
            current_time = topic_data.get("created_at", time.time())
            
            # 创建话题记忆记录
            memory = await Memory.create(
                id=topic_id,
                context=context,
                topic=topic_data.get("topic", "未命名话题"),
                summary=topic_data.get("summary", ""),
                entities=json.dumps(topic_data.get("entities", []), ensure_ascii=False),
                start_time=topic_data.get("start_time", ""),
                end_time=topic_data.get("end_time", ""),
                involved_users=json.dumps(topic_data.get("involved_users", []), ensure_ascii=False),
                created_at=current_time,
                last_accessed=current_time,
                metadata=json.dumps(metadata, ensure_ascii=False)
            )
            
            # 创建实体记录，用于快速检索
            entities = topic_data.get("entities", [])
            if entities:
                # 为每个实体查找或创建记录
                for entity_name in entities:
                    if not entity_name:
                        continue
                        
                    # 查找或创建实体记录
                    entity = await MemoryEntity.filter(name=entity_name).first()
                    if not entity:
                        entity = await MemoryEntity.create(
                            name=entity_name,
                            memory_id=topic_id,
                            created_at=current_time
                        )
                
                # 基于Hebbian理论更新实体关联
                await self._update_cooccurrences(entities, context)
                
            return topic_id
            
        except Exception as e:
            logging.error(f"添加会话话题失败: {e}")
            raise

    async def get_message_by_seq_id(self, group_id: str, seq_id: int) -> Dict:
        """根据消息序号ID获取消息内容
        
        Args:
            group_id: 群组ID
            seq_id: 序号ID（内部使用的顺序ID）
            
        Returns:
            消息信息字典，如果未找到则返回空字典
        """
        try:
            # 获取指定群组的所有消息 - 包括未处理和已处理消息
            # 这确保即使部分消息被删除，序号仍然有效（基于创建时间排序）
            messages = await MessageQueueItem.filter(
                group_id=group_id
            ).order_by('created_at').limit(500).values()
            
            # 确保序号ID有效
            if 1 <= seq_id <= len(messages):
                # 消息序号是基于1的索引，而列表是基于0的索引
                message = messages[seq_id - 1]
                
                # 处理metadata
                if 'metadata' in message and isinstance(message['metadata'], str):
                    try:
                        message['metadata'] = json.loads(message['metadata'])
                    except:
                        message['metadata'] = {}
                
                return message
            else:
                logging.warning(f"无效的消息序号ID: {seq_id}，群组 {group_id} 中只有 {len(messages)} 条消息")
                return {}
        except Exception as e:
            logging.error(f"获取消息内容失败: {e}")
            return {}

    async def get_distinct_group_ids(self) -> List[str]:
        """获取队列中所有不同的群组ID
        
        Returns:
            不同群组ID的列表
        """
        try:
            # 查询所有未处理消息的不同群组ID
            query = "SELECT DISTINCT group_id FROM message_queue WHERE processed = 0"
            conn = Tortoise.get_connection("default")
            results = await conn.execute_query_dict(query)
            
            # 提取群组ID
            group_ids = [item["group_id"] for item in results if item["group_id"]]
            
            return group_ids
        except Exception as e:
            logging.error(f"获取不同群组ID失败: {e}")
            return []