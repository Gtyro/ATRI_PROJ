import logging
from typing import Dict, List, Optional, Any

from ..storage.repository import Repository

class LongTermRetriever:
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
        # 目前只实现简单的关键词匹配，未来可以改进为向量搜索
        results = []
        
        # 1. 搜索话题
        topics = await self._search_topics(query, limit, conv_id)
        if topics:
            # 添加source标记
            for topic in topics:
                topic['source'] = 'topic'
            results.extend(topics)
        
        # 2. 通过关键词搜索记忆
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
        
        # 4. 按重要性排序
        results.sort(key=lambda x: x['weight'], reverse=True)
        
        # 5. 限制结果数量
        return results[:limit]
    
    async def _search_topics(self, query: str, limit: int, conv_id: str) -> List[Dict]:
        """搜索相关话题
        
        Args:
            query: 搜索查询
            limit: 数量限制
            conv_id: 会话ID，用于限制搜索范围
            
        Returns:
            话题列表
        """
        # 简单实现，后续可以改进
        all_memories = []
        
        # 只查询当前会话的记忆
        memories = await self.repository.get_memories_by_conv(conv_id)
        all_memories.extend(memories)
        
        # 简单关键词匹配
        results = []
        for memory in all_memories:
            # 在标题、摘要和内容中搜索关键词
            if (query.lower() in memory.title.lower() or 
                query.lower() in memory.content.lower()):
                results.append({
                    "id": memory.id,
                    "title": memory.title,
                    "content": memory.content,
                    "weight": memory.weight,
                    "created_at": memory.created_at.timestamp()
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    async def _search_nodes(self, query: str, limit: int, conv_id: Optional[str] = None) -> List[Dict]:
        """搜索相关关键词
        
        Args:
            query: 搜索查询
            limit: 数量限制
            conv_id: 会话ID，用于限制搜索范围
            
        Returns:
            节点列表
        """
        # 获取所有认知节点（如果指定了conv_id，则只获取特定会话的节点）
        nodes = await self.repository.get_nodes(conv_id=conv_id)
        # 直接节点的memories
        memories = []
        for node in nodes:
            memories.extend(await node.memories.all())
        # 通过关联模型获取间接节点的memories
        indirect_nodes = []
        for node in nodes:
            related_nodes = await self.repository.get_related_nodes(node.id)
            indirect_nodes.extend(related_nodes)
        # 合并直接和间接节点的memories
        indirect_memories = []
        for node in indirect_nodes:
            indirect_memories.extend(await node.memories.all())
        all_memories = memories + indirect_memories
        
        # 简单关键词匹配（修复：添加对查询词的过滤）
        results = []
        for memory in all_memories:
            # 添加关键词匹配过滤
            if (query.lower() in memory.title.lower() or 
                query.lower() in memory.content.lower()):
                results.append({
                    "id": memory.id,
                    "title": memory.title,
                    "content": memory.content,
                    "weight": memory.weight,
                    "created_at": memory.created_at.timestamp()
                })
                
                if len(results) >= limit:
                    break
        
        return results 