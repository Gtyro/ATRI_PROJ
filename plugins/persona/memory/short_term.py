"""
短期记忆管理器

负责处理消息队列，包括添加、获取和标记消息等功能
"""

import logging
from time import time
from typing import Any, Dict, List, Optional

from ..storage.message_repository import MessageRepository


class ShortTermMemory:
    """短期记忆管理器

    负责处理消息队列，包括添加、获取和标记消息等功能
    """

    def __init__(self, message_repo: MessageRepository, config: Dict[str, Any]):
        """初始化短期记忆管理器

        Args:
            message_repo: 消息存储库
            config: 配置参数
        """
        self.message_repo = message_repo
        self.config = config

    async def add_message(self, message_data: Dict) -> None:
        """添加消息到短期记忆

        Args:
            message_data: 消息数据
        """
        await self.message_repo.add_message(message_data)

    async def add_bot_message(self, conv_id: str, content: str) -> None:
        """添加机器人自己的消息到历史

        Args:
            conv_id: 会话ID
            content: 消息内容
        """
        message_data = {
            "conv_id": conv_id,
            "user_id": "bot",
            "user_name": "机器人",
            "content": content,
            "is_direct": False,
            "is_bot": True,
            "is_processed": True,
            "extra_data": {}
        }
        await self.message_repo.add_message(message_data)

    async def get_unprocessed_messages(self, conv_id: str, limit: int = 20) -> List[Dict]:
        """获取未处理的消息

        Args:
            conv_id: 会话ID
            limit: 返回消息数量限制

        Returns:
            未处理消息列表
        """
        return await self.message_repo.get_unprocessed_messages(conv_id, limit)

    async def get_recent_messages(self, conv_id: str, limit: int = 40) -> List[Dict]:
        """获取最近的消息

        Args:
            conv_id: 会话ID
            limit: 返回消息数量限制

        Returns:
            最近消息列表
        """
        return await self.message_repo.get_recent_messages(conv_id, limit)

    async def mark_processed(self, conv_id: str, processed_topics: List[Dict]) -> int:
        """标记消息为已处理

        Args:
            conv_id: 会话ID
            processed_topics: 已处理的话题列表，包含消息ID

        Returns:
            标记的消息数量
        """
        message_ids = []
        for topic in processed_topics:
            # 检查话题是否已完成，与原实现保持一致
            if not topic.get("completed_status", False):
                continue

            if "message_ids" in topic:
                message_ids.extend(topic["message_ids"])

        if not message_ids:
            return 0

        num_marked = await self.message_repo.mark_messages_processed(message_ids)

        # 顺便清理旧消息
        await self.remove_old_messages(conv_id)

        return num_marked

    async def remove_old_messages(self, conv_id: str) -> int:
        """移除旧消息

        Args:
            conv_id: 会话ID

        Returns:
            移除的消息数量
        """
        keep_count = self.config.get("queue_history_size", 40)
        return await self.message_repo.remove_old_messages(conv_id, keep_count)