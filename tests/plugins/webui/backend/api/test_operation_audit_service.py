from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

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

audit_service_module = importlib.import_module("plugins.webui.backend.api.audit.service")


def test_sanitize_payload_masks_sensitive_fields():
    payload = {
        "username": "admin",
        "password": "top-secret",
        "nested": {
            "access_token": "abc",
            "safe": "ok",
        },
    }

    sanitized = audit_service_module.sanitize_payload(payload)

    assert sanitized["username"] == "admin"
    assert sanitized["password"] == "***"
    assert sanitized["nested"]["access_token"] == "***"
    assert sanitized["nested"]["safe"] == "ok"


def test_is_mutating_cypher_detects_write_keywords():
    assert audit_service_module.is_mutating_cypher("CREATE (n:Node {name: 'x'})")
    assert audit_service_module.is_mutating_cypher("  MERGE (n:Node {name: 'x'})")
    assert not audit_service_module.is_mutating_cypher("MATCH (n:Node) RETURN n")


def test_record_operation_audit_writes_log_row(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(audit_service_module.OperationAuditLog, "create", fake_create)
    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/plugin-policy/policy"),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest-agent"},
    )

    asyncio.run(
        audit_service_module.record_operation_audit(
            username="admin",
            action="plugin_policy.update",
            target_type="plugin_policy",
            target_id="group_1:persona",
            request=request,
            success=False,
            after={"token": "secret-token", "enabled": True},
            error_message="update failed",
        )
    )

    assert captured["username"] == "admin"
    assert captured["action"] == "plugin_policy.update"
    assert captured["target_type"] == "plugin_policy"
    assert captured["target_id"] == "group_1:persona"
    assert captured["success"] is False
    assert captured["request_method"] == "POST"
    assert captured["request_path"] == "/api/plugin-policy/policy"
    assert captured["ip_address"] == "127.0.0.1"
    assert captured["user_agent"] == "pytest-agent"
    assert '"token": "***"' in captured["detail"]
    assert '"error": "update failed"' in captured["detail"]
