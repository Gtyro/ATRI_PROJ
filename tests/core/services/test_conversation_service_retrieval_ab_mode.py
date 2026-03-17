import asyncio
import logging
from typing import Any, Dict, List

import pytest

from src.core.services.conversation_service import ConversationService


class _ShortTermStub:
    def __init__(self, messages: List[Dict[str, Any]]):
        self._messages = list(messages)
        self.bot_messages: List[str] = []

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        return list(self._messages)

    async def mark_processed(self, conv_id: str, topics: List[Dict[str, Any]]) -> int:
        return 0

    async def get_recent_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        return list(self._messages)

    async def add_bot_message(self, conv_id: str, content: str) -> None:
        self.bot_messages.append(content)

    async def add_message(self, message_data: Dict[str, Any]) -> None:
        return None


class _LongTermStub:
    async def store_memories(self, conv_id: str, memories: List[Dict[str, Any]]) -> List[str]:
        return []


class _MessageRepoStub:
    async def has_bot_message(self, conv_id: str) -> bool:
        return False


class _GroupConfigEntry:
    def __init__(self):
        self.plugin_config: Dict[str, Any] = {}
        self.saved = 0

    async def save(self) -> None:
        self.saved += 1


class _GroupConfigStub:
    def __init__(self):
        self.entry = _GroupConfigEntry()

    async def get_config(self, group_id: str, plugin_name: str) -> _GroupConfigEntry:
        return self.entry


class _Policy:
    def __init__(self, config: Dict[str, Any]):
        self.config = config


class _PolicyServiceStub:
    def __init__(self, config: Dict[str, Any]):
        self._policy = _Policy(config)

    async def is_enabled(self, group_id: str, plugin_name: str) -> bool:
        return True

    async def is_ingest_enabled(self, group_id: str, plugin_name: str) -> bool:
        return True

    async def get_policy(self, group_id: str, plugin_name: str) -> _Policy:
        return self._policy


class _ImageContextServiceStub:
    async def build_context(self, conv_id: str, recent_messages: List[Dict[str, Any]]) -> str:
        return "图片上下文"


class _MessageProcessorStub:
    def __init__(self, *, memory_context: str = "我记得这些内容:\n1. [群聊]【张三】他最近在做项目A"):
        self.retrieve_calls: List[List[str]] = []
        self.retrieve_payload_calls: List[List[str]] = []
        self.reinforce_calls: List[Dict[str, Any]] = []
        self.last_long_memory_prompt = ""
        self.last_tool_choice = ""
        self.history_keyword_calls = 0
        self.memory_context = memory_context

    async def extract_topics_from_messages(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return []

    async def should_respond(self, conv_id: str, topics: List[Dict[str, Any]]) -> bool:
        return True

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        self.history_keyword_calls += 1
        return ["张三", "项目A"]

    async def retrieve_memory_context(self, conv_id: str, keywords: List[str]) -> str:
        self.retrieve_calls.append(list(keywords))
        return self.memory_context

    async def retrieve_memory_context_payload(self, conv_id: str, keywords: List[str]) -> Dict[str, Any]:
        self.retrieve_payload_calls.append(list(keywords))
        self.retrieve_calls.append(list(keywords))
        return {
            "query": " ".join(keywords),
            "memory_context": self.memory_context,
            "selected_ids": [],
        }

    async def reinforce_memory_selection(
        self,
        conv_id: str,
        query: str,
        selected_ids: List[str],
    ) -> None:
        self.reinforce_calls.append({
            "conv_id": conv_id,
            "query": query,
            "selected_ids": list(selected_ids),
        })

    async def generate_reply(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        self.last_long_memory_prompt = long_memory_prompt
        self.last_tool_choice = tool_choice
        return "收到"


def _build_service(*, retrieval_ab_mode: str, msgprocessor: _MessageProcessorStub) -> ConversationService:
    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "content": "你还记得张三最近在做什么吗？",
            "is_bot": False,
            "is_direct": False,
        }
    ]
    return ConversationService(
        short_term=_ShortTermStub(messages),
        long_term=_LongTermStub(),
        msgprocessor=msgprocessor,
        message_repo=_MessageRepoStub(),
        group_config=_GroupConfigStub(),
        plugin_name="persona",
        config={
            "queue_history_size": 1,
            "batch_interval": 1800,
            "image_understanding": {
                "enabled": True,
                "retrieval_ab_mode": retrieval_ab_mode,
            },
        },
        plugin_policy_service=_PolicyServiceStub(
            {
                "llm_topic_extract_enabled": False,
                "llm_active_reply_enabled": True,
                "llm_passive_reply_enabled": False,
            }
        ),
        image_context_service=_ImageContextServiceStub(),
    )


def test_unknown_retrieval_ab_mode_raises_value_error():
    service = _build_service(retrieval_ab_mode="ab_split", msgprocessor=_MessageProcessorStub())

    with pytest.raises(ValueError):
        asyncio.run(service.process_conversation("group_42", user_id="10001", is_direct=False))


def test_hybrid_mode_injects_explicit_memory_into_long_memory_prompt():
    processor = _MessageProcessorStub()
    service = _build_service(retrieval_ab_mode="hybrid", msgprocessor=processor)

    result = asyncio.run(service.process_conversation("group_42", user_id="10001", is_direct=False))

    assert result is not None
    assert processor.history_keyword_calls == 1
    assert processor.retrieve_calls == [["张三", "项目A"]]
    assert "图片上下文" in processor.last_long_memory_prompt
    assert "显式检索到的历史记忆" in processor.last_long_memory_prompt
    assert "我记得这些内容" in processor.last_long_memory_prompt
    assert processor.last_tool_choice == "none"


def test_tool_only_mode_skips_explicit_memory_injection():
    processor = _MessageProcessorStub()
    service = _build_service(retrieval_ab_mode="tool_only", msgprocessor=processor)

    result = asyncio.run(service.process_conversation("group_43", user_id="10002", is_direct=False))

    assert result is not None
    assert processor.retrieve_calls == []
    assert processor.history_keyword_calls == 0
    assert processor.last_long_memory_prompt == "图片上下文"
    assert processor.last_tool_choice == "required"


def test_hybrid_mode_without_memory_hit_keeps_no_tool_choice():
    processor = _MessageProcessorStub(memory_context="我似乎没有关于这方面的记忆")
    service = _build_service(retrieval_ab_mode="hybrid", msgprocessor=processor)

    result = asyncio.run(service.process_conversation("group_44", user_id="10003", is_direct=False))

    assert result is not None
    assert processor.retrieve_calls == [["张三", "项目A"]]
    assert processor.last_long_memory_prompt == "图片上下文"
    assert processor.last_tool_choice == "none"


def test_observability_logs_include_ab_mode_keyword_count_and_memory_hit_count(caplog):
    processor = _MessageProcessorStub()
    service = _build_service(retrieval_ab_mode="hybrid", msgprocessor=processor)

    with caplog.at_level(logging.INFO):
        result = asyncio.run(service.process_conversation("group_45", user_id="10004", is_direct=False))

    assert result is not None
    assert "ab_mode=hybrid" in caplog.text
    assert "keyword_count=2" in caplog.text
    assert "memory_hit_count=1" in caplog.text


def test_observability_logs_report_zero_memory_hit_when_tool_only(caplog):
    processor = _MessageProcessorStub()
    service = _build_service(retrieval_ab_mode="tool_only", msgprocessor=processor)

    with caplog.at_level(logging.INFO):
        result = asyncio.run(service.process_conversation("group_46", user_id="10005", is_direct=False))

    assert result is not None
    assert "ab_mode=tool_only" in caplog.text
    assert "keyword_count=0" in caplog.text
    assert "memory_hit_count=0" in caplog.text
