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
        
    async def add_message(self, user_id: str, user_name: str, message: str, 
                          context: str, is_priority: bool = False, is_tome: bool = False) -> Optional[str]:
        """添加消息到队列, 如果是优先消息立即处理
        
        Args:
            user_id: 用户ID
            user_name: 用户昵称
            message: 消息内容
            context: 上下文标识（如"group_123456"）
            is_priority: 是否为优先消息
            is_tome: 是否为@机器人消息
        Returns:
            如果是优先消息立即处理并返回记忆ID，否则返回None
        """
        # 提取分组信息（群组ID）
        group_id = context.split('_')[1]
        
        
        # 消息先加入队列
        id = await self._enqueue_message(user_id, user_name, message, context, group_id, is_tome)

        # 优先消息处理
        if is_priority:
            # 重置处理时间
            self.next_process_time = time.time() + self.batch_interval
            
            # 先处理该群聊/用户的历史消息队列
            await self._process_group_queue(group_id)
            
            # 立即处理此消息
            # await self._process_message(user_id, message, context)
        
        return id
    
    async def _enqueue_message(self, user_id: str, user_name: str, message: str, 
                              context: str, group_id: str, is_tome: bool) -> None:
        """将消息加入队列"""
        try:
            await self.storage.add_to_queue({
                "user_id": user_id,
                "user_name": user_name,
                "content": message,
                "context": context,
                "group_id": group_id,
                "created_at": time.time(),
                "is_tome": is_tome
            })
            logging.debug(f"消息已加入队列: {user_id} - {message[:20]}...")
            return None
        except Exception as e:
            logging.error(f"加入队列失败: {e}")
            return None
    
    async def _process_group_queue(self, group_id: str) -> int:
        """处理特定群组/用户的队列消息
        
        Args:
            group_id: 群组ID
            
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
                # 将队列消息批量提交给处理器，并获取已完结和未完结消息ID
                completed_ids, ongoing_ids = await self._process_group_batch(group_id, group_items)
                
                # 构建序号ID到数据库ID的映射
                seq_to_db_id = {item.get("seq_id", 0): item["id"] for item in group_items}
                
                # 收集要删除的消息数据库ID
                completed_db_ids = [seq_to_db_id.get(seq_id) for seq_id in completed_ids if seq_id in seq_to_db_id]
                
                # 只删除已完结话题的消息
                if completed_db_ids:
                    deleted_count = await self.storage.remove_from_queue(completed_db_ids)
                    if deleted_count != len(completed_db_ids):
                        logging.warning(f"队列消息删除不完全，应删除{len(completed_db_ids)}条，实际删除{deleted_count}条")
                
                # 计算已处理的总消息数
                processed_count = len(completed_ids)
                
                # 记录处理情况
                if ongoing_ids:
                    ongoing_db_ids = [seq_to_db_id.get(seq_id) for seq_id in ongoing_ids if seq_id in seq_to_db_id]
                    logging.info(f"保留 {len(ongoing_db_ids)} 条未完结话题消息在队列中")
                    
            else:
                processed_count = 0
                
            logging.info(f"群组/用户 {group_id} 队列处理完成，处理 {processed_count} 条消息")
            return processed_count
        except Exception as e:
            logging.error(f"处理群组/用户队列异常: {e}")
            return 0

    async def _process_group_batch(self, group_id: str, message_items: List[Dict]) -> Tuple[List[int], List[int]]:
        """批量处理群组消息，提取话题和交互模式
        
        Args:
            group_id: 群组ID
            message_items: 消息列表
            
        Returns:
            元组 (已完结消息ID列表, 未完结消息ID列表)
        """
        try:
            # 准备批量消息数据
            group_data = []
            for idx, item in enumerate(message_items, 1):
                # 为消息添加序号ID（仅在内部使用）
                item["seq_id"] = idx
                group_data.append({
                    "user_id": item["user_id"],
                    "user_name": item["user_name"],
                    "content": item["content"],
                    "timestamp": item.get("created_at", time.time())
                })
                
            # 批量处理群组数据
            group_topics = await self.processor.process_conversation(group_id, group_data)
            logging.info(f"提取的话题: {len(group_topics)}个")
            
            # 群组上下文
            context = f"group_{group_id}"
            
            # 用于存储已完结和未完结的消息ID
            completed_message_ids = set()
            ongoing_message_ids = set()
            
            # 将话题记忆保存到数据库并更新实体关联
            for topic in group_topics:
                topic_status = topic.get("status", "completed")  # 默认为已完结
                topic_message_ids = topic.get("message_ids", [])
                
                # 根据话题状态处理
                if topic_status == "completed":
                    # 已完结话题：保存到数据库并跟踪消息ID
                    topic_id = await self.storage.add_conversation_topic(context, topic)
                    logging.debug(f"已保存完结话题: {topic.get('topic')}，ID: {topic_id}")
                    
                    # 将该话题关联的消息ID添加到已完结集合
                    completed_message_ids.update(topic_message_ids)
                else:
                    # 未完结话题：不保存，但跟踪消息ID
                    logging.debug(f"识别到未完结话题: {topic.get('topic')}")
                    ongoing_message_ids.update(topic_message_ids)
            
            # 消息可能同时属于已完结和未完结话题，需要从已完结中排除未完结的
            # 最终要删除的消息ID = 已完结消息 - 未完结消息
            final_completed_ids = completed_message_ids - ongoing_message_ids
            
            # 转换为列表
            completed_ids_list = list(final_completed_ids)
            ongoing_ids_list = list(ongoing_message_ids)
            
            # 记录统计信息
            logging.info(f"群组 {group_id} 批量处理完成:")
            logging.info(f"- 总消息数: {len(message_items)}")
            logging.info(f"- 已完结话题消息: {len(completed_ids_list)}")
            logging.info(f"- 未完结话题消息: {len(ongoing_ids_list)}")
            
            return (completed_ids_list, ongoing_ids_list)
        except Exception as e:
            logging.error(f"批量处理群组异常: {e}")
            logging.exception(e)  # 输出完整异常堆栈信息
            return ([], [])

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
            total_processed_count = 0
            
            try:
                # 获取队列中的消息
                queue_items = await self.storage.get_queue_items(max_items)
                if not queue_items:
                    logging.info("队列为空，无需处理")
                    self.next_process_time = current_time + self.batch_interval
                    return 0
                
                # 按群组/用户分组消息
                group_messages = {}
                for item in queue_items:
                    group_id = item.get("group_id", "default")
                    if group_id not in group_messages:
                        group_messages[group_id] = []
                    group_messages[group_id].append(item)
                
                # 对每个群组单独处理
                # 这里改为按群组单独处理和删除，更符合话题划分逻辑
                for group_id, items in group_messages.items():
                    if items:
                        # 处理一个群组并获取该群组已处理的消息数
                        processed_count = await self._process_group_queue(group_id)
                        total_processed_count += processed_count
                
                logging.info(f"队列处理完成，共处理 {total_processed_count} 条消息，涉及 {len(group_messages)} 个群组/用户")
                
            except Exception as e:
                logging.error(f"处理队列异常: {e}")
            
            # 更新下次处理时间
            self.next_process_time = current_time + self.batch_interval
            return total_processed_count 