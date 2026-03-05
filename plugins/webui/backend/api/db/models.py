from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel
from tortoise import fields
from tortoise.models import Model


# Pydantic模型用于API请求/响应
class SQLQuery(BaseModel):
    """SQL查询请求模型"""
    query: str

class TableInfo(BaseModel):
    """表信息模型"""
    name: str
    columns: List[Dict[str, Any]]

class Neo4jQuery(BaseModel):
    """Neo4j查询请求模型"""
    query: str

# Tortoise ORM模型用于数据库操作
class User(Model):
    """用户模型"""
    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=100, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
        table_description = "用户表"

class Log(Model):
    """日志模型"""
    id = fields.IntField(primary_key=True)
    level = fields.CharField(max_length=20)
    message = fields.TextField()
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "logs"
        table_description = "日志表"

class Statistic(Model):
    """统计信息模型"""
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=50)
    value = fields.IntField()
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "statistics"
        table_description = "统计信息表"


class OperationAuditLog(Model):
    """操作审计日志"""

    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=64, db_index=True)
    action = fields.CharField(max_length=128, db_index=True)
    target_type = fields.CharField(max_length=64, db_index=True)
    target_id = fields.CharField(max_length=128, null=True, db_index=True)
    success = fields.BooleanField(default=True, db_index=True)
    detail = fields.TextField(null=True)
    request_method = fields.CharField(max_length=16, null=True)
    request_path = fields.CharField(max_length=255, null=True)
    ip_address = fields.CharField(max_length=64, null=True)
    user_agent = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True, db_index=True)

    class Meta:
        table = "operation_audit_logs"
        table_description = "操作审计日志表"


from plugins.db_core.model_registry import register_model_module

register_model_module("models", "plugins.webui.backend.api.db.models")
