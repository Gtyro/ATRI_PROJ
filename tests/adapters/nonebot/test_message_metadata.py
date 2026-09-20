from types import SimpleNamespace

from src.adapters.nonebot.message_metadata import (
    build_onebot_metadata,
    extract_onebot_sent_message_ids,
    extract_onebot_event_message_context,
    extract_onebot_image_metadata,
    extract_onebot_mention_metadata,
    normalize_content_for_storage,
    resolve_onebot_direct_reason,
)


def test_extract_onebot_image_metadata_keeps_required_fields():
    message = [
        {"type": "text", "data": {"text": "hello"}},
        {
            "type": "image",
            "data": {
                "url": "https://example.com/a.jpg",
                "file_id": "abc123",
                "file": "abc.jpg",
                "mime": "image/jpeg",
                "size": "2048",
            },
        },
    ]

    images = extract_onebot_image_metadata(message)

    assert images == [
        {
            "segment_index": 1,
            "url": "https://example.com/a.jpg",
            "file_id": "abc123",
            "file": "abc.jpg",
            "mime": "image/jpeg",
            "size": 2048,
        }
    ]


def test_extract_onebot_mention_metadata_marks_self_mention():
    message = [
        {"type": "at", "data": {"qq": "2539518078", "name": "月 月"}},
        {"type": "text", "data": {"text": "你好"}},
    ]

    mentions = extract_onebot_mention_metadata(message, self_id="2539518078")

    assert mentions == [
        {
            "segment_index": 0,
            "text": "@月 月",
            "qq": "2539518078",
            "name": "月 月",
            "is_self": True,
        }
    ]


def test_normalize_content_for_storage_uses_placeholder_for_image_only():
    message = normalize_content_for_storage("", [{"segment_index": 0, "url": "https://example.com/a.jpg"}])
    assert message == "[图片]"


def test_normalize_content_for_storage_appends_image_placeholder_for_text_with_images():
    message = normalize_content_for_storage("笑死", [{"segment_index": 0, "url": "https://example.com/a.jpg"}])
    assert message == "笑死 [图片]"


def test_normalize_content_for_storage_rebuilds_mixed_segments_by_segment_index():
    segments = [
        {"type": "text", "data": {"text": "先看"}},
        {"type": "image", "data": {"url": "https://example.com/a.jpg"}},
        {"type": "text", "data": {"text": "再看"}},
        {"type": "image", "data": {"url": "https://example.com/b.jpg"}},
    ]

    # 顺序故意打乱，验证会按 segment_index 回到原顺序
    images = [
        {"segment_index": 3, "url": "https://example.com/b.jpg"},
        {"segment_index": 1, "url": "https://example.com/a.jpg"},
    ]
    message = normalize_content_for_storage(
        "先看再看",
        images,
        message_segments=segments,
    )

    assert message == "先看 [图片] 再看 [图片]"


def test_normalize_content_for_storage_keeps_mention_only_message():
    segments = [
        {"type": "at", "data": {"qq": "2539518078"}},
    ]

    message = normalize_content_for_storage(
        "",
        [],
        message_segments=segments,
    )

    assert message == "@2539518078"


def test_normalize_content_for_storage_rebuilds_mention_text_and_image_segments():
    segments = [
        {"type": "at", "data": {"qq": "2539518078"}},
        {"type": "text", "data": {"text": "你好"}},
        {"type": "image", "data": {"url": "https://example.com/a.jpg"}},
    ]

    message = normalize_content_for_storage(
        "你好",
        [{"segment_index": 2, "url": "https://example.com/a.jpg"}],
        message_segments=segments,
    )

    assert message == "@2539518078 你好 [图片]"


class _EventStub:
    def __init__(self, *, message, original_message=None, plain_text="", reply=None):
        self._message = message
        self.original_message = original_message
        self._plain_text = plain_text
        self.reply = reply

    def get_message(self):
        return self._message

    def get_plaintext(self):
        return self._plain_text


def test_extract_onebot_event_message_context_keeps_pure_self_mention_from_original_message():
    event = _EventStub(
        message=[{"type": "text", "data": {"text": ""}}],
        original_message=[{"type": "at", "data": {"qq": "2539518078", "name": "月 月"}}],
        plain_text="",
    )

    context = extract_onebot_event_message_context(event, self_id="2539518078")

    assert context["content"] == "@月 月"
    assert context["mentions"] == [
        {
            "segment_index": 0,
            "text": "@月 月",
            "qq": "2539518078",
            "name": "月 月",
            "is_self": True,
        }
    ]


def test_extract_onebot_event_message_context_preserves_self_mention_metadata_for_direct_text():
    event = _EventStub(
        message=[{"type": "text", "data": {"text": "你好"}}],
        original_message=[
            {"type": "at", "data": {"qq": "2539518078", "name": "月 月"}},
            {"type": "text", "data": {"text": "你好"}},
        ],
        plain_text="你好",
    )

    context = extract_onebot_event_message_context(event, self_id="2539518078")

    assert context["content"] == "你好"
    assert context["mentions"][0]["is_self"] is True
    assert context["mentions"][0]["text"] == "@月 月"


def test_extract_onebot_event_message_context_keeps_resolved_reply_content_and_sender():
    reply = SimpleNamespace(
        message_id=9001,
        sender=SimpleNamespace(user_id=10001, card="Alice", nickname="Alice"),
        message=[{"type": "text", "data": {"text": "原消息内容"}}],
    )
    event = _EventStub(
        message=[{"type": "text", "data": {"text": "帮我看看"}}],
        original_message=[
            {"type": "reply", "data": {"id": "9001"}},
            {"type": "at", "data": {"qq": "2539518078", "name": "月 月"}},
            {"type": "text", "data": {"text": "帮我看看"}},
        ],
        plain_text="帮我看看",
        reply=reply,
    )

    context = extract_onebot_event_message_context(event, self_id="2539518078")

    assert context["reply"] == {
        "message_id": "9001",
        "sender": {"user_id": "10001", "name": "Alice"},
        "content": "原消息内容",
    }


def test_extract_onebot_event_message_context_extracts_display_text_from_json_reply():
    reply = SimpleNamespace(
        message_id=9002,
        sender=SimpleNamespace(user_id=10001, card=None, nickname="Alice"),
        message=[
            {
                "type": "json",
                "data": {
                    "data": '{"meta":{"news":{"title":"分享标题","desc":"分享描述"}}}',
                },
            }
        ],
    )
    event = _EventStub(
        message=[{"type": "text", "data": {"text": "看这个"}}],
        original_message=[{"type": "reply", "data": {"id": "9002"}}],
        plain_text="看这个",
        reply=reply,
    )

    context = extract_onebot_event_message_context(event, self_id="2539518078")

    assert context["reply"]["content"] == "分享标题；分享描述"


def test_resolve_onebot_direct_reason_keeps_reply_to_bot_with_other_mention_non_direct():
    assert (
        resolve_onebot_direct_reason(
            is_group=True,
            event_is_tome=True,
            mentions=[{"qq": "1364980135", "text": "@其他成员"}],
            reply={"message_id": "9003", "is_self": True},
        )
        == ""
    )


def test_resolve_onebot_direct_reason_keeps_reply_to_bot_direct_without_other_mention():
    assert (
        resolve_onebot_direct_reason(
            is_group=True,
            event_is_tome=True,
            mentions=[],
            reply={"message_id": "9003", "is_self": True},
        )
        == "reply_to_self"
    )


def test_resolve_onebot_direct_reason_prioritizes_explicit_self_mention():
    assert (
        resolve_onebot_direct_reason(
            is_group=True,
            event_is_tome=True,
            mentions=[
                {"qq": "2539518078", "text": "@机器人", "is_self": True},
                {"qq": "1364980135", "text": "@其他成员"},
            ],
            reply={"message_id": "9003", "is_self": True},
        )
        == "mention_self"
    )


def test_extract_onebot_sent_message_ids_normalizes_receipt_shapes():
    receipt = SimpleNamespace(msg_ids=[123, {"message_id": "456"}, 123, None])

    assert extract_onebot_sent_message_ids(receipt) == ["123", "456"]


def test_build_onebot_metadata_includes_media_and_onebot_fields():
    metadata = build_onebot_metadata(
        self_id=123456,
        message_id=777,
        images=[{"segment_index": 0, "url": "https://example.com/a.jpg"}],
        mentions=[{"segment_index": 1, "text": "@月 月", "is_self": True}],
        reply={"message_id": "700", "is_self": True},
        direct_reason="reply_to_self",
    )

    assert metadata["onebot"]["self_id"] == "123456"
    assert metadata["onebot"]["message_id"] == "777"
    assert metadata["onebot"]["mentioned_self"] is True
    assert metadata["onebot"]["mentions"][0]["text"] == "@月 月"
    assert metadata["onebot"]["reply"]["message_id"] == "700"
    assert metadata["onebot"]["reply_to_self"] is True
    assert metadata["onebot"]["direct_reason"] == "reply_to_self"
    assert metadata["media"]["images"][0]["url"] == "https://example.com/a.jpg"
