"""基础消息保留期清理函数。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

BASIC_MESSAGE_RETENTION_DAYS = 120


async def cleanup_expired_basic_messages(
    *,
    retention_days: int = BASIC_MESSAGE_RETENTION_DAYS,
    now: Optional[datetime] = None,
    model: Any = None,
) -> int:
    """删除保留期之外的基础消息，返回删除行数。"""
    if model is None:
        from plugins.message_basic.models import BasicMessage

        model = BasicMessage

    normalized_days = max(1, int(retention_days))
    current = now or datetime.utcnow()
    cutoff = current - timedelta(days=normalized_days)
    deleted_count = await model.filter(created_at__lt=cutoff).delete()
    return int(deleted_count)
