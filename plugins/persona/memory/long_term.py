import logging
import uuid
from typing import Any, Dict, List, Optional

from ..storage.memory_models import CognitiveNode
from ..storage.memory_repository import MemoryRepository


class LongTermMemory:
    """长期记忆管理器

    负责管理记忆、节点和关联作为机器人的长期记忆
    """

    def __init__(self, memory_repo: MemoryRepository, config: Dict[str, Any] = None):
        """初始化长期记忆管理器

        Args:
            memory_repo: 记忆存储库
            config: 配置参数
        """
        self.memory_repo = memory_repo
        self.config = config or {}
        self.decay_rate = self.config.get("node_decay_rate", 0.01)

    async def store_memories(self, conv_id: str, memories: List[Dict]) -> List[str]:
        """存储记忆列表

        Args:
            conv_id: 会话ID
            memories: 记忆列表

        Returns:
            记忆ID列表
        """
        memory_ids = []

        for memory_data in memories:
            if not memory_data["completed_status"]:
                continue
            # 确保记忆有ID
            if "id" not in memory_data:
                memory_data["id"] = str(uuid.uuid4())

            try:
                # 提取并存储节点
                nodes = await self._extract_and_store_nodes(conv_id, memory_data)
                # 移除节点数据，防止冲突
                memory_data.pop("nodes")

                # 存储话题（此时外键约束已满足）
                memory = await self.memory_repo.store_memory(conv_id, memory_data)
                memory_ids.append(str(memory.uid))

                # 建立关联关系
                await self.memory_repo._link_nodes_to_memory(memory, nodes)

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
                node = await self.memory_repo.update_or_create_node(conv_id, node_str)
                logging.info(f"存储节点: {node.name}")
                node_ids.append(str(node.uid))
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
            await self.memory_repo.store_association(node_id_a, node_id_b)

    async def get_node_by_name(self, name: str, conv_id: Optional[str] = None) -> Optional[Dict]:
        """根据名称获取节点

        Args:
            name: 节点名称
            conv_id: 可选的会话ID过滤

        Returns:
            节点字典，未找到则返回None
        """
        # 构建Cypher查询
        query = """
            MATCH (n:CognitiveNode {name: $name})
            WHERE n.conv_id = $conv_id OR $conv_id IS NULL
            RETURN n LIMIT 1
        """
        params = {"name": name, "conv_id": conv_id}

        # 执行查询
        results, meta = await self.memory_repo.run_cypher(query, params)

        if not results:
            return None

        # 将结果转换为CognitiveNode对象并返回字典
        node = CognitiveNode.inflate(results[0][0])
        return self._node_to_dict(node)

    def _node_to_dict(self, node) -> Dict:
        """将节点对象转换为字典"""
        return {
            "id": str(node.uid),
            "name": node.name,
            "conv_id": node.conv_id,
            "act_lv": node.act_lv
        } 