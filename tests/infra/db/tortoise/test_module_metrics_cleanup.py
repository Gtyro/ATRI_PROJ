import asyncio
from datetime import datetime

from src.infra.db.tortoise.module_metrics_cleanup import cleanup_expired_module_metric_events


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


def test_cleanup_expired_module_metric_events_deletes_by_retention_cutoff():
    recorder = {"filters": [], "delete_calls": 0, "delete_return": 5}
    model = _FakeModel(recorder)
    now = datetime(2026, 2, 15, 10, 0, 0)

    deleted = asyncio.run(cleanup_expired_module_metric_events(model, retention_days=90, now=now))

    assert deleted == 5
    assert recorder["delete_calls"] == 1
    assert recorder["filters"] == [{"created_at__lt": datetime(2025, 11, 17, 10, 0, 0)}]
