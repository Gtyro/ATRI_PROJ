"""Persona 对外门面，隔离实现与插件依赖。"""

from typing import Any, Callable, Dict, List, Optional

from ..ports.persona_engine import PersonaEngine


class PersonaFacade:
    """对外统一入口，封装 Persona 引擎实现。"""

    def __init__(self, engine: PersonaEngine):
        self._engine = engine

    async def initialize(self, reply_callback: Optional[Callable] = None) -> bool:
        return await self._engine.initialize(reply_callback=reply_callback)

    async def close(self) -> None:
        await self._engine.close()

    async def process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self._engine.process_message(message_data)

    async def process_conversation(
        self,
        conv_id: str,
        user_id: str,
        is_direct: bool = False,
    ) -> Optional[Dict[str, Any]]:
        return await self._engine.process_conversation(conv_id, user_id, is_direct=is_direct)

    async def schedule_maintenance(self) -> None:
        await self._engine.schedule_maintenance()

    def get_queue_history_size(self) -> int:
        return self._engine.get_queue_history_size()

    async def extract_topics_from_messages(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return await self._engine.extract_topics_from_messages(conv_id, messages)

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        return await self._engine.extract_reply_keywords_from_history(conv_id, messages)

    async def retrieve_related_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        conv_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._engine.retrieve_related_memories(
            query,
            user_id=user_id,
            limit=limit,
            conv_id=conv_id,
        )

    async def get_queue_status_reply(self, conv_id: Optional[str] = None) -> str:
        return await self._engine.get_queue_status_reply(conv_id)

    async def clear_queue(self, conv_id: str) -> int:
        return await self._engine.clear_queue(conv_id)

    async def set_group_prompt_file(self, group_id: str, prompt_file: str) -> None:
        await self._engine.set_group_prompt_file(group_id, prompt_file)

    async def simulate_reply(
        self,
        conv_id: str,
        test_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self._engine.simulate_reply(conv_id, test_message=test_message)

    async def create_permanent_memory(
        self,
        conv_id: str,
        node_name: str,
        memory_title: str,
        memory_content: str,
    ) -> Dict[str, Any]:
        return await self._engine.create_permanent_memory(
            conv_id,
            node_name,
            memory_title,
            memory_content,
        )

    async def format_memories(self, query: str, user_id: str, conv_id: str) -> str:
        return await self._engine.format_memories(query, user_id, conv_id)

    async def parse_chat_history(
        self,
        bot_id: str,
        file_path: str,
        conv_id: str,
    ) -> List[Dict[str, Any]]:
        return await self._engine.parse_chat_history(bot_id, file_path, conv_id)
