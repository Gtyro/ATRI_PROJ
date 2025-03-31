import logging
import os
from typing import Optional

from openai import AsyncOpenAI

from ..utils.config import load_config

class LLMClient:
    def __init__(self, base_url: str = "https://api.deepseek.com"):
        self.config = load_config()
        self.base_url = self.config.get("base_url", base_url)
        self.api_key = self._load_api_key()
    
    def _load_api_key(self) -> Optional[str]:
        """加载API密钥"""
        # 首先尝试从环境变量读取
        api_key = os.environ.get("API_KEY")
        
        # 如果环境变量中没有，尝试从配置文件读取
        if not api_key:
            api_key = self.config.get("api_key")
        
        return api_key
    
    async def call_api(self, payload_or_prompt: Optional[dict] = None) -> str:
        """调用API"""
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
        
        try:
            # 使用OpenAI客户端
            response = await self.client.chat.completions.create(**payload)
            if response.choices[0].finish_reason != "stop":
                logging.warning(f"OpenAI客户端API调用失败: {response.choices[0].finish_reason}")
            content = response.choices[0].message.content.strip()
            
            return content
        except Exception as e:
            logging.error(f"OpenAI客户端API调用失败: {e}")
            raise Exception(f"API调用失败: {e}")


# The following is deprecated
async def response2dict(response) -> dict:
    '''temporary deprecated'''
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