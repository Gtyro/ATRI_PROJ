import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..prompts import (
    MEMORY_SELECTION_PROMPT,
    REPLY_HISTORY_KEYWORDS_PROMPT,
    TOPIC_EXTRACTION_PROMPT,
)
from .client import LLMClient
from .errors import LLMOutputParseError, LLMProviderError
from .types import LLMCallParams
from src.core.domain import PersonaConfig


class AIProcessor:
    """AI处理器，负责调用大语言模型进行处理"""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        group_character: Optional[Dict[str, str]] = None,
        queue_history_size: Optional[int] = None,
        provider_name: str = "openai_compatible",
        supports_response_format: bool = False,
        raise_on_error: bool = False,
        timeout: Optional[float] = None,
    ):
        """初始化AI处理器

        Args:
            api_key: API密钥
            model: 模型名称
            group_character: 群组人格配置
            queue_history_size: 队列历史消息保留数量
            provider_name: Provider标识，用于日志与追踪
            supports_response_format: 是否支持 response_format 结构化输出
            raise_on_error: 是否在错误时抛出异常（用于回退链）
            timeout: 请求超时时间（秒）
        """
        if model is None or base_url is None or queue_history_size is None:
            try:
                defaults = PersonaConfig.load()
                model = model or defaults.model
                base_url = base_url or defaults.base_url
                queue_history_size = queue_history_size or defaults.queue_history_size
            except Exception as exc:
                raise ValueError(f"缺少 LLM 配置且无法读取默认配置: {exc}") from exc

        if model is None or base_url is None or queue_history_size is None:
            raise ValueError("LLM 配置缺失：model/base_url/queue_history_size 必须提供")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider_name = provider_name
        self.supports_response_format = supports_response_format
        self.raise_on_error = raise_on_error
        self.timeout = timeout
        self._llm_client: Optional[LLMClient] = None
        self._init_client()
        self.group_character = group_character or {}
        self.queue_history_size = int(queue_history_size)
        self.memory_retrieval_callback: Optional[Callable[..., Any]] = None
        logging.info(f"AI处理器已创建，使用模型: {model}")

    def _init_client(self):
        """初始化OpenAI兼容客户端"""
        try:
            self._llm_client = LLMClient(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                provider_name=self.provider_name,
                supports_response_format=self.supports_response_format,
                timeout=self.timeout,
            )
        except ImportError:
            logging.error("未安装openai库，请使用pip install openai安装")
            raise ImportError("未安装openai库，请使用pip install openai安装")
        except Exception as e:
            logging.error(f"OpenAI客户端初始化失败: {e}")
            raise ValueError(f"OpenAI客户端初始化失败: {e}")

    @staticmethod
    def _normalize_keywords(candidates: List[Any]) -> List[str]:
        keywords: List[str] = []
        seen = set()
        for candidate in candidates:
            keyword = str(candidate or "").strip()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            keywords.append(keyword)
        return keywords

    @classmethod
    def _parse_keyword_output(cls, result: Any, raw_text: str) -> List[str]:
        if isinstance(result, list):
            return cls._normalize_keywords(result)
        if isinstance(result, dict):
            keywords = result.get("keywords", [])
            if isinstance(keywords, list):
                return cls._normalize_keywords(keywords)

        # 兜底：按空格/逗号拆分
        separators = ["，", ",", " ", "\n"]
        candidates = [str(raw_text or "")]
        for sep in separators:
            candidates = [part for keyword in candidates for part in keyword.split(sep)]
        return cls._normalize_keywords(candidates)

    @staticmethod
    def _normalize_memory_payload(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("memory_retrieval_callback 必须返回结构化字典")

        memory_context = str(payload.get("memory_context", "") or "").strip()
        raw_candidates = payload.get("candidates", [])
        candidates: List[Dict[str, Any]] = []
        seen_ids = set()
        if isinstance(raw_candidates, list):
            for raw_candidate in raw_candidates:
                if not isinstance(raw_candidate, dict):
                    continue
                memory_id = str(raw_candidate.get("id", "") or "").strip()
                if not memory_id or memory_id in seen_ids:
                    continue
                seen_ids.add(memory_id)
                candidates.append({
                    "id": memory_id,
                    "title": str(raw_candidate.get("title", "") or "").strip(),
                    "summary": str(raw_candidate.get("summary", "") or "").strip(),
                    "source": str(raw_candidate.get("source", "") or "").strip(),
                    "weight": float(raw_candidate.get("weight", 0.0) or 0.0),
                    "created_at": float(raw_candidate.get("created_at", 0.0) or 0.0),
                })

        selected_ids = [
            str(item or "").strip()
            for item in payload.get("selected_ids", []) or []
            if str(item or "").strip()
        ]
        return {
            "memory_context": memory_context,
            "candidates": candidates,
            "selected_ids": selected_ids,
        }

    @staticmethod
    def _format_memory_candidates(candidates: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for index, candidate in enumerate(candidates, 1):
            lines.append(
                (
                    f"{index}. id={candidate['id']}\n"
                    f"标题: {candidate.get('title') or '无标题'}\n"
                    f"摘要: {candidate.get('summary') or '无摘要'}\n"
                    f"来源: {candidate.get('source') or '未知'}\n"
                    f"权重: {candidate.get('weight', 0.0):.2f}"
                )
            )
        return "\n\n".join(lines)

    @classmethod
    def _parse_memory_selection_output(
        cls,
        result: Any,
        raw_text: str,
        *,
        allowed_ids: List[str],
    ) -> List[str]:
        selected_ids: List[Any] = []
        if isinstance(result, dict):
            selected_ids = result.get("selected_ids", []) or []
        elif isinstance(result, list):
            selected_ids = result
        else:
            selected_ids = re.split(r"[\s,，]+", str(raw_text or "").strip())

        normalized_ids: List[str] = []
        seen = set()
        allowed_id_set = {str(memory_id or "").strip() for memory_id in allowed_ids}
        for candidate_id in selected_ids:
            memory_id = str(candidate_id or "").strip()
            if not memory_id or memory_id in seen or memory_id not in allowed_id_set:
                continue
            seen.add(memory_id)
            normalized_ids.append(memory_id)
        return normalized_ids[:3]

    async def select_memory_candidates(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[str]:
        if not candidates or self._llm_client is None:
            return []

        candidate_text = self._format_memory_candidates(candidates)
        params = LLMCallParams(temperature=0.2, max_tokens=300)
        try:
            output = await self._llm_client.structured_output(
                [{
                    "role": "user",
                    "content": f"当前查询:\n{query}\n\n候选记忆:\n{candidate_text}",
                }],
                params=params,
                system_prompt=MEMORY_SELECTION_PROMPT,
                operation="memory_candidate_selection",
                strict=False,
            )
            selected_ids = self._parse_memory_selection_output(
                output.data,
                output.raw_text,
                allowed_ids=[candidate["id"] for candidate in candidates],
            )
            logging.info(
                "记忆候选选择完成: query=%s candidate_count=%s selected_ids=%s",
                query,
                len(candidates),
                selected_ids,
            )
            return selected_ids
        except LLMProviderError as e:
            logging.error(f"记忆候选选择失败: {e}")
            if self.raise_on_error:
                raise
            return []
        except Exception as e:
            logging.error(f"记忆候选选择失败: {e}")
            if self.raise_on_error:
                raise
            return []

    async def extract_topics(self, conv_id: str, messages: List[Dict]) -> List[Dict]:
        """从消息中提取话题

        Args:
            conv_id: 会话ID
            messages: 消息列表

        Returns:
            话题列表(completed_status)
        """
        # 构建消息历史
        history_text = []
        seqid2msgid = {}
        for i, msg in enumerate(messages):
            sender = "你" if msg.get("is_bot", False) else msg.get("user_name", "用户")
            receiver = "你" if msg["is_direct"] else None
            content = msg.get("content", "")
            formatted_time = msg["created_at"].strftime("%Y-%m-%d %H:%M")  # 只保留到分钟
            if receiver:
                history_text.append(f"[{i}] [{formatted_time}] [{sender}]对{receiver}说: {content}")
            else:
                history_text.append(f"[{i}] [{formatted_time}] [{sender}]说: {content}")
            seqid2msgid[i] = msg["id"]
        history_str = "\n".join(history_text)
        logging.info(f"话题提取消息历史: \n{history_str}")

        # 构建系统提示词
        system_prompt = TOPIC_EXTRACTION_PROMPT
        if len(messages) > self.queue_history_size:
            system_prompt = system_prompt.replace(
                "TIME_PLACEHOLDER",
                messages[-1]["created_at"].strftime("%Y-%m-%d %H:%M"),
            )
        else:
            system_prompt = system_prompt.replace(
                "TIME_PLACEHOLDER",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            )

        if self._llm_client is None:
            self._init_client()
        try:
            params = LLMCallParams(temperature=0.2, max_tokens=2000)
            output = await self._llm_client.structured_output(
                [{"role": "user", "content": f"消息历史:\n{history_str}"}],
                params=params,
                system_prompt=system_prompt,
                operation="extract_topics",
                strict=True,
            )
            result = output.data
            logging.info(f"提取话题响应: \n{result}")
            if not isinstance(result, dict):
                raise LLMOutputParseError(
                    "话题提取结构化输出格式错误",
                    provider=self.provider_name,
                    operation="extract_topics",
                )

            topics = []
            # 处理已完结话题
            for ct in result.get("completed_topics", []):
                ct["content"] = ct.pop("summary")
                ct.update({
                    "id": str(uuid.uuid4()),
                    "conv_id": conv_id,
                    "completed_status": True,
                    "continuation_probability": 0.0,
                })
                topics.append(ct)

            # 处理未完结话题
            for ot in result.get("ongoing_topics", []):
                ot.update({
                    "id": str(uuid.uuid4()),
                    "conv_id": conv_id,
                    "completed_status": False,
                    "summary": ot.get("title", ""),  # 未完结话题用标题作为摘要
                })
                topics.append(ot)

            # 将seqid2msgid添加到topics中
            for topic in topics:
                topic["message_ids"] = [seqid2msgid[msg_id] for msg_id in topic["message_ids"]]
                topic["nodes"] = topic.pop("keywords")
            return topics
        except LLMProviderError as e:
            logging.error(f"提取话题失败: {e}")
            if self.raise_on_error:
                raise
            return []
        except Exception as e:
            logging.error(f"提取话题失败: {e}")
            if self.raise_on_error:
                raise
            return []

    async def extract_reply_keywords_from_history(self, conv_id: str, messages: List[Dict]) -> List[str]:
        """从最近消息历史中提取回复前关键词。"""
        if not messages:
            return []

        lines = []
        for index, msg in enumerate(messages, 1):
            sender = "你" if msg.get("is_bot", False) else msg.get("user_name", "用户")
            receiver = "你" if msg.get("is_direct") else None
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if receiver:
                lines.append(f"{index}. [{sender}]对{receiver}说: {content}")
            else:
                lines.append(f"{index}. [{sender}]说: {content}")

        if not lines:
            return []

        prompt_input = "最近消息历史:\n" + "\n".join(lines)
        if self._llm_client is None:
            self._init_client()
        try:
            params = LLMCallParams(temperature=0.2, max_tokens=400)
            output = await self._llm_client.structured_output(
                [{"role": "user", "content": prompt_input}],
                params=params,
                system_prompt=REPLY_HISTORY_KEYWORDS_PROMPT,
                operation="extract_reply_keywords_from_history",
                strict=False,
            )
            result = output.data
            logging.info(f"历史消息回复关键词提取响应: {result if result is not None else output.raw_text}")
            return self._parse_keyword_output(result, output.raw_text)
        except LLMProviderError as e:
            logging.error(f"历史消息回复关键词提取失败: {e}")
            if self.raise_on_error:
                raise
            return []
        except Exception as e:
            logging.error(f"历史消息回复关键词提取失败: {e}")
            if self.raise_on_error:
                raise
            return []

    async def generate_response(
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
            long_memory_prompt: 长期记忆提示
            tool_choice: 工具调用策略（none/auto/required）
        Returns:
            生成的回复
        """
        normalized_tool_choice = str(tool_choice or "").strip().lower()
        if normalized_tool_choice not in {"none", "auto", "required"}:
            error = ValueError(
                f"未知 tool_choice={tool_choice}，仅支持 none/auto/required"
            )
            logging.error(str(error))
            if self.raise_on_error:
                raise error
            return ""

        # 构建系统提示词
        system_prompt = "你需要扮演一位指定角色，根据角色的信息，模仿ta的语气进行线上的日常对话，一次回复不要包含太多内容，直接说话，不要带上\"[角色]说\"。\n"
        fallback_system_prompt = "你是一只群友"
        try:
            if conv_id.startswith("group_"):
                group_id = conv_id.split("_")[1]
                prompt_file = self.group_character.get(group_id)
                if not prompt_file:
                    logging.warning(f"群组未配置人格文件，使用默认人格: {group_id}")
                    prompt_file = "data/persona/default.txt"
                elif not os.path.exists(prompt_file):
                    logging.warning(f"群组人格文件不存在，使用默认人格: {prompt_file}")
                    prompt_file = "data/persona/default.txt"
                with open(prompt_file, "r", encoding="utf-8") as f:
                    system_prompt += f.read()
            else:
                with open("data/persona/default.txt", "r", encoding="utf-8") as f:
                    system_prompt += f.read()
        except Exception as e:
            logging.error(f"读取角色信息失败: {e}")
            logging.error(f"角色信息: {self.group_character}")
            logging.warning("使用基础人格提示词回退: 你是一只群友")
            system_prompt = fallback_system_prompt
        if long_memory_prompt:
            system_prompt += f"\n{long_memory_prompt}"

        if self._llm_client is None:
            self._init_client()
        # 定义工具函数
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "retrieve_memories",
                    "description": "从数据库中根据具体实体（人名、物名、地点等）检索相关信息，使用空格分隔的若干个具体关键词",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "要查询的具体实体关键词，如果有多个，用空格分隔。",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
        ]

        # 将消息转换为API格式（不包含system，交由LLMClient统一注入）
        api_messages = []
        for msg in messages:
            role = msg.get("role")
            if role not in {"system", "user", "assistant", "tool"}:
                role = "assistant" if msg.get("is_bot", False) else "user"
            api_messages.append({"role": role, "content": msg.get("content", "")})

        try:
            final_params = LLMCallParams(temperature=temperature, max_tokens=1200)

            if normalized_tool_choice == "none":
                content = await self._llm_client.chat(
                    api_messages,
                    params=final_params,
                    system_prompt=system_prompt,
                    operation="no_tool_response",
                )
            else:
                tool_params = LLMCallParams(temperature=0.2, max_tokens=1200)
                tool_response = await self._llm_client.chat_with_tools(
                    api_messages,
                    tools=tools,
                    params=tool_params,
                    tool_choice=normalized_tool_choice,
                    system_prompt=system_prompt,
                    operation="memory_tool_call",
                )
                final_messages = api_messages.copy()
                memory_context = ""
                if tool_response.tool_calls:
                    final_messages.append(tool_response.message)
                    for tool_call in tool_response.tool_calls:
                        if tool_call.name != "retrieve_memories":
                            continue
                        try:
                            function_args = json.loads(tool_call.arguments)
                            query = function_args.get("query", "")
                            logging.info(f"检索记忆: {query}")

                            if self.memory_retrieval_callback:
                                retrieval_payload = self._normalize_memory_payload(
                                    await self.memory_retrieval_callback(
                                        query,
                                        user_id=None,
                                        conv_id=conv_id,
                                    )
                                )
                                memory_context = retrieval_payload["memory_context"]
                                candidates = retrieval_payload["candidates"]
                                if candidates:
                                    selected_ids = await self.select_memory_candidates(
                                        query=query,
                                        candidates=candidates,
                                    )
                                    if selected_ids:
                                        selected_payload = self._normalize_memory_payload(
                                            await self.memory_retrieval_callback(
                                                query,
                                                user_id=None,
                                                conv_id=conv_id,
                                                selected_ids=selected_ids,
                                                reinforce_selected=True,
                                            )
                                        )
                                        if selected_payload["memory_context"]:
                                            memory_context = selected_payload["memory_context"]

                                logging.info(f"记忆文本: {memory_context}")
                                final_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": memory_context,
                                })
                        except Exception as e:
                            logging.error(f"处理记忆检索工具调用失败: {e}")
                            final_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": "记忆检索失败",
                            })

                if memory_context:
                    content = await self._llm_client.chat(
                        final_messages,
                        params=final_params,
                        system_prompt=system_prompt,
                        operation="final_response",
                    )
                else:
                    logging.warning("没有记忆上下文，function calling失败")
                    content = await self._llm_client.chat(
                        api_messages,
                        params=final_params,
                        system_prompt=system_prompt,
                        operation="fallback_response",
                    )

            # 对回复内容进行处理
            content = re.sub(r".*?说[:：]\s*", "", content, count=1)

            # 对可能的错误进行处理，如果content中仍然有[]，则去除[], 并log
            if re.search(r"\[.*?\]", content):
                logging.warning(f"生成回复中仍然有[]，进行处理: {content}")
                content = re.sub(r"\[.*?\]说?[:：]?.*", "", content, flags=re.DOTALL)
                # 如果出现第2个[xx]说，说明回复异常，之后的内容都删除
                logging.warning(f"处理后: {content}")
            # 对换行符进行处理，如果content中包含\n，则删除包括\n之后的内容
            if "\n" in content:
                logging.warning(f"生成回复中包含\\n，进行处理: {content}")
                content = content.split("\n")[0]
                logging.warning(f"处理后: {content}")
            # 如果content中包含"笑死"，则删除
            if "笑死" in content:
                logging.warning(f"生成回复中包含'笑死'，进行处理: {content}")
                content = re.sub(r"^笑死", "", content)
                logging.warning(f"处理后: {content}")
            logging.info(f"生成回复: {content}")
            return content
        except LLMProviderError as e:
            logging.error(f"生成回复失败: {e}")
            if self.raise_on_error:
                raise
            return ""
        except Exception as e:
            logging.error(f"生成回复失败: {e}")
            if self.raise_on_error:
                raise
            return ""

    async def _call_api(
        self,
        system_prompt: str,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> str:
        """调用OpenAI API

        Args:
            system_prompt: 系统提示词
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大生成token数

        Returns:
            API响应内容
        """
        if self._llm_client is None:
            self._init_client()

        try:
            params = LLMCallParams(temperature=temperature, max_tokens=max_tokens)
            return await self._llm_client.chat(
                messages,
                params=params,
                system_prompt=system_prompt,
                operation="chat",
            )
        except LLMProviderError:
            raise

    def set_memory_retrieval_callback(self, callback: Callable[..., Any]) -> None:
        """设置记忆检索回调函数

        Args:
            callback: 回调函数，需要接受query, user_id, conv_id参数
        """
        self.memory_retrieval_callback = callback
