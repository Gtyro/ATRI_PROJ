"""
记忆系统NoneBot插件 - 提供记忆相关的交互功能

该模块负责将记忆系统集成到NoneBot机器人中，提供：
1. 记忆管理：自动记录对话内容
2. 记忆检索：支持用户查询过去的交流内容
3. 定期维护：自动执行记忆衰减和整理
"""

import random
import re
import time
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

import os
import asyncio
import logging
import yaml
from datetime import datetime, timedelta

from .core import MemorySystem

# 插件元数据
__plugin_name__ = "记忆系统"
__plugin_usage__ = """
记忆系统 - 让机器人记住与用户的交流内容

指令:
  记得/回忆/想起 [关键词] - 让机器人回忆相关内容
  记忆统计 - 查看记忆系统状态 (仅超级用户)
  处理队列 - 立即处理消息队列 (仅超级用户)
  
必要配置:
  在 data/memory_config.yaml 中设置你的API密钥
"""

# 获取NoneBot驱动器
driver = get_driver()

# 全局变量
memory_system = None
ai_processor = None
MEMORY_SYSTEM_ENABLED = False
# 保存最近的bot实例和群组信息，用于自动回复
_latest_bots = {}  # 格式: {"group_123456": (bot, event_type)}

# 读取数据库配置
config_path = "data/memory_config.yaml"
db_config = {}

if os.path.exists(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            db_config = {
                "use_postgres": config.get("use_postgres", False),
                "postgres_config": config.get("postgres_config", {})
            }
    except Exception as e:
        logging.error(f"读取数据库配置失败: {e}")

# 初始化记忆系统
try:
    memory_system = MemorySystem(
        db_path="data/memory.db", 
        batch_interval=3600,
        use_postgres=db_config.get("use_postgres", False),
        postgres_config=db_config.get("postgres_config")
    )
except Exception as e:
    logging.error(f"记忆系统初始化失败: {e}")
    memory_system = None
    ai_processor = None

def UserName():
    """
    用户名称
    """

    async def dependency(user_info: Uninfo):
        return user_info.user.nick or user_info.user.name or ""

    return Depends(dependency)

async def memory_callback(conv_id: str, message_dict: dict) -> str:
    """记忆系统自动回复回调函数
    
    Args:
        conv_id: 对话ID（如"group_123456"）
        topic_data: 话题数据，包含消息历史和实体信息
        
    Returns:
        生成的回复内容（字符串）
    """
    try:
        target = Target(id = conv_id.split("_", 1)[1])
        if message_dict.get("reply_content"):
            if isinstance(message_dict.get("reply_content"), list):
                for reply in message_dict.get("reply_content"):
                    await UniMessage(reply).send(target)
                    sleep_time = random.uniform(0.5*len(reply), 1*len(reply))
                    await asyncio.sleep(sleep_time)
            else:
                await UniMessage(message_dict.get("reply_content")).send(target)
    except Exception as e:
        logging.error(f"生成自动回复失败: {e}", exc_info=True)
        return None

@driver.on_startup
async def init_memory_system():
    global MEMORY_SYSTEM_ENABLED
    
    if memory_system:
        try:
            # 初始化数据库
            await memory_system.initialize(reply_callback=memory_callback)
            
            MEMORY_SYSTEM_ENABLED = True
            logging.info("记忆系统数据库初始化成功")
        except Exception as e:
            logging.error(f"记忆系统数据库初始化失败: {e}")
            MEMORY_SYSTEM_ENABLED = False

@driver.on_shutdown
async def shutdown_memory_system():
    if memory_system and MEMORY_SYSTEM_ENABLED:
        try:
            await memory_system.close()
            logging.info("记忆系统已关闭")
        except Exception as e:
            logging.error(f"记忆系统关闭失败: {e}")

message_recorder = on_message(priority=10)
@message_recorder.handle()
async def record_message(bot: Bot, event: Event, uname: str = UserName()):
    '''
    记录所有接收到的消息

    bot: Bot 机器人实例,用于发送消息
    event: Event 事件实例,用于获取消息信息
    uname: str 用户昵称,记录到消息队列中
    '''
    # 如果记忆系统未启用，跳过处理
    if not MEMORY_SYSTEM_ENABLED:
        return
        
    user_id = event.get_user_id()
    message = event.get_plaintext()
    
    # 忽略空消息
    if not message.strip():
        logging.warning(f"收到空消息，跳过处理") # 图片消息也会触发这个
        return
    
    # 正确区分群聊和私聊
    is_group = isinstance(event, GroupMessageEvent)
    conv_type = "group" if is_group else "private"
    # 群组ID或用户ID
    conv_id = f"{conv_type}_{event.group_id if is_group else user_id}"
    
    # 保存最近的bot和事件类型，用于后续自动回复
    _latest_bots[conv_id] = (bot, is_group)
    
    # 判断直接交互
    is_direct = False
    
    # @机器人或私聊的消息立即处理，并标记为直接交互
    if event.is_tome() or not is_group:
        is_direct = True
    
    queue_item_dict = {
        "conv_id": conv_id,
        "user_id": user_id,
        "user_name": uname,
        "content": message,
        "is_direct": is_direct,
        "is_me": False,
        "created_at": time.time(),
        "processed": False,
        "metadata": {}
    }

    # 异步处理记忆
    try:
        message_dict = await memory_system.process_message(queue_item_dict)
        if message_dict:
            if isinstance(message_dict.get("reply_content"), list):
                for reply in message_dict.get("reply_content"):
                    await bot.send(event, reply)
                    sleep_time = random.uniform(0.5*len(reply), 1*len(reply))
                    await asyncio.sleep(sleep_time)
            else:
                await bot.send(event, message_dict.get("reply_content"))
    except Exception as e:
        logging.error(f"记忆处理异常: {e}")

memory_stats = on_command("记忆统计", permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@memory_stats.handle()
async def handle_memory_stats(bot: Bot, event: Event, state: T_State):
    # 如果记忆系统未启用，返回错误信息
    if not MEMORY_SYSTEM_ENABLED:
        await memory_stats.finish("记忆系统未启用，请检查配置和日志")
        
    try:
        # 获取队列统计
        queue_status = await memory_system.get_queue_status()
        stats = queue_status["stats"]
        
        # 生成统计信息
        reply = "记忆系统状态:\n"
        reply += f"- 队列消息: {stats['total']} 条\n"
        reply += f"- 下次处理: {queue_status['next_process_in']} 秒后\n"
        reply += f"- 处理间隔: {queue_status['batch_interval']} 秒\n"
        
        # 显示数据库信息
        db_type = "PostgreSQL" if memory_system.use_postgres else "SQLite"
        reply += f"- 数据库类型: {db_type}\n"
        
        await memory_stats.finish(reply)
    except MatcherException:
        raise
    except Exception as e:
        logging.error(f"获取记忆统计异常: {e}")
        await memory_stats.finish(f"获取统计信息失败: {str(e)}")

process_queue = on_command("处理队列", permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@process_queue.handle()
async def handle_process_queue(bot: Bot, event: Event, state: T_State):
    # 如果记忆系统未启用，返回错误信息
    if not MEMORY_SYSTEM_ENABLED:
        await process_queue.finish("记忆系统未启用，请检查配置和日志")
        return
        
    await process_queue.send("开始处理队列...")
    
    try:
        # 处理队列
        count = await memory_system.process_queue()
        await process_queue.finish(f"队列处理完成，处理了 {count} 条消息")
    except MatcherException:
        raise
    except Exception as e:
        logging.error(f"处理队列异常: {e}")
        await process_queue.finish(f"处理队列失败: {str(e)}")

async def scheduled_maintenance():
    """定时执行维护任务"""
    if not MEMORY_SYSTEM_ENABLED or not memory_system:
        return
        
    try:
        await memory_system.schedule_maintenance()
    except MatcherException:
        raise
    except Exception as e:
        logging.error(f"处理队列异常: {e}")

# 设置定时任务
@driver.on_startup
async def start_scheduler():
    # 设置定时任务
    if MEMORY_SYSTEM_ENABLED:
        # 每30分钟执行一次维护
        @scheduler.scheduled_job("interval", minutes=30)
        async def run_maintenance():
            await scheduled_maintenance()

recall = on_command("记得", aliases={"回忆", "想起"}, rule=to_me(), priority=5)
@recall.handle()
async def handle_recall(bot: Bot, event: Event, state: T_State):
    # 如果记忆系统未启用，返回错误信息
    if not MEMORY_SYSTEM_ENABLED:
        await recall.finish("记忆系统未启用，请检查配置和日志")
        return
        
    user_id = event.get_user_id()
    args = str(event.get_message()).strip()
    
    if not args:
        await recall.finish("你想让我回忆什么呢？")
        return
    
    try:
        memories = await memory_system.retrieve_related_memories(args, user_id)
        
        if not memories:
            await recall.finish("我似乎没有关于这方面的记忆...")
            return
            
        # 格式化回复
        reply = "我记得这些内容:\n"
        for i, memory in enumerate(memories, 1):
            content = memory["content"]
            time_str = datetime.fromtimestamp(memory["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            reply += f"{i}. {content} ({time_str})\n"
            
        await recall.finish(reply)
        
    except Exception as e:
        logging.error(f"回忆处理异常: {e}")
        await recall.finish("回忆过程出现了问题...") 