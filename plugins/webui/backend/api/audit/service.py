import json
import logging
import re
from typing import Any, Dict, Optional

from fastapi import Request

from ..db.models import OperationAuditLog
from .types import KNOWN_AUDIT_ACTIONS, KNOWN_AUDIT_TARGET_TYPES

_SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
)
_MAX_STRING_LENGTH = 500
_MAX_COLLECTION_ITEMS = 50
_MAX_DETAIL_LENGTH = 4000


def _truncate_text(value: str, max_length: int = _MAX_STRING_LENGTH) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}...(truncated, total={len(value)})"


def _is_sensitive_key(key: str) -> bool:
    lower_key = key.lower()
    return any(keyword in lower_key for keyword in _SENSITIVE_KEYWORDS)


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    if depth >= 4:
        return "[truncated-depth]"

    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                sanitized["__truncated_items__"] = len(value) - _MAX_COLLECTION_ITEMS
                break
            normalized_key = str(key)
            if _is_sensitive_key(normalized_key):
                sanitized[normalized_key] = "***"
                continue
            sanitized[normalized_key] = _sanitize_value(item, depth + 1)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        sequence = list(value)
        sanitized_items = [
            _sanitize_value(item, depth + 1)
            for item in sequence[:_MAX_COLLECTION_ITEMS]
        ]
        if len(sequence) > _MAX_COLLECTION_ITEMS:
            sanitized_items.append(
                f"...(truncated, total={len(sequence)})"
            )
        return sanitized_items

    if isinstance(value, str):
        return _truncate_text(value)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return _truncate_text(str(value))


def sanitize_payload(payload: Any) -> Any:
    return _sanitize_value(payload)


def _serialize_detail(detail: Dict[str, Any]) -> Optional[str]:
    if not detail:
        return None
    try:
        encoded = json.dumps(detail, ensure_ascii=False, default=str)
    except Exception:
        encoded = json.dumps({"raw": _truncate_text(str(detail))}, ensure_ascii=False)
    return _truncate_text(encoded, _MAX_DETAIL_LENGTH)


def _normalize_action(action: str) -> str:
    normalized = str(action or "").strip()
    if not normalized:
        return "custom.unknown"
    if normalized in KNOWN_AUDIT_ACTIONS:
        return normalized
    return f"custom.{normalized}"


def _normalize_target_type(target_type: str) -> str:
    normalized = str(target_type or "").strip()
    if not normalized:
        return "custom_target"
    if normalized in KNOWN_AUDIT_TARGET_TYPES:
        return normalized
    return f"custom_{normalized}"


def is_mutating_cypher(query: str) -> bool:
    pattern = re.compile(
        r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|FOREACH|LOAD\s+CSV)\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(query or ""))


async def record_operation_audit(
    *,
    username: str,
    action: str,
    target_type: str,
    request: Optional[Request] = None,
    target_id: Optional[str] = None,
    success: bool = True,
    before: Any = None,
    after: Any = None,
    extra: Any = None,
    error_message: Optional[str] = None,
) -> None:
    detail_payload: Dict[str, Any] = {}
    if before is not None:
        detail_payload["before"] = sanitize_payload(before)
    if after is not None:
        detail_payload["after"] = sanitize_payload(after)
    if extra is not None:
        detail_payload["extra"] = sanitize_payload(extra)
    if error_message:
        detail_payload["error"] = _truncate_text(error_message, 800)

    request_method = request.method if request else None
    request_path = request.url.path if request else None
    ip_address = request.client.host if request and request.client else None
    user_agent = _truncate_text(request.headers.get("user-agent", ""), 255) if request else None

    try:
        await OperationAuditLog.create(
            username=username,
            action=_normalize_action(action),
            target_type=_normalize_target_type(target_type),
            target_id=target_id,
            success=success,
            detail=_serialize_detail(detail_payload),
            request_method=request_method,
            request_path=request_path,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as exc:
        logging.error("写入操作审计日志失败: %s", exc)
