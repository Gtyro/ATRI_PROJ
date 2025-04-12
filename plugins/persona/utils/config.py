import os
import yaml
import logging
from typing import Dict, Any

DEFAULT_CONFIG = {
    "api_key": "",
    "batch_interval": 3600,  # 批处理间隔时间（秒）
    "queue_history_size": 40,  # 队列历史消息保留数量
    "autoresponse_threshold": 0.5,  # 自动回复阈值
    "node_decay_rate": 0.01,  # 衰减率
    "use_postgres": False,  # 是否使用PostgreSQL
    "postgres_config": {},  # PostgreSQL配置
}

CONFIG_PATH = "data/persona.yaml"

def load_config(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """加载配置文件，如果不存在则创建默认配置"""
    if not os.path.exists(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f)
        logging.info(f"已创建默认配置文件: {config_path}")
        return DEFAULT_CONFIG
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            # 确保所有默认配置项都存在
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
        return config
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        return DEFAULT_CONFIG

def save_config(config: Dict[str, Any], config_path: str = CONFIG_PATH) -> bool:
    """保存配置到文件"""
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
        return True
    except Exception as e:
        logging.error(f"保存配置文件失败: {e}")
        return False

def check_config(config_path: str = CONFIG_PATH) -> bool:
    """检查配置是否正确"""
    config = load_config(config_path)
    if not config.get("api_key"):
        logging.warning("API密钥未设置，请在配置文件中设置api_key")
        return False
    return True 