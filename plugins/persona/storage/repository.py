import logging
import time
from typing import Dict, List, Optional, Any
from tortoise import Tortoise
from tortoise.exceptions import OperationalError

from .models import MessageQueue, Memory, CognitiveNode, Association

class Repository:
    """统一的存储仓库，负责与数据库的所有交互"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化仓库
        
        Args:
            config: 配置字典，包含数据库配置
        """
        self.config = config
        self.db_url = self._get_db_url()
        self.is_initialized = False
        logging.info("存储仓库已创建，等待初始化")
    
    def _get_db_url(self) -> str:
        """根据配置获取数据库连接URL"""
        if self.config.get("use_postgres", False):
            pg_config = self.config.get("postgres_config", {})
            return (
                f"postgres://{pg_config.get('user', 'postgres')}:"
                f"{pg_config.get('password', 'postgres')}@"
                f"{pg_config.get('host', 'localhost')}:"
                f"{pg_config.get('port', 5432)}/"
                f"{pg_config.get('database', 'postgres')}"
            )
        else:
            db_path = self.config.get("db_path", "data/persona.db")
            return f"sqlite://{db_path}"
    
    async def initialize(self) -> None:
        """初始化数据库连接和模型"""
        try:
            await Tortoise.init(
                db_url=self.db_url,
                modules={"models": ["plugins.persona.storage.models", "plugins.models"]} # 很不好的写法，后期需要重构
            )
            await Tortoise.generate_schemas()
            self.is_initialized = True
            logging.info(f"数据库已初始化: {self.db_url}")
        except Exception as e:
            logging.error(f"数据库初始化失败: {e}")
            raise RuntimeError(f"数据库初始化失败: {e}")
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self.is_initialized:
            await Tortoise.close_connections()
            self.is_initialized = False
            logging.info("数据库连接已关闭")
    
    # === 消息队列相关操作 ===
    
    async def add_message(self, message_data: Dict) -> MessageQueue:
        """添加消息到队列"""
        message = await MessageQueue.create(**message_data)
        return message
    
    async def get_messages(self, conv_id: str, processed: Optional[bool] = None, limit: int = 20) -> List[Dict]:
        """获取指定会话的消息"""
        if processed is None:
            messages = await MessageQueue.filter(conv_id=conv_id).order_by("created_at").limit(limit).all()
        else:
            messages = await MessageQueue.filter(
                conv_id=conv_id,
                is_processed=processed
            ).order_by("created_at").limit(limit).all()
        return [msg.to_dict() for msg in messages]
    
    async def mark_messages_processed(self, message_ids: List[int]) -> int:
        """标记消息为已处理"""
            
        update_values = {
            "is_processed": True
        }
        
        try:
            # 批量更新时会自动处理None值
            return await MessageQueue.filter(id__in=message_ids).update(**update_values)
        except Exception as e:
            logging.error(f"批量标记消息失败: {e}")
            return 0
    
    async def remove_old_messages(self, conv_id: str, keep_count: int = 40) -> int:
        """移除旧的已处理消息，基于未处理消息的数量动态调整保留数量
        
        假如未处理的消息有m条，已处理的消息有n条:
        若m>=40，则移除所有n条已处理消息
        若m<40，则移除n-(40-m)条已处理消息
        """
        # 获取未处理消息数量 m
        unprocessed_count = await MessageQueue.filter(conv_id=conv_id, is_processed=False).count()
        
        # 获取已处理消息数量 n
        processed_count = await MessageQueue.filter(conv_id=conv_id, is_processed=True).count()
        
        # 根据规则确定要保留的已处理消息数量
        messages_to_keep = 0
        if unprocessed_count >= keep_count:
            # 如果未处理消息已经达到或超过keep_count，则删除所有已处理消息
            messages_to_keep = 0
        else:
            # 否则保留(keep_count-unprocessed_count)条已处理消息
            messages_to_keep = keep_count - unprocessed_count
        
        # 如果已处理消息数量小于等于需要保留的数量，则不需要删除
        if processed_count <= messages_to_keep:
            return 0
            
        # 计算需要删除的消息数量
        to_delete = processed_count - messages_to_keep
        
        # 获取要删除的消息（按创建时间排序，删除最早的）
        messages = await MessageQueue.filter(
            conv_id=conv_id, 
            is_processed=True
        ).order_by("created_at").limit(to_delete).all()
        
        # 执行删除
        deleted = 0
        for msg in messages:
            await msg.delete()
            deleted += 1
        logging.info(f"移除旧的已处理消息: {deleted} 条，保留: {messages_to_keep} 条")
        
        return deleted
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        total = await MessageQueue.all().count()
        unprocessed = await MessageQueue.filter(is_processed=False).count()
        conv_counts = {}
        
        # 获取各会话未处理消息数量
        for conv in await MessageQueue.filter(is_processed=False).distinct().values("conv_id"):
            conv_id = conv["conv_id"]
            count = await MessageQueue.filter(conv_id=conv_id, is_processed=False).count()
            conv_counts[conv_id] = count
        
        return {
            "total_messages": total,
            "unprocessed_messages": unprocessed,
            "conversations": conv_counts
        }
        
    async def has_bot_message(self, conv_id: str) -> bool:
        """判断队列中是否有机器人发的消息，不论是否已处理"""
        messages = await MessageQueue.filter(conv_id=conv_id, is_bot=True).all()
        if len(messages) > 0:
            return True
        return False

    async def _has_processed_message(self, conv_id: str) -> bool:
        """判断队列中是否有已处理消息"""
        messages = await MessageQueue.filter(conv_id=conv_id, is_processed=True).all()
        if len(messages) > 0:
            return True
        return False

    # === 记忆话题相关操作 ===
    
    async def store_memory(self, conv_id: str, memory_data: Dict) -> Memory:
        """存储记忆"""
        memory_id = memory_data.get("id")
        if memory_id:
            memory, created = await Memory.update_or_create(
                id=memory_id,
                conv_id=conv_id,
                defaults=memory_data
            )
        else:
            memory = await Memory.create(**memory_data)
        return memory
    
    async def get_memories_by_conv(self, conv_id: str, completed: Optional[bool] = None, limit: int = 20) -> List[Memory]:
        """获取指定会话的记忆"""
        query = Memory.filter(conv_id=conv_id)
        if completed is not None:
            query = query.filter(completed_status=completed)
        
        return await query.order_by("-updated_at").limit(limit).all()
    
    async def get_distinct_conv_ids(self) -> List[str]:
        """获取所有不同的会话ID
        
        Returns:
            会话ID列表
        """
        # 从话题表中获取唯一的conv_id
        conversations = await Memory.all().distinct().values_list('conv_id', flat=True)
        return conversations
    
    # === 认知节点相关操作 ===

    async def _link_nodes_to_memory(self, memory: Memory, nodes: List[str]) -> None:
        """建立记忆与节点的关联关系"""
        for node_id in nodes:
            node = await CognitiveNode.get(id=node_id)
            await memory.nodes.add(node)
    
    async def update_or_create_node(self, node_str: str) -> CognitiveNode:
        """存储或更新节点
        如果节点不存在，则创建，否则weight+0.3
        """
        node, created = await CognitiveNode.update_or_create(
            name=node_str
        )
        # 如果节点不存在，则创建
        # 如果节点存在，则weight+0.3
        # 这里的created是根据name是否存在来判断的
        # 如果name存在，则不创建，否则创建
        # 所以created为True时，weight+0.3，否则不加
        if created:
            node.act_lv += 0.3
            await node.save()
        return node
    
    async def get_nodes(self, limit: int = 100) -> List[CognitiveNode]:
        """获取节点列表"""
        query = CognitiveNode.all()
        
        return await query.order_by("-act_lv").limit(limit).all()
    
    async def get_node_by_name(self, name: str, conv_id: Optional[str] = None) -> CognitiveNode:
        """根据名称获取节点
        如果指定了conv_id，则返回指定会话的节点和conv_id为NULL的节点
        如果未指定conv_id，则返回所有conv_id为NULL的节点
        """
        if conv_id:
            return await CognitiveNode.filter(conv_id=conv_id, name=name).first()
        else:
            return await CognitiveNode.get(name=name, conv_id=None)
    
    # === 记忆关联相关操作 ===
    
    async def store_association(self, node_id_a: str, node_id_b: str) -> None:
        """存储或更新关联"""
        node_a_obj = await CognitiveNode.get(id=node_id_a)
        node_b_obj = await CognitiveNode.get(id=node_id_b)
        
        # 处理两个方向的关联
        for source, target in [(node_a_obj, node_b_obj), (node_b_obj, node_a_obj)]:
            assoc, created = await Association.update_or_create(
                source=source,
                target=target,
                defaults={'strength': 0.3}  # 新创建时初始强度
            )
            if not created:
                assoc.strength += 0.3
                await assoc.save()
    
    async def get_related_nodes(self, node_id: str) -> List[CognitiveNode]:
        """获取与指定节点相关联的所有节点"""
        query = Association.filter(source__id=node_id)
        # 获取关联的节点
        nodes = []
        for assoc in await query.order_by("-strength").limit(4).all():
            nodes.append(assoc.target)
        return nodes
    
    async def apply_decay(self, node_id: str, decay_rate: float) -> bool:
        """应用记忆衰减"""
        try:
            node = await CognitiveNode.filter(id=node_id).first()
            if node:
                node.act_lv *= (1 - decay_rate/10)  # 重要性衰减较慢
                await node.save()
                return True
        except Exception as e:
            logging.error(f"应用记忆衰减失败: {e}")
        return False 