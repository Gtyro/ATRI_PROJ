import asyncio

from src.infra.llm.providers.image_understander import ImageUnderstander


class _FakeLLMClient:
    def __init__(self):
        self.chat_calls = []
        self.callback = None

    async def chat(self, messages, params, *, operation="chat", usage_context=None):
        self.chat_calls.append(
            {
                "messages": messages,
                "params": params,
                "operation": operation,
                "usage_context": usage_context,
            }
        )
        return "图片摘要"

    def set_usage_event_callback(self, callback):
        self.callback = callback


def _build_understander(fake_llm_client):
    understander = object.__new__(ImageUnderstander)
    understander.api_key = "test"
    understander.base_url = "https://example.com"
    understander.model = "test-model"
    understander.timeout_seconds = 60.0
    understander.max_tokens = 1200
    understander.provider_name = "image_understander"
    understander._llm_client = fake_llm_client
    return understander


def test_summarize_images_passes_usage_context_to_llm_chat():
    fake_llm = _FakeLLMClient()
    understander = _build_understander(fake_llm)

    result = asyncio.run(
        understander.summarize_images(
            [{"url": "https://example.com/image.jpg"}],
            usage_contexts=[
                {
                    "plugin_name": "persona",
                    "module_name": "image_understanding",
                    "operation": "image_understanding",
                    "conv_id": "group_1",
                    "message_id": "1001",
                }
            ],
        )
    )

    assert result == ["图片摘要"]
    assert len(fake_llm.chat_calls) == 1
    call = fake_llm.chat_calls[0]
    assert call["operation"] == "image_understanding"
    assert call["usage_context"]["conv_id"] == "group_1"
    assert call["usage_context"]["message_id"] == "1001"


def test_set_usage_event_callback_delegates_to_llm_client():
    fake_llm = _FakeLLMClient()
    understander = _build_understander(fake_llm)

    def _callback(_event):
        return None

    understander.set_usage_event_callback(_callback)
    assert fake_llm.callback is _callback


def test_set_usage_event_callback_is_noop_without_llm_client():
    understander = _build_understander(None)
    understander.set_usage_event_callback(lambda _event: None)


def test_image_understander_default_max_tokens_is_2000():
    understander = ImageUnderstander(api_key="", base_url="", model="")
    assert understander.max_tokens == 2000
