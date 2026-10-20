"""Usage history for explicitly registered infrastructure units."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from tortoise.transactions import in_transaction

from .plugin_models import RegisteredUnitUsageEvent, RegisteredUnitUsageSummary


REGISTERED_UNITS = {
    "network.socks_proxy": "SOCKS 代理请求",
}
RETENTION_DAYS = 90


async def record_registered_unit_usage(unit_id: str) -> None:
    if unit_id not in REGISTERED_UNITS:
        raise ValueError(f"未注册的统计单元: {unit_id}")

    occurred_at = datetime.now(timezone.utc)
    async with in_transaction() as connection:
        await RegisteredUnitUsageEvent.create(unit_id=unit_id, using_db=connection)
        summary, created = await RegisteredUnitUsageSummary.get_or_create(
            unit_id=unit_id,
            defaults={"last_used_at": occurred_at},
            using_db=connection,
        )
        previous = summary.last_used_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        if not created and previous < occurred_at:
            summary.last_used_at = occurred_at
            await summary.save(using_db=connection, update_fields=["last_used_at"])


async def list_registered_unit_usage(*, now: datetime | None = None) -> list[dict[str, Any]]:
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=RETENTION_DAYS)
    rows = []
    for unit_id, label in REGISTERED_UNITS.items():
        recent_count = await RegisteredUnitUsageEvent.filter(
            unit_id=unit_id,
            created_at__gte=cutoff,
            created_at__lte=current_time,
        ).count()
        summary = await RegisteredUnitUsageSummary.get_or_none(unit_id=unit_id)
        last_used_at = summary.last_used_at if summary else None
        if last_used_at is not None and last_used_at.tzinfo is None:
            last_used_at = last_used_at.replace(tzinfo=timezone.utc)
        rows.append({
            "unit_id": unit_id,
            "label": label,
            "window_days": RETENTION_DAYS,
            "usage_count": recent_count,
            "last_used_at": last_used_at.isoformat() if last_used_at else None,
        })
    return rows


async def cleanup_expired_registered_unit_usage(*, now: datetime | None = None) -> int:
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=RETENTION_DAYS)
    return await RegisteredUnitUsageEvent.filter(created_at__lt=cutoff).delete()
