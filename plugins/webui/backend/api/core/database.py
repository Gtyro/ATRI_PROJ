import logging

from fastapi import HTTPException

from ..db.neo4j_utils import close_neo4j, initialize_neo4j

async def initialize_database_system():
    """初始化所有数据库连接"""
    try:
        # 初始化Neo4j
        await initialize_neo4j()

        logging.info(f"所有数据库连接已初始化")
    except Exception as e:
        logging.error(f"数据库初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库连接错误: {str(e)}")

async def close_database():
    """关闭所有数据库连接"""
    try:
        # 关闭Neo4j连接
        await close_neo4j()

        logging.info("所有数据库连接已关闭")
    except Exception as e:
        logging.error(f"关闭数据库连接失败: {e}")