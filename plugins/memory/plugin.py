"""
记忆系统NoneBot插件 - 提供记忆相关的交互功能

该模块负责将记忆系统集成到NoneBot机器人中，提供：
1. 记忆管理：自动记录对话内容
2. 记忆检索：支持用户查询过去的交流内容
3. 定期维护：自动执行记忆衰减和整理
"""

import random
import re
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

import os
import asyncio
import logging
import yaml
from datetime import datetime, timedelta

from .core import MemorySystem
from .ai_processor import AIProcessor

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
    
    # 创建AI处理器，用于生成回复
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                ai_processor = AIProcessor(
                    api_key=config.get("api_key"),
                    model=config.get("model", "deepseek-chat"),
                    api_base=config.get("api_base", "https://api.deepseek.com")
                )
        except Exception as e:
            logging.error(f"AI处理器初始化失败: {e}")
            ai_processor = None
    else:
        ai_processor = None
except Exception as e:
    logging.error(f"记忆系统初始化失败: {e}")
    memory_system = None
    ai_processor = None

# 启动时初始化数据库
@driver.on_startup
async def init_memory_system():
    global MEMORY_SYSTEM_ENABLED
    
    if memory_system:
        try:
            # 初始化数据库
            await memory_system.initialize()
            MEMORY_SYSTEM_ENABLED = True
            logging.info("记忆系统数据库初始化成功")
        except Exception as e:
            logging.error(f"记忆系统数据库初始化失败: {e}")
            MEMORY_SYSTEM_ENABLED = False

# 关闭时清理资源
@driver.on_shutdown
async def shutdown_memory_system():
    if memory_system and MEMORY_SYSTEM_ENABLED:
        try:
            await memory_system.close()
            logging.info("记忆系统已关闭")
        except Exception as e:
            logging.error(f"记忆系统关闭失败: {e}")

# 消息处理器 - 记录所有接收到的消息
message_recorder = on_message(priority=10)
@message_recorder.handle()
async def record_message(bot: Bot, event: Event, state: T_State):
    # 如果记忆系统未启用，跳过处理
    if not MEMORY_SYSTEM_ENABLED:
        return
        
    user_id = event.get_user_id()
    message = event.get_plaintext()
    
    # 忽略空消息
    if not message.strip():
        return
    
    # 正确区分群聊和私聊
    is_group = isinstance(event, GroupMessageEvent)
    session_type = "group" if is_group else "private"
    
    # 群ID或用户ID
    group_id = event.group_id if is_group else user_id
    context = f"{session_type}_{group_id}"
    
    # 判断消息优先级
    is_priority = False
    
    # 私聊消息或@机器人的消息立即处理
    if not is_group or event.is_tome():
        is_priority = True
    
    # 异步处理记忆
    try:
        await memory_system.process_message(
            user_id=user_id, 
            message=message, 
            context=context,
            is_priority=is_priority
        )
        
        # 处理智能回复
        await handle_ai_reply(bot, event, message, is_group)
    except Exception as e:
        logging.error(f"记忆处理异常: {e}")

# 智能回复处理
async def handle_ai_reply(bot: Bot, event: Event, message: str, is_group: bool):
    """处理智能回复"""
    # 如果AI处理器未初始化，跳过回复
    if not ai_processor:
        logging.warning("AI处理器未初始化，无法生成回复")
        return
        
    user_id = event.get_user_id()
    
    # 只处理私聊消息或@机器人的群聊消息
    if not (isinstance(event, PrivateMessageEvent) or (is_group and event.is_tome())):
        return
        
    try:
        # 获取历史记录
        history_messages = []
        if isinstance(event, PrivateMessageEvent):
            # 私聊消息：获取该用户历史记录
            logging.debug(f"获取用户 {user_id} 的历史记忆")
            history = await memory_system.storage.get_user_memories(user_id)
            # 只保留最近10条记录
            history = history[:10]
            for item in history:
                role = "user" if item["user_id"] == user_id else "assistant"
                history_messages.append({
                    "role": role,
                    "content": item["content"]
                })
                logging.debug(f"添加历史记忆: [{role}] {item['content'][:30]}...")
        else:
            # 群聊消息：获取该群最近10条消息
            group_id = event.group_id
            context = f"group_{group_id}"
            logging.debug(f"获取群 {group_id} 的历史记忆")
            history = await memory_system.storage.get_context_memories(context, limit=10)
            for item in history:
                # 群聊中都作为用户角色，但添加用户ID标识
                history_messages.append({
                    "role": "user",
                    "content": f"[{item['user_id']}]: {item['content']}"
                })
                logging.debug(f"添加群记忆: [{item['user_id']}] {item['content'][:30]}...")
        
        # 添加当前消息
        history_messages.append({
            "role": "user",
            "content": message
        })
        logging.debug(f"添加当前消息: {message[:30]}...")
        
        # 生成回复
        logging.info(f"正在生成对 {user_id} 的回复，历史消息数: {len(history_messages)}")
        reply_content = await ai_processor.generate_response(history_messages, temperature=0.7)
        logging.debug(f"生成的回复: {reply_content[:30]}...")
        
        # 发送回复
        pattern1 = r'(\(.*?\))'
        pattern2 = r'（.*?）'
        pattern3 = r'([^，。！？（）()\s]+\.+)'
        pattern4 = r'([^，。！？（）()\s]+)'
        split_replies = [''.join(t) for t in re.findall(rf'{pattern1}|{pattern2}|{pattern3}|{pattern4}', reply_content)]
        for reply in split_replies:
            await bot.send(event, reply)
            sleep_time = random.uniform(0.5*len(reply), 1*len(reply))
            await asyncio.sleep(sleep_time)
        
        # 记录回复到记忆系统
        bot_id = bot.self_id
        context = f"group_{event.group_id}" if is_group else f"private_{user_id}"
        await memory_system.process_message(
            user_id=bot_id,
            message=reply_content,
            context=context,
            is_priority=True
        )
        logging.info(f"已回复并记录到记忆系统")
        
    except Exception as e:
        logging.error(f"AI回复生成失败: {e}", exc_info=True)
        # 回复错误信息
        try:
            await bot.send(event, "抱歉，我暂时无法正常回复，可能是AI服务出现了问题。")
        except Exception as send_error:
            logging.error(f"发送错误提示也失败: {send_error}")

# 回忆指令 - 让机器人回忆相关内容
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

# 记忆统计指令 - 查看记忆系统状态
memory_stats = on_command("记忆统计", permission=SUPERUSER, priority=5, block=True)
@memory_stats.handle()
async def handle_memory_stats(bot: Bot, event: Event, state: T_State):
    # 如果记忆系统未启用，返回错误信息
    if not MEMORY_SYSTEM_ENABLED:
        await memory_stats.finish("记忆系统未启用，请检查配置和日志")
        return
        
    try:
        # 获取队列统计
        queue_status = await memory_system.get_queue_status()
        stats = queue_status["stats"]
        
        # 生成统计信息
        reply = "记忆系统状态:\n"
        reply += f"- 队列消息: {stats['total']} 条\n"
        reply += f"  - 优先消息: {stats['priority']} 条\n"
        reply += f"  - 普通消息: {stats['normal']} 条\n"
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

# 处理队列指令 - 立即处理消息队列
process_queue = on_command("处理队列", permission=SUPERUSER, priority=5, block=True)
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
    except Exception as e:
        logging.error(f"处理队列异常: {e}")
        await process_queue.finish(f"处理队列失败: {str(e)}")

# 定时维护
async def scheduled_maintenance():
    """定时执行维护任务"""
    if not MEMORY_SYSTEM_ENABLED or not memory_system:
        return
        
    try:
        await memory_system.schedule_maintenance()
        logging.info("计划维护完成")
    except Exception as e:
        logging.error(f"计划维护失败: {e}")

# 设置定时任务
@driver.on_startup
async def start_scheduler():
    # 检查配置文件是否存在
    if not os.path.exists("data"):
        os.makedirs("data")
        
    if not os.path.exists("data/memory_config.yaml"):
        default_config = {
            "api_key": "your_api_key_here",
            "model": "deepseek-chat",
            "api_base": "https://api.deepseek.com",
            "use_postgres": False,
            "postgres_config": {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "password",
                "database": "memories"
            }
        }
        
        try:
            with open("data/memory_config.yaml", 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            logging.info("已创建默认配置文件")
        except Exception as e:
            logging.error(f"创建配置文件失败: {e}")
    
    # 设置定时任务
    if MEMORY_SYSTEM_ENABLED:
        # 每30分钟执行一次维护
        @scheduler.scheduled_job("interval", minutes=30)
        async def run_maintenance():
            await scheduled_maintenance() 