"""
Neo4j数据库操作工具
通过基础设施层提供实现，避免直接依赖 Persona 存储模块。
"""

from src.infra.db.neo4j_gateway import (
    close_neo4j,
    create_association,
    create_cognitive_node,
    delete_association,
    delete_cognitive_node,
    execute_neo4j_query,
    get_neo4j_unavailable_reason,
    get_associations,
    get_cognitive_nodes,
    get_conversations,
    get_node_by_id,
    initialize_neo4j,
    neo4j_is_available,
    update_association,
    update_cognitive_node,
)

__all__ = [
    "initialize_neo4j",
    "close_neo4j",
    "neo4j_is_available",
    "get_neo4j_unavailable_reason",
    "execute_neo4j_query",
    "get_cognitive_nodes",
    "get_node_by_id",
    "create_cognitive_node",
    "update_cognitive_node",
    "delete_cognitive_node",
    "get_associations",
    "create_association",
    "update_association",
    "delete_association",
    "get_conversations",
]
