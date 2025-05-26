import os
import nonebot
from nonebot import require, get_driver
from nonebot.plugin import PluginMetadata
from pathlib import Path

from .models import WordCloudData
from .config import Config
from .word_analyzer import generate_word_cloud_data
from .command import wordcloud_cmd  # 导入命令
from .backend import register_router  # 导入路由注册函数

__plugin_meta__ = PluginMetadata(
    name="词云插件",
    description="生成聊天内容词云",
    usage="自动统计聊天内容生成词云",
    config=Config,
)

driver = get_driver()

# 创建存储词云数据的目录
DATA_DIR = Path("data/wordcloud")
os.makedirs(DATA_DIR, exist_ok=True)

# 暴露API
@driver.on_startup
async def _():
    # 确保词云数据表已创建
    from .models import init_wordcloud_db
    await init_wordcloud_db()
    
    # 获取 FastAPI 实例并注册路由
    from nonebot.drivers.fastapi import Driver
    app = nonebot.get_app()
    register_router(app)

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", hour="*", minute=0)
async def gen_wordcloud_data():
    """每小时整点执行一次，生成词云数据"""
    await generate_word_cloud_data()