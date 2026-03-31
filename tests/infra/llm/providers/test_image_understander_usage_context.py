import asyncio
from types import SimpleNamespace

from src.infra.llm.providers.image_understander import ImageUnderstander
from src.infra.llm.providers.errors import LLMProviderError


class _FakeLLMClient:
    def __init__(self, *, should_fail: bool = False, summary: str = "图片摘要"):
        self.response_json_calls = []
        self.callback = None
        self.should_fail = should_fail
        self.summary = summary

    async def response_json(
        self,
        *,
        input_items,
        schema,
        params,
        schema_name="output",
        instructions=None,
        operation="response_json",
        usage_context=None,
    ):
        self.response_json_calls.append(
            {
                "input_items": input_items,
                "schema": schema,
                "params": params,
                "schema_name": schema_name,
                "instructions": instructions,
                "operation": operation,
                "usage_context": usage_context,
            }
        )
        if self.should_fail:
            raise LLMProviderError("provider failed", provider="test", operation=operation)
        return type(
            "StructuredOutput",
            (),
            {
                "data": {
                    "summary": self.summary,
                    "visible_facts": [],
                    "key_values": [],
                    "ocr_text": [],
                    "ui_elements": [],
                    "charts": [],
                    "tables": [],
                    "warnings": [],
                    "uncertainties": [],
                },
                "raw_text": "{}",
            },
        )()

    def set_usage_event_callback(self, callback):
        self.callback = callback


def _build_understander(fake_llm_client):
    understander = object.__new__(ImageUnderstander)
    understander.api_key = "test"
    understander.base_url = "https://example.com"
    understander.model = "test-model"
    understander.timeout_seconds = 60.0
    understander.max_tokens = 1200
    understander.detail = "auto"
    understander.provider_name = "image_understander"
    understander._provider_runtimes = []
    if fake_llm_client is not None:
        understander._provider_runtimes = [
            SimpleNamespace(
                provider_name="primary",
                model="test-model",
                api_key="test",
                base_url="https://example.com",
                client=fake_llm_client,
            )
        ]
    return understander


def test_inspect_images_passes_usage_context_to_llm_response_json():
    fake_llm = _FakeLLMClient()
    understander = _build_understander(fake_llm)

    result = asyncio.run(
        understander.inspect_images(
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

    assert result[0].display_text == "图片摘要"
    assert result[0].detail == "auto"
    assert result[0].provider_name == "primary"
    assert result[0].model == "test-model"
    assert len(fake_llm.response_json_calls) == 1
    call = fake_llm.response_json_calls[0]
    assert call["operation"] == "image_understanding"
    assert call["usage_context"]["conv_id"] == "group_1"
    assert call["usage_context"]["message_id"] == "1001"
    assert call["usage_context"]["detail"] == "auto"
    assert call["usage_context"]["response_api"] == "responses"
    assert call["schema_name"] == "image_observation"


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


def test_inspect_images_falls_back_to_next_provider():
    primary = _FakeLLMClient(should_fail=True)
    backup = _FakeLLMClient(summary="备用摘要")
    understander = object.__new__(ImageUnderstander)
    understander.api_key = "test"
    understander.base_url = "https://example.com"
    understander.model = "primary-model"
    understander.timeout_seconds = 60.0
    understander.max_tokens = 1200
    understander.detail = "auto"
    understander.provider_name = "image_understander"
    understander._provider_runtimes = [
        SimpleNamespace(
            provider_name="primary",
            model="primary-model",
            api_key="pk1",
            base_url="https://primary.example.com",
            client=primary,
        ),
        SimpleNamespace(
            provider_name="backup",
            model="backup-model",
            api_key="pk2",
            base_url="https://backup.example.com",
            client=backup,
        ),
    ]

    result = asyncio.run(understander.inspect_images([{"url": "https://example.com/image.jpg"}]))

    assert result[0].display_text == "备用摘要"
    assert result[0].provider_name == "backup"
    assert result[0].model == "backup-model"
    assert len(primary.response_json_calls) == 2
    assert len(backup.response_json_calls) == 1
    assert primary.response_json_calls[0]["usage_context"]["fallback_index"] == 0
    assert backup.response_json_calls[0]["usage_context"]["fallback_index"] == 1


def test_image_understander_default_max_tokens_is_2000():
    understander = ImageUnderstander(api_key="", base_url="", model="")
    assert understander.max_tokens == 2000
