import asyncio
from types import SimpleNamespace

from src.core.services.conversation_service import ConversationService


class _MessageRepositoryStub:
    def __init__(self) -> None:
        self.updated = []

    async def update_message_metadata(self, message_id, metadata):
        self.updated.append((message_id, metadata))
        return True


def test_store_outbound_onebot_message_ids_updates_stored_bot_message():
    repository = _MessageRepositoryStub()
    service = ConversationService(
        short_term=object(),
        long_term=object(),
        msgprocessor=object(),
        message_repo=repository,
        group_config=object(),
        plugin_name="persona",
        config={},
    )

    asyncio.run(
        service._store_outbound_onebot_message_ids(
            SimpleNamespace(id=42),
            ["51686581", "51686582"],
        )
    )

    assert repository.updated == [
        (42, {"onebot": {"message_ids": ["51686581", "51686582"]}})
    ]


def test_normalize_onebot_message_ids_deduplicates_callback_result():
    assert ConversationService._normalize_onebot_message_ids([123, "123", "456", None]) == [
        "123",
        "456",
    ]
