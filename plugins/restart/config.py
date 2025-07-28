"""
重启配置管理
"""

import json
import logging
import os
from typing import Dict, Any


class RestartConfig:
    """重启配置管理类"""
    
    def __init__(self):
        self.config_file = "data/restart/config.json"
        self.config_data = {}
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            # 确保目录存在
            os.makedirs("data/restart", exist_ok=True)
            
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
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
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logging.info("重启配置保存完成")
        except Exception as e:
            logging.error(f"保存重启配置失败: {e}")
    
    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "auto_restart_enabled": True,
            "restart_time": "04:00",
            "startup_script_path": "scripts/restart/start_bot.sh",
            "max_restart_attempts": 3,
            "restart_delay": 5,
            "restart_notification_enabled": True
        }
    
    @property
    def auto_restart_enabled(self) -> bool:
        """是否启用自动重启"""
        return self.config_data.get("auto_restart_enabled", True)
    
    @property
    def restart_time(self) -> str:
        """重启时间"""
        return self.config_data.get("restart_time", "04:00")
    
    @property
    def startup_script_path(self) -> str:
        """启动脚本路径"""
        return self.config_data.get("startup_script_path", "scripts/restart/start_bot.sh")
    
    @property
    def max_restart_attempts(self) -> int:
        """最大重启尝试次数"""
        return self.config_data.get("max_restart_attempts", 3)
    
    @property
    def restart_delay(self) -> int:
        """重启延迟时间（秒）"""
        return self.config_data.get("restart_delay", 5)
    
    @property
    def restart_notification_enabled(self) -> bool:
        """是否启用重启完成通知"""
        return self.config_data.get("restart_notification_enabled", True)
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if key in ["auto_restart_enabled", "restart_time", "startup_script_path", 
                      "max_restart_attempts", "restart_delay", "restart_notification_enabled"]:
                self.config_data[key] = value
        self.save_config() 