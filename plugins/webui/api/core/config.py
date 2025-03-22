import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置设置"""
    # 应用设置
    API_V1_STR: str = ""
    SECRET_KEY: str = "your-secret-key"  # 在生产环境中请更改此密钥
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 数据库设置
    DATABASE_PATH: str = os.path.expanduser("~/ATRI_PROJ/data/memory.db")
    
    # CORS设置
    CORS_ORIGINS: list = ["*"]  # 在生产环境中应该限制来源
    
    class Config:
        env_file = ".env"
        
# 创建全局设置实例
settings = Settings()
