import logging
from datetime import datetime, timedelta

from nonebot import get_driver, require
from nonebot.plugin import PluginMetadata

from src.infra.db.tortoise.basic_message_cleanup import (
    BASIC_MESSAGE_RETENTION_DAYS,
    cleanup_expired_basic_messages,
)

try:
    driver = get_driver()
except ValueError:
    driver = None

if driver is not None:
    require("db_core")

from . import models

if driver is not None:
    from . import handlers

__plugin_meta__ = PluginMetadata(
    name="基础消息",
    description="记录和统计基础消息数据",
    usage="消息概览",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

__all__ = ["models"]

if driver is not None:
    __all__.append("handlers")


async def _run_basic_message_retention_cleanup(context: str) -> None:
    now = datetime.utcnow()
    try:
        deleted_count = await cleanup_expired_basic_messages(
            retention_days=BASIC_MESSAGE_RETENTION_DAYS,
            now=now,
        )
        cutoff = now - timedelta(days=BASIC_MESSAGE_RETENTION_DAYS)
        logging.info(
            "基础消息%s清理完成: deleted=%s cutoff=%s",
            context,
            deleted_count,
            cutoff.isoformat(),
        )
    except Exception as exc:
        logging.error("基础消息%s清理异常: %s", context, exc, exc_info=True)


if driver is not None:
    @driver.on_startup
    async def _cleanup_basic_messages_on_startup() -> None:
        await _run_basic_message_retention_cleanup("启动时")

    try:
        from nonebot_plugin_apscheduler import scheduler
    except Exception:
        scheduler = None

    if scheduler is not None:
        @scheduler.scheduled_job(
            "cron",
            hour=3,
            minute=30,
            id="basic_message_retention_cleanup",
        )
        async def _cleanup_basic_messages_on_schedule() -> None:
            await _run_basic_message_retention_cleanup("定时")
