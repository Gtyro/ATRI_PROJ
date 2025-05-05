from tortoise import Tortoise
from fastapi import HTTPException
import logging
from .config import settings


# 在初始化完成后（比如在 init_db() 中），构建反向映射
table_to_model_map = {}
async def build_table_model_map():
    models = Tortoise.apps.get("models", {})
    for model_name, model in models.items():
        table_name = model._meta.db_table  # 获取模型对应的真实表名
        table_to_model_map[table_name] = model  # 直接存储模型类对象而不是模型名称
    logging.info(f"构建表名到模型的映射完成，共 {len(table_to_model_map)} 个表")

async def initialize_tortoise():
    """初始化Tortoise ORM"""
    try:
        # 使用与memory模块相同的数据库
        db_url = f"sqlite://{settings.DATABASE_PATH}"

        await Tortoise.init(
            db_url=db_url,
            modules={'models': ['plugins.persona.storage.models', 'plugins.webui.api.db.models']}
        )
        await build_table_model_map()
        logging.info(f"Tortoise ORM已初始化: {db_url}")
    except Exception as e:
        logging.error(f"Tortoise ORM初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库连接错误: {str(e)}")

async def close_tortoise():
    """关闭Tortoise ORM连接"""
    await Tortoise.close_connections()
    logging.info("Tortoise ORM连接已关闭")

# async def execute_checkpoint():
#     """执行checkpoint以确保数据对其他进程可见"""
#     try:
#         await Tortoise.execute_raw("PRAGMA wal_checkpoint(PASSIVE);")
#     except Exception as e:
#         logging.error(f"执行checkpoint失败: {e}")