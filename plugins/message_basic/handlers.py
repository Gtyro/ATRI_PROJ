from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from tortoise.functions import Count
from .models import BasicMessage
import logging

from src.adapters.nonebot.command_registry import register_auto_feature, register_command

message_handler = on_message(priority=10, block=False)
register_auto_feature(
    "基础消息入库",
    role="superuser",
    trigger_type="message",
)

@message_handler.handle()
async def handle_basic_message(bot: Bot, event: Event):
    try:
        user_id = event.get_user_id()
        message = event.get_plaintext()
        if not message.strip():
            return
        is_group = isinstance(event, GroupMessageEvent)
        conv_type = "group" if is_group else "private"
        conv_id = f"{conv_type}_{event.group_id if is_group else user_id}"
        user_name = getattr(event.sender, 'card', None) or getattr(event.sender, 'nickname', None) or user_id
        is_direct = event.is_tome() or not is_group
        await BasicMessage.create(
            conv_id=conv_id,
            user_id=user_id,
            user_name=user_name,
            content=message,
            is_direct=is_direct,
            is_bot=False,
            is_processed=False,
            metadata={}
        )
    except Exception as e:
        logging.error(f"基础消息记录异常: {e}")


message_overview = register_command(
    "消息概览",
    role="superuser",
    permission=SUPERUSER,
    rule=to_me(),
    priority=5,
    block=True,
    description="统计各群聊消息总量",
    usage="消息概览",
    examples=["消息概览"],
)


@message_overview.handle()
async def handle_message_overview():
    """统计所有群号及对应消息数量"""
    try:
        rows = (
            await BasicMessage.filter(conv_id__startswith="group_")
            .group_by("conv_id")
            .annotate(total=Count("id"))
            .values("conv_id", "total")
        )
    except Exception as e:
        logging.error(f"消息概览异常: {e}")
        await message_overview.finish("消息概览获取失败，请检查日志")

    if not rows:
        await message_overview.finish("暂无群消息记录")

    def _sort_key(row):
        conv_id = row.get("conv_id") or ""
        group_id = conv_id.split("_", 1)[1] if "_" in conv_id else conv_id
        try:
            return int(group_id)
        except ValueError:
            return group_id

    rows.sort(key=_sort_key)

    lines = ["群消息概览："]
    for row in rows:
        conv_id = row.get("conv_id") or ""
        group_id = conv_id.split("_", 1)[1] if "_" in conv_id else conv_id
        total = row.get("total") or 0
        lines.append(f"{group_id}: {total} 条")

    await message_overview.finish("\n".join(lines))
