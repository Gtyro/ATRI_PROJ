import logging
import os

from nonebot import get_driver, on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.exception import MatcherException
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State

from .. import psstate
from ..psstate import is_enabled

# 状态查询命令
persona_stats = on_command("队列状态", aliases={"人格状态"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@persona_stats.handle()
async def handle_persona_stats(bot: Bot, event: Event, state: T_State):
    """查询人格系统状态"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        logging.error("人格系统未启用，请检查配置和日志")
        await persona_stats.finish("人格系统未启用，请检查配置和日志")

    # 解析命令参数
    args = str(event.get_plaintext()).strip().split()
    conv_id = None

    # 如果指定了会话ID
    if len(args) > 1:
        group_id = args[1]
        if group_id.isdigit():
            conv_id = f"group_{group_id}"
        else:
            await persona_stats.finish("会话ID格式不正确")

    try:
        # 获取队列统计
        reply = await psstate.persona_system.get_queue_status_reply(conv_id)

        await persona_stats.send(reply)
    except Exception as e:
        logging.error(f"获取系统状态异常: {e}")
        await persona_stats.send(f"获取状态信息失败: {str(e)}")

# 添加切换人格命令
switch_persona = on_command("切换人格", permission=SUPERUSER, priority=5, block=True)
@switch_persona.handle()
async def handle_switch_persona(bot: Bot, event: Event):
    """切换群组的人格配置"""
    args = str(event.get_plaintext()).strip().split()
    if len(args) != 3: # 包括命令本身
        await switch_persona.send(f"输入内容：{args}")
        await switch_persona.finish("格式错误，正确格式：切换人格 [群号] [prompt文件名]")
        return

    group_id, prompt_file = args[1], args[2]
    if not group_id.isdigit():
        await switch_persona.finish("群号格式不正确")
        return

    # 检查文件是否存在
    file_path = os.path.join("data", "persona", prompt_file)
    if not os.path.exists(file_path):
        await switch_persona.finish(f"提示文件 {prompt_file} 不存在")

    # 更新群组配置
    try:
        config = await psstate.persona_system.group_config.get_config(
            gid=group_id,
            plugin_name="persona"
        )
        config.plugin_config["prompt_file"] = file_path
        await config.save()
        await switch_persona.finish(f"已为群 {group_id} 设置人格提示文件为 {prompt_file}")
    except MatcherException as e: # finish会正常报出异常
        pass
    except Exception as e:
        logging.error(f"切换人格配置失败: {e}")
        await switch_persona.finish("配置更新失败，请检查日志")

# 强制处理命令
process_now = on_command("处理队列", aliases={"处理消息", "立即处理"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@process_now.handle()
async def handle_process_now(bot: Bot, event: Event, state: T_State):
    """强制立即处理消息"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        await process_now.finish("人格系统未启用，请检查配置和日志")

    args = str(event.get_plaintext()).strip().split()
    if args:
        await process_now.send(f"开始处理消息... 参数: {args}")
    else:
        await process_now.send("开始处理消息...")

    if len(args) == 2:
        group_id = args[1]

    try:
        if group_id:
            conv_id = f"group_{group_id}"
            await psstate.persona_system.process_conversation(conv_id, "")
        else:
            # 执行维护任务
            await psstate.persona_system.schedule_maintenance()
            await process_now.send("消息处理完成")
    except Exception as e:
        logging.error(f"处理消息异常: {e}")
        await process_now.send(f"处理消息失败: {str(e)}")