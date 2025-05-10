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
from ..storage.message_repository import MessageRepository
from ..storage.memory_repository import MemoryRepository
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
        self.message_repo = None
        self.memory_repo = None
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

        Raises:
            Exception: 如果任何组件初始化失败
        """
        # 初始化存储库 - 分离消息队列和记忆网络存储
        self.message_repo = MessageRepository(self.config)
        await self.message_repo.initialize()

        self.memory_repo = MemoryRepository(self.config)
        await self.memory_repo.initialize()

        # 初始化组件
        self.short_term = ShortTermMemory(
            self.message_repo,
            self.config
        )

        # 初始化群组配置
        group_ids = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)
        group_character = {}
        for group_id in group_ids:
            try:
                gpconfig = await GroupPluginConfig.get_config(group_id, self.plugin_name)
                prompt_file = gpconfig.plugin_config.get("prompt_file", None)
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
        self.long_term = LongTermMemory(self.memory_repo, self.config)
        self.retriever = LongTermRetriever(self.memory_repo)
        self.decay_manager = DecayManager(self.memory_repo, self.config.get("node_decay_rate", 0.01))
        await self.decay_manager.initialize()

        # 设置回调函数
        self.reply_callback = reply_callback

        # 检查所有必需组件是否初始化成功
        initialization_checks = [
            (self.message_repo, "消息存储库"),
            (self.memory_repo, "记忆存储库"),
            (self.short_term, "短期记忆"),
            (self.long_term, "长期记忆"),
            (self.aiprocessor, "AI处理器"),
            (self.msgprocessor, "消息处理器"),
            (self.retriever, "记忆检索器"),
            (self.decay_manager, "衰减管理器")
        ]

        for component, name in initialization_checks:
            if component is None:
                raise RuntimeError(f"{name}初始化失败")

        # 标记系统已初始化
        logging.info("人格系统初始化成功")
        return True

    async def close(self):
        """关闭系统并清理资源"""
        if self.message_repo:
            await self.message_repo.close()
        logging.info("人格系统已关闭")

    async def process_message(self, message_data: Dict) -> Optional[Dict]:
        """处理新消息
        添加到短期记忆，如果是直接对话，立即处理

        Args:
            message_data: 消息数据

        Returns:
            可能的回复内容
        """
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
        has_bot_message = await self.message_repo.has_bot_message(conv_id)
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
                gpconfig = await self.group_config.get_config(conv_id, self.plugin_name)
                gpconfig.plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                await gpconfig.save()
            return None

        logging.info(f"会话 {conv_id} 需要回复")

        # 获取最近消息历史（包括已处理的）
        recent_messages = await self.short_term.get_recent_messages(conv_id, self.config.get('queue_history_size', 40))
        logging.info(f"会话 {conv_id} 获取最近消息历史完成")
        # 调整下次处理时间（如果是群组）
        try:
            if conv_id.startswith('group_'):
                gpconfig = await self.group_config.get_config(conv_id, self.plugin_name)
                gpconfig.plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                await gpconfig.save()
                logging.info(f"会话 {conv_id} 调整下次处理时间完成")
        except Exception as e:
            logging.error(f"会话 {conv_id} 调整下次处理时间失败: {e}")
            raise e
        # 生成回复
        reply_content = await self.msgprocessor.generate_reply(conv_id, recent_messages, temperature=0.7)
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

        return reply_dict

    async def schedule_maintenance(self) -> None:
        """定期维护任务"""
        # 获取所有需要处理的群组
        distinct_convs = await self.group_config.get_distinct_group_ids(self.plugin_name)

        for conv_id in distinct_convs:
            # 检查是否到达处理时间
            gpconfig = await self.group_config.get_config(conv_id, self.plugin_name)
            plugin_config = gpconfig.plugin_config or {}

            next_process_time = plugin_config.get('next_process_time', 0)
            if time.time() > next_process_time or logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                # 处理该会话
                await self.process_conversation(conv_id, "")

                # 更新下次处理时间
                plugin_config['next_process_time'] = time.time() + self.config.get('batch_interval', 30*60)
                gpconfig.plugin_config = plugin_config
                await gpconfig.save()
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
        keywords = query.split(" ")
        memory_list = []
        for keyword in keywords:
            memory_list.extend(await self.retriever.search_for_memories(keyword, user_id, limit, conv_id))
        return memory_list

    async def get_queue_status_reply(self, conv_id: Optional[str] = None) -> str:
        """获取队列状态

        Args:
            conv_id: 可选的会话ID，如果指定则只返回该会话的状态

        Returns:
            队列状态回复字符串
        """
        # 获取基本队列统计
        stats = await self.message_repo.get_queue_stats(conv_id)

        # 获取处理间隔
        batch_interval = self.config.get('batch_interval', 30*60)

        # 如果指定了conv_id，获取该会话的下次处理时间
        if conv_id:
            gpconfig = await self.group_config.get_config(conv_id, self.plugin_name)
            plugin_config = gpconfig.plugin_config or {}
            next_process_time = plugin_config.get('next_process_time', 0)
            next_process_in = max(0, int(next_process_time - time.time()))
        else:
            # 获取所有会话的下一次处理时间中最早的
            distinct_convs = await self.group_config.get_distinct_group_ids(self.plugin_name)
            next_times = []

            for conv in distinct_convs:
                gpconfig = await self.group_config.get_config(conv, self.plugin_name)
                plugin_config = gpconfig.plugin_config or {}
                next_process_time = plugin_config.get('next_process_time', 0)
                if next_process_time > 0:
                    next_times.append(next_process_time)

            if next_times:
                next_process_in = max(0, int(min(next_times) - time.time()))
            else:
                next_process_in = 0

        # 生成统计信息
        reply = f"会话 {conv_id} 状态:\n" if conv_id else "人格系统状态:\n"
        reply += f"- 消息总数: {stats.get('total_messages', 0)} 条\n"
        reply += f"- 未处理消息: {stats.get('unprocessed_messages', 0)} 条\n"
        reply += f"- 下次处理: {next_process_in} 秒后\n"
        reply += f"- 处理间隔: {batch_interval} 秒\n"

        # 显示数据库信息
        db_type = "PostgreSQL" if self.config.get("use_postgres") else "SQLite"
        reply += f"- 短期记忆数据库: {db_type}\n"
        reply += f"- 长期记忆数据库: Neo4j\n"

        return reply

    async def simulate_reply(self, conv_id: str, test_message: Optional[str] = None) -> Dict:
        """模拟回复
        使用function calling功能生成回复

        Args:
            conv_id: 会话ID
            test_message: 可选的测试消息，如果提供则临时添加到消息历史末尾

        Returns:
            回复内容字典
        """
        try:
            # 获取会话最近消息
            messages = await self.short_term.get_recent_messages(conv_id, self.config.get('queue_history_size', 40))
            if not messages:
                logging.info(f"会话 {conv_id} 没有历史消息")
                return None

            # 如果提供了测试消息，临时添加到消息列表末尾
            if test_message:
                # 复制最后一条消息的格式，只替换内容
                last_message = messages[-1].copy()
                last_message["content"] = test_message
                last_message["is_bot"] = False
                last_message["is_direct"] = True
                messages.append(last_message)

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
            node = await self.memory_repo.update_or_create_node(conv_id, node_name, is_permanent=True)

            # 创建常驻记忆
            memory_data = {
                "conv_id": conv_id,
                "title": memory_title,
                "content": memory_content,
                "is_permanent": True
            }
            memory = await self.memory_repo.store_memory(conv_id, memory_data)

            # 使用现有的_link_nodes_to_memory函数建立关联
            await self.memory_repo._link_nodes_to_memory(memory, [str(node.uid)])

            logging.info(f"创建常驻节点-记忆对: 节点[{node_name}], 记忆[{memory_title}]")

            return {
                "node": {
                    "id": str(node.uid),
                    "name": node.name,
                    "is_permanent": node.is_permanent
                },
                "memory": {
                    "id": str(memory.uid),
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

    async def parse_chat_history(self, bot_id: str, file_path: str, conv_id: str) -> List[Dict]:
        """解析聊天历史记录文件

        Args:
            bot_id: 机器人的ID
            file_path: 聊天记录文件路径
            conv_id: 会话ID

        Returns:
            消息字典列表
        """
        try:
            import re
            from datetime import datetime

            # 检查文件是否存在
            if not os.path.exists(file_path):
                logging.error(f"文件不存在: {file_path}")
                return []

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析消息头部和内容
            header_pattern = r'(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}) (.*?)\((\d+)\)'
            headers = [(m.group(1), m.group(2), m.group(3), m.start(), m.end())
                    for m in re.finditer(header_pattern, content)]

            messages = []
            for i, (time_str, user_name, user_id, start_idx, end_idx) in enumerate(headers):
                # 去除用户名中的标题（【】包围）
                user_name = re.sub(r'【.*?】', '', user_name).strip()

                # 解析消息时间
                created_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

                # 提取消息内容
                if i < len(headers) - 1:
                    next_start = headers[i+1][3]
                    msg_content = content[end_idx:next_start].strip()
                else:
                    msg_content = content[end_idx:].strip()

                # 检查消息是否来自机器人
                is_bot = (user_id == bot_id)

                # 创建消息字典
                message = {
                    "conv_id": conv_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "content": msg_content,
                    "created_at": created_at,
                    "is_bot": is_bot,
                    "is_direct": False,  # 默认非直接对话
                    "is_processed": True,  # 标记为已处理
                    "metadata": {}
                }

                messages.append(message)

            logging.info(f"解析聊天记录完成，共 {len(messages)} 条消息")

            # 如果消息列表为空，则不进行删除
            if messages == []:
                return messages

            # 获取最早和最晚消息时间
            earliest_time = min(msg["created_at"] for msg in messages)
            latest_time = max(msg["created_at"] for msg in messages)

            # 删除时间范围内的消息
            deleted_messages = await self.message_repo.delete_messages_by_time_range(
                conv_id, earliest_time, latest_time
            )
            logging.info(f"已删除会话 {conv_id} 中 {earliest_time} 到 {latest_time} 之间的 {deleted_messages} 条消息")

            # 删除时间范围内的记忆及关联
            await self.memory_repo.delete_memories_by_time_range(
                conv_id, earliest_time, latest_time
            )
            logging.info(f"已删除会话 {conv_id} 中 {earliest_time} 到 {latest_time} 之间的记忆")

            # 添加消息到短期记忆
            for message in messages:
                await self.short_term.add_message(message)

            return messages

        except Exception as e:
            logging.error(f"解析聊天记录失败: {e}")
            return []