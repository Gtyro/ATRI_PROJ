import logging
import uuid
from typing import Dict, List, Optional, Any

from ..storage.repository import Repository

class LongTermMemory:
    """长期记忆管理器

    负责管理记忆、节点和关联作为机器人的长期记忆
    """

    def __init__(self, repository: Repository, config: Dict[str, Any] = None):
        """初始化长期记忆管理器

        Args:
            repository: 存储仓库
            config: 配置参数
        """
        self.repository = repository
        self.config = config or {}
        self.decay_rate = self.config.get("node_decay_rate", 0.01)
        logging.info("长期记忆管理器已创建")

    async def store_memories(self, conv_id: str, memories: List[Dict]) -> List[str]:
        """存储记忆列表

        Args:
            memories: 记忆列表

        Returns:
            记忆ID列表
        """
        async def _link_nodes_to_memory(memory, nodes: List[str]) -> None:
            """建立话题与节点的关联关系"""
            await self.repository._link_nodes_to_memory(memory, nodes)
        memory_ids = []

        for memory_data in memories:
            if not memory_data["completed_status"]:
                continue
            # 确保记忆有ID
            if "id" not in memory_data:
                memory_data["id"] = uuid.uuid4()

            try:
                # 提取并存储节点
                nodes = await self._extract_and_store_nodes(conv_id, memory_data)
                memory_data.pop("nodes")

                # 存储话题（此时外键约束已满足）
                memory = await self.repository.store_memory(conv_id, memory_data)
                memory_ids.append(str(memory.id))

                # 建立关联关系
                await _link_nodes_to_memory(memory, nodes)

            except Exception as e:
                logging.error(f"存储记忆失败: {e}")
                logging.error(f"记忆数据: \n{memory_data}")

        return memory_ids

    async def _extract_and_store_nodes(self, conv_id: str, memory_data: Dict) -> List[str]:
        """从记忆数据中提取并更新节点

        Args:
            conv_id: 会话ID
            memory_data: 记忆数据

        Returns:
            节点ID列表
        """
        # 从记忆中提取节点（这里简化处理）
        nodes:list[str] = memory_data["nodes"]

        node_ids = []
        for node_str in nodes:
            try:
                node = await self.repository.update_or_create_node(conv_id, node_str)
                logging.info(f"存储节点: {node.name}")
                node_ids.append(str(node.id))
            except Exception as e:
                logging.error(f"存储节点失败: {e}")

        # 处理关联
        await self._process_associations(node_ids)
        return node_ids

    async def _process_associations(self, node_ids: List[str]) -> None:
        """处理节点关联

        Args:
            node_ids: 节点ID列表
        """
        # 生成所有节点组合
        from itertools import combinations
        for node_id_a, node_id_b in combinations(node_ids, 2):
            await self.repository.store_association(node_id_a, node_id_b)

    async def get_topics_by_conv(self, conv_id: str, completed: Optional[bool] = None) -> List[Dict]:
        """获取指定会话的话题

        Args:
            conv_id: 会话ID
            completed: 是否已完结

        Returns:
            话题列表
        """
        topics = await self.repository.get_memories_by_conv(conv_id, completed)
        return [self._topic_to_dict(topic) for topic in topics]

    def _topic_to_dict(self, topic) -> Dict:
        """将话题模型转换为字典

        Args:
            topic: 话题模型

        Returns:
            话题字典
        """
        return {
            "id": str(topic.id),
            "conv_id": topic.conv_id,
            "title": topic.title,
            "summary": topic.content,
            "participants": topic.participants,
            "created_at": topic.created_at.timestamp(),
            "updated_at": topic.updated_at.timestamp(),
            "importance": topic.importance,
            "completed_status": topic.completed_status,
            "continuation_probability": topic.continuation_probability
        }

    async def get_node_by_name(self, name: str, conv_id: Optional[str] = None) -> Optional[Dict]:
        """根据名称获取节点

        Args:
            name: 节点名称
            conv_id: 可选的会话ID过滤

        Returns:
            节点字典，未找到则返回None
        """
        node = await self.repository.get_node_by_name(name, conv_id)
        if node:
            return self._node_to_dict(node)
        return None

    def _node_to_dict(self, node) -> Dict:
        """将节点对象转换为字典"""
        return {
            "id": str(node.id),
            "name": node.name,
            "conv_id": node.conv_id,
            "act_lv": node.act_lv
        } 