'''
人格系统主类，负责协调各个子系统
独特概念：
- 短期记忆: 用消息队列模拟大脑的短期记忆
- 长期记忆: 用图数据结构+数据库模拟大脑的长期记忆
- 群组人格: 每个群组可以设置不同的人格，通过群组配置文件设置
- 消息处理器: 消息处理器负责处理消息，提取话题，并生成回复
- 检索器: 检索器负责通过关键词从长期记忆中检索相关记忆
- 衰减管理器: 衰减管理器负责管理记忆的衰减
- 回调函数: 回调函数负责回调回复
- conversation: 会话，指一个群组或者两个用户之间的私聊
- node: 节点，指会话中的关键词(概念、对象、主题、标签等含义)，用来检索长期记忆
'''
import os
import time
import logging
import random
from typing import Dict, List, Optional, Any, Callable

from ..utils.config import check_config, load_config
from ..storage.repository import Repository
from ..memory.short_term import ShortTermMemory
from ..memory.long_term import LongTermMemory
from ..memory.decay import DecayManager
from ..processing.message_processor import MessageProcessor
from ..core.retriever import MemoryRetriever
from plugins.models import GroupPluginConfig

class PersonaSystem:
    """人格系统主类，负责协调各个子系统"""
    
    def __init__(self, db_path: str = "data/persona.db", config_path: str = "data/persona.yaml"):
        """初始化系统及相关组件
        
        Args:
            db_path: 数据库路径（SQLite使用）
            config_path: 配置文件路径
        """
        # 检查和加载配置
        check_config(config_path)
        self.config = load_config(config_path)
        self.plugin_name = "persona"
        
        # 创建数据目录
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 配置数据库路径
        self.config["db_path"] = db_path
        
        # 初始化属性但不创建对象
        self.repository = None
        self.short_term = None
        self.long_term = None
        self.processor = None
        self.retriever = None
        self.decay_manager = None
        self.reply_callback = None
        self.group_config = GroupPluginConfig
        self.group_character = {}
        
        logging.info("人格系统构造完成，等待初始化")
    
    async def initialize(self, reply_callback: Callable = None):
        """异步初始化所有组件"""
        # 初始化存储仓库
        self.repository = Repository(self.config)
        await self.repository.initialize()
        
        # 初始化记忆管理
        self.short_term = ShortTermMemory(self.repository, self.config)
        self.long_term = LongTermMemory(self.repository, self.config)
        if self.config.get("decay_system_enabled", False):
            logging.info("启用记忆衰减系统")
            self.decay_manager = DecayManager(self.repository, self.config.get("node_decay_rate", 0.01))
        else:
            logging.info("记忆衰减系统未启用")

        # 初始化群组人格字典
        group_ids = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)
        for group_id in group_ids:
            config = await GroupPluginConfig.get_config(group_id, self.plugin_name)
            self.group_character[group_id] = config.plugin_config.get("prompt_file", "")
        
        # 初始化处理器
        try:
            self.processor = MessageProcessor(self.config, self.group_character, self.config['queue_history_size'])
            logging.info("消息处理器初始化成功")
        except Exception as e:
            logging.error(f"消息处理器初始化失败: {e}")
            raise ValueError(f"无法初始化人格系统，原因: {e}")
        
        # 初始化检索器
        self.retriever = MemoryRetriever(self.repository)
        
        # 设置回调
        self.reply_callback = reply_callback
        
        logging.info("人格系统初始化完成")
    
    async def close(self):
        """关闭系统并清理资源"""
        if self.repository:
            await self.repository.close()
        logging.info("人格系统已关闭")
    
    async def process_message(self, message_data: Dict) -> Optional[Dict]:
        """处理新消息
        添加到短期记忆，如果是直接对话，立即处理
        
        Args:
            message_data: 消息数据
            
        Returns:
            可能的回复内容
        """
        if not self.short_term:
            raise RuntimeError("系统尚未初始化，请先调用initialize()")
            
        # 添加到短期记忆
        try:
            await self.short_term.add_message(message_data)
        except Exception as e:
            logging.error(f"persona_system.process_message:添加消息到短期记忆失败: {e}")
            raise e
        
        # 如果是直接对话，立即处理
        try:
            if message_data.get('is_direct', False):
                return await self.process_conversation(
                    message_data['conv_id'], 
                    message_data['user_id']
                )
        except Exception as e:
            logging.error(f"persona_system.process_message:处理消息失败: {e}")
            raise e
        
        return None
    
    async def process_conversation(self, conv_id: str, user_id: str) -> Optional[Dict]:
        """处理特定会话的消息
        
        Args:
            conv_id: 会话ID
            user_id: 用户ID
            
        Returns:
            可能的回复内容
        """
        message_count = 0
        topic_count = 0
        messages = await self.short_term.get_unprocessed_messages(conv_id, 2*self.config['queue_history_size'])
        if not messages:
            logging.info(f"会话 {conv_id} 没有未处理消息")
            return None
        message_count += len(messages)

        # 处理会话
        topics = await self.processor.extract_topics_from_messages(conv_id, messages)
        topic_count += len(topics)
        
        # 存储到长期记忆
        await self.long_term.store_topics(conv_id, topics)

        # 标记消息为已处理
        await self.short_term.mark_processed(conv_id, topics)
        logging.info(f"会话 {conv_id} 处理完成，有 {message_count} 条消息，{topic_count} 个话题")
            
        # 判断是否需要回复
        should_reply = await self.processor.should_respond(topics)
        
        if not should_reply:
            if conv_id.startswith('group_'):
                # 如果群组不需要回复，下次处理时间设置为30分钟
                config = await self.group_config.get_config(conv_id, self.plugin_name)
                config.plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                await config.save()
            return None
        
        logging.info(f"会话 {conv_id} 需要回复")
        
        # 获取最近消息历史（包括已处理的）
        recent_messages = await self.short_term.get_all_messages(conv_id, self.config['queue_history_size'])
        logging.info(f"会话 {conv_id} 获取最近消息历史完成")
        # 调整下次处理时间（如果是群组）
        try:
            if conv_id.startswith('group_'):
                config = await self.group_config.get_config(conv_id, self.plugin_name)
                config.plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                await config.save()
                logging.info(f"会话 {conv_id} 调整下次处理时间完成")
        except Exception as e:
            logging.error(f"会话 {conv_id} 调整下次处理时间失败: {e}")
            raise e
        # 生成回复
        reply_data = await self.processor.generate_reply(conv_id, recent_messages, temperature=0.7)
        reply_content = reply_data.get('content', '')
        logging.info(f"会话 {conv_id} 生成回复完成")
        logging.info(f"会话 {conv_id} 回复内容: {reply_content}")
        return # 暂时测试
        # 添加机器人自己的消息到历史
        if reply_content:
            await self.short_term.add_bot_message(conv_id, reply_content)
            logging.info(f"会话 {conv_id} 添加机器人自己的消息到历史完成")
        # 返回回复
        return {
            "reply_content": reply_content,
            "user_id": user_id
        }
    
    async def schedule_maintenance(self) -> None:
        """定期维护任务"""
        if not self.repository or not self.short_term:
            logging.warning("系统尚未初始化，跳过维护")
            return
            
        # 获取所有需要处理的群组
        distinct_convs = await self.group_config.get_distinct_group_ids(self.plugin_name)
        
        for conv_id in distinct_convs:
            # 检查是否到达处理时间
            config = await self.group_config.get_config(conv_id, self.plugin_name)
            plugin_config = config.plugin_config or {}
            
            next_process_time = plugin_config.get('next_process_time', 0)
            if time.time() > next_process_time or logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                # 处理该会话
                reply_dict = await self.process_conversation(conv_id, "")
                
                # 如果有回复且注册了回调，则调用回调
                if reply_dict and self.reply_callback:
                    await self.reply_callback(conv_id, reply_dict)
                    
                # 更新下次处理时间
                plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                config.plugin_config = plugin_config
                await config.save()
            else:
                logging.debug(f"会话 {conv_id} 未到处理时间，跳过")
        
        # 执行记忆衰减
        await self.decay_manager.apply_decay()
    
    async def retrieve_related_memories(self, query: str, user_id: str = None, limit: int = 5) -> List[Dict]:
        """检索相关记忆
        
        Args:
            query: 查询内容
            user_id: 用户ID（可选）
            limit: 结果数量限制
            
        Returns:
            相关记忆列表
        """
        if not self.retriever:
            raise RuntimeError("系统尚未初始化，请先调用initialize()")
            
        return await self.retriever.search_for_memories(query, user_id, limit)
    
    async def get_queue_status(self) -> Dict:
        """获取队列状态
        
        Returns:
            队列状态字典
        """
        if not self.short_term:
            raise RuntimeError("系统尚未初始化，请先调用initialize()")
            
        return await self.short_term.get_queue_stats()

    async def simulate_reply(self, conv_id: str) -> Dict:
        """模拟回复
        从短期记忆中获取未处理消息，并提取关键信息
        从长期记忆中获取相关记忆
        使用AI生成回复
        返回回复内容
        """
        if not self.short_term:
            raise RuntimeError("系统尚未初始化，请先调用initialize()")
            
        # 获取未处理消息
        messages = await self.short_term.get_unprocessed_messages(conv_id)
        if not messages:
            logging.info(f"会话 {conv_id} 没有未处理消息")
            return None
        
        # 提取关键信息
        topics: List[Dict] = await self.processor.extract_topics_from_messages(conv_id, messages)
        logging.info(f"会话 {conv_id} 提取关键信息完成")
        # 从长期记忆中获取相关记忆
        related_memories = []
        for topic in topics:
            if topic['completed_status'] == False:
                related_memories.extend(await self.retriever.search_for_memories(topic['content'], None, 5))
        logging.info(f"会话 {conv_id} 从长期记忆中获取相关记忆完成")
        # 使用AI生成回复
        reply_data = await self.processor.generate_reply(conv_id, related_memories, temperature=0.7)
