import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..storage.memory_repository import MemoryRepository
from ..storage.memory_models import Memory, CognitiveNode

class LongTermRetriever:
    """记忆检索器

    负责从长期记忆中检索相关内容
    """

    def __init__(self, memory_repo: MemoryRepository):
        """初始化记忆检索器

        Args:
            memory_repo: 记忆存储库
        """
        self.memory_repo = memory_repo
        logging.info("记忆检索器已创建")

    async def search_for_memories(self, query: str, user_id: Optional[str] = None, limit: int = 5, conv_id: Optional[str] = None) -> List[Dict]:
        """搜索相关记忆

        Args:
            query: 搜索查询
            user_id: 用户ID，用于个性化搜索
            limit: 返回结果数量限制
            conv_id: 会话ID，用于限制搜索范围

        Returns:
            相关记忆列表
        """
        # 使用Neo4j的全文搜索功能
        results = []

        # 1. 搜索话题记忆内容
        topics = await self._search_topics(query, limit, conv_id)
        if topics:
            # 添加source标记
            for topic in topics:
                topic['source'] = 'topic'
            results.extend(topics)

        # 2. 通过节点搜索关联记忆
        memories = await self._search_nodes(query, limit, conv_id)
        if memories:
            # 添加source标记
            for memory in memories:
                memory['source'] = 'node'
            results.extend(memories)

        # 3. 按id过滤重复数据
        unique_results = []
        seen_ids = set()
        for result in results:
            if result['id'] not in seen_ids:
                unique_results.append(result)
                seen_ids.add(result['id'])
        results = unique_results

        # 4. 按权重排序
        results.sort(key=lambda x: x['weight'], reverse=True)

        # 5. 限制结果数量
        return results[:limit]

    async def _search_topics(self, query: str, limit: int, conv_id: str) -> List[Dict]:
        """搜索相关话题内容

        Args:
            query: 搜索查询
            limit: 数量限制
            conv_id: 会话ID，用于限制搜索范围

        Returns:
            记忆列表
        """
        try:
            # 使用Neo4j的正则表达式搜索功能
            cypher_query = """
                MATCH (m:Memory)
                WHERE 
                    (m.conv_id = $conv_id OR $conv_id IS NULL) AND
                    (m.title =~ $query_pattern OR m.content =~ $query_pattern)
                RETURN m
                ORDER BY m.weight DESC, m.last_accessed DESC
                LIMIT $limit
            """
            
            # 构建正则表达式模式 (不区分大小写)
            query_pattern = f"(?i).*{query}.*"
            
            # 执行查询
            params = {
                "conv_id": conv_id,
                "query_pattern": query_pattern,
                "limit": limit
            }
            
            results, meta = await self.memory_repo.run_cypher(cypher_query, params)
            
            # 将结果转换为字典
            memories = []
            for row in results:
                memory = Memory.inflate(row[0])
                memories.append({
                    "id": memory.uid,
                    "title": memory.title,
                    "content": memory.content,
                    "weight": memory.weight,
                    "created_at": memory.created_at.timestamp() if memory.created_at else datetime.now().timestamp()
                })
                
            return memories
        except Exception as e:
            logging.error(f"搜索记忆内容失败: {e}")
            return []

    async def _search_nodes(self, query: str, limit: int, conv_id: Optional[str] = None) -> List[Dict]:
        """通过节点搜索相关记忆

        Args:
            query: 搜索查询
            limit: 数量限制
            conv_id: 会话ID，用于限制搜索范围

        Returns:
            记忆列表
        """
        try:
            # 使用Neo4j的图查询功能从节点关联查找记忆
            # 1. 通过节点名称匹配查找相关节点 
            # 2. 再通过节点查找关联记忆
            cypher_query = """
                MATCH (n:CognitiveNode)-[:RELATED_TO]-(m:Memory)
                WHERE 
                    (n.conv_id = $conv_id OR $conv_id IS NULL) AND
                    n.name =~ $query_pattern
                RETURN DISTINCT m
                ORDER BY m.weight DESC, m.last_accessed DESC
                LIMIT $limit
            """
            
            # 构建正则表达式模式 (不区分大小写)
            query_pattern = f"(?i).*{query}.*"
            
            # 执行查询
            params = {
                "conv_id": conv_id,
                "query_pattern": query_pattern,
                "limit": limit
            }
            
            results, meta = await self.memory_repo.run_cypher(cypher_query, params)
            
            # 将结果转换为字典
            memories = []
            for row in results:
                memory = Memory.inflate(row[0])
                memories.append({
                    "id": memory.uid,
                    "title": memory.title,
                    "content": memory.content,
                    "weight": memory.weight,
                    "created_at": memory.created_at.timestamp() if memory.created_at else datetime.now().timestamp()
                })
                
            # 如果没有足够的结果，尝试查找间接关联记忆
            if len(memories) < limit:
                additional_limit = limit - len(memories)
                indirect_memories = await self._search_indirect_memories(query, additional_limit, conv_id, [m["id"] for m in memories])
                memories.extend(indirect_memories)
                
            return memories
        except Exception as e:
            logging.error(f"通过节点搜索记忆失败: {e}")
            return []
            
    async def _search_indirect_memories(self, query: str, limit: int, conv_id: Optional[str], excluded_ids: List[str]) -> List[Dict]:
        """搜索间接关联记忆 (通过节点关联)

        Args:
            query: 搜索查询
            limit: 数量限制
            conv_id: 会话ID
            excluded_ids: 要排除的记忆ID列表

        Returns:
            记忆列表
        """
        try:
            # 使用Neo4j图查询查找2级间接关联
            # 1. 找到节点名称匹配的节点 n1
            # 2. 找到与n1关联的节点 n2
            # 3. 找到与n2关联的记忆
            cypher_query = """
                MATCH (n1:CognitiveNode)-[:ASSOCIATED_WITH]-(n2:CognitiveNode)-[:RELATED_TO]-(m:Memory)
                WHERE 
                    (n1.conv_id = $conv_id OR $conv_id IS NULL) AND
                    n1.name =~ $query_pattern AND
                    NOT(m.uid IN $excluded_ids)
                RETURN DISTINCT m
                ORDER BY m.weight DESC, m.last_accessed DESC
                LIMIT $limit
            """
            
            # 构建正则表达式模式 (不区分大小写)
            query_pattern = f"(?i).*{query}.*"
            
            # 执行查询
            params = {
                "conv_id": conv_id,
                "query_pattern": query_pattern,
                "excluded_ids": excluded_ids,
                "limit": limit
            }
            
            results, meta = await self.memory_repo.run_cypher(cypher_query, params)
            
            # 将结果转换为字典
            memories = []
            for row in results:
                memory = Memory.inflate(row[0])
                memories.append({
                    "id": memory.uid,
                    "title": memory.title,
                    "content": memory.content,
                    "weight": memory.weight,
                    "created_at": memory.created_at.timestamp() if memory.created_at else datetime.now().timestamp()
                })
                
            return memories
        except Exception as e:
            logging.error(f"搜索间接关联记忆失败: {e}")
            return [] 