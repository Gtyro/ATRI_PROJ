import logging

from ..db.neo4j_utils import (
    close_neo4j,
    get_neo4j_unavailable_reason,
    initialize_neo4j,
    neo4j_is_available,
)

async def initialize_database_system():
    """初始化所有数据库连接"""
    # 初始化 Neo4j。不可用时仅进入降级模式，不阻断 WebUI 启动。
    await initialize_neo4j(allow_unavailable=True)
    if neo4j_is_available():
        logging.info("所有数据库连接已初始化")
        return True

    reason = get_neo4j_unavailable_reason() or "Neo4j 当前不可用"
    logging.warning("Neo4j 不可用，WebUI 将以降级模式启动: %s", reason)
    return False

async def close_database():
    """关闭所有数据库连接"""
    try:
        # 关闭Neo4j连接
        await close_neo4j()

        logging.info("所有数据库连接已关闭")
    except Exception as e:
        logging.error(f"关闭数据库连接失败: {e}")
