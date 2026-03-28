"""OneBot 消息元信息提取工具。"""

from __future__ import annotations

from typing import Any, Dict, List


IMAGE_ONLY_PLACEHOLDER = "[图片]"


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

    return {
        "onebot": onebot,
        "media": {
            "images": images,
        },
    }
