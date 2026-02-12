import asyncio
import importlib
import re
import sys
import types


class _Memory:
    total = 8 * 1024**3
    used = 3 * 1024**3
    percent = 37.5


class _Disk:
    total = 100 * 1024**3
    used = 25 * 1024**3
    percent = 25.0


class _DummyMatcher:
    def handle(self):
        def decorator(func):
            return func

        return decorator


def _install_nonebot_stubs(monkeypatch):
    nonebot = types.ModuleType("nonebot")
    nonebot.__path__ = []

    adapters = types.ModuleType("nonebot.adapters")
    adapters.__path__ = []

    onebot = types.ModuleType("nonebot.adapters.onebot")
    onebot.__path__ = []

    v11 = types.ModuleType("nonebot.adapters.onebot.v11")

    class Bot:
        pass

    class MessageEvent:
        pass

    v11.Bot = Bot
    v11.MessageEvent = MessageEvent

    v11_permission = types.ModuleType("nonebot.adapters.onebot.v11.permission")
    v11_permission.GROUP_ADMIN = 1
    v11_permission.GROUP_OWNER = 2

    permission = types.ModuleType("nonebot.permission")
    permission.SUPERUSER = 4

    plugin = types.ModuleType("nonebot.plugin")

    class PluginMetadata:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    plugin.PluginMetadata = PluginMetadata

    rule = types.ModuleType("nonebot.rule")

    def to_me():
        return object()

    rule.to_me = to_me

    monkeypatch.setitem(sys.modules, "nonebot", nonebot)
    monkeypatch.setitem(sys.modules, "nonebot.adapters", adapters)
    monkeypatch.setitem(sys.modules, "nonebot.adapters.onebot", onebot)
    monkeypatch.setitem(sys.modules, "nonebot.adapters.onebot.v11", v11)
    monkeypatch.setitem(sys.modules, "nonebot.adapters.onebot.v11.permission", v11_permission)
    monkeypatch.setitem(sys.modules, "nonebot.permission", permission)
    monkeypatch.setitem(sys.modules, "nonebot.plugin", plugin)
    monkeypatch.setitem(sys.modules, "nonebot.rule", rule)


def _load_status_module(monkeypatch):
    dummy_matcher = _DummyMatcher()

    fake_command_registry = types.ModuleType("src.adapters.nonebot.command_registry")

    def register_command(*args, **kwargs):
        return dummy_matcher

    fake_command_registry.register_command = register_command

    fake_nonebot_pkg = types.ModuleType("src.adapters.nonebot")
    fake_nonebot_pkg.__path__ = []

    _install_nonebot_stubs(monkeypatch)
    monkeypatch.setitem(sys.modules, "src.adapters.nonebot", fake_nonebot_pkg)
    monkeypatch.setitem(sys.modules, "src.adapters.nonebot.command_registry", fake_command_registry)

    sys.modules.pop("plugins.status", None)
    status_module = importlib.import_module("plugins.status")
    return status_module, dummy_matcher


def test_status_handler_formats_message(monkeypatch):
    status_module, dummy_matcher = _load_status_module(monkeypatch)

    monkeypatch.setattr(status_module.psutil, "cpu_percent", lambda interval=1: 12.34)
    monkeypatch.setattr(status_module.psutil, "virtual_memory", lambda: _Memory())
    monkeypatch.setattr(status_module.psutil, "disk_usage", lambda path: _Disk())

    captured = {}

    async def fake_finish(message):
        captured["message"] = message

    dummy_matcher.finish = fake_finish

    asyncio.run(status_module.handle_status(bot=None, event=None))

    message = captured.get("message")
    assert message is not None

    assert re.search(r"CPU.*12\.3%", message)
    assert "8.00 GB" in message
    assert "3.00 GB (37.5%)" in message
    assert "100.00 GB" in message
    assert "25.00 GB (25.0%)" in message
