import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List

from src.core.engine.persona_engine_core import PersonaEngineCore
from src.core.facade.persona_facade import PersonaFacade


class _FacadeEngineStub:
    def __init__(self) -> None:
        self.history_calls: List[Any] = []

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        self.history_calls.append((conv_id, list(messages)))
        return ["张三", "项目A"]


class _MsgProcessorStub:
    def __init__(self) -> None:
        self.history_calls: List[Any] = []

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        self.history_calls.append((conv_id, list(messages)))
        return ["张三", "项目A"]


def _build_engine(msgprocessor: _MsgProcessorStub) -> PersonaEngineCore:
    return PersonaEngineCore(
        config=SimpleNamespace(queue_history_size=20),
        plugin_name="persona",
        group_config=object(),
        message_repo=object(),
        memory_repo=object(),
        short_term=object(),
        long_term=object(),
        msgprocessor=msgprocessor,
        retriever=object(),
        decay_manager=object(),
    )


def test_persona_facade_exposes_history_keyword_api():
    engine = _FacadeEngineStub()
    facade = PersonaFacade(engine)
    messages = [{"content": "你还记得张三吗？"}]

    result = asyncio.run(facade.extract_reply_keywords_from_history("group_1", messages))

    assert result == ["张三", "项目A"]
    assert engine.history_calls == [("group_1", messages)]


def test_persona_engine_core_history_keyword_api_forwards_messages():
    msgprocessor = _MsgProcessorStub()
    engine = _build_engine(msgprocessor)
    messages = [{"content": "你还记得张三吗？", "is_bot": False}]

    result = asyncio.run(engine.extract_reply_keywords_from_history("group_2", messages))

    assert result == ["张三", "项目A"]
    assert msgprocessor.history_calls == [("group_2", messages)]
