"""记忆相关服务。"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


class MemoryService:
    """负责记忆检索、格式化与常驻记忆创建。"""

    def __init__(self, memory_repo: Any, retriever: Any) -> None:
        self.memory_repo = memory_repo
        self.retriever = retriever

    async def retrieve_related_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        conv_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        keywords = query.split(" ")
        memory_list: List[Dict[str, Any]] = []
        for keyword in keywords:
            memory_list.extend(await self.retriever.search_for_memories(keyword, user_id, limit, conv_id))
        return memory_list

    async def format_memories(self, query: str, user_id: str, conv_id: str) -> str:
        related_memories = await self.retrieve_related_memories(query, user_id, conv_id=conv_id)

        if not related_memories:
            return "我似乎没有关于这方面的记忆..."

        reply = "我记得这些内容:\n"
        for i, memory in enumerate(related_memories, 1):
            memory_source = memory.get("source", "未知")
            title = memory.get("title", "无标题")
            content = memory.get("content", "无内容")
            time_str = datetime.fromtimestamp(memory.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
            reply += f"{i}. [{memory_source}]【{title}】{content} ({time_str})\n"

        return reply

    async def create_permanent_memory(
        self,
        conv_id: str,
        node_name: str,
        memory_title: str,
        memory_content: str,
    ) -> Dict[str, Any]:
        try:
            node = await self.memory_repo.update_or_create_node(conv_id, node_name, is_permanent=True)
            memory_data = {
                "conv_id": conv_id,
                "title": memory_title,
                "content": memory_content,
                "is_permanent": True,
            }
            memory = await self.memory_repo.store_memory(conv_id, memory_data)
            await self.memory_repo._link_nodes_to_memory(memory, [str(node.uid)])

            logging.info(f"创建常驻节点-记忆对: 节点[{node_name}], 记忆[{memory_title}]")

            return {
                "node": {
                    "id": str(node.uid),
                    "name": node.name,
                    "is_permanent": node.is_permanent,
                },
                "memory": {
                    "id": str(memory.uid),
                    "title": memory.title,
                    "content": memory.content,
                    "is_permanent": memory.is_permanent,
                },
            }
        except Exception as e:
            logging.error(f"创建常驻节点-记忆对失败: {e}")
            raise
