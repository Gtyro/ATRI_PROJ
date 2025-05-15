from fastapi import APIRouter, Depends

from ..auth.utils import get_current_active_user
from ..auth.models import User
from .models import SQLQuery, Neo4jQuery
from .utils import execute_select_query, get_tables, get_table_structure, execute_insert_query, execute_update_query, execute_delete_query
from .neo4j_utils import (
    execute_neo4j_query, get_cognitive_nodes, get_associations, 
    get_node_by_id, create_cognitive_node, update_cognitive_node, delete_cognitive_node,
    create_association, update_association, delete_association, get_conversations
)
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

# 创建SQL数据库路由
router = APIRouter(
    prefix="/db",
    tags=["database"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)

# === SQL/ORM 相关接口 ===

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

# === Neo4j/记忆网络相关接口 ===

@router.post("/neo4j/query")
async def execute_neo4j_cypher(query: Neo4jQuery, current_user: User = Depends(get_current_active_user)):
    """执行Neo4j Cypher查询"""
    return await execute_neo4j_query(query.query)

@router.get("/memory/nodes")
async def get_memory_nodes(conv_id: str = '', limit: int = 50, current_user: User = Depends(get_current_active_user)):
    """获取认知节点数据，用于知识图谱可视化

    Args:
        conv_id: 可选，如果提供则获取特定会话的节点，否则获取公共节点(空conv_id)
        limit: 返回的最大节点数量，默认50个
    """
    nodes = await get_cognitive_nodes(conv_id, limit)
    # 包装为与原API兼容的格式
    return {"rows": nodes}

@router.get("/memory/node/{node_id}")
async def get_memory_node(node_id: str, current_user: User = Depends(get_current_active_user)):
    """获取单个认知节点

    Args:
        node_id: 节点ID
    """
    return await get_node_by_id(node_id)

@router.post("/memory/node")
async def create_memory_node(data: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    """创建新认知节点"""
    return await create_cognitive_node(data)

@router.put("/memory/node/{node_id}")
async def update_memory_node(
    node_id: str,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """更新认知节点"""
    return await update_cognitive_node(node_id, data)

@router.delete("/memory/node/{node_id}")
async def delete_memory_node(
    node_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除认知节点"""
    return await delete_cognitive_node(node_id)

@router.get("/memory/associations")
async def get_memory_associations(
    conv_id: str = '', 
    node_ids: str = None, 
    limit: int = 200, 
    current_user: User = Depends(get_current_active_user)
):
    """获取节点之间的关联数据

    Args:
        conv_id: 可选，如果提供则获取特定会话的关联，否则获取公共关联
        node_ids: 可选，逗号分隔的节点ID列表，如果提供则只获取这些节点之间的关联
        limit: 返回的最大关联数量，默认200个
    """
    # 处理节点ID列表
    node_id_list = node_ids.split(',') if node_ids else None
    return await get_associations(conv_id, node_id_list, limit)

@router.post("/memory/association")
async def create_memory_association(
    data: dict = Body(...), 
    current_user: User = Depends(get_current_active_user)
):
    """创建节点关联关系

    请求体格式:
    {
        "source_id": "节点1 ID",
        "target_id": "节点2 ID",
        "strength": 1.0  // 可选，默认为1.0
    }
    """
    source_id = data.get("source_id")
    target_id = data.get("target_id")
    strength = data.get("strength", 1.0)
    
    if not source_id or not target_id:
        raise HTTPException(status_code=400, detail="必须提供source_id和target_id")
    
    return await create_association(source_id, target_id, strength)

@router.put("/memory/association")
async def update_memory_association(
    data: dict = Body(...), 
    current_user: User = Depends(get_current_active_user)
):
    """更新节点关联关系强度

    请求体格式:
    {
        "source_id": "节点1 ID",
        "target_id": "节点2 ID",
        "strength": 2.0
    }
    """
    source_id = data.get("source_id")
    target_id = data.get("target_id")
    strength = data.get("strength")
    
    if not source_id or not target_id or strength is None:
        raise HTTPException(status_code=400, detail="必须提供source_id、target_id和strength")
    
    return await update_association(source_id, target_id, float(strength))

@router.delete("/memory/association")
async def delete_memory_association(
    source_id: str,
    target_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除节点关联关系"""
    if not source_id or not target_id:
        raise HTTPException(status_code=400, detail="必须提供source_id和target_id")
    
    return await delete_association(source_id, target_id)

@router.get("/memory/conversations")
async def get_memory_conversations(current_user: User = Depends(get_current_active_user)):
    """获取所有可用的会话ID"""
    return await get_conversations()
