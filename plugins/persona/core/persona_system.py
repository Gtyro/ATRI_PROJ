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
import re
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
            if message_data["is_direct"]:
                return await self.process_conversation(
                    message_data['conv_id'], 
                    message_data['user_id'],
                    message_data['is_direct']
                )
        except Exception as e:
            logging.error(f"persona_system.process_message:处理消息失败: {e}")
            raise e
        
        return None
    
    async def process_conversation(self, conv_id: str, user_id: str, is_direct: bool = False) -> Optional[Dict]:
        """处理特定会话的消息
        
        Args:
            conv_id: 会话ID
            user_id: 用户ID
            is_direct: 是否是直接对话
        Returns:
            可能的回复内容
        """
        # 获取待处理消息
        try:
            message_count = 0
            memory_count = 0
            marked_count_total = 0
            loop_count = 0
            while True:
                loop_count += 1
                messages: List[Dict] = await self.short_term.get_unprocessed_messages(conv_id, 2*self.config['queue_history_size'])
                if not messages:
                    logging.info(f"会话 {conv_id} 没有未处理消息")
                    return None
                message_count += len(messages)

                # 处理会话
                topics = await self.processor.extract_topics_from_messages(conv_id, messages)
                if len(topics) == 0:
                    break
                
                # 将话题存储为长期记忆
                memory_ids = await self.long_term.store_memories(conv_id, topics)
                memory_count += len(memory_ids)
                if len(memory_ids) == 0:
                    break

                # 标记消息为已处理
                marked_count = await self.short_term.mark_processed(conv_id, topics)
                marked_count_total += marked_count
                
                if len(messages) < 2*self.config['queue_history_size']:
                    break
                if len(topics) == 0 or len(memory_ids) == 0 or marked_count == 0:
                    logging.warning(f"会话 {conv_id} 处理异常，有 {len(topics)} 个话题，{len(memory_ids)} 个记忆，{marked_count} 条消息被标记为已处理")
                    break
                logging.info(f"会话 {conv_id} 第{loop_count}次循环: 处理了 {len(messages)} 条消息，存储了 {len(memory_ids)} 个记忆，标记了 {marked_count} 条消息为已处理")
            
            logging.info(f"会话 {conv_id} 处理完成: 共 {loop_count} 次循环，处理了 {message_count} 条消息，存储了 {memory_count} 个记忆，标记了 {marked_count_total} 条消息为已处理")
        except Exception as e:
            logging.error(f"会话 {conv_id} 处理失败: {e}")
            raise e
            
        # 判断是否需要回复
        should_reply = await self.processor.should_respond(conv_id, topics)
        # 判断队列中是否有机器人发的消息
        has_bot_message = await self.repository.has_bot_message(conv_id)
        if has_bot_message:
            logging.info(f"会话 {conv_id} 已有机器人发的消息，不回复")
            should_reply = False
        # 判断消息是否未处理完
        if len(messages) >= 2*self.config['queue_history_size']:
            logging.info(f"会话 {conv_id} 消息未处理完，不回复")
            should_reply = False
        if is_direct: # 如果是直接对话，则必须回复
            should_reply = True
        
        if not should_reply:
            if conv_id.startswith('group_'):
                # 如果群组不需要回复，下次处理时间设置为30分钟
                logging.info(f"会话 {conv_id} 不需要回复，下次处理时间设置为30分钟")
                config = await self.group_config.get_config(conv_id, self.plugin_name)
                config.plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                await config.save()
            return None
        
        logging.info(f"会话 {conv_id} 需要回复")
        
        # 获取最近消息历史（包括已处理的）
        recent_messages = await self.short_term.get_all_messages(conv_id)
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
        reply_content = reply_data["content"]
        logging.info(f"会话 {conv_id} 生成回复完成")
        logging.info(f"会话 {conv_id} 回复内容: {reply_content}")

        # 添加机器人自己的消息到历史
        if reply_content:
            await self.short_term.add_bot_message(conv_id, reply_content)
            logging.info(f"会话 {conv_id} 添加机器人自己的消息到历史完成")

        # 分割回复
        pattern1 = r'(\(.*?\))'
        pattern2 = r'（.*?）'
        pattern3 = r'([^，。！？（）()\s]+\.+)'
        pattern4 = r'([^，。！？（）()\s]+)'
        split_replies = [''.join(t) for t in re.findall(rf'{pattern1}|{pattern2}|{pattern3}|{pattern4}', reply_content)]
        # 返回回复
        reply_dict = {
            "reply_content": split_replies,
            "user_id": user_id
        }
        if reply_content and self.reply_callback:
            await self.reply_callback(conv_id, reply_dict)
    
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
                await self.process_conversation(conv_id, "")
                    
                # 更新下次处理时间
                plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                config.plugin_config = plugin_config
                await config.save()
            else:
                logging.info(f"会话 {conv_id} 未到处理时间，跳过")
        
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
        messages = await self.short_term.get_unprocessed_messages(conv_id, self.config['queue_history_size'])
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
                for node in topic['nodes']:
                    related_memories.extend(await self.retriever.search_for_memories(node, None, 5))
        logging.info(f"会话 {conv_id} 从长期记忆中获取相关记忆完成")
        long_memory_promt = ["你记得:\n"]
        for memory in related_memories:
            long_memory_promt.append(f"{memory['content']}，")
        long_memory_promt.append("，请根据这些记忆生成回复")
        long_memory_promt = "".join(long_memory_promt)
        logging.info(f"会话 {conv_id} 长期记忆提示: \n{long_memory_promt}")
        # 使用AI生成回复
        reply_data = await self.processor.generate_reply(conv_id, related_memories, temperature=0.7, long_memory_promt=long_memory_promt)
        reply_dict = {
            "reply_content": reply_data["content"]
        }
        return reply_dict
