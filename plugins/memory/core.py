"""
记忆系统核心模块 - 协调各个子系统的工作

该模块包含记忆系统的主类，负责协调存储、处理、检索和维护等子系统。
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from .storage import StorageManager
from .processor import MemoryProcessor
from .decay import DecayManager
from .message_queue import MessageQueue

class MemoryRetriever:
    """负责从记忆存储中检索相关信息"""
    
    def __init__(self, storage: StorageManager):
        self.storage = storage
    
    async def search(self, query: str, user_id: str = None, limit: int = 5) -> List[Dict]:
        """搜索相关记忆"""
        # 此处实现将在后续完善
        return []

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
            "batch_size": 50,  # 每次批处理的消息数量
            "history_limit": 10  # 保留给AI回复的历史消息数量
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
        
        logging.info("记忆系统构造完成，等待数据库初始化")
    
    async def initialize(self):
        """初始化记忆系统数据库和组件"""
        # 初始化存储结构
        await self.storage.initialize(self.use_postgres, self.postgres_config)
        
        # 初始化消息队列
        self.message_queue = MessageQueue(
            self.storage, 
            self.processor, 
            batch_interval=self.config["batch_interval"]
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
        
    def set_auto_reply_threshold(self, threshold: float):
        """设置自动回复阈值
        
        Args:
            threshold: 阈值 (0.0-1.0)，当话题的continuation_probability大于此值时可能触发自动回复
        """
        if not hasattr(self, 'message_queue'):
            raise RuntimeError("请先调用initialize()初始化记忆系统")
            
        self.message_queue.auto_reply_threshold = float(threshold)
        logging.info(f"自动回复阈值已设为: {threshold}")
    
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
    
    async def process_message(self, user_id: str, user_name: str, message: str, context: str, 
                            is_priority: bool = False, is_tome: bool = False) -> Optional[str]:
        """处理新消息并加入队列，如果是优先级消息则立即处理该群消息
        
        注意：单条消息处理不如批量处理高效。系统会将消息加入队列，然后定期批量处理，
        这可以节省API调用并获得更准确的上下文理解。只有在紧急情况下才应使用is_priority=True。
        
        Args:
            user_id: 用户ID
            user_name: 用户昵称
            message: 消息内容
            context: 上下文（如"group_123456"）
            is_priority: 是否为优先处理消息（私聊或@机器人）
            is_tome: 是否为@机器人消息
        Returns:
            处理后的队列项ID；若为优先消息，则返回处理结果ID
        """
        if context.startswith("private_"):
            return None  # 私聊消息暂不处理
            
        # 如果是优先消息，添加警告日志
        if is_priority:
            logging.warning(f"正在使用优先处理: {user_id} - {message[:20]}... 这种方式不如批量处理高效")
            
        return await self.message_queue.add_message(user_id, user_name, message, context, is_priority, is_tome)
    
    async def process_queue(self, max_items_per_group: int = None) -> int:
        """处理消息队列
        
        Args:
            max_items_per_group: 每个群组最大处理条数，默认使用配置值
            
        Returns:
            处理的消息数量
        """
        if max_items_per_group is None:
            max_items_per_group = self.config["batch_size"]
            
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
        
        # 默认设置较低的阈值，使系统谨慎回复
        self.set_auto_reply_threshold(0.6)
        
        logging.info("自动回复功能已激活") 