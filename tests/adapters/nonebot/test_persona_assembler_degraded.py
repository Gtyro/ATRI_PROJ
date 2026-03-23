import asyncio
from types import SimpleNamespace

from src.adapters.nonebot import persona_assembler
from src.infra.db.neo4j.unavailable import UnavailableMemoryRepository


class _MessageRepositoryStub:
    def __init__(self, config) -> None:
        self.config = config

    async def initialize(self) -> None:
        return None

    async def cleanup_stale_messages(self, *, keep_count: int, max_age_days: int) -> int:
        return 0

    async def get_queue_stats(self, conv_id=None):
        return {"total_messages": 0, "unprocessed_messages": 0}

    async def close(self) -> None:
        return None


class _ProviderStub:
    def __init__(self) -> None:
        self.memory_retrieval_callback = None

    async def extract_topics(self, conv_id, messages):
        return []

    async def extract_reply_keywords_from_history(self, conv_id, messages):
        return []

    async def generate_response(
        self,
        conv_id,
        messages,
        temperature=0.7,
        long_memory_prompt="",
        tool_choice="required",
    ):
        return ""

    def set_memory_retrieval_callback(self, callback) -> None:
        self.memory_retrieval_callback = callback


class _RegistryStub:
    def __init__(self) -> None:
        self.provider = _ProviderStub()

    def create(self, name, **kwargs):
        return self.provider


class _GroupConfigStub:
    async def get_distinct_group_ids(self, plugin_name):
        return []


class _ImageUnderstanderStub:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.callback = None

    def set_usage_event_callback(self, callback) -> None:
        self.callback = callback


def test_assemble_persona_engine_degrades_when_neo4j_unavailable(tmp_path, monkeypatch):
    registry = _RegistryStub()

    async def _fake_initialize_neo4j(config, allow_unavailable=False):
        assert allow_unavailable is True
        return UnavailableMemoryRepository("connection refused")

    monkeypatch.setattr(persona_assembler, "MessageRepository", _MessageRepositoryStub)
    monkeypatch.setattr(persona_assembler, "initialize_neo4j", _fake_initialize_neo4j)
    monkeypatch.setattr(persona_assembler, "get_llm_provider_registry", lambda: registry)
    monkeypatch.setattr(persona_assembler, "NapcatImageResolver", lambda timeout_seconds: object())
    monkeypatch.setattr(persona_assembler, "ImageUnderstander", _ImageUnderstanderStub)
    monkeypatch.setattr(persona_assembler, "ImageContextService", lambda **kwargs: object())

    config = SimpleNamespace(
        db_path=str(tmp_path / "persona.db"),
        queue_history_size=20,
        batch_interval=1800,
        use_postgres=False,
        model="test-model",
        base_url="https://example.com",
        api_key="test-key",
        extras={},
        node_decay_rate=0.1,
        image_understanding=SimpleNamespace(
            api_key="ik",
            base_url="https://img.example.com",
            model="img-model",
            timeout_seconds=30.0,
            http_timeout_seconds=10.0,
            max_tokens=256,
        ),
    )

    engine = asyncio.run(
        persona_assembler.assemble_persona_engine(
            config=config,
            group_config=_GroupConfigStub(),
            plugin_name="persona",
        )
    )

    assert engine.neo4j_available is False
    assert engine.memory_repo.is_available() is False

    status_reply = asyncio.run(engine.get_queue_status_reply())
    assert "降级模式" in status_reply
    assert registry.provider.memory_retrieval_callback is not None
