from src.adapters.nonebot.message_metadata import (
    build_onebot_metadata,
    extract_onebot_image_metadata,
    normalize_content_for_storage,
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


def test_build_onebot_metadata_includes_media_and_onebot_fields():
    metadata = build_onebot_metadata(
        self_id=123456,
        message_id=777,
        images=[{"segment_index": 0, "url": "https://example.com/a.jpg"}],
    )

    assert metadata["onebot"]["self_id"] == "123456"
    assert metadata["onebot"]["message_id"] == "777"
    assert metadata["media"]["images"][0]["url"] == "https://example.com/a.jpg"
