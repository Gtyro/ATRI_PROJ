import asyncio

from src.infra.llm.providers.ai_processor import AIProcessor
from src.infra.llm.providers.types import LLMStructuredOutput


class _CaptureStructuredClient:
    def __init__(self):
        self.calls = []

    async def structured_output(
        self,
        messages,
        params,
        *,
        system_prompt=None,
        schema=None,
        operation="structured_output",
        request_id=None,
        strict=True,
        usage_context=None,
    ):
        self.calls.append(
            {
                "messages": list(messages),
                "system_prompt": system_prompt,
                "operation": operation,
                "strict": strict,
            }
        )
        return LLMStructuredOutput(
            data={"keywords": ["你好"]},
            raw_text='{"keywords":["你好"]}',
        )


def test_extract_reply_keywords_formats_group_mentions_as_at_you():
    processor = object.__new__(AIProcessor)
    processor.provider_name = "test"
    processor.raise_on_error = True
    processor.queue_history_size = 20
    processor._llm_client = _CaptureStructuredClient()

    messages = [
        {
            "conv_id": "group_1",
            "user_name": "张三",
            "content": "@月 月 你好",
            "is_direct": True,
            "is_bot": False,
            "metadata": {
                "onebot": {
                    "mentions": [
                        {"text": "@月 月", "is_self": True},
                    ]
                }
            },
        }
    ]

    keywords = asyncio.run(processor.extract_reply_keywords_from_history("group_1", messages))

    assert keywords == ["你好"]
    assert processor._llm_client.calls[0]["operation"] == "extract_reply_keywords_from_history"
    assert (
        processor._llm_client.calls[0]["messages"][0]["content"]
        == "最近消息历史:\n1. [张三]@了你: 你好"
    )
