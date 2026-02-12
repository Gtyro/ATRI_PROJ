"""
配置文件处理工具
负责加载、检查和验证配置
"""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

from src.core.domain import PersonaConfig

# 定义配置文件路径
CONFIG_PATH = "data/persona/persona.yaml"


def _ensure_config(config_path: str) -> PersonaConfig:
    return PersonaConfig.load(config_path)


def load_config(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """加载配置文件并应用环境变量覆盖。"""
    try:
        config = _ensure_config(config_path)
        return config.to_dict()
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        raise


def save_config(config: Dict[str, Any], config_path: str = CONFIG_PATH) -> bool:
    """保存配置到文件。"""
    try:
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        defaults: Dict[str, Any] = {}
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                defaults = yaml.safe_load(f) or {}
        persona_config = PersonaConfig.from_dict(config, defaults=defaults).apply_env_overrides()
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(persona_config.to_dict(), f, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        logging.error(f"保存配置文件失败: {e}")
        return False


def check_config(config_path: str = CONFIG_PATH) -> bool:
    """检查配置是否正确。"""
    config = _ensure_config(config_path)
    if not config.api_key:
        logging.warning("API密钥未设置，请在配置文件中设置api_key")
        return False
    return True
