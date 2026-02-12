"""
重启配置管理
"""

import logging
import os
from typing import Any, Dict

import yaml


DEFAULT_RESTART_CONFIG: Dict[str, Any] = {
    "auto_restart_enabled": True,
    "restart_time": "04:00",
    "startup_script_path": "scripts/restart/start_bot.sh",
    "max_restart_attempts": 3,
    "restart_delay": 5,
    "restart_notification_enabled": True,
}


class RestartConfig:
    """重启配置管理类"""

    def __init__(self):
        self.config_file = "data/restart/config.yaml"
        self.config_data = {}
        self.load_config()

    def load_config(self) -> None:
        """加载配置文件"""
        try:
            # 确保目录存在
            os.makedirs("data/restart", exist_ok=True)

            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
            else:
                # 创建默认配置
                self.config_data = self.get_default_config()
                self.save_config()

            logging.info("重启配置加载完成")

        except Exception as e:
            logging.error(f"加载重启配置失败: {e}")
            self.config_data = self.get_default_config()

    def save_config(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config_data, f, allow_unicode=True, sort_keys=False)
            logging.info("重启配置保存完成")
        except Exception as e:
            logging.error(f"保存重启配置失败: {e}")

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return dict(DEFAULT_RESTART_CONFIG)

    def __getattr__(self, name: str) -> Any:
        """按需提供配置字段的默认值。"""
        if name in DEFAULT_RESTART_CONFIG:
            return self.config_data.get(name, DEFAULT_RESTART_CONFIG[name])
        raise AttributeError(f"{type(self).__name__} has no attribute {name}")

    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if key in DEFAULT_RESTART_CONFIG:
                self.config_data[key] = value
        self.save_config()
