import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .prompt import TOPIC_EXTRACTION_PROMPT


class AIProcessor:
    """AI处理器，负责调用大语言模型进行处理"""

    def __init__(self, api_key: str,
                 model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com",
                 group_character: Dict[str, str] = {},
                 queue_history_size: int = 40):
        """初始化AI处理器

        Args:
            api_key: API密钥
            model: 模型名称
            group_character: 群组人格配置
            queue_history_size: 队列历史消息保留数量
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client = None
        self._init_client()
        self.group_character = group_character
        self.queue_history_size = queue_history_size
        self.memory_retrieval_callback = None
        logging.info(f"AI处理器已创建，使用模型: {model}")

    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            logging.debug("OpenAI客户端初始化成功")
        except ImportError:
            logging.error("未安装openai库，请使用pip install openai安装")
            raise ImportError("未安装openai库，请使用pip install openai安装")
        except Exception as e:
            logging.error(f"OpenAI客户端初始化失败: {e}")
            raise ValueError(f"OpenAI客户端初始化失败: {e}")

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
            receiver = "你" if msg['is_direct'] else None
            content = msg.get("content", "")
            formatted_time = msg["created_at"].strftime("%Y-%m-%d %H:%M") # 只保留到分钟
            if receiver:
                history_text.append(f"[{i}] [{formatted_time}] [{sender}]对{receiver}说: {content}")
            else:
                history_text.append(f"[{i}] [{formatted_time}] [{sender}]说: {content}")
            seqid2msgid[i] = msg['id']
        history_str = "\n".join(history_text)
        logging.info(f"消息历史: \n{history_str}")

        # 构建系统提示词
        system_prompt = TOPIC_EXTRACTION_PROMPT
        if len(messages) > self.queue_history_size:
            system_prompt = system_prompt.replace("TIME_PLACEHOLDER", messages[-1]["created_at"].strftime("%Y-%m-%d %H:%M"))
        else:
            system_prompt = system_prompt.replace("TIME_PLACEHOLDER", datetime.now().strftime("%Y-%m-%d %H:%M"))

        try:
            response = await self._call_api(
                system_prompt,
                [{"role": "user", "content": f"消息历史:\n{history_str}"}],
                temperature=0.2
            )
            logging.info(f"提取话题响应: \n{response}")

            # 解析响应
            try:
                if response.startswith("```json") and response.endswith("```"):
                    response = response[7:-3]
                result = json.loads(response)
                topics = []
                # 处理已完结话题
                for ct in result.get("completed_topics", []):
                    ct['content'] = ct.pop('summary')
                    ct.update({
                        "id": str(uuid.uuid4()),
                        "conv_id": conv_id,
                        "completed_status": True,
                        "continuation_probability": 0.0
                    })
                    topics.append(ct)

                # 处理未完结话题
                for ot in result.get("ongoing_topics", []):
                    ot.update({
                        "id": str(uuid.uuid4()),
                        "conv_id": conv_id,
                        "completed_status": False,
                        "summary": ot.get("title", "")  # 未完结话题用标题作为摘要
                    })
                    topics.append(ot)

                # 将seqid2msgid添加到topics中
                for topic in topics:
                    topic['message_ids'] = [seqid2msgid[msg_id] for msg_id in topic['message_ids']]
                    topic['nodes'] = topic.pop('keywords')
                return topics
            except json.JSONDecodeError as e:
                logging.error(f"解析话题失败: {e}, 响应内容: {response}...")
                # 创建一个默认话题
                return []

        except Exception as e:
            logging.error(f"提取话题失败: {e}")
            # 出错也返回一个简单的话题
            return []

    async def generate_response(self, conv_id: str, messages: List[Dict], temperature: float = 0.7, long_memory_promt: str = "") -> str:
        """生成回复

        Args:
            conv_id: 会话ID
            messages: 消息列表
            temperature: 温度
            long_memory_promt: 长期记忆提示
        Returns:
            生成的回复
        """
        # 构建系统提示词
        system_prompt = "你需要扮演一位指定角色，根据角色的信息，模仿ta的语气进行线上的日常对话，一次回复不要包含太多内容，直接说话，不要带上\"[角色]说\"。\n"
        try:
            if conv_id.startswith('group_'):
                with open(f"{self.group_character[conv_id]}", "r", encoding="utf-8") as f:
                    system_prompt += f.read()
            else:
                with open("data/persona/default.txt", "r", encoding="utf-8") as f:
                    system_prompt += f.read()
        except Exception as e:
            logging.error(f"读取角色信息失败: {e}")
            logging.error(f"角色信息: {self.group_character}")
            return ""
        if long_memory_promt:
            system_prompt += f"\n{long_memory_promt}"

        try:
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
                            "required": ["query"]
                        },
                    }
                },
            ]

            # 将消息转换为API格式
            api_messages = [{"role": "system", "content": system_prompt}]
            for msg in messages:
                role = "assistant" if msg.get("is_bot", False) else "user"
                api_messages.append({"role": role, "content": msg.get("content", "")})

            # 第一次调用API，可能会触发函数调用
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                tools=tools,
                tool_choice="required",
                temperature=0.2,
                max_tokens=1200
            )

            response_message = response.choices[0].message
            final_messages = api_messages.copy()

            # 检查是否有函数调用
            memory_context = ""
            if hasattr(response_message, "tool_calls") and response_message.tool_calls:
                # 添加助手消息
                final_messages.append({
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        } for tool_call in response_message.tool_calls
                    ]
                })

                for tool_call in response_message.tool_calls:
                    # 只处理检索记忆的工具调用
                    if tool_call.function.name == "retrieve_memories":
                        try:
                            # 解析参数
                            function_args = json.loads(tool_call.function.arguments)
                            query = function_args.get("query", "")
                            logging.info(f"检索记忆: {query}")

                            # 调用format_memories直接获取格式化的记忆文本
                            if hasattr(self, "memory_retrieval_callback") and self.memory_retrieval_callback:
                                memory_context = await self.memory_retrieval_callback(query, user_id=None, conv_id=conv_id)
                                logging.info(f"记忆文本: {memory_context}")
                                # 将记忆文本添加到消息中
                                final_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": memory_context
                                })
                        except Exception as e:
                            logging.error(f"处理记忆检索工具调用失败: {e}")
                            # 即使出错也需要添加空响应
                            final_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": "记忆检索失败"
                            })

            # 使用完整消息历史生成最终回复
            if memory_context:
                # 如果有记忆上下文，使用更新后的消息列表生成最终回复
                final_response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=final_messages,
                    temperature=temperature,
                    max_tokens=1200
                )
                content = final_response.choices[0].message.content or ""
            else:
                logging.warning(f"没有记忆上下文，function calling失败: {response}")
                # 如果没有记忆上下文，直接使用第一次调用的结果
                content = await self._call_api(
                system_prompt,
                api_messages,
                temperature=temperature
            )

            # 对回复内容进行处理
            content = re.sub(r'.*?说[:：]\s*', '', content, count=1)

            # 对可能的错误进行处理，如果content中仍然有[]，则去除[], 并log
            if re.search(r'\[.*?\]', content):
                logging.warning(f"生成回复中仍然有[]，进行处理: {content}")
                content = re.sub(r'\[.*?\]说?[:：]?.*', '', content, flags=re.DOTALL) # 如果出现第2个[xx]说，说明回复异常，之后的内容都删除
                logging.warning(f"处理后: {content}")
            # 对换行符进行处理，如果content中包含\n，则删除包括\n之后的内容
            if "\n" in content:
                logging.warning(f"生成回复中包含\\n，进行处理: {content}")
                content = content.split("\n")[0]
                logging.warning(f"处理后: {content}")
            # 如果content中包含"笑死"，则删除
            if "笑死" in content:
                logging.warning(f"生成回复中包含'笑死'，进行处理: {content}")
                content = re.sub(r'^笑死', '', content)
                logging.warning(f"处理后: {content}")
            logging.info(f"生成回复: {content}")
            return content
        except Exception as e:
            logging.error(f"生成回复失败: {e}")
            return ""

    async def _call_api(self, system_prompt: str, messages: List[Dict],
                        temperature: float = 0.7, max_tokens: int = 1200) -> str:
        """调用OpenAI API

        Args:
            system_prompt: 系统提示词
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大生成token数

        Returns:
            API响应内容
        """
        if self._client is None:
            self._init_client()

        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": msg["role"],
                    "content": msg["content"]
                } for msg in full_messages],
                temperature=temperature,
                max_tokens=max_tokens
            )
            logging.info(f"API调用成功，用量信息: {response.usage.completion_tokens} tokens")
            return response.choices[0].message.content or ""
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_details = str(e)
            stack_trace = traceback.format_exc()

            # 记录详细错误信息
            logging.error(f"API调用失败 - 错误类型: {error_type}")
            logging.error(f"错误详情: {error_details}")
            logging.error(f"堆栈跟踪: {stack_trace}")

            # 尝试记录请求信息（不含敏感内容）
            try:
                logging.error(f"请求模型: {self.model}")
                logging.error(f"消息数量: {len(full_messages)}")
                logging.error(f"温度参数: {temperature}")
                logging.error(f"最大token数: {max_tokens}")
            except Exception as log_err:
                logging.error(f"记录请求信息失败: {log_err}")

            raise

    def set_memory_retrieval_callback(self, callback):
        """设置记忆检索回调函数

        Args:
            callback: 回调函数，需要接受query, user_id, conv_id参数
        """
        self.memory_retrieval_callback = callback