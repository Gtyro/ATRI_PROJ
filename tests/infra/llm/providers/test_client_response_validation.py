import asyncio
from types import SimpleNamespace

import pytest

from src.infra.llm.providers.client import LLMClient
from src.infra.llm.providers.errors import LLMProviderError
from src.infra.llm.providers.types import LLMCallParams


class _FakeCompletions:
    def __init__(self, response):
        self._response = response

    async def create(self, **kwargs):
        return self._response


class _FakeOpenAIClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


def _build_client(response) -> LLMClient:
    client = object.__new__(LLMClient)
    client.provider_name = "test_provider"
    client.base_url = "https://example.com"
    client.model = "test-model"
    client.supports_response_format = False
    client.timeout = 30.0
    client._client = _FakeOpenAIClient(response)
    return client


def test_chat_raises_provider_error_when_choices_missing():
    response = SimpleNamespace(
        id="resp_missing_choices",
        object="chat.completion",
        choices=None,
        usage=None,
    )
    client = _build_client(response)

    with pytest.raises(LLMProviderError) as exc_info:
        asyncio.run(
            client.chat(
                messages=[{"role": "user", "content": "hello"}],
                params=LLMCallParams(),
            )
        )

    err = exc_info.value
    assert err.provider == "test_provider"
    assert err.operation == "chat"
    assert err.retryable is True


def test_chat_merges_text_blocks_from_message_content_list():
    response = SimpleNamespace(
        id="resp_content_list",
        object="chat.completion",
        usage=None,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=[
                        {"type": "text", "text": "第一句"},
                        {"type": "tool_result", "text": "第二句"},
                    ]
                )
            )
        ],
    )
    client = _build_client(response)

    result = asyncio.run(
        client.chat(
            messages=[{"role": "user", "content": "describe"}],
            params=LLMCallParams(),
        )
    )

    assert result == "第一句\n第二句"
