from __future__ import annotations

import re
from typing import Any, Dict, List


_LEADING_MENTION_PATTERN = re.compile(r"^(?:@(?:\S+)\s*)+")


def format_message_history_entry(message: Dict[str, Any]) -> str:
    sender = "你" if message.get("is_bot", False) else str(message.get("user_name") or "用户")
    content = str(message.get("content") or "").strip()

    if message.get("is_bot", False):
        return _join_sender_and_content(sender, "说", content)

    mentioned_self, normalized_content = _normalize_direct_mention_content(message, content)
    if mentioned_self:
        return _join_sender_and_content(sender, "@了你", normalized_content)
    if message.get("is_direct", False):
        return _join_sender_and_content(sender, "对你说", content)
    return _join_sender_and_content(sender, "说", content)


def _join_sender_and_content(sender: str, action: str, content: str) -> str:
    prefix = f"[{sender}]{action}"
    if content:
        return f"{prefix}: {content}"
    return prefix


def _normalize_direct_mention_content(message: Dict[str, Any], content: str) -> tuple[bool, str]:
    if not content or not message.get("is_direct", False):
        return False, content
    conv_id = str(message.get("conv_id") or "").strip()
    if not conv_id.startswith("group_"):
        return False, content

    normalized = _strip_leading_self_mentions_from_metadata(message, content)
    if normalized != content:
        return True, normalized

    fallback = _LEADING_MENTION_PATTERN.sub("", content, count=1).strip()
    if fallback != content:
        return True, fallback
    return False, content


def _strip_leading_self_mentions_from_metadata(message: Dict[str, Any], content: str) -> str:
    mention_texts = _extract_self_mention_texts(message)
    normalized = content
    changed = False
    for mention_text in mention_texts:
        while mention_text and normalized.startswith(mention_text):
            normalized = normalized[len(mention_text):].lstrip()
            changed = True
    return normalized if changed else content


def _extract_self_mention_texts(message: Dict[str, Any]) -> List[str]:
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return []
    onebot = metadata.get("onebot")
    if not isinstance(onebot, dict):
        return []
    mentions = onebot.get("mentions")
    if not isinstance(mentions, list):
        return []

    texts: List[str] = []
    seen = set()
    for item in mentions:
        if not isinstance(item, dict) or not item.get("is_self"):
            continue
        text = str(item.get("text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
    return texts
