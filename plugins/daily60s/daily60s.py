from __future__ import annotations

import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from nonebot import get_bots
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot_plugin_apscheduler import scheduler

from src.adapters.nonebot.command_registry import register_auto_feature, register_command
from src.core.services.plugin_policy_service import PluginPolicyService
from src.infra.temp_storage import TempStorage
from src.infra.db.tortoise.plugin_policy_store import TortoisePluginPolicyStore

from .config import Daily60sConfig


logger = logging.getLogger(__name__)

PLUGIN_NAME = (__package__ or "daily60s").split(".")[-1]

config = Daily60sConfig.load()
temp_store = TempStorage("daily60s")
policy_service = PluginPolicyService(TortoisePluginPolicyStore())


daily60s_cmd = register_command(
    "每日早报",
    role="normal",
    priority=5,
    block=True,
)

register_auto_feature(
    "每日早报自动获取",
    role="superuser",
    trigger_type="schedule",
)


def _today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _cache_key(date_key: str) -> str:
    return f"daily60s_{date_key}"


def _build_file_uri(path: Path) -> str:
    resolved = path.resolve().as_posix()
    if not resolved.startswith("/"):
        resolved = "/" + resolved
    return f"file://{resolved}"


def _guess_suffix(content_type: str) -> str:
    normalized = content_type.split(";")[0].strip().lower() if content_type else ""
    if normalized in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if normalized == "image/png":
        return ".png"
    if normalized == "image/webp":
        return ".webp"
    if normalized == "image/gif":
        return ".gif"
    guessed = mimetypes.guess_extension(normalized) if normalized else None
    return guessed if guessed else ".jpg"


def _extract_image_url(payload: dict) -> Optional[str]:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("image", "img", "head_image", "imageUrl", "url"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(data, str) and data:
        return data
    return None


def _normalize_gid(value: object) -> Optional[str]:
    if value is None:
        return None
    gid = str(value).strip()
    return gid if gid else None


async def _load_enabled_group_ids() -> List[str]:
    try:
        policies = await policy_service.list_policies(plugin_name=PLUGIN_NAME)
    except Exception as exc:
        logger.error("Failed to load daily60s policy list: %s", exc)
        return []
    gids = [policy.gid for policy in policies if policy.enabled]
    return sorted({gid for gid in gids if gid})


async def _safe_get_group_list(bot: Bot) -> List[Dict[str, object]]:
    try:
        if hasattr(bot, "get_group_list"):
            groups = await bot.get_group_list()
            return groups or []
    except Exception as exc:
        logger.warning(
            "Failed to load group list for bot %s: %s",
            getattr(bot, "self_id", "unknown"),
            exc,
        )
    return []


async def _build_group_bot_map() -> Dict[str, Bot]:
    bots = get_bots()
    group_map: Dict[str, Bot] = {}
    for bot in bots.values():
        groups = await _safe_get_group_list(bot)
        for group in groups:
            gid = _normalize_gid(group.get("group_id") or group.get("gid"))
            if gid and gid not in group_map:
                group_map[gid] = bot
    return group_map


async def _send_daily_image_to_groups() -> None:
    if not config.alapi_key:
        logger.warning("daily60s auto send skipped: missing alapi_key")
        return

    group_ids = await _load_enabled_group_ids()
    if not group_ids:
        logger.info("daily60s auto send skipped: no enabled groups")
        return

    bots = get_bots()
    if not bots:
        logger.warning("daily60s auto send skipped: no active bots")
        return

    group_bot_map = await _build_group_bot_map()
    fallback_bot = next(iter(bots.values())) if bots else None
    use_fallback = not group_bot_map and fallback_bot is not None

    try:
        image_path = await get_daily_image_path()
    except Exception as exc:
        logger.error("daily60s auto send failed to fetch image: %s", exc)
        return

    image_message = MessageSegment.image(_build_file_uri(image_path))
    sent = 0
    for gid in group_ids:
        bot = group_bot_map.get(gid) if not use_fallback else fallback_bot
        if bot is None:
            logger.info("daily60s auto send skipped: no bot for group %s", gid)
            continue
        if not use_fallback and gid not in group_bot_map:
            logger.info("daily60s auto send skipped: bot not in group %s", gid)
            continue
        try:
            await bot.send_group_msg(group_id=int(gid), message=image_message)
            sent += 1
        except Exception as exc:
            logger.error("daily60s auto send failed for group %s: %s", gid, exc)
    logger.info("daily60s auto send finished: sent=%s target=%s", sent, len(group_ids))


async def _fetch_daily_image() -> Tuple[bytes, str]:
    if not config.alapi_key:
        raise RuntimeError("Missing alapi_key in config")

    params = {"format": config.image_format}
    headers = {"token": config.alapi_key}
    params["token"] = config.alapi_key

    async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=True) as client:
        response = await client.get(config.api_url, params=params, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("image/"):
            return response.content, content_type

        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("Unexpected response from API") from exc

        if isinstance(payload, dict):
            code = payload.get("code")
            if code not in (None, 200, "200"):
                message = payload.get("msg") or payload.get("message") or "unknown error"
                raise RuntimeError(f"API error: {message}")

            image_url = _extract_image_url(payload)
            if image_url:
                image_resp = await client.get(image_url, follow_redirects=True)
                image_resp.raise_for_status()
                return image_resp.content, image_resp.headers.get("content-type", "")

        raise RuntimeError("API did not return image data")


async def get_daily_image_path(*, force_refresh: bool = False) -> Path:
    date_key = _today_key()
    cache_key = _cache_key(date_key)

    if not force_refresh:
        cached = temp_store.get_path(cache_key)
        if cached and cached.exists() and cached.stat().st_size > 0:
            return cached

    image_bytes, content_type = await _fetch_daily_image()
    suffix = _guess_suffix(content_type)
    return temp_store.write_bytes(
        cache_key,
        image_bytes,
        suffix=suffix,
        content_type=content_type,
    )


def setup_scheduler() -> None:
    if not config.auto_enabled:
        logger.info("daily60s auto task is disabled")
        return

    try:
        hour, minute = map(int, config.schedule_time.split(":", 1))
    except Exception:
        logger.error("Invalid schedule_time in daily60s config: %s", config.schedule_time)
        return

    @scheduler.scheduled_job("cron", hour=hour, minute=minute, id="daily60s_broadcast")
    async def _():
        try:
            await _send_daily_image_to_groups()
        except Exception as exc:
            logger.error("daily60s auto task failed: %s", exc)


@daily60s_cmd.handle()
async def handle_daily60s(event: MessageEvent):
    if not config.alapi_key:
        await daily60s_cmd.finish("未配置 alapi key，请在 data/daily60s.yaml 中设置 alapi_key")
        return

    try:
        image_path = await get_daily_image_path()
    except Exception as exc:
        logger.error("Failed to fetch daily60s image: %s", exc, exc_info=True)
        await daily60s_cmd.finish("获取每日早报失败，请稍后再试")
        return

    await daily60s_cmd.finish(MessageSegment.image(_build_file_uri(image_path)))
