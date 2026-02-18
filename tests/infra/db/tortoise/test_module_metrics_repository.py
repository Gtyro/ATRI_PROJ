import asyncio
from datetime import datetime

from src.infra.db.tortoise.module_metrics_repository import (
    ModuleMetricsFilter,
    TortoiseModuleMetricsRepository,
)


def _match_condition(row, key, value):
    if key.endswith("__gte"):
        field = key[:-5]
        return row.get(field) is not None and row.get(field) >= value
    if key.endswith("__lte"):
        field = key[:-5]
        return row.get(field) is not None and row.get(field) <= value
    return row.get(key) == value


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._offset = 0
        self._limit = None

    def _clone(self):
        cloned = _FakeQuery(self._rows)
        cloned._offset = self._offset
        cloned._limit = self._limit
        return cloned

    def filter(self, **kwargs):
        return _FakeQuery(
            [row for row in self._rows if all(_match_condition(row, key, value) for key, value in kwargs.items())]
        )

    def order_by(self, *fields):
        rows = list(self._rows)
        for field in reversed(fields):
            reverse = field.startswith("-")
            key = field[1:] if reverse else field
            rows.sort(key=lambda item: item.get(key), reverse=reverse)
        return _FakeQuery(rows)

    def offset(self, value):
        cloned = self._clone()
        cloned._offset = value
        return cloned

    def limit(self, value):
        cloned = self._clone()
        cloned._limit = value
        return cloned

    async def count(self):
        return len(self._rows)

    async def values_list(self, field, flat=False):
        values = [row.get(field) for row in self._rows]
        return values

    async def values(self, *fields):
        rows = list(self._rows)
        rows = rows[self._offset :]
        if self._limit is not None:
            rows = rows[: self._limit]
        if not fields:
            return [dict(row) for row in rows]
        return [{field: row.get(field) for field in fields} for row in rows]


class _FakeModel:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return _FakeQuery(self._rows)


def test_list_events_supports_filter_and_pagination():
    rows = [
        {
            "id": 1,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_1",
            "success": True,
            "prompt_tokens": 3,
            "completion_tokens": 7,
            "total_tokens": 10,
            "created_at": datetime(2026, 1, 1, 10, 0, 0),
            "message_id": None,
            "provider_name": None,
            "model": None,
            "request_id": None,
            "error_type": None,
            "extra": {},
        },
        {
            "id": 2,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_1",
            "success": False,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "created_at": datetime(2026, 1, 1, 11, 0, 0),
            "message_id": None,
            "provider_name": None,
            "model": None,
            "request_id": None,
            "error_type": "RuntimeError",
            "extra": {},
        },
        {
            "id": 3,
            "plugin_name": "other",
            "module_name": "x",
            "operation": "x",
            "conv_id": "group_2",
            "success": True,
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
            "message_id": None,
            "provider_name": None,
            "model": None,
            "request_id": None,
            "error_type": None,
            "extra": {},
        },
    ]
    repository = TortoiseModuleMetricsRepository(model=_FakeModel(rows))

    result = asyncio.run(
        repository.list_events(
            ModuleMetricsFilter(plugin_name="persona"),
            page=1,
            size=1,
        )
    )

    assert result["total"] == 2
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == 2
    assert result["items"][0]["plugin_name"] == "persona"


def test_list_events_filters_by_conv_id():
    rows = [
        {
            "id": 1,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_1",
            "success": True,
            "prompt_tokens": 3,
            "completion_tokens": 7,
            "total_tokens": 10,
            "created_at": datetime(2026, 1, 1, 10, 0, 0),
            "message_id": None,
            "provider_name": None,
            "model": None,
            "request_id": None,
            "error_type": None,
            "extra": {},
        },
        {
            "id": 2,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_2",
            "success": False,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "created_at": datetime(2026, 1, 1, 11, 0, 0),
            "message_id": None,
            "provider_name": None,
            "model": None,
            "request_id": None,
            "error_type": "RuntimeError",
            "extra": {},
        },
    ]
    repository = TortoiseModuleMetricsRepository(model=_FakeModel(rows))

    result = asyncio.run(
        repository.list_events(
            ModuleMetricsFilter(plugin_name="persona", conv_id="group_2"),
            page=1,
            size=20,
        )
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == 2
    assert result["items"][0]["conv_id"] == "group_2"
    assert result["items"][0]["success"] is False
    assert result["items"][0]["error_type"] == "RuntimeError"


def test_get_summary_builds_kpi_and_trends():
    rows = [
        {
            "id": 1,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_1",
            "success": True,
            "total_tokens": 10,
            "created_at": datetime(2026, 1, 1, 10, 5, 0),
        },
        {
            "id": 2,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_1",
            "success": False,
            "total_tokens": None,
            "created_at": datetime(2026, 1, 1, 12, 30, 0),
        },
        {
            "id": 3,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_2",
            "success": True,
            "total_tokens": 30,
            "created_at": datetime(2026, 1, 2, 9, 0, 0),
        },
    ]
    repository = TortoiseModuleMetricsRepository(model=_FakeModel(rows))

    summary = asyncio.run(
        repository.get_summary(
            ModuleMetricsFilter(plugin_name="persona"),
            interval="day",
        )
    )

    assert summary["total_calls"] == 3
    assert summary["failed_calls"] == 1
    assert summary["total_tokens"] == 40
    assert round(summary["success_rate"], 4) == round(2 / 3, 4)
    assert round(summary["avg_tokens_per_call"], 4) == round(40 / 3, 4)
    trends_by_day = {item["time"][:10]: item for item in summary["trends"]}
    assert trends_by_day["2026-01-01"]["total_calls"] == 2
    assert trends_by_day["2026-01-01"]["failed_calls"] == 1
    assert trends_by_day["2026-01-01"]["total_tokens"] == 10
    assert trends_by_day["2026-01-02"]["total_calls"] == 1
    assert trends_by_day["2026-01-02"]["total_tokens"] == 30


def test_list_options_excludes_empty_values():
    rows = [
        {
            "id": 1,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "group_2",
            "created_at": datetime(2026, 1, 1, 10, 0, 0),
            "success": True,
            "total_tokens": 1,
        },
        {
            "id": 2,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": "",
            "created_at": datetime(2026, 1, 1, 10, 0, 1),
            "success": True,
            "total_tokens": 1,
        },
        {
            "id": 3,
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding",
            "conv_id": None,
            "created_at": datetime(2026, 1, 1, 10, 0, 2),
            "success": True,
            "total_tokens": 1,
        },
    ]
    repository = TortoiseModuleMetricsRepository(model=_FakeModel(rows))

    options = asyncio.run(repository.list_options(ModuleMetricsFilter(plugin_name="persona")))

    assert options["plugin_names"] == ["persona"]
    assert options["module_names"] == ["image_understanding"]
    assert options["operations"] == ["image_understanding"]
    assert options["conv_ids"] == ["group_2"]
