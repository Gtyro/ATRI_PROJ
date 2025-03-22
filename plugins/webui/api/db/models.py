from pydantic import BaseModel
from typing import List, Dict, Any

class SQLQuery(BaseModel):
    """SQL查询请求模型"""
    query: str

class TableInfo(BaseModel):
    """表信息模型"""
    name: str
    columns: List[Dict[str, Any]]
