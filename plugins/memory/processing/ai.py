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
import time
import httpx
import asyncio
from typing import Dict, List, Any, Optional, Union

# 添加OpenAI客户端支持
from openai import AsyncOpenAI
from ..api.llm_api import LLMClient
from .prompt import conversation_prompt

# 配置
DEFAULT_TIMEOUT = 60.0  # 超时时间（秒）

class AIProcessor:
    """通过AI API增强记忆处理能力"""
    
    def __init__(self, api_key:str, model: str, base_url: str):
        """初始化AI处理器
        
        Args:
            api_key: API密钥
            model: 使用的模型名称
            api_base: API基础URL
        """
        self.model = model
            
        # 初始化客户端
        self.client = LLMClient(api_key=api_key, model=model, base_url=base_url)
        
        logging.info(f"api_base: {self.client.base_url}")
        
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
            content = await self.client.call_api(payload)
            return content
        except Exception as e:
            logging.error(f"AI回复生成失败: {e}")
            raise ValueError(f"无法生成回复: {e}")

    async def process_conversation_batch(self, conversation_text: str) -> List[Dict]:
        """批量处理对话，提取话题和交互模式
        
        Args:
            conversation_text: 格式化的对话文本，包含消息编号
            
        Returns:
            话题列表，每个话题包含主题、摘要、实体、时间范围等
        """
        # 对话处理提示模板 - 不使用直接的format，而是手动替换，避免花括号转义问题
        prompt = conversation_prompt.replace("（与最新消息相比）", f"现在时间:{time.strftime('%Y-%m-%d %H:%M',time.localtime())}")
        prompt = prompt.replace("CONVERSATION_PLACEHOLDER", conversation_text)
        
        logging.info(f"对话处理提示: {prompt[:200]}...")  # 只记录前200个字符避免日志过长
        
        try:
            content = await self.client.call_api(prompt)
            logging.debug(f"对话处理API响应: {content}")
            topics = self._parse_conversation_response(content)
            logging.debug(f"对话处理API响应解析结果: {topics}")
            return topics
        except Exception as e:
            logging.error(f"对话处理失败: {e}")
            return []
        
    def _parse_conversation_response(self, content: str) -> List[Dict]:
        """解析对话处理API响应"""
        try:
            # 处理Markdown格式
            if content.startswith("```json") and content.endswith("```"):
                content = content[7:-3].strip()  # 去掉开头和结尾的 Markdown 标记
            else:
                logging.error(f"API返回的JSON格式不符合预期: {type(content)}")
                raise ValueError(f"API返回的JSON格式不符合预期: {type(content)}")
            
            # 解析JSON对象
            data = json.loads(content)
            
            topics = []
            
            topic_types = ["completed_topics", "ongoing_topics"]
            for topic_type in topic_types:
                if topic_type in data:
                    topics = data[topic_type]
                    logging.info(f"成功解析为JSON对象，包含 {len(topics)} 个{topic_type}")
                    topics.extend(self._ensure_topic_fields(topics, is_completed=topic_type == "completed_topics"))
            
            if not topics:
                # 如果得到的JSON不符合预期格式
                logging.warning(f"API返回的JSON格式不符合预期: {type(data)}")
                
            return topics
                
        except Exception as e:
            logging.error(f"解析对话响应失败: {e}")
            logging.info(f"原始内容: {content}")
            return []
    
    def _ensure_topic_fields(self, topics: List[Dict], is_completed: bool) -> List[Dict]:
        """确保话题对象包含所有必要字段，如果缺失必要字段则跳过，返回正确的话题列表
        
        Args:
            topics: 话题字典对象列表
            is_completed: 是否为已完结话题
            
        Returns:
            topics: 正确的话题列表
        """
        for topic in topics:
            check_dict = {
                "topic": str,
                "message_ids": list,
                "entities": list
            }
            for key, value in check_dict.items():
                if key not in topic:
                    logging.error(f"话题缺少必要字段'{key}': {topic}")
                    continue
                if not isinstance(topic[key], value):
                    logging.error(f"话题'{key}'的类型不正确: {topic}")
                    continue

            if is_completed:
                check_dict = {
                    "summary": str,
                    "start_time": str,
                    "end_time": str
                }
                for key, value in check_dict.items():
                    if key not in topic:
                        logging.error(f"已完结话题缺少必要字段'{key}': {topic}")
                        continue
            else:
                # 检查未完结话题必要字段
                check_dict = {
                    "continuation_probability": float
                }
                for key, value in check_dict.items():
                    if key not in topic:
                        logging.error(f"未完结话题缺少必要字段'{key}': {topic}")
                        continue
            topic["completed_status"] = is_completed