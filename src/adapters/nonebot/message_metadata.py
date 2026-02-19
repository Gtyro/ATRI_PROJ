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
    if images and message_segments is not None:
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
    for index, segment in enumerate(segments):
        segment_type = _segment_type(segment)
        if segment_type == "text":
            text = str(_segment_data(segment).get("text") or "")
            if text:
                if parts and parts[-1] == image_only_placeholder and not text[:1].isspace():
                    parts.append(" ")
                parts.append(text)

        placeholder_count = image_count_by_index.get(index, 0)
        if placeholder_count <= 0 and not has_index_mapping and segment_type == "image":
            placeholder_count = 1

        for _ in range(placeholder_count):
            if parts and not parts[-1].endswith((" ", "\t", "\n")):
                parts.append(" ")
            parts.append(image_only_placeholder)
            has_image = True

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
) -> Dict[str, Any]:
    """构造标准化 metadata。"""
    onebot: Dict[str, Any] = {}
    if self_id is not None:
        onebot["self_id"] = str(self_id)
    if message_id is not None:
        onebot["message_id"] = str(message_id)

    return {
        "onebot": onebot,
        "media": {
            "images": images,
        },
    }
