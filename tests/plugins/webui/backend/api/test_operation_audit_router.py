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

audit_router_module = importlib.import_module("plugins.webui.backend.api.audit.router")


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._offset = 0
        self._limit = len(rows)
        self.filters = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    async def count(self):
        return len(self._rows)

    def order_by(self, *_args):
        return self

    def offset(self, value: int):
        self._offset = value
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def __await__(self):
        async def _collect():
            end = self._offset + self._limit
            return self._rows[self._offset:end]

        return _collect().__await__()


def _fake_user():
    return SimpleNamespace(username="admin", disabled=False)


def test_list_operation_audit_logs_parses_detail_json(monkeypatch: pytest.MonkeyPatch):
    rows = [
        SimpleNamespace(
            id=1,
            username="admin",
            action="sql.table.update",
            target_type="statistics",
            target_id="1",
            success=True,
            detail='{"after":{"value":2}}',
            request_method="PUT",
            request_path="/db/table/statistics/update",
            ip_address="127.0.0.1",
            user_agent="pytest",
            created_at="2026-03-05T09:00:00",
        ),
    ]
    fake_query = _FakeQuery(rows)
    monkeypatch.setattr(audit_router_module.OperationAuditLog, "all", lambda: fake_query)

    payload = asyncio.run(
        audit_router_module.list_operation_audit_logs(
            limit=10,
            offset=0,
            username="admin",
            action="sql.table",
            target_type="statistics",
            success=True,
            current_user=_fake_user(),
        )
    )

    assert payload.total == 1
    assert len(payload.items) == 1
    assert payload.items[0].username == "admin"
    assert payload.items[0].detail == {"after": {"value": 2}}
    assert {"username__contains": "admin"} in fake_query.filters
    assert {"action__contains": "sql.table"} in fake_query.filters
    assert {"target_type": "statistics"} in fake_query.filters
    assert {"success": True} in fake_query.filters


def test_get_operation_audit_meta_exposes_known_options():
    payload = asyncio.run(
        audit_router_module.get_operation_audit_meta(
            current_user=_fake_user(),
        )
    )

    assert "sql.table.insert" in payload.actions
    assert "plugin_policy.batch_update" in payload.actions
    assert "sql_table" in payload.target_types
    assert "audit_log" in payload.target_types
    assert payload.default_retention_days >= 1


def test_cleanup_operation_audit_logs_records_cleanup_audit(monkeypatch: pytest.MonkeyPatch):
    async def fake_cleanup(*, retention_days: int):
        assert retention_days == 90
        return 12

    captured = {}

    async def fake_record(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        audit_router_module,
        "cleanup_expired_operation_audit_logs",
        fake_cleanup,
    )
    monkeypatch.setattr(
        audit_router_module,
        "record_operation_audit",
        fake_record,
    )

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/audit/cleanup"),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
    )

    payload = asyncio.run(
        audit_router_module.cleanup_operation_audit_logs(
            request=request,
            retention_days=90,
            current_user=_fake_user(),
        )
    )

    assert payload.retention_days == 90
    assert payload.deleted == 12
    assert captured["action"] == "audit.log.cleanup"
    assert captured["target_type"] == "audit_log"
