from nonebot import get_driver, require
from nonebot.plugin import PluginMetadata

from .guard import setup_scheduler

require("db_core")

__plugin_meta__ = PluginMetadata(
    name="群活跃度管理",
    description="根据群组近24小时活跃度自动关闭指定插件",
    usage="自动运行，无需手动使用",
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

driver = get_driver()


@driver.on_startup
async def _():
    setup_scheduler()
