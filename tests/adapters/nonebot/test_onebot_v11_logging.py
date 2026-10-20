import asyncio
from types import SimpleNamespace

import pytest

from nonebot.adapters.onebot.v11 import adapter as onebot_adapter
from nonebot.exception import WebSocketClosed

from src.adapters.nonebot import onebot_v11_logging


def test_only_service_restart_disconnect_is_suppressed(monkeypatch: pytest.MonkeyPatch):
    logged = []
    monkeypatch.setattr(
        onebot_v11_logging,
        "_original_log",
        lambda *args: logged.append(args),
    )
    message = "WebSocket for Bot 123 closed by peer"

    for code in (1012, 1006):
        try:
            raise WebSocketClosed(code)
        except WebSocketClosed:
            onebot_v11_logging._log_without_restart_warning("WARNING", message)

    onebot_v11_logging._log_without_restart_warning("WARNING", message)
    onebot_v11_logging._log_without_restart_warning("WARNING", "Another warning")

    assert logged == [
        ("WARNING", message, None),
        ("WARNING", message, None),
        ("WARNING", "Another warning", None),
    ]


def test_adapter_keeps_runtime_disconnect_warning(monkeypatch: pytest.MonkeyPatch):
    logged = []
    original = onebot_adapter.log
    monkeypatch.setattr(onebot_adapter, "log", original)
    monkeypatch.setattr(
        onebot_v11_logging,
        "_original_log",
        lambda *args: logged.append(args),
    )
    monkeypatch.setattr(onebot_adapter, "Bot", lambda adapter, self_id: object())

    class AdapterStub:
        def __init__(self):
            self.bots = {}
            self.connections = {}

        def _check_access_token(self, request):
            return None

        def bot_connect(self, bot):
            pass

        def bot_disconnect(self, bot):
            pass

    class WebSocketStub:
        request = SimpleNamespace(headers={"x-self-id": "123"})

        def __init__(self, code):
            self.code = code

        async def accept(self):
            pass

        async def receive(self):
            raise WebSocketClosed(self.code)

        async def close(self):
            pass

    onebot_v11_logging.install_onebot_v11_restart_log_filter()
    for code in (1012, 1006):
        asyncio.run(onebot_adapter.Adapter._handle_ws(AdapterStub(), WebSocketStub(code)))

    assert [entry for entry in logged if entry[0] == "WARNING"] == [
        ("WARNING", "WebSocket for Bot 123 closed by peer", None)
    ]
