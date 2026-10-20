import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from tortoise import Tortoise

from src.infra.db.tortoise.plugin_models import (
    RegisteredUnitUsageEvent,
    RegisteredUnitUsageSummary,
)
from src.infra.db.tortoise.registered_unit_usage import (
    cleanup_expired_registered_unit_usage,
    list_registered_unit_usage,
    record_registered_unit_usage,
)


def test_registered_usage_retains_last_use_after_90_day_event_cleanup(tmp_path):
    async def check():
        await Tortoise.init(
            db_url=f"sqlite://{tmp_path / 'usage.sqlite3'}",
            modules={"models": ["src.infra.db.tortoise.plugin_models"]},
        )
        try:
            await Tortoise.generate_schemas()
            with pytest.raises(ValueError, match="未注册"):
                await record_registered_unit_usage("network.unregistered")
            assert await RegisteredUnitUsageEvent.all().count() == 0

            await record_registered_unit_usage("network.socks_proxy")
            recent = (await list_registered_unit_usage())[0]
            assert recent["usage_count"] == 1
            assert recent["last_used_at"] is not None

            old_time = datetime.now(timezone.utc) - timedelta(days=91)
            await RegisteredUnitUsageEvent.all().update(created_at=old_time)
            older = (await list_registered_unit_usage())[0]
            assert older["usage_count"] == 0
            assert older["last_used_at"] == recent["last_used_at"]

            assert await cleanup_expired_registered_unit_usage() == 1
            assert await RegisteredUnitUsageEvent.all().count() == 0
            assert await RegisteredUnitUsageSummary.all().count() == 1
        finally:
            await Tortoise.close_connections()

    asyncio.run(check())


def test_concurrent_registered_usage_attempts_are_all_counted(tmp_path):
    async def check():
        await Tortoise.init(
            db_url=f"sqlite://{tmp_path / 'concurrent.sqlite3'}",
            modules={"models": ["src.infra.db.tortoise.plugin_models"]},
        )
        try:
            await Tortoise.generate_schemas()
            await asyncio.gather(*(
                record_registered_unit_usage("network.socks_proxy") for _ in range(8)
            ))
            assert (await list_registered_unit_usage())[0]["usage_count"] == 8
        finally:
            await Tortoise.close_connections()

    asyncio.run(check())
