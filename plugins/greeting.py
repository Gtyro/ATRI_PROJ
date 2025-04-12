from nonebot import on_command, on_keyword
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, MessageSegment, Message
from nonebot.typing import T_State
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
# 注册一个问候命令处理器（使用命令方式）
greeting_cmd = on_command("你好", aliases={"hello", "hi"}, permission=SUPERUSER, priority=5, block=True)

@greeting_cmd.handle()
async def handle_greeting_cmd(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    # 获取用户名称
    user_id = event.get_user_id()
    
    # 构建回复消息
    reply = Message(f"你好呀，{user_id}！很高兴见到你~")
    
    # 发送回复
    await greeting_cmd.finish(reply)
