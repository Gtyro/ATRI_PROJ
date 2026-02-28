import asyncio
import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

import nonebot
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from nonebot import get_driver
from nonebot_plugin_uninfo import SceneType, get_interface
from nonebot_plugin_uninfo.model import BasicInfo
from pydantic import BaseModel

try:
    from plugins.message_basic.models import BasicMessage
except Exception:  # pragma: no cover - 兼容未安装消息插件的场景
    BasicMessage = None

try:
    from src.infra.db.tortoise.plugin_models import ModuleMetricEvent
except Exception:  # pragma: no cover - 兼容模块指标不可用的场景
    ModuleMetricEvent = None


router = APIRouter(tags=["bot_info"])
driver = get_driver()


@dataclass
class _BotConnectionState:
    connected_at: datetime
    last_seen_at: datetime
    online: bool = True
    last_disconnected_at: Optional[datetime] = None


@dataclass
class _ConnectionEvent:
    occurred_at: datetime
    account: str
    event_type: str
    duration_seconds: Optional[int] = None


_CONNECTION_STATES: Dict[str, _BotConnectionState] = {}
_CONNECTION_LOGS: Deque[_ConnectionEvent] = deque(maxlen=200)
_STATE_LOCK = asyncio.Lock()


class BotInfo(BaseModel):
    id: str
    platform: str
    group_count: int
    friend_count: int
    nickname: Optional[str] = None
    plugin_calls_today: int
    messages_today: int
    connected_date: str
    uptime: str


class ConnectionLog(BaseModel):
    date: str
    account: str
    duration: str


class HourlyThroughput(BaseModel):
    hours: List[str]
    data: List[int]


class DailyThroughput(BaseModel):
    start_date: str
    end_date: str
    data: List[Tuple[str, int]]


def _now() -> datetime:
    return datetime.now()


def _day_start(value: Optional[datetime] = None) -> datetime:
    current = value or _now()
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_duration(seconds: int) -> str:
    total_minutes = max(0, int(seconds) // 60)
    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)
    parts: List[str] = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0 or days > 0:
        parts.append(f"{hours}小时")
    parts.append(f"{minutes}分钟")
    return "".join(parts)


def _record_connection_event(
    *,
    account: str,
    event_type: str,
    occurred_at: datetime,
    duration_seconds: Optional[int] = None,
) -> None:
    _CONNECTION_LOGS.append(
        _ConnectionEvent(
            occurred_at=occurred_at,
            account=account,
            event_type=event_type,
            duration_seconds=duration_seconds,
        )
    )


async def _mark_bot_connected(bot_id: str, connected_at: Optional[datetime] = None) -> None:
    now = connected_at or _now()
    async with _STATE_LOCK:
        state = _CONNECTION_STATES.get(bot_id)
        if state and state.online:
            state.last_seen_at = now
            return
        _CONNECTION_STATES[bot_id] = _BotConnectionState(
            connected_at=now,
            last_seen_at=now,
            online=True,
            last_disconnected_at=None,
        )
        _record_connection_event(account=bot_id, event_type="connected", occurred_at=now)


async def _mark_bot_disconnected(bot_id: str, disconnected_at: Optional[datetime] = None) -> None:
    now = disconnected_at or _now()
    async with _STATE_LOCK:
        state = _CONNECTION_STATES.get(bot_id)
        duration_seconds: Optional[int] = None
        if state and state.online:
            duration_seconds = int((now - state.connected_at).total_seconds())
            state.online = False
            state.last_seen_at = now
            state.last_disconnected_at = now
        else:
            _CONNECTION_STATES[bot_id] = _BotConnectionState(
                connected_at=now,
                last_seen_at=now,
                online=False,
                last_disconnected_at=now,
            )
        _record_connection_event(
            account=bot_id,
            event_type="disconnected",
            occurred_at=now,
            duration_seconds=duration_seconds,
        )


@driver.on_bot_connect
async def _on_bot_connect(bot) -> None:
    await _mark_bot_connected(str(bot.self_id))


if hasattr(driver, "on_bot_disconnect"):
    @driver.on_bot_disconnect
    async def _on_bot_disconnect(bot) -> None:
        await _mark_bot_disconnected(str(bot.self_id))


async def get_platform(bot) -> str:
    try:
        interface = get_interface(bot)
        info: BasicInfo = interface.basic_info()
        scope = info.get("scope", "unknown")
        return str(scope)
    except Exception:
        return "unknown"


async def get_group_list(bot, count_only: bool = False):
    scene_count = 0
    try:
        interface = get_interface(bot)
        scenes = await interface.get_scenes(SceneType.GROUP)
        scene_count = len(scenes or [])
    except Exception:
        scene_count = 0

    try:
        if hasattr(bot, "get_group_list"):
            groups = await bot.get_group_list()
            return len(groups) if count_only else groups
    except Exception:
        pass
    return scene_count if count_only else []


async def get_friend_list(bot) -> int:
    try:
        if hasattr(bot, "get_friend_list"):
            friends = await bot.get_friend_list()
            return len(friends)
    except Exception:
        pass
    return 0


async def _get_today_metrics() -> Tuple[int, int]:
    start = _day_start()
    plugin_calls_today = 0
    messages_today = 0

    if ModuleMetricEvent is not None:
        try:
            plugin_calls_today = await ModuleMetricEvent.filter(created_at__gte=start).count()
        except Exception:
            plugin_calls_today = 0

    if BasicMessage is not None:
        try:
            messages_today = await BasicMessage.filter(created_at__gte=start).count()
        except Exception:
            messages_today = 0

    return plugin_calls_today, messages_today


async def _get_connection_snapshot(bot_id: str) -> Tuple[datetime, str]:
    now = _now()
    async with _STATE_LOCK:
        state = _CONNECTION_STATES.get(bot_id)
        if state is None:
            state = _BotConnectionState(connected_at=now, last_seen_at=now, online=True)
            _CONNECTION_STATES[bot_id] = state
            _record_connection_event(account=bot_id, event_type="connected", occurred_at=now)
        elif state.online:
            state.last_seen_at = now

        connected_at = state.connected_at
        if state.online:
            uptime_seconds = int((now - state.connected_at).total_seconds())
        else:
            end_at = state.last_disconnected_at or now
            uptime_seconds = int((end_at - state.connected_at).total_seconds())

    return connected_at, _format_duration(uptime_seconds)


async def _collect_message_timestamps(start: datetime) -> List[datetime]:
    if BasicMessage is None:
        return []
    try:
        rows = await BasicMessage.filter(created_at__gte=start).values_list("created_at", flat=True)
    except Exception:
        return []
    return [item for item in rows if isinstance(item, datetime)]


async def _build_hourly_throughput(hours: int = 24) -> HourlyThroughput:
    total_hours = max(1, min(hours, 24))
    end = _now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=total_hours - 1)

    buckets: Dict[datetime, int] = {}
    labels: List[str] = []
    for idx in range(total_hours):
        point = start + timedelta(hours=idx)
        buckets[point] = 0
        labels.append(point.strftime("%H:00"))

    for created_at in await _collect_message_timestamps(start):
        bucket_time = created_at.replace(minute=0, second=0, microsecond=0)
        if bucket_time in buckets:
            buckets[bucket_time] += 1

    data = [buckets[start + timedelta(hours=idx)] for idx in range(total_hours)]
    return HourlyThroughput(hours=labels, data=data)


async def _build_daily_throughput(days: int = 120) -> DailyThroughput:
    total_days = max(7, min(days, 365))
    end_date = _now().date()
    start_date = end_date - timedelta(days=total_days - 1)
    start_time = datetime.combine(start_date, time.min)

    buckets: Dict[str, int] = {}
    for idx in range(total_days):
        value = start_date + timedelta(days=idx)
        buckets[value.isoformat()] = 0

    for created_at in await _collect_message_timestamps(start_time):
        day_key = created_at.date().isoformat()
        if day_key in buckets:
            buckets[day_key] += 1

    series_data = [(key, buckets[key]) for key in sorted(buckets.keys())]
    return DailyThroughput(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        data=series_data,
    )


def _model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


async def get_bot_info(bot, plugin_calls_today: int, messages_today: int) -> BotInfo:
    bot_id = str(bot.self_id)
    await _mark_bot_connected(bot_id)

    platform = await get_platform(bot)
    group_count = await get_group_list(bot, True)
    friend_count = await get_friend_list(bot)

    nickname = None
    if platform.lower() == "onebot":
        try:
            login_info = await bot.get_login_info()
            nickname = login_info.get("nickname")
        except Exception:
            nickname = None

    connected_at, uptime = await _get_connection_snapshot(bot_id)
    return BotInfo(
        id=bot_id,
        platform=platform,
        group_count=group_count,
        friend_count=friend_count,
        nickname=nickname,
        plugin_calls_today=plugin_calls_today,
        messages_today=messages_today,
        connected_date=connected_at.strftime("%Y-%m-%d"),
        uptime=uptime,
    )


async def _collect_all_bots_info() -> List[BotInfo]:
    bots = nonebot.get_bots()
    plugin_calls_today, messages_today = await _get_today_metrics()
    result: List[BotInfo] = []
    for _, bot in bots.items():
        bot_info = await get_bot_info(bot, plugin_calls_today, messages_today)
        result.append(bot_info)
    return result


async def _collect_connection_logs(limit: int = 20) -> List[ConnectionLog]:
    logs_limit = max(1, min(limit, 200))
    for bot_id in nonebot.get_bots().keys():
        await _mark_bot_connected(str(bot_id))

    async with _STATE_LOCK:
        recent_events = list(_CONNECTION_LOGS)[-logs_limit:]
        recent_events.reverse()
        if recent_events:
            logs: List[ConnectionLog] = []
            for item in recent_events:
                if item.event_type == "connected":
                    duration_text = "连接建立"
                elif item.duration_seconds is None:
                    duration_text = "连接断开"
                else:
                    duration_text = _format_duration(item.duration_seconds)
                logs.append(
                    ConnectionLog(
                        date=_format_datetime(item.occurred_at),
                        account=item.account,
                        duration=duration_text,
                    )
                )
            return logs

        states_snapshot = dict(_CONNECTION_STATES)

    now = _now()
    fallback: List[ConnectionLog] = []
    for account, state in states_snapshot.items():
        if not state.online:
            continue
        uptime_seconds = int((now - state.connected_at).total_seconds())
        fallback.append(
            ConnectionLog(
                date=_format_datetime(state.connected_at),
                account=account,
                duration=_format_duration(uptime_seconds),
            )
        )
    fallback.sort(key=lambda item: item.date, reverse=True)
    return fallback[:logs_limit]


@router.get("/bot-info", response_model=List[BotInfo])
async def get_all_bots_info():
    return await _collect_all_bots_info()


@router.get("/bot-connections", response_model=List[ConnectionLog])
async def get_connection_logs(limit: int = Query(20, ge=1, le=200)):
    return await _collect_connection_logs(limit=limit)


@router.get("/chat-throughput/hourly", response_model=HourlyThroughput)
async def get_chat_throughput_hourly(hours: int = Query(24, ge=1, le=24)):
    return await _build_hourly_throughput(hours=hours)


@router.get("/chat-throughput/daily", response_model=DailyThroughput)
async def get_chat_throughput_daily(days: int = Query(120, ge=7, le=365)):
    return await _build_daily_throughput(days=days)


@router.get("/stream")
async def stream_dashboard_updates(interval_seconds: int = Query(5, ge=2, le=60)):
    async def event_generator():
        try:
            while True:
                bots = await _collect_all_bots_info()
                connections = await _collect_connection_logs(limit=20)
                hourly = await _build_hourly_throughput(hours=24)
                daily = await _build_daily_throughput(days=120)

                payload = {
                    "bots": [_model_to_dict(item) for item in bots],
                    "connections": [_model_to_dict(item) for item in connections],
                    "throughput": {
                        "hourly": _model_to_dict(hourly),
                        "daily": _model_to_dict(daily),
                    },
                }
                data = json.dumps(payload, ensure_ascii=False)
                yield f"event: dashboard_update\ndata: {data}\n\n"
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
