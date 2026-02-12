"""
群组 x 插件策略管理插件
"""

import logging
from typing import Any, Dict, List, Optional, Set

from arclet.alconna import Args, Arparma, MultiVar
from nonebot import require
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

from src.core.services.plugin_policy_service import PluginPolicyService
from src.core.services.plugin_policy_defaults import get_ingest_plugins, get_policy_plugins
from src.infra.db.tortoise.plugin_policy_store import TortoisePluginPolicyStore
from src.adapters.nonebot.command_registry import register_alconna

# 声明依赖
require("db_core")

__plugin_meta__ = PluginMetadata(
    name="PluginPolicy",
    description="群组 x 插件策略管理",
    usage="\n".join(
        [
            "插件开关 启用/禁用 插件名 群号 [入库]",
            "插件列表 [全部]",
            "群组列表",
            "插件启用群 插件名 [全部]",
            "群组插件 群号 [全部]",
        ]
    ),
    type="application",
    homepage="https://github.com/yourusername/ATRI_PROJ",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
        }
    },
)

policy_service = PluginPolicyService(TortoisePluginPolicyStore())

ALL_TOKENS = {"全部", "所有", "all", "ALL"}


def _want_all(args: List[str]) -> bool:
    return any(arg in ALL_TOKENS for arg in args)


def _normalize_args(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _get_ingest_plugins() -> Set[str]:
    try:
        return set(get_ingest_plugins())
    except Exception as e:
        logging.warning(f"获取入库插件失败: {e}")
        return set()


async def _load_plugin_names(*, include_hidden: bool = True) -> List[str]:
    plugin_names = set()
    try:
        plugin_names.update(get_policy_plugins(include_hidden=include_hidden))
    except Exception as e:
        logging.warning(f"获取插件列表失败: {e}")
    ingest_plugins = get_ingest_plugins()
    plugin_names.update(ingest_plugins)
    return sorted(plugin_names)


async def _safe_get_group_list(bot: Bot) -> List[Dict[str, Any]]:
    try:
        if hasattr(bot, "get_group_list"):
            groups = await bot.get_group_list()
            return groups or []
    except Exception as e:
        logging.warning(f"获取群组列表失败: {e}")
    return []


def _build_group_map(groups: List[Dict[str, Any]], policies: List[Any]) -> Dict[str, str]:
    group_map: Dict[str, str] = {}
    for group in groups:
        gid = str(group.get("group_id") or group.get("gid") or "")
        if not gid:
            continue
        group_map[gid] = group.get("group_name") or group.get("name") or gid
    for policy in policies:
        if policy.gid not in group_map:
            group_map[policy.gid] = policy.group_name or policy.gid
    return group_map

plugin_policy_cmd = register_alconna(
    "插件开关",
    aliases={"启用插件", "禁用插件", "插件启用", "插件禁用"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[
        Args["action?", str]["plugin_name?", str]["group_id?", str]["scope?", str]["extra", MultiVar(str, "*")],
    ],
    description="为指定群组设置插件启用/禁用状态",
    usage="插件开关 启用/禁用 [插件名] [群号] [入库]",
    examples=["插件开关 启用 persona 123456", "插件开关 禁用 persona 123456 入库"],
)

plugin_policy_cmd.shortcut("启用插件", {"args": ["启用"], "prefix": True, "fuzzy": True})
plugin_policy_cmd.shortcut("插件启用", {"args": ["启用"], "prefix": True, "fuzzy": True})
plugin_policy_cmd.shortcut("禁用插件", {"args": ["禁用"], "prefix": True, "fuzzy": True})
plugin_policy_cmd.shortcut("插件禁用", {"args": ["禁用"], "prefix": True, "fuzzy": True})


@plugin_policy_cmd.handle()
async def handle_plugin_policy(bot: Bot, event: Event, arp: Arparma):
    action = arp.all_matched_args.get("action")
    plugin_name = arp.all_matched_args.get("plugin_name")
    group_id = arp.all_matched_args.get("group_id")
    scope = arp.all_matched_args.get("scope") or ""

    if not action or not plugin_name or not group_id:
        await plugin_policy_cmd.finish("用法: 插件开关 启用/禁用 插件名 群号 [入库]")

    action = str(action)
    plugin_name = str(plugin_name)
    group_id = str(group_id)
    scope = str(scope)

    if action not in ("启用", "禁用"):
        await plugin_policy_cmd.finish("格式错误: 需要启用/禁用指令")

    if not group_id.isdigit():
        await plugin_policy_cmd.finish("群号格式不正确")

    target_enabled = action == "启用"
    if scope in ("入库", "ingest", "ingestion"):
        ingest_plugins = _get_ingest_plugins()
        if plugin_name not in ingest_plugins:
            await plugin_policy_cmd.finish("该插件不支持入库开关")
        enabled = None
        ingest_enabled = target_enabled
    else:
        enabled = target_enabled
        ingest_enabled = target_enabled

    group_name = None
    try:
        group_info = await bot.get_group_info(group_id=int(group_id))
        group_name = group_info.get("group_name")
    except Exception as e:
        logging.warning(f"获取群组名称失败: {e}")

    try:
        policy = await policy_service.set_policy(
            gid=group_id,
            plugin_name=plugin_name,
            enabled=enabled,
            ingest_enabled=ingest_enabled,
            group_name=group_name,
        )
    except Exception as e:
        logging.error(f"更新插件策略失败: {e}")
        await plugin_policy_cmd.finish("更新失败，请检查日志")
    await plugin_policy_cmd.finish(
        f"已设置群 {group_id} 插件 {plugin_name} "
        f"启用={policy.enabled} 入库={policy.ingest_enabled}"
    )


plugin_list_cmd = register_alconna(
    "插件列表",
    aliases={"插件清单", "插件一览"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["flags", MultiVar(str, "*")]],
    description="查看可管理或全部插件列表",
    usage="插件列表 [全部]",
    examples=["插件列表", "插件列表 全部"],
)


@plugin_list_cmd.handle()
async def handle_plugin_list(event: Event, arp: Arparma):
    args = _normalize_args(arp.all_matched_args.get("flags"))
    include_hidden = _want_all(args)
    plugin_names = await _load_plugin_names(include_hidden=include_hidden)
    if not plugin_names:
        await plugin_list_cmd.finish("未获取到插件列表")
    title = "全部插件" if include_hidden else "可管理插件"
    lines = [f"{title}（{len(plugin_names)}）:"]
    lines.extend([f"- {name}" for name in plugin_names])
    if not include_hidden:
        lines.append("提示: 发送“插件列表 全部”查看全部插件")
    await plugin_list_cmd.finish("\n".join(lines))


group_list_cmd = register_alconna(
    "群组列表",
    aliases={"群列表", "群组清单"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["flags", MultiVar(str, "*")]],
    description="查看机器人可见的群组列表",
    usage="群组列表",
    examples=["群组列表"],
)


@group_list_cmd.handle()
async def handle_group_list(bot: Bot, event: Event, arp: Arparma):
    _ = _normalize_args(arp.all_matched_args.get("flags"))
    groups = await _safe_get_group_list(bot)
    if not groups:
        await group_list_cmd.finish("未获取到群组列表（适配器可能不支持获取群列表）")
    normalized = []
    for group in groups:
        gid = str(group.get("group_id") or group.get("gid") or "")
        if not gid:
            continue
        name = group.get("group_name") or group.get("name") or gid
        normalized.append((gid, name))
    if not normalized:
        await group_list_cmd.finish("未获取到群组列表")
    normalized.sort(key=lambda item: item[0])
    lines = [f"群组列表（{len(normalized)}）:"]
    lines.extend([f"- {gid} {name}" for gid, name in normalized])
    await group_list_cmd.finish("\n".join(lines))


plugin_groups_cmd = register_alconna(
    "插件启用群",
    aliases={"插件群组", "插件启用群组", "插件在哪些群", "插件在哪些群组"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["plugin_name?", str]["flags", MultiVar(str, "*")]],
    description="查看指定插件在哪些群启用",
    usage="插件启用群 [插件名] [全部]",
    examples=["插件启用群 persona", "插件启用群 persona 全部"],
)


@plugin_groups_cmd.handle()
async def handle_plugin_groups(bot: Bot, event: Event, arp: Arparma):
    plugin_name = arp.all_matched_args.get("plugin_name")
    flags = _normalize_args(arp.all_matched_args.get("flags"))
    if not plugin_name:
        await plugin_groups_cmd.finish("用法: 插件启用群 插件名 [全部]")
    plugin_name = str(plugin_name)
    show_all = _want_all(flags)
    ingest_plugins = _get_ingest_plugins()

    all_plugins = await _load_plugin_names(include_hidden=True)
    if plugin_name not in all_plugins:
        await plugin_groups_cmd.finish(f"未找到插件 {plugin_name}，请先使用“插件列表”确认名称")

    groups = await _safe_get_group_list(bot)
    if groups:
        await policy_service.ensure_policies(groups, [plugin_name])

    policies = await policy_service.list_policies(plugin_name=plugin_name)
    if not policies:
        await plugin_groups_cmd.finish(f"未查询到插件 {plugin_name} 的群组策略")

    group_map = _build_group_map(groups, policies)
    filtered = policies if show_all else [policy for policy in policies if policy.enabled]
    if not filtered:
        await plugin_groups_cmd.finish(f"插件 {plugin_name} 当前没有启用的群组")

    title = "群组策略" if show_all else "启用群组"
    lines = [f"插件 {plugin_name} {title}（{len(filtered)}）:"]
    for policy in sorted(filtered, key=lambda item: item.gid):
        group_name = group_map.get(policy.gid, policy.gid)
        if plugin_name in ingest_plugins:
            lines.append(f"- {policy.gid} {group_name} 启用={policy.enabled} 入库={policy.ingest_enabled}")
        elif show_all:
            lines.append(f"- {policy.gid} {group_name} 启用={policy.enabled}")
        else:
            lines.append(f"- {policy.gid} {group_name}")
    await plugin_groups_cmd.finish("\n".join(lines))


group_plugins_cmd = register_alconna(
    "群组插件",
    aliases={"群插件", "群启用插件", "群组启用插件"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["flags", MultiVar(str, "*")]],
    description="查看指定群启用的插件",
    usage="群组插件 [群号] [全部]",
    examples=["群组插件 123456", "群组插件 123456 全部"],
)


@group_plugins_cmd.handle()
async def handle_group_plugins(bot: Bot, event: Event, arp: Arparma):
    group_id = arp.all_matched_args.get("group_id")
    flags = _normalize_args(arp.all_matched_args.get("flags"))
    if not group_id:
        await group_plugins_cmd.finish("用法: 群组插件 群号 [全部]")
    group_id = str(group_id)
    show_all = _want_all(flags)
    ingest_plugins = _get_ingest_plugins()
    if not group_id.isdigit():
        await group_plugins_cmd.finish("群号格式不正确")

    groups = await _safe_get_group_list(bot)
    group_name = None
    for group in groups:
        gid = str(group.get("group_id") or group.get("gid") or "")
        if gid == group_id:
            group_name = group.get("group_name") or group.get("name")
            break
    if not group_name:
        try:
            group_info = await bot.get_group_info(group_id=int(group_id))
            group_name = group_info.get("group_name")
        except Exception as e:
            logging.warning(f"获取群组名称失败: {e}")

    plugin_names = await _load_plugin_names(include_hidden=show_all)
    if plugin_names:
        await policy_service.ensure_policies(
            [{"group_id": group_id, "group_name": group_name or group_id}],
            plugin_names,
        )

    policies = await policy_service.list_policies(gids=[group_id])
    if not policies:
        await group_plugins_cmd.finish(f"未查询到群 {group_id} 的插件策略")

    policy_map = {policy.plugin_name: policy for policy in policies}
    items: List[Any] = []
    if plugin_names:
        for name in sorted(plugin_names):
            policy = policy_map.get(name)
            if not policy:
                continue
            if show_all or policy.enabled:
                items.append(policy)
    else:
        items = [policy for policy in policies if show_all or policy.enabled]

    if not items:
        await group_plugins_cmd.finish(f"群 {group_id} 当前没有启用的插件")

    display_name = group_name or group_id
    title = "插件策略" if show_all else "启用插件"
    lines = [f"群组 {group_id} ({display_name}) {title}（{len(items)}）:"]
    for policy in sorted(items, key=lambda item: item.plugin_name):
        if policy.plugin_name in ingest_plugins:
            lines.append(f"- {policy.plugin_name} 启用={policy.enabled} 入库={policy.ingest_enabled}")
        elif show_all:
            lines.append(f"- {policy.plugin_name} 启用={policy.enabled}")
        else:
            lines.append(f"- {policy.plugin_name}")
    await group_plugins_cmd.finish("\n".join(lines))
