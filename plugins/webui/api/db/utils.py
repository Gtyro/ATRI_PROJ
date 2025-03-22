import sqlite3
from fastapi import HTTPException
from api.core.database import get_db_connection, is_select_query

def execute_select_query(query: str):
    """执行SELECT查询"""
    if not is_select_query(query):
        raise HTTPException(
            status_code=403, 
            detail="出于安全原因，仅支持SELECT查询"
        )
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [description[0] for description in cursor.description] if cursor.description else []
        rows = [dict(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows}
    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=f"查询执行错误: {str(e)}")
    finally:
        conn.close()

def get_tables():
    """获取所有表名称"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        return {"tables": tables}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")
    finally:
        conn.close()

def get_table_structure(table_name: str):
    """获取表结构"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [
            {
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": row[3],
                "default_value": row[4],
                "pk": row[5]
            }
            for row in cursor.fetchall()
        ]
        return {"table_name": table_name, "columns": columns}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")
    finally:
        conn.close()
