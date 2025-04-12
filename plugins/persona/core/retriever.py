import logging
from typing import Dict, List, Optional, Any

from ..storage.repository import Repository

class MemoryRetriever:
    """记忆检索器
    
    负责从长期记忆中检索相关内容
    """
    
    def __init__(self, repository: Repository):
        """初始化记忆检索器
        
        Args:
            repository: 存储仓库
        """
        self.repository = repository
        logging.info("记忆检索器已创建")
    
    async def search_for_memories(self, query: str, user_id: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """搜索相关记忆
        
        Args:
            query: 搜索查询
            user_id: 用户ID，用于个性化搜索
            limit: 返回结果数量限制
            
        Returns:
            相关记忆列表
        """
        # 目前只实现简单的关键词匹配，未来可以改进为向量搜索
        results = []
        
        # 1. 搜索话题
        topics = await self._search_topics(query, limit)
        if topics:
            results.extend(topics)
        
        # 2. 搜索关键词
        nodes = await self._search_nodes(query, limit)
        if nodes:
            results.extend(nodes)
        
        # 3. 按重要性排序
        results.sort(key=lambda x: x.get("importance", 0), reverse=True)
        
        # 4. 限制结果数量
        return results[:limit]
    
    async def _search_topics(self, query: str, limit: int) -> List[Dict]:
        """搜索相关话题
        
        Args:
            query: 搜索查询
            limit: 数量限制
            
        Returns:
            话题列表
        """
        # 简单实现，后续可以改进
        all_memories = []
        
        # 查询所有话题
        distinct_conv_ids = await self.repository.get_distinct_conv_ids()
        for conv_id in distinct_conv_ids:
            memories = await self.repository.get_memories_by_conv(conv_id)
            all_memories.extend(memories)
        
        # 简单关键词匹配
        results = []
        for memory in all_memories:
            # 在标题、摘要和内容中搜索关键词
            if (query.lower() in memory.title.lower() or 
                query.lower() in memory.content.lower()):
                results.append({
                    "id": str(memory.id),
                    "type": "memory",
                    "title": memory.title,
                    "summary": memory.content,
                    "importance": memory.weight,
                    "created_at": memory.created_at.timestamp()
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    async def _search_nodes(self, query: str, limit: int) -> List[Dict]:
        """搜索相关关键词
        
        Args:
            query: 搜索查询
            limit: 数量限制
            
        Returns:
            节点列表
        """
        # 获取所有认知节点
        nodes = await self.repository.get_nodes()
        # 直接节点的memories
        memories = [node.memories for node in nodes]
        # 通过关联模型获取间接节点的memories
        indirect_nodes = []
        for node in nodes:
            indirect_nodes.extend(await self.repository.get_related_nodes(node.id))
        # 合并直接和间接节点的memories
        all_memories = memories + [node.memories for node in indirect_nodes]
        
        # 简单关键词匹配
        results = []
        for memory in all_memories:
            # 在名称中搜索关键词
            if query.lower() in memory.name.lower():
                results.append({
                    "id": str(memory.id),
                    "type": "node",
                    "name": memory.name,
                    "weight": memory.weight
                })
                
                if len(results) >= limit:
                    break
        
        return results 