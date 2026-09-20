import asyncio

from src.core.message_history_formatter import format_message_history_entry
from src.core.services.message_processor import MessageProcessor


class _CaptureProvider:
    def __init__(self):
        self.calls = []
        self.memory_retrieval_callback = None

    async def extract_topics(self, conv_id, messages):
        return []

    async def extract_reply_keywords_from_history(self, conv_id, messages):
        return []

    async def generate_response(
        self,
        conv_id,
        messages,
        temperature=0.7,
        long_memory_prompt="",
        tool_choice="required",
    ):
        self.calls.append(
            {
                "conv_id": conv_id,
                "messages": list(messages),
                "temperature": temperature,
                "long_memory_prompt": long_memory_prompt,
                "tool_choice": tool_choice,
            }
        )
        return "收到"


def test_format_message_history_entry_uses_at_you_for_group_mentions():
    message = {
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

    assert format_message_history_entry(message) == "[张三]@了你: 你好"


def test_format_message_history_entry_uses_at_you_when_only_metadata_marks_self_mention():
    message = {
        "conv_id": "group_1",
        "user_name": "张三",
        "content": "你好",
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

    assert format_message_history_entry(message) == "[张三]@了你: 你好"


def test_format_message_history_entry_keeps_private_direct_wording():
    message = {
        "conv_id": "private_1",
        "user_name": "张三",
        "content": "你好",
        "is_direct": True,
        "is_bot": False,
        "metadata": {},
    }

    assert format_message_history_entry(message) == "[张三]对你说: 你好"


def test_format_message_history_entry_includes_referenced_message_for_self_mention():
    message = {
        "conv_id": "group_1",
        "user_name": "张三",
        "content": "帮我看看",
        "is_direct": True,
        "is_bot": False,
        "metadata": {
            "onebot": {
                "mentions": [{"text": "@月 月", "is_self": True}],
                "reply": {
                    "message_id": "9001",
                    "sender": {"user_id": "10001", "name": "Alice"},
                    "content": "原消息内容",
                },
            }
        },
    }

    assert format_message_history_entry(message) == "[张三]@了你: 【引用 Alice说: 原消息内容】 帮我看看"


def test_format_message_history_entry_marks_other_mention_as_reference_not_direct_reply():
    message = {
        "conv_id": "group_1",
        "user_name": "张三",
        "content": "@李四",
        "is_direct": False,
        "is_bot": False,
        "metadata": {
            "onebot": {
                "mentions": [{"text": "@李四", "qq": "10002"}],
                "reply": {
                    "message_id": "9002",
                    "sender": {"user_id": "2539518078", "name": "月 月"},
                    "content": "我是 bot 的上一条回复",
                    "is_self": True,
                },
                "reply_to_self": True,
                "direct_reason": "",
            }
        },
    }

    assert (
        format_message_history_entry(message)
        == "[张三]引用了你的消息: 【引用 你说: 我是 bot 的上一条回复】 @李四"
    )


def test_message_processor_generate_reply_formats_group_mentions_for_llm():
    provider = _CaptureProvider()
    processor = MessageProcessor(
        config={"queue_history_size": 20},
        llm_provider=provider,
    )
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

    reply = asyncio.run(processor.generate_reply("group_1", messages))

    assert reply == "收到"
    assert provider.calls == [
        {
            "conv_id": "group_1",
            "messages": [{"role": "user", "content": "[张三]@了你: 你好"}],
            "temperature": 0.7,
            "long_memory_prompt": "",
            "tool_choice": "required",
        }
    ]
