from datetime import datetime
import logging
import json
import re
import uuid
from typing import Dict, List, Any, Optional

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
        logging.info(f"AI处理器已创建，使用模型: {model}")
    
    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            logging.info("OpenAI客户端初始化成功")
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
            
        Returns:
            生成的回复
        """
        # 构建系统提示词
        system_prompt = "你需要扮演指定角色，根据角色的信息，模仿ta的语气进行线上的日常对话，一次回复不要包含太多内容，直接说话，不要带上\"[角色]说\"。\n"
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
            content = await self._call_api(
                system_prompt,
                messages,
                temperature=temperature
            )
            # 这里需要对content进行处理，去除[xx]说:部分
            content = re.sub(r'.*?说[:：]\s*', '', content, count=1)

            # 对可能的错误进行处理，如果content中仍然有[]，则去除[], 并log
            if re.search(r'\[.*?\]', content):
                logging.warning(f"生成回复中仍然有[]，进行处理: {content}")
                content = re.sub(r'\[.*?\]说?[:：]?.*', '', content, flags=re.DOTALL) # 如果出现第2个[xx]说，说明回复异常，之后的内容都删除
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
            logging.error(f"API调用失败: {e}")
            raise 