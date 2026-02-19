"""
人格系统NoneBot插件 - 提供智能记忆和自然对话功能

该模块负责将Persona系统集成到NoneBot机器人中，提供：
1. 记忆管理：自动记录对话内容并分析话题
2. 记忆检索：支持用户查询过去的交流内容
3. 智能对话：根据上下文自主进行对话
4. 定期维护：自动执行记忆衰减和整理
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta

from nonebot import get_driver, on_message, require
from nonebot_plugin_alconna.uniseg import Target, UniMessage
from nonebot_plugin_apscheduler import scheduler

from src.infra.db.tortoise.plugin_models import GroupPluginConfig, PluginModuleMetricEvent
from src.adapters.nonebot import assemble_persona_engine
from src.adapters.nonebot.command_registry import register_auto_feature
from src.core.domain import PersonaConfig
from src.core.events import Event, MESSAGE_RECEIVED
from src.core.facade.persona_facade import PersonaFacade
from src.infra.db.tortoise.module_metrics_cleanup import cleanup_expired_module_metric_events

from . import psstate
from .handlers import *
from .psstate import is_enabled

# 使用require机制加载数据库插件
require("db_core")

# 获取NoneBot驱动器
driver = get_driver()


# 初始化人格系统占位（实际装配在启动时完成）
psstate.persona_system = None

register_auto_feature(
    "人格定时维护",
    role="superuser",
    trigger_type="schedule",
)


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
                    reply = str(reply).strip()
                    if not reply:
                        continue
                    await UniMessage(reply).send(target)
                    # 多条消息之间添加随机间隔，模拟真人打字速度
                    sleep_time = random.uniform(0.5*len(reply), 1*len(reply))
                    await asyncio.sleep(sleep_time)
            else:
                reply_content = str(reply_content).strip()
                if not reply_content:
                    return
                await UniMessage(reply_content).send(target)
    except Exception as e:
        logging.error(f"生成自动回复失败: {e}", exc_info=True)


async def _handle_message_event(event: Event) -> None:
    """处理消息事件并交给 Persona 引擎。"""
    if not is_enabled() or not psstate.persona_system:
        return
    payload = event.payload
    if not payload:
        return
    message_data = {
        "conv_id": payload.conv_id,
        "user_id": payload.user_id,
        "user_name": payload.user_name,
        "content": payload.content,
        "is_direct": payload.is_direct,
        "is_bot": payload.is_bot,
        "is_processed": payload.is_processed,
        "metadata": payload.metadata,
    }
    if payload.created_at:
        message_data["created_at"] = payload.created_at
    try:
        await psstate.persona_system.process_message(message_data)
    except Exception as e:
        logging.error(f"消息事件处理异常: {e}", exc_info=True)


def _register_message_subscriber() -> None:
    if psstate.message_subscriber_registered:
        return
    psstate.event_bus.subscribe(MESSAGE_RECEIVED, _handle_message_event)
    psstate.message_subscriber_registered = True

@driver.on_startup
async def init_persona_system():
    try:
        # 模型已由db_core插件集中注册，这里不再单独注册
        persona_config = PersonaConfig.load("data/persona/persona.yaml")
        engine = await assemble_persona_engine(
            config=persona_config,
            group_config=GroupPluginConfig,
            plugin_name="persona",
            reply_callback=persona_callback,
            plugin_policy_service=psstate.plugin_policy_service,
        )
        psstate.persona_system = PersonaFacade(engine)
        await psstate.persona_system.initialize(reply_callback=persona_callback)
        _register_message_subscriber()
        psstate.PERSONA_SYSTEM_ENABLED = True
        logging.debug("人格系统初始化成功")
    except Exception as e:
        logging.error(f"人格系统初始化失败，功能将被禁用: {e}", exc_info=True)
        psstate.persona_system = None
        psstate.PERSONA_SYSTEM_ENABLED = False

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


@scheduler.scheduled_job(
    "cron",
    hour=3,
    minute=0,
    id="persona_module_metrics_retention_cleanup",
)
async def cleanup_module_metric_events() -> None:
    try:
        now = datetime.utcnow()
        deleted_count = await cleanup_expired_module_metric_events(
            PluginModuleMetricEvent,
            retention_days=90,
            now=now,
        )
        cutoff = now - timedelta(days=90)
        logging.info("模块指标定时清理完成: deleted=%s cutoff=%s", deleted_count, cutoff.isoformat())
    except Exception as exc:
        logging.error("模块指标定时清理异常: %s", exc, exc_info=True)
