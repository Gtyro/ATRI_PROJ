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
from nonebot_plugin_uninfo import Uninfo
from nonebot.internal.params import Depends

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

def UserName():
    """
    用户名称
    """

    async def dependency(user_info: Uninfo):
        return user_info.user.nick or user_info.user.name or ""

    return Depends(dependency)

# 自动回复回调函数
async def memory_callback(group_id: str, topic_data: dict) -> str:
    """记忆系统自动回复回调函数
    
    Args:
        group_id: 群组ID
        topic_data: 话题数据，包含消息历史和实体信息
        
    Returns:
        生成的回复内容（字符串）
    """
    # 检查AI处理器和bot信息
    if not ai_processor:
        logging.warning("AI处理器未初始化，无法生成自动回复")
        return None
        
    # 获取该群组的bot信息
    bot_info = _latest_bots.get(f"group_{group_id}")
    if not bot_info:
        logging.warning(f"未找到群组 {group_id} 的bot信息，无法发送自动回复")
        return None
        
    bot, is_group = bot_info
    
    try:
        # 从话题数据中提取相关信息
        topic_name = topic_data.get("topic", "未知话题")
        entities = topic_data.get("entities", [])
        messages = topic_data.get("messages", [])
        related_users = topic_data.get("related_users", [])
        last_user_id = topic_data.get("last_user_id")
        is_tome = topic_data.get("is_tome", False)  # 是否为直接@机器人的话题
        
        # 如果是直接@机器人的话题，不进行自动回复
        # 这些话题会由handle_sync_reply处理
        if is_tome:
            logging.info(f"话题 '{topic_name}' 是直接@机器人的对话，跳过自动回复")
            return None
        
        logging.info(f"生成对话题 '{topic_name}' 的自动回复，实体: {entities}，相关用户: {related_users}")
        
        # 准备历史消息 - 使用话题中的消息而不是从Memory获取
        history_messages = []
        
        # 添加相关消息作为历史
        for idx, msg in enumerate(messages):
            # 消息格式通常是 "用户名: 内容"
            if ":" in msg:
                name, content = msg.split(":", 1)
                history_messages.append({
                    "role": "user",
                    "content": f"[{name}]: {content.strip()}"
                })
                logging.debug(f"添加消息历史 {idx+1}: {name} - {content[:20]}...")
            else:
                # 格式不符合预期，直接使用整个消息
                history_messages.append({
                    "role": "user", 
                    "content": msg
                })
        
        # 添加提示信息，引导AI关注当前话题
        prompt = f"请针对'{topic_name}'这个话题，基于上述对话生成一个自然、有帮助的回复。"
        if entities:
            entity_str = "、".join(entities[:3])
            prompt += f" 请特别关注这些关键概念：{entity_str}。"
        
        # 如果有最后发言的用户，可以引导AI回复该用户
        if last_user_id:
            prompt += f" 请考虑回复最后发言的用户。"
        
        history_messages.append({
            "role": "user",
            "content": prompt
        })
        
        # 生成回复
        logging.info(f"正在生成对话题 '{topic_name}' 的回复，历史消息数: {len(history_messages)}")
        reply_content = await ai_processor.generate_response(history_messages, temperature=0.7)
        logging.debug(f"生成的回复: {reply_content[:30]}...")
        
        # 发送自动回复
        asyncio.create_task(send_auto_reply(group_id, reply_content))
        
        return reply_content
        
    except Exception as e:
        logging.error(f"生成自动回复失败: {e}", exc_info=True)
        return None

# 启动时初始化数据库
@driver.on_startup
async def init_memory_system():
    global MEMORY_SYSTEM_ENABLED
    
    if memory_system:
        try:
            # 初始化数据库
            await memory_system.initialize()
            
            # 注册自动回复回调
            if ai_processor:
                await memory_system.generate_auto_reply(memory_callback)
                logging.info("已注册记忆系统自动回复回调")
            
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
async def record_message(bot: Bot, event: Event, state: T_State, uname: str = UserName()):
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
    
    # 保存最近的bot和事件类型，用于后续自动回复
    _latest_bots[context] = (bot, is_group)
    
    # 判断消息优先级和直接交互
    is_priority = False
    is_tome = False  # 是否为直接交互（私聊或@机器人）
    
    # 私聊消息或@机器人的消息立即处理，并标记为直接交互
    if not is_group or event.is_tome():
        is_priority = True
        is_tome = True
    
    # 异步处理记忆
    try:
        await memory_system.process_message(
            user_id=user_id, 
            user_name=uname,
            message=message,
            is_tome=event.is_tome(),
            context=context,
            is_priority=is_priority
        )
        
        # 如果是@或私聊，使用同步回复
        if is_tome:
            await handle_sync_reply(bot, event, message, is_group)
    except Exception as e:
        logging.error(f"记忆处理异常: {e}")

# 同步回复处理（替代原handle_ai_reply，用于直接回复@和私聊）
async def handle_sync_reply(bot: Bot, event: Event, message: str, is_group: bool):
    """处理同步回复（直接回复@和私聊消息）"""
    # 如果AI处理器未初始化，跳过回复
    if not ai_processor:
        logging.warning("AI处理器未初始化，无法生成回复")
        return
        
    user_id = event.get_user_id()
    
    try:
        # 获取上下文和历史记录
        if is_group:
            context = f"group_{event.group_id}"
        else:
            context = f"private_{user_id}"
            
        # 从消息队列获取最近的消息（当前消息已经在process_message中添加到队列中）
        history = []
        if is_group:
            # 获取群消息队列
            group_id = event.group_id
            group_messages = await memory_system.storage.get_group_queue_items(group_id, limit=10)
            history = [{"role": "user", "content": f"[{item['user_name']}]: {item['content']}"} for item in group_messages]
        else:
            # 获取私聊消息
            private_messages = await memory_system.storage.get_group_queue_items(user_id, limit=10)
            history = [{"role": "user" if item["user_id"] == user_id else "assistant", "content": item["content"]} for item in private_messages]
            
        # 当前消息已包含在消息队列中，不需要再次添加
        # 如果没有消息，才需要添加（保险措施）
        if not history:
            logging.debug("没有消息，手动添加当前消息")
            history.append({
                "role": "user",
                "content": message
            })
        
        # 生成回复
        logging.info(f"正在生成对 {user_id} 的回复，历史消息数: {len(history)}")
        reply_content = await ai_processor.generate_response(history, temperature=0.7)
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
        
        # 记录回复到消息队列
        bot_id = bot.self_id
        bot_name = "机器人"
        await memory_system.message_queue.add_bot_message(
            message=reply_content,
            context=context,
            in_reply_to=user_id
        )
        logging.info(f"已回复并记录到消息队列")
        
    except Exception as e:
        logging.error(f"同步回复生成失败: {e}", exc_info=True)
        # 回复错误信息
        try:
            if not is_group:
                await bot.send(event, "抱歉，我暂时无法正常回复，可能是AI服务出现了问题。")
        except Exception as send_error:
            logging.error(f"发送错误提示也失败: {send_error}")

# 处理自动回复生成的消息
async def send_auto_reply(group_id: str, reply_content: str):
    """发送自动回复消息
    
    Args:
        group_id: 群组ID
        reply_content: 回复内容
    """
    if not reply_content or not reply_content.strip():
        logging.warning("自动回复内容为空，取消发送")
        return
        
    context = f"group_{group_id}"
    bot_info = _latest_bots.get(context)
    
    if not bot_info:
        logging.warning(f"未找到群组 {group_id} 的bot信息，无法发送自动回复")
        return
        
    bot, is_group = bot_info
    
    try:
        logging.info(f"开始向群组 {group_id} 发送自动回复")
        
        # 分段发送回复
        pattern1 = r'(\(.*?\))'
        pattern2 = r'（.*?）'
        pattern3 = r'([^，。！？（）()\s]+\.+)'
        pattern4 = r'([^，。！？（）()\s]+)'
        split_replies = [''.join(t) for t in re.findall(rf'{pattern1}|{pattern2}|{pattern3}|{pattern4}', reply_content)]
        
        if not split_replies:
            # 如果分割失败，就直接发送整个回复
            split_replies = [reply_content]
            
        send_count = 0
        for reply in split_replies:
            if not reply.strip():
                continue
                
            try:
                if is_group:
                    await bot.send_group_msg(group_id=int(group_id), message=reply)
                else:
                    await bot.send_private_msg(user_id=int(group_id), message=reply)
                    
                send_count += 1
                
                # 模拟人类打字速度的间隔
                sleep_time = random.uniform(0.3*len(reply), 0.8*len(reply))
                await asyncio.sleep(sleep_time)
            except Exception as e:
                logging.error(f"发送自动回复片段失败: {e}")
        
        # 记录回复到消息队列，使其能够被后续处理记住
        await memory_system.message_queue.add_bot_message(
            message=reply_content,
            context=context
        )
        
        logging.info(f"已完成自动回复发送，共 {send_count} 条片段")
    except Exception as e:
        logging.error(f"发送自动回复失败: {e}", exc_info=True)

# 记忆统计指令 - 查看记忆系统状态
memory_stats = on_command("记忆统计", permission=SUPERUSER, rule=to_me(), priority=5, block=True)
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