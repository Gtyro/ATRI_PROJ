import random
import re
from typing import Callable, Dict, List, Tuple, Optional, Any
import os
import time
import logging

from ..storage import StorageManager
from ..processing import MemoryProcessor, DecayManager
from ..storage.queue import MessageQueue
from .retriever import MemoryRetriever
from ...models import GroupPluginConfig
from ..utils.config import check_config, load_config

class MemorySystem:
    """记忆系统主类，负责协调各个子系统"""
    
    def __init__(self, db_path: str = "data/memory.db", batch_interval: int = 3600, 
                 use_postgres: bool = False, postgres_config: Dict = None):
        """初始化记忆系统及相关组件
        
        Args:
            db_path: 数据库路径（SQLite使用）
            batch_interval: 消息批处理间隔（秒）
            use_postgres: 是否使用PostgreSQL
            postgres_config: PostgreSQL配置，包含host, port, user, password, database
        """
        check_config()
        self.config = load_config()
        self.plugin_name = "memory"
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.use_postgres = use_postgres
        self.postgres_config = postgres_config
        
        # 初始化各子系统
        self.storage = StorageManager(db_path)
        
        try:
            self.processor = MemoryProcessor(self.config['api_key'])
            logging.info("记忆处理器初始化成功")
        except Exception as e:
            logging.error(f"记忆处理器初始化失败: {e}")
            raise ValueError(f"无法初始化记忆系统，原因: {e}")
            
        self.retriever = MemoryRetriever()
        self.decay_manager = DecayManager()
        self.group_config = GroupPluginConfig()
        
        logging.info("记忆系统构造完成，等待数据库初始化")
        self.reply_callback = None
    
    async def initialize(self, reply_callback: Callable = None):
        """初始化记忆系统数据库和组件"""
        # 初始化存储结构
        await self.storage.initialize(self.use_postgres, self.postgres_config)
        
        # 初始化消息队列
        self.message_queue = MessageQueue(
            self.storage,
            batch_interval=self.config["batch_interval"],
            queue_history_size=self.config["queue_history_size"]
        )
        
        logging.info("记忆系统初始化完成")
        self.reply_callback = reply_callback

    def register_auto_reply_callback(self, callback):
        """注册自动回复回调函数
        
        当系统检测到需要自动回复的未完结话题时，将调用此回调函数。
        
        Args:
            callback: 回调函数，需要接收两个参数：(group_id, topic_data)
                      topic_data包含话题信息和建议回复内容
        """
        if not hasattr(self, 'message_queue'):
            raise RuntimeError("请先调用initialize()初始化记忆系统")
            
        self.message_queue.register_reply_callback(callback)
        logging.info("已注册自动回复回调函数")
    
    async def close(self):
        """关闭记忆系统并清理资源"""
        await self.storage.close()
        logging.info("记忆系统已关闭")
    
    async def process_message(self, queue_item_dict: Dict) -> Optional[str]:
        """先将新消息加入队列
        如果是直接交互消息则立即处理该队列消息
        如果是群交互消息则将该群的ORM插件的plugin_config字典的next_process_time设置为5分钟后
        
        Args:
            queue_item_dict: 队列项字典
        
        Returns:
            可能的回复字典
        """
        await self.message_queue.enqueue_message(queue_item_dict)
        if queue_item_dict['is_direct']:
            return await self.process_conv_queue(queue_item_dict['conv_id'], queue_item_dict['user_id'])

    async def process_conv_queue(self, conv_id: str, user_id: str) -> int:
        """处理特定对话的队列消息
        
        Args:
            conv_id: 对话ID
        
        Returns:
            可能的回复内容
        """
        # 获取队列中未处理消息
        conv_queue_items = await self.message_queue.get_conv_queue_items(conv_id)
        if len(conv_queue_items) <= 0:
            logging.warning(f"对话 {conv_id} 队列为空，无需处理")
            return 0
        # 将队列消息批量提交给处理器，获取话题消息
        topics = await self.processor.process_conversation(conv_id, conv_queue_items)
        # 完结消息存入数据库
        # 标记完结消息并清除队列
        await self.clean_conv_queue(conv_id, topics)
        # 判定回复
        is_reply = False
        for topic in topics:
            if topic.get("completed_status"):
                continue
            else:
                if topic.get("continuation_probability") < 0.5:
                    continue
                random_num = random.random()
                if random_num > topic.get("continuation_probability"):
                    continue
                else:
                    is_reply = True
                    break
        if not is_reply:
            return None
        # 获取队列
        conv_queue_items = await self.message_queue.get_conv_queue_items(conv_id)
        # 调整下次处理时间
        if conv_id.startswith('group_'):
            self.group_config.update_config(conv_id, self.plugin_name, {'next_process_time': time.time() + 300})
        # 返回回复

        # 判断消息是否是机器人说的
        # 如果是，role为assistant
        # 判断消息是否是@机器人的
        # 如果是，在['user_name']后添加'对你'
        messages = [{"role": "assistant" if item.get("is_me") else "user", "content": f"[{item.get('user_name')}]{'对你' if item.get('is_direct') else ''}说: {item.get('content')}"} for item in conv_queue_items]
        
        # 生成回复
        logging.info(f"正在生成对 {user_id} 的回复，历史消息数: {len(messages)}")
        reply_content = await self.processor.ai_processor.generate_response(messages, temperature=0.7)
        logging.debug(f"生成的回复: {reply_content[:30]}...")

        # 添加回复消息到队列
        await self.message_queue.add_bot_message(conv_id, reply_content)

        # 分割回复
        pattern1 = r'(\(.*?\))'
        pattern2 = r'（.*?）'
        pattern3 = r'([^，。！？（）()\s]+\.+)'
        pattern4 = r'([^，。！？（）()\s]+)'
        split_replies = [''.join(t) for t in re.findall(rf'{pattern1}|{pattern2}|{pattern3}|{pattern4}', reply_content)]

        # 回复字典
        message_dict = {
            "reply_content": split_replies if logging.getLogger().getEffectiveLevel() != logging.DEBUG else reply_content,
        }
        return message_dict

    async def clean_conv_queue(self, conv_id: str, topics: List[Dict]) -> None:
        """通过主题列表标记并清理对话队列"""
        completed_ids = set()
        ongoing_ids = set()
        for topic in topics:
            if topic.get("completed_status"):
                completed_ids.update(topic.get("message_ids", []))
            else:
                ongoing_ids.update(topic.get("message_ids", []))

        # 判断是否有同时包含在ongoing_ids和completed_ids中的消息
        # 如果有，则warning
        if ongoing_ids & completed_ids:
            logging.warning(f"对话 {conv_id} 存在同时包含在ongoing_ids和completed_ids中的消息")
        completed_ids = completed_ids - ongoing_ids
        
        # 标记已完结消息
        if completed_ids:
            marked_count = await self.storage.mark_as_processed(list(completed_ids))
            if marked_count != len(completed_ids):
                logging.warning(f"队列消息标记不完全，应标记{len(completed_ids)}条，实际标记{marked_count}条")
        # 清理过量的已完结对话消息，保留最新的queue_history_size条
        await self.storage.remove_old_processed_messages(conv_id, self.config["queue_history_size"])

    async def process_queue(self, max_items_per_group: int = None) -> int:
        """处理消息队列，debug用
        
        Args:
            max_items_per_group: 每个群组最大处理条数，默认使用配置值
            
        Returns:
            处理的消息数量
        """

        # 获取所有需要处理的不同对话ID
        distinct_convs = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)

        # 对每个对话单独处理
        for conv_id in distinct_convs:
            await self.process_conv_queue(conv_id)
            
        return await self.message_queue.process_queue(max_items_per_group)
    
    async def retrieve_related_memories(self, query: str, user_id: str = None, limit: int = 5) -> List[Dict]:
        """检索相关记忆"""
        return await self.retriever.search(query, user_id, limit)
    
    async def schedule_maintenance(self) -> None:
        """计划执行维护任务（如记忆衰减、整理、处理队列等）"""
        # 获取所有需要处理的不同群组ID
        distinct_convs = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)
        for conv_id in distinct_convs:
            # 判断是否达到下次处理时间
            config = await self.group_config.get_config(conv_id, self.plugin_name)
            if time.time() > config.get('next_process_time', 0):
                reply_dict = await self.process_conv_queue(conv_id)
                if reply_dict:
                    config.plugin_config['next_process_time'] = time.time() + self.config['batch_interval']
                    await config.save()
                self.reply_callback(conv_id, reply_dict)
            else:
                logging.info(f"对话 {conv_id} 未达到下次处理时间，跳过")
        
        # 基础衰减处理
        await self.decay_manager.apply_decay()
        
        # 未来可添加更多维护任务
        # await self.consolidate_memories()
        # await self.prune_weak_connections()
    
    async def get_queue_status(self) -> Dict:
        """获取队列状态"""
        stats = await self.storage.get_queue_stats()
        next_process = self.message_queue.next_process_time
        remaining = max(0, int(next_process - time.time()))
        
        return {
            "stats": stats,
            "next_process_in": remaining,
            "batch_interval": self.config["batch_interval"]
        }
