"""
数据库核心插件 - 为所有其他插件提供ORM数据库功能
"""

from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from .db_init import initialize_database, shutdown_database
from .db_manager import db_manager
from .model_registry import register_all_models, register_model_module

# 注册插件共享模型，确保在 fallback 未触发时也会纳入初始化。
register_model_module("models", "src.infra.db.tortoise.plugin_models")

__plugin_meta__ = PluginMetadata(
    name="数据库核心",
    description="提供ORM数据库功能，用于模型管理和数据存储",
    usage="无需手动使用，其他插件会自动调用",
    type="application",
    config=None,
    homepage="https://github.com/yourusername/ATRI_PROJ",
    supported_adapters={"~all"},
    extra={
        "policy": {
            "manageable": False,
        }
    }
)

# 导出函数和对象，供其他插件使用
__all__ = [
    "db_manager",
    "initialize_database",
    "shutdown_database",
    "register_all_models",
    "register_model_module",
]


async def init_db():
    """在 NoneBot 启动时注册模型并初始化数据库。"""
    register_all_models()
    await initialize_database()


async def close_db():
    """在 NoneBot 关闭时释放数据库连接。"""
    await shutdown_database()


try:
    driver = get_driver()
except ValueError:
    # 允许在未初始化 NoneBot 的环境中安全导入（例如单元测试）。
    driver = None

if driver is not None:
    driver.on_startup(init_db)
    driver.on_shutdown(close_db)
