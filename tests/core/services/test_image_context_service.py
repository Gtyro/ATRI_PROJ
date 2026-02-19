import asyncio
import logging

from src.adapters.nonebot.image_resolver import ResolvedImage
from src.core.services.image_context_service import ImageContextService


class _FakeResolver:
    def __init__(self, result_by_url):
        self.result_by_url = result_by_url
        self.calls = []

    async def resolve(self, *, conv_id, message_id, image_meta):
        self.calls.append((conv_id, message_id, image_meta))
        url = image_meta.get("url")
        return self.result_by_url.get(url)


class _FakeUnderstander:
    def __init__(self, summaries):
        self.summaries = summaries
        self.calls = []

    async def summarize_images(self, images, *, usage_contexts=None):
        self.calls.append({"images": images, "usage_contexts": usage_contexts})
        return list(self.summaries[: len(images)])


class _FakeRepo:
    def __init__(self):
        self.updated = []

    async def update_message_metadata(self, message_id, metadata):
        self.updated.append((message_id, metadata))
        return True


def test_build_context_uses_cache_and_persists_new_summary(caplog):
    resolver = _FakeResolver(
        {
            "https://example.com/new.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"img",
                original_url="https://example.com/new.jpg",
            )
        }
    )
    understander = _FakeUnderstander(["新图片摘要"])
    repo = _FakeRepo()
    service = ImageContextService(
        config={
            "image_understanding": {
                "max_images_per_round": 5,
                "analyze_window_size": 20,
                "cache_enabled": True,
            }
        },
        image_resolver=resolver,
        image_understander=understander,
        message_repo=repo,
    )

    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "metadata": {"media": {"images": [{"url": "https://example.com/new.jpg"}]}},
        },
        {
            "id": 2,
            "user_name": "Bob",
            "metadata": {
                "media": {
                    "images": [
                        {
                            "url": "https://example.com/cached.jpg",
                            "understanding": {"summary": "缓存摘要"},
                        }
                    ]
                }
            },
        },
    ]

    with caplog.at_level(logging.INFO):
        context = asyncio.run(service.build_context("group_1", messages))

    assert "- Bob 发图：缓存摘要" in context
    assert "- Alice 发图：新图片摘要" in context
    assert len(resolver.calls) == 1
    assert len(understander.calls) == 1
    usage_context = understander.calls[0]["usage_contexts"][0]
    assert usage_context["plugin_name"] == "persona"
    assert usage_context["module_name"] == "image_understanding"
    assert usage_context["operation"] == "image_understanding"
    assert usage_context["conv_id"] == "group_1"
    assert usage_context["message_id"] == 1
    assert repo.updated[0][0] == 1
    assert (
        repo.updated[0][1]["media"]["images"][0]["understanding"]["summary"]
        == "新图片摘要"
    )
    assert "image_cache_hit=1" in caplog.text
    assert "image_understanding_cost=1" in caplog.text
    assert "image_fetch_source(url)=1" in caplog.text


def test_build_context_respects_max_images_budget(caplog):
    resolver = _FakeResolver(
        {
            "https://example.com/1.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"1",
                original_url="https://example.com/1.jpg",
            ),
            "https://example.com/2.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"2",
                original_url="https://example.com/2.jpg",
            ),
        }
    )
    understander = _FakeUnderstander(["摘要1", "摘要2"])
    repo = _FakeRepo()
    service = ImageContextService(
        config={
            "image_understanding": {
                "max_images_per_round": 1,
                "analyze_window_size": 20,
                "cache_enabled": True,
            }
        },
        image_resolver=resolver,
        image_understander=understander,
        message_repo=repo,
    )

    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "metadata": {"media": {"images": [{"url": "https://example.com/1.jpg"}]}},
        },
        {
            "id": 2,
            "user_name": "Bob",
            "metadata": {"media": {"images": [{"url": "https://example.com/2.jpg"}]}},
        },
    ]

    with caplog.at_level(logging.INFO):
        context = asyncio.run(service.build_context("group_1", messages))

    assert "- Bob 发图：摘要1" in context
    assert "Alice" not in context
    assert len(resolver.calls) == 1
    usage_context = understander.calls[0]["usage_contexts"][0]
    assert usage_context["conv_id"] == "group_1"
    assert usage_context["message_id"] == 2
    assert len(repo.updated) == 1
    assert "image_understanding_cost=1" in caplog.text
    assert "image_fetch_source(url)=1" in caplog.text


def test_build_context_respects_segment_index_order_within_message(caplog):
    resolver = _FakeResolver(
        {
            "https://example.com/1.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"1",
                original_url="https://example.com/1.jpg",
            ),
            "https://example.com/2.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"2",
                original_url="https://example.com/2.jpg",
            ),
        }
    )
    understander = _FakeUnderstander(["首图摘要"])
    repo = _FakeRepo()
    service = ImageContextService(
        config={
            "image_understanding": {
                "max_images_per_round": 1,
                "analyze_window_size": 20,
                "cache_enabled": True,
            }
        },
        image_resolver=resolver,
        image_understander=understander,
        message_repo=repo,
    )

    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "metadata": {
                "media": {
                    "images": [
                        {"url": "https://example.com/2.jpg", "segment_index": 2},
                        {"url": "https://example.com/1.jpg", "segment_index": 0},
                    ]
                }
            },
        }
    ]

    with caplog.at_level(logging.INFO):
        context = asyncio.run(service.build_context("group_1", messages))

    assert resolver.calls[0][2]["url"] == "https://example.com/1.jpg"
    assert "- Alice 发图：首图摘要" in context


def test_build_context_logs_zero_cost_when_no_recent_messages(caplog):
    service = ImageContextService(
        config={"image_understanding": {}},
        image_resolver=_FakeResolver({}),
        image_understander=_FakeUnderstander([]),
        message_repo=_FakeRepo(),
    )

    with caplog.at_level(logging.INFO):
        context = asyncio.run(service.build_context("group_1", []))

    assert context == ""
    assert "images=0" in caplog.text
    assert "image_understanding_cost=0" in caplog.text
