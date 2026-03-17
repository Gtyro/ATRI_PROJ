"""核心 Ports 的适配器实现。"""

from typing import Any, Dict, List

from src.core.ports import LLMProvider, LongTermMemoryPort, ShortTermMemoryPort


class ShortTermMemoryAdapter(ShortTermMemoryPort):
    """短期记忆适配器。"""

    def __init__(self, impl: Any) -> None:
        self._impl = impl

    def __getattr__(self, name: str) -> Any:
        return getattr(self._impl, name)

    async def add_message(self, message_data: Dict[str, Any]) -> None:
        await self._impl.add_message(message_data)

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        return await self._impl.get_unprocessed_messages(conv_id, limit)

    async def mark_processed(self, conv_id: str, topics: List[Dict[str, Any]]) -> int:
        return await self._impl.mark_processed(conv_id, topics)

    async def get_recent_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        return await self._impl.get_recent_messages(conv_id, limit)

    async def add_bot_message(self, conv_id: str, content: str) -> None:
        await self._impl.add_bot_message(conv_id, content)

    async def clear_messages(self, conv_id: str) -> int:
        return await self._impl.clear_messages(conv_id)


class LongTermMemoryAdapter(LongTermMemoryPort):
    """长期记忆适配器。"""

    def __init__(self, impl: Any) -> None:
        self._impl = impl

    def __getattr__(self, name: str) -> Any:
        return getattr(self._impl, name)

    async def store_memories(self, conv_id: str, memories: List[Dict[str, Any]]) -> List[str]:
        return await self._impl.store_memories(conv_id, memories)


class LLMProviderAdapter(LLMProvider):
    """LLM 提供者适配器。"""

    def __init__(self, impl: Any) -> None:
        self._impl = impl

    def __getattr__(self, name: str) -> Any:
        return getattr(self._impl, name)

    async def extract_topics(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return await self._impl.extract_topics(conv_id, messages)

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        return await self._impl.extract_reply_keywords_from_history(conv_id, messages)

    async def generate_response(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        return await self._impl.generate_response(
            conv_id=conv_id,
            messages=messages,
            temperature=temperature,
            long_memory_prompt=long_memory_prompt,
            tool_choice=tool_choice,
        )

    async def select_memory_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[str]:
        return await self._impl.select_memory_candidates(query, candidates)
