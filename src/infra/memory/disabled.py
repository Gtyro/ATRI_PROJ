"""Neo4j 不可用时的人格长期记忆降级实现。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class DisabledLongTermMemory:
    """禁用长期记忆写入，但保持会话处理链可继续运行。"""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "").strip() or "Neo4j 当前不可用"

    def is_available(self) -> bool:
        return False

    async def store_memories(self, conv_id: str, memories: List[Dict[str, Any]]) -> List[str]:
        stored_ids: List[str] = []
        for index, memory in enumerate(memories):
            if not memory.get("completed_status", False):
                continue
            stored_ids.append(f"neo4j-unavailable:{conv_id}:{index}")

        if stored_ids:
            logger.warning(
                "Neo4j 不可用，已跳过长期记忆写入: conv_id=%s count=%s reason=%s",
                conv_id,
                len(stored_ids),
                self.reason,
            )

        return stored_ids


class DisabledLongTermRetriever:
    """禁用长期记忆检索。"""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "").strip() or "Neo4j 当前不可用"

    def is_available(self) -> bool:
        return False

    async def search_for_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        conv_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return []


class DisabledDecayManager:
    """禁用长期记忆衰减。"""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "").strip() or "Neo4j 当前不可用"

    def is_available(self) -> bool:
        return False

    async def initialize(self) -> None:
        logger.warning("Neo4j 不可用，已跳过长期记忆衰减初始化: reason=%s", self.reason)

    async def apply_decay(self, force: bool = False) -> int:
        return 0
