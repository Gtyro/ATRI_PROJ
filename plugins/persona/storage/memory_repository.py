"""
记忆网络存储库，处理长期记忆的存储和检索
使用Neo4j OGM (neomodel)管理记忆图结构
"""

import logging
import time
import json
import random
import asyncio
from functools import partial
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime

from neomodel import db, config
from .memory_models import Memory, CognitiveNode, NodeAssociation

class MemoryRepository:
    """记忆网络存储库，处理长期记忆的存储和检索"""

    def __init__(self, config_dict: Dict[str, Any]):
        """初始化记忆网络存储库"""
        self.config = config_dict
        logging.info("记忆网络存储库已创建，等待初始化")

    async def _run_sync(self, func, *args, **kwargs):
        """在事件循环中运行同步函数"""
        return await asyncio.get_event_loop().run_in_executor(
            None, partial(func, *args, **kwargs)
        )

    async def run_cypher(self, query: str, params: Dict = None) -> Tuple[List, Dict]:
        """执行Cypher查询"""
        try:
            return await self._run_sync(db.cypher_query, query, params or {})
        except Exception as e:
            logging.error(f"执行Cypher查询失败: {e}")
            raise

    async def initialize(self) -> None:
        """初始化Neo4j连接"""
        try:
            # 设置Neo4j连接
            neo4j_config = self.config.get("neo4j_config", {})
            neo4j_uri = neo4j_config.get("uri", "bolt://localhost:7687")
            neo4j_user = neo4j_config.get("user", "neo4j")
            neo4j_password = neo4j_config.get("password", "neo4jpsw")

            # 配置neomodel - 修正URL格式
            host_port = neo4j_uri.replace('bolt://', '')
            config.DATABASE_URL = f"bolt://{neo4j_user}:{neo4j_password}@{host_port}"

            # 测试连接
            results, meta = await self.run_cypher("MATCH (n) RETURN count(n) as count", {})
            logging.info(f"Neo4j连接成功，当前数据库中有 {results[0][0]} 个节点")

            # 创建约束和索引
            await self._setup_constraints()

            logging.debug("记忆网络数据库已初始化")
        except Exception as e:
            logging.error(f"记忆网络数据库初始化失败: {e}")
            raise RuntimeError(f"Neo4j初始化失败: {e}")

    async def _setup_constraints(self):
        """创建必要的约束和索引"""
        try:
            # 为Memory创建唯一约束
            await self.run_cypher("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.uid IS UNIQUE")

            # 为CognitiveNode创建唯一约束
            await self.run_cypher("CREATE CONSTRAINT IF NOT EXISTS FOR (n:CognitiveNode) REQUIRE n.uid IS UNIQUE")

            # 为(conv_id, name)创建复合索引
            await self.run_cypher("""
                CREATE INDEX IF NOT EXISTS FOR (n:CognitiveNode)
                ON (n.conv_id, n.name)
            """)

            logging.debug("Neo4j约束和索引设置完成")
        except Exception as e:
            logging.error(f"设置Neo4j约束和索引失败: {e}")

    # === 记忆相关操作 ===

    async def store_memory(self, conv_id: str, memory_data: Dict) -> Memory:
        """存储记忆"""
        # 确保conv_id一致
        memory_data['conv_id'] = conv_id

        # 处理metadata (如果是字典，转为JSON字符串)
        if 'metadata' in memory_data and isinstance(memory_data['metadata'], dict):
            memory_data['metadata'] = json.dumps(memory_data['metadata'])

        # 如果提供了ID，则更新或创建
        if 'id' in memory_data:
            uid = memory_data.pop('id')
            try:
                # 尝试查找现有记忆
                memory = Memory.nodes.get_or_none(uid=uid)
                if memory:
                    # 更新属性
                    for key, value in memory_data.items():
                        if hasattr(memory, key):
                            setattr(memory, key, value)
                    memory.save()
                else:
                    # 创建新记忆
                    memory_data['uid'] = uid
                    memory = Memory(**memory_data).save()
            except Exception as e:
                logging.error(f"更新记忆失败: {e}")
                # 创建新记忆
                memory_data['uid'] = uid
                memory = Memory(**memory_data).save()
        else:
            # 直接创建新记忆
            memory = Memory(**memory_data).save()

        return memory

    async def clean_old_memories_by_conv(self, conv_id: str, max_memories: int = 500) -> int:
        """清理指定会话的旧记忆，只保留指定数量

        Args:
            conv_id: 会话ID
            max_memories: 每个会话保留的最大记忆数

        Returns:
            清理的记忆数量
        """
        try:
            # 计算要删除的记忆数量
            count_query = """
                MATCH (m:Memory {conv_id: $conv_id, is_permanent: false})
                RETURN count(m) AS count
            """
            results, meta = await self.run_cypher(count_query, {"conv_id": conv_id})
            total_non_permanent = results[0][0] if results else 0

            if total_non_permanent <= max_memories:
                return 0  # 不需要清理

            # 计算需要删除的数量
            to_delete = total_non_permanent - max_memories

            # 获取要删除的记忆ID列表（权重最低的）
            find_query = """
                MATCH (m:Memory {conv_id: $conv_id, is_permanent: false})
                RETURN m
                ORDER BY m.weight ASC, m.last_accessed ASC
                LIMIT $limit
            """
            results, meta = await self.run_cypher(find_query, {"conv_id": conv_id, "limit": to_delete})

            if not results:
                return 0

            # 删除这些记忆
            memories_to_delete = [Memory.inflate(row[0]) for row in results]

            for memory in memories_to_delete:
                # 先删除与节点的关系
                delete_rel_query = """
                    MATCH (m:Memory {uid: $uid})-[r:RELATED_TO]-()
                    DELETE r
                """
                await self.run_cypher(delete_rel_query, {"uid": memory.uid})

                # 然后删除记忆
                memory.delete()

            logging.info(f"会话 {conv_id} 清理了 {len(memories_to_delete)} 个非永久性记忆")
            return len(memories_to_delete)
        except Exception as e:
            logging.error(f"清理会话 {conv_id} 的记忆失败: {e}")
            return 0

    async def delete_memories_by_time_range(self, conv_id: str, start_time: datetime, end_time: datetime):
        """删除指定会话时间范围内的记忆"""
        try:
            # 构建查询
            query = """
                MATCH (m:Memory {conv_id: $conv_id})
                WHERE m.created_at >= $start_time AND m.created_at <= $end_time
                RETURN m
            """
            results, meta = await self.run_cypher(query, {
                "conv_id": conv_id,
                "start_time": start_time,
                "end_time": end_time
            })

            memories_to_delete = [Memory.inflate(row[0]) for row in results]

            for memory in memories_to_delete:
                # 先删除与节点的关系
                delete_rel_query = """
                    MATCH (m:Memory {uid: $uid})-[r:RELATED_TO]-()
                    DELETE r
                """
                await self.run_cypher(delete_rel_query, {"uid": memory.uid})

                # 然后删除记忆
                memory.delete()

            logging.info(f"会话 {conv_id} 清理了时间在 {start_time} 到 {end_time} 之间的记忆共 {len(memories_to_delete)} 条")
        except Exception as e:
            logging.error(f"删除会话 {conv_id} 的记忆失败: {e}")

    # === 认知节点相关操作 ===

    async def update_or_create_node(self, conv_id: str, node_name: str, is_permanent: bool = False) -> CognitiveNode:
        """存储或更新节点"""
        try:
            # 查询现有节点
            node = CognitiveNode.nodes.get_or_none(conv_id=conv_id, name=node_name)

            if node:
                # 更新节点
                node.act_lv += 0.3
                node.last_accessed = datetime.now()
                # 如果更新为常驻节点
                if is_permanent and not node.is_permanent:
                    node.is_permanent = True
                    logging.info(f"节点设为常驻: {conv_id}-{node_name}")
                node.save()
                logging.info(f"增强节点: {conv_id}-{node_name}")
            else:
                # 创建新节点
                node = CognitiveNode(
                    conv_id=conv_id,
                    name=node_name,
                    is_permanent=is_permanent
                ).save()
                logging.info(f"创建节点: {conv_id}-{node_name}")

            return node
        except Exception as e:
            logging.error(f"更新或创建节点失败: {e}")
            return node

    async def _link_nodes_to_memory(self, memory: Memory, node_ids: List[str]) -> None:
        """建立记忆与节点的关联关系

        Args:
            memory: 记忆对象
            node_ids: 节点ID列表
        """
        try:
            for node_id in node_ids:
                # 查找节点
                node = CognitiveNode.nodes.get_or_none(uid=node_id)
                if node:
                    # 建立关联
                    memory.cognitive_nodes.connect(node)
        except Exception as e:
            logging.error(f"关联节点到记忆失败: {e}")

    async def store_association(self, node_id_a: str, node_id_b: str) -> bool:
        """存储或更新节点关联"""
        try:
            # 获取节点
            node_a = CognitiveNode.nodes.get_or_none(uid=node_id_a)
            node_b = CognitiveNode.nodes.get_or_none(uid=node_id_b)

            if not node_a or not node_b:
                return False

            # 处理双向关联 (a->b)
            rel = node_a.associated_nodes.relationship(node_b)
            if rel:
                # 关联已存在，增强强度
                rel.strength += 0.3
                rel.updated_at = datetime.now()
                rel.save()
                logging.info(f"增强关联: {node_a.name}-{node_b.name}")
            else:
                # 创建新关联
                node_a.associated_nodes.connect(node_b)
                logging.info(f"创建关联: {node_a.name}-{node_b.name}")

            # 处理另一个方向 (b->a)
            rel = node_b.associated_nodes.relationship(node_a)
            if rel:
                rel.strength += 0.3
                rel.updated_at = datetime.now()
                rel.save()
            else:
                node_b.associated_nodes.connect(node_a)

            return True
        except Exception as e:
            logging.error(f"存储节点关联失败: {e}")
            return False

    async def get_nodes(self, limit: Optional[int] = None, conv_id: Optional[str] = None) -> List[CognitiveNode]:
        """获取节点列表"""
        try:
            # 构建查询
            query = "MATCH (n:CognitiveNode) "
            params = {}

            # 添加conv_id过滤
            if conv_id:
                query += "WHERE n.conv_id = $conv_id "
                params["conv_id"] = conv_id

            # 添加排序和限制
            query += "RETURN n ORDER BY n.act_lv DESC "
            if limit:
                query += "LIMIT $limit"
                params["limit"] = limit

            # 执行查询
            results, meta = await self.run_cypher(query, params)

            # 将结果转换为CognitiveNode对象
            nodes = [CognitiveNode.inflate(row[0]) for row in results]
            return nodes
        except Exception as e:
            logging.error(f"获取节点失败: {e}")
            return []

    async def get_related_nodes(self, node_id: str) -> List[CognitiveNode]:
        """获取与指定节点相关联的所有节点

        Args:
            node_id: 节点ID

        Returns:
            相关联的节点列表
        """
        try:
            # 构建查询
            query = """
                MATCH (n:CognitiveNode {uid: $node_id})-[r:ASSOCIATED_WITH]->(related:CognitiveNode)
                RETURN related, r.strength
                ORDER BY r.strength DESC
                LIMIT 4
            """

            # 执行查询
            results, meta = await self.run_cypher(query, {"node_id": node_id})

            # 将结果转换为CognitiveNode对象
            nodes = [CognitiveNode.inflate(row[0]) for row in results]
            return nodes
        except Exception as e:
            logging.error(f"获取相关节点失败: {e}")
            return []

    async def get_nodes_by_conv_id(self, conv_id: str, order_by: str = "-act_lv",
                              limit: Optional[int] = None, is_permanent: Optional[bool] = None) -> List[CognitiveNode]:
        """获取指定会话ID的所有认知节点

        Args:
            conv_id: 会话ID
            order_by: 排序字段
            limit: 返回数量限制
            is_permanent: 是否只返回常驻节点

        Returns:
            节点列表
        """
        try:
            # 构建基础查询
            query = "MATCH (n:CognitiveNode {conv_id: $conv_id}) "
            params = {"conv_id": conv_id}

            # 添加is_permanent过滤
            if is_permanent is not None:
                query += "WHERE n.is_permanent = $is_permanent "
                params["is_permanent"] = is_permanent

            # 添加排序
            if order_by == "-act_lv":
                query += "RETURN n ORDER BY n.act_lv DESC "
            elif order_by == "act_lv":
                query += "RETURN n ORDER BY n.act_lv ASC "
            elif order_by == "-created_at":
                query += "RETURN n ORDER BY n.created_at DESC "
            elif order_by == "created_at":
                query += "RETURN n ORDER BY n.created_at ASC "
            else:
                query += "RETURN n "

            # 添加限制
            if limit:
                query += "LIMIT $limit"
                params["limit"] = limit

            # 执行查询
            results, meta = await self.run_cypher(query, params)

            # 将结果转换为CognitiveNode对象
            nodes = [CognitiveNode.inflate(row[0]) for row in results]
            return nodes
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
            # 获取节点
            node = CognitiveNode.nodes.get_or_none(uid=node_id)

            if not node:
                return False

            # 如果是常驻节点，不允许删除
            if node.is_permanent:
                logging.warning(f"尝试删除常驻节点 {node_id}（{node.name}）被拒绝")
                return False

            # 首先获取关联的记忆
            memory_query = """
                MATCH (n:CognitiveNode {uid: $node_id})<-[:RELATED_TO]-(m:Memory)
                RETURN m
            """
            results, meta = await self.run_cypher(memory_query, {"node_id": node_id})
            memories = [Memory.inflate(row[0]) for row in results]

            # 删除与该节点相关的所有关系
            rel_query = """
                MATCH (n:CognitiveNode {uid: $node_id})-[r]-()
                DELETE r
            """
            await self.run_cypher(rel_query, {"node_id": node_id})

            # 删除节点
            node.delete()

            # 检查每个记忆是否还有其他关联节点，如果没有，则删除
            for memory in memories:
                # 如果记忆是常驻的，不删除
                if memory.is_permanent:
                    continue

                # 检查是否还有关联节点
                check_query = """
                    MATCH (m:Memory {uid: $memory_id})-[:RELATED_TO]-()
                    RETURN count(*) as count
                """
                results, meta = await self.run_cypher(check_query, {"memory_id": memory.uid})

                if results[0][0] == 0:
                    # 没有关联节点，删除记忆
                    logging.info(f"删除没有关联节点的记忆: {memory.uid}")
                    memory.delete()

            return True
        except Exception as e:
            logging.error(f"删除节点 {node_id} 失败: {e}")
            return False

    # === 衰减相关操作 ===

    async def apply_decay(self, node_id: str, decay_rate: float) -> bool:
        """应用节点衰减"""
        try:
            # 获取节点
            node = CognitiveNode.nodes.get_or_none(uid=node_id)

            if not node:
                return False

            # 应用衰减
            node.act_lv *= (1 - decay_rate * (random.random() * 0.5 + 0.5))
            node.save()

            return True
        except Exception as e:
            logging.error(f"应用节点衰减失败: {e}")
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
            query = """
                MATCH ()-[r:ASSOCIATED_WITH]->()
                RETURN elementId(r) as rel_id, r.strength as strength
            """
            results, meta = await self.run_cypher(query, {})

            processed = 0
            for row in results:
                rel_id, strength = row

                # 计算新强度
                new_strength = strength * (1 - decay_rate * (random.random() * 0.5 + 0.5))

                # 更新关联强度
                update_query = """
                    MATCH ()-[r]-()
                    WHERE elementId(r) = $rel_id
                    SET r.strength = $new_strength
                """
                await self.run_cypher(update_query, {"rel_id": rel_id, "new_strength": new_strength})
                processed += 1

            return processed
        except Exception as e:
            logging.error(f"应用关联衰减失败: {e}")
            return 0

    async def apply_memory_decay(self, decay_rate: float) -> int:
        """应用记忆权重衰减

        Args:
            decay_rate: 衰减率

        Returns:
            处理的记忆数量
        """
        try:
            # 获取所有非永久性记忆
            query = """
                MATCH (m:Memory)
                WHERE m.is_permanent = false
                RETURN m
            """
            results, meta = await self.run_cypher(query, {})

            processed = 0
            for row in results:
                memory = Memory.inflate(row[0])

                # 应用衰减
                memory.weight *= (1 - decay_rate * (random.random() * 0.5 + 0.5))
                memory.save()
                processed += 1

            return processed
        except Exception as e:
            logging.error(f"应用记忆衰减失败: {e}")
            return 0 