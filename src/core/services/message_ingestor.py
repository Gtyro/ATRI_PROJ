"""消息入口统一处理。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.core.events import Event, EventBus, MessagePayload, MESSAGE_RECEIVED


class MessageIngestor:
    """统一消息入口，将消息标准化后发布事件。"""

    def __init__(self, event_bus: EventBus, source: str = "unknown") -> None:
        self.event_bus = event_bus
        self.source = source

    async def ingest(self, message_data: Dict[str, Any], *, raw_event: Any = None) -> MessagePayload:
        payload = self._normalize_message(message_data, raw_event=raw_event)
        await self.event_bus.publish(Event(name=MESSAGE_RECEIVED, payload=payload))
        return payload

    def _normalize_message(
        self,
        message_data: Dict[str, Any],
        *,
        raw_event: Any = None,
    ) -> MessagePayload:
        metadata = message_data.get("metadata")
        if metadata is None:
            metadata = message_data.get("extra_data") or {}
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}

        metadata = dict(metadata)
        metadata.setdefault("source", self.source)

        created_at: Optional[datetime] = message_data.get("created_at")
        return MessagePayload(
            conv_id=message_data["conv_id"],
            user_id=message_data["user_id"],
            user_name=message_data.get("user_name", ""),
            content=message_data.get("content", ""),
            is_direct=bool(message_data.get("is_direct", False)),
            is_bot=bool(message_data.get("is_bot", False)),
            is_processed=bool(message_data.get("is_processed", False)),
            metadata=metadata,
            created_at=created_at,
            raw_event=raw_event,
        )
