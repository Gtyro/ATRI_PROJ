import logging
import re

from fastapi import HTTPException
from tortoise import Tortoise
from tortoise.expressions import Q, RawSQL

# 改为从shared模块导入
from ..core.shared import table_to_model_map

# from ..core.database import execute_checkpoint

async def execute_select_query(query: str):
    """执行SELECT查询"""
    if not is_select_query(query):
        raise HTTPException(
            status_code=403,
            detail="出于安全原因，仅支持SELECT查询"
        )

    try:
        # 使用连接对象执行查询
        conn = Tortoise.get_connection("default")
        results = await conn.execute_query_dict(query) # Executes a RAW SQL query statement, and returns the resultset as a list of dicts.

        # 处理结果 - 针对SELECT查询，结果通常是一个包含行的列表
        # 将每一行转换为字典
        columns = []
        rows = []

        if results and len(results) > 0:
            if hasattr(results[0], 'keys'):
                # 如果结果有keys方法，说明是Row对象
                first_row = results[0]
                columns = list(first_row.keys())
                rows = [dict(row) for row in results]

        return {"columns": columns, "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询执行错误: {str(e)}")

def is_select_query(query: str) -> bool:
    """检查是否为SELECT查询，阻止非SELECT语句"""
    pattern = re.compile(r'^\s*SELECT\s+', re.IGNORECASE)
    return bool(pattern.match(query))

async def get_tables():
    """获取所有表名称"""
    try:
        # 执行checkpoint确保能看到最新数据
        # await execute_checkpoint()

        models = Tortoise.apps.get("models", {})
        table_names = [model._meta.db_table for model in models.values()]
        return {"tables": table_names}
    except Exception as e:
        logging.error(f"获取表名称错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")

async def get_table_structure(table_name: str):
    """获取表结构"""
    try:
        query = f"PRAGMA table_info({table_name});"
        conn = Tortoise.get_connection("default")
        columns = await conn.execute_query_dict(query)
        return {"table_name": table_name, "columns": columns}
    except Exception as e:
        logging.error(f"获取表结构错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")

async def execute_insert_query(table_name: str, data: dict):
    """执行INSERT操作"""
    try:
        # 获取表对应的模型
        model_class = get_model_for_table(table_name)
        if not model_class:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在或未映射")

        # 创建并保存新记录
        instance = model_class(**data)
        await instance.save()
        return {"success": True, "message": "数据添加成功", "id": instance.pk}
    except Exception as e:
        logging.error(f"插入操作错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"插入操作错误: {str(e)}")

async def execute_update_query(table_name: str, id_value: any, data: dict):
    """执行UPDATE操作"""
    try:
        # 获取表对应的模型
        model_class = get_model_for_table(table_name)
        if not model_class:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在或未映射")

        # 查找主键字段
        pk_field = get_primary_key_field(model_class)
        if not pk_field:
            raise HTTPException(status_code=400, detail=f"无法确定表 {table_name} 的主键")

        # 尝试根据主键类型转换id值
        id_value = convert_id_value(id_value, pk_field)

        # 查找并更新记录
        try:
            instance = await model_class.get(**{pk_field: id_value})
            for key, value in data.items():
                setattr(instance, key, value)
            await instance.save()
            return {"success": True, "message": "数据更新成功"}
        except Exception:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {id_value} 的记录")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新操作错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"更新操作错误: {str(e)}")

async def execute_delete_query(table_name: str, id_value: any):
    """执行DELETE操作"""
    try:
        # 获取表对应的模型
        model_class = get_model_for_table(table_name)
        if not model_class:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在或未映射")

        # 查找主键字段
        pk_field = get_primary_key_field(model_class)
        if not pk_field:
            raise HTTPException(status_code=400, detail=f"无法确定表 {table_name} 的主键")

        # 尝试根据主键类型转换id值
        id_value = convert_id_value(id_value, pk_field)

        # 查找并删除记录
        try:
            instance = await model_class.get(**{pk_field: id_value})
            await instance.delete()
            return {"success": True, "message": "数据删除成功"}
        except Exception:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {id_value} 的记录")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"删除操作错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"删除操作错误: {str(e)}")

def get_primary_key_field(model_class):
    """获取模型的主键字段名"""
    try:
        for field_name, field_obj in model_class._meta.fields_map.items():
            if field_obj.pk:
                return field_name
        return "id"  # 默认返回id
    except Exception as e:
        logging.error(f"获取主键字段错误: {str(e)}")
        return "id"  # 出错时默认返回id

def convert_id_value(id_value, pk_field):
    """根据字段名转换ID值为正确的类型"""
    try:
        from uuid import UUID

        # 如果id字段名包含uuid，尝试将其转换为UUID对象
        if "uuid" in pk_field.lower() and isinstance(id_value, str):
            return UUID(id_value)
        # 否则根据类型转换为整数
        elif isinstance(id_value, str) and id_value.isdigit():
            return int(id_value)
        return id_value
    except Exception as e:
        logging.error(f"转换ID值错误: {str(e)}")
        return id_value

def get_model_for_table(table_name: str):
    """根据表名获取对应的模型类"""
    model = table_to_model_map.get(table_name)

    # 检查获取到的是否是有效的模型类
    if model and hasattr(model, 'get') and callable(getattr(model, 'get')):
        return model

    logging.error(f"找不到表 {table_name} 对应的有效模型类")
    return None