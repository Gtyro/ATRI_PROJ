"""回复生成相关服务。"""

import logging
from typing import Any, Dict, Optional

from ..ports import ShortTermMemoryPort
from .conversation_service import ConversationService


class ReplyService:
    """负责模拟回复等回复相关能力。"""

    def __init__(self, short_term: ShortTermMemoryPort, msgprocessor: Any, queue_history_size: int) -> None:
        self.short_term = short_term
        self.msgprocessor = msgprocessor
        self.queue_history_size = queue_history_size

    async def _build_reply_messages(
        self,
        conv_id: str,
        test_message: Optional[str] = None,
    ) -> Optional[list[dict]]:
        messages = await self.short_term.get_recent_messages(conv_id, self.queue_history_size)
        if not messages:
            logging.info(f"会话 {conv_id} 没有历史消息")
            return None

        if test_message:
            last_message = messages[-1].copy()
            last_message["content"] = test_message
            last_message["is_bot"] = False
            last_message["is_direct"] = True
            messages.append(last_message)

        return messages

    async def simulate_reply(self, conv_id: str, test_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            messages = await self._build_reply_messages(conv_id, test_message=test_message)
            if not messages:
                return None

            logging.info(f"开始为会话 {conv_id} 生成模拟回复，获取到 {len(messages)} 条历史消息")

            reply_content = await self.msgprocessor.generate_reply(conv_id, messages, temperature=0.7)

            if reply_content:
                logging.info(f"会话 {conv_id} 生成模拟回复成功: {reply_content[:30]}...")
                return {"reply_content": reply_content}

            logging.error(f"会话 {conv_id} 模拟回复内容为空")
            return None
        except Exception as e:
            logging.error(f"会话 {conv_id} 模拟回复异常: {e}")
            return None

    async def force_reply(self, conv_id: str, test_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            messages = await self._build_reply_messages(conv_id, test_message=test_message)
            if not messages:
                return None

            logging.info(f"开始为会话 {conv_id} 生成一次性回复，获取到 {len(messages)} 条历史消息")
            reply_content = await self.msgprocessor.generate_reply(conv_id, messages, temperature=0.7)
            if not reply_content:
                logging.error(f"会话 {conv_id} 一次性回复内容为空")
                return None

            await self.short_term.add_bot_message(conv_id, reply_content)
            split_replies = ConversationService._split_reply_content(reply_content)
            logging.info(f"会话 {conv_id} 一次性回复生成成功: {reply_content[:30]}...")
            return {
                "reply_content": split_replies or [reply_content],
                "raw_reply_content": reply_content,
            }
        except Exception as e:
            logging.error(f"会话 {conv_id} 一次性回复异常: {e}")
            return None
