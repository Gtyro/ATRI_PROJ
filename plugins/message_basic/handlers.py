from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent
from .models import BasicMessage
import logging

message_handler = on_message(priority=10, block=False)

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