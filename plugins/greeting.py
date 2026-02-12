from nonebot import on_keyword
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent, Message,
                                         MessageEvent, MessageSegment)
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me
from nonebot.typing import T_State

from src.adapters.nonebot.command_registry import register_command

# 插件元信息
__plugin_meta__ = PluginMetadata(
    name="问候语",
    description="简单的问候回复",
    usage="你好/hello/hi",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": True,
            "default_enabled": True,
        }
    },
)

# 注册一个问候命令处理器（使用命令方式）
greeting_cmd = register_command(
    "你好",
    aliases={"hello", "hi"},
    role="normal",
    priority=5,
    block=True,
)

@greeting_cmd.handle()
async def handle_greeting_cmd(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    # 获取用户名称
    user_id = event.get_user_id()

    # 构建回复消息
    reply = Message(f"你好呀，{user_id}！很高兴见到你~")

    # 发送回复
    await greeting_cmd.finish(reply)
