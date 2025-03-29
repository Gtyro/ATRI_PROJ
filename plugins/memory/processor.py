"""
记忆系统处理模块 - 负责处理和转换输入消息

该模块将输入消息处理成结构化记忆，通过AI增强处理实现高质量的语义分析。
"""

from datetime import datetime
import re
import uuid
import time
import json
import logging
import os
from typing import Dict, List, Optional, Any
import asyncio

from .ai_processor import AIProcessor

class MemoryProcessor:
    """负责将输入消息处理成结构化记忆"""
    
    def __init__(self):
        """初始化处理器"""
        # 加载API密钥
        api_key = self._load_api_key()
        
        if not api_key:
            raise ValueError("记忆处理器需要API密钥才能初始化")
        
        # 初始化AI处理器
        model = self._load_model_config()
        api_base = self._load_api_base()
        
        self.ai_processor = AIProcessor(
            api_key=api_key,
            model=model,
            api_base=api_base
        )
        logging.info(f"AI记忆处理器已启用，使用模型: {model}")
    
    def _load_api_key(self) -> Optional[str]:
        """加载API密钥"""
        # 首先尝试从环境变量读取
        api_key = os.environ.get("API_KEY")
        
        # 如果环境变量中没有，尝试从配置文件读取
        if not api_key:
            config_path = "data/memory_config.yaml"
            if os.path.exists(config_path):
                try:
                    import yaml
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        api_key = config.get("api_key")
                except Exception as e:
                    logging.error(f"读取API配置失败: {e}")
        
        return api_key
    
    def _load_model_config(self) -> str:
        """加载模型配置"""
        config_path = "data/memory_config.yaml"
        default_model = "deepseek-chat"
        
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get("model", default_model)
            except Exception:
                pass
        
        return default_model
    
    def _load_api_base(self) -> str:
        """加载API基础URL"""
        config_path = "data/memory_config.yaml"
        default_api_base = "https://api.deepseek.com"
        
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get("api_base", default_api_base)
            except Exception:
                pass
        
        return default_api_base
    
    async def process_conversation(self, conv_id: str, messages: List[Dict]) -> List[Dict]:
        """处理一批对话消息，提取话题和交互模式
        
        Args:
            conv_id: 对话ID
            messages: 消息列表，每个消息包含user_id、user_name、content和timestamp
            
        Returns:
            话题列表，每个话题包含主题、摘要、实体、时间范围等信息
        """
        # 确保消息按时间排序
        sorted_messages = sorted(messages, key=lambda x: x.get("timestamp", 0))
        
        # 准备提交给AI的消息格式
        formatted_messages = []
        message_times = []  # 记录所有消息的时间戳
        message_map = {}    # 用于存储消息ID到原始消息的映射
        
        # 为每条消息分配一个简短的数字ID
        for idx, msg in enumerate(sorted_messages, 1):
            # 消息ID就是简单的序号
            msg_id = idx
            # 保存ID到原始消息的映射
            message_map[msg_id] = msg
            
            timestamp = datetime.fromtimestamp(msg.get("timestamp", time.time()))
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M") # 只保留到分钟
            
            # 消息格式添加更多标注
            is_direct = msg.get("is_direct", False)  # 是否是发给机器人的
            is_me = msg.get("is_me", False)      # 是否是机器人发的
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
                
            reply_to = metadata.get("reply_to", "")
            
            # 构建消息前缀
            prefix = f"[{msg_id}] [{formatted_time}] "
            
            # 添加用户标识
            if is_me:
                prefix += f"{user_name}(你)"
            else:
                prefix += f"{user_name}"
                
            # 添加回复标识
            if reply_to:
                prefix += f"对{reply_to}说"
            elif is_direct:
                prefix += "对你说"
                
            # 最终格式：[编号] [时间] {用户}[对{用户}]：内容
            formatted_messages.append(f"{prefix}: {msg['content']}")
            message_times.append(timestamp)
        
        conversation_text = "\n".join(formatted_messages)
        
        # 记录对话处理开始
        logging.info(f"开始处理对话 {conv_id} 的对话，共 {len(sorted_messages)} 条消息")
        
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
                
                # 提取参与话题的用户
                involved_users = set()
                for user_ref in re.findall(r"{([^}]+)}", topic.get("summary", "")):
                    involved_users.add(user_ref)
                topic["involved_users"] = list(involved_users)
                
                # 确保实体列表存在且不为空
                if not topic.get("entities"):
                    if topic.get("status") == "completed":
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
                    "message_count": len(sorted_messages),
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
        
    def find_associations(self, memory_data: Dict) -> List[Dict]:
        """查找关联 - 未来扩展功能
        未来可以实现更复杂的关联发现逻辑
        """
        # 此版本返回空关联
        return [] 
