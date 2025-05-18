"""
数据库初始化模块
提供框架无关的数据库初始化功能
"""

import logging

from .db_manager import db_manager

# 标准的数据库URL，可以被外部配置覆盖
DEFAULT_DB_URL = "sqlite://data/persona.db"

async def initialize_database(db_url=None, force=False):
    """
    初始化数据库，确保所有模型都已注册
    
    Args:
        db_url: 数据库连接URL，如果为None则使用默认值
        force: 是否强制重新初始化，即使已经初始化过
    
    Returns:
        bool: 初始化是否成功
    """
    # 如果已初始化且不强制重新初始化，则跳过
    if db_manager.is_initialized() and not force:
        logging.warning("数据库已初始化，跳过初始化过程")
        return True
        
    # 使用提供的URL或默认URL
    actual_db_url = db_url or DEFAULT_DB_URL
    db_manager.set_db_url(actual_db_url)
    
    # 初始化数据库
    try:
        await db_manager.initialize()
        return True
    except Exception as e:
        logging.error(f"数据库初始化失败: {e}")
        raise

async def shutdown_database():
    """
    关闭数据库连接
    
    Returns:
        bool: 关闭是否成功
    """
    try:
        await db_manager.close()
        logging.info("数据库连接已关闭")
        return True
    except Exception as e:
        logging.error(f"关闭数据库连接失败: {e}")
        return False
        
def get_manager():
    """
    获取数据库管理器实例
    
    Returns:
        DBManager: 数据库管理器实例
    """
    return db_manager 