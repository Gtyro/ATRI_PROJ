"""NoneBot/Alconna 参数解析辅助工具。"""

from __future__ import annotations

from typing import Any, Iterable


_SEND_TOKENS = {
    "发送",
    "真发",
    "实发",
    "执行",
    "send",
}


def normalize_alconna_tokens(value: Any) -> list[str]:
    """将 Alconna 参数归一为 token 列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def parse_reply_send_mode(tokens: Iterable[str]) -> tuple[bool, str | None]:
    """解析“默认预览，显式发送”的回复命令参数。"""
    normalized_tokens = [str(item) for item in tokens]
    send_mode = False
    if normalized_tokens:
        head = normalized_tokens[0].strip().lower()
        if head in _SEND_TOKENS:
            send_mode = True
            normalized_tokens = normalized_tokens[1:]

    message = " ".join(item for item in normalized_tokens).strip()
    return send_mode, (message or None)
