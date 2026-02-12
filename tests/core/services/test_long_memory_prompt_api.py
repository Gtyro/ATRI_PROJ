import asyncio
import inspect

import pytest

from src.adapters.persona.ports_adapters import LLMProviderAdapter
from src.core.services.message_processor import MessageProcessor
from src.infra.llm.providers.ai_processor import AIProcessor
from src.infra.llm.providers.fallback import FallbackLLMProvider


class _FakeProvider:
    def __init__(self):
        self.history_keyword_calls = []
        self.memory_retrieval_callback = None

    async def extract_topics(self, conv_id, messages):
        return []

    async def extract_reply_keywords_from_history(self, conv_id, messages):
        self.history_keyword_calls.append((conv_id, list(messages)))
        return ["张三", "项目A"]

    async def generate_response(
        self,
        conv_id,
        messages,
        temperature=0.7,
        long_memory_prompt="",
        tool_choice="required",
    ):
        return "ok"


@pytest.mark.parametrize(
    "callable_obj",
    [
        MessageProcessor.generate_reply,
        AIProcessor.generate_response,
        FallbackLLMProvider.generate_response,
        LLMProviderAdapter.generate_response,
    ],
)
def test_generate_response_interfaces_remove_legacy_typo_param(callable_obj):
    assert "long_memory_promt" not in inspect.signature(callable_obj).parameters


def test_message_processor_rejects_legacy_typo_param():
    processor = MessageProcessor(
        config={"queue_history_size": 20},
        llm_provider=_FakeProvider(),
    )

    with pytest.raises(TypeError):
        asyncio.run(
            processor.generate_reply(
                "group_1",
                [],
                long_memory_promt="legacy",
            )
        )


def test_message_processor_extract_reply_keywords_from_history():
    provider = _FakeProvider()
    processor = MessageProcessor(
        config={"queue_history_size": 20},
        llm_provider=provider,
    )
    messages = [{"user_name": "Alice", "content": "你还记得张三吗？", "is_bot": False, "is_direct": False}]

    keywords = asyncio.run(processor.extract_reply_keywords_from_history("group_1", messages))

    assert keywords == ["张三", "项目A"]
    assert provider.history_keyword_calls == [("group_1", messages)]


def test_message_processor_retrieve_memory_context_requires_keyword_signature():
    provider = _FakeProvider()
    processor = MessageProcessor(
        config={"queue_history_size": 20},
        llm_provider=provider,
    )

    def legacy_positional_callback(a, b, c):
        return "legacy"

    provider.memory_retrieval_callback = legacy_positional_callback
    context = asyncio.run(processor.retrieve_memory_context("group_1", ["张三"]))

    assert context == ""
