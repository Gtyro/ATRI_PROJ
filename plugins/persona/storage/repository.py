import logging
import time
import random
from typing import Dict, List, Optional, Any, Tuple, Union
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

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict]:
        """获取指定会话的未处理消息字典列表"""
        messages = await MessageQueue.filter(conv_id=conv_id, is_processed=False).order_by("created_at").limit(limit).all()
        return [msg.to_dict() for msg in messages]
    
    async def get_recent_messages(self, conv_id: str, limit: int = 40) -> List[Dict]:
        """按照创建时间升序返回指定会话最近的limit条消息"""
        # 直接获取最近的limit条消息（按时间倒序）
        messages = await MessageQueue.filter(
            conv_id=conv_id
        ).order_by("-created_at").limit(limit).all()
        
        # 反转列表得到正确的时间顺序
        return [msg.to_dict() for msg in reversed(messages)]
    
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
        """移除旧消息，基于时间阈值策略
        
        Args:
            conv_id: 会话ID
            keep_count: 最少保留的消息数量
            
        Returns:
            移除的消息数量
        """
        # 获取最新的已处理消息
        latest_processed = await MessageQueue.filter(
            conv_id=conv_id, 
            is_processed=True
        ).order_by("-created_at").first()

        # 获取第keep_count+1条消息
        threshold_msg = await MessageQueue.filter(
            conv_id=conv_id
        ).order_by("-created_at").offset(keep_count).first()

        if not latest_processed or not threshold_msg:
            return 0

        # 确定时间阈值
        time_threshold = min(latest_processed.created_at, threshold_msg.created_at)

        # 删除早于等于阈值的消息
        deleted = await MessageQueue.filter(
            conv_id=conv_id,
            created_at__lte=time_threshold
        ).delete()

        logging.info(f"移除旧消息: {deleted} 条，基于双重时间阈值策略")
        return deleted
    
    async def get_queue_stats(self, conv_id: Optional[str] = None) -> Dict[str, Any]:
        """获取队列统计信息
        
        Args:
            conv_id: 可选的会话ID，如果指定则只返回该会话的统计
        """
        # 如果指定了conv_id，只获取该会话的统计
        if conv_id:
            total = await MessageQueue.filter(conv_id=conv_id).count()
            unprocessed = await MessageQueue.filter(conv_id=conv_id, is_processed=False).count()
            return {
                "total_messages": total,
                "unprocessed_messages": unprocessed
            }
        
        # 否则获取全局统计
        total = await MessageQueue.all().count()
        unprocessed = await MessageQueue.filter(is_processed=False).count()        
        return {
            "total_messages": total,
            "unprocessed_messages": unprocessed
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
        
        return await query.order_by("-last_accessed").limit(limit).all()
        
    async def clean_old_memories_by_conv(self, conv_id: str, max_memories: int = 500) -> int:
        """清理指定会话的旧记忆，只保留指定数量
        
        Args:
            conv_id: 会话ID
            max_memories: 每个会话保留的最大记忆数
            
        Returns:
            清理的记忆数量
        """
        try:
            # 只获取非永久性记忆
            non_permanent_memories = await Memory.filter(conv_id=conv_id, is_permanent=False).all()
            non_permanent_count = len(non_permanent_memories)
            
            # 如果非永久性记忆数量超过了允许的限制
            if non_permanent_count > max_memories:
                # 计算需要删除的数量
                to_delete_count = non_permanent_count - max_memories
                
                # 获取权重最低的非永久性记忆 (先按权重升序，再按最后访问时间升序)
                memories_to_delete = await Memory.filter(
                    conv_id=conv_id,
                    is_permanent=False
                ).order_by("weight", "last_accessed").limit(to_delete_count).all()
                
                # 删除这些记忆
                deleted_count = 0
                for memory in memories_to_delete:
                    # 先解除与节点的关联
                    await memory.nodes.clear()
                    # 然后删除记忆
                    await memory.delete()
                    deleted_count += 1
                
                logging.info(f"会话 {conv_id} 清理了 {deleted_count} 个非永久性记忆，保留了 {max_memories} 个")
                return deleted_count
            
            return 0  # 不需要清理
        except Exception as e:
            logging.error(f"清理会话 {conv_id} 的记忆失败: {e}")
            return 0

    # === 认知节点相关操作 ===

    async def _link_nodes_to_memory(self, memory: Memory, nodes: List[str]) -> None:
        """建立记忆与节点的关联关系"""
        for node_id in nodes:
            node = await CognitiveNode.get(id=node_id)
            await memory.nodes.add(node)
    
    async def update_or_create_node(self, conv_id: str, node_str: str, is_permanent: bool = False) -> CognitiveNode:
        """存储或更新节点
        如果节点不存在，则创建，否则weight+0.3
        
        Args:
            conv_id: 会话ID
            node_str: 节点名称
            is_permanent: 是否为常驻节点，常驻节点不会被遗忘(删除)，但仍会被衰减
        """
        node, created = await CognitiveNode.update_or_create(
            conv_id=conv_id,
            name=node_str,
            defaults={"is_permanent": is_permanent}
        )
        # 如果节点不存在，则创建，weight为默认值
        # 如果节点存在，则weight+0.3
        if not created:
            logging.info(f"增强节点: {conv_id}-{node_str}")
            node.act_lv += 0.3
            # 如果更新时指定了常驻属性为True，则更新节点的常驻属性
            if is_permanent and not node.is_permanent:
                node.is_permanent = True
                logging.info(f"节点设为常驻: {conv_id}-{node_str}")
            await node.save()
        return node
    
    async def get_nodes(self, limit: int = None, conv_id: Optional[str] = None) -> List[CognitiveNode]:
        """获取节点列表
        
        Args:
            limit: 限制返回的节点数量，None表示返回所有节点
            conv_id: 会话ID，用于限制搜索范围
            
        Returns:
            节点列表，按激活水平降序排序
        """
        query = CognitiveNode.all().order_by("-act_lv")
        
        # 如果指定了会话ID，则只查询该会话的节点
        if conv_id:
            query = query.filter(conv_id=conv_id)
            
        if limit is not None:
            return await query.limit(limit).all()
        return await query.all()
    
    async def get_node_by_name(self, name: str, conv_id: Optional[str] = None) -> Optional[CognitiveNode]:
        """根据名称获取节点，不区分大小写
        
        Args:
            name: 节点名称
            conv_id: 会话ID，如果提供则查找特定会话的节点，否则查找所有会话的节点
            
        Returns:
            找到的节点，未找到则返回None
        """
        from tortoise.expressions import Q
        
        # 创建一个基本查询
        query = CognitiveNode.filter(name__iexact=name)  # 使用iexact进行不区分大小写的匹配
        
        # 如果指定了conv_id，则添加会话过滤条件
        if conv_id:
            query = query.filter(conv_id=conv_id)
            
        # 查询并返回结果
        return await query.first()
    
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
            )
            if not created:
                # 需要await获取关联对象
                logging.info(f"增强关联: {(await assoc.source).name}-{(await assoc.target).name}")
                assoc.strength += 0.3
                await assoc.save()
            else:
                logging.info(f"创建关联: {assoc.source.name}-{assoc.target.name}")
    
    async def get_related_nodes(self, node_id: str) -> List[CognitiveNode]:
        """获取与指定节点相关联的所有节点"""
        query = Association.filter(source__id=node_id)
        # 获取关联的节点
        nodes = []
        for assoc in await query.order_by("-strength").limit(4).all():
            # 确保获取完整的CognitiveNode实例
            target_node = await CognitiveNode.get_or_none(id=assoc.target_id)
            if target_node:
                nodes.append(target_node)
        return nodes
        
    async def get_nodes_by_conv_id(self, conv_id: str, order_by: str = "-act_lv", limit: Optional[int] = None, is_permanent: Optional[bool] = None) -> List[CognitiveNode]:
        """获取指定会话ID的所有认知节点
        
        Args:
            conv_id: 会话ID
            order_by: 排序字段，默认按激活水平降序排序，可选值：
                      "-act_lv" - 按激活水平降序（高到低）
                      "act_lv" - 按激活水平升序（低到高）
                      "-created_at" - 按创建时间降序（新到旧）
                      "created_at" - 按创建时间升序（旧到新）
            limit: 限制返回的数量，None表示不限制
            is_permanent: 是否只返回常驻节点，None表示不过滤
            
        Returns:
            认知节点列表
        """
        try:
            query = CognitiveNode.filter(conv_id=conv_id)
            
            # 如果指定了is_permanent，则添加过滤条件
            if is_permanent is not None:
                query = query.filter(is_permanent=is_permanent)
                
            # 添加排序
            query = query.order_by(order_by)
            
            if limit is not None:
                return await query.limit(limit).all()
            return await query.all()
        except Exception as e:
            logging.error(f"获取会话 {conv_id} 的节点失败: {e}")
            return []
            
    async def delete_node(self, node_id: str) -> bool:
        """删除指定ID的节点
        
        Args:
            node_id: 节点ID
            
        Returns:
            是否成功删除
        """
        try:
            node = await CognitiveNode.filter(id=node_id).first()
            if not node:
                return False
                
            # 如果是常驻节点，不允许删除
            if node.is_permanent:
                logging.warning(f"尝试删除常驻节点 {node_id}（{node.name}）被拒绝")
                return False
                
            # 获取与该节点关联的所有记忆
            memories = await node.memories.all()
            
            # 删除节点（关联关系会自动删除，因为设置了 on_delete=fields.CASCADE）
            await node.delete()
            
            # 检查每个记忆是否还有其他关联节点，如果没有，则删除该记忆
            for memory in memories:
                # 如果记忆是常驻的，则不删除
                if memory.is_permanent:
                    continue
                    
                remaining_nodes_count = await memory.nodes.all().count()
                if remaining_nodes_count == 0:
                    logging.info(f"删除没有关联节点的记忆: {memory.id}")
                    await memory.delete()
                    
            return True
        except Exception as e:
            logging.error(f"删除节点 {node_id} 失败: {e}")
            return False
            
    # === 衰减相关操作 ===
    
    async def apply_decay(self, node_id: str, decay_rate: float) -> bool:
        """应用节点衰减"""
        try:
            node = await CognitiveNode.filter(id=node_id).first()
            if node:
                node.act_lv *= (1 - decay_rate*(random.random()*0.5+0.5))  # 应用完整的衰减率
                await node.save()
                return True
        except Exception as e:
            logging.error(f"应用记忆衰减失败: {e}")
        return False

    async def apply_association_decay(self, decay_rate: float) -> int:
        """应用关联关系衰减
        
        Args:
            decay_rate: 衰减率
            
        Returns:
            处理的关联数量
        """
        try:
            # 获取所有关联关系
            associations = await Association.all()
            processed = 0
            
            for assoc in associations:
                # 应用衰减
                assoc.strength *= (1 - decay_rate*(random.random()*0.5+0.5))
                await assoc.save()
                processed += 1
                
            return processed
        except Exception as e:
            logging.error(f"应用关联关系衰减失败: {e}")
            return 0

    async def apply_memory_decay(self, decay_rate: float) -> int:
        """应用记忆权重衰减到非永久性记忆
        
        Args:
            decay_rate: 衰减率
            
        Returns:
            处理的记忆数量
        """
        try:
            # 获取所有非永久性记忆
            memories = await Memory.filter(is_permanent=False).all()
            processed = 0
            
            for memory in memories:
                # 应用衰减到权重
                memory.weight *= (1 - decay_rate * (random.random() * 0.5 + 0.5))
                
                # 如果权重过低，可以考虑在这里添加删除逻辑，但目前仅应用衰减
                # if memory.weight < some_threshold:
                #     await memory.delete() # 需要考虑关联等清理
                
                await memory.save()
                processed += 1
                
            return processed
        except Exception as e:
            logging.error(f"应用记忆衰减失败: {e}")
            return 0