import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import nonebot
from nonebot import get_driver, require
from nonebot.plugin import PluginMetadata

from .cleanup import (
    WORDCLOUD_RETENTION_DAYS,
    cleanup_expired_wordcloud_data,
)
from .config import Config

try:
    driver = get_driver()
except ValueError:
    driver = None

if driver is not None:
    require("db_core")  # ORM模型会由db_core插件初始化
    from nonebot_plugin_apscheduler import scheduler

    from src.adapters.nonebot.command_registry import register_auto_feature

    from .backend import register_router
    from .command import wordcloud_cmd  # 导入命令
    from .word_analyzer import generate_word_cloud_data
else:
    scheduler = None

__plugin_meta__ = PluginMetadata(
    name="词云插件",
    description="生成聊天内容词云",
    usage="自动统计聊天内容生成词云",
    config=Config,
    extra={
        "policy": {
            "manageable": True,
            "default_enabled": False,
        }
    },
)

if driver is not None:
    register_auto_feature(
        "词云自动统计",
        role="superuser",
        trigger_type="schedule",
    )

# 创建存储词云数据的目录
DATA_DIR = Path("data/wordcloud")
os.makedirs(DATA_DIR, exist_ok=True)


async def _run_wordcloud_retention_cleanup(context: str) -> None:
    now = datetime.utcnow()
    try:
        deleted_count = await cleanup_expired_wordcloud_data(
            retention_days=WORDCLOUD_RETENTION_DAYS,
            now=now,
        )
        cutoff = now - timedelta(days=WORDCLOUD_RETENTION_DAYS)
        logging.info(
            "词云历史%s清理完成: deleted=%s cutoff=%s",
            context,
            deleted_count,
            cutoff.isoformat(),
        )
    except Exception as exc:
        logging.error("词云历史%s清理异常: %s", context, exc, exc_info=True)


if driver is not None:
    @driver.on_startup
    async def _startup_wordcloud() -> None:
        app = nonebot.get_app()
        register_router(app)
        await _run_wordcloud_retention_cleanup("启动时")

    @scheduler.scheduled_job("cron", hour="*", minute=0)
    async def gen_wordcloud_data():
        """每小时整点执行一次，生成词云数据"""
        from plugins.message_basic.models import BasicMessage

        conv_ids = await BasicMessage.all().distinct().values_list("conv_id", flat=True)

        for conv_id in conv_ids:
            try:
                await generate_word_cloud_data(conv_id)
            except Exception as e:
                nonebot.logger.error(f"为会话 {conv_id} 生成词云数据时出错: {e}")

    @scheduler.scheduled_job(
        "cron",
        hour=4,
        minute=0,
        id="wordcloud_retention_cleanup",
    )
    async def cleanup_wordcloud_history():
        await _run_wordcloud_retention_cleanup("定时")
