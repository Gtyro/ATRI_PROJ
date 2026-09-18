from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from nonebot import get_bots, get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.permission import SUPERUSER
from nonebot_plugin_apscheduler import scheduler

from src.adapters.nonebot.command_registry import register_auto_feature, register_command

from .config import ItadGiveawaysConfig
from .service import (
    Giveaway,
    fetch_active_giveaways,
    format_giveaway_messages,
    load_state,
    select_new_giveaways,
    write_state,
)


logger = logging.getLogger(__name__)
STATE_PATH = Path("data/itad_giveaways_last_result.json")
config = ItadGiveawaysConfig.load()


@dataclass(frozen=True)
class CheckResult:
    fetched_count: int
    new_count: int
    notified: bool
    reason: str = ""


itad_giveaways_check = register_command(
    "ITAD限免检查",
    role="superuser",
    permission=SUPERUSER,
    priority=5,
    block=True,
    description="检查 ITAD 新增限免并私聊超级用户",
    usage="ITAD限免检查",
)

register_auto_feature(
    "ITAD 限免每日检查",
    role="superuser",
    trigger_type="schedule",
)


def _parse_schedule_time(schedule_time: str) -> tuple[int, int]:
    hour_text, minute_text = schedule_time.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("hour or minute is out of range")
    return hour, minute


def _recipient_ids() -> list[str]:
    configured_recipients = config.recipient_ids
    if configured_recipients:
        return list(dict.fromkeys(configured_recipients))

    superusers = get_driver().config.superusers or set()
    return list(dict.fromkeys(str(user_id) for user_id in superusers if str(user_id).isdigit()))


def _persist_current_ids(current_ids: Sequence[int]) -> str:
    try:
        write_state(STATE_PATH, current_ids)
    except OSError as exc:
        logger.error("Failed to persist ITAD giveaway state: %s", exc, exc_info=True)
        return "状态文件写入失败，将在下次检查时重试"
    return ""


async def _send_messages_to_recipients(messages: Sequence[str]) -> tuple[bool, str]:
    recipients = _recipient_ids()
    if not recipients:
        return False, "未配置 recipient_ids 或 SUPERUSERS"

    bots = get_bots()
    if not bots:
        return False, "没有活跃的机器人连接"
    bot: Bot = next(iter(bots.values()))

    failed: list[str] = []
    for user_id in recipients:
        for message in messages:
            try:
                await bot.send_private_msg(user_id=int(user_id), message=message)
            except Exception as exc:
                failed.append(user_id)
                logger.error("Failed to send ITAD giveaway notification to %s: %s", user_id, exc)
                break

    if failed:
        return False, f"私聊发送失败: {', '.join(sorted(set(failed)))}"
    return True, ""


async def run_giveaway_check() -> CheckResult:
    if not config.api_key:
        logger.warning("ITAD giveaways check skipped: API key is not configured")
        return CheckResult(0, 0, False, "未配置 ITAD API Key")

    try:
        giveaways = await fetch_active_giveaways(
            api_key=config.api_key,
            api_url=config.api_url,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:
        logger.error("Failed to fetch ITAD giveaways: %s", exc, exc_info=True)
        return CheckResult(0, 0, False, "ITAD 请求失败")

    previous_state = load_state(STATE_PATH)
    new_giveaways = select_new_giveaways(giveaways, previous_state.giveaway_ids)
    current_ids = [giveaway.id for giveaway in giveaways]
    if not new_giveaways:
        reason = _persist_current_ids(current_ids)
        if reason:
            return CheckResult(len(giveaways), 0, False, reason)
        logger.info("ITAD giveaways check finished: no new giveaways")
        return CheckResult(len(giveaways), 0, False)

    messages = format_giveaway_messages(new_giveaways)
    notified, reason = await _send_messages_to_recipients(messages)
    if not notified:
        logger.warning("ITAD giveaways found but state was not updated: %s", reason)
        return CheckResult(len(giveaways), len(new_giveaways), False, reason)

    reason = _persist_current_ids(current_ids)
    if reason:
        return CheckResult(len(giveaways), len(new_giveaways), True, reason)
    logger.info(
        "ITAD giveaways notification finished: fetched=%s new=%s",
        len(giveaways),
        len(new_giveaways),
    )
    return CheckResult(len(giveaways), len(new_giveaways), True)


def setup_scheduler() -> None:
    if not config.auto_enabled:
        logger.info("ITAD giveaways auto task is disabled")
        return

    try:
        hour, minute = _parse_schedule_time(config.schedule_time)
    except (TypeError, ValueError):
        logger.error("Invalid ITAD giveaways schedule_time: %s", config.schedule_time)
        return

    @scheduler.scheduled_job("cron", hour=hour, minute=minute, id="itad_giveaways_daily_check")
    async def _scheduled_itad_giveaways_check() -> None:
        await run_giveaway_check()


@itad_giveaways_check.handle()
async def handle_itad_giveaways_check() -> None:
    result = await run_giveaway_check()
    if result.reason:
        await itad_giveaways_check.finish(f"ITAD 限免检查未完成：{result.reason}")
    if result.new_count == 0:
        await itad_giveaways_check.finish(f"检查完成：当前 {result.fetched_count} 项限免，无新增活动")
    await itad_giveaways_check.finish(
        f"检查完成：发现 {result.new_count} 项新增限免，已私聊通知超级用户"
    )
