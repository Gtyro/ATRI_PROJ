import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from src.infra.llm.providers.client import LLMClient
from src.infra.llm.providers.errors import LLMProviderError
from src.infra.llm.providers.types import LLMCallParams


class _FakeRequest:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def _build_client(
    response=None,
    *,
    error: Exception | None = None,
    usage_event_callback=None,
) -> LLMClient:
    client = LLMClient(
        api_key="test-key",
        base_url="https://example.com",
        model="test-model",
        provider_name="test_provider",
        timeout=30.0,
        usage_event_callback=usage_event_callback,
    )
    fake_request = _FakeRequest(response, error=error)
    client._create_chat = fake_request.create
    client._create_response = fake_request.create
    client._test_calls = fake_request.calls
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


def test_response_json_parses_output_and_emits_usage_event_with_extra_fields():
    events = []
    response = SimpleNamespace(
        output_text=json.dumps(
            {
                "summary": "仪表盘截图",
                "visible_facts": ["有机器人信息卡片"],
                "key_values": [],
                "ocr_text": [],
                "ui_elements": [],
                "charts": [],
                "tables": [],
                "warnings": [],
                "uncertainties": [],
            },
            ensure_ascii=False,
        ),
        usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
    )
    client = _build_client(response, usage_event_callback=events.append)

    result = asyncio.run(
        client.response_json(
            input_items=[{"role": "user", "content": [{"type": "input_text", "text": "inspect"}]}],
            schema={"type": "object", "properties": {"summary": {"type": "string"}}},
            params=LLMCallParams(),
            schema_name="image_observation",
            operation="image_understanding",
            usage_context={
                "plugin_name": "persona",
                "module_name": "image_understanding",
                "operation": "image_understanding",
                "conv_id": "conv_123",
                "message_id": "msg_456",
                "detail": "auto",
                "response_api": "responses",
            },
        )
    )

    assert result.data["summary"] == "仪表盘截图"
    assert len(events) == 1
    event = events[0]
    assert event["success"] is True
    assert event["prompt_tokens"] == 9
    assert event["completion_tokens"] == 4
    assert event["total_tokens"] == 13
    assert event["detail"] == "auto"
    assert event["response_api"] == "responses"


def test_response_json_emits_failure_event_when_output_is_empty():
    events = []
    response = SimpleNamespace(output_text="", usage=SimpleNamespace(input_tokens=3, output_tokens=0, total_tokens=3))
    client = _build_client(response, usage_event_callback=events.append)

    with pytest.raises(LLMProviderError):
        asyncio.run(
            client.response_json(
                input_items=[{"role": "user", "content": [{"type": "input_text", "text": "inspect"}]}],
                schema={"type": "object", "properties": {"summary": {"type": "string"}}},
                params=LLMCallParams(),
                usage_context={
                    "plugin_name": "persona",
                    "module_name": "image_understanding",
                    "detail": "auto",
                },
            )
        )

    assert len(events) == 1
    event = events[0]
    assert event["success"] is False
    assert event["detail"] == "auto"
    assert event["error_type"] == "LLMProviderError"


def test_response_json_adds_message_type_for_responses_input():
    response = SimpleNamespace(
        output_text=json.dumps({"summary": "ok"}, ensure_ascii=False),
        usage=SimpleNamespace(input_tokens=5, output_tokens=2, total_tokens=7),
    )
    client = _build_client(response)
    client.base_url = "https://openrouter.ai/api/v1"

    result = asyncio.run(
        client.response_json(
            input_items=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "inspect"},
                        {"type": "input_image", "image_url": "data:image/png;base64,abc", "detail": "auto"},
                    ],
                }
            ],
            schema={"type": "object", "properties": {"summary": {"type": "string"}}},
            params=LLMCallParams(),
        )
    )

    assert result.data["summary"] == "ok"
    call = client._test_calls[0]
    assert call["input"][0]["type"] == "message"
    assert call["input"][0]["content"][1]["detail"] == "auto"


def test_response_json_logs_explicit_truncation_reason_when_output_hits_max_tokens(caplog):
    response = SimpleNamespace(
        output_text='{"summary":"截断中"',
        usage=SimpleNamespace(input_tokens=9, output_tokens=120, total_tokens=129),
        status="completed",
        incomplete_details=None,
    )
    client = _build_client(response)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMProviderError):
            asyncio.run(
                client.response_json(
                    input_items=[{"role": "user", "content": [{"type": "input_text", "text": "inspect"}]}],
                    schema={"type": "object", "properties": {"summary": {"type": "string"}}},
                    params=LLMCallParams(max_tokens=120),
                )
            )

    assert "LLM response.truncation" in caplog.text
    assert "reason=max_output_tokens_exhausted_inferred" in caplog.text


def test_parse_json_payload_does_not_fallback_to_inner_array_for_truncated_object():
    with pytest.raises(json.JSONDecodeError):
        LLMClient._parse_json_payload(
            '{"summary":"截断","visible_facts":["a","b"]'
        )
