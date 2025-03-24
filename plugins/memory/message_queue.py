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
        self.priority_groups: Set[str] = set()  # 优先处理的群组/用户
        
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
        # 提取分组信息（群组ID或用户ID）
        group_id = context.split('_')[1] if '_' in context else user_id
        
        # 优先消息直接处理
        if is_priority:
            # 将此分组添加到优先处理组
            self.priority_groups.add(group_id)
            # 重置处理时间
            self.next_process_time = time.time() + self.batch_interval
            # 立即处理此消息
            return await self._process_message(user_id, message, context)
        
        # 普通消息加入队列
        return await self._enqueue_message(user_id, message, context, group_id)
    
    async def _enqueue_message(self, user_id: str, message: str, 
                              context: str, group_id: str) -> None:
        """将消息加入队列"""
        try:
            await self.storage.add_to_queue({
                "user_id": user_id,
                "content": message,
                "context": context,
                "group_id": group_id,
                "created_at": time.time(),
                "priority": 1 if group_id in self.priority_groups else 0
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
                
                # 按优先级分组处理
                priority_items = []
                normal_items = []
                
                for item in queue_items:
                    if item["priority"] > 0 or item["group_id"] in self.priority_groups:
                        priority_items.append(item)
                    else:
                        normal_items.append(item)
                
                # 先处理优先消息
                for item in priority_items:
                    await self._process_message(
                        item["user_id"], 
                        item["content"], 
                        item["context"]
                    )
                    await self.storage.remove_from_queue(item["id"])
                    processed_count += 1
                
                # 再处理普通消息
                for item in normal_items:
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