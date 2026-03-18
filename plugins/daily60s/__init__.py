from nonebot import get_driver, require
from nonebot.plugin import PluginMetadata

from .daily60s import cleanup_daily_cache, daily60s_cmd, setup_scheduler

require("db_core")

__plugin_meta__ = PluginMetadata(
    name="每日早报",
    description="获取每日60秒早报图片",
    usage="每日早报",
    extra={
        "policy": {
            "manageable": True,
            "default_enabled": False,
        }
    },
)

driver = get_driver()


@driver.on_startup
async def _():
    cleanup_daily_cache()
    setup_scheduler()
