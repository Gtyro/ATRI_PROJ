"""
消息队列存储库，处理短期记忆的存储和检索
使用Tortoise ORM管理数据
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from src.core.domain import PersonaConfig, PostgresConfig

from .message_models import MessageQueue


def _deep_merge_dict(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class MessageRepository:
    """消息队列存储库，处理短期记忆的存储和检索"""

    def __init__(self, config: Union[Dict[str, Any], PersonaConfig]):
        """初始化存储库

        Args:
            config: 配置字典，包含数据库配置
        """
        self.config = config
        self.db_url = self._get_db_url()
        self.is_initialized = False

    def _get_db_url(self) -> str:
        """根据配置获取数据库连接URL"""
        if isinstance(self.config, PersonaConfig):
            if self.config.use_postgres:
                pg_config = self.config.postgres_config or PostgresConfig()
                return (
                    f"postgres://{pg_config.user}:"
                    f"{pg_config.password}@"
                    f"{pg_config.host}:"
                    f"{pg_config.port}/"
                    f"{pg_config.database}"
                )
            db_path = self.config.db_path
            return f"sqlite://{db_path}"

        if self.config.get("use_postgres", False):
            pg_config = self.config.get("postgres_config", {})
            return (
                f"postgres://{pg_config.get('user', 'postgres')}:"
                f"{pg_config.get('password', 'postgres')}@"
                f"{pg_config.get('host', 'localhost')}:"
                f"{pg_config.get('port', 5432)}/"
                f"{pg_config.get('database', 'postgres')}"
            )
        db_path = self.config.get("db_path", "data/persona.db")
        return f"sqlite://{db_path}"

    async def initialize(self) -> None:
        """初始化存储库，仅标记状态"""
        try:
            # 设置初始化状态即可
            self.is_initialized = True
            logging.debug("消息队列存储库准备就绪")
        except Exception as e:
            logging.error(f"消息队列存储库准备失败: {e}")
            raise RuntimeError(f"存储库准备失败: {e}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.is_initialized:
            # 我们不在这里关闭连接，因为可能有其他组件还在使用
            # 连接将在程序终止时由db_manager关闭
            self.is_initialized = False
            logging.info("消息队列数据库连接已关闭")

    # === 消息队列相关操作 ===

    async def add_message(self, message_data: Dict) -> MessageQueue:
        """添加消息到队列"""
        message = await MessageQueue.create(**message_data)
        return message

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict]:
        """获取指定会话的未处理消息字典列表"""
        messages = (
            await MessageQueue.filter(conv_id=conv_id, is_processed=False)
            .order_by("created_at")
            .limit(limit)
            .all()
        )
        return [msg.to_dict() for msg in messages]

    async def get_recent_messages(self, conv_id: str, limit: int = 40) -> List[Dict]:
        """按照创建时间升序返回指定会话最近的limit条消息"""
        # 直接获取最近的limit条消息（按时间倒序）
        messages = (
            await MessageQueue.filter(conv_id=conv_id)
            .order_by("-created_at")
            .limit(limit)
            .all()
        )

        # 反转列表得到正确的时间顺序
        return [msg.to_dict() for msg in reversed(messages)]

    async def mark_messages_processed(self, message_ids: List[int]) -> int:
        """标记消息为已处理"""
        update_values = {
            "is_processed": True,
        }
        try:
            # 批量更新时会自动处理None值
            return await MessageQueue.filter(id__in=message_ids).update(**update_values)
        except Exception as e:
            logging.error(f"批量标记消息失败: {e}")
            return 0

    async def remove_old_messages(self, conv_id: str, keep_count: int = 40) -> int:
        """移除旧消息，仅保留最近 keep_count 条。

        Args:
            conv_id: 会话ID
            keep_count: 最少保留的消息数量

        Returns:
            移除的消息数量
        """
        keep_ids = await (
            MessageQueue.filter(conv_id=conv_id)
            .order_by("-created_at")
            .limit(keep_count)
            .values_list("id", flat=True)
        )
        if not keep_ids:
            return 0

        deleted = await MessageQueue.filter(conv_id=conv_id).exclude(id__in=list(keep_ids)).delete()

        logging.info(f"移除旧消息: {deleted} 条，仅保留最近 {keep_count} 条")
        return deleted

    async def cleanup_stale_messages(
        self,
        *,
        keep_count: int = 40,
        max_age_days: int = 1,
    ) -> int:
        """清理过期消息，保留最新 keep_count 条。

        规则：删除创建时间超过 max_age_days 的消息，但每个会话至少保留最近 keep_count 条。
        """
        try:
            conv_ids = await MessageQueue.all().distinct().values_list("conv_id", flat=True)
            if not conv_ids:
                return 0

            cutoff = datetime.utcnow() - timedelta(days=max_age_days)
            total_deleted = 0
            for conv_id in conv_ids:
                keep_ids = await (
                    MessageQueue.filter(conv_id=conv_id)
                    .order_by("-created_at")
                    .limit(keep_count)
                    .values_list("id", flat=True)
                )
                query = MessageQueue.filter(conv_id=conv_id, created_at__lt=cutoff)
                if keep_ids:
                    query = query.exclude(id__in=list(keep_ids))
                deleted = await query.delete()
                total_deleted += deleted

            logging.info(
                f"短期记忆过期清理完成: 删除 {total_deleted} 条（保留每会话 {keep_count} 条）"
            )
            return total_deleted
        except Exception as e:
            logging.error(f"短期记忆过期清理失败: {e}")
            return 0

    async def get_queue_stats(self, conv_id: Optional[str] = None) -> Dict[str, Any]:
        """获取队列统计信息

        Args:
            conv_id: 可选的会话ID，如果指定则只返回该会话的统计
        """
        # 如果指定了conv_id，只获取该会话的统计
        if conv_id:
            total = await MessageQueue.filter(conv_id=conv_id).count()
            unprocessed = await MessageQueue.filter(conv_id=conv_id, is_processed=False).count()
            return {
                "total_messages": total,
                "unprocessed_messages": unprocessed,
            }

        # 否则获取全局统计
        total = await MessageQueue.all().count()
        unprocessed = await MessageQueue.filter(is_processed=False).count()
        return {
            "total_messages": total,
            "unprocessed_messages": unprocessed,
        }

    async def has_bot_message(self, conv_id: str) -> bool:
        """判断队列中是否有机器人发的消息，不论是否已处理"""
        count = await MessageQueue.filter(conv_id=conv_id, is_bot=True).count()
        return count > 0

    async def update_message_metadata(self, message_id: int, metadata: Dict[str, Any]) -> bool:
        """更新消息 metadata，默认与已有 metadata 深合并。"""
        if not isinstance(metadata, dict):
            logging.warning(
                f"update_message_metadata 收到非字典 metadata，已降级为 value 包装: message_id={message_id}"
            )
            metadata = {"value": metadata}

        try:
            message = await MessageQueue.get_or_none(id=message_id)
            if message is None:
                logging.warning(f"更新消息 metadata 失败，消息不存在: message_id={message_id}")
                return False

            current_metadata = message.metadata if isinstance(message.metadata, dict) else {}
            merged_metadata = _deep_merge_dict(current_metadata, metadata)
            updated = await MessageQueue.filter(id=message_id).update(metadata=merged_metadata)
            return updated > 0
        except Exception as e:
            logging.error(f"更新消息 metadata 失败: message_id={message_id} error={e}")
            return False

    async def _has_processed_message(self, conv_id: str) -> bool:
        """判断队列中是否有已处理消息"""
        count = await MessageQueue.filter(conv_id=conv_id, is_processed=True).count()
        return count > 0

    async def delete_messages_by_time_range(
        self,
        conv_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """删除指定会话时间范围内的消息

        Args:
            conv_id: 会话ID
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            删除的消息数量
        """
        try:
            deleted = await MessageQueue.filter(
                conv_id=conv_id,
                created_at__gte=start_time,
                created_at__lte=end_time + timedelta(seconds=1),
            ).delete()

            logging.info(f"会话 {conv_id} 删除了时间在 {start_time} 到 {end_time} 之间的消息共 {deleted} 条")
            return deleted
        except Exception as e:
            logging.error(f"删除会话 {conv_id} 的消息失败: {e}")
            return 0

    async def clear_messages(self, conv_id: str) -> int:
        """清空指定会话的消息队列"""
        try:
            deleted = await MessageQueue.filter(conv_id=conv_id).delete()
            logging.info(f"会话 {conv_id} 已清空消息队列，共删除 {deleted} 条")
            return deleted
        except Exception as e:
            logging.error(f"清空会话 {conv_id} 的消息队列失败: {e}")
            return 0


__all__ = ["MessageRepository"]
