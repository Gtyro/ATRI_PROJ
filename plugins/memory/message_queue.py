"""
记忆系统消息队列模块 - 管理消息的队列和批处理

该模块负责将接收到的消息进行排队，并根据不同优先级进行处理：
1. 高优先级消息（私聊、@机器人）：立即处理
2. 普通消息：加入队列，定时批量处理
"""

import time
import asyncio
import logging
from typing import Dict, List, Tuple, Optional, Set, Any

from .storage import StorageManager
from .processor import MemoryProcessor

class MessageQueue:
    """消息队列管理器"""
    
    def __init__(self, storage: StorageManager, processor: MemoryProcessor, 
                 batch_interval: int = 3600):
        """初始化消息队列
        
        Args:
            storage: 存储管理器
            processor: 处理器
            batch_interval: 定时处理间隔（秒），默认1小时
        """
        self.storage = storage
        self.processor = processor
        self.batch_interval = batch_interval
        self.next_process_time = time.time() + batch_interval
        self.processing_lock = asyncio.Lock()
        
    async def add_message(self, user_id: str, message: str, 
                          context: str, is_priority: bool = False) -> Optional[str]:
        """添加消息到队列
        
        Args:
            user_id: 用户ID
            message: 消息内容
            context: 上下文标识（如"group_123456"）
            is_priority: 是否为优先消息
            
        Returns:
            如果是优先消息立即处理并返回记忆ID，否则返回None
        """
        # 提取分组信息（群组ID）
        group_id = context.split('_')[1] if '_' in context else user_id
        
        
        # 普通消息加入队列
        id = await self._enqueue_message(user_id, message, context, group_id)

        # 优先消息处理
        if is_priority:
            # 重置处理时间
            self.next_process_time = time.time() + self.batch_interval
            
            # 先处理该群聊/用户的历史消息队列
            await self._process_group_queue(group_id)
            
            # 立即处理此消息
            await self._process_message(user_id, message, context)
        
        return id
    
    async def _enqueue_message(self, user_id: str, message: str, 
                              context: str, group_id: str) -> None:
        """将消息加入队列"""
        try:
            await self.storage.add_to_queue({
                "user_id": user_id,
                "content": message,
                "context": context,
                "group_id": group_id,
                "created_at": time.time()
            })
            logging.debug(f"消息已加入队列: {user_id} - {message[:20]}...")
            return None
        except Exception as e:
            logging.error(f"加入队列失败: {e}")
            return None
    
    async def _process_message(self, user_id: str, message: str, context: str) -> Optional[str]:
        """处理单条消息"""
        try:
            memory_data = await self.processor.process_message(user_id, message, context)
            memory_id = await self.storage.add_memory(memory_data)
            logging.info(f"消息已添加: {user_id} - {message[:20]}...，记忆ID: {memory_id}")
            return memory_id
        except Exception as e:
            logging.error(f"消息处理失败: {e}")
            return None
    
    async def _process_group_queue(self, group_id: str, max_items: int = 100) -> int:
        """处理特定群组/用户的队列消息
        
        Args:
            group_id: 群组ID
            max_items: 单次最大处理条数
            
        Returns:
            处理的消息数量
        """
        try:
            # 获取该群组/用户在队列中的消息
            group_items = await self.storage.get_group_queue_items(group_id)
            if not group_items:
                logging.info(f"群组/用户 {group_id} 队列为空，无需处理")
                return 0
            
            # 不再逐条处理，而是批量处理整个群组的消息
            if len(group_items) > 0:
                # 将队列消息批量提交给处理器
                await self._process_group_batch(group_id, group_items)
                
                # 处理完成后，移除所有已处理的消息
                for item in group_items:
                    await self.storage.remove_from_queue(item["id"])
                    
            logging.info(f"群组/用户 {group_id} 队列处理完成，共处理 {len(group_items)} 条消息")
            return len(group_items)
        except Exception as e:
            logging.error(f"处理群组/用户队列异常: {e}")
            return 0

    async def _process_group_batch(self, group_id: str, message_items: List[Dict]) -> None:
        """批量处理群组消息，提取话题和交互模式"""
        try:
            # 准备批量消息数据
            group_data = []
            for item in message_items:
                group_data.append({
                    "user_id": item["user_id"],
                    "content": item["content"],
                    "timestamp": item.get("created_at", time.time())
                })
                
            # 批量处理群组数据
            group_topics = await self.processor.process_conversation(group_id, group_data)
            
            # 将话题记忆保存到数据库
            for topic in group_topics:
                await self.storage.add_group_topic(group_id, topic)
                
            logging.info(f"群组 {group_id} 批量处理完成，提取了 {len(group_topics)} 个话题")
        except Exception as e:
            logging.error(f"批量处理群组异常: {e}")

    async def process_queue(self, max_items: int = 100) -> int:
        """处理队列中的消息
        
        Args:
            max_items: 单次最大处理条数
            
        Returns:
            处理的消息数量
        """
        # 使用锁防止并发处理
        async with self.processing_lock:
            current_time = time.time()
            
            # 如果还没到处理时间，跳过
            if current_time < self.next_process_time:
                remaining = int(self.next_process_time - current_time)
                logging.debug(f"距离下次定时处理还有 {remaining} 秒")
                return 0
            
            logging.info("开始处理消息队列...")
            processed_count = 0
            
            try:
                # 获取队列中的消息
                queue_items = await self.storage.get_queue_items(max_items)
                if not queue_items:
                    logging.info("队列为空，无需处理")
                    self.next_process_time = current_time + self.batch_interval
                    return 0
                
                # 直接按创建时间处理所有消息
                for item in queue_items:
                    await self._process_message(
                        item["user_id"], 
                        item["content"], 
                        item["context"]
                    )
                    await self.storage.remove_from_queue(item["id"])
                    processed_count += 1
                
                logging.info(f"队列处理完成，共处理 {processed_count} 条消息")
                
            except Exception as e:
                logging.error(f"处理队列异常: {e}")
            
            # 更新下次处理时间
            self.next_process_time = current_time + self.batch_interval
            return processed_count 