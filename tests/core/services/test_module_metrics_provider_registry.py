import asyncio

import pytest

from src.core.services.module_metrics_provider import ModuleMetricsProviderRegistry
from src.core.services.module_metrics_service import ModuleMetricsService


class _FakeProvider:
    def __init__(self, module_id: str):
        self.module_id = module_id
        self.overview_calls = []
        self.detail_calls = []
        self.filter_calls = []

    def get_module_definition(self):
        return {"module_id": self.module_id, "title": self.module_id}

    async def get_overview(self, query):
        self.overview_calls.append(query)
        return {"title": f"overview:{self.module_id}"}

    async def get_detail(self, query):
        self.detail_calls.append(query)
        return {"title": f"detail:{self.module_id}"}

    async def get_filter_options(self, query):
        self.filter_calls.append(query)
        return {"values": [self.module_id]}


def test_provider_registry_rejects_duplicate_module_id():
    registry = ModuleMetricsProviderRegistry()
    registry.register(_FakeProvider("persona.image_understanding"))

    with pytest.raises(ValueError):
        registry.register(_FakeProvider("persona.image_understanding"))


def test_module_metrics_service_dispatches_provider_calls():
    provider = _FakeProvider("persona.image_understanding")
    registry = ModuleMetricsProviderRegistry([provider])
    service = ModuleMetricsService(provider_registry=registry)

    overview = asyncio.run(
        service.get_provider_overview(
            module_ids=[" persona.image_understanding "],
            plugin_name=" persona ",
            module_name=" image_understanding ",
            operation=" image_understanding ",
            conv_id=" group_1 ",
        )
    )
    detail = asyncio.run(
        service.get_provider_detail(
            "persona.image_understanding",
            conv_id=" group_1 ",
        )
    )
    options = asyncio.run(service.get_provider_filter_options("persona.image_understanding"))

    assert overview["items"][0]["module_id"] == "persona.image_understanding"
    assert detail["module_id"] == "persona.image_understanding"
    assert options == {"values": ["persona.image_understanding"]}
    assert provider.overview_calls[0].plugin_name == "persona"
    assert provider.overview_calls[0].module_name == "image_understanding"
    assert provider.overview_calls[0].operation == "image_understanding"
    assert provider.overview_calls[0].conv_id == "group_1"
    assert provider.detail_calls[0].conv_id == "group_1"
