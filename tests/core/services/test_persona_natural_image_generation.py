import asyncio
import base64
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from src.adapters.nonebot import persona_reply
from src.adapters.persona.ports_adapters import LLMProviderAdapter
from src.core.services.conversation_service import ConversationService
from src.core.services.message_processor import MessageProcessor
from src.core.services.image_generation_service import ImageGenerationTurn
from src.infra.llm.providers.ai_processor import AIProcessor
from src.infra.llm.providers.fallback import FallbackLLMProvider
from src.infra.llm.providers.image_generator import ImageGenerationError, ImageGenerator
from src.infra.llm.providers.types import LLMToolCall, LLMToolCallResponse


IMAGE_PROMPT = "Silver-haired girl with blue eyes, white dress, seaside selfie, anime style"
IMAGE_BYTES = b"mock-image-bytes"


def _tool_response(name, arguments, call_id="call-1"):
    call = LLMToolCall(call_id, name, json.dumps(arguments))
    return LLMToolCallResponse(
        message={
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }],
        },
        tool_calls=[call],
    )


class _Client:
    def __init__(self, responses=None, caption="给你。", error=None):
        self.responses = list(responses or [
            _tool_response("generate_image", {"prompt": IMAGE_PROMPT}),
        ])
        self.caption = caption
        self.error = error
        self.tool_requests = []
        self.final_requests = []

    async def chat_with_tools(self, messages, **kwargs):
        self.tool_requests.append({"messages": list(messages), **kwargs})
        return self.responses.pop(0)

    async def chat(self, messages, **kwargs):
        self.final_requests.append({"messages": list(messages), **kwargs})
        if self.error is not None:
            raise self.error
        return self.caption


@pytest.fixture(autouse=True)
def isolated_persona(monkeypatch, tmp_path):
    persona_dir = tmp_path / "data" / "persona"
    persona_dir.mkdir(parents=True)
    (persona_dir / "default.txt").write_text(
        "You are a silver-haired girl with blue eyes and a white dress.", encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)


def _provider(client):
    provider = object.__new__(AIProcessor)
    provider.group_character = {}
    provider.memory_retrieval_callback = AsyncMock(return_value={
        "memory_context": "No relevant memory", "candidates": [],
    })
    provider.raise_on_error = True
    provider._llm_client = client
    provider.extract_topics = AsyncMock(return_value=[])
    provider.extract_reply_keywords_from_history = AsyncMock(return_value=[])
    return provider


def _service(clients, generator, *, mode="tool_only", enabled=True):
    providers = [_provider(client) for client in clients]
    chain = FallbackLLMProvider(providers)
    processor = MessageProcessor(
        config={"queue_history_size": 20}, llm_provider=LLMProviderAdapter(chain),
    )
    stored_messages = {}

    async def store(message):
        stored_messages.setdefault(message["conv_id"], []).append(message)

    short_term = SimpleNamespace(
        add_message=AsyncMock(side_effect=store),
        get_unprocessed_messages=AsyncMock(side_effect=lambda conv_id, limit: list(stored_messages[conv_id])),
        get_recent_messages=AsyncMock(side_effect=lambda conv_id, limit: list(stored_messages[conv_id])),
        add_bot_message=AsyncMock(return_value=None),
    )
    service = ConversationService(
        short_term=short_term,
        long_term=SimpleNamespace(store_memories=AsyncMock(return_value=[])),
        msgprocessor=processor,
        message_repo=SimpleNamespace(has_bot_message=AsyncMock(return_value=False)),
        group_config=None,
        plugin_name="persona",
        config={
            "queue_history_size": 20,
            "batch_interval": 60,
            "image_understanding": {"enabled": False, "retrieval_ab_mode": mode},
        },
        reply_callback=persona_reply.persona_callback,
        image_generator=generator if enabled else None,
    )
    return service, providers


def _message(*, is_superuser=True, conv_id="private_10001"):
    return {
        "conv_id": conv_id,
        "user_id": "10001",
        "user_name": "Test user",
        "content": "画一张你的自拍",
        "is_direct": True,
        "is_bot": False,
        "is_superuser": is_superuser,
    }


@pytest.fixture
def sent_messages(monkeypatch):
    sent = []

    async def send(message, target):
        sent.append((message, target))
        return SimpleNamespace(msg_ids=[{"message_id": str(200 + len(sent))}])

    monkeypatch.setattr(persona_reply.UniMessage, "send", send)
    monkeypatch.setattr(persona_reply.asyncio, "sleep", AsyncMock())
    return sent


@pytest.mark.parametrize("mode", ["tool_only", "hybrid"])
def test_natural_selfie_generates_and_sends_image_without_progress_text(mode, sent_messages):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{
            "b64_json": base64.b64encode(IMAGE_BYTES).decode(),
        }]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            generator = ImageGenerator(
                api_key="test-key", base_url="https://images.test/v1",
                model="test-image-model", client=transport,
            )
            client = _Client()
            service, _ = _service([client], generator, mode=mode)
            result = await service.process_message(_message())
            return result, service, client

    result, service, client = asyncio.run(run())

    assert result["images"] == [IMAGE_BYTES]
    assert len(requests) == 1
    assert json.loads(requests[0].content)["prompt"] == IMAGE_PROMPT
    assert sent_messages[0][0][0].type == "image"
    assert sent_messages[0][0][0].raw == IMAGE_BYTES
    assert all(target.private and target.id == "10001" for _, target in sent_messages)
    assert [str(message) for message, _ in sent_messages[1:]] == ["给你"]
    assert "正在生成" not in str(sent_messages)
    request = client.tool_requests[0]
    assert "silver-haired girl" in request["system_prompt"]
    assert "generate_image" in {tool["function"]["name"] for tool in request["tools"]}
    if mode == "hybrid":
        assert request["tool_choice"] == "auto"
        assert [tool["function"]["name"] for tool in request["tools"]] == ["generate_image"]
    assert any(
        message["role"] == "tool" and '"status": "ok"' in message["content"]
        for message in client.final_requests[0]["messages"]
    )
    service.short_term.add_bot_message.assert_awaited_once_with("private_10001", "给你。 [图片]")


def test_natural_image_generation_treats_names_as_optional_identity_labels(sent_messages):
    client = _Client()
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)

    asyncio.run(service.process_message(_message()))

    request = client.tool_requests[0]
    assert "可选的辅助身份标签" in request["system_prompt"]
    image_tool = next(
        tool for tool in request["tools"]
        if tool["function"]["name"] == "generate_image"
    )
    assert "辅助身份标签" in image_tool["function"]["parameters"]["properties"]["prompt"]["description"]
    assert image_tool["function"]["parameters"]["required"] == [
        "prompt",
        "use_character_reference",
    ]


def test_natural_selfie_passes_character_reference_flag_to_generator(sent_messages):
    client = _Client(responses=[
        _tool_response("generate_image", {
            "prompt": IMAGE_PROMPT,
            "use_character_reference": True,
        }),
    ])
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)

    asyncio.run(service.process_message(_message()))

    generator.generate.assert_awaited_once_with(
        IMAGE_PROMPT,
        use_character_reference=True,
    )
    image_tool = next(
        tool for tool in client.tool_requests[0]["tools"]
        if tool["function"]["name"] == "generate_image"
    )
    assert "use_character_reference" in image_tool["function"]["parameters"]["properties"]


def test_memory_lookup_can_be_followed_by_image_generation(sent_messages):
    client = _Client(responses=[
        _tool_response("retrieve_memories", {"query": "appearance"}),
        _tool_response("generate_image", {"prompt": IMAGE_PROMPT}, "call-2"),
    ])
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, providers = _service([client], generator)

    result = asyncio.run(service.process_message(_message()))

    assert result["images"] == [IMAGE_BYTES]
    assert len(client.tool_requests) == 2
    assert client.tool_requests[1]["tool_choice"] == "auto"
    providers[0].memory_retrieval_callback.assert_awaited_once()
    assert client.tool_requests[1]["messages"][-1]["role"] == "tool"
    generator.generate.assert_awaited_once()


def test_ordinary_private_chat_cannot_generate_or_send(sent_messages):
    client = _Client()
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)

    result = asyncio.run(service.process_message(_message(is_superuser=False)))

    assert result is None
    assert client.tool_requests == []
    generator.generate.assert_not_awaited()
    assert sent_messages == []


def test_disabled_generation_never_exposes_image_tool(sent_messages):
    client = _Client(responses=[LLMToolCallResponse(
        message={"role": "assistant", "content": "不能画图。"}, tool_calls=[],
    )], caption="不能画图。")
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator, enabled=False)

    result = asyncio.run(service.process_message(_message()))

    assert "images" not in result
    assert [tool["function"]["name"] for tool in client.tool_requests[0]["tools"]] == [
        "retrieve_memories",
    ]
    generator.generate.assert_not_awaited()


def test_image_failure_does_not_send_success_claim(sent_messages):
    client = _Client(caption="已经发给你啦。")
    generator = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError("offline")))
    service, _ = _service([client], generator)

    result = asyncio.run(service.process_message(_message()))

    assert "images" not in result
    assert "没能画出来" in "".join(result["reply_content"])
    assert client.final_requests == []
    assert all(message[0].type == "text" for message, _ in sent_messages)


def test_fallback_keeps_image_and_does_not_generate_twice(sent_messages):
    primary = _Client(error=RuntimeError("caption request failed"))
    secondary = _Client()
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([primary, secondary], generator)

    result = asyncio.run(service.process_message(_message()))

    assert result["images"] == [IMAGE_BYTES]
    generator.generate.assert_awaited_once_with(IMAGE_PROMPT)
    assert len(secondary.tool_requests) == 1
    assert sum(message[0].type == "image" for message, _ in sent_messages) == 1


@pytest.mark.parametrize("failure", [False, True])
def test_image_still_sends_without_caption_when_text_provider_fails(failure, sent_messages):
    client = _Client(caption="", error=RuntimeError("text failed") if failure else None)
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)

    result = asyncio.run(service.process_message(_message()))

    assert result["reply_content"] == []
    assert result["images"] == [IMAGE_BYTES]
    assert len(sent_messages) == 1
    assert sent_messages[0][0][0].type == "image"
    service.short_term.add_bot_message.assert_awaited_once_with("private_10001", "[图片]")


def test_parallel_conversations_keep_their_own_images(sent_messages):
    class ContextClient(_Client):
        async def chat_with_tools(self, messages, **kwargs):
            user_message = messages[-1]["content"]
            return _tool_response("generate_image", {"prompt": user_message})

    message_a = _message(conv_id="private_10001")
    message_a["content"] = "画一张海边自拍"
    message_b = _message(conv_id="private_10002")
    message_b["content"] = "画一张雪地自拍"

    async def run():
        gate = asyncio.Event()
        arrivals = 0

        async def generate(prompt):
            nonlocal arrivals
            arrivals += 1
            if arrivals == 2:
                gate.set()
            await asyncio.wait_for(gate.wait(), timeout=2)
            return prompt.encode()

        generator = SimpleNamespace(generate=AsyncMock(side_effect=generate))
        service, _ = _service([ContextClient()], generator)
        return await asyncio.gather(
            service.process_message(message_a), service.process_message(message_b),
        )

    result_a, result_b = asyncio.run(run())

    assert "海边" in result_a["images"][0].decode()
    assert "雪地" in result_b["images"][0].decode()
    sent_images = {target.id: message[0].raw for message, target in sent_messages if message[0].type == "image"}
    assert sent_images == {"10001": result_a["images"][0], "10002": result_b["images"][0]}


def test_ordinary_conversation_does_not_generate_image(sent_messages):
    client = _Client(responses=[LLMToolCallResponse(
        message={"role": "assistant", "content": "你好呀。"}, tool_calls=[],
    )])
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator, mode="hybrid")
    message = _message()
    message["content"] = "你好"

    result = asyncio.run(service.process_message(message))

    assert result["reply_content"] == ["你好呀"]
    assert "images" not in result
    generator.generate.assert_not_awaited()
    assert client.final_requests == []


def test_unavailable_image_tool_cannot_be_invoked_by_model(sent_messages):
    client = _Client()
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator, enabled=False)

    result = asyncio.run(service.process_message(_message()))

    assert "images" not in result
    generator.generate.assert_not_awaited()
    assert "没能画出来" in "".join(result["reply_content"])


def test_invalid_image_prompt_does_not_generate_or_claim_success(sent_messages):
    client = _Client(responses=[_tool_response("generate_image", {"prompt": ""})])
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)

    result = asyncio.run(service.process_message(_message()))

    assert "images" not in result
    generator.generate.assert_not_awaited()
    assert "没能画出来" in "".join(result["reply_content"])


def test_multiple_image_tool_calls_only_generate_once(sent_messages):
    response = _tool_response("generate_image", {"prompt": IMAGE_PROMPT})
    second = _tool_response("generate_image", {"prompt": "another image"}, "call-2")
    response.tool_calls.extend(second.tool_calls)
    response.message["tool_calls"].extend(second.message["tool_calls"])
    client = _Client(responses=[response])
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)

    result = asyncio.run(service.process_message(_message()))

    assert result["images"] == [IMAGE_BYTES]
    generator.generate.assert_awaited_once_with(IMAGE_PROMPT)
    assert len([message for message in client.final_requests[0]["messages"] if message["role"] == "tool"]) == 2


def test_disabled_group_policy_blocks_image_generation(sent_messages):
    client = _Client()
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)
    service.plugin_policy_service = SimpleNamespace(
        is_ingest_enabled=AsyncMock(return_value=False),
        is_enabled=AsyncMock(return_value=False),
    )

    result = asyncio.run(service.process_message(_message(
        is_superuser=False, conv_id="group_20001",
    )))

    assert result is None
    generator.generate.assert_not_awaited()
    assert client.tool_requests == []
    assert sent_messages == []


def test_no_reply_sender_means_no_image_generation_capability(sent_messages):
    client = _Client(responses=[LLMToolCallResponse(
        message={"role": "assistant", "content": "不能发图。"}, tool_calls=[],
    )], caption="不能发图。")
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([client], generator)
    service.reply_callback = None

    result = asyncio.run(service.process_message(_message()))

    assert "images" not in result
    generator.generate.assert_not_awaited()
    assert [tool["function"]["name"] for tool in client.tool_requests[0]["tools"]] == [
        "retrieve_memories",
    ]
    assert sent_messages == []


@pytest.mark.parametrize("mode", ["tool_only", "hybrid"])
@pytest.mark.parametrize("status,explanation,retryable", [
    (400, "不接受这次请求", False),
    (401, "凭据没通过验证", False),
    (402, "额度不足", False),
    (403, "拒绝了这次请求", False),
    (404, "找不到所请求的接口或模型", False),
    (429, "请求太频繁", True),
    (503, "暂时出故障", True),
])
def test_failed_generation_reason_reaches_natural_reply_and_logs(
    mode, status, explanation, retryable, sent_messages, caplog,
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"x-request-id": "req-natural-failed"},
            json={"error": {"message": "upstream diagnostic: token=secret-value"}},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            generator = ImageGenerator(
                api_key="test-key", base_url="https://images.test/v1",
                model="test-image-model", client=transport,
            )
            client = _Client(caption="已经发给你了。")
            service, _ = _service([client], generator, mode=mode)
            return await service.process_message(_message()), client

    with caplog.at_level(logging.WARNING):
        result, client = asyncio.run(run())

    assert "images" not in result
    assert explanation in "".join(result["reply_content"])
    assert explanation in "".join(str(message) for message, _ in sent_messages)
    assert client.final_requests == []
    assert "已经发给你" not in str(sent_messages)
    assert len(requests) == (2 if retryable else 1)
    if not retryable:
        assert "等会儿再试" not in str(sent_messages)
        assert "稍后再试" not in str(sent_messages)
    assert f"status={status}" in caplog.text
    assert "req-natural-failed" in caplog.text
    assert "upstream diagnostic" in caplog.text
    assert "secret-value" not in caplog.text


@pytest.mark.parametrize("exc,explanation", [
    (httpx.ReadTimeout("timed out"), "请求超时"),
    (httpx.ConnectError("cannot connect"), "没连上绘图服务"),
])
def test_transport_error_reason_reaches_natural_reply(exc, explanation, sent_messages):
    def handler(request):
        raise exc

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            generator = ImageGenerator(
                api_key="test-key", base_url="https://images.test/v1",
                model="test-image-model", client=transport,
            )
            service, _ = _service([_Client()], generator)
            return await service.process_message(_message())

    result = asyncio.run(run())
    assert explanation in "".join(result["reply_content"])
    assert "images" not in result


def test_failed_turn_caches_reason_without_repeating_request(caplog):
    def handler(request):
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            generator = ImageGenerator(
                api_key="test-key", base_url="https://images.test/v1",
                model="test-image-model", client=transport,
            )
            turn = ImageGenerationTurn(generator, "private_10001")
            result_a = await turn.generate("a cat")
            result_b = await turn.generate("another prompt")
            return result_a, result_b, turn

    with caplog.at_level(logging.WARNING):
        result_a, result_b, turn = asyncio.run(run())
    assert result_a == result_b
    assert result_a["error_code"] == "not_found"
    assert "接口或模型" in result_a["message"]
    assert turn.images == []
    assert caplog.text.count("Persona image generation failed") == 1


@pytest.mark.parametrize("arguments", ["invalid json", "null", "[]", "123", '{"prompt": 123}'])
def test_malformed_image_tool_arguments_have_specific_reply(arguments, sent_messages):
    response = _tool_response("generate_image", {})
    response.tool_calls[0].arguments = arguments
    response.message["tool_calls"][0]["function"]["arguments"] = arguments
    generator = SimpleNamespace(generate=AsyncMock(return_value=IMAGE_BYTES))
    service, _ = _service([_Client(responses=[response])], generator)

    result = asyncio.run(service.process_message(_message()))

    assert "没能整理好绘图描述" in "".join(result["reply_content"])
    generator.generate.assert_not_awaited()


def test_error_reason_survives_exhausted_text_provider_fallback(sent_messages):
    generator = SimpleNamespace(generate=AsyncMock(side_effect=ImageGenerationError(
        "HTTP 404", code="not_found", status_code=404, detail="model not found",
    )))
    service, providers = _service([_Client(), _Client()], generator)

    async def fail_after_tool(*args, **kwargs):
        await kwargs["image_generation_callback"](IMAGE_PROMPT)
        raise RuntimeError("text provider failed after executing tool")

    for provider in providers:
        provider.generate_response = AsyncMock(side_effect=fail_after_tool)

    result = asyncio.run(service.process_message(_message()))

    assert "找不到所请求的接口或模型" in "".join(result["reply_content"])
    generator.generate.assert_awaited_once()
    assert "images" not in result
