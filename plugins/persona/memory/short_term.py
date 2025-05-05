import logging
import time
from typing import Dict, List, Optional, Any, Callable

from ..storage.repository import Repository

class ShortTermMemory:
    """短期记忆管理器
    
    负责管理消息队列作为机器人的短期记忆
    """
    
    def __init__(self, repository: Repository, config: Dict[str, Any] = None):
        """初始化短期记忆管理器
        
        Args:
            repository: 存储仓库
            config: 配置参数
        """
        self.repository = repository
        self.config = config or {}
        self.batch_interval = self.config.get("batch_interval", 3600)  # 默认1小时
        self.queue_history_size = self.config.get("queue_history_size", 100)
        self.next_process_time = time.time() + self.batch_interval
        self.reply_callback = None
        logging.info(f"短期记忆管理器已创建，批处理间隔: {self.batch_interval}秒")
    
    def register_reply_callback(self, callback: Callable) -> None:
        """注册回复回调函数"""
        self.reply_callback = callback
        logging.info("短期记忆管理器已注册回复回调函数")
    
    async def add_message(self, message_data: Dict) -> int:
        """添加消息到队列
        
        Args:
            message_data: 消息数据
            
        Returns:
            消息ID
        """
        message = await self.repository.add_message(message_data)
        logging.info(f"已添加消息到队列: {message.id}")
        return message.id
    
    async def add_bot_message(self, conv_id: str, content: str) -> int:
        """添加机器人自己的消息到队列
        
        Args:
            conv_id: 会话ID
            content: 消息内容
            
        Returns:
            消息ID
        """
        message_data = { # 此处有7个字段+自动生成的id和created_at+metadata
            "conv_id": conv_id,
            "user_id": "bot",
            "user_name": "你", # 使用第二人称
            "content": content,
            "is_bot": True,
            "is_processed": False,
            "is_direct": False
        }
        return await self.add_message(message_data)
    
    async def get_unprocessed_messages(self, conv_id: str, limit: int) -> List[Dict]:
        """获取未处理的消息字典列表"""
        return await self.repository.get_unprocessed_messages(conv_id, limit)
    
    async def get_recent_messages(self, conv_id: str, limit: int = 40) -> List[Dict]:
        """获取最近的消息，按时间从前往后排序"""
        return await self.repository.get_recent_messages(conv_id, limit)
    
    async def mark_processed(self, conv_id: str, memories: List[Dict]) -> int:
        """标记消息为已处理
        
        根据记忆列表中的message_ids标记对应消息为已处理
        
        Args:
            conv_id: 会话ID
            memories: 记忆列表
            
        Returns:
            标记的消息数量
        """
        marked_count = 0
        
        # 从记忆中收集所有消息ID
        for memory in memories:
            if not memory["completed_status"]:
                continue
            message_ids = memory["message_ids"]
            if message_ids:
                count = await self.repository.mark_messages_processed(message_ids)
                marked_count += count
        logging.info(f"标记消息为已处理: {marked_count} 条")
        
        # 清理过多的历史消息
        await self.clean_history(conv_id)
        
        return marked_count
    
    async def clean_history(self, conv_id: str) -> int:
        """清理历史消息，保留最新的queue_history_size条
        
        Args:
            conv_id: 会话ID
            
        Returns:
            删除的消息数量
        """
        return await self.repository.remove_old_messages(conv_id, self.queue_history_size)
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        stats = await self.repository.get_queue_stats()
        stats["next_process_in"] = max(0, int(self.next_process_time - time.time()))
        stats["batch_interval"] = self.batch_interval
        return stats 