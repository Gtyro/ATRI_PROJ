import logging
import random
import re
from typing import Dict, List, Optional, Any

from .ai import AIProcessor

class MessageProcessor:
    """消息处理器
    
    负责处理消息并转换为话题
    """
    
    def __init__(self, config: Dict[str, Any], group_character: Dict[str, str], queue_history_size: int):
        """初始化消息处理器
        
        Args:
            config: 配置字典
            group_character: 群组人格字典
            queue_history_size: 队列历史消息保留数量
        """
        self.config = config
        api_key = config.get("api_key", "")
        if not api_key:
            raise ValueError("API密钥未设置")
            
        self.ai_processor = AIProcessor(api_key, group_character = group_character, queue_history_size = queue_history_size)
        self.autoresponse_threshold = config.get("autoresponse_threshold", 0.5)
        logging.info("消息处理器已创建")
    
    async def extract_topics_from_messages(self, conv_id: str, messages: List[Dict]) -> List[Dict]:
        """从消息列表中提取话题
        
        Args:
            conv_id: 会话ID
            messages: 消息列表
            
        Returns:
            话题列表(completed_status)
        """
        if not messages:
            logging.warning(f"罕见！会话 {conv_id} 没有消息")
            return []
            
        # 提取话题
        try:
            topics = await self.ai_processor.extract_topics(conv_id, messages)
            
            return topics
        except Exception as e:
            logging.error(f"处理对话失败: {e}")
    
    async def should_respond(self, conv_id: str, topics: List[Dict]) -> bool:
        """判断是否应该回复
        
        Args:
            topics: 话题列表
            
        Returns:
            是否应该回复
        """
        # 无话题或全部已完结
        if not topics or all(topic.get("completed_status", True) for topic in topics):
            logging.info(f"会话 {conv_id} 无话题或全部已完结，不回复")
            return False
            
        # 从未完结的话题中选择是否回复
        for topic in topics:
            if topic.get("completed_status", True):
                continue
                
            continuation_prob = topic.get("continuation_probability", 0.0)
            if continuation_prob < self.autoresponse_threshold:
                continue
                
            # 根据概率决定是否回复
            if random.random() <= continuation_prob or logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                return True
                
        return False
    
    async def generate_reply(self, conv_id: str, messages: List[Dict], temperature: float = 0.7) -> Dict:
        """生成回复
        
        Args:
            messages: 消息历史
            temperature: 生成温度
            
        Returns:
            回复内容字典
        """
        # 准备消息格式
        chat_messages = []
        for msg in messages:
            user_name = msg.get("user_name", "用户")
            content = msg.get("content", "")
            is_direct = msg.get("is_direct", False)
            is_bot = msg.get("is_bot", False)
            
            role = "assistant" if is_bot else "user"
            message_text = f"[{user_name}]{'对你' if is_direct else ''}说: {content}"
            
            chat_messages.append({"role": role, "content": message_text})
        logging.info(f"消息历史: \n{chat_messages}")
        
        # 生成回复
        reply_content = await self.ai_processor.generate_response(conv_id, chat_messages, temperature)
        
        return {
            "content": reply_content,
            "temperature": temperature
        } 