from tortoise.expressions import Q, RawSQL
from tortoise import Tortoise
from fastapi import HTTPException
import re
import logging
from ..core.database import table_to_model_map
# from ..core.database import execute_checkpoint

async def execute_select_query(query: str):
    """执行SELECT查询"""
    if not is_select_query(query):
        raise HTTPException(
            status_code=403, 
            detail="出于安全原因，仅支持SELECT查询"
        )
    
    try:
        # 使用连接对象执行查询
        conn = Tortoise.get_connection("default")
        results = await conn.execute_query_dict(query) # Executes a RAW SQL query statement, and returns the resultset as a list of dicts.
        
        # 处理结果 - 针对SELECT查询，结果通常是一个包含行的列表
        # 将每一行转换为字典
        columns = []
        rows = []

        if results and len(results) > 0:
            if hasattr(results[0], 'keys'):
                # 如果结果有keys方法，说明是Row对象
                first_row = results[0]
                columns = list(first_row.keys())
                rows = [dict(row) for row in results]

        return {"columns": columns, "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询执行错误: {str(e)}")

def is_select_query(query: str) -> bool:
    """检查是否为SELECT查询，阻止非SELECT语句"""
    pattern = re.compile(r'^\s*SELECT\s+', re.IGNORECASE)
    return bool(pattern.match(query))

async def get_tables():
    """获取所有表名称"""
    try:
        # 执行checkpoint确保能看到最新数据
        # await execute_checkpoint()
        
        models = Tortoise.apps.get("models", {})
        table_names = [model._meta.db_table for model in models.values()]
        return {"tables": table_names}
    except Exception as e:
        logging.error(f"获取表名称错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")

async def get_table_structure(table_name: str):
    """获取表结构"""
    try:
        query = f"PRAGMA table_info({table_name});"
        conn = Tortoise.get_connection("default")
        columns = await conn.execute_query_dict(query)
        return {"table_name": table_name, "columns": columns}
    except Exception as e:
        logging.error(f"获取表结构错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")