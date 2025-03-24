from pydantic import BaseModel
from typing import List, Dict, Any
from tortoise import fields
from tortoise.models import Model
from datetime import datetime

# Pydantic模型用于API请求/响应
class SQLQuery(BaseModel):
    """SQL查询请求模型"""
    query: str

class TableInfo(BaseModel):
    """表信息模型"""
    name: str
    columns: List[Dict[str, Any]]

# Tortoise ORM模型用于数据库操作
class User(Model):
    """用户模型"""
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=100, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
        table_description = "用户表"

class Log(Model):
    """日志模型"""
    id = fields.IntField(pk=True)
    level = fields.CharField(max_length=20)
    message = fields.TextField()
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "logs"
        table_description = "日志表"

class Statistic(Model):
    """统计信息模型"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    value = fields.IntField()
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "statistics"
        table_description = "统计信息表"