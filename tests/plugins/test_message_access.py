import asyncio
from types import SimpleNamespace

import pytest
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    HeartbeatMetaEvent,
    PrivateMessageEvent,
)
from nonebot.message import _apply_event_preprocessors

from plugins import message_access  # noqa: F401 - registers the event preprocessor


def _bot(superusers):
    adapter = SimpleNamespace(
        config=SimpleNamespace(superusers=set(superusers)),
        get_name=lambda: "OneBot V11",
    )
    return Bot(adapter=adapter, self_id="99999")


def _message_event(event_type, content="你好"):
    data = {
        "time": 0,
        "self_id": 99999,
        "post_type": "message",
        "message_type": "private" if event_type is PrivateMessageEvent else "group",
        "sub_type": "friend" if event_type is PrivateMessageEvent else "normal",
        "message_id": 1,
        "user_id": 10001,
        "message": content,
        "raw_message": content,
        "font": 0,
        "sender": {"user_id": 10001, "nickname": "Test user"},
        "group_id": 0 if event_type is PrivateMessageEvent else 20001,
    }
    return event_type.model_validate(data)


@pytest.mark.parametrize("content", ["你好", "帮助", "/画一张 猫"])
def test_ordinary_private_messages_stop_before_matchers(content):
    allowed = asyncio.run(_apply_event_preprocessors(
        _bot([]), _message_event(PrivateMessageEvent, content), {}, show_log=False,
    ))

    assert allowed is False


@pytest.mark.parametrize("superuser_id", ["10001", "onebot:10001"])
def test_superuser_private_messages_use_canonical_permission(superuser_id):
    allowed = asyncio.run(_apply_event_preprocessors(
        _bot([superuser_id]), _message_event(PrivateMessageEvent), {}, show_log=False,
    ))

    assert allowed is True


def test_group_messages_keep_existing_policy_path():
    allowed = asyncio.run(_apply_event_preprocessors(
        _bot([]), _message_event(GroupMessageEvent), {}, show_log=False,
    ))

    assert allowed is True


def test_non_message_events_are_not_blocked():
    event = HeartbeatMetaEvent.model_validate({
        "time": 0,
        "self_id": 99999,
        "post_type": "meta_event",
        "meta_event_type": "heartbeat",
        "status": {"online": True, "good": True},
        "interval": 5000,
    })
    allowed = asyncio.run(_apply_event_preprocessors(_bot([]), event, {}, show_log=False))

    assert allowed is True
