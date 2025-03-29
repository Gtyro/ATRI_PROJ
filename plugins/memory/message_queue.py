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
        
        # 回调处理器
        self.reply_callback = None
        # 最近发送过自动回复的话题，避免重复回复
        self.recent_replied_topics = set()
        # 自动回复阈值 (当随机值小于话题的continuation_probability时触发回复)
        self.auto_reply_threshold = 0.5
        
    def register_reply_callback(self, callback):
        """注册回复回调函数
        
        Args:
            callback: 回调函数，接收 (group_id, topic_data) 参数
        """
        self.reply_callback = callback
        logging.info("已注册自动回复回调函数")
        
    async def trigger_auto_reply(self, group_id: str, topic: Dict) -> bool:
        """触发自动回复逻辑
        
        Args:
            group_id: 群组ID
            topic: 话题数据
            
        Returns:
            是否成功触发回复
        """
        if not self.reply_callback:
            return False
            
        # 构建话题标识符
        topic_id = f"{group_id}:{topic['topic']}"
        
        # 如果最近回复过，避免重复回复
        if topic_id in self.recent_replied_topics:
            logging.debug(f"话题 '{topic['topic']}' 最近已回复过，跳过")
            return False
            
        # 计算是否应该回复 (随机值 < continuation_probability)
        continuation_prob = float(topic.get("continuation_probability", 0))
        
        if continuation_prob < self.auto_reply_threshold:
            logging.debug(f"话题 '{topic['topic']}' 继续概率 {continuation_prob} 低于阈值 {self.auto_reply_threshold}，不回复")
            return False
            
        # 随机决定是否回复
        import random
        if random.random() > continuation_prob:
            logging.debug(f"话题 '{topic['topic']}' 随机决定不回复 (概率{continuation_prob})")
            return False
        
        try:
            # 获取相关消息内容
            message_contents = []
            related_users = set()
            last_user_id = None
            
            for msg_id in topic.get("message_ids", []):
                if isinstance(msg_id, int):
                    # 获取消息内容
                    message = await self.storage.get_message_by_seq_id(group_id, msg_id)
                    if message:
                        # 添加格式化消息
                        user_name = message.get("user_name", "未知用户")
                        user_id = message.get("user_id", "")
                        content = message.get("content", "")
                        message_contents.append(f"{user_name}: {content}")
                        
                        # 记录用户ID以便回复
                        if user_id and not message.get("is_me", False):
                            related_users.add(user_id)
                            last_user_id = user_id
            
            # 准备回复数据
            reply_data = {
                "group_id": group_id,
                "topic": topic["topic"],
                "entities": topic.get("entities", []),
                "message_ids": topic.get("message_ids", []),
                "continuation_probability": continuation_prob,
                "messages": message_contents,  # 添加消息内容
                "related_users": list(related_users),
                "last_user_id": last_user_id
            } 
            
            # 调用回调函数
            logging.info(f"触发自动回复: '{topic['topic']}' (概率: {continuation_prob})")
            response = await self.reply_callback(group_id, reply_data)
            
            # 如果回调返回了回复内容，添加到队列
            if isinstance(response, str) and response.strip():
                # 将回复添加到消息队列
                context = f"group_{group_id}"
                await self.add_bot_message(response, context, last_user_id)
            
            # 添加到最近回复集合
            self.recent_replied_topics.add(topic_id)
            
            # 为避免内存泄漏，控制集合大小
            if len(self.recent_replied_topics) > 100:
                self.recent_replied_topics = set(list(self.recent_replied_topics)[-50:])
                
            return True
        except Exception as e:
            logging.error(f"触发自动回复失败: {e}")
            return False
    
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
        group_id = context.split('_')[1] if '_' in context else user_id
        
        # 消息先加入队列
        message_id = await self._enqueue_message(user_id, user_name, message, context, group_id, is_tome)

        # 优先消息处理
        if is_priority or is_tome:
            # 重置处理时间
            self.next_process_time = time.time() + self.batch_interval
            
            # 先处理该群聊/用户的历史消息队列
            await self._process_group_queue(group_id)
        
        return message_id
    
    async def _enqueue_message(self, user_id: str, user_name: str, message: str, 
                              context: str, group_id: str, is_tome: bool = False, 
                              is_me: bool = False, reply_to: Optional[str] = None) -> None:
        """将消息加入队列
        
        Args:
            user_id: 用户ID
            user_name: 用户昵称
            message: 消息内容
            context: 上下文标识
            group_id: 群组ID
            is_tome: 是否发给机器人的消息
            is_me: 是否机器人发的消息
            reply_to: 回复的用户ID
        """
        try:
            # 构建metadata保存额外信息
            metadata = {}
            if reply_to:
                metadata["reply_to"] = reply_to
                
            await self.storage.add_to_queue({
                "user_id": user_id,
                "user_name": user_name,
                "content": message,
                "context": context,
                "group_id": group_id,
                "created_at": time.time(),
                "is_tome": is_tome,
                "is_me": is_me,
                "metadata": metadata
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
                # 检查是否有直接交互标志
                is_tome = item.get("is_tome", False)
                group_data.append({
                    "user_id": item["user_id"],
                    "user_name": item["user_name"],
                    "content": item["content"],
                    "timestamp": item.get("created_at", time.time()),
                    "is_tome": is_tome
                })
                
            # 批量处理群组数据
            group_topics = await self.processor.process_conversation(group_id, group_data)
            logging.info(f"提取的话题: {len(group_topics)}个")
            
            # 群组上下文
            context = f"group_{group_id}"
            
            # 用于存储已完结和未完结的消息ID
            completed_message_ids = set()
            ongoing_message_ids = set()
            
            # 保存话题记忆
            for topic in group_topics:
                is_concluded = topic.get("is_concluded", True)
                topic_id = topic.get("id")
                
                # 记录消息ID
                message_ids = topic.get("message_ids", [])
                
                # 检查话题是否包含直接交互的消息
                is_tome_topic = any(
                    message_items[msg_id-1].get("is_tome", False) 
                    for msg_id in message_ids 
                    if 1 <= msg_id <= len(message_items)
                )
                
                # 向话题添加直接交互的标志
                topic["is_tome"] = is_tome_topic
                
                if not is_concluded:
                    # 未完结话题，需要保留相关消息ID
                    for msg_id in message_ids:
                        ongoing_message_ids.add(msg_id)
                        
                    # 计算自动回复概率
                    await self.trigger_auto_reply(group_id, topic)
                else:
                    # 已完结话题，可以删除消息
                    for msg_id in message_ids:
                        if msg_id not in ongoing_message_ids:  # 避免重复添加到不同集合
                            completed_message_ids.add(msg_id)
                            
                # 保存话题
                await self.storage.add_conversation_topic(context, topic)
                
            # 对集合排序，便于日志打印和调试
            completed_ids_list = sorted(list(completed_message_ids))
            ongoing_ids_list = sorted(list(ongoing_message_ids))
            
            logging.info(f"话题处理结果:")
            logging.info(f"- 已完结话题消息: {len(completed_ids_list)}")
            logging.info(f"- 未完结话题消息: {len(ongoing_ids_list)}")
            
            return (completed_ids_list, ongoing_ids_list)
        except Exception as e:
            logging.error(f"批量处理群组异常: {e}")
            logging.exception(e)  # 输出完整异常堆栈信息
            return ([], [])

    async def process_queue(self, max_items_per_group: int = 100) -> int:
        """处理队列中的消息
        
        Args:
            max_items_per_group: 每个群组最大处理条数
            
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
                # 直接获取所有需要处理的不同群组ID
                distinct_groups = await self.storage.get_distinct_group_ids()
                
                if not distinct_groups:
                    logging.info("队列为空，无需处理")
                    self.next_process_time = current_time + self.batch_interval
                    return 0
                
                logging.info(f"发现 {len(distinct_groups)} 个不同群组/用户的消息")
                
                # 对每个群组单独处理
                for group_id in distinct_groups:
                    if group_id:  # 确保群组ID有效
                        # 处理一个群组并获取该群组已处理的消息数
                        processed_count = await self._process_group_queue(group_id)
                        total_processed_count += processed_count
                
                logging.info(f"队列处理完成，共处理 {total_processed_count} 条消息，涉及 {len(distinct_groups)} 个群组/用户")
                
            except Exception as e:
                logging.error(f"处理队列异常: {e}")
            
            # 更新下次处理时间
            self.next_process_time = current_time + self.batch_interval
            return total_processed_count

    async def add_bot_message(self, message: str, context: str, in_reply_to: Optional[str] = None) -> Optional[str]:
        """添加机器人回复消息到队列
        
        Args:
            message: 消息内容
            context: 上下文标识（如"group_123456"）
            in_reply_to: 所回复消息的用户ID（可选）
            
        Returns:
            消息队列项ID
        """
        # 机器人ID和名称（可根据实际情况配置）
        bot_id = "12345"
        bot_name = "ATRI机器人"
        
        # 提取分组信息（群组ID）
        group_id = context.split('_')[1] if '_' in context else ""
        
        try:
            # 将机器人消息加入队列
            message_id = await self._enqueue_message(
                user_id=bot_id,
                user_name=bot_name,
                message=message,
                context=context,
                group_id=group_id,
                is_tome=False,  # 这不是发给机器人的
                is_me=True,     # 这是机器人发的
                reply_to=in_reply_to  # 记录回复的目标
            )
            
            logging.info(f"机器人回复已加入队列: {message[:30]}...")
            return message_id
        except Exception as e:
            logging.error(f"添加机器人回复到队列失败: {e}")
            return None 