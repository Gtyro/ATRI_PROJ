import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.infra.db import neo4j_gateway


class _FailingMemoryRepository:
    def __init__(self, config):
        self.config = config

    async def initialize(self):
        raise RuntimeError("connection refused")


def _config_stub():
    return SimpleNamespace(
        neo4j_config=SimpleNamespace(
            uri="bolt://127.0.0.1:7687",
            user="neo4j",
        )
    )


def test_initialize_neo4j_can_fall_back_to_unavailable_repository(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(neo4j_gateway, "MemoryRepository", _FailingMemoryRepository)
    monkeypatch.setattr(neo4j_gateway, "_memory_repo", None)
    monkeypatch.setattr(neo4j_gateway, "_active_connection", None)

    repo = asyncio.run(
        neo4j_gateway.initialize_neo4j(
            _config_stub(),
            allow_unavailable=True,
        )
    )

    assert repo.is_available() is False
    assert neo4j_gateway.neo4j_is_available() is False
    assert "connection refused" in neo4j_gateway.get_neo4j_unavailable_reason()


def test_execute_neo4j_query_returns_503_when_neo4j_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(neo4j_gateway, "MemoryRepository", _FailingMemoryRepository)
    monkeypatch.setattr(neo4j_gateway, "_memory_repo", None)
    monkeypatch.setattr(neo4j_gateway, "_active_connection", None)

    asyncio.run(
        neo4j_gateway.initialize_neo4j(
            _config_stub(),
            allow_unavailable=True,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(neo4j_gateway.execute_neo4j_query("RETURN 1"))

    assert exc_info.value.status_code == 503
    assert "Neo4j不可用" in str(exc_info.value.detail)
