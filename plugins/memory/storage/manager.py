


from datetime import datetime
from typing import List, Dict, Optional, Any
import json
import time
import uuid
import logging

from tortoise import Tortoise
from tortoise.expressions import Q
from tortoise.transactions import atomic

from .models import Memory, MemoryEntity, MessageQueueItem, MemoryAssociation



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
                conv_id=memory_data.get("conv_id", "default"),
                topic=memory_data.get("topic", ""),
                summary=memory_data.get("summary", ""),
                entities=json.dumps(memory_data.get("entities", []), ensure_ascii=False),
                start_time=memory_data.get("start_time", ""),
                end_time=memory_data.get("end_time", ""),
                involved_users=json.dumps(memory_data.get("involved_users", []), ensure_ascii=False),
                created_at=memory_data.get("created_at", time.time()),
                last_accessed=memory_data.get("last_accessed", time.time()),
                weight=memory_data.get("weight", 1.0),
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
                "conv_id": memory.conv_id,
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
                    "conv_id": memory.conv_id,
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
    
    async def get_conv_memories(self, conv_id: str, limit: int = 10) -> List[Dict]:
        """获取指定上下文的记忆"""
        try:
            # 查询记忆
            memories = await Memory.filter(conv_id=conv_id).order_by("-created_at").limit(limit)
            
            results = []
            for memory in memories:
                # 转换为字典
                memory_dict = {
                    "id": memory.id,
                    "user_id": memory.user_id,
                    "content": memory.content,
                    "conv_id": memory.conv_id,
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
    
    async def add_to_queue(self, queue_item_dict: Dict) -> str:
        """添加消息到队列"""
        try:
            # 准备数据
            item_id = str(uuid.uuid4())

            # 对过长的内容只保留头尾
            if len(queue_item_dict["content"]) > 200:
                queue_item_dict["content"] = queue_item_dict["content"][:100] + "..." + queue_item_dict["content"][-100:]
            
            queue_item_dict["metadata"] = json.dumps(queue_item_dict['metadata'], ensure_ascii=False)
            if "is_direct" in queue_item_dict:
                queue_item_dict["metadata"]["is_direct"] = queue_item_dict["is_direct"]

            # 创建队列项
            await MessageQueueItem.create(**queue_item_dict)
            
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
                    "conv_id": item.conv_id,
                    "created_at": item.created_at,
                    "is_direct": item.is_direct,
                    "is_me": item.is_me,
                }
                for item in items
            ]
        except Exception as e:
            logging.error(f"获取队列项失败: {e}")
            return []

    async def get_conv_queue_items(self, conv_id: str, limit: int = 100, include_processed: bool = False) -> List[Dict]:
        """获取特定对话的队列消息
        
        Args:
            conv_id: 对话ID
            limit: 最大返回条数
            include_processed: 是否包含已处理的消息
            
        Returns:
            该对话的队列消息列表
        """
        try:
            # 构建过滤条件
            query = Q(conv_id=conv_id)
            if not include_processed:
                query &= Q(processed=False)
                
            # 获取特定对话的消息，按创建时间排序，限制数量
            items = await MessageQueueItem.filter(query).order_by("created_at").limit(limit)
            
            # 转换为字典列表
            return [
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "user_name": item.user_name,
                    "content": item.content,
                    "conv_id": item.conv_id,
                    "created_at": item.created_at,
                    "is_direct": item.is_direct,
                    "is_me": item.is_me,
                    "processed": item.processed,
                }
                for item in items
            ]
        except Exception as e:
            logging.error(f"获取对话队列项失败: {e}")
            return []
    
    async def mark_as_processed(self, item_ids: List[str]) -> int:
        """将消息标记为已处理（而不是删除）
        
        Args:
            item_ids: 要标记的消息ID列表
            
        Returns:
            成功标记的消息数量
        """
        if not item_ids:
            return 0
            
        try:
            # 使用 id__in 更高效地批量更新
            updated_count = await MessageQueueItem.filter(id__in=item_ids).update(processed=True)
            logging.debug(f"批量标记队列消息为已处理，共标记 {updated_count} 条")
            return updated_count
        except Exception as e:
            logging.error(f"批量标记队列项为已处理失败: {e}")
            return 0
            
    async def remove_old_processed_messages(self, conv_id: str, keep_count: int = 20) -> int:
        """删除已处理的旧消息，保留最新的一定数量
        
        Args:
            conv_id: 对话ID
            keep_count: 保留的最新消息数量（不限于已处理消息）
            
        Returns:
            删除的消息数量
        """
        try:
            # 获取该对话所有消息，按时间倒序排序，找出时间截止点
            recent_messages = await MessageQueueItem.filter(
                conv_id=conv_id
            ).order_by("-created_at").limit(keep_count).values("id", "created_at", "processed")
            
            if not recent_messages:
                return 0  # 没有消息，不需要删除
                
            # 如果消息数少于保留数，不需要删除
            if len(recent_messages) < keep_count:
                logging.debug(f"对话 {conv_id} 的消息总数少于 {keep_count}，不需要删除")
                return 0
            
            # 获取时间截止点（第keep_count条消息的时间戳）
            cutoff_time = recent_messages[-1]["created_at"]
            
            # 删除早于截止时间且已处理的消息
            deleted_count = await MessageQueueItem.filter(
                conv_id=conv_id,
                processed=True,
                created_at__lt=cutoff_time
            ).delete()
            
            if deleted_count > 0:
                logging.info(f"为对话 {conv_id} 删除了 {deleted_count} 条早于 {datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d %H:%M:%S')} 的已处理消息")
            
            return deleted_count
        except Exception as e:
            logging.error(f"删除旧的已处理消息失败: {e}")
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
            
    async def remove_from_queue(self, item_ids: List[str]) -> int:
        """批量从队列中移除消息（完全删除）
        
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

    async def _update_cooccurrences(self, entities: List[str], conv_id: str):
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
                        await self._update_pair(entities[i], entities[j], 0.3, current_time, conv_id)
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
                            await self._update_pair(entity, cached_entity, strength, current_time, conv_id)
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
    
    async def _update_pair(self, entity_a: str, entity_b: str, delta: float, timestamp: float, conv_id: str):
        """优化后的关联更新方法，基于唯一实体名称

        Args:
            entity_a: 实体A的名称
            entity_b: 实体B的名称
            delta: 关联强度增量
            timestamp: 时间戳
            conv_id: 对话ID
        """
        try:
            # 系统记忆ID，用于存储没有归属的实体
            system_memory_id = f"system_{conv_id}"
            
            # 查找或创建系统记忆
            system_memory = await Memory.filter(id=system_memory_id).first()
            if not system_memory:
                system_memory = await Memory.create(
                    id=system_memory_id,
                    conv_id=conv_id,
                    topic="系统记忆",
                    summary="用于存储系统生成的实体关联",
                    entities="[]",
                    start_time="",
                    end_time="",
                    involved_users="[]",
                    created_at=timestamp,
                    last_accessed=timestamp,
                    weight=1.0,
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
    async def add_conversation_topic(self, conv_id: str, topic_data: Dict) -> str:
        """添加一个对话话题"""
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
                conv_id=conv_id,
                topic=topic_data.get("topic", "未命名话题"),
                summary=topic_data.get("summary", ""),
                entities=json.dumps(topic_data.get("entities", []), ensure_ascii=False),
                start_time=topic_data.get("start_time", ""),
                end_time=topic_data.get("end_time", ""),
                involved_users=json.dumps(topic_data.get("involved_users", []), ensure_ascii=False),
                created_at=current_time,
                last_accessed=current_time,
                weight=1.0,
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
                await self._update_cooccurrences(entities, conv_id)
                
            return topic_id
            
        except Exception as e:
            logging.error(f"添加对话话题失败: {e}")
            raise

    async def get_message_by_seq_id(self, conv_id: str, seq_id: int) -> Dict:
        """根据消息序号ID获取消息内容
        
        Args:
            conv_id: 对话ID
            seq_id: 序号ID（内部使用的顺序ID）
            
        Returns:
            消息信息字典，如果未找到则返回空字典
        """
        try:
            # 获取指定群组的所有消息 - 包括未处理和已处理消息
            # 这确保即使部分消息被删除，序号仍然有效（基于创建时间排序）
            messages = await MessageQueueItem.filter(
                conv_id=conv_id
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
                logging.warning(f"无效的消息序号ID: {seq_id}，对话 {conv_id} 中只有 {len(messages)} 条消息")
                return {}
        except Exception as e:
            logging.error(f"获取消息内容失败: {e}")
            return {}

    async def get_distinct_conv_ids(self) -> List[str]:
        """获取队列中所有不同的对话ID
        
        Returns:
            不同对话ID的列表
        """
        try:
            # 查询所有未处理消息的不同对话ID
            query = "SELECT DISTINCT conv_id FROM message_queue WHERE processed = 0"
            conn = Tortoise.get_connection("default")
            results = await conn.execute_query_dict(query)
            
            # 提取对话ID
            conv_ids = [item["conv_id"] for item in results if item["conv_id"]]
            
            return conv_ids
        except Exception as e:
            logging.error(f"获取不同对话ID失败: {e}")
            return []