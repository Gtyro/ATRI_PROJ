from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


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

database_module = importlib.import_module("plugins.webui.backend.api.core.database")


def test_initialize_database_system_degrades_when_neo4j_unavailable(monkeypatch: pytest.MonkeyPatch):
    async def _fake_initialize_neo4j(*, allow_unavailable=False):
        assert allow_unavailable is True
        return object()

    monkeypatch.setattr(database_module, "initialize_neo4j", _fake_initialize_neo4j)
    monkeypatch.setattr(database_module, "neo4j_is_available", lambda: False)
    monkeypatch.setattr(database_module, "get_neo4j_unavailable_reason", lambda: "connection refused")

    initialized = asyncio.run(database_module.initialize_database_system())

    assert initialized is False
