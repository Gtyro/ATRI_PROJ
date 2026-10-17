"""统一限制私聊消息的功能入口。"""

from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import PrivateMessageEvent
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata


__plugin_meta__ = PluginMetadata(
    name="私聊访问控制",
    description="普通用户私聊保持静默，超级用户私聊进入功能处理",
    usage="自动生效",
    type="application",
    supported_adapters={"~onebot.v11"},
    extra={"policy": {"manageable": False, "default_enabled": True, "core": True}},
)


@event_preprocessor
async def enforce_private_access(bot: Bot, event: Event) -> None:
    if isinstance(event, PrivateMessageEvent) and not await SUPERUSER(bot, event):
        raise IgnoredException("普通用户私聊不处理")
