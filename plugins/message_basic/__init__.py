from nonebot.plugin import PluginMetadata

from . import handlers, models

__plugin_meta__ = PluginMetadata(
    name="基础消息",
    description="记录和统计基础消息数据",
    usage="消息概览",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

__all__ = ["models", "handlers"]
