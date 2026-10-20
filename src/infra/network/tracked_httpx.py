"""Record requests routed through an HTTPX SOCKS transport."""

from __future__ import annotations

import logging

import httpcore
import httpx


logger = logging.getLogger(__name__)


class SocksUsageMixin:
    async def _send_single_request(self, request: httpx.Request) -> httpx.Response:
        # HTTPX resolves redirects and proxy mounts here, immediately before sending.
        transport = self._transport_for_url(request.url)
        if isinstance(getattr(transport, "_pool", None), httpcore.AsyncSOCKSProxy):
            try:
                from src.infra.db.tortoise.registered_unit_usage import record_registered_unit_usage

                await record_registered_unit_usage("network.socks_proxy")
            except Exception:
                logger.exception("无法记录 SOCKS 代理请求使用事件")
        return await super()._send_single_request(request)


class TrackedAsyncClient(SocksUsageMixin, httpx.AsyncClient):
    """HTTPX client that counts each request attempt selected for SOCKS."""
