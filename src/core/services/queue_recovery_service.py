"""短期记忆队列恢复服务。"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List

from ..ports.memory import ShortTermMemoryPort

RecentMessageLoader = Callable[[str, int], Awaitable[List[Dict[str, Any]]]]


class QueueRecoveryService:
    """基于基础消息表重建 Persona 短期队列。"""

    def __init__(
        self,
        short_term: ShortTermMemoryPort,
        queue_history_size: int,
        recent_loader: RecentMessageLoader,
    ) -> None:
        self.short_term = short_term
        self.queue_history_size = queue_history_size
        self.recent_loader = recent_loader

    async def rebuild_from_basic_messages(self, conv_id: str) -> Dict[str, int]:
        recent_messages = await self.recent_loader(conv_id, self.queue_history_size)
        normalized_messages = [self._normalize_message(conv_id, item) for item in recent_messages]
        normalized_messages = [item for item in normalized_messages if item is not None]

        if not normalized_messages:
            return {
                "source_count": 0,
                "cleared": 0,
                "restored": 0,
            }

        cleared = await self.short_term.clear_messages(conv_id)
        restored = 0
        for message_data in normalized_messages:
            await self.short_term.add_message(message_data)
            restored += 1

        return {
            "source_count": len(normalized_messages),
            "cleared": cleared,
            "restored": restored,
        }

    @staticmethod
    def _normalize_message(conv_id: str, item: Dict[str, Any]) -> Dict[str, Any] | None:
        content = str(item.get("content") or "").strip()
        if not content:
            return None

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        normalized: Dict[str, Any] = {
            "conv_id": conv_id,
            "user_id": str(item.get("user_id") or ""),
            "user_name": str(item.get("user_name") or ""),
            "content": content,
            "is_direct": bool(item.get("is_direct", False)),
            "is_bot": bool(item.get("is_bot", False)),
            "is_processed": bool(item.get("is_processed", False)),
            "metadata": metadata,
        }

        created_at = item.get("created_at")
        if created_at is not None:
            normalized["created_at"] = created_at

        return normalized
