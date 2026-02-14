import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from src.core.engine.persona_engine_core import PersonaEngineCore


class _MessageRepoStub:
    def __init__(self) -> None:
        self.deleted_ranges: List[Tuple[str, datetime, datetime]] = []

    async def delete_messages_by_time_range(
        self,
        conv_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        self.deleted_ranges.append((conv_id, start_time, end_time))
        return 2


class _MemoryRepoStub:
    def __init__(self) -> None:
        self.deleted_ranges: List[Tuple[str, datetime, datetime]] = []

    async def delete_memories_by_time_range(
        self,
        conv_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self.deleted_ranges.append((conv_id, start_time, end_time))


class _ShortTermStub:
    def __init__(self) -> None:
        self.added_messages: List[Dict[str, Any]] = []

    async def add_message(self, message_data: Dict[str, Any]) -> None:
        self.added_messages.append(message_data)


class _LongTermStub:
    def __init__(self) -> None:
        self.store_calls = 0

    async def store_memories(self, conv_id: str, memories: List[Dict[str, Any]]) -> List[str]:
        self.store_calls += 1
        return []


class _MsgProcessorStub:
    def __init__(self) -> None:
        self.extract_topic_calls = 0
        self.generate_reply_calls = 0

    async def extract_topics_from_messages(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.extract_topic_calls += 1
        return []

    async def generate_reply(self, conv_id: str, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        self.generate_reply_calls += 1
        return ""


def _build_engine(
    *,
    message_repo: _MessageRepoStub,
    memory_repo: _MemoryRepoStub,
    short_term: _ShortTermStub,
    long_term: _LongTermStub,
    msgprocessor: _MsgProcessorStub,
    reply_calls: List[Dict[str, Any]],
) -> PersonaEngineCore:
    async def _reply_callback(conv_id: str, message_dict: Dict[str, Any]) -> None:
        reply_calls.append({"conv_id": conv_id, "message_dict": message_dict})

    return PersonaEngineCore(
        config=SimpleNamespace(queue_history_size=20, batch_interval=1800),
        plugin_name="persona",
        group_config=object(),
        message_repo=message_repo,
        memory_repo=memory_repo,
        short_term=short_term,
        long_term=long_term,
        msgprocessor=msgprocessor,
        retriever=object(),
        decay_manager=object(),
        reply_callback=_reply_callback,
    )


def test_parse_chat_history_imports_short_term_only(tmp_path):
    message_repo = _MessageRepoStub()
    memory_repo = _MemoryRepoStub()
    short_term = _ShortTermStub()
    long_term = _LongTermStub()
    msgprocessor = _MsgProcessorStub()
    reply_calls: List[Dict[str, Any]] = []
    engine = _build_engine(
        message_repo=message_repo,
        memory_repo=memory_repo,
        short_term=short_term,
        long_term=long_term,
        msgprocessor=msgprocessor,
        reply_calls=reply_calls,
    )

    history_file = tmp_path / "chat.log"
    history_file.write_text(
        "2026-02-01 09:00:00 Alice(10001)\n"
        "早上好\n"
        "2026-02-01 09:05:00 Atri(9000)\n"
        "你好\n",
        encoding="utf-8",
    )

    messages = asyncio.run(
        engine.parse_chat_history(
            bot_id="9000",
            file_path=str(history_file),
            conv_id="group_42",
        )
    )

    assert len(messages) == 2
    assert messages[0]["content"] == "早上好"
    assert messages[1]["content"] == "你好"
    assert messages[0]["is_bot"] is False
    assert messages[1]["is_bot"] is True

    expected_start = datetime(2026, 2, 1, 9, 0, 0)
    expected_end = datetime(2026, 2, 1, 9, 5, 0)
    assert message_repo.deleted_ranges == [("group_42", expected_start, expected_end)]
    assert memory_repo.deleted_ranges == [("group_42", expected_start, expected_end)]

    assert short_term.added_messages == messages
    assert long_term.store_calls == 0
    assert msgprocessor.extract_topic_calls == 0
    assert msgprocessor.generate_reply_calls == 0
    assert reply_calls == []


def test_parse_chat_history_empty_result_has_no_side_effect(tmp_path):
    message_repo = _MessageRepoStub()
    memory_repo = _MemoryRepoStub()
    short_term = _ShortTermStub()
    long_term = _LongTermStub()
    msgprocessor = _MsgProcessorStub()
    reply_calls: List[Dict[str, Any]] = []
    engine = _build_engine(
        message_repo=message_repo,
        memory_repo=memory_repo,
        short_term=short_term,
        long_term=long_term,
        msgprocessor=msgprocessor,
        reply_calls=reply_calls,
    )

    history_file = tmp_path / "empty.log"
    history_file.write_text("这不是可解析格式\n", encoding="utf-8")

    messages = asyncio.run(
        engine.parse_chat_history(
            bot_id="9000",
            file_path=str(history_file),
            conv_id="group_42",
        )
    )

    assert messages == []
    assert short_term.added_messages == []
    assert message_repo.deleted_ranges == []
    assert memory_repo.deleted_ranges == []
    assert long_term.store_calls == 0
    assert msgprocessor.extract_topic_calls == 0
    assert msgprocessor.generate_reply_calls == 0
    assert reply_calls == []
