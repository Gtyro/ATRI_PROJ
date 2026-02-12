"""LLM 提供者接口定义。"""

from typing import Any, Dict, List, Protocol


class LLMProvider(Protocol):
    async def extract_topics(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        ...

    async def generate_response(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        ...
