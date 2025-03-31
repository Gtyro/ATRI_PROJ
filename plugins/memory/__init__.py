"""
记忆系统 - 为NoneBot2机器人提供类人记忆功能

这个包实现了一个模块化的记忆系统，包括存储、处理、检索和记忆衰减功能。
设计为可扩展架构，允许逐步添加更复杂的记忆处理机制。
支持SQLite和PostgreSQL数据库存储。
"""

from .core import MemorySystem
from .storage import StorageManager, Memory, MemoryAssociation, MemoryEntity, MessageQueueItem
from .processing import MemoryProcessor
from .processing.decay import DecayManager
from .processing.ai import AIProcessor
from .storage.queue import MessageQueue

# 导入插件入口点以确保NoneBot可以找到插件定义
from .plugin import *

# 暴露主要接口
__all__ = [
    'MemorySystem', 'StorageManager', 'MemoryProcessor', 
    'DecayManager', 'AIProcessor', 'MessageQueue',
    'Memory', 'MemoryAssociation', 'MemoryEntity', 'MessageQueueItem'
]

# 版本信息
__version__ = '0.3.0' 