import asyncio
from datetime import datetime

from plugins.wordcloud.cleanup import cleanup_expired_wordcloud_data


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


def test_cleanup_expired_wordcloud_data_deletes_by_retention_cutoff():
    recorder = {"filters": [], "delete_calls": 0, "delete_return": 12}
    model = _FakeModel(recorder)
    now = datetime(2026, 3, 18, 4, 0, 0)

    deleted = asyncio.run(
        cleanup_expired_wordcloud_data(
            model=model,
            retention_days=30,
            now=now,
        )
    )

    assert deleted == 12
    assert recorder["delete_calls"] == 1
    assert recorder["filters"] == [{"created_at__lt": datetime(2026, 2, 16, 4, 0, 0)}]
