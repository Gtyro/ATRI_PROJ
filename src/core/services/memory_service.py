"""记忆相关服务。"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


class MemoryService:
    """负责记忆检索、格式化与常驻记忆创建。"""

    DEFAULT_MEMORY_LIMIT = 5
    DEFAULT_CANDIDATE_LIMIT = 8
    DEFAULT_RECALL_BOOST = 0.08
    DEFAULT_MAX_WEIGHT = 3.0

    def __init__(self, memory_repo: Any, retriever: Any) -> None:
        self.memory_repo = memory_repo
        self.retriever = retriever

    @staticmethod
    def _build_summary_excerpt(content: str, limit: int = 120) -> str:
        summary = " ".join(str(content or "").split())
        if len(summary) <= limit:
            return summary
        return f"{summary[:limit].rstrip()}..."

    @staticmethod
    def _dedupe_memories(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for memory in memories:
            memory_id = str(memory.get("id", "")).strip()
            if not memory_id:
                continue
            existing = merged.get(memory_id)
            if existing is None:
                merged[memory_id] = dict(memory)
                continue

            if float(memory.get("weight", 0.0) or 0.0) > float(existing.get("weight", 0.0) or 0.0):
                merged[memory_id] = dict(memory)
                continue

            existing_source = str(existing.get("source", "")).strip()
            incoming_source = str(memory.get("source", "")).strip()
            if not existing_source and incoming_source:
                existing["source"] = incoming_source

        return sorted(
            merged.values(),
            key=lambda item: (
                float(item.get("weight", 0.0) or 0.0),
                float(item.get("last_accessed", 0.0) or 0.0),
                float(item.get("created_at", 0.0) or 0.0),
            ),
            reverse=True,
        )

    @staticmethod
    def _normalize_selected_ids(selected_ids: Optional[List[str]]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for selected_id in selected_ids or []:
            memory_id = str(selected_id or "").strip()
            if not memory_id or memory_id in seen:
                continue
            seen.add(memory_id)
            normalized.append(memory_id)
        return normalized

    def _build_candidates(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for memory in memories:
            candidates.append({
                "id": memory.get("id"),
                "title": memory.get("title", "无标题"),
                "summary": self._build_summary_excerpt(memory.get("content", "")),
                "source": memory.get("source", "未知"),
                "weight": float(memory.get("weight", 0.0) or 0.0),
                "created_at": float(memory.get("created_at", 0.0) or 0.0),
            })
        return candidates

    def render_memories(self, memories: List[Dict[str, Any]]) -> str:
        if not memories:
            return "我似乎没有关于这方面的记忆..."

        reply = "我记得这些内容:\n"
        for i, memory in enumerate(memories, 1):
            memory_source = memory.get("source", "未知")
            title = memory.get("title", "无标题")
            content = memory.get("content", "无内容")
            time_str = datetime.fromtimestamp(memory.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
            reply += f"{i}. [{memory_source}]【{title}】{content} ({time_str})\n"
        return reply

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
            normalized_keyword = str(keyword or "").strip()
            if not normalized_keyword:
                continue
            memory_list.extend(
                await self.retriever.search_for_memories(normalized_keyword, user_id, limit, conv_id)
            )
        deduped_memories = self._dedupe_memories(memory_list)
        return deduped_memories[:limit]

    async def retrieve_memory_payload(
        self,
        query: str,
        user_id: Optional[str] = None,
        conv_id: Optional[str] = None,
        *,
        limit: int = DEFAULT_MEMORY_LIMIT,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
        selected_ids: Optional[List[str]] = None,
        reinforce_selected: bool = False,
    ) -> Dict[str, Any]:
        retrieval_limit = max(limit, candidate_limit)
        selected_memory_ids = self._normalize_selected_ids(selected_ids)
        related_memories = await self.retrieve_related_memories(
            query,
            user_id=user_id,
            limit=retrieval_limit,
            conv_id=conv_id,
        )

        context_memories = related_memories[:limit]
        selection_applied = False
        if selected_memory_ids:
            selected_memory_set = set(selected_memory_ids)
            selected_memories = [
                memory for memory in related_memories if str(memory.get("id", "")) in selected_memory_set
            ]
            if selected_memories:
                context_memories = selected_memories[:limit]
                selection_applied = True
                if reinforce_selected:
                    await self.memory_repo.reinforce_memories(
                        [str(memory.get("id", "")) for memory in context_memories],
                        boost=self.DEFAULT_RECALL_BOOST,
                        max_weight=self.DEFAULT_MAX_WEIGHT,
                    )

        return {
            "query": query,
            "memory_context": self.render_memories(context_memories),
            "candidates": self._build_candidates(related_memories[:candidate_limit]),
            "selected_ids": [str(memory.get("id", "")) for memory in context_memories] if selection_applied else [],
            "selection_applied": selection_applied,
        }

    async def format_memories(self, query: str, user_id: str, conv_id: str) -> str:
        payload = await self.retrieve_memory_payload(query, user_id=user_id, conv_id=conv_id)
        return str(payload.get("memory_context", "")).strip() or "我似乎没有关于这方面的记忆..."

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
