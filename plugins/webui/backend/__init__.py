import nonebot
from fastapi import FastAPI
from nonebot import get_driver
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.plugin.manager import PluginManager

# 全局驱动器
driver = get_driver()

# 导入webui运行模块
try:
    from .api import create_app, configure_app
    from .api.core.database import initialize_database_system, close_database
except ImportError as e:
    logger.error(f"无法导入WebUI模块: {e}")
    raise

@driver.on_startup
async def start_webui():
    """启动WebUI服务"""
    logger.info("正在启动WebUI管理面板...")

    try:
        # 获取nonebot应用实例
        nonebot_app: FastAPI = nonebot.get_app()
        logger.info("nonebot_app is {}".format(nonebot_app))

        # 配置应用（使用统一配置函数）
        configure_app(nonebot_app, is_nonebot_app=True)
        
        # 初始化数据库
        await initialize_database_system()

        logger.success("WebUI管理面板已启动，访问 http://127.0.0.1:8080/webui")
    except Exception as e:
        logger.error(f"启动WebUI失败: {e}")

@driver.on_shutdown
async def stop_webui():
    """关闭WebUI服务"""
    try:
        # 关闭数据库连接
        await close_database()
        logger.success("WebUI数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭WebUI数据库连接失败: {e}")