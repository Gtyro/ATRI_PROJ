"""消息处理器，负责处理消息并生成回复"""

import logging
import time
import random
from typing import Dict, List, Optional, Any, Tuple

from .ai_processor import AIProcessor
from plugins.models import GroupPluginConfig

class MessageProcessor:
    """
    消息处理器，负责处理消息并生成回复
    """
    
    def __init__(self, config: Dict, ai_processor: AIProcessor, group_character: Dict[str, str] = {}, queue_history_size: int = 40):
        """初始化消息处理器
        
        Args:
            config: 配置信息
            ai_processor: AI处理器实例
            group_character: 群组人格配置
            queue_history_size: 队列历史消息保留数量
        """
        # 配置
        self.config = config
        self.queue_history_size = queue_history_size
        
        # 使用传入的AI处理器
        self.ai_processor = ai_processor
        
        # 群组配置
        self.group_config = GroupPluginConfig
        
        logging.info("消息处理器初始化成功")
    
    async def extract_topics_from_messages(self, conv_id: str, messages: List[Dict]) -> List[Dict]:
        """从消息中提取话题
        
        Args:
            conv_id: 会话ID
            messages: 消息列表
            
        Returns:
            话题列表
        """
        return await self.ai_processor.extract_topics(conv_id, messages)
    
    async def should_respond(self, conv_id: str, topics: List[Dict]) -> bool:
        """判断是否应该回复
        
        Args:
            conv_id: 会话ID
            topics: 话题列表
            
        Returns:
            是否应该回复
        """
        # 如果是私聊，总是回复
        if conv_id.startswith("private_"):
            return True
            
        # 如果没有话题，不回复
        if not topics:
            return False
            
        # 如果有未完结话题，判断是否应该回复
        unfinished_topics = [t for t in topics if t["completed_status"] == False]
        
        if unfinished_topics:
            # 获取群组的回复概率
            try:
                response_rate = 0.3  # 默认回复概率
                config = await self.group_config.get_config(conv_id, "persona")
                if config and config.plugin_config:
                    response_rate = config.plugin_config.get("response_rate", 0.3)
                
                # 基于最高的话题概率和群组概率决定是否回复
                max_prob = max([t.get("continuation_probability", 0) for t in unfinished_topics])
                should_reply = random.random() < (response_rate * max_prob)
                
                if should_reply and len(topics) > 0:
                    return True
            except Exception as e:
                logging.error(f"获取群组回复概率失败: {e}")
                return False
        
        return False
    
    async def generate_reply(self, conv_id: str, messages: List[Dict], temperature: float = 0.7, long_memory_promt: str = "") -> Dict[str, str]:
        """生成回复
        
        Args:
            conv_id: 会话ID
            messages: 消息列表
            temperature: 温度
            
        Returns:
            生成的回复
        """
        # 准备消息格式
        chat_messages = []
        for msg in messages:
            if not isinstance(msg, Dict): # 如果是记忆数据，则直接插入到消息历史中
                continue
                
            user_name = msg.get("user_name", "用户")
            content = msg.get("content", "")
            is_direct = msg.get("is_direct", False)
            is_bot = msg.get("is_bot", False)
            
            role = "assistant" if is_bot else "user"
            message_text = f"[{user_name}]{'对你' if is_direct else ''}说: {content}" if not is_bot else content
            
            chat_messages.append({"role": role, "content": message_text})
        logging.info(f"消息历史: \n{'\n'.join([f'[{msg['role']}] {msg['content']}' for msg in chat_messages])}")
                
        # 生成回复
        response = await self.ai_processor.generate_response(
            conv_id=conv_id,
            messages=chat_messages,
            temperature=temperature,
            long_memory_promt=long_memory_promt
        )
        
        return {"content": response} 