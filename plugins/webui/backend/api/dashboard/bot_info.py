import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import nonebot
from fastapi import APIRouter
from nonebot_plugin_uninfo import SceneType, Uninfo, get_interface
from nonebot_plugin_uninfo.model import BasicInfo
from pydantic import BaseModel

# 定义API路由
router = APIRouter(
    # 注意：不需要设置prefix，因为已经在dashboard_router中设置了前缀
    tags=["bot_info"],
)


async def get_platform(bot):
    # 从bot实例获取平台信息
    interface = get_interface(bot)
    info: BasicInfo = interface.basic_info()
    return info["scope"]

async def get_group_list(bot, count_only=False) -> list[dict[str, Any]]:
    """
    获取群组列表

    Args:
        bot: 机器人实例
        count_only: 是否只返回群组数量

    Returns:
        群组列表，每个群组包含以下字段:
            - group_id: 群号 不是conv_id
            - group_name: 群名
            - group_remark: 群备注
            - member_count: 成员数量
            - max_member_count: 最大成员数量
    """
    # 尝试获取群组列表
    interface = get_interface(bot)
    scenes = await interface.get_scenes(SceneType.GROUP)
    try:
        if hasattr(bot, "get_group_list"):
            groups = await bot.get_group_list()
            return len(groups) if count_only else groups
    except Exception:
        pass
    return 0 if count_only else []

async def get_friend_list(bot):
    # 尝试获取好友列表
    try:
        if hasattr(bot, "get_friend_list"):
            friends = await bot.get_friend_list()
            return len(friends)
    except Exception:
        pass
    return 0

# 定义机器人信息模型
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

# 获取单个机器人的信息
async def get_bot_info(bot) -> BotInfo:
    bot_id = "unknown"
    platform = "unknown"
    group_count = 0
    friend_count = 0
    nickname = None

    # 获取机器人ID
    bot_id = bot.self_id

    # 获取平台
    platform = await get_platform(bot)

    # 获取群组数量
    group_count = await get_group_list(bot, True)

    # 获取好友数量
    friend_count = await get_friend_list(bot)

    # 获取昵称（QQ平台）
    if platform.lower() == "onebot":
        try:
            login_info = await bot.get_login_info()
            nickname = login_info.get("nickname", None)
        except Exception:
            pass

    # 生成随机数据（临时）
    plugin_calls = random.randint(100, 1000)
    messages = random.randint(500, 5000)

    # 连接日期和运行时间（临时）
    connected_date = datetime.now().strftime("%Y-%m-%d")
    hours = random.randint(1, 24)
    minutes = random.randint(0, 59)
    uptime = f"{hours}小时{minutes}分钟"

    return BotInfo(
        id=bot_id,
        platform=platform,
        group_count=group_count,
        friend_count=friend_count,
        nickname=nickname,
        plugin_calls_today=plugin_calls,
        messages_today=messages,
        connected_date=connected_date,
        uptime=uptime
    )

# 获取所有机器人信息的API端点
@router.get("/bot-info", response_model=List[BotInfo])
async def get_all_bots_info():
    result = []
    bots = nonebot.get_bots()

    for bot_id, bot in bots.items():
        bot_info = await get_bot_info(bot)
        result.append(bot_info)

    return result

# 获取连接日志的模型
class ConnectionLog(BaseModel):
    date: str
    account: str
    duration: str

# 获取连接日志的API端点（临时返回模拟数据）
@router.get("/bot-connections", response_model=List[ConnectionLog])
async def get_connection_logs():
    logs = []
    today = datetime.now()

    # 生成模拟数据
    for i in range(5):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        account = f"bot_{random.randint(1000, 9999)}"
        hours = random.randint(1, 24)
        minutes = random.randint(0, 59)
        duration = f"{hours}小时{minutes}分钟"

        logs.append(ConnectionLog(
            date=date,
            account=account,
            duration=duration
        ))

    return logs 