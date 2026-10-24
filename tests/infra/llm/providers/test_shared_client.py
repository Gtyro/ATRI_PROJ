import asyncio
import json
import logging

import httpx
import pytest

from src.infra.llm.providers.client import LLMClient
from src.infra.llm.providers.errors import LLMOutputParseError
from src.infra.llm.providers.types import LLMCallParams
from src.infra.network.tracked_httpx import TrackedAsyncClient


async def _run_with_response(api, payload, action, *, supports_response_format=False):
    requests = []
    events = []
    client = LLMClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        supports_response_format=supports_response_format,
        usage_event_callback=events.append,
    )
    shared = await client._shared_client(api, "test-model")
    assert isinstance(shared._async_client, TrackedAsyncClient)
    await shared._async_client.aclose()

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    shared._async_client = TrackedAsyncClient(
        transport=httpx.MockTransport(respond),
        event_hooks=shared._async_client.event_hooks,
    )
    try:
        value = await action(client)
        return value, requests, events
    finally:
        await shared.aclose()
        shared.close()


def test_shared_client_logs_when_socks_accounting_cannot_be_attached(monkeypatch, caplog):
    class ChangedSharedClient:
        def __init__(self, **kwargs):
            pass

        def close(self):
            pass

    monkeypatch.setattr("src.infra.llm.providers.client.SharedLLMClient", ChangedSharedClient)
    client = LLMClient(api_key="test-key", base_url="https://example.test/v1",
                       model="test-model")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="SOCKS 请求计数"):
            asyncio.run(client._shared_client("responses", "test-model"))
    assert "SOCKS 请求计数接入失败" in caplog.text


def test_shared_request_logs_when_tracking_client_is_not_used(caplog):
    async def action():
        client = LLMClient(api_key="test-key", base_url="https://example.test/v1",
                           model="test-model")
        shared = await client._shared_client("responses", "test-model")

        async def bypass_tracking(*args, **kwargs):
            return object()

        shared.arequest = bypass_tracking
        try:
            await client._request_shared(shared, "hello")
        finally:
            await shared.aclose()

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="SOCKS 计数客户端"):
            asyncio.run(action())
    assert "请求未经过计数客户端" in caplog.text


def test_shared_chat_preserves_request_and_usage_event():
    async def action(client):
        return await client.chat(
            [{"role": "user", "content": "hello"}],
            LLMCallParams(max_tokens=42),
            system_prompt="system",
        )

    result, requests, events = asyncio.run(_run_with_response("responses", {
        "id": "resp-chat-1", "status": "completed", "output_text": "hi",
        "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
    }, action))

    assert result == "hi"
    assert requests[0].url.path == "/v1/responses"
    body = json.loads(requests[0].content)
    assert body["input"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]
    assert body["max_output_tokens"] == 42
    assert events[0]["prompt_tokens"] == 5


def test_shared_chat_tools_returns_original_message_shape():
    async def action(client):
        return await client.chat_with_tools(
            [{"role": "user", "content": "weather"}],
            [{"type": "function", "function": {"name": "weather", "parameters": {"type": "object"}}}],
            LLMCallParams(),
        )

    result, requests, _ = asyncio.run(_run_with_response("responses", {
        "id": "resp-chat-2", "status": "completed",
        "output": [{"type": "function_call", "call_id": "call-1",
                    "name": "weather", "arguments": "{}"}],
    }, action))

    assert result.tool_calls[0].name == "weather"
    assert result.message["tool_calls"][0]["id"] == "call-1"
    body = json.loads(requests[0].content)
    assert body["tool_choice"] == "auto"
    assert body["tools"] == [{"type": "function", "name": "weather",
                              "parameters": {"type": "object"}}]


def test_shared_tool_result_converts_chat_history_to_responses_items():
    async def action(client):
        return await client.chat([
            {"role": "user", "content": "weather"},
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "weather", "arguments": "{}"},
            }]},
            {"role": "tool", "tool_call_id": "call-1", "content": "sunny"},
        ], LLMCallParams())

    result, requests, _ = asyncio.run(_run_with_response("responses", {
        "id": "resp-chat-3", "status": "completed", "output_text": "It is sunny.",
    }, action))

    assert result == "It is sunny."
    assert json.loads(requests[0].content)["input"] == [
        {"role": "user", "content": "weather"},
        {"type": "function_call", "call_id": "call-1", "name": "weather",
         "arguments": "{}"},
        {"type": "function_call_output", "call_id": "call-1", "output": "sunny"},
    ]


def test_shared_structured_output_uses_responses_format():
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
              "required": ["ok"]}

    async def action(client):
        return await client.structured_output(
            [{"role": "user", "content": "confirm"}], LLMCallParams(), schema=schema)

    result, requests, _ = asyncio.run(_run_with_response("responses", {
        "id": "resp-chat-4", "status": "completed", "output_text": '{"ok":true}',
    }, action, supports_response_format=True))

    assert result.data == {"ok": True}
    body = json.loads(requests[0].content)
    assert body["text"]["format"]["schema"] == schema
    assert body["text"]["format"]["strict"] is False


def test_shared_responses_sends_schema_and_parses_data():
    schema = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}

    async def action(client):
        return await client.response_json(
            input_items=[{"role": "user", "content": [{"type": "input_text", "text": "inspect"}]}],
            schema=schema,
            params=LLMCallParams(max_tokens=50),
            schema_name="observation",
        )

    result, requests, events = asyncio.run(_run_with_response("responses", {
        "id": "resp-1", "status": "completed", "output_text": '{"summary":"ok"}',
        "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12},
    }, action))

    assert result.data == {"summary": "ok"}
    body = json.loads(requests[0].content)
    assert requests[0].url.path == "/v1/responses"
    assert body["input"][0]["type"] == "message"
    assert body["text"]["format"]["schema"] == schema
    assert events[0]["total_tokens"] == 12


def test_shared_invalid_json_keeps_parse_error_contract():
    async def action(client):
        return await client.response_json(
            input_items=[{"role": "user", "content": "inspect"}],
            schema={"type": "object"},
            params=LLMCallParams(),
        )

    with pytest.raises(LLMOutputParseError):
        asyncio.run(_run_with_response("responses", {
            "id": "resp-2", "status": "completed", "output_text": "bad json",
        }, action))
