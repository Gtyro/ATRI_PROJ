import asyncio
import logging
import os
import random

from nonebot import get_driver, on_command, on_message
from nonebot.adapters.onebot.v11 import (Bot, Event, GroupMessageEvent,
                                         Message, PrivateMessageEvent)
from nonebot.internal.params import Depends
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot_plugin_uninfo import Uninfo

from .. import psstate
from ..psstate import is_enabled


def UserName():
    """
    用户名称依赖函数
    """

    async def dependency(user_info: Uninfo):
        return user_info.user.nick or user_info.user.name or ""

    return Depends(dependency)

# 消息记录器，处理所有接收到的消息
message_handler = on_message(priority=10)
@message_handler.handle()
async def handle_message(bot: Bot, event: Event, uname: str = UserName()):
    """
    记录所有接收到的消息并处理
    """
    # 如果人格系统未启用，跳过处理
    if not is_enabled():
        return

    user_id = event.get_user_id()
    message = event.get_plaintext() # 目前只处理纯文本消息

    # 忽略空消息
    if not message.strip():
        return

    # 正确区分群聊和私聊
    is_group = isinstance(event, GroupMessageEvent)
    conv_type = "group" if is_group else "private"
    # 群组ID或用户ID
    conv_id = f"{conv_type}_{event.group_id if is_group else user_id}"
    # 尝试获取群组名称
    group_info = await bot.get_group_info(group_id=event.group_id)
    group_name = group_info["group_name"]

    # 判断直接交互（@机器人或私聊）
    is_direct = False
    if event.is_tome() or not is_group:
        is_direct = True

    # 构建消息数据
    message_data = { # 此处有8个字段+自动生成的id和created_at
        "conv_id": conv_id,
        "user_id": user_id,
        "user_name": uname,
        "content": message,
        "is_direct": is_direct,
        "is_bot": False,
        "is_processed": False,
        "extra_data": {}
    }

    # 异步处理消息
    try:
        reply_dict = await psstate.persona_system.process_message(message_data)

        # 如果有回复内容，发送回复
        if reply_dict:
            reply_content = reply_dict["reply_content"]

            if isinstance(reply_content, list):
                for reply in reply_content:
                    await bot.send(event, reply)
                    sleep_time = random.uniform(0.5*len(reply), 1*len(reply))
                    await asyncio.sleep(sleep_time)
            else:
                await bot.send(event, reply_content)
    except Exception as e:
        logging.error(f"消息处理异常: {e}")

parse_history = on_command("解析历史记录", permission=SUPERUSER, priority=5, block=True)
@parse_history.handle()
async def handle_parse_history(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理解析历史记录命令"""
    if not is_enabled():
        await parse_history.finish("人格系统未启用")

    # 获取参数
    arg_list = args.extract_plain_text().strip().split()
    if len(arg_list) < 2:
        await parse_history.finish("参数不足，格式：解析历史记录 群号 文件路径")

    group_id = arg_list[0]
    file_path = " ".join(arg_list[1:])  # 文件路径可能包含空格

    # 验证群是否存在
    try:
        group_info = await bot.get_group_info(group_id=group_id)
        group_name = group_info["group_name"]
    except Exception as e:
        await parse_history.finish(f"获取群信息失败: {e}")
        return

    # 构造会话ID
    conv_id = f"group_{group_id}"

    # 验证文件是否存在
    if not os.path.exists(file_path):
        await parse_history.finish(f"文件不存在: {file_path}")
        return

    # 获取bot ID
    bot_id = bot.self_id

    try:
        # 调用解析函数
        messages = await psstate.persona_system.parse_chat_history(bot_id, file_path, conv_id)
    except Exception as e:
        await parse_history.finish(f"解析消息记录失败: {e}")

    if not messages:
        await parse_history.finish("解析消息记录失败或记录为空")

    # 目前只解析到这一步，后续功能待实现
    await parse_history.finish(f"成功解析消息记录，共 {len(messages)} 条消息\n群名称: {group_name}\n群号: {group_id}")
        