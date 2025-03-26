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
    
    async def process_message(self, user_id: str, message: str, context: str = "chat", 
                            is_priority: bool = False) -> Optional[str]:
        """处理新消息，如果是优先级消息则立即处理，否则加入队列
        
        Args:
            user_id: 用户ID
            message: 消息内容
            context: 上下文（如"group_123456"）
            is_priority: 是否为优先处理消息（私聊或@机器人）
            
        Returns:
            处理后的记忆ID（如果立即处理）或None（如果加入队列）
        """
        return await self.message_queue.add_message(user_id, message, context, is_priority)
    
    async def process_queue(self, max_items: int = None) -> int:
        """处理消息队列
        
        Args:
            max_items: 最大处理条数，默认使用配置值
            
        Returns:
            处理的消息数量
        """
        if max_items is None:
            max_items = self.config["batch_size"]
            
        return await self.message_queue.process_queue(max_items)
    
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