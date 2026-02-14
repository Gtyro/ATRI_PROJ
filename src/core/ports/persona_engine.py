"""Persona 引擎抽象接口。"""

from typing import Any, Callable, Dict, List, Optional, Protocol


class PersonaEngine(Protocol):
    """Persona 核心能力接口，用于解耦具体实现。"""

    async def initialize(self, reply_callback: Optional[Callable] = None) -> bool:
        ...

    async def close(self) -> None:
        ...

    async def process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...

    async def process_conversation(
        self,
        conv_id: str,
        user_id: str,
        is_direct: bool = False,
    ) -> Optional[Dict[str, Any]]:
        ...

    async def schedule_maintenance(self) -> None:
        ...

    def get_queue_history_size(self) -> int:
        ...

    async def extract_topics_from_messages(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        ...

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        ...

    async def retrieve_related_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        conv_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...

    async def get_queue_status_reply(self, conv_id: Optional[str] = None) -> str:
        ...

    async def clear_queue(self, conv_id: str) -> int:
        ...

    async def set_group_prompt_file(self, group_id: str, prompt_file: str) -> None:
        ...

    async def simulate_reply(
        self,
        conv_id: str,
        test_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        ...

    async def create_permanent_memory(
        self,
        conv_id: str,
        node_name: str,
        memory_title: str,
        memory_content: str,
    ) -> Dict[str, Any]:
        ...

    async def format_memories(self, query: str, user_id: str, conv_id: str) -> str:
        ...

    async def parse_chat_history(
        self,
        bot_id: str,
        file_path: str,
        conv_id: str,
    ) -> List[Dict[str, Any]]:
        ...
