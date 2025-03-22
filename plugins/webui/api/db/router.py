from fastapi import APIRouter, Depends

from ..auth.utils import get_current_active_user
from ..auth.models import User
from .models import SQLQuery
from .utils import execute_select_query, get_tables, get_table_structure

# 创建路由
router = APIRouter(
    prefix="/db",
    tags=["database"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)

@router.post("/query")
async def execute_query(query: SQLQuery, current_user: User = Depends(get_current_active_user)):
    """执行SQL查询"""
    return execute_select_query(query.query)

@router.get("/tables")
async def list_tables(current_user: User = Depends(get_current_active_user)):
    """获取所有表名称"""
    return get_tables()

@router.get("/table/{table_name}")
async def get_table_info(table_name: str, current_user: User = Depends(get_current_active_user)):
    """获取表结构"""
    return get_table_structure(table_name)
