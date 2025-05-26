import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path

from tortoise import Model, fields
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from plugins.message_basic.models import BasicMessage

class WordCloudData(Model):
    """词云数据模型"""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    date = fields.DateField()  # 日期
    hour = fields.IntField()   # 小时
    word_data = fields.JSONField()  # 词频数据，格式为 [{word: "词", weight: 频率}, ...]
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "wordcloud_data"

async def get_messages(hours=24):
    """从数据库中获取指定时间段内的消息"""
    time_limit = datetime.now() - timedelta(hours=hours)
    
    # 获取过去指定小时内的所有消息
    messages = await BasicMessage.filter(
        Q(created_at__gte=time_limit) & 
        ~Q(is_bot=True)  # 排除机器人消息
    ).all()
    
    return messages

async def save_word_cloud_data(word_data, date, hour):
    """保存词云数据到数据库"""
    # 检查是否已存在相同日期和小时的数据
    existing = await WordCloudData.filter(date=date, hour=hour).first()
    
    if existing:
        # 更新现有数据
        existing.word_data = word_data
        await existing.save()
        return existing
    else:
        # 创建新数据
        return await WordCloudData.create(
            date=date,
            hour=hour,
            word_data=word_data
        )

async def get_latest_word_cloud_data():
    """获取最新的词云数据"""
    return await WordCloudData.all().order_by('-date', '-hour').first()

async def get_word_cloud_data(date=None, hour=None):
    """获取指定日期和小时的词云数据"""
    if date and hour is not None:
        return await WordCloudData.filter(date=date, hour=hour).first()
    elif date:
        return await WordCloudData.filter(date=date).order_by('-hour').first()
    else:
        return await get_latest_word_cloud_data()

def save_word_data_to_file(word_data, date, hour):
    """将词云数据保存到文件"""
    data_dir = Path("data/wordcloud")
    data_dir.mkdir(exist_ok=True, parents=True)
    
    filename = f"{date.strftime('%m-%d')}-{hour}.json"
    file_path = data_dir / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(word_data, f, ensure_ascii=False, indent=2)
    
    return file_path 