"""
模型注册辅助模块
提供中央模型注册功能，避免重复代码
"""

import logging

from .db_manager import db_manager


def register_all_models():
    """
    注册应用中所有已知的模型
    这个函数集中了所有模型的注册，避免重复代码
    """
    # 注册核心模型
    db_manager.register_models("models", ["plugins.models"])
    
    # 注册persona相关模型
    db_manager.register_models("models", ["plugins.persona.storage.message_models"])
    
    # 注册webui相关模型
    db_manager.register_models("models", ["plugins.webui.backend.api.db.models"])
    
    # 记录已注册的模型
    registered_modules = db_manager.get_registered_modules()
    logging.info(f"已注册所有数据库模型: {', '.join(registered_modules)}")
    
    return registered_modules 