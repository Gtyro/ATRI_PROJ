from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from .weather import weather

__plugin_meta__ = PluginMetadata(
    name="天气查询",
    description="基于高德地图API的天气查询插件",
    usage="天气 [城市名]",
    extra={
        "author": "User",
        "version": "1.0.0",
    },
)

driver = get_driver()

@driver.on_startup
async def _():
    # 在这里可以进行插件启动时的初始化操作
    pass 