"""
人格系统NoneBot插件 - 提供智能记忆和自然对话功能

该模块负责将Persona系统集成到NoneBot机器人中，提供：
1. 记忆管理：自动记录对话内容并分析话题
2. 记忆检索：支持用户查询过去的交流内容
3. 智能对话：根据上下文自主进行对话
4. 定期维护：自动执行记忆衰减和整理
"""

import random
import asyncio
import logging

from nonebot import on_message, on_command, get_driver
from nonebot import require
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_alconna.uniseg import UniMessage, MsgTarget, Target, SupportScope

from .core import PersonaSystem
from .psstate import is_enabled, persona_system
from . import psstate
from .handlers import *

# 获取NoneBot驱动器
driver = get_driver()


# 初始化人格系统
try:
    psstate.persona_system = PersonaSystem(
        db_path="data/persona.db",
        config_path="data/persona.yaml"
    )
except Exception as e:
    logging.error(f"人格系统初始化失败: {e}")
    psstate.persona_system = None


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
    if psstate.persona_system:
        try:
            # 初始化数据库和组件
            await psstate.persona_system.initialize(reply_callback=persona_callback)
            psstate.PERSONA_SYSTEM_ENABLED = True
            logging.info("人格系统初始化成功")
        except Exception as e:
            logging.error(f"人格系统初始化失败，功能将被禁用: {e}", exc_info=True)

@driver.on_shutdown
async def shutdown_persona_system():
    if psstate.persona_system and is_enabled():
        try:
            await psstate.persona_system.close()
            logging.info("人格系统已关闭")
        except Exception as e:
            logging.error(f"人格系统关闭失败: {e}")

# 设置定时维护任务
@driver.on_startup
async def start_scheduler():
    if is_enabled():
        # 每30分钟执行一次维护
        @scheduler.scheduled_job("interval", minutes=30)
        async def _():
            """定时执行维护任务"""
            try:
                logging.info("开始执行定时维护任务")
                await psstate.persona_system.schedule_maintenance()
                logging.info("定时维护任务完成")
            except Exception as e:
                logging.error(f"定时维护任务异常: {e}")
