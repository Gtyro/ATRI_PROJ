from __future__ import annotations

from datetime import datetime, timedelta

from .models import WordCloudData

WORDCLOUD_RETENTION_DAYS = 30


async def cleanup_expired_wordcloud_data(
    *,
    model=WordCloudData,
    retention_days: int = WORDCLOUD_RETENTION_DAYS,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.utcnow()
    cutoff = current_time - timedelta(days=retention_days)
    return await model.filter(created_at__lt=cutoff).delete()
