from __future__ import annotations

from collections import defaultdict

from nonebot.adapters.onebot.v11 import MessageEvent

from src.adapters.nonebot.command_registry import (
    get_plugin_display_name,
    list_auto_features_for_role,
    list_commands_for_role,
)


def _format_grouped_items(
    grouped: dict[str, list],
    *,
    viewer_role: str,
    disabled_marker: str = " [禁用]",
    contextual_marker: str = " [按群]",
) -> list[str]:
    lines: list[str] = []
    for plugin in sorted(grouped.keys()):
        display_name = get_plugin_display_name(plugin)
        lines.append(f"{display_name}:")
        for item in sorted(grouped[plugin], key=lambda cmd: cmd.name):
            suffix = ""
            if viewer_role == "superuser":
                status = getattr(item, "status", "enabled")
                if status == "disabled":
                    suffix = disabled_marker
                elif status == "contextual":
                    suffix = contextual_marker
            lines.append(f"- {item.name}{suffix}")
    return lines


async def render_command_list(
    event: MessageEvent,
    target_role: str,
    *,
    include_auto: bool,
) -> str:
    commands = await list_commands_for_role(event, target_role)
    if not commands:
        return "暂无可用命令"

    grouped_commands: dict[str, list] = defaultdict(list)
    for cmd in commands:
        grouped_commands[cmd.plugin].append(cmd)

    lines = ["📋 命令列表 📋"]
    lines.extend(_format_grouped_items(grouped_commands, viewer_role=target_role))

    if include_auto:
        auto_features = await list_auto_features_for_role(event, target_role)
        if auto_features:
            grouped_auto: dict[str, list] = defaultdict(list)
            for feature in auto_features:
                grouped_auto[feature.plugin].append(feature)

            lines.append("")
            lines.append("⚙️ 自动功能列表 ⚙️")
            lines.extend(_format_grouped_items(grouped_auto, viewer_role=target_role))

    return "\n".join(lines)
