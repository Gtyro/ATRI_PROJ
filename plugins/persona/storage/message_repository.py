"""
消息队列存储库，处理短期记忆的存储和检索
使用Tortoise ORM管理数据
"""

import logging
from typing import Dict, List, Optional, Any
from tortoise import Tortoise
from datetime import datetime

from .message_models import MessageQueue

class MessageRepository:
    """消息队列存储库，处理短期记忆的存储和检索"""

    def __init__(self, config: Dict[str, Any]):
        """初始化存储库
        
        Args:
            config: 配置字典，包含数据库配置
        """
        self.config = config
        self.db_url = self._get_db_url()
        self.is_initialized = False
        logging.info("消息队列存储库已创建，等待初始化")

    def _get_db_url(self) -> str:
        """根据配置获取数据库连接URL"""
        if self.config.get("use_postgres", False):
            pg_config = self.config.get("postgres_config", {})
            return (
                f"postgres://{pg_config.get('user', 'postgres')}:"
                f"{pg_config.get('password', 'postgres')}@"
                f"{pg_config.get('host', 'localhost')}:"
                f"{pg_config.get('port', 5432)}/"
                f"{pg_config.get('database', 'postgres')}"
            )
        else:
            db_path = self.config.get("db_path", "data/persona.db")
            return f"sqlite://{db_path}"

    async def initialize(self) -> None:
        """初始化数据库连接和模型"""
        try:
            await Tortoise.init(
                db_url=self.db_url,
                modules={"models": ["plugins.persona.storage.message_models", "plugins.models"]}
            )
            await Tortoise.generate_schemas()
            self.is_initialized = True
            logging.info(f"消息队列数据库已初始化: {self.db_url}")
        except Exception as e:
            logging.error(f"消息队列数据库初始化失败: {e}")
            raise RuntimeError(f"数据库初始化失败: {e}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.is_initialized:
            await Tortoise.close_connections()
            self.is_initialized = False
            logging.info("消息队列数据库连接已关闭")

    # === 消息队列相关操作 ===

    async def add_message(self, message_data: Dict) -> MessageQueue:
        """添加消息到队列"""
        message = await MessageQueue.create(**message_data)
        return message

    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict]:
        """获取指定会话的未处理消息字典列表"""
        messages = await MessageQueue.filter(conv_id=conv_id, is_processed=False).order_by("created_at").limit(limit).all()
        return [msg.to_dict() for msg in messages]

    async def get_recent_messages(self, conv_id: str, limit: int = 40) -> List[Dict]:
        """按照创建时间升序返回指定会话最近的limit条消息"""
        # 直接获取最近的limit条消息（按时间倒序）
        messages = await MessageQueue.filter(
            conv_id=conv_id
        ).order_by("-created_at").limit(limit).all()

        # 反转列表得到正确的时间顺序
        return [msg.to_dict() for msg in reversed(messages)]

    async def mark_messages_processed(self, message_ids: List[int]) -> int:
        """标记消息为已处理"""
        update_values = {
            "is_processed": True
        }
        try:
            # 批量更新时会自动处理None值
            return await MessageQueue.filter(id__in=message_ids).update(**update_values)
        except Exception as e:
            logging.error(f"批量标记消息失败: {e}")
            return 0

    async def remove_old_messages(self, conv_id: str, keep_count: int = 40) -> int:
        """移除旧消息，基于时间阈值策略
        
        Args:
            conv_id: 会话ID
            keep_count: 最少保留的消息数量
            
        Returns:
            移除的消息数量
        """
        # 获取最新的已处理消息
        latest_processed = await MessageQueue.filter(
            conv_id=conv_id,
            is_processed=True
        ).order_by("-created_at").first()

        # 获取第keep_count+1条消息
        threshold_msg = await MessageQueue.filter(
            conv_id=conv_id
        ).order_by("-created_at").offset(keep_count).first()

        if not latest_processed or not threshold_msg:
            return 0

        # 确定时间阈值
        time_threshold = min(latest_processed.created_at, threshold_msg.created_at)

        # 删除早于等于阈值的消息
        deleted = await MessageQueue.filter(
            conv_id=conv_id,
            created_at__lte=time_threshold
        ).delete()

        logging.info(f"移除旧消息: {deleted} 条，基于双重时间阈值策略")
        return deleted

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
                "unprocessed_messages": unprocessed
            }

        # 否则获取全局统计
        total = await MessageQueue.all().count()
        unprocessed = await MessageQueue.filter(is_processed=False).count()
        return {
            "total_messages": total,
            "unprocessed_messages": unprocessed
        }

    async def has_bot_message(self, conv_id: str) -> bool:
        """判断队列中是否有机器人发的消息，不论是否已处理"""
        count = await MessageQueue.filter(conv_id=conv_id, is_bot=True).count()
        return count > 0

    async def _has_processed_message(self, conv_id: str) -> bool:
        """判断队列中是否有已处理消息"""
        count = await MessageQueue.filter(conv_id=conv_id, is_processed=True).count()
        return count > 0

    async def delete_messages_by_time_range(self, conv_id: str, start_time: datetime, end_time: datetime) -> int:
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
                created_at__lte=end_time
            ).delete()
            
            logging.info(f"会话 {conv_id} 删除了时间在 {start_time} 到 {end_time} 之间的消息共 {deleted} 条")
            return deleted
        except Exception as e:
            logging.error(f"删除会话 {conv_id} 的消息失败: {e}")
            return 0 