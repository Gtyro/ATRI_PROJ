import os
import nonebot
from fastapi import FastAPI
from nonebot import get_driver
from nonebot.log import logger

STANDALONE_WEBUI = os.getenv("ATRI_WEBUI_STANDALONE") == "1"

if not STANDALONE_WEBUI:
    driver = get_driver()

    try:
        from .api import WEBUI_BROWSER_URL, configure_app
        from .api.core.database import close_database, initialize_database_system
    except ImportError as error:
        logger.error(f"无法导入WebUI模块: {error}")
        raise

    @driver.on_startup
    async def start_webui():
        """Mount the WebUI routes on the ATRI host."""
        logger.info("正在启动WebUI管理面板...")

        try:
            nonebot_app: FastAPI = nonebot.get_app()
            logger.info("nonebot_app is {}".format(nonebot_app))
            configure_app(nonebot_app, is_nonebot_app=True)

            neo4j_ready = await initialize_database_system()
            if neo4j_ready:
                logger.success(f"WebUI管理面板已启动，访问 {WEBUI_BROWSER_URL}")
            else:
                logger.warning("WebUI管理面板已启动，但 Neo4j 当前不可用，相关功能暂时降级")
        except Exception as error:
            logger.error(f"启动WebUI失败: {error}")

    @driver.on_shutdown
    async def stop_webui():
        """Close WebUI resources mounted on the ATRI host."""
        try:
            await close_database()
            logger.success("WebUI数据库连接已关闭")
        except Exception as error:
            logger.error(f"关闭WebUI数据库连接失败: {error}")
