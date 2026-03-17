"""消息处理器，负责处理消息并生成回复。"""

import inspect
import logging
import random
from typing import Any, Dict, List, Optional, Union

from src.core.domain import PersonaConfig
from src.core.ports import LLMProvider


class MessageProcessor:
    """消息处理器，负责处理消息并生成回复。"""

    def __init__(
        self,
        config: Union[Dict[str, Any], PersonaConfig],
        llm_provider: LLMProvider,
        group_character: Optional[Dict[str, str]] = None,
        queue_history_size: Optional[int] = None,
        *,
        group_config: Optional[Any] = None,
        plugin_name: str = "persona",
    ):
        """初始化消息处理器

        Args:
            config: 配置信息
            llm_provider: LLM提供者实例
            group_character: 群组人格配置
            queue_history_size: 队列历史消息保留数量
            group_config: 群组配置模型或适配器
            plugin_name: 插件名称
        """
        # 配置
        self.config = config
        if queue_history_size is None:
            if isinstance(config, PersonaConfig):
                queue_history_size = config.queue_history_size
            elif isinstance(config, dict) and "queue_history_size" in config:
                queue_history_size = int(config["queue_history_size"])
            else:
                raise ValueError("queue_history_size 未配置")
        self.queue_history_size = int(queue_history_size)

        # 使用传入的LLM提供者
        self.llm_provider = llm_provider
        # 兼容旧逻辑的属性访问
        self.ai_processor = llm_provider

        self.group_character = group_character or {}
        self.group_config = group_config
        self.plugin_name = plugin_name

    async def extract_topics_from_messages(self, conv_id: str, messages: List[Dict]) -> List[Dict]:
        """从消息中提取话题

        Args:
            conv_id: 会话ID
            messages: 消息列表

        Returns:
            话题列表
        """
        return await self.llm_provider.extract_topics(conv_id, messages)

    async def extract_reply_keywords_from_history(self, conv_id: str, messages: List[Dict]) -> List[str]:
        """从最近消息历史中提取回复关键词。"""
        return await self.llm_provider.extract_reply_keywords_from_history(conv_id, messages)

    async def retrieve_memory_context(self, conv_id: str, keywords: List[str]) -> str:
        """根据关键词显式检索记忆，返回可注入回复提示词的文本。"""
        payload = await self.retrieve_memory_context_payload(conv_id, keywords)
        return str(payload.get("memory_context", "") or "").strip()

    async def retrieve_memory_context_payload(
        self,
        conv_id: str,
        keywords: List[str],
    ) -> Dict[str, Any]:
        """根据关键词显式检索记忆，并在可用时进行候选选择。"""
        normalized_keywords: List[str] = []
        seen = set()
        for item in keywords:
            keyword = str(item or "").strip()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            normalized_keywords.append(keyword)

        if not normalized_keywords:
            return {"query": "", "memory_context": "", "selected_ids": []}

        callback = getattr(self.llm_provider, "memory_retrieval_callback", None)
        if not callable(callback):
            logging.warning("未配置 memory_retrieval_callback，跳过显式记忆检索")
            return {"query": "", "memory_context": "", "selected_ids": []}

        query = " ".join(normalized_keywords)
        try:
            retrieval_result = callback(
                query,
                user_id=None,
                conv_id=conv_id,
            )
            if inspect.isawaitable(retrieval_result):
                retrieval_result = await retrieval_result
            if not isinstance(retrieval_result, dict):
                raise TypeError("memory_retrieval_callback 必须返回包含 memory_context 的字典")
            memory_context = str(retrieval_result.get("memory_context", "") or "").strip()
            selected_ids: List[str] = []
            candidates = retrieval_result.get("candidates", [])
            selector = getattr(self.llm_provider, "select_memory_candidates", None)
            if isinstance(candidates, list) and candidates and callable(selector):
                selection_result = selector(query, candidates)
                if inspect.isawaitable(selection_result):
                    selection_result = await selection_result
                if isinstance(selection_result, list):
                    selected_ids = [
                        str(memory_id or "").strip()
                        for memory_id in selection_result
                        if str(memory_id or "").strip()
                    ]
                if selected_ids:
                    selected_payload = callback(
                        query,
                        user_id=None,
                        conv_id=conv_id,
                        selected_ids=selected_ids,
                        reinforce_selected=False,
                    )
                    if inspect.isawaitable(selected_payload):
                        selected_payload = await selected_payload
                    if not isinstance(selected_payload, dict):
                        raise TypeError("memory_retrieval_callback 必须返回包含 memory_context 的字典")
                    memory_context = str(selected_payload.get("memory_context", "") or "").strip()
            return {
                "query": query,
                "memory_context": memory_context,
                "selected_ids": selected_ids,
            }
        except Exception as e:
            logging.error(f"显式记忆检索失败: {e}")
            return {
                "query": query,
                "memory_context": "",
                "selected_ids": [],
            }

    async def reinforce_memory_selection(
        self,
        conv_id: str,
        query: str,
        selected_ids: List[str],
    ) -> None:
        """在回复成功后强化已选中的显式记忆。"""
        callback = getattr(self.llm_provider, "memory_retrieval_callback", None)
        if not callable(callback):
            return
        normalized_selected_ids = [
            str(memory_id or "").strip()
            for memory_id in selected_ids
            if str(memory_id or "").strip()
        ]
        if not query or not normalized_selected_ids:
            return
        try:
            result = callback(
                query,
                user_id=None,
                conv_id=conv_id,
                selected_ids=normalized_selected_ids,
                reinforce_selected=True,
            )
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            logging.error(f"显式记忆强化失败: {e}")

    async def should_respond(self, conv_id: str, topics: List[Dict]) -> bool:
        """判断是否应该回复

        Args:
            conv_id: 会话ID
            topics: 话题列表

        Returns:
            是否应该回复
        """
        # 如果是私聊，总是回复
        if conv_id.startswith("private_"):
            return True

        # 如果没有话题，不回复
        if not topics:
            return False

        # 如果有未完结话题，判断是否应该回复
        unfinished_topics = [t for t in topics if t["completed_status"] is False]

        if unfinished_topics:
            # 获取群组的回复概率
            try:
                response_rate = self._default_response_rate()
                if self.group_config:
                    group_id = conv_id.split("_")[1]
                    config = await self.group_config.get_config(group_id, self.plugin_name)
                    if config and config.plugin_config:
                        response_rate = config.plugin_config.get("response_rate", response_rate)

                # 基于最高的话题概率和群组概率决定是否回复
                max_prob = max([t.get("continuation_probability", 0) for t in unfinished_topics])
                should_reply = random.random() < (response_rate * max_prob)

                if should_reply and len(topics) > 0:
                    return True
            except Exception as e:
                logging.error(f"获取群组回复概率失败: {e}")
                return False

        return False

    def _default_response_rate(self) -> float:
        if isinstance(self.config, PersonaConfig):
            return self.config.default_response_rate
        if "default_response_rate" not in self.config:
            raise ValueError("default_response_rate 未配置")
        return float(self.config["default_response_rate"])

    async def generate_reply(
        self,
        conv_id: str,
        messages: List[Dict],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        """生成回复

        Args:
            conv_id: 会话ID
            messages: 消息列表
            temperature: 温度
            long_memory_prompt: 长期记忆/图片上下文提示
            tool_choice: 工具调用策略（none/auto/required）

        Returns:
            生成的回复
        """
        # 准备消息格式
        chat_messages = []
        for msg in messages:
            if not isinstance(msg, dict):  # 如果是记忆数据，则直接插入到消息历史中
                continue

            user_name = msg.get("user_name", "用户")
            content = msg.get("content", "")
            is_direct = msg.get("is_direct", False)
            is_bot = msg.get("is_bot", False)

            role = "assistant" if is_bot else "user"
            message_text = f"[{user_name}]{'对你' if is_direct else ''}说: {content}" if not is_bot else content

            chat_messages.append({"role": role, "content": message_text})
        history_lines = [f"[{msg['role']}] {msg['content']}" for msg in chat_messages]
        logging.info("回复阶段消息历史: \n%s", "\n".join(history_lines))

        # 生成回复
        reply_content = await self.llm_provider.generate_response(
            conv_id=conv_id,
            messages=chat_messages,
            temperature=temperature,
            long_memory_prompt=long_memory_prompt,
            tool_choice=tool_choice,
        )

        return reply_content
