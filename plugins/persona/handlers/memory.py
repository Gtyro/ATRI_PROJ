import logging
from nonebot import on_message, on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.exception import MatcherException
from nonebot.typing import T_State

from ..psstate import is_enabled
from .. import psstate
# 记忆查询命令
memories = on_command("记得", aliases={"回忆", "想起"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@memories.handle()
async def handle_memories(bot: Bot, event: Event, state: T_State):
    """查询记忆"""
    # 如果系统未启用，返回错误信息
    try:
        if not is_enabled():
            await memories.finish("人格系统未启用，请检查配置和日志")

        user_id = event.get_user_id()
        args = str(event.get_message()).strip().split()

        # 格式: 记得 [conv_id] [query]
        if len(args) < 3:
            await memories.finish("命令格式: 记得 [群号/私聊ID] [查询内容]")

        cmd, conv_id, *query_parts = args
        query = " ".join(query_parts)

        # 构建conv_id的格式
        if conv_id.isdigit():
            # 判断是群聊还是私聊
            if await bot.get_group_info(group_id=int(conv_id)):
                conv_id = f"group_{conv_id}"
            else:
                conv_id = f"private_{conv_id}"

        # 使用persona_system的format_memories方法获取格式化的记忆回复
        reply = await psstate.persona_system.format_memories(query, user_id, conv_id)
        await memories.send(reply)
    except MatcherException as e: # finish会正常报出异常
        pass
    except Exception as e:
        logging.error(f"记忆查询异常: {e}")
        await memories.send("回忆过程出现了问题...")

# 添加常驻记忆命令
remember_permanent = on_command("记住", permission=SUPERUSER, priority=5, block=True)
@remember_permanent.handle()
async def handle_remember_permanent(bot: Bot, event: Event):
    """创建常驻节点和记忆对"""
    if not is_enabled():
        await remember_permanent.finish("人格系统未启用，请检查配置和日志")

    command_text = str(event.get_plaintext()).strip()
    parts = command_text.split(maxsplit=4)

    if len(parts) < 4:
        await remember_permanent.finish("命令格式: 记住 [群号/私聊ID] [节点名称] [记忆标题] [记忆内容]")

    _, group_id, node_name, memory_title, memory_content = parts

    # 构建conv_id的格式
    if group_id.isdigit():
        # 判断是群聊还是私聊
        try:
            if await bot.get_group_info(group_id=int(group_id)):
                conv_id = f"group_{group_id}"
            else:
                await remember_permanent.finish("群号格式不正确")
        except Exception:
            await remember_permanent.finish("群号格式不正确")

    try:
        # 直接使用persona_system的方法创建常驻节点和记忆对
        result = await psstate.persona_system.create_permanent_memory(
            conv_id, node_name, memory_title, memory_content
        )

        await remember_permanent.send(f"已创建常驻节点-记忆对:\n节点: {node_name}\n记忆标题: {memory_title}\n记忆内容: {memory_content[:10]}...")
    except Exception as e:
        logging.error(f"创建常驻节点-记忆对异常: {e}")
        await remember_permanent.send("创建常驻节点-记忆对失败，请检查日志")