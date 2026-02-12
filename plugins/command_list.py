from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

from src.adapters.nonebot.command_list_renderer import render_command_list
from src.adapters.nonebot.command_registry import register_command

# 插件元信息
__plugin_meta__ = PluginMetadata(
    name="命令列表",
    description="输出不同权限范围的命令列表",
    usage="命令/命令列表/管理员命令/超级用户命令",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

# 普通用户命令列表
normal_cmd = register_command(
    "命令",
    aliases={"命令列表"},
    role="normal",
    rule=to_me(),
    priority=1,
    block=True,
    description="查看普通用户可用命令列表",
    usage="命令 或 命令列表",
)

# 管理员命令列表
admin_cmd = register_command(
    "管理员命令",
    role="admin",
    permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER,
    rule=to_me(),
    priority=1,
    block=True,
    description="查看管理员可用命令列表",
    usage="管理员命令",
)

# 超级用户命令列表
super_cmd = register_command(
    "超级用户命令",
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=1,
    block=True,
    description="查看超级用户可用命令列表",
    usage="超级用户命令",
)


@normal_cmd.handle()
async def handle_normal_cmd(event: MessageEvent):
    text = await render_command_list(event, "normal", include_auto=False)
    await normal_cmd.finish(text)


@admin_cmd.handle()
async def handle_admin_cmd(event: MessageEvent):
    text = await render_command_list(event, "admin", include_auto=False)
    await admin_cmd.finish(text)


@super_cmd.handle()
async def handle_super_cmd(event: MessageEvent):
    text = await render_command_list(event, "superuser", include_auto=True)
    await super_cmd.finish(text)
