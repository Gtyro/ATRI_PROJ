from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.models import User
from ..auth.utils import get_current_active_user
from ..db.neo4j_utils import execute_neo4j_query

router = APIRouter(
    prefix="/api/memory",
    tags=["memory"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)

@router.get("/timeline")
async def get_memory_timeline(
    conv_id: str = Query("", description="会话ID，如果为空则获取公共记忆"),
    start_time: int = Query(None, description="开始时间戳（秒）"),
    end_time: int = Query(None, description="结束时间戳（秒）"),
    limit: int = Query(100, description="返回的最大记忆数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取记忆时间线数据"""
    try:
        # 构建查询
        query = """
        MATCH (m:Memory)
        WHERE m.conv_id = $conv_id
        """
        
        params = {"conv_id": conv_id}
        
        # 添加时间范围条件
        if start_time is not None:
            query += " AND m.created_at >= $start_time"
            params["start_time"] = start_time
            
        if end_time is not None:
            query += " AND m.created_at <= $end_time"
            params["end_time"] = end_time
            
        # 添加排序和限制
        query += """
        RETURN m
        ORDER BY m.created_at DESC
        LIMIT $limit
        """
        params["limit"] = limit
        
        # 执行查询
        response = await execute_neo4j_query(query, params)
        results = response["results"]
        
        # 处理结果
        memories = []
        for row in results:
            memory_node = row[0]
            memory = {
                "id": memory_node["uid"],
                "title": memory_node["title"],
                "content": memory_node["content"],
                "created_at": memory_node["created_at"].timestamp() if isinstance(memory_node["created_at"], datetime) else memory_node["created_at"],
                "last_accessed": memory_node["last_accessed"].timestamp() if isinstance(memory_node["last_accessed"], datetime) else memory_node["last_accessed"],
                "weight": memory_node["weight"],
                "is_permanent": memory_node["is_permanent"]
            }
            memories.append(memory)
            
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆时间线失败: {str(e)}")

@router.get("/detail/{memory_id}")
async def get_memory_detail(
    memory_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取记忆详情，包括关联的认知节点"""
    try:
        # 查询记忆详情
        memory_query = """
        MATCH (m:Memory {uid: $memory_id})
        RETURN m
        """
        
        response = await execute_neo4j_query(memory_query, {"memory_id": memory_id})
        memory_results = response["results"]
        
        if not memory_results:
            raise HTTPException(status_code=404, detail=f"记忆 {memory_id} 不存在")
            
        memory_node = memory_results[0][0]
        
        # 查询关联的认知节点
        nodes_query = """
        MATCH (m:Memory {uid: $memory_id})-[:RELATED_TO]->(n:CognitiveNode)
        RETURN n
        """
        
        response = await execute_neo4j_query(nodes_query, {"memory_id": memory_id})
        nodes_results = response["results"]
        
        # 处理关联节点
        associated_nodes = []
        for row in nodes_results:
            node = row[0]
            associated_nodes.append({
                "id": node["uid"],
                "name": node["name"],
                "is_permanent": node["is_permanent"],
                "act_lv": node["act_lv"]
            })
            
        # 构建完整的记忆详情
        memory = {
            "id": memory_node["uid"],
            "title": memory_node["title"],
            "content": memory_node["content"],
            "created_at": memory_node["created_at"].timestamp() if isinstance(memory_node["created_at"], datetime) else memory_node["created_at"],
            "last_accessed": memory_node["last_accessed"].timestamp() if isinstance(memory_node["last_accessed"], datetime) else memory_node["last_accessed"],
            "weight": memory_node["weight"],
            "is_permanent": memory_node["is_permanent"],
            "associated_nodes": associated_nodes
        }
        
        # 尝试解析metadata
        if "metadata" in memory_node and memory_node["metadata"]:
            try:
                import json
                memory["metadata"] = json.loads(memory_node["metadata"])
            except Exception:
                memory["metadata"] = memory_node["metadata"]
                
        return memory
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆详情失败: {str(e)}")

@router.get("/stats")
async def get_memory_stats(
    conv_id: str = Query("", description="会话ID，如果为空则获取公共记忆统计"),
    current_user: User = Depends(get_current_active_user)
):
    """获取记忆统计数据"""
    try:
        # 构建查询
        stats_query = """
        MATCH (m:Memory)
        WHERE m.conv_id = $conv_id
        RETURN 
            count(m) as total_memories,
            sum(CASE WHEN m.is_permanent THEN 1 ELSE 0 END) as permanent_memories,
            avg(m.weight) as avg_weight,
            min(m.created_at) as earliest_memory,
            max(m.created_at) as latest_memory
        """
        
        response = await execute_neo4j_query(stats_query, {"conv_id": conv_id})
        stats_results = response["results"]
        
        if not stats_results:
            return {
                "total_memories": 0,
                "permanent_memories": 0,
                "avg_weight": 0,
                "earliest_memory": None,
                "latest_memory": None
            }
            
        stats_row = stats_results[0]
        
        # 获取节点关联统计
        nodes_query = """
        MATCH (m:Memory {conv_id: $conv_id})-[:RELATED_TO]->(n:CognitiveNode)
        RETURN count(DISTINCT n) as node_count
        """
        
        response = await execute_neo4j_query(nodes_query, {"conv_id": conv_id})
        nodes_results = response["results"]
        
        node_count = nodes_results[0][0] if nodes_results else 0
        
        # 构建统计数据
        stats = {
            "total_memories": stats_row[0],
            "permanent_memories": stats_row[1],
            "avg_weight": stats_row[2],
            "earliest_memory": stats_row[3].timestamp() if isinstance(stats_row[3], datetime) else stats_row[3],
            "latest_memory": stats_row[4].timestamp() if isinstance(stats_row[4], datetime) else stats_row[4],
            "associated_nodes": node_count
        }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆统计失败: {str(e)}") 