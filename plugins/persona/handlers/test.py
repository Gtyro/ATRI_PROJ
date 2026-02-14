import json
import logging
from datetime import datetime

from arclet.alconna import Args, Arparma, MultiVar
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me

from plugins.message_basic.models import BasicMessage
from .. import psstate
from ..psstate import is_enabled
from src.adapters.nonebot.command_registry import register_alconna


def _normalize_tokens(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]

# 设置拟人测试指令
test_persona = register_alconna(
    "测试",
    aliases={"测试人格"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["message", MultiVar(str, "*")]],
    description="模拟人格回复，不实际向群内发送",
    usage="测试 [群号] [可选消息]",
    examples=["测试 123456", "测试 123456 今晚聊什么"],
)
@test_persona.handle()
async def handle_test_persona(bot: Bot, event: Event, arp: Arparma):
    """测试拟人回复，对某个群组进行模拟处理，返回回复内容给超级用户"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        await test_persona.finish("人格系统未启用，请检查配置和日志")

    # 解析参数获取群号和可选的测试消息
    group_id = arp.all_matched_args.get("group_id")
    message_parts = _normalize_tokens(arp.all_matched_args.get("message"))
    if not group_id:
        await test_persona.finish("格式错误，正确格式：测试 [群号] [消息]，消息是可选的")

    group_id = str(group_id)
    if not group_id.isdigit():
        await test_persona.finish("群号格式不正确")

    # 构造会话ID
    conv_id = f"group_{group_id}"

    # 检查是否有测试消息
    test_message = " ".join(message_parts).strip() if message_parts else None
    if test_message == "":
        test_message = None

    try:
        # 提示开始生成回复
        if test_message:
            await test_persona.send(f"正在为群 {group_id} 使用测试消息「{test_message}」生成模拟回复...")
        else:
            await test_persona.send(f"正在为群 {group_id} 生成模拟回复...")

        # 调用simulate_reply生成回复，直接传入测试消息
        reply_data = await psstate.persona_system.simulate_reply(conv_id, test_message)
    except Exception as e:
        logging.error(f"测试人格回复异常: {e}")
        await test_persona.finish(f"模拟回复出错: {str(e)}")

    # 处理回复结果
    if reply_data and "reply_content" in reply_data:
        reply_content = reply_data["reply_content"]
        if reply_content:
            await test_persona.send(reply_content)
        else:
            await test_persona.finish("生成的回复内容为空")
    else:
        await test_persona.finish("模拟回复失败，请检查日志")


def _parse_datetime(value: str) -> datetime:
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    ]
    if "T" in value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    for pattern in patterns:
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    raise ValueError("时间格式不正确")


async def _send_to_superusers(bot: Bot, text: str) -> int:
    driver = get_driver()
    superusers = driver.config.superusers or []
    success = 0
    for user_id in superusers:
        try:
            await bot.send_private_msg(user_id=int(user_id), message=text)
            success += 1
        except Exception as e:
            logging.error(f"向超级用户 {user_id} 发送消息失败: {e}")
    return success


async def _load_basic_messages(conv_id: str, start_time: datetime, limit: int):
    messages = (
        await BasicMessage.filter(conv_id=conv_id, created_at__gte=start_time)
        .order_by("created_at")
        .limit(limit)
        .all()
    )
    return [message.to_dict() for message in messages]


memory_extract_test = register_alconna(
    "记忆提取测试",
    aliases={"记忆提取", "测试记忆提取"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["rest", MultiVar(str, "*")]],
    description="测试记忆/话题提取并私发结果给超级用户",
    usage="记忆提取测试 [群号] [起始时间] [可选条数]",
    examples=["记忆提取测试 123456 2025-02-01 12:00", "记忆提取测试 123456 2025-02-01 12:00 50"],
)


@memory_extract_test.handle()
async def handle_memory_extract_test(bot: Bot, event: Event, arp: Arparma):
    """测试话题/记忆提取，结果私发给超级用户"""
    if not is_enabled():
        await memory_extract_test.finish("人格系统未启用，请检查配置和日志")

    group_id = arp.all_matched_args.get("group_id")
    rest = _normalize_tokens(arp.all_matched_args.get("rest"))
    if not group_id or len(rest) < 2:
        await memory_extract_test.finish("格式错误：记忆提取 群号 起始时间 [条数]")

    group_id = str(group_id)
    if not group_id.isdigit():
        await memory_extract_test.finish("群号格式不正确")

    if len(rest) >= 3:
        time_text = f"{rest[0]} {rest[1]}"
        rest = rest[2:]
    else:
        time_text = rest[0]
        rest = rest[1:]

    try:
        start_time = _parse_datetime(time_text)
    except ValueError:
        await memory_extract_test.finish("时间格式不正确，示例：2025-02-01 12:00")

    limit = psstate.persona_system.get_queue_history_size()
    if rest:
        try:
            limit = int(rest[0])
        except ValueError:
            await memory_extract_test.finish("条数格式不正确")

    conv_id = f"group_{group_id}"
    messages = await _load_basic_messages(conv_id, start_time, limit)
    if not messages:
        await memory_extract_test.finish("没有匹配到消息")

    topics = await psstate.persona_system.extract_topics_from_messages(conv_id, messages)
    payload = {
        "conv_id": conv_id,
        "start_time": start_time.isoformat(sep=" ", timespec="seconds"),
        "message_count": len(messages),
        "topic_count": len(topics),
        "topics": topics,
    }
    report = "记忆提取测试结果:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    sent = await _send_to_superusers(bot, report)
    await memory_extract_test.finish(f"已发送提取结果给 {sent} 位超级用户")


keyword_extract_test = register_alconna(
    "关键词提取测试",
    aliases={"关键词提取", "测试关键词"},
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["rest", MultiVar(str, "*")]],
    description="测试回复关键词提取并私发结果给超级用户",
    usage="关键词提取测试 [群号] [起始时间] [可选条数]",
    examples=["关键词提取测试 123456 2025-02-01 12:00", "关键词提取测试 123456 2025-02-01 12:00 50"],
)


@keyword_extract_test.handle()
async def handle_keyword_extract_test(bot: Bot, event: Event, arp: Arparma):
    """测试回复前关键词提取，结果私发给超级用户"""
    if not is_enabled():
        await keyword_extract_test.finish("人格系统未启用，请检查配置和日志")

    group_id = arp.all_matched_args.get("group_id")
    rest = _normalize_tokens(arp.all_matched_args.get("rest"))
    if not group_id or len(rest) < 2:
        await keyword_extract_test.finish("格式错误：关键词提取 群号 起始时间 [条数]")

    group_id = str(group_id)
    if not group_id.isdigit():
        await keyword_extract_test.finish("群号格式不正确")

    if len(rest) >= 3:
        time_text = f"{rest[0]} {rest[1]}"
        rest = rest[2:]
    else:
        time_text = rest[0]
        rest = rest[1:]

    try:
        start_time = _parse_datetime(time_text)
    except ValueError:
        await keyword_extract_test.finish("时间格式不正确，示例：2025-02-01 12:00")

    limit = psstate.persona_system.get_queue_history_size()
    if rest:
        try:
            limit = int(rest[0])
        except ValueError:
            await keyword_extract_test.finish("条数格式不正确")

    conv_id = f"group_{group_id}"
    messages = await _load_basic_messages(conv_id, start_time, limit)
    if not messages:
        await keyword_extract_test.finish("没有匹配到消息")

    topics = await psstate.persona_system.extract_topics_from_messages(conv_id, messages)
    keywords = await psstate.persona_system.extract_reply_keywords_from_history(conv_id, messages)
    payload = {
        "conv_id": conv_id,
        "start_time": start_time.isoformat(sep=" ", timespec="seconds"),
        "message_count": len(messages),
        "topic_count": len(topics),
        "keywords": keywords,
    }
    report = "关键词提取测试结果:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    sent = await _send_to_superusers(bot, report)
    await keyword_extract_test.finish(f"已发送提取结果给 {sent} 位超级用户")
