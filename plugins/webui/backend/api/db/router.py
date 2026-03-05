import re

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ..audit.service import is_mutating_cypher, record_operation_audit
from ..audit.types import AuditAction, AuditTargetType
from ..auth.models import User
from ..auth.utils import get_current_active_user
from .models import Neo4jQuery, SQLQuery
from .neo4j_utils import (create_association, create_cognitive_node,
                          delete_association, delete_cognitive_node,
                          execute_neo4j_query, get_associations,
                          get_cognitive_nodes, get_conversations,
                          get_node_by_id, update_association,
                          update_cognitive_node)
from .utils import (execute_delete_query, execute_insert_query,
                    execute_select_query, execute_update_query,
                    get_table_structure, get_tables)

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
async def insert_data(
    table_name: str,
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """向表中插入数据"""
    try:
        result = await execute_insert_query(table_name, data)
        record_id = str(result.get("id", "")) or "unknown"
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.SQL_TABLE_INSERT.value,
            target_type=AuditTargetType.SQL_TABLE.value,
            target_id=f"{table_name}:{record_id}",
            request=request,
            success=True,
            after={"data": data, "result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.SQL_TABLE_INSERT.value,
            target_type=AuditTargetType.SQL_TABLE.value,
            target_id=table_name,
            request=request,
            success=False,
            after={"data": data},
            error_message=str(exc),
        )
        raise

@router.put("/table/{table_name}/update")
async def update_data(
    table_name: str,
    id: str,
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """更新表中的数据"""
    # 验证ID
    validate_id(id)
    try:
        result = await execute_update_query(table_name, id, data)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.SQL_TABLE_UPDATE.value,
            target_type=AuditTargetType.SQL_TABLE.value,
            target_id=f"{table_name}:{id}",
            request=request,
            success=True,
            after={"data": data, "result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.SQL_TABLE_UPDATE.value,
            target_type=AuditTargetType.SQL_TABLE.value,
            target_id=f"{table_name}:{id}",
            request=request,
            success=False,
            after={"data": data},
            error_message=str(exc),
        )
        raise

@router.delete("/table/{table_name}/delete")
async def delete_data(
    table_name: str,
    id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """删除表中的数据"""
    # 验证ID
    validate_id(id)
    try:
        result = await execute_delete_query(table_name, id)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.SQL_TABLE_DELETE.value,
            target_type=AuditTargetType.SQL_TABLE.value,
            target_id=f"{table_name}:{id}",
            request=request,
            success=True,
            after={"result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.SQL_TABLE_DELETE.value,
            target_type=AuditTargetType.SQL_TABLE.value,
            target_id=f"{table_name}:{id}",
            request=request,
            success=False,
            error_message=str(exc),
        )
        raise

# === Neo4j/记忆网络相关接口 ===

@router.post("/neo4j/query")
async def execute_neo4j_cypher(
    query: Neo4jQuery,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """执行Neo4j Cypher查询"""
    mutating = is_mutating_cypher(query.query)
    try:
        result = await execute_neo4j_query(query.query)
        if mutating:
            await record_operation_audit(
                username=current_user.username,
                action=AuditAction.NEO4J_QUERY_MUTATE.value,
                target_type=AuditTargetType.NEO4J.value,
                request=request,
                success=True,
                after={"query": query.query, "result_meta": result.get("metadata")},
            )
        return result
    except Exception as exc:
        if mutating:
            await record_operation_audit(
                username=current_user.username,
                action=AuditAction.NEO4J_QUERY_MUTATE.value,
                target_type=AuditTargetType.NEO4J.value,
                request=request,
                success=False,
                after={"query": query.query},
                error_message=str(exc),
            )
        raise

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
async def create_memory_node(
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """创建新认知节点"""
    try:
        result = await create_cognitive_node(data)
        node_id = result.get("uid") if isinstance(result, dict) else None
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_NODE_CREATE.value,
            target_type=AuditTargetType.COGNITIVE_NODE.value,
            target_id=str(node_id) if node_id else None,
            request=request,
            success=True,
            after={"data": data, "result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_NODE_CREATE.value,
            target_type=AuditTargetType.COGNITIVE_NODE.value,
            request=request,
            success=False,
            after={"data": data},
            error_message=str(exc),
        )
        raise

@router.put("/memory/node/{node_id}")
async def update_memory_node(
    node_id: str,
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """更新认知节点"""
    try:
        result = await update_cognitive_node(node_id, data)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_NODE_UPDATE.value,
            target_type=AuditTargetType.COGNITIVE_NODE.value,
            target_id=node_id,
            request=request,
            success=True,
            after={"data": data, "result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_NODE_UPDATE.value,
            target_type=AuditTargetType.COGNITIVE_NODE.value,
            target_id=node_id,
            request=request,
            success=False,
            after={"data": data},
            error_message=str(exc),
        )
        raise

@router.delete("/memory/node/{node_id}")
async def delete_memory_node(
    node_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """删除认知节点"""
    try:
        result = await delete_cognitive_node(node_id)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_NODE_DELETE.value,
            target_type=AuditTargetType.COGNITIVE_NODE.value,
            target_id=node_id,
            request=request,
            success=True,
            after={"result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_NODE_DELETE.value,
            target_type=AuditTargetType.COGNITIVE_NODE.value,
            target_id=node_id,
            request=request,
            success=False,
            error_message=str(exc),
        )
        raise

@router.post("/memory/associations")
async def post_memory_associations(
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """获取节点之间的关联数据

    请求体格式:
    {
        "conv_id": "会话ID", // 可选
        "node_ids": ["节点ID1", "节点ID2", ...], // 可选
        "limit": 200 // 可选，默认200
    }
    """
    conv_id = data.get("conv_id", "")
    node_ids = data.get("node_ids")
    limit = data.get("limit", 200)

    return await get_associations(conv_id, node_ids, limit)

@router.post("/memory/association")
async def create_memory_association(
    request: Request,
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

    relation_id = f"{source_id}->{target_id}"
    try:
        result = await create_association(source_id, target_id, strength)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_ASSOCIATION_CREATE.value,
            target_type=AuditTargetType.MEMORY_ASSOCIATION.value,
            target_id=relation_id,
            request=request,
            success=True,
            after={"strength": strength, "result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_ASSOCIATION_CREATE.value,
            target_type=AuditTargetType.MEMORY_ASSOCIATION.value,
            target_id=relation_id,
            request=request,
            success=False,
            after={"strength": strength},
            error_message=str(exc),
        )
        raise

@router.put("/memory/association")
async def update_memory_association(
    request: Request,
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

    relation_id = f"{source_id}->{target_id}"
    try:
        result = await update_association(source_id, target_id, float(strength))
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_ASSOCIATION_UPDATE.value,
            target_type=AuditTargetType.MEMORY_ASSOCIATION.value,
            target_id=relation_id,
            request=request,
            success=True,
            after={"strength": strength, "result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_ASSOCIATION_UPDATE.value,
            target_type=AuditTargetType.MEMORY_ASSOCIATION.value,
            target_id=relation_id,
            request=request,
            success=False,
            after={"strength": strength},
            error_message=str(exc),
        )
        raise

@router.delete("/memory/association")
async def delete_memory_association(
    source_id: str,
    target_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """删除节点关联关系"""
    if not source_id or not target_id:
        raise HTTPException(status_code=400, detail="必须提供source_id和target_id")

    relation_id = f"{source_id}->{target_id}"
    try:
        result = await delete_association(source_id, target_id)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_ASSOCIATION_DELETE.value,
            target_type=AuditTargetType.MEMORY_ASSOCIATION.value,
            target_id=relation_id,
            request=request,
            success=True,
            after={"result": result},
        )
        return result
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.MEMORY_ASSOCIATION_DELETE.value,
            target_type=AuditTargetType.MEMORY_ASSOCIATION.value,
            target_id=relation_id,
            request=request,
            success=False,
            error_message=str(exc),
        )
        raise

@router.get("/memory/conversations")
async def get_memory_conversations(current_user: User = Depends(get_current_active_user)):
    """获取所有可用的会话ID"""
    return await get_conversations()
