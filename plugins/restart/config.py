"""
重启系统配置管理模块
"""

import json
import logging
import os
from typing import Dict, Any


class RestartConfig:
    """重启系统配置管理器"""
    
    def __init__(self, config_path: str = "data/restart/config.json"):
        self.config_path = config_path
        self.auto_restart_enabled = True
        self.restart_time = "04:00"  # 默认凌晨4点
        self.startup_script_path = "scripts/restart/start_bot.sh"
        self.max_restart_attempts = 3
        self.restart_delay = 5  # 重启延迟秒数
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> None:
        """从文件加载配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                self.auto_restart_enabled = config_data.get('auto_restart_enabled', True)
                self.restart_time = config_data.get('restart_time', "04:00")
                self.startup_script_path = config_data.get('startup_script_path', "scripts/restart/start_bot.sh")
                self.max_restart_attempts = config_data.get('max_restart_attempts', 3)
                self.restart_delay = config_data.get('restart_delay', 5)
                
                logging.info(f"重启配置已从 {self.config_path} 加载")
            else:
                # 创建默认配置
                self.save_config()
                logging.info(f"已创建默认重启配置文件: {self.config_path}")
                
        except Exception as e:
            logging.error(f"加载重启配置失败: {e}")
            # 使用默认配置
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            config_data = {
                'auto_restart_enabled': self.auto_restart_enabled,
                'restart_time': self.restart_time,
                'startup_script_path': self.startup_script_path,
                'max_restart_attempts': self.max_restart_attempts,
                'restart_delay': self.restart_delay
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"重启配置已保存到 {self.config_path}")
            
        except Exception as e:
            logging.error(f"保存重启配置失败: {e}")
    
    async def save(self) -> None:
        """异步保存配置"""
        self.save_config()
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            'auto_restart_enabled': self.auto_restart_enabled,
            'restart_time': self.restart_time,
            'startup_script_path': self.startup_script_path,
            'max_restart_attempts': self.max_restart_attempts,
            'restart_delay': self.restart_delay
        }
    
    def update_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """从字典更新配置"""
        self.auto_restart_enabled = config_dict.get('auto_restart_enabled', self.auto_restart_enabled)
        self.restart_time = config_dict.get('restart_time', self.restart_time)
        self.startup_script_path = config_dict.get('startup_script_path', self.startup_script_path)
        self.max_restart_attempts = config_dict.get('max_restart_attempts', self.max_restart_attempts)
        self.restart_delay = config_dict.get('restart_delay', self.restart_delay)
        
        # 保存更新后的配置
        self.save_config() 