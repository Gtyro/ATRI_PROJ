import asyncio
from datetime import datetime

from src.core.services.module_metrics_builtin_providers import (
    PersonaImageFetchMetricsProvider,
    PersonaImageUnderstandingMetricsProvider,
    build_builtin_module_metrics_providers,
)
from src.core.services.module_metrics_provider import ModuleMetricsQuery


class _FakeRepository:
    async def get_summary(self, filters, *, interval):
        if filters.module_id == "persona.image_understanding":
            if interval == "hour":
                return {
                    "total_calls": 3,
                    "failed_calls": 1,
                    "success_rate": 2 / 3,
                    "total_tokens": 40,
                    "avg_tokens_per_call": 40 / 3,
                    "trends": [
                        {
                            "time": "2026-01-01T10:00:00",
                            "total_calls": 2,
                            "failed_calls": 1,
                            "total_tokens": 20,
                        }
                    ],
                }
            return {
                "total_calls": 3,
                "failed_calls": 1,
                "success_rate": 2 / 3,
                "total_tokens": 40,
                "avg_tokens_per_call": 40 / 3,
                "trends": [
                    {
                        "time": "2026-01-01T00:00:00",
                        "total_calls": 3,
                        "failed_calls": 1,
                        "total_tokens": 40,
                    }
                ],
            }

        return {
            "total_calls": 4,
            "failed_calls": 1,
            "success_rate": 0.75,
            "total_tokens": 0,
            "avg_tokens_per_call": 0,
            "trends": [
                {
                    "time": "2026-01-01T00:00:00",
                    "total_calls": 4,
                    "failed_calls": 1,
                    "total_tokens": 0,
                }
            ],
        }

    async def list_events(self, filters, *, page, size):
        if filters.module_id == "persona.image_understanding":
            return {
                "items": [
                    {
                        "id": 101,
                        "module_id": filters.module_id,
                        "created_at": datetime(2026, 1, 1, 12, 0, 0),
                        "operation": "image_understanding",
                        "success": False,
                        "error_type": "RuntimeError",
                    }
                ],
                "total": 1,
                "page": page,
                "size": size,
            }

        return {
            "items": [
                {
                    "id": 201,
                    "module_id": filters.module_id,
                    "created_at": datetime(2026, 1, 1, 13, 0, 0),
                    "operation": "image_fetch",
                    "phase": "image_fetch",
                    "resolved_via": "url",
                    "success": True,
                }
            ],
            "total": 1,
            "page": page,
            "size": size,
        }

    async def list_rows(self, filters, *, fields=None):
        return [
            {
                "operation": "image_fetch",
                "phase": "image_fetch",
                "resolved_via": "url",
                "success": True,
                "created_at": datetime(2026, 1, 1, 12, 0, 0),
            },
            {
                "operation": "image_fetch",
                "phase": "image_fetch",
                "resolved_via": "get_file_by_file_id",
                "success": False,
                "created_at": datetime(2026, 1, 1, 12, 1, 0),
            },
            {
                "operation": "image_fetch",
                "phase": "image_fetch",
                "resolved_via": "failed",
                "success": True,
                "created_at": datetime(2026, 1, 1, 12, 2, 0),
            },
        ]

    async def list_options(self, filters):
        return {
            "plugin_names": ["persona"],
            "module_names": ["image_fetch"],
            "operations": ["image_fetch"],
            "phases": ["image_fetch"],
            "resolved_vias": ["failed", "get_file_by_file_id", "url"],
            "conv_ids": ["group_1"],
        }


def test_builtin_provider_factory_registers_phase3_modules():
    providers = build_builtin_module_metrics_providers(repository=_FakeRepository())
    module_ids = [provider.module_id for provider in providers]
    assert module_ids == [
        "persona.image_understanding",
        "persona.image_fetch",
    ]


def test_image_understanding_provider_outputs_line_overview_chart():
    provider = PersonaImageUnderstandingMetricsProvider(repository=_FakeRepository())

    payload = asyncio.run(
        provider.get_overview(
            ModuleMetricsQuery(conv_id="group_1"),
        )
    )

    assert payload["module_id"] == "persona.image_understanding"
    assert payload["main_chart"]["type"] == "line"
    assert payload["main_chart"]["chart_id"] == "persona.image_understanding.overview.main"
    assert payload["main_chart"]["x_axis"]["field"] == "time"
    assert payload["main_chart"]["series"][0]["field"] == "total_calls"


def test_image_understanding_provider_outputs_detail_chart_collection():
    provider = PersonaImageUnderstandingMetricsProvider(repository=_FakeRepository())

    payload = asyncio.run(
        provider.get_detail(
            ModuleMetricsQuery(conv_id="group_1"),
        )
    )

    chart_types = [chart["type"] for chart in payload["charts"]]
    assert payload["module_id"] == "persona.image_understanding"
    assert chart_types == ["kpi", "line", "line", "pie", "table"]
    assert payload["charts"][-1]["dataset"][0]["created_at"] == "2026-01-01T12:00:00"


def test_image_fetch_provider_outputs_pie_overview_chart():
    provider = PersonaImageFetchMetricsProvider(repository=_FakeRepository())

    payload = asyncio.run(
        provider.get_overview(
            ModuleMetricsQuery(conv_id="group_1"),
        )
    )

    assert payload["module_id"] == "persona.image_fetch"
    assert payload["main_chart"]["type"] == "pie"
    names = [item["name"] for item in payload["main_chart"]["dataset"]]
    assert names == ["failed", "get_file_by_file_id", "url"]


def test_image_fetch_provider_exposes_resolved_via_filter_options():
    provider = PersonaImageFetchMetricsProvider(repository=_FakeRepository())

    payload = asyncio.run(
        provider.get_filter_options(
            ModuleMetricsQuery(conv_id="group_1"),
        )
    )

    assert payload["plugin_names"] == ["persona"]
    assert payload["resolved_vias"] == ["failed", "get_file_by_file_id", "url"]
