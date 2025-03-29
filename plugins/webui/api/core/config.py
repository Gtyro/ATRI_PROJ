from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置设置"""
    # 应用设置
    API_V1_STR: str = ""
    SECRET_KEY: str = "your-secret-key"  # 在生产环境中请更改此密钥
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 项目根目录
    PROJECT_ROOT: str = str(Path(__file__).parent.parent.parent.parent.parent)
    
    # 数据库设置
    DATABASE_PATH: str = str(Path(PROJECT_ROOT) / "data" / "memory.db")
    PUBLIC_PATH: str = str(Path(PROJECT_ROOT) / "plugins" / "webui" / "static" / "webui")
    
    # CORS设置
    CORS_ORIGINS: list = ["*"]  # 在生产环境中应该限制来源
    
    class Config:
        env_file = ".env"
        
# 创建全局设置实例
settings = Settings()
