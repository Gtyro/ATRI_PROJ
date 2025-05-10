"""
Neo4j数据库操作工具
用于处理与记忆网络相关的操作
依赖于plugins.persona.storage.memory_repository中的连接管理
"""

from fastapi import HTTPException
import logging
import os
import yaml
from pathlib import Path
from plugins.persona.storage.memory_repository import MemoryRepository
from plugins.persona.storage.memory_models import CognitiveNode, Memory, NodeAssociation
from neomodel import db

# 从persona.yaml读取配置
def load_config():
    config_path = Path('data/persona.yaml')
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {
        "neo4j_config": {
            "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.environ.get("NEO4J_USER", "neo4j"),
            "password": os.environ.get("NEO4J_PASSWORD", "neo4jpsw")
        }
    }

# 加载配置
config = load_config()

# 初始化存储库
memory_repo = MemoryRepository(config)

async def initialize_neo4j():
    """初始化Neo4j连接"""
    try:
        # 使用memory模块的初始化方法
        await memory_repo.initialize()
        logging.info("Neo4j连接已初始化")
    except Exception as e:
        logging.error(f"Neo4j初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"Neo4j连接错误: {str(e)}")

async def close_neo4j():
    """关闭Neo4j连接"""
    # Neo4j会话在每次查询后自动关闭，这里主要是记录日志
    logging.info("Neo4j连接已关闭")

async def execute_neo4j_query(query: str, params: dict = None):
    """执行Neo4j Cypher查询"""
    try:
        if params is None:
            params = {}
        
        results, meta = db.cypher_query(query, params)
        return {"results": results, "metadata": meta}
    except Exception as e:
        logging.error(f"Neo4j查询执行错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"查询执行错误: {str(e)}")

async def get_cognitive_nodes(conv_id: str = '', limit: int = 50):
    """获取认知节点数据，用于知识图谱可视化
    
    Args:
        conv_id: 可选，如果提供则获取特定会话的节点，否则获取公共节点(空conv_id)
        limit: 返回的最大节点数量，默认50个
    """
    try:
        # 构建查询条件
        if conv_id:  # 非空字符串
            nodes = CognitiveNode.nodes.filter(conv_id=conv_id).order_by("-act_lv")[:limit]
        else:  # 空字符串，获取公共图谱
            nodes = CognitiveNode.nodes.filter(conv_id="").order_by("-act_lv")[:limit]
        
        # 转换为字典列表
        return [node.to_dict() for node in nodes]
    except Exception as e:
        logging.error(f"获取认知节点错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取节点错误: {str(e)}")

async def get_node_by_id(node_id: str):
    """根据ID获取节点"""
    try:
        node = CognitiveNode.nodes.get(uid=node_id)
        return node.to_dict()
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except Exception as e:
        logging.error(f"获取节点错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取节点错误: {str(e)}")

async def create_cognitive_node(data: dict):
    """创建新的认知节点"""
    try:
        # 避免使用uid字段，让Neo4j自动生成
        if 'uid' in data:
            del data['uid']
            
        node = CognitiveNode(**data)
        node.save()
        return node.to_dict()
    except Exception as e:
        logging.error(f"创建节点错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"创建节点错误: {str(e)}")

async def update_cognitive_node(node_id: str, data: dict):
    """更新认知节点"""
    try:
        node = CognitiveNode.nodes.get(uid=node_id)
        
        # 避免更新uid字段
        if 'uid' in data:
            del data['uid']
            
        # 更新节点属性
        for key, value in data.items():
            if hasattr(node, key):
                setattr(node, key, value)
        
        node.save()
        return node.to_dict()
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except Exception as e:
        logging.error(f"更新节点错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"更新节点错误: {str(e)}")

async def delete_cognitive_node(node_id: str):
    """删除认知节点"""
    try:
        node = CognitiveNode.nodes.get(uid=node_id)
        node.delete()
        return {"success": True, "message": "节点删除成功"}
    except CognitiveNode.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except Exception as e:
        logging.error(f"删除节点错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"删除节点错误: {str(e)}")

async def get_associations(conv_id: str = '', node_ids: list = None, limit: int = 200):
    """获取节点之间的关联数据
    
    Args:
        conv_id: 可选，如果提供则获取特定会话的关联，否则获取公共关联
        node_ids: 可选，节点ID列表，如果提供则只获取这些节点之间的关联
        limit: 返回的最大关联数量，默认200个
    """
    try:
        # 构建Cypher查询，获取节点的关联关系
        query = """
        MATCH (n:CognitiveNode)-[r:ASSOCIATED_WITH]->(m:CognitiveNode)
        WHERE n.conv_id = $conv_id AND m.conv_id = $conv_id
        """
        
        params = {"conv_id": conv_id if conv_id else ""}
        
        # 如果提供了节点ID列表，只获取这些节点之间的关联
        if node_ids and len(node_ids) > 0:
            query += " AND n.uid IN $node_ids AND m.uid IN $node_ids"
            params["node_ids"] = node_ids
            
        query += " RETURN n.uid as source_id, n.name as source_name, m.uid as target_id, m.name as target_name, r.strength as strength, id(r) as id ORDER BY r.strength DESC LIMIT $limit"
        params["limit"] = limit
        
        results, _ = db.cypher_query(query, params)
        
        # 转换结果为字典列表
        associations = []
        for record in results:
            associations.append({
                "id": str(record[5]),  # 关系ID
                "source_id": record[0],
                "source_name": record[1],
                "target_id": record[2],
                "target_name": record[3],
                "strength": record[4]
            })
            
        # 返回与原API兼容的格式，便于前端处理
        return {"rows": associations}
    except Exception as e:
        logging.error(f"获取关联关系错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取关联关系错误: {str(e)}")

async def create_association(source_id: str, target_id: str, strength: float = 1.0):
    """创建节点之间的关联关系"""
    try:
        # 获取源节点和目标节点
        source_node = CognitiveNode.nodes.get(uid=source_id)
        target_node = CognitiveNode.nodes.get(uid=target_id)
        
        # 创建关联关系
        rel = source_node.associated_nodes.connect(target_node, {"strength": strength})
        
        return {
            "success": True, 
            "message": "关联创建成功",
            "source_id": source_id,
            "target_id": target_id,
            "strength": strength
        }
    except (CognitiveNode.DoesNotExist) as e:
        raise HTTPException(status_code=404, detail="节点不存在")
    except Exception as e:
        logging.error(f"创建关联关系错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"创建关联关系错误: {str(e)}")

async def update_association(source_id: str, target_id: str, strength: float):
    """更新节点之间的关联关系强度"""
    try:
        # 获取源节点和目标节点
        source_node = CognitiveNode.nodes.get(uid=source_id)
        target_node = CognitiveNode.nodes.get(uid=target_id)
        
        # 查找现有关系
        relationships = source_node.associated_nodes.relationship(target_node)
        if not relationships:
            raise HTTPException(status_code=404, detail="关联关系不存在")
        
        # 更新关系强度
        for rel in relationships:
            rel.strength = strength
            rel.save()
        
        return {
            "success": True, 
            "message": "关联更新成功",
            "source_id": source_id,
            "target_id": target_id,
            "strength": strength
        }
    except (CognitiveNode.DoesNotExist) as e:
        raise HTTPException(status_code=404, detail="节点不存在")
    except Exception as e:
        logging.error(f"更新关联关系错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"更新关联关系错误: {str(e)}")

async def delete_association(source_id: str, target_id: str):
    """删除节点之间的关联关系"""
    try:
        # 获取源节点和目标节点
        source_node = CognitiveNode.nodes.get(uid=source_id)
        target_node = CognitiveNode.nodes.get(uid=target_id)
        
        # 查找并删除关系
        relationships = source_node.associated_nodes.relationship(target_node)
        if not relationships:
            raise HTTPException(status_code=404, detail="关联关系不存在")
        
        # 删除所有匹配的关系
        for rel in relationships:
            rel.delete()
        
        return {"success": True, "message": "关联删除成功"}
    except (CognitiveNode.DoesNotExist) as e:
        raise HTTPException(status_code=404, detail="节点不存在")
    except Exception as e:
        logging.error(f"删除关联关系错误: {str(e)}")
        raise HTTPException(status_code=400, detail=f"删除关联关系错误: {str(e)}")

async def get_conversations():
    """获取所有会话ID (根据节点的conv_id字段)"""
    try:
        query = """
        MATCH (n:CognitiveNode)
        WHERE n.conv_id <> ''
        RETURN DISTINCT n.conv_id as gid, n.conv_id as name
        ORDER BY n.conv_id
        """
        
        results, _ = db.cypher_query(query, {})
        
        # 转换结果为字典列表
        conversations = []
        for record in results:
            conversations.append({
                "id": record[0],
                "name": record[1].split("_")[1] if "_" in record[1] else record[1]  # 提取群号或用户ID
            })
            
        return {"rows": conversations}
    except Exception as e:
        logging.error(f"获取会话列表错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话列表错误: {str(e)}") 