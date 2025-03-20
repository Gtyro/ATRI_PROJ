"""
记忆系统处理模块 - 负责处理和转换输入消息

该模块将输入消息处理成结构化记忆，通过AI增强处理实现高质量的语义分析。
"""

import uuid
import time
import json
import logging
import os
from typing import Dict, List, Optional, Any

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
    
    async def process_message(self, user_id: str, message: str, context: str = "chat") -> Dict:
        """处理消息，转换为记忆数据结构"""
        # 生成唯一ID
        memory_id = str(uuid.uuid4())
        
        # 基础数据结构
        memory_data = {
            "id": memory_id,
            "user_id": user_id,
            "content": message,
            "context": context,
            "created_at": time.time(),
            "weight": 1.0,
            "metadata": {}
        }
        
        # AI处理消息
        try:
            ai_result = await self.ai_processor.process_memory(message)
            
            # 提取AI处理结果
            memory_data.update({
                "type": ai_result.get("memory_type", "general"),
                "emotion_score": ai_result.get("emotion", {}).get("polarity", 0),
                "emotion_intensity": ai_result.get("emotion", {}).get("intensity", 0),
                "tags": ai_result.get("tags", []),
                "summary": ai_result.get("summary", "")
            })
            
            # 如果情感强烈，增加初始权重
            if memory_data.get("emotion_intensity", 0) > 0.6:
                memory_data["weight"] = 1.2
                
            # 保存原始AI结果
            memory_data["metadata"]["ai_analysis"] = ai_result
            
        except Exception as e:
            # 记录错误但继续执行，设置默认值
            logging.error(f"消息处理失败: {e}")
            memory_data.update({
                "type": "general",
                "emotion_score": 0,
                "emotion_intensity": 0,
                "tags": [],
                "summary": message[:50] + ("..." if len(message) > 50 else "")
            })
        
        return memory_data
    
    def find_associations(self, memory_data: Dict) -> List[Dict]:
        """查找关联 - 未来扩展功能
        未来可以实现更复杂的关联发现逻辑
        """
        # 此版本返回空关联
        return [] 