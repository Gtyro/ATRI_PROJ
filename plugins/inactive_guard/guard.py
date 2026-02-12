from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Set

from nonebot_plugin_apscheduler import scheduler
from tortoise.functions import Count

from plugins.message_basic.models import BasicMessage
from src.adapters.nonebot.command_registry import register_auto_feature
from src.core.services.plugin_policy_defaults import get_auto_disable_plugins
from src.core.services.plugin_policy_service import PluginPolicyService
from src.infra.db.tortoise.plugin_policy_store import TortoisePluginPolicyStore

from .config import InactiveGuardConfig


logger = logging.getLogger(__name__)

config = InactiveGuardConfig.load()
policy_service = PluginPolicyService(TortoisePluginPolicyStore())

register_auto_feature(
    "群活跃度检查",
    role="superuser",
    trigger_type="schedule",
)


def _parse_group_id(conv_id: str) -> str:
    return conv_id.split("_", 1)[1] if "_" in conv_id else conv_id


async def _load_all_group_ids() -> List[str]:
    conv_ids = (
        await BasicMessage.filter(conv_id__startswith="group_")
        .distinct()
        .values_list("conv_id", flat=True)
    )
    return [_parse_group_id(conv_id) for conv_id in conv_ids]


async def _load_recent_counts(start_time: datetime) -> Dict[str, int]:
    rows = (
        await BasicMessage.filter(
            conv_id__startswith="group_",
            created_at__gte=start_time,
        )
        .group_by("conv_id")
        .annotate(total=Count("id"))
        .values("conv_id", "total")
    )
    return {row.get("conv_id", ""): int(row.get("total") or 0) for row in rows}


def _build_active_set(recent_counts: Dict[str, int], threshold: int) -> Set[str]:
    active: Set[str] = set()
    for conv_id, total in recent_counts.items():
        if total >= threshold:
            active.add(_parse_group_id(conv_id))
    return active


async def _disable_plugins_for_group(gid: str, plugins: Iterable[str]) -> int:
    disabled = 0
    for plugin in plugins:
        try:
            policy = await policy_service.get_policy(gid=gid, plugin_name=plugin)
            if not policy.enabled:
                continue
            await policy_service.set_policy(gid=gid, plugin_name=plugin, enabled=False)
            disabled += 1
            logger.info("Disabled plugin %s for group %s due to inactivity", plugin, gid)
        except Exception as exc:
            logger.error("Failed to disable plugin %s for group %s: %s", plugin, gid, exc)
    return disabled


async def run_inactive_guard() -> None:
    if not config.auto_enabled:
        logger.info("inactive guard auto task is disabled")
        return

    plugins = get_auto_disable_plugins()
    if not plugins:
        logger.info("No plugins marked for auto-disable on inactivity")
        return

    all_groups = await _load_all_group_ids()
    if not all_groups:
        logger.info("No group messages found, skip inactivity check")
        return

    start_time = datetime.now() - timedelta(hours=config.window_hours)
    recent_counts = await _load_recent_counts(start_time)
    active_groups = _build_active_set(recent_counts, config.active_message_threshold)

    inactive_groups = [gid for gid in all_groups if gid not in active_groups]
    if not inactive_groups:
        logger.info("All groups are active within last %s hours", config.window_hours)
        return

    if config.dry_run:
        logger.info(
            "Dry run: %s inactive groups, plugins=%s",
            len(inactive_groups),
            ", ".join(plugins),
        )
        return

    total_disabled = 0
    for gid in inactive_groups:
        total_disabled += await _disable_plugins_for_group(gid, plugins)

    logger.info(
        "Inactivity check finished. groups=%s disabled=%s",
        len(inactive_groups),
        total_disabled,
    )


def setup_scheduler() -> None:
    if not config.auto_enabled:
        logger.info("inactive guard auto task is disabled")
        return

    try:
        hour, minute = map(int, config.schedule_time.split(":", 1))
    except Exception:
        logger.error("Invalid schedule_time in inactive guard config: %s", config.schedule_time)
        return

    @scheduler.scheduled_job("cron", hour=hour, minute=minute, id="inactive_guard_check")
    async def _():
        try:
            await run_inactive_guard()
        except Exception as exc:
            logger.error("Inactive guard task failed: %s", exc)
