from __future__ import annotations

from enum import Enum
from typing import List


class AuditAction(str, Enum):
    SQL_TABLE_INSERT = "sql.table.insert"
    SQL_TABLE_UPDATE = "sql.table.update"
    SQL_TABLE_DELETE = "sql.table.delete"
    NEO4J_QUERY_MUTATE = "neo4j.query.mutate"
    MEMORY_NODE_CREATE = "memory.node.create"
    MEMORY_NODE_UPDATE = "memory.node.update"
    MEMORY_NODE_DELETE = "memory.node.delete"
    MEMORY_ASSOCIATION_CREATE = "memory.association.create"
    MEMORY_ASSOCIATION_UPDATE = "memory.association.update"
    MEMORY_ASSOCIATION_DELETE = "memory.association.delete"
    PLUGIN_POLICY_UPDATE = "plugin_policy.update"
    PLUGIN_POLICY_BATCH_UPDATE = "plugin_policy.batch_update"
    AUDIT_LOG_CLEANUP = "audit.log.cleanup"


class AuditTargetType(str, Enum):
    SQL_TABLE = "sql_table"
    NEO4J = "neo4j"
    COGNITIVE_NODE = "cognitive_node"
    MEMORY_ASSOCIATION = "memory_association"
    PLUGIN_POLICY = "plugin_policy"
    PLUGIN_POLICY_BATCH = "plugin_policy_batch"
    AUDIT_LOG = "audit_log"


KNOWN_AUDIT_ACTIONS = {item.value for item in AuditAction}
KNOWN_AUDIT_TARGET_TYPES = {item.value for item in AuditTargetType}


def list_known_actions() -> List[str]:
    return [item.value for item in AuditAction]


def list_known_target_types() -> List[str]:
    return [item.value for item in AuditTargetType]
