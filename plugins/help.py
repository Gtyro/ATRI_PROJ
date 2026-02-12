from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

from src.adapters.nonebot.command_registry import (
    get_plugin_display_name,
    get_plugin_metadata,
    register_command,
    resolve_command_for_event,
)
from src.adapters.nonebot.command_list_renderer import render_command_list

# 插件元信息
__plugin_meta__ = PluginMetadata(
    name="帮助",
    description="查询功能帮助说明",
    usage="帮助 功能名",
    type="application",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
            "default_enabled": True,
        }
    },
)

# 注册帮助命令
help_cmd = register_command(
    "帮助",
    aliases={"help"},
    role="normal",
    rule=to_me(),
    priority=1,
    block=True,
    description="查询功能帮助，或查看普通用户命令列表",
    usage="帮助 功能名",
    examples=["帮助 天气", "帮助 签到"],
)

SCOPE_LABELS = {
    "any": "不限",
    "group_only": "仅群聊",
    "private_only": "仅私聊",
}


def _scope_label(scope: str) -> str:
    return SCOPE_LABELS.get(scope, scope)


def _permission_denied_message(role: str) -> str:
    if role == "admin":
        return "该功能需要管理员权限"
    if role == "superuser":
        return "该功能需要超级用户权限"
    return "该功能当前不可用"


def _render_command_help(result) -> str:
    spec = result.spec
    meta = get_plugin_metadata(spec.plugin)
    description = spec.description or (meta.description if meta else "")
    usage = spec.usage or (meta.usage if meta else "")

    lines = ["🧭 功能帮助"]
    lines.append(f"功能: {spec.name}")
    if spec.aliases:
        lines.append(f"别名: {'、'.join(spec.aliases)}")
    lines.append(f"范围: {_scope_label(spec.scope)}")
    if not result.enabled:
        lines.append("状态: 已禁用")
    lines.append(f"所属插件: {get_plugin_display_name(spec.plugin)}")
    if description:
        lines.append(f"描述: {description}")
    if usage:
        lines.append("用法:")
        lines.append(usage)
    if spec.examples:
        lines.append("示例:")
        lines.extend([f"- {example}" for example in spec.examples])
    return "\n".join(lines)


@help_cmd.handle()
async def handle_help(event: MessageEvent, args: Message = CommandArg()):
    query = args.extract_plain_text().strip()
    if not query:
        text = await render_command_list(event, "normal", include_auto=False)
        await help_cmd.finish(text)
    result = await resolve_command_for_event(event, query)
    if not result:
        await help_cmd.finish("未找到该功能的帮助")
    if not result.permitted:
        await help_cmd.finish(_permission_denied_message(result.spec.role))
    await help_cmd.finish(_render_command_help(result))
