import logging

from arclet.alconna import Args, Arparma, MultiVar
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State

from .. import psstate
from ..psstate import is_enabled
from src.adapters.nonebot.command_args import normalize_alconna_tokens
from src.adapters.nonebot.command_registry import register_alconna

# 记忆查询命令
memories = register_alconna(
    "记得",
    aliases={"回忆", "想起"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["conv_id?", str]["query", MultiVar(str, "*")]],
    description="查询指定会话的长期记忆",
    usage="记得 [群号/私聊ID] [查询内容]",
    examples=["记得 123456 最近聊过什么", "记得 10001 TA喜欢吃什么"],
)
@memories.handle()
async def handle_memories(bot: Bot, event: Event, state: T_State, arp: Arparma):
    """查询记忆"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        await memories.finish("人格系统未启用，请检查配置和日志")

    user_id = event.get_user_id()
    conv_id = arp.all_matched_args.get("conv_id")
    query_parts = normalize_alconna_tokens(arp.all_matched_args.get("query"))
    query = " ".join(query_parts).strip()

    # 格式: 记得 [conv_id] [query]
    if not conv_id or not query:
        await memories.finish("命令格式: 记得 [群号/私聊ID] [查询内容]")
    conv_id = str(conv_id)

    try:
        # 构建conv_id的格式
        if conv_id.isdigit():
            # 判断是群聊还是私聊
            if await bot.get_group_info(group_id=int(conv_id)):
                conv_id = f"group_{conv_id}"
            else:
                conv_id = f"private_{conv_id}"

        # 使用persona_system的format_memories方法获取格式化的记忆回复
        reply = await psstate.persona_system.format_memories(query, user_id, conv_id)
        await memories.send(reply)
    except Exception as e:
        logging.error(f"记忆查询异常: {e}")
        await memories.send("回忆过程出现了问题...")

# 添加常驻记忆命令
remember_permanent = register_alconna(
    "记住",
    role="superuser",
    permission=SUPERUSER,
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[
        Args["group_id?", str]["node_name?", str]["memory_title?", str]["memory_content", MultiVar(str, "*")],
    ],
    description="写入常驻记忆（节点+记忆内容）",
    usage="记住 [群号] [节点名称] [记忆标题] [记忆内容]",
    examples=["记住 123456 角色设定 喜好 爱吃可乐饼"],
)
@remember_permanent.handle()
async def handle_remember_permanent(bot: Bot, event: Event, arp: Arparma):
    """创建常驻节点和记忆对"""
    if not is_enabled():
        await remember_permanent.finish("人格系统未启用，请检查配置和日志")

    group_id = arp.all_matched_args.get("group_id")
    node_name = arp.all_matched_args.get("node_name")
    memory_title = arp.all_matched_args.get("memory_title")
    memory_content_parts = _normalize_tokens(arp.all_matched_args.get("memory_content"))
    memory_content = " ".join(memory_content_parts).strip()

    if not group_id or not node_name or not memory_title or not memory_content:
        await remember_permanent.finish("命令格式: 记住 [群号/私聊ID] [节点名称] [记忆标题] [记忆内容]")

    group_id = str(group_id)
    node_name = str(node_name)
    memory_title = str(memory_title)

    # 构建conv_id的格式
    conv_id = None
    if group_id.isdigit():
        # 判断是群聊还是私聊
        try:
            if await bot.get_group_info(group_id=int(group_id)):
                conv_id = f"group_{group_id}"
            else:
                await remember_permanent.finish("群号格式不正确")
        except Exception:
            await remember_permanent.finish("群号格式不正确")

    try:
        # 直接使用persona_system的方法创建常驻节点和记忆对
        if conv_id is None:
            raise ValueError("群号格式不正确")
        result = await psstate.persona_system.create_permanent_memory(
            conv_id, node_name, memory_title, memory_content
        )

        await remember_permanent.send(f"已创建常驻节点-记忆对:\n节点: {node_name}\n记忆标题: {memory_title}\n记忆内容: {memory_content[:10]}...")
    except Exception as e:
        logging.error(f"创建常驻节点-记忆对异常: {e}")
        await remember_permanent.send("创建常驻节点-记忆对失败，请检查日志")
