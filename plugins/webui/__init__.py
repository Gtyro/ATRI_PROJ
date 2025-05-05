from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from nonebot import get_driver
import nonebot
from nonebot.plugin import PluginMetadata
from nonebot.log import logger
import inspect
import threading
import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from .api.core import waitfor_nonebot_app
# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="WebUI管理面板",
    description="提供可视化的方式管理和监控您的数据库",
    usage="启动后访问 http://127.0.0.1:8080/webui",
    type="application",
    homepage="https://github.com/yourusername/nonebot-plugin-webui",
    config=None,
    supported_adapters={"~onebot.v11"}
)

# 全局驱动器
driver = get_driver()

# 获取当前插件所在目录
PLUGIN_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# 导入webui运行模块
try:
    # from .run import main as run_webui
    from .api import create_app, auth_router, db_router
    from .api.core.config import settings
except ImportError as e:
    logger.error(f"无法导入WebUI模块: {e}")
    raise

# WebUI服务线程
webui_thread = None

@driver.on_startup
async def start_webui():

    """启动WebUI服务"""
    global webui_thread
    logger.info("正在启动WebUI管理面板...")

    try:
        # 获取nonebot应用实例
        nonebot_app: FastAPI = nonebot.get_app()
        logger.info("nonebot_app is {}".format(nonebot_app))

        # 添加路由
        nonebot_app.include_router(auth_router)
        nonebot_app.include_router(db_router)
        await waitfor_nonebot_app(nonebot_app)

        logger.success("WebUI管理面板已启动，访问 http://127.0.0.1:8080/webui")
    except Exception as e:
        logger.error(f"启动WebUI失败: {e}")

@driver.on_shutdown
async def stop_webui():
    """关闭WebUI服务"""
    global webui_thread

    if webui_thread and webui_thread.is_alive():
        logger.info("正在关闭WebUI管理面板...")
        # 由于使用daemon=True，主线程结束时WebUI也会自动关闭
        # 如果需要更优雅的关闭，可以在此添加相应代码
        logger.success("WebUI管理面板已关闭")
