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
        
        try:
            response = await self._call_api(prompt)
            result = self._parse_response(response, message)
            return result
        except Exception as e:
            logging.error(f"AI处理失败: {e}")
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
        
        try:
            response = await self._call_api(payload)
            content = response["choices"][0]["message"]["content"].strip()
            return content
        except Exception as e:
            logging.error(f"AI回复生成失败: {e}")
            raise ValueError(f"无法生成回复: {e}")
    
    async def _call_api(self, payload_or_prompt) -> Dict:
        """调用AI API"""
        if isinstance(payload_or_prompt, str):
            # 为会话分析设置系统提示和较低温度
            system_message = "你是一个专业的对话分析助手，请从群聊消息中提取结构化话题信息，严格按照指定的JSON格式返回结果。"
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": payload_or_prompt}
                ],
                "temperature": 0.1,  # 低温度，提高确定性
                "max_tokens": 1500,   # 足够返回多个话题
                "response_format": {"type": "text"}
            }
        else:
            payload = payload_or_prompt
        
        logging.debug(f"调用AI API: {self.model}")
        
        if OPENAI_CLIENT_AVAILABLE:
            try:
                # 使用OpenAI客户端
                response = await self.client.chat.completions.create(**payload)
                
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
            response = await self.client.post(
                self.api_base,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logging.error(f"API调用失败: {response.status_code} {response.text}")
                raise Exception(f"API调用失败: {response.status_code}")
                
            result = response.json()
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
        # 会话处理提示模板 - 不使用直接的format，而是手动替换，避免花括号转义问题
        conversation_prompt = """
        分析群聊消息并提取以下结构化信息。
        - 话题情感倾向（positive/negative）
        - 话题延续可能性（0.0-1.0）：根据对话结束时的情况，预测此话题在未来继续讨论的可能性

        消息格式：[时间] {用户}：内容
        返回要求：{
        "topics": [
            {
            "topic": "话题核心词",
            "summary": "{用户A}讨论了X，{用户B}回应了Y",
            "entities": ["实体1", "对象2", "概念3"], # 最少1个
            "start_time": "YYYY-MM-DD HH:mm",
            "end_time": "YYYY-MM-DD HH:mm",
            "continuation_probability": 0.7  # 话题延续可能性，范围0.0-1.0
            }
        ]
        }

        群聊消息:
        CONVERSATION_PLACEHOLDER
        """
        
        try:
            # 手动替换占位符，避免format函数的花括号转义问题
            prompt = conversation_prompt.replace("CONVERSATION_PLACEHOLDER", conversation_text)
        except Exception as e:
            logging.error(f"会话处理提示生成失败: {e}")
            return []
        
        logging.info(f"会话处理提示: {prompt[:200]}...")  # 只记录前200个字符避免日志过长
        
        try:
            response = await self._call_api(prompt)
            logging.debug(f"会话处理API响应: {response}")
            result = self._parse_conversation_response(response)
            logging.debug(f"会话处理API响应解析结果: {result}")
            return result
        except Exception as e:
            logging.error(f"会话处理失败: {e}")
            return []
        
    def _parse_conversation_response(self, response: dict) -> List[Dict]:
        """解析会话处理API响应"""
        try:
            content = response["choices"][0]["message"]["content"].strip()
            
            # 处理Markdown格式
            if "```json" in content and "```" in content:
                # 提取Markdown代码块中的JSON
                start_idx = content.find("```json") + 7
                end_idx = content.rfind("```")
                logging.info(f"start_idx: {start_idx}, end_idx: {end_idx}")
                # 修正条件：如果找到了开始标记且有结束标记
                if start_idx >= 7 and end_idx > start_idx:
                    content = content[start_idx:end_idx].strip()
                    logging.info("成功从Markdown代码块中提取JSON内容")
                    logging.debug(f"提取的JSON内容: {content[:100]}...")
            
            logging.info(f"原始响应内容: {content[:200]}...") # 只记录前200个字符
            
            # 解析JSON对象
            data = json.loads(content)
            
            # 如果是对象且包含topics字段
            if isinstance(data, dict) and "topics" in data:
                logging.info(f"成功解析为JSON对象，包含 {len(data['topics'])} 个话题")
                topics = data["topics"]
                # 确保每个话题有必要字段
                for topic in topics:
                    self._ensure_topic_fields(topic)
                return topics
            
            # 如果得到的JSON不符合预期格式
            logging.warning(f"API返回的JSON格式不符合预期: {type(data)}")
            return []
                
        except Exception as e:
            logging.error(f"解析会话响应失败: {e}")
            logging.info(f"原始响应: {response}")
            return []
            
    def _ensure_topic_fields(self, topic: Dict) -> None:
        """确保话题对象包含所有必要字段"""
        # 确保基本字段存在
        topic.setdefault("topic", "未命名话题")
        topic.setdefault("summary", "")
        topic.setdefault("entities", [])
        topic.setdefault("start_time", "")
        topic.setdefault("end_time", "")
        # 确保continuation_probability字段存在
        if "continuation_probability" not in topic:
            topic["continuation_probability"] = 0.5