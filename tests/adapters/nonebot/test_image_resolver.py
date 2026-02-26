import asyncio
import base64
import logging
import sys
from types import SimpleNamespace

from src.adapters.nonebot.image_resolver import NapcatImageResolver, ResolvedImage


def test_resolve_logs_file_id_fallback_warning(caplog):
    resolver = NapcatImageResolver(timeout_seconds=0.1)

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            resolver.resolve(
                conv_id="group_1",
                message_id=99,
                image_meta={"file_id": "abc123456789"},
            )
        )

    assert result is None
    assert "file_id_fallback_warning=1" in caplog.text
    assert "abc123456789" not in caplog.text
    assert "file_id=abc1" in caplog.text
    assert "6789" in caplog.text


def test_resolve_logs_file_id_fallback_warning_masks_short_id(caplog):
    resolver = NapcatImageResolver(timeout_seconds=0.1)

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            resolver.resolve(
                conv_id="group_1",
                message_id=100,
                image_meta={"file_id": "xy"},
            )
        )

    assert result is None
    assert "file_id_fallback_warning=1" in caplog.text
    assert "file_id=**" in caplog.text
    assert "file_id=xy" not in caplog.text


def test_resolve_uses_onebot_self_id_to_get_bot():
    calls = []

    def _bot_getter(self_id: str):
        calls.append(self_id)
        return object()

    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=_bot_getter)

    asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=99,
            image_meta={"file_id": "abc123456789"},
            onebot_self_id="10086",
        )
    )

    assert calls == ["10086"]


def test_resolve_skips_bot_getter_when_onebot_self_id_missing():
    calls = []

    def _bot_getter(self_id: str):
        calls.append(self_id)
        return object()

    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=_bot_getter)

    asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=99,
            image_meta={"file_id": "abc123456789"},
            onebot_self_id="",
        )
    )

    assert calls == []


def test_resolve_caches_bot_by_self_id():
    calls = []

    def _bot_getter(self_id: str):
        calls.append(self_id)
        return object()

    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=_bot_getter)

    asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=1,
            image_meta={"file_id": "abc123456789"},
            onebot_self_id="10086",
        )
    )
    asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=2,
            image_meta={"file_id": "def123456789"},
            onebot_self_id="10086",
        )
    )

    assert calls == ["10086"]


def test_resolve_returns_url_directly_without_entering_fallback_branches():
    calls = []

    def _bot_getter(self_id: str):
        calls.append(self_id)
        return object()

    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=_bot_getter)

    async def _fake_resolve_by_url(url, *, image_meta, source="url"):
        return ResolvedImage(
            source=source,
            mime="image/png",
            image_bytes=b"url-ok",
            original_url=url,
        )

    resolver._resolve_by_url = _fake_resolve_by_url  # type: ignore[method-assign]

    result = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=98,
            image_meta={
                "url": "https://example.com/ok.png",
                "file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg",
                "file_id": "fid_should_not_be_used",
            },
            onebot_self_id="10086",
        )
    )

    assert result is not None
    assert result.source == "url"
    assert result.image_bytes == b"url-ok"
    assert calls == []


def test_resolve_falls_back_to_get_image_and_reuses_url_download():
    class _FakeBot:
        def __init__(self):
            self.calls = []

        async def call_api(self, action, **params):
            self.calls.append((action, params))
            return {"url": "https://example.com/fresh.jpg"}

    bot = _FakeBot()
    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=lambda _: bot)
    url_calls = []

    async def _fake_resolve_by_url(url, *, image_meta, source="url"):
        url_calls.append((url, source))
        if source == "url":
            return None
        return ResolvedImage(
            source=source,
            mime="image/jpeg",
            image_bytes=b"fresh",
            original_url=url,
        )

    resolver._resolve_by_url = _fake_resolve_by_url  # type: ignore[method-assign]

    result = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=99,
            image_meta={
                "url": "https://example.com/expired.jpg",
                "file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg",
            },
            onebot_self_id="10086",
        )
    )

    assert result is not None
    assert result.source == "get_image"
    assert result.image_bytes == b"fresh"
    assert url_calls == [
        ("https://example.com/expired.jpg", "url"),
        ("https://example.com/fresh.jpg", "get_image"),
    ]
    assert bot.calls == [
        (
            "get_image",
            {"file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg"},
        )
    ]


def test_resolve_falls_back_to_get_file_by_file_id_prefers_base64():
    class _FakeBot:
        def __init__(self):
            self.calls = []

        async def call_api(self, action, **params):
            self.calls.append((action, params))
            if action == "get_file":
                return {
                    "base64": base64.b64encode(b"from-file-id").decode("ascii"),
                    "url": "https://example.com/should-not-be-used.jpg",
                }
            return {}

    bot = _FakeBot()
    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=lambda _: bot)
    url_calls = []

    async def _fake_resolve_by_url(url, *, image_meta, source="url"):
        url_calls.append((url, source))
        return None

    resolver._resolve_by_url = _fake_resolve_by_url  # type: ignore[method-assign]

    result = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=101,
            image_meta={"file_id": "fid_1234"},
            onebot_self_id="10086",
        )
    )

    assert result is not None
    assert result.source == "get_file_by_file_id"
    assert result.image_bytes == b"from-file-id"
    assert url_calls == []
    assert bot.calls == [("get_file", {"file_id": "fid_1234"})]


def test_resolve_falls_back_to_get_file_by_file_after_file_id_branch_failed():
    class _FakeBot:
        def __init__(self):
            self.calls = []

        async def call_api(self, action, **params):
            self.calls.append((action, params))
            if action == "get_image":
                return {}
            if action == "get_file" and "file_id" in params:
                return {}
            if action == "get_file" and "file" in params:
                return {"base64": base64.b64encode(b"from-file").decode("ascii")}
            return {}

    bot = _FakeBot()
    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=lambda _: bot)

    result = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=102,
            image_meta={
                "file_id": "fid_1234",
                "file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg",
            },
            onebot_self_id="10086",
        )
    )

    assert result is not None
    assert result.source == "get_file_by_file"
    assert result.image_bytes == b"from-file"
    assert bot.calls == [
        ("get_image", {"file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg"}),
        ("get_file", {"file_id": "fid_1234"}),
        ("get_file", {"file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg"}),
    ]


def test_resolve_returns_none_when_all_fetch_paths_failed():
    class _FakeBot:
        def __init__(self):
            self.calls = []

        async def call_api(self, action, **params):
            self.calls.append((action, params))
            return {}

    bot = _FakeBot()
    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=lambda _: bot)
    url_calls = []

    async def _fake_resolve_by_url(url, *, image_meta, source="url"):
        url_calls.append((url, source))
        return None

    resolver._resolve_by_url = _fake_resolve_by_url  # type: ignore[method-assign]

    result = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=188,
            image_meta={
                "url": "https://example.com/expired.jpg",
                "file_id": "fid_1234",
                "file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg",
            },
            onebot_self_id="10086",
        )
    )

    assert result is None
    assert url_calls == [("https://example.com/expired.jpg", "url")]
    assert bot.calls == [
        ("get_image", {"file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg"}),
        ("get_file", {"file_id": "fid_1234"}),
        ("get_file", {"file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg"}),
    ]


def test_resolve_skips_unsupported_get_image_and_continues_get_file_with_cache():
    class _UnsupportedActionError(RuntimeError):
        def __init__(self):
            super().__init__("unsupported action")
            self.info = {"retcode": 1404, "msg": "api not found"}

    class _FakeBot:
        def __init__(self):
            self.calls = []

        async def call_api(self, action, **params):
            self.calls.append((action, params))
            if action == "get_image":
                raise _UnsupportedActionError()
            if action == "get_file":
                return {"base64": base64.b64encode(b"from-file-id").decode("ascii")}
            return {}

    bot = _FakeBot()
    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=lambda _: bot)

    first = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=201,
            image_meta={
                "file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg",
                "file_id": "fid_unsupported_01",
            },
            onebot_self_id="10086",
        )
    )
    second = asyncio.run(
        resolver.resolve(
            conv_id="group_1",
            message_id=202,
            image_meta={
                "file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg",
                "file_id": "fid_unsupported_02",
            },
            onebot_self_id="10086",
        )
    )

    assert first is not None
    assert first.source == "get_file_by_file_id"
    assert first.image_bytes == b"from-file-id"
    assert second is not None
    assert second.source == "get_file_by_file_id"
    assert second.image_bytes == b"from-file-id"
    assert bot.calls == [
        ("get_image", {"file": "A2609E26DDFD23A4EEDF7485BCA99730.jpg"}),
        ("get_file", {"file_id": "fid_unsupported_01"}),
        ("get_file", {"file_id": "fid_unsupported_02"}),
    ]


def test_resolve_skips_bot_getter_when_no_fallback_fields(caplog):
    calls = []

    def _bot_getter(self_id: str):
        calls.append(self_id)
        raise RuntimeError("boom")

    resolver = NapcatImageResolver(timeout_seconds=0.1, bot_getter=_bot_getter)

    async def _fake_resolve_by_url(url, *, image_meta, source="url"):
        return None

    resolver._resolve_by_url = _fake_resolve_by_url  # type: ignore[method-assign]

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            resolver.resolve(
                conv_id="group_1",
                message_id=103,
                image_meta={"url": "https://example.com/expired.jpg"},
                onebot_self_id="10086",
            )
        )

    assert result is None
    assert calls == []
    assert "跳过 OneBot 兜底分支" not in caplog.text


def test_resolve_by_url_warning_message_no_longer_claims_followup_fallback(caplog, monkeypatch):
    class _FailingResponse:
        headers = {}
        content = b""

        def raise_for_status(self):
            raise RuntimeError("boom")

    class _FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            return _FailingResponse()

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(AsyncClient=_FakeAsyncClient))
    resolver = NapcatImageResolver(timeout_seconds=0.1)

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            resolver._resolve_by_url(
                "https://example.com/expired.jpg",
                image_meta={},
            )
        )

    assert result is None
    assert "图片 URL 拉取失败: url=" in caplog.text
    assert "https://example.com/expired.jpg" not in caplog.text
    assert "error=RuntimeError" in caplog.text
    assert "准备尝试后续兜底" not in caplog.text


def test_read_local_image_warning_masks_path(caplog):
    missing_path = "/tmp/very/secret/path/image-secret-1234567890.jpg"

    with caplog.at_level(logging.WARNING):
        result = NapcatImageResolver._read_local_image(
            missing_path,
            image_meta={},
            source="get_file_by_file",
        )

    assert result is None
    assert "图片本地路径拉取失败: path=" in caplog.text
    assert missing_path not in caplog.text
    assert "FileNotFoundError" in caplog.text


def test_decode_base64_failure_logs_only_length_and_digest(caplog):
    payload = {
        "base64": "base64://not-base64$$secret_token_12345",
    }

    with caplog.at_level(logging.WARNING):
        result = NapcatImageResolver._decode_base64_image_from_payload(
            payload,
            conv_id="group_1",
            message_id=999,
            source="get_file_by_file_id",
        )

    assert result is None
    assert "base64_length=" in caplog.text
    assert "base64_sha256_prefix=" in caplog.text
    assert "secret_token_12345" not in caplog.text
