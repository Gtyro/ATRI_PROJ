from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from nonebot import get_bots

from .models import (
    get_all_conversations,
    get_word_cloud_data as get_db_word_cloud_data,
)
from .word_analyzer import generate_word_cloud_data, get_word_cloud_data

# 创建路由
router = APIRouter(prefix="/wordcloud")


async def _safe_get_group_list(bot: Any) -> list[dict[str, Any]]:
    try:
        if hasattr(bot, "get_group_list"):
            groups = await bot.get_group_list()
            return groups or []
    except Exception:
        return []
    return []


async def _load_group_name_map() -> dict[str, str]:
    group_map: dict[str, str] = {}
    for bot in get_bots().values():
        groups = await _safe_get_group_list(bot)
        for group in groups:
            group_id = str(group.get("group_id") or group.get("gid") or "")
            if not group_id:
                continue
            group_map[group_id] = str(
                group.get("group_name") or group.get("name") or group_id
            )
    return group_map


def _format_conversation_option(
    conv_id: str,
    group_map: dict[str, str],
) -> dict[str, str]:
    if conv_id.startswith("group_"):
        group_id = conv_id.split("_", 1)[1]
        group_name = group_map.get(group_id, group_id)
        return {"id": conv_id, "label": f"{group_name} ({group_id})"}
    if conv_id.startswith("private_"):
        user_id = conv_id.split("_", 1)[1]
        return {"id": conv_id, "label": f"私聊 {user_id}"}
    return {"id": conv_id, "label": conv_id}


@router.get("/data")
async def get_wordcloud_data(
    conv_id: str = Query(..., description="会话ID"),
    limit: int = Query(None, description="返回的词数量限制"),
    hours: int = Query(None, description="统计最近多少小时的数据"),
    refresh: bool = Query(False, description="是否刷新数据"),
):
    """
    获取词云数据

    参数:
        conv_id: 会话ID
        limit: 返回的词数量限制，默认使用配置中的值
        hours: 统计最近多少小时的数据，默认使用配置中的值
        refresh: 是否强制刷新数据，默认为False

    返回:
        词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    try:
        data = await get_word_cloud_data(
            conv_id,
            limit=limit,
            hours=hours,
            refresh=refresh,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取词云数据失败: {str(e)}")


@router.get("/history")
async def get_wordcloud_history(
    conv_id: str = Query(..., description="会话ID"),
    date: str = Query(..., description="日期，格式为YYYY-MM-DD"),
    hour: int = Query(None, description="小时，0-23，不提供则返回当天最新数据"),
):
    """
    获取历史词云数据

    参数:
        conv_id: 会话ID
        date: 日期，格式为YYYY-MM-DD
        hour: 小时，0-23，不提供则返回当天最新数据

    返回:
        词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        data = await get_db_word_cloud_data(conv_id, date=date_obj, hour=hour)

        if not data:
            return {"success": False, "message": "找不到对应的历史数据"}

        return {"success": True, "data": data.word_data}
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史词云数据失败: {str(e)}")


@router.post("/generate")
async def generate_wordcloud(
    conv_id: str = Query(..., description="会话ID"),
    word_limit: int = Query(None, description="词云中显示的词数量"),
    hours: int = Query(None, description="获取多少小时前的消息"),
):
    """
    手动生成词云数据

    参数:
        conv_id: 会话ID
        word_limit: 词云中显示的词数量，None表示使用配置中的默认值
        hours: 获取多少小时前的消息，None表示使用配置中的默认值

    返回:
        生成的词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    try:
        data = await generate_word_cloud_data(
            conv_id,
            word_limit=word_limit,
            hours=hours,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成词云数据失败: {str(e)}")


@router.get("/conversations")
async def get_conversations():
    """
    获取所有有词云数据的会话ID列表

    返回:
        会话选项列表
    """
    try:
        conv_ids = await get_all_conversations()
        group_map = await _load_group_name_map()
        options = [
            _format_conversation_option(conv_id, group_map)
            for conv_id in conv_ids
        ]
        return {"success": True, "data": options}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")
