import asyncio
import logging

from src.adapters.nonebot.image_resolver import ResolvedImage
from src.core.services.image_context_service import ImageContextService


class _FakeResolver:
    def __init__(self, result_by_url, telemetry_by_url=None):
        self.result_by_url = result_by_url
        self.telemetry_by_url = telemetry_by_url or {}
        self.calls = []

    async def resolve(
        self,
        *,
        conv_id,
        message_id,
        image_meta,
        onebot_self_id="",
        onebot_message_id="",
        telemetry=None,
    ):
        self.calls.append((conv_id, message_id, image_meta, onebot_self_id, onebot_message_id))
        url = image_meta.get("url")
        payload = self.telemetry_by_url.get(url)
        if isinstance(telemetry, dict) and isinstance(payload, dict):
            telemetry.update(payload)
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
    assert resolver.calls[0][3] == ""
    assert len(understander.calls) == 1
    usage_context = understander.calls[0]["usage_contexts"][0]
    assert usage_context["plugin_name"] == "persona"
    assert usage_context["module_name"] == "image_understanding"
    assert usage_context["operation"] == "image_understanding"
    assert usage_context["conv_id"] == "group_1"
    assert usage_context["message_id"] == 1
    assert usage_context["fetch_source"] == "url"
    assert repo.updated[0][0] == 1
    assert (
        repo.updated[0][1]["media"]["images"][0]["understanding"]["summary"]
        == "新图片摘要"
    )
    assert (
        repo.updated[0][1]["media"]["images"][0]["understanding"]["resolved_via"]
        == "url"
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
    assert resolver.calls[0][3] == ""
    usage_context = understander.calls[0]["usage_contexts"][0]
    assert usage_context["conv_id"] == "group_1"
    assert usage_context["message_id"] == 2
    assert usage_context["fetch_source"] == "url"
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


def test_build_context_forwards_onebot_self_id_to_resolver():
    resolver = _FakeResolver(
        {
            "https://example.com/1.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"1",
                original_url="https://example.com/1.jpg",
            )
        }
    )
    service = ImageContextService(
        config={
            "image_understanding": {
                "max_images_per_round": 1,
                "analyze_window_size": 20,
                "cache_enabled": False,
            }
        },
        image_resolver=resolver,
        image_understander=_FakeUnderstander(["摘要"]),
        message_repo=_FakeRepo(),
    )
    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "metadata": {
                "onebot": {"self_id": "10086"},
                "media": {"images": [{"url": "https://example.com/1.jpg"}]},
            },
        }
    ]

    asyncio.run(service.build_context("group_1", messages))

    assert len(resolver.calls) == 1
    assert resolver.calls[0][3] == "10086"


def test_build_context_cache_hit_skips_re_resolve_and_re_understand():
    resolver = _FakeResolver(
        {
            "https://example.com/1.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"1",
                original_url="https://example.com/1.jpg",
            )
        }
    )
    understander = _FakeUnderstander(["首次摘要"])
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
        }
    ]

    first = asyncio.run(service.build_context("group_1", messages))
    second = asyncio.run(service.build_context("group_1", messages))

    assert "- Alice 发图：首次摘要" in first
    assert "- Alice 发图：首次摘要" in second
    assert len(resolver.calls) == 1
    assert len(understander.calls) == 1
    assert len(repo.updated) == 1


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


def test_build_context_resolve_failed_marks_resolved_via_failed():
    resolver = _FakeResolver({})
    understander = _FakeUnderstander([])
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
            "metadata": {"media": {"images": [{"url": "https://example.com/missing.jpg"}]}},
        }
    ]

    context = asyncio.run(service.build_context("group_1", messages))

    assert context == ""
    assert len(repo.updated) == 1
    understanding = repo.updated[0][1]["media"]["images"][0]["understanding"]
    assert understanding["resolved_via"] == "failed"
    assert understanding["error"] == "resolve_failed"


def test_build_context_logs_resolver_error_category_and_retry_stats(caplog):
    resolver = _FakeResolver(
        {
            "https://example.com/new.jpg": ResolvedImage(
                source="url",
                mime="image/jpeg",
                image_bytes=b"img",
                original_url="https://example.com/new.jpg",
            )
        },
        telemetry_by_url={
            "https://example.com/new.jpg": {
                "error_category_count": {"timeout": 1, "network": 2},
                "retry_count_by_branch": {"url_fetch": 1, "get_file_api": 2},
            }
        },
    )
    understander = _FakeUnderstander(["摘要"])
    service = ImageContextService(
        config={
            "image_understanding": {
                "max_images_per_round": 1,
                "analyze_window_size": 20,
                "cache_enabled": False,
            }
        },
        image_resolver=resolver,
        image_understander=understander,
        message_repo=_FakeRepo(),
    )
    messages = [
        {
            "id": 1,
            "user_name": "Alice",
            "metadata": {"media": {"images": [{"url": "https://example.com/new.jpg"}]}},
        }
    ]

    with caplog.at_level(logging.INFO):
        context = asyncio.run(service.build_context("group_1", messages))

    assert "- Alice 发图：摘要" in context
    assert "image_fetch_error(timeout)=1" in caplog.text
    assert "image_fetch_error(network)=2" in caplog.text
    assert "image_fetch_retry(url_fetch)=1" in caplog.text
    assert "image_fetch_retry(get_file_api)=2" in caplog.text
