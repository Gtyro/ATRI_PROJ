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
        
        # 对话系统提示
        self.chat_system_prompt = "你需要扮演指定角色，根据角色的信息，模仿她的语气进行线上的日常对话，一次回复尽量不要超过20字。"
        try:
            with open("data/prompt.txt", "r", encoding="utf-8") as f:
                self.chat_system_prompt += f.read()
        except Exception as e:
                logging.warning("data/prompt.txt不存在，使用默认系统提示")
                self.chat_system_prompt += "任务 你需要扮演一个AI助手，进行线上的日常对话。"
    
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
            "max_tokens": 100
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
            # 为对话分析设置系统提示和较低温度
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
        """批量处理对话，提取话题和交互模式
        
        Args:
            conversation_text: 格式化的对话文本，包含消息编号
            
        Returns:
            话题列表，每个话题包含主题、摘要、实体、时间范围等
        """
        # 对话处理提示模板 - 不使用直接的format，而是手动替换，避免花括号转义问题
        conversation_prompt = """
        分析群聊消息并提取以下结构化信息。需要区分已完结和未完结的话题：
        
        1. 已完结话题：时间较早、讨论告一段落的话题。对这类话题，提取详细信息。
        2. 未完结话题：最近正在讨论、尚未结束的话题。对这类话题，返回相关消息编号并评估话题延续可能性。
        
        消息格式：[编号] [时间] {用户}：内容
        
        返回结果格式：
        {
          "completed_topics": [
            {
              "topic": "已完结话题名称",
              "summary": "{用户A}讨论了X，{用户B}回应了Y",
              "entities": ["实体1", "对象2", "概念3"],
              "start_time": "YYYY-MM-DD HH:mm",
              "end_time": "YYYY-MM-DD HH:mm",
              "message_ids": [1, 2, 3, 4] // 相关消息的编号
            }
          ],
          "ongoing_topics": [
            {
              "topic": "未完结话题名称",
              "entities": ["相关实体1", "相关实体2"], // 捕获未完结话题的相关实体
              "message_ids": [8, 9, 10], // 相关消息的编号
              "continuation_probability": 0.7, // 话题延续的可能性 (0.0-1.0)
              "last_message_id": 10 // 最后一条相关消息的编号，用于追踪对话最新进展
            }
          ]
        }
        
        判断已完结话题标准：
        1. 最后一条相关消息已经过去较长时间（与最新消息相比）
        2. 话题已有明确结论或自然终止
        
        未完结话题的continuation_probability评估标准：
        1. 高概率 (0.7-1.0): 话题急需人解答/参与；存在直接提问
        2. 中等概率 (0.3-0.7): 话题可能受益于人参与；存在间接提问；讨论陷入停滞
        3. 低概率 (0.0-0.3): 人类交流顺畅；无需干预；话题即将自然结束
        
        注意：
        - 每条消息可能属于多个话题
        - 未完结话题无需提供详细总结，但需要捕获相关实体和评估话题延续可能性
        - 确保每个话题至少关联一条消息

        群聊消息:
        CONVERSATION_PLACEHOLDER
        """
        
        try:
            # 手动替换占位符，避免format函数的花括号转义问题
            prompt = conversation_prompt.replace("CONVERSATION_PLACEHOLDER", conversation_text)
        except Exception as e:
            logging.error(f"对话处理提示生成失败: {e}")
            return []
        
        logging.info(f"对话处理提示: {prompt[:200]}...")  # 只记录前200个字符避免日志过长
        
        try:
            response = await self._call_api(prompt)
            logging.debug(f"对话处理API响应: {response}")
            result = self._parse_conversation_response(response)
            logging.debug(f"对话处理API响应解析结果: {result}")
            return result
        except Exception as e:
            logging.error(f"对话处理失败: {e}")
            return []
        
    def _parse_conversation_response(self, response: dict) -> List[Dict]:
        """解析对话处理API响应"""
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
                    logging.debug(f"提取的JSON内容: {content}")
            
            logging.info(f"原始响应内容: {content[:200]}...") # 只记录前200个字符
            
            # 解析JSON对象
            data = json.loads(content)
            
            result = []
            
            # 处理已完结的话题
            if isinstance(data, dict) and "completed_topics" in data:
                completed_topics = data["completed_topics"]
                logging.info(f"成功解析为JSON对象，包含 {len(completed_topics)} 个已完结话题")
                
                for topic in completed_topics:
                    # 确保每个话题有必要字段
                    self._ensure_topic_fields(topic, is_completed=True)
                    # 标记为已完结话题
                    topic["status"] = "completed"
                    result.append(topic)
            
            # 处理未完结的话题
            if isinstance(data, dict) and "ongoing_topics" in data:
                ongoing_topics = data["ongoing_topics"]
                logging.info(f"成功解析为JSON对象，包含 {len(ongoing_topics)} 个未完结话题")
                
                for topic in ongoing_topics:
                    # 确保每个话题有必要字段
                    self._ensure_topic_fields(topic, is_completed=False)
                    # 标记为未完结话题
                    topic["status"] = "ongoing"
                    result.append(topic)
            
            # 兼容旧版格式
            elif isinstance(data, dict) and "topics" in data:
                topics = data["topics"]
                logging.info(f"使用兼容模式，解析旧版格式，包含 {len(topics)} 个话题")
                for topic in topics:
                    self._ensure_topic_fields(topic, is_completed=True)
                    topic["status"] = "completed"  # 旧版本都视为已完结
                    # 如果没有message_ids，设置为空列表
                    if "message_ids" not in topic:
                        topic["message_ids"] = []
                    result.append(topic)
            
            if not result:
                # 如果得到的JSON不符合预期格式
                logging.warning(f"API返回的JSON格式不符合预期: {type(data)}")
                
            return result
                
        except Exception as e:
            logging.error(f"解析对话响应失败: {e}")
            logging.info(f"原始响应: {response}")
            return []
            
    def _ensure_topic_fields(self, topic: Dict, is_completed: bool) -> None:
        """确保话题对象包含所有必要字段
        
        Args:
            topic: 话题字典对象
            is_completed: 是否为已完结话题
        """
        # 确保基本字段存在
        topic.setdefault("topic", "未命名话题")
        
        # 确保message_ids字段存在
        topic.setdefault("message_ids", [])
        
        # 确保实体列表字段存在
        topic.setdefault("entities", [])
        
        # 如果有话题名称但没有实体，添加话题名为实体
        if topic["topic"] and topic["topic"] != "未命名话题" and not topic["entities"]:
            topic["entities"].append(topic["topic"])
        
        if is_completed:
            # 已完结话题需要完整的字段
            topic.setdefault("summary", "")
            topic.setdefault("start_time", "")
            topic.setdefault("end_time", "")
        else:
            # 未完结话题特有字段
            topic.setdefault("continuation_probability", 0.3)  # 默认为中低概率
            if "message_ids" in topic and topic["message_ids"]:
                # 如果有消息ID，尝试设置最后一条消息ID
                topic.setdefault("last_message_id", topic["message_ids"][-1])
            else:
                topic.setdefault("last_message_id", 0)
            
            # 未完结话题的基本字段
            topic.setdefault("summary", "（未完结话题）")
        
        # 确保status字段存在
        topic.setdefault("status", "completed" if is_completed else "ongoing")