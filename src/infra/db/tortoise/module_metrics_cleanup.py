"""模块指标保留期清理函数。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional


async def cleanup_expired_module_metric_events(
    model: Any,
    *,
    retention_days: int = 90,
    now: Optional[datetime] = None,
) -> int:
    """删除保留期之外的模块指标事件，返回删除行数。"""
    current_time = now or datetime.utcnow()
    cutoff = current_time - timedelta(days=retention_days)
    return await model.filter(created_at__lt=cutoff).delete()
