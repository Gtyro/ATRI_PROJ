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

@router.get("/memory/nodes")
async def get_cognitive_nodes(conv_id: str = '', limit: int = 50, current_user: User = Depends(get_current_active_user)):
    """获取认知节点数据，用于知识图谱可视化
    
    Args:
        conv_id: 可选，如果提供则获取特定会话的节点，否则获取公共节点(空conv_id)
        limit: 返回的最大节点数量，默认50个
    """
    query = "SELECT id, name, conv_id, act_lv FROM nodes"
    
    if conv_id:  # 非空字符串
        query += f" WHERE conv_id = '{conv_id}'"
    else:  # 空字符串，获取公共图谱
        query += " WHERE conv_id = ''"
    
    # 按激活水平降序排序，限制数量    
    query += f" ORDER BY act_lv DESC LIMIT {limit}"
        
    result = await execute_select_query(query)
    return result

@router.get("/memory/associations")
async def get_associations(conv_id: str = '', node_ids: str = None, limit: int = 200, current_user: User = Depends(get_current_active_user)):
    """获取节点之间的关联数据
    
    Args:
        conv_id: 可选，如果提供则获取特定会话的关联，否则获取公共关联
        node_ids: 可选，逗号分隔的节点ID列表，如果提供则只获取这些节点之间的关联
        limit: 返回的最大关联数量，默认200个
    """
    # 基本查询
    query = """
    SELECT a.id, a.source_id, a.target_id, a.strength,
           s.name as source_name, t.name as target_name
    FROM associations a
    JOIN nodes s ON a.source_id = s.id
    JOIN nodes t ON a.target_id = t.id
    """
    
    # 条件部分
    conditions = []
    
    # 会话ID条件
    if conv_id:  # 非空字符串
        conditions.append(f"s.conv_id = '{conv_id}' AND t.conv_id = '{conv_id}'")
    else:  # 空字符串，获取公共图谱
        conditions.append("s.conv_id = '' AND t.conv_id = ''")
    
    # 节点ID条件
    if node_ids:
        ids = node_ids.split(',')
        if ids:
            node_ids_str = "','".join(ids)
            conditions.append(f"a.source_id IN ('{node_ids_str}') AND a.target_id IN ('{node_ids_str}')")
    
    # 添加WHERE子句
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # 添加排序和限制
    query += f" ORDER BY a.strength DESC LIMIT {limit}"
        
    result = await execute_select_query(query)
    return result

@router.get("/memory/conversations")
async def get_conversations(current_user: User = Depends(get_current_active_user)):
    """获取所有可用的会话ID（从GroupPluginConfig表获取）"""
    # 从group_plugin_configs表获取所有不同的gid
    query = """
    SELECT DISTINCT gid, name
    FROM group_plugin_configs
    ORDER BY gid
    """
    
    result = await execute_select_query(query)
    return result
