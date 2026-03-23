"""Persona 核心引擎实现，负责协调服务层。"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..domain import PersonaConfig
from ..services.conversation_service import ConversationService
from ..services.memory_service import MemoryService
from ..services.maintenance_service import MaintenanceService
from ..services.plugin_policy_service import PluginPolicyService
from ..services.queue_recovery_service import QueueRecoveryService
from ..services.reply_service import ReplyService
from src.infra.db.neo4j.unavailable import is_memory_repo_available


class PersonaEngineCore:
    """Persona 核心引擎，依赖外部装配注入。"""

    def __init__(
        self,
        *,
        config: PersonaConfig,
        plugin_name: str,
        group_config: Any,
        message_repo: Any,
        memory_repo: Any,
        short_term: Any,
        long_term: Any,
        msgprocessor: Any,
        retriever: Any,
        decay_manager: Any,
        reply_callback: Optional[Callable] = None,
        aiprocessor: Any = None,
        plugin_policy_service: Optional[PluginPolicyService] = None,
        image_context_service: Optional[Any] = None,
        basic_message_loader: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.plugin_name = plugin_name
        self.group_config = group_config
        self.message_repo = message_repo
        self.memory_repo = memory_repo
        self.short_term = short_term
        self.long_term = long_term
        self.msgprocessor = msgprocessor
        self.retriever = retriever
        self.decay_manager = decay_manager
        self.reply_callback = reply_callback
        self.aiprocessor = aiprocessor
        self.plugin_policy_service = plugin_policy_service
        self.image_context_service = image_context_service
        self.basic_message_loader = basic_message_loader

        self.memory_service = MemoryService(self.memory_repo, self.retriever)
        self.conversation_service = ConversationService(
            short_term=self.short_term,
            long_term=self.long_term,
            msgprocessor=self.msgprocessor,
            message_repo=self.message_repo,
            group_config=self.group_config,
            plugin_name=self.plugin_name,
            config=self.config,
            reply_callback=self.reply_callback,
            plugin_policy_service=self.plugin_policy_service,
            image_context_service=self.image_context_service,
        )
        self.reply_service = ReplyService(
            self.short_term,
            self.msgprocessor,
            self.config.queue_history_size,
        )
        self.maintenance_service = MaintenanceService(
            group_config=self.group_config,
            config=self.config,
            conversation_service=self.conversation_service,
            decay_manager=self.decay_manager,
            plugin_name=self.plugin_name,
            plugin_policy_service=self.plugin_policy_service,
        )
        self.queue_recovery_service = (
            QueueRecoveryService(
                short_term=self.short_term,
                queue_history_size=self.config.queue_history_size,
                recent_loader=self.basic_message_loader,
            )
            if self.basic_message_loader is not None
            else None
        )

    def set_reply_callback(self, reply_callback: Optional[Callable]) -> None:
        self.reply_callback = reply_callback
        self.conversation_service.set_reply_callback(reply_callback)

    async def initialize(self, reply_callback: Optional[Callable] = None) -> bool:
        if reply_callback is not None:
            self.set_reply_callback(reply_callback)
        logging.info("Persona 引擎初始化完成")
        return True

    async def close(self) -> None:
        if self.message_repo:
            await self.message_repo.close()
        logging.info("人格系统已关闭")

    async def process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self.conversation_service.process_message(message_data)

    async def process_conversation(
        self,
        conv_id: str,
        user_id: str,
        is_direct: bool = False,
    ) -> Optional[Dict[str, Any]]:
        return await self.conversation_service.process_conversation(conv_id, user_id, is_direct=is_direct)

    async def schedule_maintenance(self) -> None:
        await self.maintenance_service.schedule_maintenance()

    def get_queue_history_size(self) -> int:
        if isinstance(self.config, PersonaConfig):
            return self.config.queue_history_size
        if "queue_history_size" not in self.config:
            raise ValueError("queue_history_size 未配置")
        return int(self.config["queue_history_size"])

    async def extract_topics_from_messages(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return await self.msgprocessor.extract_topics_from_messages(conv_id, messages)

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        return await self.msgprocessor.extract_reply_keywords_from_history(conv_id, messages)

    async def retrieve_related_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        conv_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self.memory_service.retrieve_related_memories(
            query,
            user_id=user_id,
            limit=limit,
            conv_id=conv_id,
        )

    async def get_queue_status_reply(self, conv_id: Optional[str] = None) -> str:
        stats = await self.message_repo.get_queue_stats(conv_id)
        batch_interval = self.config.batch_interval

        if conv_id:
            group_id = conv_id.split("_")[1]
            gpconfig = await self.group_config.get_config(group_id, self.plugin_name)
            plugin_config = gpconfig.plugin_config or {}
            next_process_time = plugin_config.get("next_process_time", 0)
            next_process_in = max(0, int(next_process_time - time.time()))
        else:
            distinct_gids = await self.group_config.get_distinct_group_ids(self.plugin_name)
            next_times = []
            for group_id in distinct_gids:
                gpconfig = await self.group_config.get_config(group_id, self.plugin_name)
                plugin_config = gpconfig.plugin_config or {}
                next_process_time = plugin_config.get("next_process_time", 0)
                if next_process_time > 0:
                    next_times.append(next_process_time)

            if next_times:
                next_process_in = max(0, int(min(next_times) - time.time()))
            else:
                next_process_in = 0

        reply = f"会话 {conv_id} 状态:\n" if conv_id else "人格系统状态:\n"
        reply += f"- 消息总数: {stats.get('total_messages', 0)} 条\n"
        reply += f"- 未处理消息: {stats.get('unprocessed_messages', 0)} 条\n"
        reply += f"- 下次处理: {next_process_in} 秒后\n"
        reply += f"- 处理间隔: {batch_interval} 秒\n"

        db_type = "PostgreSQL" if self.config.use_postgres else "SQLite"
        reply += f"- 短期记忆数据库: {db_type}\n"
        if is_memory_repo_available(self.memory_repo):
            reply += "- 长期记忆数据库: Neo4j\n"
        else:
            reply += "- 长期记忆数据库: Neo4j（不可用，当前为降级模式）\n"

        return reply

    async def clear_queue(self, conv_id: str) -> int:
        """清空指定会话的短期记忆队列"""
        return await self.short_term.clear_messages(conv_id)

    async def rebuild_queue_from_basic_messages(self, conv_id: str) -> Dict[str, int]:
        """从基础消息表恢复指定会话的短期记忆队列。"""
        if self.queue_recovery_service is None:
            raise RuntimeError("基础消息恢复服务不可用")
        return await self.queue_recovery_service.rebuild_from_basic_messages(conv_id)

    async def set_group_prompt_file(self, group_id: str, prompt_file: str) -> None:
        if not self.group_config:
            raise RuntimeError("group_config 未配置，无法更新群组配置")
        config = await self.group_config.get_config(gid=group_id, plugin_name=self.plugin_name)
        plugin_config = config.plugin_config or {}
        plugin_config["prompt_file"] = prompt_file
        config.plugin_config = plugin_config
        await config.save()

    async def simulate_reply(
        self,
        conv_id: str,
        test_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.reply_service.simulate_reply(conv_id, test_message=test_message)

    async def force_reply(
        self,
        conv_id: str,
        test_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.reply_service.force_reply(conv_id, test_message=test_message)

    async def create_permanent_memory(
        self,
        conv_id: str,
        node_name: str,
        memory_title: str,
        memory_content: str,
    ) -> Dict[str, Any]:
        return await self.memory_service.create_permanent_memory(
            conv_id,
            node_name,
            memory_title,
            memory_content,
        )

    async def format_memories(self, query: str, user_id: str, conv_id: str) -> str:
        return await self.memory_service.format_memories(query, user_id, conv_id)

    async def retrieve_memory_payload(
        self,
        query: str,
        user_id: Optional[str] = None,
        conv_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return await self.memory_service.retrieve_memory_payload(
            query,
            user_id=user_id,
            conv_id=conv_id,
            **kwargs,
        )

    async def parse_chat_history(self, bot_id: str, file_path: str, conv_id: str) -> List[Dict[str, Any]]:
        try:
            if not os.path.exists(file_path):
                logging.error(f"文件不存在: {file_path}")
                return []

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            header_pattern = r"(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}) (.*?)\((\d+)\)"
            headers = [
                (m.group(1), m.group(2), m.group(3), m.start(), m.end())
                for m in re.finditer(header_pattern, content)
            ]

            messages = []
            for i, (time_str, user_name, user_id, start_idx, end_idx) in enumerate(headers):
                user_name = re.sub(r"【.*?】", "", user_name).strip()
                created_at = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

                if i < len(headers) - 1:
                    next_start = headers[i + 1][3]
                    msg_content = content[end_idx:next_start].strip()
                else:
                    msg_content = content[end_idx:].strip()

                is_bot = (user_id == bot_id)

                message = {
                    "conv_id": conv_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "content": msg_content,
                    "created_at": created_at,
                    "is_bot": is_bot,
                    "is_direct": False,
                    "is_processed": False,
                    "metadata": {},
                }

                messages.append(message)

            logging.info(f"解析聊天记录完成，共 {len(messages)} 条消息")

            if not messages:
                return messages

            earliest_time = min(msg["created_at"] for msg in messages)
            latest_time = max(msg["created_at"] for msg in messages)

            deleted_messages = await self.message_repo.delete_messages_by_time_range(
                conv_id, earliest_time, latest_time
            )
            logging.info(
                f"已删除会话 {conv_id} 中 {earliest_time} 到 {latest_time} 之间的 {deleted_messages} 条消息"
            )

            await self.memory_repo.delete_memories_by_time_range(
                conv_id, earliest_time, latest_time
            )
            logging.info(f"已删除会话 {conv_id} 中 {earliest_time} 到 {latest_time} 之间的记忆")

            for message in messages:
                await self.short_term.add_message(message)

            return messages
        except Exception as e:
            logging.error(f"解析聊天记录失败: {e}")
            return []
