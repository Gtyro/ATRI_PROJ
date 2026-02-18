import asyncio
from types import SimpleNamespace

import pytest

from src.infra.llm.providers.client import LLMClient
from src.infra.llm.providers.errors import LLMProviderError
from src.infra.llm.providers.types import LLMCallParams


class _FakeCompletions:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error

    async def create(self, **kwargs):
        if self._error is not None:
            raise self._error
        return self._response


class _FakeOpenAIClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response, error=error))


def _build_client(
    response=None,
    *,
    error: Exception | None = None,
    usage_event_callback=None,
) -> LLMClient:
    client = object.__new__(LLMClient)
    client.provider_name = "test_provider"
    client.base_url = "https://example.com"
    client.model = "test-model"
    client.supports_response_format = False
    client.timeout = 30.0
    client._usage_event_callback = usage_event_callback
    client._client = _FakeOpenAIClient(response, error=error)
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


def test_chat_emits_usage_event_on_success_with_context():
    events = []
    response = SimpleNamespace(
        id="resp_success",
        object="chat.completion",
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
    )
    client = _build_client(response, usage_event_callback=events.append)

    result = asyncio.run(
        client.chat(
            messages=[{"role": "user", "content": "hello"}],
            params=LLMCallParams(),
            operation="chat",
            usage_context={
                "plugin_name": "persona",
                "module_name": "image_understanding",
                "operation": "image_understanding",
                "conv_id": "conv_123",
                "message_id": "msg_456",
            },
        )
    )

    assert result == "ok"
    assert len(events) == 1
    event = events[0]
    assert event["success"] is True
    assert event["plugin_name"] == "persona"
    assert event["module_name"] == "image_understanding"
    assert event["operation"] == "image_understanding"
    assert event["conv_id"] == "conv_123"
    assert event["message_id"] == "msg_456"
    assert event["prompt_tokens"] == 11
    assert event["completion_tokens"] == 7
    assert event["total_tokens"] == 18
    assert event["error_type"] is None


def test_chat_emits_usage_event_on_failure():
    events = []
    client = _build_client(
        error=RuntimeError("network down"),
        usage_event_callback=events.append,
    )

    with pytest.raises(LLMProviderError):
        asyncio.run(
            client.chat(
                messages=[{"role": "user", "content": "hello"}],
                params=LLMCallParams(),
                usage_context={
                    "plugin_name": "persona",
                    "module_name": "image_understanding",
                    "conv_id": "conv_123",
                    "message_id": "msg_456",
                },
            )
        )

    assert len(events) == 1
    event = events[0]
    assert event["success"] is False
    assert event["plugin_name"] == "persona"
    assert event["module_name"] == "image_understanding"
    assert event["conv_id"] == "conv_123"
    assert event["message_id"] == "msg_456"
    assert event["prompt_tokens"] is None
    assert event["completion_tokens"] is None
    assert event["total_tokens"] is None
    assert event["error_type"] == "RuntimeError"


def test_chat_ignores_usage_callback_error():
    response = SimpleNamespace(
        id="resp_callback_error",
        object="chat.completion",
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
    )

    def _callback(_event):
        raise RuntimeError("callback failed")

    client = _build_client(response, usage_event_callback=_callback)
    result = asyncio.run(
        client.chat(
            messages=[{"role": "user", "content": "hello"}],
            params=LLMCallParams(),
        )
    )
    assert result == "ok"
