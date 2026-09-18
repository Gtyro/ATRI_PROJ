from nonebot import get_driver
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="ITAD 限免提醒",
    description="每天检查 IsThereAnyDeal 限免活动，并私聊通知超级用户",
    usage="ITAD限免检查",
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

try:
    driver = get_driver()
except ValueError:
    driver = None


if driver is not None:
    from .plugin import setup_scheduler

    @driver.on_startup
    async def _setup_itad_giveaways_scheduler() -> None:
        setup_scheduler()
