from datetime import datetime
from fastapi import APIRouter, Query, HTTPException

from .config import Config
from .word_analyzer import get_word_cloud_data, generate_word_cloud_data
from .models import get_word_cloud_data as get_db_word_cloud_data

# 获取配置
config = Config()

# 创建路由
router = APIRouter(prefix="/wordcloud")

@router.get("/data")
async def get_wordcloud_data(
    limit: int = Query(None, description="返回的词数量限制"),
    refresh: bool = Query(False, description="是否刷新数据")
):
    """
    获取词云数据
    
    参数:
        limit: 返回的词数量限制，默认使用配置中的值
        refresh: 是否强制刷新数据，默认为False
    
    返回:
        词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    try:
        if refresh:
            # 强制刷新，重新生成数据
            data = await generate_word_cloud_data(word_limit=limit)
        else:
            # 获取缓存数据
            data = await get_word_cloud_data(limit=limit)
        
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取词云数据失败: {str(e)}")

@router.get("/history")
async def get_wordcloud_history(
    date: str = Query(..., description="日期，格式为YYYY-MM-DD"),
    hour: int = Query(None, description="小时，0-23，不提供则返回当天最新数据")
):
    """
    获取历史词云数据
    
    参数:
        date: 日期，格式为YYYY-MM-DD
        hour: 小时，0-23，不提供则返回当天最新数据
    
    返回:
        词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    try:
        # 解析日期
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        
        # 获取数据
        data = await get_db_word_cloud_data(date=date_obj, hour=hour)
        
        if not data:
            return {"success": False, "message": "找不到对应的历史数据"}
        
        return {"success": True, "data": data.word_data}
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史词云数据失败: {str(e)}")

@router.post("/generate")
async def generate_wordcloud(
    word_limit: int = Query(None, description="词云中显示的词数量"),
    hours: int = Query(None, description="获取多少小时前的消息")
):
    """
    手动生成词云数据
    
    参数:
        word_limit: 词云中显示的词数量，None表示使用配置中的默认值
        hours: 获取多少小时前的消息，None表示使用配置中的默认值
    
    返回:
        生成的词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    try:
        data = await generate_word_cloud_data(word_limit=word_limit, hours=hours)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成词云数据失败: {str(e)}") 