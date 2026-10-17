import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError

from src.adapters.nonebot import persona_reply


@pytest.mark.parametrize("conv_id,is_private", [
    ("private_10001", True),
    ("group_20001", False),
])
@pytest.mark.parametrize("reply_content", ["你好", ["你好", " ", "再聊聊"]])
def test_persona_reply_sends_to_correct_conversation_type(
    monkeypatch, conv_id, is_private, reply_content,
):
    sent = []

    async def send(message, target):
        sent.append((str(message), target))
        return SimpleNamespace(msg_ids=[{"message_id": "123"}])

    monkeypatch.setattr(persona_reply.UniMessage, "send", send)
    monkeypatch.setattr(persona_reply.asyncio, "sleep", AsyncMock())

    message_ids = asyncio.run(persona_reply.persona_callback(
        conv_id, {"reply_content": reply_content},
    ))

    assert message_ids == ["123"]
    assert [content for content, _ in sent] == (
        ["你好"] if isinstance(reply_content, str) else ["你好", "再聊聊"]
    )
    assert all(target.private is is_private for _, target in sent)
    assert all(target.id == conv_id.split("_", 1)[1] for _, target in sent)


@pytest.mark.parametrize("conv_id,is_private", [
    ("private_10001", True), ("group_20001", False),
])
def test_persona_reply_sends_raw_image_and_collects_its_message_id(monkeypatch, conv_id, is_private):
    sent = []

    async def send(message, target):
        sent.append((message, target))
        return SimpleNamespace(msg_ids=[{"message_id": str(len(sent))}])

    monkeypatch.setattr(persona_reply.UniMessage, "send", send)
    monkeypatch.setattr(persona_reply.asyncio, "sleep", AsyncMock())

    message_ids = asyncio.run(persona_reply.persona_callback(
        conv_id, {"reply_content": ["给你。"], "images": [b"png-bytes"]},
    ))

    assert message_ids == ["1", "2"]
    assert sent[0][0][0].type == "image"
    assert sent[0][0][0].raw == b"png-bytes"
    assert all(target.private is is_private for _, target in sent)


def test_persona_reply_reports_image_send_failure_without_success_caption(monkeypatch):
    sent = []

    async def send(message, target):
        sent.append(message)
        if message[0].type == "image":
            raise RuntimeError("OneBot send failed")
        return SimpleNamespace(msg_ids=[{"message_id": "error-message"}])

    monkeypatch.setattr(persona_reply.UniMessage, "send", send)
    message_ids = asyncio.run(persona_reply.persona_callback(
        "private_10001", {"reply_content": "已经发给你。", "images": [b"png-bytes"]},
    ))

    assert message_ids == ["error-message"]
    assert len(sent) == 2
    assert "没能发出去" in str(sent[1])
    assert "已经发给你" not in str(sent[1])


@pytest.mark.parametrize("exc,expected_reason", [
    (ActionFailed(retcode=1200, message="image rejected"), "检查发送日志"),
    (NetworkError("connection failed"), "没连上消息服务"),
])
def test_image_send_failure_distinguishes_network_and_platform_errors(
    monkeypatch, caplog, exc, expected_reason,
):
    sent = []

    async def send(message, target):
        sent.append(message)
        if message[0].type == "image":
            raise exc
        return SimpleNamespace(msg_ids=[{"message_id": "failure-notice"}])

    monkeypatch.setattr(persona_reply.UniMessage, "send", send)

    message_ids = asyncio.run(persona_reply.persona_callback(
        "private_10001", {"reply_content": "发给你了。", "images": [b"image-bytes"]},
    ))

    assert message_ids == ["failure-notice"]
    assert expected_reason in str(sent[1])
    assert "图片画好了" in str(sent[1])
    if isinstance(exc, ActionFailed):
        assert "retcode=1200" in caplog.text
        assert "image rejected" in caplog.text
        assert "稍后再试" not in str(sent[1])
    else:
        assert "connection failed" in caplog.text


def test_send_error_diagnostics_do_not_dump_image_payload_or_credentials(monkeypatch, caplog):
    exc = ActionFailed(
        retcode=1200, message="Authorization: Bearer secret-key; image rejected",
        data={"image": "base64://private-image-bytes", "token": "private-token"},
    )

    async def send(message, target):
        raise exc

    monkeypatch.setattr(persona_reply.UniMessage, "send", send)
    message_ids = asyncio.run(persona_reply.persona_callback(
        "private_10001", {"images": [b"image-bytes"]},
    ))

    assert message_ids == []
    assert "image rejected" in caplog.text
    assert "retcode=1200" in caplog.text
    for secret in ["secret-key", "private-image-bytes", "private-token"]:
        assert secret not in caplog.text
