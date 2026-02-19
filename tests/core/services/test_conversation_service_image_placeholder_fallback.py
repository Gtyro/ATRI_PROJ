import asyncio
from typing import Any, Dict, List

from src.core.services.conversation_service import ConversationService


class _ShortTermStub:
    def __init__(self, messages: List[Dict[str, Any]]):
        self._messages = list(messages)
        self.bot_messages: List[str] = []

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        return list(self._messages)

    async def mark_processed(self, conv_id: str, topics: List[Dict[str, Any]]) -> int:
        return 0

    async def get_recent_messages(self, conv_id: str, limit: int) -> List[Dict[str, Any]]:
        return [dict(msg) for msg in self._messages]

    async def add_bot_message(self, conv_id: str, content: str) -> None:
        self.bot_messages.append(content)


class _LongTermStub:
    async def store_memories(self, conv_id: str, memories: List[Dict[str, Any]]) -> List[str]:
        return []


class _MessageRepoStub:
    async def has_bot_message(self, conv_id: str) -> bool:
        return False


class _GroupConfigEntry:
    def __init__(self):
        self.plugin_config: Dict[str, Any] = {}

    async def save(self) -> None:
        return None


class _GroupConfigStub:
    def __init__(self):
        self.entry = _GroupConfigEntry()

    async def get_config(self, group_id: str, plugin_name: str) -> _GroupConfigEntry:
        return self.entry


class _Policy:
    def __init__(self, config: Dict[str, Any]):
        self.config = config


class _PolicyServiceStub:
    def __init__(self, *, topic_extract_enabled: bool = False):
        self._policy = _Policy(
            {
                "llm_topic_extract_enabled": topic_extract_enabled,
                "llm_active_reply_enabled": True,
                "llm_passive_reply_enabled": False,
            }
        )

    async def is_enabled(self, group_id: str, plugin_name: str) -> bool:
        return True

    async def is_ingest_enabled(self, group_id: str, plugin_name: str) -> bool:
        return True

    async def get_policy(self, group_id: str, plugin_name: str) -> _Policy:
        return self._policy


class _ImageContextServiceStub:
    def __init__(self, context: str):
        self.context = context

    async def build_context(self, conv_id: str, recent_messages: List[Dict[str, Any]]) -> str:
        return self.context


class _MessageProcessorStub:
    def __init__(self):
        self.last_messages: List[Dict[str, Any]] = []
        self.last_keyword_messages: List[Dict[str, Any]] = []
        self.last_long_memory_prompt = ""

    async def extract_topics_from_messages(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return []

    async def should_respond(self, conv_id: str, topics: List[Dict[str, Any]]) -> bool:
        return True

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        self.last_keyword_messages = [dict(item) for item in messages]
        return []

    async def retrieve_memory_context(self, conv_id: str, keywords: List[str]) -> str:
        return ""

    async def generate_reply(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        self.last_messages = [dict(item) for item in messages]
        self.last_long_memory_prompt = long_memory_prompt
        return "收到"


def _build_service(
    *,
    messages: List[Dict[str, Any]],
    image_context: str,
    topic_extract_enabled: bool = False,
) -> _MessageProcessorStub:
    processor = _MessageProcessorStub()
    service = ConversationService(
        short_term=_ShortTermStub(messages),
        long_term=_LongTermStub(),
        msgprocessor=processor,
        message_repo=_MessageRepoStub(),
        group_config=_GroupConfigStub(),
        plugin_name="persona",
        config={
            "queue_history_size": 1,
            "batch_interval": 1800,
            "image_understanding": {"enabled": True, "retrieval_ab_mode": "hybrid"},
        },
        plugin_policy_service=_PolicyServiceStub(topic_extract_enabled=topic_extract_enabled),
        image_context_service=_ImageContextServiceStub(image_context),
    )
    asyncio.run(service.process_conversation("group_300", user_id="10001", is_direct=False))
    return processor


def test_failed_image_understanding_keeps_original_text_without_placeholder_fallback():
    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "content": "笑死",
            "is_bot": False,
            "is_direct": False,
            "metadata": {
                "media": {
                    "images": [
                        {
                            "url": "https://example.com/1.jpg",
                            "understanding": {"summary": "", "error": "understand_failed"},
                        }
                    ]
                }
            },
        }
    ]

    processor = _build_service(messages=messages, image_context="")

    assert processor.last_messages[0]["content"] == "笑死"
    assert processor.last_long_memory_prompt == ""


def test_successful_image_understanding_keeps_original_text_history():
    messages = [
        {
            "id": 2,
            "user_name": "Alice",
            "content": "笑死",
            "is_bot": False,
            "is_direct": False,
            "metadata": {
                "media": {
                    "images": [
                        {
                            "url": "https://example.com/2.jpg",
                            "understanding": {"summary": "一个人在笑", "error": ""},
                        }
                    ]
                }
            },
        }
    ]

    processor = _build_service(
        messages=messages,
        image_context="【图片上下文】\n- Alice 发图：一个人在笑",
    )

    assert processor.last_messages[0]["content"] == "笑死"
    assert "【图片上下文】" in processor.last_long_memory_prompt


def test_successful_image_understanding_replaces_image_placeholder_in_history():
    messages = [
        {
            "id": 3,
            "user_name": "Alice",
            "content": "看这个 [图片]",
            "is_bot": False,
            "is_direct": False,
            "metadata": {
                "media": {
                    "images": [
                        {
                            "url": "https://example.com/3.jpg",
                            "understanding": {"summary": "一张恐怖游戏场景截图", "error": ""},
                        }
                    ]
                }
            },
        }
    ]

    processor = _build_service(
        messages=messages,
        image_context="【图片上下文】\n- Alice 发图：一张恐怖游戏场景截图",
    )

    assert processor.last_keyword_messages[0]["content"] == "看这个 [图片内容: 一张恐怖游戏场景截图]"
    assert processor.last_messages[0]["content"] == "看这个 [图片内容: 一张恐怖游戏场景截图]"


def test_successful_image_understanding_replaces_multiple_placeholders_in_segment_order():
    messages = [
        {
            "id": 4,
            "user_name": "Alice",
            "content": "先看 [图片] 再看 [图片]",
            "is_bot": False,
            "is_direct": False,
            "metadata": {
                "media": {
                    "images": [
                        {
                            "segment_index": 3,
                            "url": "https://example.com/4b.jpg",
                            "understanding": {"summary": "第二张图", "error": ""},
                        },
                        {
                            "segment_index": 1,
                            "url": "https://example.com/4a.jpg",
                            "understanding": {"summary": "第一张图", "error": ""},
                        },
                    ]
                }
            },
        }
    ]

    processor = _build_service(
        messages=messages,
        image_context="【图片上下文】\n- Alice 发图：第一张图\n- Alice 发图：第二张图",
    )

    expected = "先看 [图片内容: 第一张图] 再看 [图片内容: 第二张图]"
    assert processor.last_keyword_messages[0]["content"] == expected
    assert processor.last_messages[0]["content"] == expected
