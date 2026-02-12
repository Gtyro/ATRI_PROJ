"""记忆相关接口定义。"""

from typing import Any, Dict, List, Protocol


class ShortTermMemoryPort(Protocol):
    async def add_message(self, message_data: Dict[str, Any]) -> None:
        ...

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        ...

    async def mark_processed(self, conv_id: str, topics: List[Dict[str, Any]]) -> int:
        ...

    async def get_recent_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        ...

    async def add_bot_message(self, conv_id: str, content: str) -> None:
        ...

    async def clear_messages(self, conv_id: str) -> int:
        ...


class LongTermMemoryPort(Protocol):
    async def store_memories(self, conv_id: str, memories: List[Dict[str, Any]]) -> List[str]:
        ...
