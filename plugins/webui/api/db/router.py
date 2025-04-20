from fastapi import APIRouter, Depends

from ..auth.utils import get_current_active_user
from ..auth.models import User
from .models import SQLQuery
from .utils import execute_select_query, get_tables, get_table_structure, execute_insert_query, execute_update_query, execute_delete_query
from fastapi import Body, Path, HTTPException
import re

# 支持UUID模式的正则表达式
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

# 验证ID是否有效
def validate_id(id_str: str):
    """验证ID字符串，支持整数或UUID格式"""
    # 尝试确定它是数字还是UUID
    if id_str.isdigit():
        # 是数字ID
        return id_str
    elif UUID_PATTERN.match(id_str):
        # 是UUID格式
        return id_str
    else:
        # 不是有效的ID格式
        raise HTTPException(status_code=400, detail=f"无效的ID格式: {id_str}")

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
    return await execute_select_query(query.query)

@router.get("/tables")
async def list_tables(current_user: User = Depends(get_current_active_user)):
    """获取所有表名称"""
    return await get_tables()

@router.get("/table/{table_name}")
async def get_table_info(table_name: str, current_user: User = Depends(get_current_active_user)):
    """获取表结构"""
    return await get_table_structure(table_name)

@router.post("/table/{table_name}")
async def insert_data(table_name: str, data: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    """向表中插入数据"""
    return await execute_insert_query(table_name, data)

@router.put("/table/{table_name}/update")
async def update_data(
    table_name: str,
    id: str,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """更新表中的数据"""
    # 验证ID
    validate_id(id)
    return await execute_update_query(table_name, id, data)

@router.delete("/table/{table_name}/delete")
async def delete_data(
    table_name: str,
    id: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除表中的数据"""
    # 验证ID
    validate_id(id)
    return await execute_delete_query(table_name, id)
