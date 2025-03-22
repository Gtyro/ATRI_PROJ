import sqlite3
import re
from fastapi import HTTPException
from .config import settings

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = sqlite3.connect(settings.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库连接错误: {str(e)}")

def is_select_query(query: str) -> bool:
    """检查是否为SELECT查询，阻止非SELECT语句"""
    pattern = re.compile(r'^\s*SELECT\s+', re.IGNORECASE)
    return bool(pattern.match(query))
