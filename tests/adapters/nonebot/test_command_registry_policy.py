import asyncio
from types import SimpleNamespace

import pytest

from src.adapters.nonebot import command_registry


@pytest.mark.parametrize("superuser_id", ["10001", "onebot:10001"])
def test_help_recognizes_canonical_superuser_ids(monkeypatch, superuser_id):
    monkeypatch.setattr(command_registry, "get_driver", lambda: SimpleNamespace(
        config=SimpleNamespace(superusers={superuser_id}),
    ))
    event = SimpleNamespace(get_user_id=lambda: "10001")

    assert command_registry.get_viewer_role(event) == "superuser"


def test_superuser_normal_command_list_uses_viewer_role(monkeypatch):
    event = SimpleNamespace(get_user_id=lambda: "10001")
    monkeypatch.setattr(command_registry, "get_driver", lambda: SimpleNamespace(
        config=SimpleNamespace(superusers={"10001"}),
    ))
    registry = command_registry.CommandRegistry()
    registry.add(command_registry.CommandSpec("天气", "normal", "weather"))
    monkeypatch.setattr(command_registry, "registry", registry)
    monkeypatch.setattr(command_registry, "get_policy_plugins", lambda: ["weather"])

    async def unexpected_policy_lookup(*args, **kwargs):
        raise AssertionError("superuser normal commands must not consult group switch")

    monkeypatch.setattr(command_registry, "_is_plugin_enabled", unexpected_policy_lookup)

    commands = asyncio.run(command_registry.list_commands_for_role(event, "normal"))

    assert len(commands) == 1
    assert commands[0].enabled is True


def test_superuser_policy_view_bypasses_group_feature_switch(monkeypatch):
    async def unexpected_policy_lookup(*args, **kwargs):
        raise AssertionError("superuser policy view must not consult group switch")

    monkeypatch.setattr(command_registry, "_is_plugin_enabled", unexpected_policy_lookup)

    enabled, status = asyncio.run(
        command_registry._resolve_plugin_status(
            "weather",
            "12345",
            viewer_role="superuser",
            required_role="normal",
            policy_plugins={"weather"},
        )
    )

    assert enabled is True
    assert status == "enabled"


def test_superuser_private_management_help_remains_contextual():
    enabled, status = asyncio.run(
        command_registry._resolve_plugin_status(
            "persona",
            None,
            viewer_role="superuser",
            required_role="superuser",
            policy_plugins={"persona"},
        )
    )

    assert enabled is True
    assert status == "contextual"


def test_ordinary_user_still_obeys_group_feature_switch(monkeypatch):
    async def disabled(*args, **kwargs):
        return False

    monkeypatch.setattr(command_registry, "_is_plugin_enabled", disabled)

    enabled, status = asyncio.run(
        command_registry._resolve_plugin_status(
            "weather",
            "12345",
            viewer_role="normal",
            required_role="normal",
            policy_plugins={"weather"},
        )
    )

    assert enabled is False
    assert status == "disabled"
