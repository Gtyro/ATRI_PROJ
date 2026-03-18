import asyncio
from datetime import datetime

from src.infra.db.tortoise.basic_message_cleanup import cleanup_expired_basic_messages


class _FakeDeleteQuery:
    def __init__(self, recorder):
        self._recorder = recorder

    async def delete(self):
        self._recorder["delete_calls"] += 1
        return self._recorder["delete_return"]


class _FakeModel:
    def __init__(self, recorder):
        self._recorder = recorder

    def filter(self, **kwargs):
        self._recorder["filters"].append(kwargs)
        return _FakeDeleteQuery(self._recorder)


def test_cleanup_expired_basic_messages_deletes_by_retention_cutoff():
    recorder = {"filters": [], "delete_calls": 0, "delete_return": 8}
    model = _FakeModel(recorder)
    now = datetime(2026, 3, 18, 3, 30, 0)

    deleted = asyncio.run(
        cleanup_expired_basic_messages(
            model=model,
            retention_days=120,
            now=now,
        )
    )

    assert deleted == 8
    assert recorder["delete_calls"] == 1
    assert recorder["filters"] == [{"created_at__lt": datetime(2025, 11, 18, 3, 30, 0)}]
