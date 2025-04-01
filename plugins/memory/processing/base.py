"""
记忆系统处理模块 - 负责处理和转换输入消息

该模块将输入消息处理成结构化记忆，通过AI增强处理实现高质量的语义分析。
"""

import logging
import os
from typing import Optional
import time
import json
import re
from datetime import datetime
from typing import Dict, List

from .ai import AIProcessor

class MemoryProcessor:
    """负责将输入消息处理成结构化记忆"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化处理器"""
        # 加载API密钥
        self.api_key = api_key
        
        
        self.ai_processor = AIProcessor(
            api_key=self.api_key
        )
        logging.info(f"AI记忆处理器已启用，使用模型: {self.ai_processor.model}")
    
    async def process_conversation(self, conv_id: str, messages: List[Dict]) -> List[Dict]:
        """处理一批对话消息，提取话题和交互模式
        
        Args:
            conv_id: 对话ID
            messages: 消息列表，每个消息包含user_id、user_name、content和timestamp
            
        Returns:
            话题列表
            每个话题固定包含topic、conv_id、message_ids:list、entities:list、involved_users:list、completed_status:bool
            完结话题额外包括summary、start_time、end_time
            未完结话题额外包括continuation_probability
            元数据字段包括processed_at、message_count、conversation_duration_seconds、processed_by、model
        """
        # 准备提交给AI的消息格式
        formatted_messages = []
        message_times = []  # 记录所有消息的时间戳
        
        seq_to_db_id = {i: item["id"] for i, item in enumerate(messages)}

        # 为每条消息分配一个简短的数字ID
        for idx, msg in enumerate(messages, 1):
            # 消息ID就是简单的序号
            msg_id = idx
            
            timestamp = msg["timestamp"]
            # 只保留到分钟
            formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
            
            user_name = msg.get("user_name", "未知用户")
            
            # 获取回复信息
            metadata_str = msg.get("metadata", "{}")
            if isinstance(metadata_str, str):
                try:
                    metadata = json.loads(metadata_str)
                except:
                    metadata = {}
            else:
                metadata = metadata_str
                
            # 构建消息前缀
            prefix = f"[{msg_id}] [{formatted_time}] "
            
            # 添加用户标识
            if msg.get("is_me", False): # 是否是机器人发的
                prefix += f"{user_name}(你)"
            else:
                prefix += f"{user_name}"
                
            # 添加回复标识
            if msg.get("is_direct", False): # 是否是发给机器人的
                prefix += "对你说"
                
            # 最终格式：[编号] [时间] {用户}[对{用户}]：内容
            formatted_messages.append(f"{prefix}: {msg['content']}")
            message_times.append(timestamp)
        
        conversation_text = "\n".join(formatted_messages)
        
        # 记录对话处理开始
        logging.info(f"开始处理对话 {conv_id} 的对话，共 {len(messages)} 条消息")
        
        try:
            # 获取AI处理结果
            topics = await self.ai_processor.process_conversation_batch(conversation_text)
            
            # 如果没有提取到任何话题，返回空列表
            if not topics:
                logging.debug(f"未从对话中提取到话题: {conv_id}")
                return []
                
            # 处理AI返回的结果
            processed_topics = []
            for topic in topics:
                # 添加基础元数据
                topic["conv_id"] = conv_id
                topic["message_ids"] = [seq_to_db_id[i] for i in topic.get("message_ids", [])]
                # 提取参与话题的用户
                involved_users = set()
                for user_ref in re.findall(r"{([^}]+)}", topic.get("summary", "")):
                    involved_users.add(user_ref)
                topic["involved_users"] = list(involved_users)
                
                # 确保实体列表存在且不为空
                if not topic.get("entities"):
                    if topic.get("completed_status"):
                        logging.warning(f"已完结话题缺少实体列表: {topic.get('topic')}")
                    
                    topic["entities"] = []
                    
                    # 尝试从话题名称提取至少一个实体
                    if topic.get("topic") and topic.get("topic") != "未命名话题":
                        topic["entities"].append(topic["topic"])
                
                # 添加话题元数据
                if "metadata" not in topic:
                    topic["metadata"] = {}
                
                # 记录处理信息
                topic["metadata"].update({
                    "processed_at": time.time(),
                    "message_count": len(messages),
                    "conversation_duration_seconds": (message_times[-1] - message_times[0]).total_seconds() if len(message_times) > 1 else 0,
                    "processed_by": "ai_processor",
                    "model": self.ai_processor.model
                })
                
                # 记录消息ID (用于跟踪已处理的消息)
                if "message_ids" not in topic:
                    topic["message_ids"] = []
                
                processed_topics.append(topic)
                
            logging.info(f"成功从对话提取话题: {len(processed_topics)} 个")
            return processed_topics
        except Exception as e:
            logging.error(f"对话批处理失败: {e}")
            return []