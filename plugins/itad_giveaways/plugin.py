from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from nonebot import get_bots, get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.permission import SUPERUSER
from nonebot_plugin_apscheduler import scheduler

from src.adapters.nonebot.command_registry import register_auto_feature, register_command

from .config import ItadGiveawaysConfig
from .service import (
    DailyGiveawayState,
    Giveaway,
    build_daily_report,
    fetch_active_giveaways,
    format_giveaway_messages,
    load_state,
    mark_notification_sent,
    write_state,
)


logger = logging.getLogger(__name__)
STATE_PATH = Path("data/itad_giveaways_last_result.json")
config = ItadGiveawaysConfig.load()


@dataclass(frozen=True)
class CheckResult:
    fetched_count: int
    todays_giveaways: tuple[Giveaway, ...]
    state: DailyGiveawayState | None = None
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
        return CheckResult(0, (), reason="未配置 ITAD API Key")

    try:
        report_date = datetime.now(ZoneInfo(config.timezone)).date().isoformat()
    except Exception as exc:
        logger.error("Invalid ITAD giveaways timezone %s: %s", config.timezone, exc)
        return CheckResult(0, (), reason="时区配置无效")

    previous_state = load_state(STATE_PATH)
    if previous_state.report_date == report_date:
        logger.info("ITAD giveaways check reused daily report for %s", report_date)
        return CheckResult(
            len(previous_state.snapshot_ids),
            previous_state.todays_giveaways,
            previous_state,
        )

    try:
        giveaways = await fetch_active_giveaways(
            api_key=config.api_key,
            api_url=config.api_url,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:
        logger.error("Failed to fetch ITAD giveaways: %s", exc, exc_info=True)
        return CheckResult(0, (), reason="ITAD 请求失败")

    try:
        state = build_daily_report(
            giveaways,
            previous_state=previous_state,
            report_date=report_date,
        )
        write_state(STATE_PATH, state)
    except Exception as exc:
        logger.error("Failed to save ITAD daily giveaway report: %s", exc, exc_info=True)
        return CheckResult(len(giveaways), (), reason="日报状态写入失败")

    logger.info(
        "ITAD giveaways check finished: fetched=%s today=%s",
        len(giveaways),
        len(state.todays_giveaways),
    )
    return CheckResult(len(giveaways), state.todays_giveaways, state)


def _format_daily_report(result: CheckResult) -> list[str]:
    if result.todays_giveaways:
        return format_giveaway_messages(result.todays_giveaways)
    return [f"ITAD 限免日报：今日无新增活动。当前有效活动 {result.fetched_count} 项。"]


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
        result = await run_giveaway_check()
        if result.state is not None and result.state.notification_sent:
            logger.info("ITAD daily giveaway report was already sent for %s", result.state.report_date)
            return
        messages = (
            [f"ITAD 限免日报检查失败：{result.reason}"]
            if result.reason
            else _format_daily_report(result)
        )
        notified, reason = await _send_messages_to_recipients(messages)
        if not notified:
            logger.error("Failed to send ITAD daily giveaway report: %s", reason)
            return
        if result.state is not None:
            try:
                mark_notification_sent(STATE_PATH, result.state)
            except OSError as exc:
                logger.error("Failed to mark ITAD daily giveaway report as notified: %s", exc)


@itad_giveaways_check.handle()
async def handle_itad_giveaways_check() -> None:
    result = await run_giveaway_check()
    if result.reason:
        await itad_giveaways_check.finish(f"ITAD 限免检查未完成：{result.reason}")
    messages = _format_daily_report(result)
    for message in messages[:-1]:
        await itad_giveaways_check.send(message)
    await itad_giveaways_check.finish(messages[-1])
