"""
Neo4j数据库操作工具（基础设施层）
当前仍复用 Persona 的存储实现，后续可替换为独立实现。
"""

import asyncio
import logging
from typing import Any, Optional, Tuple

from fastapi import HTTPException
from neomodel import db

from src.core.domain import PersonaConfig
from src.infra.db.neo4j.memory_models import CognitiveNode
from src.infra.db.neo4j.memory_repository import MemoryRepository
from src.infra.db.neo4j.unavailable import (
    UnavailableMemoryRepository,
    get_memory_repo_unavailable_reason,
    is_memory_repo_available,
)


_init_lock = asyncio.Lock()
_memory_repo: Optional[Any] = None
_active_connection: Optional[Tuple[str, str]] = None


def _connection_key(config: PersonaConfig) -> Tuple[str, str]:
    return (config.neo4j_config.uri, config.neo4j_config.user)


def _warn_on_connection_mismatch(config: Optional[PersonaConfig]) -> None:
    if config is None or _active_connection is None:
        return
    requested = _connection_key(config)
    if requested != _active_connection:
        logging.warning(
            "Neo4j已初始化，忽略新的连接配置请求，继续使用现有连接: uri=%s user=%s",
            _active_connection[0],
            _active_connection[1],
        )


def neo4j_is_available() -> bool:
    return is_memory_repo_available(_memory_repo)


def get_neo4j_unavailable_reason() -> str:
    return get_memory_repo_unavailable_reason(_memory_repo)


def _build_unavailable_http_exception() -> HTTPException:
    reason = get_neo4j_unavailable_reason() or "Neo4j 当前不可用"
    return HTTPException(status_code=503, detail=f"Neo4j不可用: {reason}")


async def _require_neo4j_ready() -> Any:
    if neo4j_is_available():
        return _memory_repo
    return await initialize_neo4j(allow_unavailable=False)


async def initialize_neo4j(
    config: Optional[PersonaConfig] = None,
    *,
    allow_unavailable: bool = False,
) -> Any:
    """初始化Neo4j连接（进程内只执行一次）。"""
    global _memory_repo
    global _active_connection

    if _memory_repo is not None:
        if is_memory_repo_available(_memory_repo):
            _warn_on_connection_mismatch(config)
            return _memory_repo
        if allow_unavailable:
            _warn_on_connection_mismatch(config)
            return _memory_repo

    async with _init_lock:
        if _memory_repo is not None:
            if is_memory_repo_available(_memory_repo):
                _warn_on_connection_mismatch(config)
                return _memory_repo
            if allow_unavailable:
                _warn_on_connection_mismatch(config)
                return _memory_repo

        effective_config = config or PersonaConfig.load()
        memory_repo = MemoryRepository(effective_config)
        _active_connection = _connection_key(effective_config)

        try:
            await memory_repo.initialize()
        except Exception as e:
            reason = str(e)
            logging.error(f"Neo4j初始化失败: {reason}")
            unavailable_repo = UnavailableMemoryRepository(reason)
            _memory_repo = unavailable_repo
            if allow_unavailable:
                logging.warning("Neo4j 不可用，已切换为降级模式: %s", reason)
                return unavailable_repo
            raise _build_unavailable_http_exception()

        _memory_repo = memory_repo
        logging.info("Neo4j连接已初始化")
        _warn_on_connection_mismatch(config)
        return _memory_repo


async def close_neo4j():
    """关闭Neo4j连接"""
    logging.info("Neo4j连接已关闭")


async def execute_neo4j_query(query: str, params: dict = None):
    """执行Neo4j Cypher查询"""
    try:
        await _require_neo4j_ready()
        if params is None:
            params = {}

        results, meta = db.cypher_query(query, params)
        return {"results": results, "metadata": meta}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Neo4j查询执行错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"查询执行错误: {str(e)}")


async def get_cognitive_nodes(conv_id: str = "", limit: int = 50):
    """获取认知节点数据，用于知识图谱可视化"""
    try:
        await _require_neo4j_ready()
        if conv_id:
            nodes = CognitiveNode.nodes.filter(conv_id=conv_id).order_by("-act_lv")[:limit]
        else:
            nodes = CognitiveNode.nodes.filter(conv_id="").order_by("-act_lv")[:limit]

        return [node.to_dict() for node in nodes]
    except Exception as e:
        logging.error(f"获取认知节点错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取节点错误: {str(e)}")


async def get_node_by_id(node_id: str):
    """根据ID获取节点"""
    try:
        await _require_neo4j_ready()
        node = CognitiveNode.nodes.get(uid=node_id)
        return node.to_dict()
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"获取节点错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取节点错误: {str(e)}")


async def create_cognitive_node(data: dict):
    """创建新的认知节点"""
    try:
        await _require_neo4j_ready()
        if "uid" in data:
            del data["uid"]

        node = CognitiveNode(**data)
        node.save()
        return node.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"创建节点错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"创建节点错误: {str(e)}")


async def update_cognitive_node(node_id: str, data: dict):
    """更新认知节点"""
    try:
        await _require_neo4j_ready()
        node = CognitiveNode.nodes.get(uid=node_id)

        if "uid" in data:
            del data["uid"]

        for key, value in data.items():
            if hasattr(node, key):
                setattr(node, key, value)

        node.save()
        return node.to_dict()
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新节点错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"更新节点错误: {str(e)}")


async def delete_cognitive_node(node_id: str):
    """删除认知节点"""
    try:
        await _require_neo4j_ready()
        node = CognitiveNode.nodes.get(uid=node_id)
        node.delete()
        return {"success": True, "message": "节点删除成功"}
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"删除节点错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"删除节点错误: {str(e)}")


async def get_associations(conv_id: str = "", node_ids: list = None, limit: int = 200):
    """获取节点之间的关联数据"""
    try:
        await _require_neo4j_ready()
        query = """
        MATCH (n:CognitiveNode)-[r:ASSOCIATED_WITH]->(m:CognitiveNode)
        WHERE n.conv_id = $conv_id AND m.conv_id = $conv_id
        """

        params = {"conv_id": conv_id if conv_id else ""}

        if node_ids and len(node_ids) > 0:
            query += " AND n.uid IN $node_ids AND m.uid IN $node_ids"
            params["node_ids"] = node_ids

        query += (
            " RETURN n.uid as source_id, n.name as source_name, m.uid as target_id, "
            "m.name as target_name, r.strength as strength, elementId(r) as id "
            "ORDER BY r.strength DESC LIMIT $limit"
        )
        params["limit"] = limit

        results, _ = db.cypher_query(query, params)

        associations = []
        for record in results:
            associations.append(
                {
                    "id": str(record[5]),
                    "source_id": record[0],
                    "source_name": record[1],
                    "target_id": record[2],
                    "target_name": record[3],
                    "strength": record[4],
                }
            )

        return {"rows": associations}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"获取关联关系错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取关联关系错误: {str(e)}")


async def create_association(source_id: str, target_id: str, strength: float = 1.0):
    """创建节点之间的关联关系"""
    try:
        await _require_neo4j_ready()
        source_node = CognitiveNode.nodes.get(uid=source_id)
        target_node = CognitiveNode.nodes.get(uid=target_id)

        source_node.associated_nodes.connect(target_node, {"strength": strength})

        return {
            "success": True,
            "message": "关联创建成功",
            "source_id": source_id,
            "target_id": target_id,
            "strength": strength,
        }
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail="节点不存在")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"创建关联关系错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"创建关联关系错误: {str(e)}")


async def update_association(source_id: str, target_id: str, strength: float):
    """更新节点之间的关联关系强度"""
    try:
        await _require_neo4j_ready()
        source_node = CognitiveNode.nodes.get(uid=source_id)
        target_node = CognitiveNode.nodes.get(uid=target_id)

        relationships = source_node.associated_nodes.relationship(target_node)
        if not relationships:
            raise HTTPException(status_code=404, detail="关联关系不存在")

        for rel in relationships:
            rel.strength = strength
            rel.save()

        return {
            "success": True,
            "message": "关联更新成功",
            "source_id": source_id,
            "target_id": target_id,
            "strength": strength,
        }
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail="节点不存在")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新关联关系错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"更新关联关系错误: {str(e)}")


async def delete_association(source_id: str, target_id: str):
    """删除节点之间的关联关系"""
    try:
        await _require_neo4j_ready()
        source_node = CognitiveNode.nodes.get(uid=source_id)
        target_node = CognitiveNode.nodes.get(uid=target_id)

        relationships = source_node.associated_nodes.relationship(target_node)
        if not relationships:
            raise HTTPException(status_code=404, detail="关联关系不存在")

        for rel in relationships:
            rel.delete()

        return {"success": True, "message": "关联删除成功"}
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail="节点不存在")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"删除关联关系错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"删除关联关系错误: {str(e)}")


async def get_conversations():
    """获取所有会话ID (根据节点的conv_id字段)"""
    try:
        await _require_neo4j_ready()
        query = """
        MATCH (n:CognitiveNode)
        WHERE n.conv_id <> ''
        RETURN DISTINCT n.conv_id as gid, n.conv_id as name
        ORDER BY n.conv_id
        """

        results, _ = db.cypher_query(query, {})

        conversations = []
        for record in results:
            conversations.append(
                {
                    "id": record[0],
                    "name": record[1].split("_")[1] if "_" in record[1] else record[1],
                }
            )

        return {"rows": conversations}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"获取会话列表错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话列表错误: {str(e)}")
