"""
人格系统NoneBot插件 - 提供智能记忆和自然对话功能

该模块负责将Persona系统集成到NoneBot机器人中，提供：
1. 记忆管理：自动记录对话内容并分析话题
2. 记忆检索：支持用户查询过去的交流内容
3. 智能对话：根据上下文自主进行对话
4. 定期维护：自动执行记忆衰减和整理
"""

import random
import re
import time
import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from nonebot import on_message, on_command, get_driver
from nonebot import require
require("nonebot_plugin_apscheduler")
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.typing import T_State
from nonebot.permission import SUPERUSER
from nonebot.exception import MatcherException
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import Uninfo
from nonebot.internal.params import Depends
from nonebot_plugin_alconna.uniseg import UniMessage, MsgTarget, Target, SupportScope

from .core import PersonaSystem

# 获取NoneBot驱动器
driver = get_driver()

# 全局变量
persona_system = None
PERSONA_SYSTEM_ENABLED = False

# 初始化人格系统
try:
    persona_system = PersonaSystem(
        db_path="data/persona.db",
        config_path="data/persona.yaml"
    )
except Exception as e:
    logging.error(f"人格系统初始化失败: {e}")
    persona_system = None

def UserName():
    """
    用户名称依赖函数
    """

    async def dependency(user_info: Uninfo):
        return user_info.user.nick or user_info.user.name or ""

    return Depends(dependency)

async def persona_callback(conv_id: str, message_dict: dict) -> None:
    """人格系统自动回复回调函数
    
    Args:
        conv_id: 对话ID（如"group_123456"）
        message_dict: 消息数据，包含回复内容
    """
    try:
        target = Target(id=conv_id.split("_")[1])
        if message_dict:
            reply_content = message_dict["reply_content"]
            
            # 处理回复内容（可能是字符串或列表）
            if isinstance(reply_content, list):
                for reply in reply_content:
                    await UniMessage(reply).send(target)
                    # 多条消息之间添加随机间隔，模拟真人打字速度
                    sleep_time = random.uniform(0.5*len(reply), 1*len(reply))
                    await asyncio.sleep(sleep_time)
            else:
                await UniMessage(reply_content).send(target)
    except Exception as e:
        logging.error(f"生成自动回复失败: {e}", exc_info=True)

@driver.on_startup
async def init_persona_system():
    global PERSONA_SYSTEM_ENABLED
    
    if persona_system:
        try:
            # 初始化数据库和组件
            await persona_system.initialize(reply_callback=persona_callback)
            
            PERSONA_SYSTEM_ENABLED = True
            logging.info("人格系统初始化成功")
        except Exception as e:
            logging.error(f"人格系统初始化失败: {e}")

@driver.on_shutdown
async def shutdown_persona_system():
    if persona_system and PERSONA_SYSTEM_ENABLED:
        try:
            await persona_system.close()
            logging.info("人格系统已关闭")
        except Exception as e:
            logging.error(f"人格系统关闭失败: {e}")

# 消息记录器，处理所有接收到的消息
message_recorder = on_message(priority=10)
@message_recorder.handle()
async def record_message(bot: Bot, event: Event, uname: str = UserName()):
    """
    记录所有接收到的消息并处理
    """
    # 如果人格系统未启用，跳过处理
    if not PERSONA_SYSTEM_ENABLED:
        return
        
    user_id = event.get_user_id()
    message = event.get_plaintext()
    
    # 忽略空消息
    if not message.strip():
        return
    
    # 正确区分群聊和私聊
    is_group = isinstance(event, GroupMessageEvent)
    conv_type = "group" if is_group else "private"
    # 群组ID或用户ID
    conv_id = f"{conv_type}_{event.group_id if is_group else user_id}"
    # 尝试获取群组名称
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
        group_name = group_info["group_name"]
    except Exception as e:
        logging.error(f"获取群组名称失败: {e}")
    
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
        reply_dict = await persona_system.process_message(message_data)
        
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

# 状态查询命令
persona_stats = on_command("状态", aliases={"人格状态", "系统状态"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@persona_stats.handle()
async def handle_persona_stats(bot: Bot, event: Event, state: T_State):
    """查询人格系统状态"""
    # 如果系统未启用，返回错误信息
    if not PERSONA_SYSTEM_ENABLED:
        await persona_stats.finish("人格系统未启用，请检查配置和日志")
        
    try:
        # 获取队列统计
        queue_status = await persona_system.get_queue_status()
        stats = queue_status.get("stats", {})
        
        # 生成统计信息
        reply = "人格系统状态:\n"
        reply += f"- 消息总数: {stats.get('total_messages', 0)} 条\n"
        reply += f"- 未处理消息: {stats.get('unprocessed_messages', 0)} 条\n"
        reply += f"- 下次处理: {queue_status.get('next_process_in', 0)} 秒后\n"
        reply += f"- 处理间隔: {queue_status.get('batch_interval', 0)} 秒\n"
        
        # 显示数据库信息
        db_type = "PostgreSQL" if persona_system.config.get("use_postgres") else "SQLite"
        reply += f"- 数据库类型: {db_type}\n"
        
        await persona_stats.send(reply)
    except Exception as e:
        logging.error(f"获取系统状态异常: {e}")
        await persona_stats.send(f"获取状态信息失败: {str(e)}")

# 强制处理命令
process_now = on_command("处理队列", aliases={"处理消息", "立即处理"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@process_now.handle()
async def handle_process_now(bot: Bot, event: Event, state: T_State):
    """强制立即处理消息"""
    # 如果系统未启用，返回错误信息
    if not PERSONA_SYSTEM_ENABLED:
        await process_now.finish("人格系统未启用，请检查配置和日志")
        return
    
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
            await persona_system.process_conversation(conv_id, "")
        else:
            # 执行维护任务
            await persona_system.schedule_maintenance()
            await process_now.send("消息处理完成")
    except Exception as e:
        logging.error(f"处理消息异常: {e}")
        await process_now.send(f"处理消息失败: {str(e)}")

# 记忆查询命令
memories = on_command("记得", aliases={"回忆", "想起"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@memories.handle()
async def handle_memories(bot: Bot, event: Event, state: T_State):
    """查询记忆"""
    # 如果系统未启用，返回错误信息
    try:
        if not PERSONA_SYSTEM_ENABLED:
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
        reply = await persona_system.format_memories(query, user_id, conv_id)
        await memories.send(reply)
    except MatcherException as e: # finish会正常报出异常
        pass
    except Exception as e:
        logging.error(f"记忆查询异常: {e}")
        await memories.send("回忆过程出现了问题...")

# 添加常驻记忆命令
remember_permanent = on_command("牢记", permission=SUPERUSER, priority=5, block=True)
@remember_permanent.handle()
async def handle_remember_permanent(bot: Bot, event: Event):
    """创建常驻节点和记忆对"""
    if not PERSONA_SYSTEM_ENABLED:
        await remember_permanent.finish("人格系统未启用，请检查配置和日志")
        
    command_text = str(event.get_plaintext()).strip()
    parts = command_text.split(maxsplit=4)
    
    if len(parts) < 4:
        await remember_permanent.finish("命令格式: 牢记 [群号/私聊ID] [节点名称] [记忆标题] [记忆内容]")
        
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
        result = await persona_system.create_permanent_memory(
            conv_id, node_name, memory_title, memory_content
        )
        
        await remember_permanent.send(f"已创建常驻节点-记忆对:\n节点: {node_name}\n记忆标题: {memory_title}\n记忆内容: {memory_content[:10]}...")
    except Exception as e:
        logging.error(f"创建常驻节点-记忆对异常: {e}")
        await remember_permanent.send("创建常驻节点-记忆对失败，请检查日志")

# 设置定时维护任务
@driver.on_startup
async def start_scheduler():
    if PERSONA_SYSTEM_ENABLED:
        # 每30分钟执行一次维护
        @scheduler.scheduled_job("interval", minutes=30)
        async def _():
            """定时执行维护任务"""
            try:
                logging.info("开始执行定时维护任务")
                await persona_system.schedule_maintenance()
                logging.info("定时维护任务完成")
            except Exception as e:
                logging.error(f"定时维护任务异常: {e}")

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
        config = await persona_system.group_config.get_config(
            gid=f"group_{group_id}",
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

# 设置拟人测试指令
test_persona = on_command("测试", aliases={"测试人格"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@test_persona.handle()
async def handle_test_persona(bot: Bot, event: Event):
    """测试拟人回复，对某个群组进行模拟处理，返回回复内容给超级用户"""
    # 如果系统未启用，返回错误信息
    if not PERSONA_SYSTEM_ENABLED:
        await test_persona.finish("人格系统未启用，请检查配置和日志")

    # 解析参数获取群号
    args = str(event.get_plaintext()).strip().split()
    if len(args) != 2:
        await test_persona.finish("格式错误，正确格式：测试 [群号]")

    group_id = args[1]
    if not group_id.isdigit():
        await test_persona.finish("群号格式不正确")
    
    # 构造会话ID
    conv_id = f"group_{group_id}"
    
    try:
        # 调用simulate_reply生成回复
        await test_persona.send(f"正在为群 {group_id} 生成模拟回复...")
        reply_data = await persona_system.simulate_reply(conv_id)
        
        # 处理回复结果
        if reply_data and "reply_content" in reply_data:
            reply_content = reply_data["reply_content"]
            if reply_content:
                await test_persona.send(reply_content)
            else:
                await test_persona.finish("生成的回复内容为空")
        else:
            await test_persona.finish("模拟回复失败，请检查日志")
    except Exception as e:
        logging.error(f"测试人格回复异常: {e}")
        await test_persona.finish(f"模拟回复出错: {str(e)}")
