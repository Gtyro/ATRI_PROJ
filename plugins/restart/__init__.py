"""
ATRI 自动重启插件
功能：
1. 每日凌晨4点自动重启
2. 超级用户手动重启命令
3. 安全的重启流程管理
"""

import asyncio
import logging
from datetime import datetime

from arclet.alconna import Args, Arparma, MultiVar
from nonebot import get_driver, require
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me
from nonebot_plugin_apscheduler import scheduler

from .restart_manager import RestartManager
from .config import RestartConfig
from src.adapters.nonebot.command_registry import register_alconna, register_auto_feature, register_command
from src.infra.logging.restart_diagnostics import summarize_issue_status

# 声明依赖
require("db_core")

__plugin_meta__ = PluginMetadata(
    name="自动重启",
    description="机器人自动重启与手动重启管理",
    usage="管理员可使用 重启 / 重启状态 / 重启配置 等命令",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
        }
    },
)

# 获取驱动器
driver = get_driver()

# 初始化重启管理器
restart_manager = None
restart_config = None

register_auto_feature(
    "自动重启任务",
    role="superuser",
    trigger_type="schedule",
)
register_auto_feature(
    "重启通知",
    role="superuser",
    trigger_type="event",
)

@driver.on_startup
async def init_restart_system():
    """初始化重启系统"""
    global restart_manager, restart_config

    try:
        restart_config = RestartConfig()
        restart_manager = RestartManager(restart_config)

        # 初始化管理器
        await restart_manager.initialize()

        logging.info("重启系统初始化成功")

        # 设置定时重启任务
        setup_scheduled_restart()

        # 注意：不在这里发送重启通知，因为机器人可能还未连接

    except Exception as e:
        logging.error(f"重启系统初始化失败: {e}")

# 监听机器人连接事件，用于发送重启完成通知
@driver.on_bot_connect
async def on_bot_connect(bot: Bot):
    """机器人连接成功时发送重启通知"""
    global restart_manager

    if restart_manager:
        try:
            # 检查并发送重启完成通知
            await restart_manager.check_and_send_restart_notification()
        except Exception as e:
            logging.error(f"发送重启通知失败: {e}")

def setup_scheduled_restart():
    """设置定时重启任务"""
    if not restart_config.auto_restart_enabled:
        logging.info("自动重启功能已禁用")
        return

    restart_time = restart_config.restart_time
    hour, minute = map(int, restart_time.split(':'))

    @scheduler.scheduled_job("cron", hour=hour, minute=minute, id="daily_restart")
    async def daily_restart():
        """每日定时重启任务"""
        try:
            logging.info(f"开始执行定时重启任务 - {datetime.now()}")
            await restart_manager.perform_restart(reason="定时重启")
        except Exception as e:
            logging.error(f"定时重启任务执行失败: {e}")

    logging.info(f"已设置定时重启任务：每日 {restart_time}")

# 手动重启命令
restart_cmd = register_command(
    "重启",
    aliases={"restart", "重启机器人", "重新启动"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=1,
    block=True,
    description="手动触发机器人重启",
    usage="重启",
    examples=["重启"],
)

@restart_cmd.handle()
async def handle_restart(bot: Bot, event: MessageEvent):
    """处理手动重启命令"""
    if not restart_manager:
        await restart_cmd.finish("重启系统未初始化，请检查配置")

    user_id = event.get_user_id()

    try:
        await restart_cmd.send("🔄 准备重启机器人...")

        # 执行重启
        await restart_manager.perform_restart(
            reason=f"手动重启 (用户: {user_id})",
            delay_seconds=3  # 给用户3秒时间看到回复
        )

    except Exception as e:
        logging.error(f"手动重启失败: {e}")
        await restart_cmd.finish(f"❌ 重启失败: {str(e)}")

# 重启状态查询命令
restart_status_cmd = register_command(
    "重启状态",
    aliases={"restart_status", "重启信息"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=1,
    block=True,
    description="查看自动重启与最近重启状态",
    usage="重启状态",
    examples=["重启状态"],
)

@restart_status_cmd.handle()
async def handle_restart_status(bot: Bot, event: MessageEvent):
    """查询重启系统状态"""
    if not restart_manager or not restart_config:
        await restart_status_cmd.finish("重启系统未初始化")

    status_info = await restart_manager.get_status_info()
    log_diagnostics = status_info.get("log_diagnostics", {})
    startup_summary = log_diagnostics.get("startup_summary", {})
    previous_summary = log_diagnostics.get("previous_log_summary", {})
    startup_samples = tuple(startup_summary.get("sample_messages", ()) or ())
    startup_sample_line = "无"
    if startup_samples:
        startup_sample_line = " / ".join(str(message) for message in startup_samples[:2])

    # 构建状态文本
    status_text = f"""
🔄 重启系统状态
------------------------
🔹 自动重启: {'✅ 已启用' if restart_config.auto_restart_enabled else '❌ 已禁用'}
🔹 重启时间: {restart_config.restart_time}
🔹 启动脚本: {restart_config.startup_script_path}
🔹 重启通知: {'✅ 已启用' if restart_config.restart_notification_enabled else '❌ 已禁用'}

📊 运行状态
------------------------
🔹 最后启动: {status_info.get('last_startup', '未知')}
🔹 最后重启: {status_info.get('last_restart', '从未重启')}
🔹 重启原因: {status_info.get('restart_reason', '无')}
🔹 运行时长: {status_info.get('uptime', '未知')}
🔹 重启次数: {status_info.get('restart_count', 0)}

📋 启动诊断
------------------------
🔹 启动日志: {log_diagnostics.get('current_log', '未找到')}
🔹 启动状态: {summarize_issue_status(int(startup_summary.get('errors', 0)), int(startup_summary.get('warnings', 0)), str(startup_summary.get('status', '')))}
🔹 问题样例: {startup_sample_line}

📚 上一份日志
------------------------
🔹 日志文件: {log_diagnostics.get('previous_log', '未找到')}
🔹 ERROR: {previous_summary.get('errors', 0)}
🔹 WARNING: {previous_summary.get('warnings', 0)}
""".strip()

    # 如果启用了通知，显示通知状态
    if restart_config.restart_notification_enabled:
        notification_sent = status_info.get('notification_sent', False)
        notification_time = status_info.get('notification_time', '未发送')

        if notification_time != '未发送' and notification_time != '未知':
            notification_time = notification_time[:19].replace('T', ' ')

        status_text += f"""

📬 通知状态
------------------------
🔹 通知状态: {'✅ 已发送' if notification_sent else '⏳ 待发送'}
🔹 发送时间: {notification_time}"""

    await restart_status_cmd.finish(status_text)

# 重启配置命令
restart_config_cmd = register_alconna(
    "重启配置",
    aliases={"restart_config", "配置重启"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=1,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["action?", str]["value?", str]["extra", MultiVar(str, "*")]],
    description="查看或修改自动重启配置",
    usage="重启配置 [启用/禁用] 或 重启配置 时间 HH:MM",
    examples=["重启配置", "重启配置 启用", "重启配置 时间 04:00"],
)

@restart_config_cmd.handle()
async def handle_restart_config(bot: Bot, event: MessageEvent, arp: Arparma):
    """处理重启配置命令"""
    if not restart_config:
        await restart_config_cmd.finish("重启系统未初始化")

    action = arp.all_matched_args.get("action")
    value = arp.all_matched_args.get("value")
    if not action:
        # 显示当前配置
        config_text = f"""
⚙️ 重启配置
------------------------
🔹 自动重启: {restart_config.auto_restart_enabled}
🔹 重启时间: {restart_config.restart_time}
🔹 启动脚本: {restart_config.startup_script_path}

📖 使用方法：
• 重启配置 启用/禁用 - 开启/关闭自动重启
• 重启配置 时间 HH:MM - 设置重启时间
""".strip()
        await restart_config_cmd.finish(config_text)

    action = str(action)

    if action in ["启用", "enable"]:
        try:
            restart_config.auto_restart_enabled = True
            await restart_config.save()
        except Exception as e:
            logging.error(f"重启配置修改失败: {e}")
            await restart_config_cmd.finish(f"❌ 配置修改失败: {str(e)}")
        await restart_config_cmd.finish("✅ 自动重启已启用")

    elif action in ["禁用", "disable"]:
        try:
            restart_config.auto_restart_enabled = False
            await restart_config.save()
        except Exception as e:
            logging.error(f"重启配置修改失败: {e}")
            await restart_config_cmd.finish(f"❌ 配置修改失败: {str(e)}")
        await restart_config_cmd.finish("❌ 自动重启已禁用")

    elif action in ["时间", "time"] and value:
        new_time = str(value)
        if ":" in new_time and len(new_time.split(":")) == 2:
            try:
                hour, minute = map(int, new_time.split(":"))
            except Exception:
                await restart_config_cmd.finish("❌ 时间格式错误，请使用 HH:MM 格式")
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                try:
                    restart_config.restart_time = new_time
                    await restart_config.save()
                    # 重新设置定时任务
                    scheduler.remove_job("daily_restart")
                    setup_scheduled_restart()
                except Exception as e:
                    logging.error(f"重启配置修改失败: {e}")
                    await restart_config_cmd.finish(f"❌ 配置修改失败: {str(e)}")
                await restart_config_cmd.finish(f"✅ 重启时间已设置为 {new_time}")
            else:
                await restart_config_cmd.finish("❌ 时间格式错误，小时应为0-23，分钟应为0-59")
        else:
            await restart_config_cmd.finish("❌ 时间格式错误，请使用 HH:MM 格式")
    else:
        await restart_config_cmd.finish("❌ 未知的配置参数")
