"""
记忆系统AI处理模块 - 通过AI服务增强记忆处理能力

该模块负责调用外部AI API处理消息，实现更高级的：
1. 消息分类 - 识别消息类型
2. 情感分析 - 检测情感极性和强度
3. 标签提取 - 识别关键概念和实体
"""

import json
import logging
import re
import httpx
import asyncio
from typing import Dict, List, Any, Optional, Union

# 添加OpenAI客户端支持
try:
    from openai import AsyncOpenAI
    OPENAI_CLIENT_AVAILABLE = True
except ImportError:
    OPENAI_CLIENT_AVAILABLE = False
    logging.warning("未安装openai库，将使用httpx直接调用API。建议安装openai: pip install openai")

# 配置
DEFAULT_TIMEOUT = 60.0  # 超时时间（秒）
MAX_RETRIES = 0  # 最大重试次数
RETRY_DELAY = 1  # 重试延迟（秒）

class AIProcessor:
    """通过AI API增强记忆处理能力"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat", api_base: str = "https://api.deepseek.com"):
        """初始化AI处理器
        
        Args:
            api_key: API密钥
            model: 使用的模型名称
            api_base: API基础URL
        """
        if not api_key:
            raise ValueError("AI处理器需要API密钥才能运行")
            
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        
        # 初始化客户端
        if OPENAI_CLIENT_AVAILABLE:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_base, timeout=DEFAULT_TIMEOUT)
            logging.info(f"使用OpenAI客户端调用API: {self.api_base}")
        else:
            self.client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
            # 确保API端点正确
            if "/v1/chat/completions" not in self.api_base:
                self.api_base = f"{self.api_base.rstrip('/')}/v1/chat/completions"
            logging.info(f"使用httpx客户端调用API: {self.api_base}")
        
        logging.info(f"api_base: {self.api_base}")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 记忆处理提示模板
        self.memory_prompt = """
        请分析以下消息，并以JSON格式返回以下信息：
        1. memory_type: 消息类型，可选值为 ["question", "fact", "event", "preference", "greeting", "farewell", "general"]
        2. emotion: 情感分析，包含两个字段：
           - polarity: 情感极性，范围为 [-1.0, 1.0]，负值表示消极，正值表示积极
           - intensity: 情感强度，范围为 [0.0, 1.0]
        3. tags: 标签列表，提取消息中的关键概念、实体、主题，最多5个标签
        4. summary: 一句话总结消息的核心内容
        
        只返回JSON格式，不要有其他文字。
        
        消息: {message}
        """
        
        # 对话系统提示
        self.chat_system_prompt = "你需要扮演指定角色，根据角色的信息，模仿她的语气进行线上的日常对话。"
        try:
            with open("data/prompt.txt", "r", encoding="utf-8") as f:
                self.chat_system_prompt += f.read()
        except Exception as e:
                logging.warning("data/prompt.txt不存在，使用默认系统提示")
                self.chat_system_prompt += "任务 你需要扮演一个AI助手，进行线上的日常对话。"
    
    async def process_memory(self, message: str) -> Dict:
        """处理消息，返回结构化的记忆信息"""
        prompt = self.memory_prompt.format(message=message)
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._call_api(prompt)
                result = self._parse_response(response, message)
                return result
            except Exception as e:
                if attempt < MAX_RETRIES:
                    logging.warning(f"AI处理失败，尝试重试 ({attempt+1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(1)  # 重试前短暂延迟
                else:
                    logging.error(f"AI处理最终失败: {e}")
                    raise ValueError(f"无法处理消息: {e}")
    
    async def generate_response(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """生成对话响应
        
        Args:
            messages: 对话历史，格式为[{"role": "user", "content": "消息内容"}, ...]
            temperature: 温度参数，控制创造性，0.0-1.0
            
        Returns:
            生成的回复文本
        """
        # 添加系统提示
        full_messages = [{"role": "system", "content": self.chat_system_prompt}]
        full_messages.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": 800
        }
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._call_api(payload)
                content = response["choices"][0]["message"]["content"].strip()
                return content
            except Exception as e:
                if attempt < MAX_RETRIES:
                    logging.warning(f"AI回复生成失败，尝试重试 ({attempt+1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(1)  # 重试前短暂延迟
                else:
                    logging.error(f"AI回复生成最终失败: {e}")
                    raise ValueError(f"无法生成回复: {e}")
    
    async def _call_api(self, payload_or_prompt) -> Dict:
        """调用AI API"""
        if isinstance(payload_or_prompt, str):
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": payload_or_prompt}],
                "temperature": 0.1,  # 低温度，提高可预测性
                "max_tokens": 300
            }
        else:
            payload = payload_or_prompt
        
        logging.debug(f"调用AI API: {payload}")
        
        if OPENAI_CLIENT_AVAILABLE:
            try:
                # 使用OpenAI客户端
                response = await self.client.chat.completions.create(**payload)
                logging.debug(f"API响应: {response}")
                
                # 将OpenAI响应对象转换为旧格式的字典
                response_dict = {
                    "choices": [
                        {
                            "message": {
                                "content": response.choices[0].message.content,
                                "role": response.choices[0].message.role
                            },
                            "index": response.choices[0].index
                        }
                    ],
                    "id": response.id,
                    "model": response.model,
                    "created": response.created
                }
                
                return response_dict
            except Exception as e:
                logging.error(f"OpenAI客户端API调用失败: {e}")
                raise Exception(f"API调用失败: {e}")
        else:
            # 使用httpx直接调用
            logging.debug(f"API基础URL: {self.api_base}")
            response = await self.client.post(
                self.api_base,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logging.error(f"API调用失败: {response.status_code} {response.text}")
                raise Exception(f"API调用失败: {response.status_code}")
                
            result = response.json()
            logging.debug(f"API响应: {result}")
            return result
    
    def _parse_response(self, response: Dict, original_message: str) -> Dict:
        """解析API响应"""
        try:
            content = response["choices"][0]["message"]["content"].strip()
            
            # 去掉 Markdown 格式部分
            if content.startswith("```json") and content.endswith("```"):
                content = content[7:-3].strip()  # 去掉开头和结尾的 Markdown 标记
            
            # 尝试解析JSON
            result = json.loads(content)
            
            # 验证必要字段
            if not all(k in result for k in ["memory_type", "emotion", "tags"]):
                raise ValueError("响应缺少必要字段")
                
            return result
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.error(f"解析AI响应失败: {e}")
            raise ValueError(f"无法解析AI响应: {e}") 

    async def process_conversation_batch(self, conversation_text: str) -> List[Dict]:
        """批量处理会话，提取话题和交互模式
        
        Args:
            conversation_text: 格式化的会话文本
            
        Returns:
            话题列表，每个话题包含主题、摘要、实体、时间范围等
        """
        # 会话处理提示模板
        conversation_prompt = """
        分析以下群聊消息，提取其中的主要话题及交互。消息格式为 "[时间] {用户ID}: 消息内容"。

        请提取所有独立的话题，并以JSON数组格式返回，每个话题(数组元素/字典)包含以下信息：
        1. topic: 话题名称，简洁表达话题核心
        2. summary: 话题摘要，使用 {userX} 表示用户（不要替换为实际ID），描述用户间的主要交互
        3. entities: 话题中提到的关键实体、对象、概念等
        4. start_time: 话题开始时间（从消息时间提取）
        5. end_time: 话题结束时间（从消息时间提取）

        只返回JSON数组，不要有其他文字。如果没有明确的话题，返回空数组 []。

        群聊消息:
        {conversation}
        """
        
        prompt = conversation_prompt.format(conversation=conversation_text)
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._call_api(prompt)
                logging.debug(f"会话处理API响应: {response}")
                result = self._parse_conversation_response(response)
                logging.debug(f"会话处理API响应解析结果: {result}")
                return result
            except Exception as e:
                if attempt < MAX_RETRIES:
                    logging.warning(f"会话处理尝试 {attempt+1}/{MAX_RETRIES+1} 失败: {e}，重试中...")
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                else:
                    logging.error(f"会话处理失败，已达最大重试次数: {e}")
                    raise
                    
        return []
        
    def _parse_conversation_response(self, response: str) -> List[Dict]:
        """解析会话处理API响应"""
        try:
            # 提取JSON部分
            json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                topics = json.loads(json_str)
                return topics
            else:
                # 尝试直接解析整个响应
                return json.loads(response)
        except Exception as e:
            logging.error(f"解析会话响应失败: {e}")
            logging.debug(f"原始响应: {response}")
            return []