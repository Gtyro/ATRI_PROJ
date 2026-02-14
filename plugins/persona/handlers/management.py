import logging
import os

from arclet.alconna import Args, Arparma, MultiVar
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State

from .. import psstate
from ..psstate import is_enabled
from src.core.services.persona_policy_flags import (
    LLM_ACTIVE_REPLY_ENABLED_KEY,
    LLM_KEYWORD_EXTRACT_ENABLED_KEY,
    LLM_PASSIVE_REPLY_ENABLED_KEY,
    LLM_TOPIC_EXTRACT_ENABLED_KEY,
    normalize_persona_policy_config,
    resolve_llm_flags,
)
from src.adapters.nonebot.command_registry import register_alconna

# 状态查询命令
persona_stats = register_alconna(
    "队列状态",
    aliases={"人格状态"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["extra", MultiVar(str, "*")]],
    description="查看人格队列与处理状态",
    usage="队列状态 [群号]",
    examples=["队列状态", "队列状态 123456"],
)
@persona_stats.handle()
async def handle_persona_stats(bot: Bot, event: Event, state: T_State, arp: Arparma):
    """查询人格系统状态"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        logging.error("人格系统未启用，请检查配置和日志")
        await persona_stats.finish("人格系统未启用，请检查配置和日志")

    # 解析命令参数
    conv_id = None

    # 如果指定了会话ID
    group_id = arp.all_matched_args.get("group_id")
    if group_id:
        group_id = str(group_id)
        if group_id.isdigit():
            conv_id = f"group_{group_id}"
        else:
            await persona_stats.finish("会话ID格式不正确")

    try:
        # 获取队列统计
        reply = await psstate.persona_system.get_queue_status_reply(conv_id)

        await persona_stats.send(reply)
    except Exception as e:
        logging.error(f"获取系统状态异常: {e}")
        await persona_stats.send(f"获取状态信息失败: {str(e)}")

# 添加切换人格命令
switch_persona = register_alconna(
    "切换人格",
    role="superuser",
    permission=SUPERUSER,
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["prompt_file?", str]["extra", MultiVar(str, "*")]],
    description="为指定群切换人格提示词文件",
    usage="切换人格 [群号] [prompt文件名]",
    examples=["切换人格 123456 atri_prompt.txt"],
)
@switch_persona.handle()
async def handle_switch_persona(bot: Bot, event: Event, arp: Arparma):
    """切换群组的人格配置"""
    group_id = arp.all_matched_args.get("group_id")
    prompt_file = arp.all_matched_args.get("prompt_file")
    extra = arp.all_matched_args.get("extra") or []
    extra_args = extra if isinstance(extra, list) else [extra]
    parsed_args = [value for value in [group_id, prompt_file, *extra_args] if value]
    if not group_id or not prompt_file or extra_args:
        await switch_persona.send(f"输入内容：{['切换人格', *parsed_args]}")
        await switch_persona.finish("格式错误，正确格式：切换人格 [群号] [prompt文件名]")
        return

    group_id = str(group_id)
    prompt_file = str(prompt_file)
    if not group_id.isdigit():
        await switch_persona.finish("群号格式不正确")
        return

    # 检查文件是否存在
    file_path = os.path.join("data", "persona", prompt_file)
    if not os.path.exists(file_path):
        await switch_persona.finish(f"提示文件 {prompt_file} 不存在")

    # 更新群组配置
    try:
        await psstate.persona_system.set_group_prompt_file(group_id, file_path)
    except Exception as e:
        logging.error(f"切换人格配置失败: {e}")
        await switch_persona.finish("配置更新失败，请检查日志")
    await switch_persona.finish(f"已为群 {group_id} 设置人格提示文件为 {prompt_file}")

# 强制处理命令
process_now = register_alconna(
    "处理队列",
    aliases={"处理消息", "立即处理"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["extra", MultiVar(str, "*")]],
    description="立即触发人格消息处理",
    usage="处理队列 [群号]",
    examples=["处理队列", "处理队列 123456"],
)
@process_now.handle()
async def handle_process_now(bot: Bot, event: Event, state: T_State, arp: Arparma):
    """强制立即处理消息"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        await process_now.finish("人格系统未启用，请检查配置和日志")

    group_id = arp.all_matched_args.get("group_id")
    extra = arp.all_matched_args.get("extra") or []
    extra_args = extra if isinstance(extra, list) else [extra]
    args = [value for value in [group_id, *extra_args] if value]
    if args:
        await process_now.send(f"开始处理消息... 参数: {args}")
    else:
        await process_now.send("开始处理消息...")

    group_id = str(group_id) if group_id else None

    try:
        if group_id:
            conv_id = f"group_{group_id}"
            await psstate.persona_system.process_conversation(conv_id, "")
        else:
            # 执行维护任务
            await psstate.persona_system.schedule_maintenance()
            await process_now.send("消息处理完成")
    except Exception as e:
        logging.error(f"处理消息异常: {e}")
        await process_now.send(f"处理消息失败: {str(e)}")

# 清空队列命令
clear_queue = register_alconna(
    "清空队列",
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["extra", MultiVar(str, "*")]],
    description="清空指定群的人格短期记忆队列",
    usage="清空队列 [群号]",
    examples=["清空队列 123456"],
)
@clear_queue.handle()
async def handle_clear_queue(bot: Bot, event: Event, state: T_State, arp: Arparma):
    """清空指定群组的消息队列（短期记忆）"""
    if not is_enabled():
        await clear_queue.finish("人格系统未启用，请检查配置和日志")

    group_id = arp.all_matched_args.get("group_id")
    if not group_id:
        await clear_queue.finish("格式错误，正确格式：清空队列 [群号]")

    group_id = str(group_id)
    if not group_id.isdigit():
        await clear_queue.finish("群号格式不正确")

    conv_id = f"group_{group_id}"
    try:
        deleted = await psstate.persona_system.clear_queue(conv_id)
    except Exception as e:
        logging.error(f"清空消息队列异常: {e}")
        await clear_queue.finish("清空消息队列失败，请检查日志")
    await clear_queue.finish(f"已清空群 {group_id} 的消息队列，共删除 {deleted} 条")


llm_switch = register_alconna(
    "LLM开关",
    aliases={"人格LLM", "人格开关", "LLM设置"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["feature?", str]["action?", str]["extra", MultiVar(str, "*")]],
    description="查看或设置 Persona 的 LLM 功能开关",
    usage="LLM开关 [群号] [记忆/被动/主动/回复] [开/关] 或 LLM开关 [群号] 查看",
    examples=["LLM开关 123456 查看", "LLM开关 123456 回复 关"],
)


def _parse_switch_action(action: str):
    if action in {"开", "开启", "on", "ON", "true", "True", "1"}:
        return True
    if action in {"关", "关闭", "off", "OFF", "false", "False", "0"}:
        return False
    return None


@llm_switch.handle()
async def handle_llm_switch(bot: Bot, event: Event, state: T_State, arp: Arparma):
    """设置或查看 LLM 开关"""
    if not is_enabled():
        await llm_switch.finish("人格系统未启用，请检查配置和日志")

    group_id = arp.all_matched_args.get("group_id")
    feature = arp.all_matched_args.get("feature")
    action = arp.all_matched_args.get("action")

    if not group_id or not feature:
        await llm_switch.finish("格式错误：LLM开关 [群号] [记忆/被动/主动/回复] [开/关] 或 LLM开关 [群号] 查看")

    group_id = str(group_id)
    feature = str(feature)
    if action is not None:
        action = str(action)

    if not group_id.isdigit():
        await llm_switch.finish("群号格式不正确")

    if feature in {"查看", "状态"}:
        policy = await psstate.plugin_policy_service.get_policy(gid=group_id, plugin_name="persona")
        flags = resolve_llm_flags(policy.config or {})
        await llm_switch.finish(
            f"群 {group_id} LLM开关状态:\n"
            f"- 记忆提取: {flags.get(LLM_TOPIC_EXTRACT_ENABLED_KEY)}\n"
            f"- 关键词提取(联动): {flags.get(LLM_KEYWORD_EXTRACT_ENABLED_KEY)}\n"
            f"- 被动回复: {flags.get(LLM_PASSIVE_REPLY_ENABLED_KEY)}\n"
            f"- 主动回复: {flags.get(LLM_ACTIVE_REPLY_ENABLED_KEY)}"
        )

    if not action:
        await llm_switch.finish("格式错误：LLM开关 [群号] [记忆/被动/主动/回复] [开/关]")

    action = _parse_switch_action(action)
    if action is None:
        await llm_switch.finish("开关参数错误：请使用 开/关")

    if feature in {"关键词", "关键字"}:
        await llm_switch.finish("关键词提取为联动项，不能单独设置；请改用 被动/主动/回复 开关")

    feature_map = {
        "记忆": [LLM_TOPIC_EXTRACT_ENABLED_KEY],
        "话题": [LLM_TOPIC_EXTRACT_ENABLED_KEY],
        "提取": [LLM_TOPIC_EXTRACT_ENABLED_KEY],
        "被动": [LLM_PASSIVE_REPLY_ENABLED_KEY],
        "被动回复": [LLM_PASSIVE_REPLY_ENABLED_KEY],
        "主动": [LLM_ACTIVE_REPLY_ENABLED_KEY],
        "主动回复": [LLM_ACTIVE_REPLY_ENABLED_KEY],
        # 兼容旧用法：回复 = 被动 + 主动
        "回复": [LLM_PASSIVE_REPLY_ENABLED_KEY, LLM_ACTIVE_REPLY_ENABLED_KEY],
        "回答": [LLM_PASSIVE_REPLY_ENABLED_KEY, LLM_ACTIVE_REPLY_ENABLED_KEY],
    }
    keys = feature_map.get(feature)
    if not keys:
        await llm_switch.finish("功能参数错误：仅支持 记忆/被动/主动/回复")

    group_name = None
    try:
        group_info = await bot.get_group_info(group_id=int(group_id))
        group_name = group_info.get("group_name")
    except Exception:
        group_name = None

    policy = await psstate.plugin_policy_service.get_policy(
        gid=group_id,
        plugin_name="persona",
        group_name=group_name,
    )
    config = policy.config or {}
    for key in keys:
        config[key] = action
    config = normalize_persona_policy_config(config)

    await psstate.plugin_policy_service.set_policy(
        gid=group_id,
        plugin_name="persona",
        config=config,
        group_name=group_name,
    )
    flags = resolve_llm_flags(config)
    await llm_switch.finish(
        f"已更新群 {group_id} LLM开关:\n"
        f"- 记忆提取: {flags.get(LLM_TOPIC_EXTRACT_ENABLED_KEY)}\n"
        f"- 关键词提取(联动): {flags.get(LLM_KEYWORD_EXTRACT_ENABLED_KEY)}\n"
        f"- 被动回复: {flags.get(LLM_PASSIVE_REPLY_ENABLED_KEY)}\n"
        f"- 主动回复: {flags.get(LLM_ACTIVE_REPLY_ENABLED_KEY)}"
    )
