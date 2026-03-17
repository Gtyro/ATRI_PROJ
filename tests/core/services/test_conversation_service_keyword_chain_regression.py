import asyncio
from typing import Any, Dict, List, Optional

from src.core.services.conversation_service import ConversationService
from src.core.services.message_processor import MessageProcessor
from src.infra.llm.providers.fallback import FallbackLLMProvider


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


class _ProviderStub:
    def __init__(
        self,
        *,
        name: str,
        history_keywords: Optional[List[str]] = None,
        selected_memory_ids: Optional[List[str]] = None,
        history_error: Optional[Exception] = None,
        selection_error: Optional[Exception] = None,
        response_text: str = "收到",
    ):
        self.provider_name = name
        self.history_keywords = list(history_keywords or [])
        self.selected_memory_ids = list(selected_memory_ids or [])
        self.history_error = history_error
        self.selection_error = selection_error
        self.response_text = response_text
        self.history_calls = 0
        self.selection_calls = 0
        self.generate_calls = 0
        self.last_long_memory_prompt = ""
        self.last_tool_choice = ""

    async def extract_topics(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return []

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        self.history_calls += 1
        if self.history_error is not None:
            raise self.history_error
        return list(self.history_keywords)

    async def generate_response(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        self.generate_calls += 1
        self.last_long_memory_prompt = long_memory_prompt
        self.last_tool_choice = tool_choice
        return self.response_text

    async def select_memory_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[str]:
        self.selection_calls += 1
        if self.selection_error is not None:
            raise self.selection_error
        return list(self.selected_memory_ids)


def _build_service(
    *,
    primary: _ProviderStub,
    secondary: _ProviderStub,
) -> tuple[ConversationService, FallbackLLMProvider]:
    fallback_provider = FallbackLLMProvider([primary, secondary])
    msgprocessor = MessageProcessor(
        config={"queue_history_size": 20},
        llm_provider=fallback_provider,
    )

    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "content": "你还记得张三最近在做什么吗？",
            "is_bot": False,
            "is_direct": True,
        }
    ]
    service = ConversationService(
        short_term=_ShortTermStub(messages),
        long_term=_LongTermStub(),
        msgprocessor=msgprocessor,
        message_repo=_MessageRepoStub(),
        group_config=_GroupConfigStub(),
        plugin_name="persona",
        config={
            "queue_history_size": 20,
            "batch_interval": 1800,
            "image_understanding": {
                "enabled": False,
                "retrieval_ab_mode": "hybrid",
            },
        },
        plugin_policy_service=_PolicyServiceStub(
            {
                "llm_topic_extract_enabled": False,
                "llm_active_reply_enabled": False,
                "llm_passive_reply_enabled": True,
            }
        ),
        image_context_service=None,
    )
    return service, fallback_provider


def _resolve_reply_provider(primary: _ProviderStub, secondary: _ProviderStub) -> _ProviderStub:
    return primary if primary.generate_calls > 0 else secondary


def test_keyword_chain_provider_fallback_keeps_hybrid_memory_injection():
    primary = _ProviderStub(
        name="primary",
        history_error=RuntimeError("primary unavailable"),
        selection_error=RuntimeError("primary unavailable"),
    )
    secondary = _ProviderStub(
        name="secondary",
        history_keywords=["张三", "项目A"],
    )
    service, fallback_provider = _build_service(primary=primary, secondary=secondary)
    retrieval_queries: List[str] = []

    def _retrieve_callback(
        query: str,
        user_id: Any = None,
        conv_id: str = "",
        selected_ids: Optional[List[str]] = None,
        reinforce_selected: bool = False,
    ) -> dict:
        retrieval_queries.append(query)
        return {
            "memory_context": "我记得这些内容:\n1. [群聊]【张三】他最近在做项目A",
            "candidates": [],
            "selected_ids": [],
        }

    fallback_provider.set_memory_retrieval_callback(_retrieve_callback)

    result = asyncio.run(service.process_conversation("group_201", user_id="10001", is_direct=True))

    assert result is not None
    assert result["reply_content"] == ["收到"]
    assert primary.history_calls == 1
    assert secondary.history_calls == 1
    assert retrieval_queries == ["张三 项目A"]

    reply_provider = _resolve_reply_provider(primary, secondary)
    assert reply_provider.last_tool_choice == "none"
    assert "显式检索到的历史记忆" in reply_provider.last_long_memory_prompt
    assert "我记得这些内容" in reply_provider.last_long_memory_prompt


def test_keyword_chain_empty_keywords_skips_explicit_retrieval():
    primary = _ProviderStub(name="primary", history_keywords=[])
    secondary = _ProviderStub(name="secondary", history_keywords=["不会触发"])
    service, fallback_provider = _build_service(primary=primary, secondary=secondary)
    retrieval_queries: List[str] = []

    def _retrieve_callback(
        query: str,
        user_id: Any = None,
        conv_id: str = "",
        selected_ids: Optional[List[str]] = None,
        reinforce_selected: bool = False,
    ) -> dict:
        retrieval_queries.append(query)
        return {
            "memory_context": "不应被调用",
            "candidates": [],
            "selected_ids": [],
        }

    fallback_provider.set_memory_retrieval_callback(_retrieve_callback)

    result = asyncio.run(service.process_conversation("group_202", user_id="10002", is_direct=True))

    assert result is not None
    assert primary.history_calls == 1
    assert secondary.history_calls == 0
    assert retrieval_queries == []

    reply_provider = _resolve_reply_provider(primary, secondary)
    assert reply_provider.last_long_memory_prompt == ""
    assert reply_provider.last_tool_choice == "none"


def test_hybrid_selected_memories_are_reinforced_after_reply():
    primary = _ProviderStub(
        name="primary",
        history_error=RuntimeError("primary unavailable"),
        selection_error=RuntimeError("primary unavailable"),
    )
    secondary = _ProviderStub(
        name="secondary",
        history_keywords=["张三", "项目A"],
        selected_memory_ids=["mem-2"],
    )
    service, fallback_provider = _build_service(primary=primary, secondary=secondary)
    callback_calls: List[Dict[str, Any]] = []

    def _retrieve_callback(
        query: str,
        user_id: Any = None,
        conv_id: str = "",
        selected_ids: Optional[List[str]] = None,
        reinforce_selected: bool = False,
    ) -> dict:
        callback_calls.append({
            "query": query,
            "conv_id": conv_id,
            "selected_ids": list(selected_ids or []),
            "reinforce_selected": reinforce_selected,
        })
        if selected_ids:
            return {
                "memory_context": "我记得这些内容:\n1. [群聊]【项目A】项目A延期到下周",
                "candidates": [],
                "selected_ids": list(selected_ids),
            }
        return {
            "memory_context": "我记得这些内容:\n1. [群聊]【张三】他最近在做项目A",
            "candidates": [
                {
                    "id": "mem-1",
                    "title": "张三",
                    "summary": "张三最近在做项目A",
                    "source": "topic",
                    "weight": 1.2,
                    "created_at": 1742205600.0,
                },
                {
                    "id": "mem-2",
                    "title": "项目A",
                    "summary": "项目A延期到下周",
                    "source": "topic",
                    "weight": 1.0,
                    "created_at": 1742205601.0,
                },
            ],
            "selected_ids": [],
        }

    fallback_provider.set_memory_retrieval_callback(_retrieve_callback)

    result = asyncio.run(service.process_conversation("group_203", user_id="10003", is_direct=True))

    assert result is not None
    assert result["reply_content"] == ["收到"]
    reply_provider = _resolve_reply_provider(primary, secondary)
    assert "【项目A】项目A延期到下周" in reply_provider.last_long_memory_prompt
    assert callback_calls == [
        {
            "query": "张三 项目A",
            "conv_id": "group_203",
            "selected_ids": [],
            "reinforce_selected": False,
        },
        {
            "query": "张三 项目A",
            "conv_id": "group_203",
            "selected_ids": ["mem-2"],
            "reinforce_selected": False,
        },
        {
            "query": "张三 项目A",
            "conv_id": "group_203",
            "selected_ids": ["mem-2"],
            "reinforce_selected": True,
        },
    ]
