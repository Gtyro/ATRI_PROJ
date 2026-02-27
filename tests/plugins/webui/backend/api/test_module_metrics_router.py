from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import HTTPException

# Avoid importing plugins.webui/__init__.py during tests, which requires NoneBot plugin runtime.
PROJECT_ROOT = Path(__file__).resolve().parents[5]
WEBUI_ROOT = PROJECT_ROOT / "plugins" / "webui"
BACKEND_ROOT = WEBUI_ROOT / "backend"
API_ROOT = BACKEND_ROOT / "api"

if "plugins.webui" not in sys.modules:
    module = ModuleType("plugins.webui")
    module.__path__ = [str(WEBUI_ROOT)]
    sys.modules["plugins.webui"] = module
if "plugins.webui.backend" not in sys.modules:
    module = ModuleType("plugins.webui.backend")
    module.__path__ = [str(BACKEND_ROOT)]
    sys.modules["plugins.webui.backend"] = module
if "plugins.webui.backend.api" not in sys.modules:
    module = ModuleType("plugins.webui.backend.api")
    module.__path__ = [str(API_ROOT)]
    sys.modules["plugins.webui.backend.api"] = module

module_metrics_router_module = importlib.import_module("plugins.webui.backend.api.module_metrics.router")
get_current_active_user = importlib.import_module("plugins.webui.backend.api.auth.utils").get_current_active_user


class _FakeModuleMetricsService:
    def __init__(self) -> None:
        self.modules_calls = []
        self.overview_calls = []
        self.detail_calls = []
        self.detail_filter_calls = []
        self.options_calls = []
        self.summary_calls = []
        self.events_calls = []

    def list_provider_modules(self):
        self.modules_calls.append({})
        return [
            {
                "module_id": "persona.image_understanding",
                "title": "图片理解",
            },
            {
                "module_id": "persona.image_fetch",
                "title": "图片拉取",
            },
        ]

    async def get_provider_overview(self, **kwargs):
        self.overview_calls.append(kwargs)
        module_ids = kwargs.get("module_ids")
        if module_ids and "missing.module" in module_ids:
            raise KeyError("missing.module")
        return {
            "items": [
                {
                    "module_id": "persona.image_understanding",
                    "title": "图片理解",
                    "main_chart": {"type": "line", "dataset": []},
                }
            ]
        }

    async def get_provider_detail(self, module_id: str, **kwargs):
        self.detail_calls.append({"module_id": module_id, **kwargs})
        if module_id == "missing.module":
            raise KeyError("missing.module")
        return {
            "module_id": module_id,
            "title": module_id,
            "charts": [],
        }

    async def get_provider_filter_options(self, module_id: str, **kwargs):
        self.detail_filter_calls.append({"module_id": module_id, **kwargs})
        if module_id == "missing.module":
            raise KeyError("missing.module")
        return {"resolved_vias": ["url", "get_image"]}

    async def get_options(self, **kwargs):
        self.options_calls.append(kwargs)
        return {
            "plugin_names": ["persona"],
            "module_names": ["image_understanding"],
            "operations": ["image_understanding"],
            "conv_ids": ["group_1"],
        }

    async def get_summary(self, **kwargs):
        self.summary_calls.append(kwargs)
        interval = kwargs.get("interval")
        if interval not in {"day", "hour"}:
            raise ValueError(f"unsupported interval: {interval}")
        return {
            "total_calls": 3,
            "failed_calls": 1,
            "success_rate": 2 / 3,
            "total_tokens": 40,
            "avg_tokens_per_call": 40 / 3,
            "trends": [],
        }

    async def get_events(self, **kwargs):
        self.events_calls.append(kwargs)
        return {
            "items": [
                {
                    "id": 101,
                    "plugin_name": "persona",
                    "module_name": "image_understanding",
                    "operation": "image_understanding",
                    "conv_id": "group_1",
                    "message_id": "msg_1",
                    "provider_name": "openai",
                    "model": "gpt-4o-mini",
                    "request_id": "req_1",
                    "success": False,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                    "error_type": "RuntimeError",
                    "extra": {},
                    "created_at": "2026-01-01T12:00:00",
                }
            ],
            "total": 1,
            "page": kwargs["page"],
            "size": kwargs["size"],
        }


def _fake_user():
    return SimpleNamespace(username="admin", disabled=False)


def test_module_metrics_router_declares_auth_dependency():
    assert any(dep.dependency is get_current_active_user for dep in module_metrics_router_module.router.dependencies)


def test_module_metrics_modules_lists_registered_providers(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    payload = asyncio.run(
        module_metrics_router_module.get_module_metric_modules(
            current_user=_fake_user(),
        )
    )

    assert [item["module_id"] for item in payload["items"]] == [
        "persona.image_understanding",
        "persona.image_fetch",
    ]
    assert len(fake_service.modules_calls) == 1


def test_module_metrics_overview_supports_module_id_list(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    payload = asyncio.run(
        module_metrics_router_module.get_module_metric_overview(
            from_time=datetime(2026, 1, 1, 0, 0, 0),
            to_time=datetime(2026, 1, 2, 0, 0, 0),
            module_id=[" persona.image_understanding ", "persona.image_fetch, persona.image_understanding"],
            conv_id="group_1",
            current_user=_fake_user(),
        )
    )

    assert payload["items"][0]["module_id"] == "persona.image_understanding"
    assert len(fake_service.overview_calls) == 1
    call = fake_service.overview_calls[0]
    assert call["module_ids"] == ["persona.image_understanding", "persona.image_fetch"]
    assert call["conv_id"] == "group_1"
    assert call["from_time"] == datetime(2026, 1, 1, 0, 0, 0)
    assert call["to_time"] == datetime(2026, 1, 2, 0, 0, 0)


def test_module_metrics_overview_rejects_unknown_module(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            module_metrics_router_module.get_module_metric_overview(
                module_id=["missing.module"],
                current_user=_fake_user(),
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "module provider 不存在: missing.module"


def test_module_metrics_detail_returns_filter_options(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    payload = asyncio.run(
        module_metrics_router_module.get_module_metric_module_detail(
            module_id="persona.image_understanding",
            from_time=datetime(2026, 1, 1, 0, 0, 0),
            to_time=datetime(2026, 1, 2, 0, 0, 0),
            conv_id="group_1",
            current_user=_fake_user(),
        )
    )

    assert payload["module_id"] == "persona.image_understanding"
    assert payload["filter_options"]["resolved_vias"] == ["url", "get_image"]
    assert len(fake_service.detail_calls) == 1
    assert len(fake_service.detail_filter_calls) == 1
    detail_call = fake_service.detail_calls[0]
    assert detail_call["conv_id"] == "group_1"
    assert detail_call["from_time"] == datetime(2026, 1, 1, 0, 0, 0)
    assert detail_call["to_time"] == datetime(2026, 1, 2, 0, 0, 0)


def test_module_metrics_detail_rejects_unknown_module(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            module_metrics_router_module.get_module_metric_module_detail(
                module_id="missing.module",
                current_user=_fake_user(),
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "module provider 不存在: missing.module"


def test_module_metrics_options_passes_conv_id_filters(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    payload = asyncio.run(
        module_metrics_router_module.get_module_metric_options(
            from_time=datetime(2026, 1, 1, 0, 0, 0),
            to_time=datetime(2026, 1, 2, 0, 0, 0),
            plugin_name="persona",
            module_name="image_understanding",
            operation="image_understanding",
            conv_id="group_1",
            current_user=_fake_user(),
        )
    )

    assert payload["conv_ids"] == ["group_1"]
    assert len(fake_service.options_calls) == 1
    call = fake_service.options_calls[0]
    assert call["plugin_name"] == "persona"
    assert call["module_name"] == "image_understanding"
    assert call["operation"] == "image_understanding"
    assert call["conv_id"] == "group_1"
    assert call["from_time"] == datetime(2026, 1, 1, 0, 0, 0)
    assert call["to_time"] == datetime(2026, 1, 2, 0, 0, 0)


def test_module_metrics_summary_rejects_invalid_interval(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            module_metrics_router_module.get_module_metric_summary(
                from_time=None,
                to_time=None,
                interval="week",
                current_user=_fake_user(),
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "unsupported interval: week"


def test_module_metrics_events_exposes_failure_items(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    payload = asyncio.run(
        module_metrics_router_module.get_module_metric_events(
            from_time=None,
            to_time=None,
            conv_id="group_1",
            page=2,
            size=5,
            current_user=_fake_user(),
        )
    )

    assert payload["page"] == 2
    assert payload["size"] == 5
    assert payload["total"] == 1
    assert payload["items"][0]["success"] is False
    assert payload["items"][0]["error_type"] == "RuntimeError"

    assert len(fake_service.events_calls) == 1
    call = fake_service.events_calls[0]
    assert call["conv_id"] == "group_1"
    assert call["page"] == 2
    assert call["size"] == 5


def test_module_metrics_router_rejects_invalid_time_range(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeModuleMetricsService()
    monkeypatch.setattr(module_metrics_router_module, "module_metrics_service", fake_service)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            module_metrics_router_module.get_module_metric_options(
                from_time=datetime(2026, 1, 2, 0, 0, 0),
                to_time=datetime(2026, 1, 1, 0, 0, 0),
                current_user=_fake_user(),
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "from 不能大于 to"
    assert fake_service.options_calls == []
