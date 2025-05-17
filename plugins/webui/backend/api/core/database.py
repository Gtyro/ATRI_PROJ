import logging

from fastapi import HTTPException
from tortoise import Tortoise

from plugins.db_core import db_manager, initialize_database, shutdown_database

from ..db.neo4j_utils import close_neo4j, initialize_neo4j
from .config import settings

# 数据库URL
DB_URL = None

async def initialize_database_system():
    """初始化所有数据库连接"""
    try:
        global DB_URL
        # 设置数据库URL
        DB_URL = f"sqlite://{settings.DATABASE_PATH}"
        
        # 初始化Tortoise ORM
        await initialize_database(db_url=DB_URL)
        
        # 初始化Neo4j
        await initialize_neo4j()
        
        logging.info(f"所有数据库连接已初始化")
    except Exception as e:
        logging.error(f"数据库初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库连接错误: {str(e)}")

async def register_models():
    """注册WebUI设置，不再单独注册模型"""
    try:
        global DB_URL
        # 设置数据库URL
        DB_URL = f"sqlite://{settings.DATABASE_PATH}"
    except Exception as e:
        logging.error(f"WebUI数据库设置失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库设置错误: {str(e)}")

async def close_database():
    """关闭所有数据库连接"""
    try:
        # 关闭数据库连接
        await shutdown_database()
        
        # 关闭Neo4j连接
        await close_neo4j()
        
        logging.info("所有数据库连接已关闭")
    except Exception as e:
        logging.error(f"关闭数据库连接失败: {e}")

# async def execute_checkpoint():
#     """执行checkpoint以确保数据对其他进程可见"""
#     try:
#         await Tortoise.execute_raw("PRAGMA wal_checkpoint(PASSIVE);")
#     except Exception as e:
#         logging.error(f"执行checkpoint失败: {e}")