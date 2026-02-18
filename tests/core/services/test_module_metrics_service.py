import asyncio

import pytest

from src.core.services.module_metrics_service import ModuleMetricsService


class _FakeRepository:
    def __init__(self):
        self.last_options = None
        self.last_summary = None
        self.last_events = None

    async def list_options(self, filters):
        self.last_options = filters
        return {"plugin_names": [], "module_names": [], "operations": [], "conv_ids": []}

    async def get_summary(self, filters, *, interval):
        self.last_summary = (filters, interval)
        return {"total_calls": 0, "failed_calls": 0, "trends": []}

    async def list_events(self, filters, *, page, size):
        self.last_events = (filters, page, size)
        return {"items": [], "total": 0, "page": page, "size": size}


def test_get_events_normalizes_filter_and_pagination():
    repository = _FakeRepository()
    service = ModuleMetricsService(repository=repository)

    result = asyncio.run(
        service.get_events(
            plugin_name=" persona ",
            module_name=" image_understanding ",
            operation="",
            conv_id=" ",
            page=0,
            size=999,
        )
    )

    filters, page, size = repository.last_events
    assert filters.plugin_name == "persona"
    assert filters.module_name == "image_understanding"
    assert filters.operation is None
    assert filters.conv_id is None
    assert page == 1
    assert size == 200
    assert result["size"] == 200


def test_get_summary_rejects_invalid_interval():
    repository = _FakeRepository()
    service = ModuleMetricsService(repository=repository)

    with pytest.raises(ValueError):
        asyncio.run(service.get_summary(interval="week"))
