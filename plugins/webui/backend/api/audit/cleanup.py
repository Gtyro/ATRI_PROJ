from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..db.models import OperationAuditLog


async def cleanup_expired_operation_audit_logs(
    *,
    retention_days: int,
    now: Optional[datetime] = None,
) -> int:
    normalized_days = max(1, int(retention_days))
    current = now or datetime.utcnow()
    cutoff = current - timedelta(days=normalized_days)
    deleted_count = await OperationAuditLog.filter(created_at__lt=cutoff).delete()
    return int(deleted_count)
