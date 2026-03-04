"""
记忆网络存储库，处理长期记忆的存储和检索
使用Neo4j OGM (neomodel)管理记忆图结构
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, Union

from neomodel import config, db
from neo4j import GraphDatabase

from src.core.domain import PersonaConfig

from .memory_models import CognitiveNode, Memory


class MemoryRepository:
    """记忆网络存储库，处理长期记忆的存储和检索"""

    def __init__(self, config_dict: Union[Dict[str, Any], PersonaConfig]):
        """初始化记忆网络存储库"""
        self.config = config_dict
        self._driver = None

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

    @staticmethod
    def _to_epoch_seconds(value: Union[datetime, float, int]) -> float:
        """统一转换为秒级时间戳。"""
        if isinstance(value, datetime):
            return float(value.timestamp())
        return float(value)

    async def initialize(self) -> None:
        """初始化Neo4j连接"""
        try:
            if isinstance(self.config, PersonaConfig):
                neo4j_uri = self.config.neo4j_config.uri
                neo4j_user = self.config.neo4j_config.user
                neo4j_password = self.config.neo4j_config.password
                liveness_check_timeout = self.config.neo4j_config.liveness_check_timeout
            else:
                neo4j_config = self.config.get("neo4j_config")
                if not isinstance(neo4j_config, dict):
                    raise ValueError("neo4j_config 未配置")
                neo4j_uri = neo4j_config["uri"]
                neo4j_user = neo4j_config["user"]
                neo4j_password = neo4j_config["password"]
                liveness_check_timeout = neo4j_config.get("liveness_check_timeout", 30.0)

            driver_kwargs: Dict[str, Any] = {
                "auth": (neo4j_user, neo4j_password),
                "liveness_check_timeout": liveness_check_timeout,
            }

            # 配置 neomodel 连接，交由 driver 层处理连接保活检查。
            self._driver = GraphDatabase.driver(neo4j_uri, **driver_kwargs)
            config.DATABASE_URL = ""
            config.DRIVER = self._driver
            db.set_connection(driver=self._driver)

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

            # 旧逻辑：在仓库中硬编码复合唯一约束，现迁移到模型声明。
            # await self.run_cypher(
            #     """
            #     CREATE CONSTRAINT IF NOT EXISTS FOR (n:CognitiveNode)
            #     REQUIRE (n.conv_id, n.name) IS UNIQUE
            #     """
            # )

            # 从模型声明中安装复合约束（目前仅 CognitiveNode 使用）。
            await self._apply_model_constraints(CognitiveNode)

            logging.debug("Neo4j约束和索引设置完成")
        except Exception as e:
            logging.error(f"设置Neo4j约束和索引失败: {e}")

    async def _apply_model_constraints(self, model_cls: Any) -> None:
        """执行模型中声明的自定义约束。"""
        for query in getattr(model_cls, "schema_constraints", ()):
            if isinstance(query, str) and query.strip():
                await self.run_cypher(query)

    # === 记忆相关操作 ===

    async def store_memory(self, conv_id: str, memory_data: Dict) -> Memory:
        """存储记忆"""
        # 确保conv_id一致
        memory_data["conv_id"] = conv_id

        # 处理metadata (如果是字典，转为JSON字符串)
        if "metadata" in memory_data and isinstance(memory_data["metadata"], dict):
            memory_data["metadata"] = json.dumps(memory_data["metadata"])

        # 如果提供了ID，则更新或创建
        if "id" in memory_data:
            uid = memory_data.pop("id")
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
                    memory_data["uid"] = uid
                    memory = Memory(**memory_data).save()
            except Exception as e:
                logging.error(f"更新记忆失败: {e}")
                # 创建新记忆
                memory_data["uid"] = uid
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

    async def delete_memories_by_time_range(
        self,
        conv_id: str,
        start_time: Union[datetime, float, int],
        end_time: Union[datetime, float, int],
    ):
        """删除指定会话时间范围内的记忆"""
        try:
            start_ts = self._to_epoch_seconds(start_time)
            end_ts = self._to_epoch_seconds(end_time)

            # 构建查询
            query = """
                MATCH (m:Memory {conv_id: $conv_id})
                WHERE m.created_at >= $start_time AND m.created_at <= $end_time
                RETURN m
            """
            results, meta = await self.run_cypher(query, {
                "conv_id": conv_id,
                "start_time": start_ts,
                "end_time": end_ts,
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
            query = """
                MERGE (n:CognitiveNode {conv_id: $conv_id, name: $node_name})
                ON CREATE SET
                    n.uid = $uid,
                    n.act_lv = 1.0,
                    n.created_at = $now_ts,
                    n.last_accessed = $now_ts,
                    n.is_permanent = $is_permanent
                ON MATCH SET
                    n.act_lv = coalesce(n.act_lv, 1.0) + $delta,
                    n.last_accessed = $now_ts,
                    n.is_permanent = n.is_permanent OR $is_permanent
                RETURN n
            """
            now_ts = datetime.now().timestamp()
            results, _ = await self.run_cypher(
                query,
                {
                    "conv_id": conv_id,
                    "node_name": node_name,
                    "uid": str(uuid.uuid4()),
                    "is_permanent": bool(is_permanent),
                    "delta": 0.3,
                    "now_ts": now_ts,
                },
            )
            if not results:
                raise RuntimeError("更新或创建节点后未返回结果")
            node = CognitiveNode.inflate(results[0][0])
            logging.info(f"更新或创建节点: {conv_id}-{node_name}")
            return node
        except Exception as e:
            logging.error(f"更新或创建节点失败: {e}")
            raise

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
            query = """
                MATCH (a:CognitiveNode {uid: $node_id_a}), (b:CognitiveNode {uid: $node_id_b})
                MERGE (a)-[r1:ASSOCIATED_WITH]->(b)
                ON CREATE SET
                    r1.strength = 1.0,
                    r1.created_at = $now_ts,
                    r1.updated_at = $now_ts
                ON MATCH SET
                    r1.strength = coalesce(r1.strength, 1.0) + $delta,
                    r1.updated_at = $now_ts
                MERGE (b)-[r2:ASSOCIATED_WITH]->(a)
                ON CREATE SET
                    r2.strength = 1.0,
                    r2.created_at = $now_ts,
                    r2.updated_at = $now_ts
                ON MATCH SET
                    r2.strength = coalesce(r2.strength, 1.0) + $delta,
                    r2.updated_at = $now_ts
                RETURN a.name, b.name
            """
            now_ts = datetime.now().timestamp()
            results, _ = await self.run_cypher(
                query,
                {
                    "node_id_a": node_id_a,
                    "node_id_b": node_id_b,
                    "delta": 0.3,
                    "now_ts": now_ts,
                },
            )
            if not results:
                return False
            node_a_name, node_b_name = results[0]
            logging.info(f"更新或创建关联: {node_a_name}-{node_b_name}")
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

    async def get_nodes_by_conv_id(
        self,
        conv_id: str,
        order_by: str = "-act_lv",
        limit: Optional[int] = None,
        is_permanent: Optional[bool] = None,
    ) -> List[CognitiveNode]:
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
