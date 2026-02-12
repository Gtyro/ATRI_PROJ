import psutil
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

from src.adapters.nonebot.command_registry import register_command

# 插件元信息
__plugin_meta__ = PluginMetadata(
    name="系统状态",
    description="查询系统资源使用情况",
    usage="系统状态/status",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

# 注册系统状态命令处理器
status_cmd = register_command(
    "系统状态",
    aliases={"status", "状态"},
    role="admin",
    permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER,
    rule=to_me(),
    priority=1,
    block=True,
)

@status_cmd.handle()
async def handle_status(bot: Bot, event: MessageEvent):
    # 获取CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)

    # 获取内存使用情况
    memory = psutil.virtual_memory()
    memory_total = memory.total / (1024 * 1024 * 1024)  # 转换为GB
    memory_used = memory.used / (1024 * 1024 * 1024)    # 转换为GB
    memory_percent = memory.percent

    # 获取磁盘使用情况
    disk = psutil.disk_usage('/')
    disk_total = disk.total / (1024 * 1024 * 1024)  # 转换为GB
    disk_used = disk.used / (1024 * 1024 * 1024)    # 转换为GB
    disk_percent = disk.percent

    status_text = f"""
📊 系统状态信息 📊
------------------------
🔹 CPU使用率: {cpu_percent:.1f}%

🔹 内存使用情况:
  - 总内存: {memory_total:.2f} GB
  - 已使用: {memory_used:.2f} GB ({memory_percent:.1f}%)

🔹 磁盘使用情况:
  - 总空间: {disk_total:.2f} GB
  - 已使用: {disk_used:.2f} GB ({disk_percent:.1f}%)
    """.strip()

    await status_cmd.finish(status_text)
