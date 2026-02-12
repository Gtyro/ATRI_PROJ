import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.infra.db.neo4j.memory_repository import MemoryRepository
from src.infra.db.neo4j import memory_repository as memory_repository_module


def test_update_or_create_node_uses_epoch_seconds(monkeypatch):
    repo = MemoryRepository(config_dict={})
    captured = {}

    async def fake_run_cypher(query, params=None):
        captured["query"] = query
        captured["params"] = params or {}
        return [[object()]], {}

    monkeypatch.setattr(repo, "run_cypher", fake_run_cypher)
    monkeypatch.setattr(
        memory_repository_module.CognitiveNode,
        "inflate",
        staticmethod(lambda _: SimpleNamespace(name="n1", uid="uid-1")),
    )

    node = asyncio.run(repo.update_or_create_node("group_1", "topic_1"))

    assert node.name == "n1"
    assert "created_at = $now_ts" in captured["query"]
    assert "last_accessed = $now_ts" in captured["query"]
    assert isinstance(captured["params"]["now_ts"], float)
    assert captured["params"]["now_ts"] > 0


def test_store_association_uses_epoch_seconds(monkeypatch):
    repo = MemoryRepository(config_dict={})
    captured = {}

    async def fake_run_cypher(query, params=None):
        captured["query"] = query
        captured["params"] = params or {}
        return [["a", "b"]], {}

    monkeypatch.setattr(repo, "run_cypher", fake_run_cypher)

    result = asyncio.run(repo.store_association("node-a", "node-b"))

    assert result is True
    assert "r1.created_at = $now_ts" in captured["query"]
    assert "r2.updated_at = $now_ts" in captured["query"]
    assert isinstance(captured["params"]["now_ts"], float)
    assert captured["params"]["now_ts"] > 0


def test_delete_memories_by_time_range_converts_datetime_to_epoch(monkeypatch):
    repo = MemoryRepository(config_dict={})
    captured_calls = []

    async def fake_run_cypher(query, params=None):
        captured_calls.append((query, params or {}))
        return [], {}

    monkeypatch.setattr(repo, "run_cypher", fake_run_cypher)

    start = datetime(2026, 2, 7, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 2, 7, 20, 0, tzinfo=timezone.utc)
    asyncio.run(repo.delete_memories_by_time_range("group_1", start, end))

    assert len(captured_calls) == 1
    _, params = captured_calls[0]
    assert params["conv_id"] == "group_1"
    assert params["start_time"] == pytest.approx(start.timestamp())
    assert params["end_time"] == pytest.approx(end.timestamp())
