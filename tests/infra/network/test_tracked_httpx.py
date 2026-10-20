import asyncio

import httpcore
import httpx
import pytest

from src.infra.db.tortoise import registered_unit_usage
from src.infra.network.tracked_httpx import TrackedAsyncClient


def test_socks_request_attempt_is_recorded_even_when_connection_fails(monkeypatch):
    recorded = []

    async def record(unit_id):
        recorded.append(unit_id)

    async def fail_connection(self, request):
        raise httpcore.ConnectError("connection failed")

    monkeypatch.setattr(registered_unit_usage, "record_registered_unit_usage", record)
    monkeypatch.setattr(httpcore.AsyncSOCKSProxy, "handle_async_request", fail_connection)

    async def check():
        async with TrackedAsyncClient(proxy="socks5://127.0.0.1:9", trust_env=False) as client:
            with pytest.raises(httpx.ConnectError):
                await client.get("https://example.test/one")
            with pytest.raises(httpx.ConnectError):
                await client.get("https://example.test/two")

    asyncio.run(check())
    assert recorded == ["network.socks_proxy", "network.socks_proxy"]


def test_direct_request_does_not_record_socks_usage(monkeypatch):
    recorded = []

    async def record(unit_id):
        recorded.append(unit_id)

    monkeypatch.setattr(registered_unit_usage, "record_registered_unit_usage", record)

    async def check():
        transport = httpx.MockTransport(lambda request: httpx.Response(200))
        async with TrackedAsyncClient(transport=transport, trust_env=False) as client:
            response = await client.get("https://example.test/")
            assert response.status_code == 200

    asyncio.run(check())
    assert recorded == []


def test_http_proxy_request_does_not_record_socks_usage(monkeypatch):
    recorded = []

    async def record(unit_id):
        recorded.append(unit_id)

    async def fail_connection(self, request):
        raise httpcore.ConnectError("connection failed")

    monkeypatch.setattr(registered_unit_usage, "record_registered_unit_usage", record)
    monkeypatch.setattr(httpcore.AsyncHTTPProxy, "handle_async_request", fail_connection)

    async def check():
        async with TrackedAsyncClient(proxy="http://127.0.0.1:9", trust_env=False) as client:
            with pytest.raises(httpx.ConnectError):
                await client.get("https://example.test/")

    asyncio.run(check())
    assert recorded == []


def test_openai_client_uses_socks_tracking_transport():
    from src.infra.llm.providers.client import LLMClient
    from src.infra.network.tracked_httpx import SocksUsageMixin

    client = LLMClient(api_key="test", base_url="https://example.test/v1", model="test")
    try:
        assert isinstance(client._client._client, SocksUsageMixin)
    finally:
        asyncio.run(client._client.close())


def test_environment_socks_proxy_respects_no_proxy(monkeypatch):
    recorded = []

    async def record(unit_id):
        recorded.append(unit_id)

    async def fail_socks(self, request):
        raise httpcore.ConnectError("connection failed")

    async def direct_response(request):
        return httpx.Response(200, request=request)

    monkeypatch.setattr(registered_unit_usage, "record_registered_unit_usage", record)
    monkeypatch.setattr(httpcore.AsyncSOCKSProxy, "handle_async_request", fail_socks)
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "direct.example.test")

    async def check():
        async with TrackedAsyncClient() as client:
            monkeypatch.setattr(client._transport, "handle_async_request", direct_response)
            assert (await client.get("https://direct.example.test/")).status_code == 200
            with pytest.raises(httpx.ConnectError):
                await client.get("https://proxied.example.test/")

    asyncio.run(check())
    assert recorded == ["network.socks_proxy"]
