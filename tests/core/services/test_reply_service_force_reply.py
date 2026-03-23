import asyncio

from src.core.services.reply_service import ReplyService


class _ShortTermStub:
    def __init__(self, messages):
        self.messages = list(messages)
        self.bot_messages = []

    async def get_recent_messages(self, conv_id, limit):
        return list(self.messages)

    async def add_bot_message(self, conv_id, content):
        self.bot_messages.append((conv_id, content))


class _MsgProcessorStub:
    def __init__(self, reply_content="你好"):
        self.reply_content = reply_content
        self.calls = []

    async def generate_reply(self, conv_id, messages, temperature=0.7):
        self.calls.append(
            {
                "conv_id": conv_id,
                "messages": list(messages),
                "temperature": temperature,
            }
        )
        return self.reply_content


def test_force_reply_appends_test_message_and_persists_bot_reply():
    short_term = _ShortTermStub(
        [
            {
                "user_name": "Alice",
                "content": "前文",
                "is_bot": False,
                "is_direct": False,
            }
        ]
    )
    msgprocessor = _MsgProcessorStub(reply_content="你好")
    service = ReplyService(short_term=short_term, msgprocessor=msgprocessor, queue_history_size=20)

    reply_data = asyncio.run(service.force_reply("group_1", test_message="摸摸"))

    assert reply_data == {
        "reply_content": ["你好"],
        "raw_reply_content": "你好",
    }
    assert short_term.bot_messages == [("group_1", "你好")]
    assert msgprocessor.calls[0]["messages"][-1]["content"] == "摸摸"
    assert msgprocessor.calls[0]["messages"][-1]["is_direct"] is True
    assert msgprocessor.calls[0]["messages"][-1]["is_bot"] is False


def test_force_reply_returns_none_without_history():
    short_term = _ShortTermStub([])
    msgprocessor = _MsgProcessorStub(reply_content="你好")
    service = ReplyService(short_term=short_term, msgprocessor=msgprocessor, queue_history_size=20)

    reply_data = asyncio.run(service.force_reply("group_1"))

    assert reply_data is None
    assert short_term.bot_messages == []
    assert msgprocessor.calls == []
