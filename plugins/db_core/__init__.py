"""
数据库核心插件 - 为所有其他插件提供ORM数据库功能
"""

from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from .db_init import initialize_database, shutdown_database
from .db_manager import db_manager
from .model_registry import register_all_models

__plugin_meta__ = PluginMetadata(
    name="数据库核心",
    description="提供ORM数据库功能，用于模型管理和数据存储",
    usage="无需手动使用，其他插件会自动调用",
    type="application",
    config=None,
    homepage="https://github.com/yourusername/ATRI_PROJ",
    supported_adapters={"~all"}
)

driver = get_driver()

# 导出函数和对象，供其他插件使用
__all__ = ["db_manager", "initialize_database", "shutdown_database", "register_all_models"]

# 在Nonebot启动时注册所有模型并初始化数据库
@driver.on_startup
async def init_db():
    # 注册所有模型
    register_all_models()
    # 初始化数据库
    await initialize_database()

# 在Nonebot关闭时关闭数据库连接
@driver.on_shutdown
async def close_db():
    await shutdown_database() 