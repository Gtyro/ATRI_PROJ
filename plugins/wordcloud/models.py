import logging
import uuid
from datetime import datetime, timedelta

from tortoise import Model, fields
from tortoise.expressions import Q

from plugins.message_basic.models import BasicMessage

class WordCloudData(Model):
    """词云数据模型"""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    conv_id = fields.CharField(max_length=50, index=True)  # 会话ID
    date = fields.DateField()  # 日期
    hour = fields.IntField()   # 小时
    word_data = fields.JSONField()  # 词频数据，格式为 [{word: "词", weight: 频率}, ...]
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "wordcloud_data"
        unique_together = (("conv_id", "date", "hour"),)

async def get_messages(conv_id, hours=24):
    """从数据库中获取指定会话和时间段内的消息"""
    time_limit = datetime.now() - timedelta(hours=hours)

    # 获取过去指定小时内的特定会话的所有消息
    messages = await BasicMessage.filter(
        Q(created_at__gte=time_limit) &
        Q(conv_id=conv_id) &
        ~Q(is_bot=True)  # 排除机器人消息
    ).all()

    return messages

async def save_word_cloud_data(word_data, conv_id, date, hour):
    """保存词云数据到数据库"""
    try:
        record, _ = await WordCloudData.update_or_create(
            conv_id=conv_id,
            date=date,
            hour=hour,
            defaults={"word_data": word_data},
        )
        return record
    except Exception as e:
        # 兼容历史重复数据与并发写入：退化为直接更新
        logging.warning(f"词云数据 upsert 回退为 update: {e}")
        await WordCloudData.filter(conv_id=conv_id, date=date, hour=hour).update(word_data=word_data)
        fallback = await (
            WordCloudData.filter(conv_id=conv_id, date=date, hour=hour)
            .order_by("-created_at")
            .first()
        )
        if fallback:
            return fallback
        return await WordCloudData.create(
            conv_id=conv_id,
            date=date,
            hour=hour,
            word_data=word_data,
        )

async def get_latest_word_cloud_data(conv_id):
    """获取指定会话的最新词云数据"""
    return await WordCloudData.filter(conv_id=conv_id).order_by('-date', '-hour').first()

async def get_word_cloud_data(conv_id, date=None, hour=None):
    """获取指定会话、日期和小时的词云数据"""
    if date and hour is not None:
        return await WordCloudData.filter(conv_id=conv_id, date=date, hour=hour).order_by('-created_at').first()
    elif date:
        return await WordCloudData.filter(conv_id=conv_id, date=date).order_by('-hour').first()
    else:
        return await get_latest_word_cloud_data(conv_id)

async def get_all_conversations():
    """获取所有有词云数据的会话ID列表"""
    # 获取所有有词云数据的不同会话ID
    conversations = await WordCloudData.all().distinct().values_list('conv_id', flat=True)

    # 如果没有词云数据，尝试从消息表获取所有会话ID
    if not conversations:
        conversations = await BasicMessage.all().distinct().values_list('conv_id', flat=True)

    return conversations


from plugins.db_core.model_registry import register_model_module

register_model_module("models", "plugins.wordcloud.models")
