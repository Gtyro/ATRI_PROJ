from typing import Dict, List, Tuple, Optional, Any
import os
import time
import logging

from ..storage import StorageManager
from ..processing import MemoryProcessor, DecayManager
from ..storage.queue import MessageQueue
from .retriever import MemoryRetriever
from ...models import GroupPluginConfig

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
        self.plugin_name = "memory"
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.use_postgres = use_postgres
        self.postgres_config = postgres_config
        
        # 初始化配置参数
        self.config = {
            "short_term_capacity": 100,
            "decay_rate": 0.05,
            "emotion_weight": 0.3,
            "access_boost": 0.1,
            "default_retention": 0.7,
            "batch_interval": batch_interval,
            "batch_size": 50,          # 每次批处理的消息数量
            "history_limit": 10,       # 保留给AI回复的历史消息数量
            "queue_history_size": 20   # 每个对话保留在队列中的历史消息数量
        }
        
        # 加载自定义配置
        self._load_config()
        
        # 初始化各子系统
        self.storage = StorageManager(db_path)
        
        try:
            self.processor = MemoryProcessor()
            logging.info("记忆处理器初始化成功")
        except Exception as e:
            logging.error(f"记忆处理器初始化失败: {e}")
            raise ValueError(f"无法初始化记忆系统，原因: {e}")
            
        self.retriever = MemoryRetriever(self.storage)
        self.decay_manager = DecayManager(self.storage)
        self.group_config = GroupPluginConfig()
        
        logging.info("记忆系统构造完成，等待数据库初始化")
    
    async def initialize(self):
        """初始化记忆系统数据库和组件"""
        # 初始化存储结构
        await self.storage.initialize(self.use_postgres, self.postgres_config)
        
        # 初始化消息队列
        self.message_queue = MessageQueue(
            self.storage, 
            self.processor, 
            batch_interval=self.config["batch_interval"],
            queue_history_size=self.config["queue_history_size"]
        )
        
        logging.info("记忆系统初始化完成")
        
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
    
    def _load_config(self):
        """加载自定义配置"""
        config_path = "data/memory_config.yaml"
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    custom_config = yaml.safe_load(f)
                    self.config.update(custom_config)
                logging.info("已加载自定义记忆系统配置")
            except Exception as e:
                logging.error(f"加载配置文件失败: {e}")
    
    async def process_message(self, queue_item_dict: Dict) -> Optional[str]:
        """先将新消息加入队列
        如果是直接交互消息则立即处理该队列消息
        如果是群交互消息则将该群的ORM插件的plugin_config字典的next_process_time设置为5分钟后
        
        Args:
            queue_item_dict: 队列项字典
        """
        await self.message_queue.enqueue_message(queue_item_dict)
        if queue_item_dict['is_direct']:
            await self.process_conv_queue(queue_item_dict['conv_id'])
            if queue_item_dict['conv_id'].startswith('group_'):
                self.group_config.update_config(queue_item_dict['conv_id'], self.plugin_name, {'next_process_time': time.time() + 300})

    async def process_conv_queue(self, conv_id: str) -> int:
        """处理特定对话的队列消息
        
        Args:
            conv_id: 对话ID
        
        Returns:
            处理的消息数量
        """
        conv_queue_items = await self.message_queue.get_conv_queue_items(conv_id)
        if len(conv_queue_items) > 0:
            # 将队列消息批量提交给处理器，并获取已完结和未完结消息ID
            completed_ids, ongoing_ids = await self.message_queue._process_conv_batch(conv_id, conv_queue_items)

            # 构建序号ID到数据库ID的映射
            seq_to_db_id = {item.get("seq_id", 0): item["id"] for item in conv_queue_items}

            # 收集要标记为已处理的消息数据库ID
            completed_db_ids = [seq_to_db_id.get(seq_id) for seq_id in completed_ids if seq_id in seq_to_db_id]
            
            # 只标记已完结话题的消息为已处理
            if completed_db_ids:
                marked_count = await self.storage.mark_as_processed(completed_db_ids)
                if marked_count != len(completed_db_ids):
                    logging.warning(f"队列消息标记不完全，应标记{len(completed_db_ids)}条，实际标记{marked_count}条")
            
            # 清理旧的已处理消息，保留最新的queue_history_size条
            await self.storage.remove_old_processed_messages(conv_id, self.config["queue_history_size"])
            
            # 计算已处理的总消息数
            processed_count = len(completed_ids)

            if ongoing_ids:
                ongoing_db_ids = [seq_to_db_id.get(seq_id) for seq_id in ongoing_ids if seq_id in seq_to_db_id]
                logging.info(f"保留 {len(ongoing_db_ids)} 条未完结话题消息在队列中")
            
            # 记录处理情况
            logging.info(f"对话 {conv_id} 已处理 {processed_count} 条消息")
            
            return processed_count
        else:
            logging.info(f"对话 {conv_id} 队列为空，无需处理")
            return 0
    
    async def process_queue(self, max_items_per_group: int = None) -> int:
        """处理消息队列
        
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
        # 处理消息队列
        await self.process_queue()
        
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
    
    async def generate_auto_reply(self, callback) -> None:
        """配置并启用系统的自动回复功能
        
        Args:
            callback: 回调函数，用于生成回复内容。接收(group_id, topic_data)参数，
                    应返回字符串回复或None（不回复）
        """
        # 设置自动回复处理器
        self.register_auto_reply_callback(callback)
        
        logging.info("自动回复功能已激活")