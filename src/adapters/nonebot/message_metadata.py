"""OneBot 消息元信息提取工具。"""

from __future__ import annotations

import json
from typing import Any, Dict, List


IMAGE_ONLY_PLACEHOLDER = "[图片]"
_REFERENCE_JSON_TEXT_KEYS = frozenset(
    {"title", "desc", "description", "prompt", "text", "content", "summary"}
)
_REFERENCE_CONTENT_MAX_LENGTH = 1000


def _segment_type(segment: Any) -> str:
    value = getattr(segment, "type", None)
    if isinstance(value, str):
        return value
    if isinstance(segment, dict):
        raw = segment.get("type")
        return str(raw) if raw is not None else ""
    return ""


def _segment_data(segment: Any) -> Dict[str, Any]:
    value = getattr(segment, "data", None)
    if isinstance(value, dict):
        return value
    if isinstance(segment, dict):
        raw = segment.get("data")
        if isinstance(raw, dict):
            return raw
    return {}


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _object_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_nonempty(*values: Any) -> str:
    for value in values:
        normalized = _string_value(value)
        if normalized:
            return normalized
    return ""


def _extract_reply_segment_id(message: Any) -> str:
    try:
        segments = list(message or [])
    except TypeError:
        return ""

    for segment in segments:
        if _segment_type(segment) != "reply":
            continue
        message_id = _string_value(_segment_data(segment).get("id"))
        if message_id:
            return message_id
    return ""


def _reference_content(message: Any, images: List[Dict[str, Any]]) -> str:
    content = normalize_content_for_storage(
        "",
        images,
        message_segments=message,
    )
    if content:
        return content

    json_texts: List[str] = []
    try:
        segments = list(message or [])
    except TypeError:
        return ""
    for segment in segments:
        if _segment_type(segment) != "json":
            continue
        json_text = _extract_json_display_text(_segment_data(segment).get("data"))
        if json_text and json_text not in json_texts:
            json_texts.append(json_text)

    return _truncate_reference_content("；".join(json_texts))


def _extract_json_display_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return ""

    texts: List[str] = []

    def _collect(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if (
                    str(key).strip().lower() in _REFERENCE_JSON_TEXT_KEYS
                    and isinstance(child, str)
                ):
                    text = " ".join(child.split())
                    if text and text not in texts:
                        texts.append(text)
                elif isinstance(child, (dict, list)):
                    _collect(child)
        elif isinstance(item, list):
            for child in item:
                _collect(child)

    _collect(payload)
    return _truncate_reference_content("；".join(texts[:6]))


def _truncate_reference_content(value: str) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= _REFERENCE_CONTENT_MAX_LENGTH:
        return normalized
    return f"{normalized[:_REFERENCE_CONTENT_MAX_LENGTH].rstrip()}..."


def _render_mention_segment(segment: Any) -> str:
    data = _segment_data(segment)
    qq = data.get("qq")
    if qq == "all":
        return "@全体成员"

    display_name = data.get("name") or data.get("nickname")
    if display_name not in (None, ""):
        return f"@{display_name}"
    if qq not in (None, ""):
        return f"@{qq}"
    return "@提及"


def extract_onebot_mention_metadata(message: Any, *, self_id: Any = None) -> List[Dict[str, Any]]:
    """从 OneBot 消息段中提取 @ 元信息。"""
    try:
        segments = list(message or [])
    except TypeError:
        return []

    normalized_self_id = str(self_id or "").strip()
    mentions: List[Dict[str, Any]] = []
    for index, segment in enumerate(segments):
        if _segment_type(segment) != "at":
            continue

        data = _segment_data(segment)
        qq = str(data.get("qq") or "").strip()
        name = str(data.get("name") or data.get("nickname") or "").strip()
        text = _render_mention_segment(segment)
        item: Dict[str, Any] = {
            "segment_index": index,
            "text": text,
        }
        if qq:
            item["qq"] = qq
        if name:
            item["name"] = name
        if qq == "all":
            item["is_all"] = True
        if normalized_self_id and qq == normalized_self_id:
            item["is_self"] = True
        mentions.append(item)

    return mentions


def extract_onebot_event_message_context(event: Any, *, self_id: Any = None) -> Dict[str, Any]:
    """从 NoneBot OneBot 事件中提取用于入库的消息上下文。

    优先保留适配层预处理前的原始 @ 元信息，避免纯 @ 机器人消息在 `to_me`
    处理后变成空文本并被业务层忽略。
    """
    message_segments = _resolve_event_message_segments(event)
    original_segments = _resolve_original_event_message_segments(event, message_segments=message_segments)
    plain_text = _safe_event_plaintext(event)

    images = extract_onebot_image_metadata(message_segments)
    mentions = extract_onebot_mention_metadata(original_segments, self_id=self_id)
    reply = extract_onebot_reply_metadata(
        event,
        self_id=self_id,
        original_message_segments=original_segments,
    )
    content = normalize_content_for_storage(
        plain_text,
        images,
        message_segments=message_segments,
    )
    if not content and mentions:
        content = " ".join(
            text
            for text in (
                str(item.get("text") or "").strip()
                for item in mentions
                if isinstance(item, dict)
            )
            if text
        )

    return {
        "content": content,
        "images": images,
        "mentions": mentions,
        "reply": reply,
        "message_segments": message_segments,
        "original_message_segments": original_segments,
    }


def extract_onebot_reply_metadata(
    event: Any,
    *,
    self_id: Any = None,
    original_message_segments: Any = None,
) -> Dict[str, Any] | None:
    """提取 NoneBot 已解析的引用消息，并保留无法解析时的原始引用 ID。"""
    reply = getattr(event, "reply", None)
    reply_id = _string_value(_object_value(reply, "message_id"))
    if not reply_id:
        reply_id = _extract_reply_segment_id(original_message_segments)
    if reply is None and not reply_id:
        return None

    metadata: Dict[str, Any] = {}
    if reply_id:
        metadata["message_id"] = reply_id

    sender = _object_value(reply, "sender")
    sender_id = _string_value(_object_value(sender, "user_id"))
    sender_name = _first_nonempty(
        _object_value(sender, "card"),
        _object_value(sender, "nickname"),
    )
    if sender_id or sender_name:
        sender_metadata: Dict[str, Any] = {}
        if sender_id:
            sender_metadata["user_id"] = sender_id
        if sender_name:
            sender_metadata["name"] = sender_name
        metadata["sender"] = sender_metadata

    normalized_self_id = _string_value(self_id)
    if normalized_self_id and sender_id == normalized_self_id:
        metadata["is_self"] = True

    reply_message = _object_value(reply, "message")
    if reply_message is not None:
        images = extract_onebot_image_metadata(reply_message)
        content = _reference_content(reply_message, images)
        if content:
            metadata["content"] = content
        if images:
            metadata["images"] = images

    return metadata or None


def resolve_onebot_direct_reason(
    *,
    is_group: bool,
    event_is_tome: bool,
    mentions: List[Dict[str, Any]],
    reply: Dict[str, Any] | None,
) -> str:
    """返回需要立即回复的直接交互原因。

    ``reply.is_self`` 只表示消息引用了机器人。若用户同时明确 @ 其他成员，
    该消息仍与机器人上下文相关，但不应被视为直接对机器人说话。
    """
    if not is_group:
        return "private"
    if any(bool(item.get("is_self")) for item in mentions if isinstance(item, dict)):
        return "mention_self"
    has_other_mention = any(
        not bool(item.get("is_self")) for item in mentions if isinstance(item, dict)
    )
    if isinstance(reply, dict) and reply.get("is_self") is True and not has_other_mention:
        return "reply_to_self"
    if isinstance(reply, dict) and reply.get("is_self") is True and has_other_mention:
        return ""
    if event_is_tome:
        return "adapter_tome"
    return ""


def extract_onebot_sent_message_ids(receipt: Any) -> List[str]:
    """从 UniMessage 回执中提取并去重 OneBot 平台消息 ID。"""
    raw_ids = _object_value(receipt, "msg_ids")
    if not isinstance(raw_ids, (list, tuple)):
        return []

    message_ids: List[str] = []
    seen = set()
    for raw_id in raw_ids:
        value = _object_value(raw_id, "message_id")
        if value is None and isinstance(raw_id, dict):
            value = raw_id.get("message_id")
        if value is None:
            value = raw_id
        message_id = _string_value(value)
        if message_id and message_id not in seen:
            seen.add(message_id)
            message_ids.append(message_id)
    return message_ids


def extract_onebot_image_metadata(message: Any) -> List[Dict[str, Any]]:
    """从 OneBot 消息段中提取图片元信息。"""
    try:
        segments = list(message or [])
    except TypeError:
        return []

    images: List[Dict[str, Any]] = []
    for index, segment in enumerate(segments):
        if _segment_type(segment) != "image":
            continue

        data = _segment_data(segment)
        item: Dict[str, Any] = {"segment_index": index}

        for key in ("url", "file_id", "file"):
            value = data.get(key)
            if value not in (None, ""):
                item[key] = str(value)

        mime = data.get("mime") or data.get("mimetype") or data.get("content_type")
        if mime not in (None, ""):
            item["mime"] = str(mime)

        size = _to_int_or_none(data.get("size"))
        if size is None:
            size = _to_int_or_none(data.get("file_size"))
        if size is not None:
            item["size"] = size

        images.append(item)

    return images


def normalize_content_for_storage(
    plain_text: str,
    images: List[Dict[str, Any]],
    *,
    image_only_placeholder: str = IMAGE_ONLY_PLACEHOLDER,
    message_segments: Any = None,
) -> str:
    """根据文本与图片情况，生成用于入库的 content。"""
    if message_segments is not None:
        rebuilt = _rebuild_content_with_segment_index(
            message_segments,
            images,
            image_only_placeholder=image_only_placeholder,
        )
        if rebuilt:
            return rebuilt

    text = (plain_text or "").strip()
    if text:
        if images:
            if image_only_placeholder in text:
                return text
            return f"{text} {image_only_placeholder}"
        return text
    if images:
        return image_only_placeholder
    return ""


def _resolve_event_message_segments(event: Any) -> Any:
    getter = getattr(event, "get_message", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return getattr(event, "message", None)
    return getattr(event, "message", None)


def _resolve_original_event_message_segments(event: Any, *, message_segments: Any = None) -> Any:
    original_message = getattr(event, "original_message", None)
    if original_message is not None:
        return original_message
    return message_segments


def _safe_event_plaintext(event: Any) -> str:
    getter = getattr(event, "get_plaintext", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            return ""
    return ""


def _rebuild_content_with_segment_index(
    message_segments: Any,
    images: List[Dict[str, Any]],
    *,
    image_only_placeholder: str,
) -> str:
    """基于 segment_index 重建图文混排文本，保留图片在原消息中的位置。"""
    try:
        segments = list(message_segments or [])
    except TypeError:
        return ""
    if not segments:
        return ""

    image_count_by_index: Dict[int, int] = {}
    for image in images:
        if not isinstance(image, dict):
            continue
        index = _to_int_or_none(image.get("segment_index"))
        if index is None:
            continue
        image_count_by_index[index] = image_count_by_index.get(index, 0) + 1

    parts: List[str] = []
    has_image = False
    has_index_mapping = bool(image_count_by_index)
    previous_segment_type = ""
    for index, segment in enumerate(segments):
        segment_type = _segment_type(segment)
        if segment_type == "text":
            text = str(_segment_data(segment).get("text") or "")
            if text:
                if (
                    parts
                    and previous_segment_type in {"at", "image"}
                    and not text[:1].isspace()
                ):
                    parts.append(" ")
                parts.append(text)
        elif segment_type == "at":
            mention = _render_mention_segment(segment)
            if mention:
                if parts and not parts[-1].endswith((" ", "\t", "\n")):
                    parts.append(" ")
                parts.append(mention)

        placeholder_count = image_count_by_index.get(index, 0)
        if placeholder_count <= 0 and not has_index_mapping and segment_type == "image":
            placeholder_count = 1

        for _ in range(placeholder_count):
            if parts and not parts[-1].endswith((" ", "\t", "\n")):
                parts.append(" ")
            parts.append(image_only_placeholder)
            has_image = True
        previous_segment_type = segment_type

    rebuilt = "".join(parts).strip()
    if rebuilt:
        return rebuilt
    if has_image:
        return image_only_placeholder
    return ""


def build_onebot_metadata(
    *,
    self_id: Any,
    message_id: Any,
    images: List[Dict[str, Any]],
    mentions: List[Dict[str, Any]] | None = None,
    reply: Dict[str, Any] | None = None,
    direct_reason: str = "",
) -> Dict[str, Any]:
    """构造标准化 metadata。"""
    onebot: Dict[str, Any] = {}
    if self_id is not None:
        onebot["self_id"] = str(self_id)
    if message_id is not None:
        onebot["message_id"] = str(message_id)
    if mentions:
        onebot["mentions"] = mentions
        if any(bool(item.get("is_self")) for item in mentions if isinstance(item, dict)):
            onebot["mentioned_self"] = True
    if reply:
        onebot["reply"] = reply
        if reply.get("is_self") is True:
            onebot["reply_to_self"] = True
    if direct_reason:
        onebot["direct_reason"] = direct_reason

    return {
        "onebot": onebot,
        "media": {
            "images": images,
        },
    }
