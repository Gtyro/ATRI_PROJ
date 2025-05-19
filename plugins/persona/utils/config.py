"""
配置文件处理工具
负责加载、检查和验证配置
"""

import logging
import os
from typing import Any, Dict

import yaml

# 定义配置文件路径
CONFIG_PATH = "data/persona.yaml"

def check_config(config_path: str) -> None:
    """
    检查配置文件是否存在，不存在则创建默认配置
    """
    if not os.path.exists(config_path):
        # 创建目录
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # 默认配置
        default_config = {
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"),
            "model": "gpt-3.5-turbo",
            "use_postgres": False,
            "db_path": "data/persona.db",
            "batch_interval": 30 * 60,  # 30分钟
            "node_decay_rate": 0.01,
            "queue_history_size": 40,

            # Neo4j配置
            "neo4j_config": {
                "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                "user": os.environ.get("NEO4J_USER", "neo4j"),
                "password": os.environ.get("NEO4J_PASSWORD", "neo4j")
            }
        }

        # 如果设置了环境变量USE_POSTGRES，则使用PostgreSQL
        if os.environ.get("USE_POSTGRES", "false").lower() == "true":
            default_config["use_postgres"] = True
            default_config["postgres_config"] = {
                "host": os.environ.get("POSTGRES_HOST", "localhost"),
                "port": int(os.environ.get("POSTGRES_PORT", "5432")),
                "user": os.environ.get("POSTGRES_USER", "postgres"),
                "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
                "database": os.environ.get("POSTGRES_DB", "persona")
            }

        # 写入配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

        logging.info(f"已创建默认配置文件: {config_path}")

def load_config(config_path: str) -> Dict[str, Any]:
    """
    加载配置文件
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 环境变量优先级更高，如果设置了环境变量则覆盖配置
        if os.environ.get("OPENAI_API_KEY"):
            config["api_key"] = os.environ.get("OPENAI_API_KEY")
        if os.environ.get("OPENAI_BASE_URL"):
            config["base_url"] = os.environ.get("OPENAI_BASE_URL")

        # 处理Neo4j环境变量
        if os.environ.get("NEO4J_URI"):
            config["neo4j_config"]["uri"] = os.environ.get("NEO4J_URI")
        if os.environ.get("NEO4J_USER"):
            config["neo4j_config"]["user"] = os.environ.get("NEO4J_USER")
        if os.environ.get("NEO4J_PASSWORD"):
            config["neo4j_config"]["password"] = os.environ.get("NEO4J_PASSWORD")

        return config
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        raise

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