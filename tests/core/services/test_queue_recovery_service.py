import asyncio

from src.core.services.queue_recovery_service import QueueRecoveryService


class _ShortTermStub:
    def __init__(self, cleared=0):
        self.cleared = cleared
        self.clear_calls = []
        self.added = []

    async def clear_messages(self, conv_id):
        self.clear_calls.append(conv_id)
        return self.cleared

    async def add_message(self, message_data):
        self.added.append(dict(message_data))


def test_rebuild_queue_from_basic_messages_replaces_queue_in_order():
    async def _loader(conv_id, limit):
        assert conv_id == "group_1"
        assert limit == 2
        return [
            {
                "user_id": "u1",
                "user_name": "Alice",
                "content": "第一句",
                "is_direct": False,
                "is_bot": False,
                "is_processed": False,
                "metadata": {"source": "basic"},
            },
            {
                "user_id": "u2",
                "user_name": "Bob",
                "content": "第二句",
                "is_direct": True,
                "is_bot": False,
                "is_processed": True,
                "metadata": {},
            },
        ]

    short_term = _ShortTermStub(cleared=7)
    service = QueueRecoveryService(
        short_term=short_term,
        queue_history_size=2,
        recent_loader=_loader,
    )

    result = asyncio.run(service.rebuild_from_basic_messages("group_1"))

    assert result == {
        "source_count": 2,
        "cleared": 7,
        "restored": 2,
    }
    assert short_term.clear_calls == ["group_1"]
    assert short_term.added == [
        {
            "conv_id": "group_1",
            "user_id": "u1",
            "user_name": "Alice",
            "content": "第一句",
            "is_direct": False,
            "is_bot": False,
            "is_processed": False,
            "metadata": {"source": "basic"},
        },
        {
            "conv_id": "group_1",
            "user_id": "u2",
            "user_name": "Bob",
            "content": "第二句",
            "is_direct": True,
            "is_bot": False,
            "is_processed": True,
            "metadata": {},
        },
    ]


def test_rebuild_queue_from_basic_messages_skips_empty_payload_and_keeps_existing_queue():
    async def _loader(conv_id, limit):
        return [
            {
                "user_id": "u1",
                "user_name": "Alice",
                "content": "   ",
            }
        ]

    short_term = _ShortTermStub(cleared=5)
    service = QueueRecoveryService(
        short_term=short_term,
        queue_history_size=40,
        recent_loader=_loader,
    )

    result = asyncio.run(service.rebuild_from_basic_messages("group_1"))

    assert result == {
        "source_count": 0,
        "cleared": 0,
        "restored": 0,
    }
    assert short_term.clear_calls == []
    assert short_term.added == []
