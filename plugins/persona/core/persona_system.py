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
import yaml

from ..utils.config import check_config, load_config
from ..storage.repository import Repository
from ..memory.short_term import ShortTermMemory
from ..memory.long_term import LongTermMemory
from ..memory.decay import DecayManager
from ..processing.message_processor import MessageProcessor
from .memory_retriever import LongTermRetriever
from plugins.models import GroupPluginConfig
from ..processing.ai_processor import AIProcessor

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
        self.aiprocessor = None
        self.msgprocessor = None
        self.retriever = None
        self.decay_manager = None
        self.reply_callback = None
        self.group_config = GroupPluginConfig
        self.group_character = {}
        
        logging.info("人格系统构造完成，等待初始化")
    
    async def initialize(self, reply_callback: Callable = None):
        """初始化人格系统
        
        包括:
        1. 初始化数据库连接
        2. 初始化各个组件
        3. 设置回调函数
        
        Args:
            reply_callback: 回复回调函数
        """
        try:
            # 初始化仓库
            self.repository = Repository(self.config)
            await self.repository.initialize()
            
            # 初始化组件
            self.short_term = ShortTermMemory(
                self.repository,
                self.config
            )
            
            # 初始化群组配置
            group_ids = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)
            group_character = {}
            for group_id in group_ids:
                try:
                    config = await GroupPluginConfig.get_config(group_id, self.plugin_name)
                    prompt_file = config.plugin_config.get("prompt_file", None)
                    if prompt_file and os.path.exists(prompt_file):
                        group_character[group_id] = prompt_file
                except Exception as e:
                    logging.error(f"读取群组配置失败[{group_id}]: {e}")
            
            # 初始化AI处理器
            api_key = self.config.get('api_key', '') or os.getenv('OPENAI_API_KEY', '')
            base_url = self.config.get('base_url', '') or os.getenv('OPENAI_BASE_URL', '')
            
            self.aiprocessor = AIProcessor(
                api_key=api_key,
                model=self.config.get('model', 'deepseek-chat'),
                base_url=base_url or "https://api.deepseek.com",
                group_character=group_character,
                queue_history_size=self.config.get('queue_history_size', 40)
            )
            
            # 传递现有的AI处理器实例给消息处理器
            self.msgprocessor = MessageProcessor(
                self.config,
                ai_processor=self.aiprocessor,
                group_character=group_character,
                queue_history_size=self.config.get('queue_history_size', 40)
            )
            
            # 设置记忆检索回调
            self.aiprocessor.set_memory_retrieval_callback(self.format_memories)
            
            # 初始化长期记忆组件
            self.long_term = LongTermMemory(self.repository, self.config)
            self.retriever = LongTermRetriever(self.repository)
            self.decay_manager = DecayManager(self.repository, self.config.get("node_decay_rate", 0.01))
            
            # 设置回调函数
            self.reply_callback = reply_callback
            
            # 标记系统已初始化
            logging.info("人格系统初始化成功")
            return True
        except Exception as e:
            logging.error(f"人格系统初始化失败: {e}")
            raise
    
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
                topics = await self.msgprocessor.extract_topics_from_messages(conv_id, messages)
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
        should_reply = await self.msgprocessor.should_respond(conv_id, topics)
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
        reply_data = await self.msgprocessor.generate_reply(conv_id, recent_messages, temperature=0.7)
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
    
    async def retrieve_related_memories(self, query: str, user_id: str = None, limit: int = 5, conv_id: str = None) -> List[Dict]:
        """检索相关记忆
        
        Args:
            query: 查询内容
            user_id: 用户ID（可选）
            limit: 结果数量限制
            conv_id: 会话ID（可选），用于限制查询范围
            
        Returns:
            相关记忆列表
        """
        if not self.retriever:
            raise RuntimeError("系统尚未初始化，请先调用initialize()")
        
        keywords = query.split(" ")
        memory_list = []
        for keyword in keywords:
            memory_list.extend(await self.retriever.search_for_memories(keyword, user_id, limit, conv_id))
        return memory_list
    
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
        使用function calling功能生成回复
        
        Args:
            conv_id: 会话ID
            
        Returns:
            回复内容字典
        """
        try:
            # 获取会话最近消息
            messages = await self.short_term.get_recent_messages(conv_id, self.config.get('queue_history_size', 40))
            if not messages:
                logging.info(f"会话 {conv_id} 没有历史消息")
                return None
                
            # 日志记录消息数量
            logging.info(f"开始为会话 {conv_id} 生成模拟回复，获取到 {len(messages)} 条历史消息")
            
            # 直接使用AI处理器的function calling能力生成回复
            reply_content = await self.msgprocessor.generate_reply(conv_id, messages, temperature=0.7)
            
            # 判断回复状态
            if reply_content:
                logging.info(f"会话 {conv_id} 生成模拟回复成功: {reply_content[:30]}...")
                reply_dict = {
                    "reply_content": reply_content
                }
                return reply_dict
            else:
                logging.error(f"会话 {conv_id} 模拟回复内容为空")
                return None
        except Exception as e:
            logging.error(f"会话 {conv_id} 模拟回复异常: {e}")
            return None
        
    async def create_permanent_memory(self, conv_id: str, node_name: str, memory_title: str, memory_content: str) -> Dict:
        """创建常驻节点和记忆对
            
        Returns:
            包含节点和记忆信息的字典
        """
        try:
            # 创建常驻节点
            node = await self.repository.update_or_create_node(conv_id, node_name, is_permanent=True)
            
            # 创建常驻记忆
            memory_data = {
                "conv_id": conv_id,
                "title": memory_title,
                "content": memory_content,
                "is_permanent": True
            }
            memory = await self.repository.store_memory(conv_id, memory_data)
            
            # 使用现有的_link_nodes_to_memory函数建立关联
            await self.repository._link_nodes_to_memory(memory, [str(node.id)])
            
            logging.info(f"创建常驻节点-记忆对: 节点[{node_name}], 记忆[{memory_title}]")
            
            return {
                "node": {
                    "id": str(node.id),
                    "name": node.name,
                    "is_permanent": node.is_permanent
                },
                "memory": {
                    "id": str(memory.id),
                    "title": memory.title,
                    "content": memory.content,
                    "is_permanent": memory.is_permanent
                }
            }
        except Exception as e:
            logging.error(f"创建常驻节点-记忆对失败: {e}")
            raise
            
    async def format_memories(self, query: str, user_id: str, conv_id: str) -> str:
        """检索相关记忆并格式化为可读文本
        
        Args:
            query: 查询内容
            user_id: 用户ID
            conv_id: 会话ID
            
        Returns:
            格式化后的记忆文本
        """
        from datetime import datetime
        
        # 检索相关记忆
        related_memories = await self.retrieve_related_memories(query, user_id, conv_id=conv_id)
        
        if not related_memories:
            return "我似乎没有关于这方面的记忆..."
            
        # 格式化回复
        reply = "我记得这些内容:\n"
        for i, memory in enumerate(related_memories, 1):
            memory_source = memory.get("source", "未知")
            title = memory.get("title", "无标题")
            content = memory.get("content", "无内容")
            time_str = datetime.fromtimestamp(memory.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
            reply += f"{i}. [{memory_source}]【{title}】{content} ({time_str})\n"
            
        return reply