#!/usr/bin/env python3
"""
迁移脚本 - 将现有记忆数据从关系型数据库迁移到Neo4j

用法:
python -m plugins.persona.scripts.migrate_to_neo4j

注意：确保已正确设置Neo4j连接信息
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from tortoise import Tortoise
from neomodel import db, config
from plugins.persona.utils.config import load_config
from plugins.persona.storage.models import Memory as OldMemory, CognitiveNode as OldNode, Association as OldAssociation
from plugins.persona.storage.memory_models import Memory, CognitiveNode

# 配置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载配置文件
CONFIG_PATH = "data/persona.yaml"
config_data = load_config(CONFIG_PATH)

# Neo4j配置
neo4j_config = config_data.get("neo4j_config", {})
neo4j_uri = neo4j_config.get("uri", "bolt://localhost:7687")
neo4j_user = neo4j_config.get("user", "neo4j")
neo4j_password = neo4j_config.get("password", "neo4jpsw")

# 正确设置Neo4j连接URL
# 确保URL中包含用户名和密码 - neomodel要求的格式为: bolt://user:password@host:port
if "//" in neo4j_uri:
    protocol_part, host_part = neo4j_uri.split("//", 1)
    config.DATABASE_URL = f"{protocol_part}//{neo4j_user}:{neo4j_password}@{host_part}"
else:
    logger.error(f"无效的Neo4j URI格式: {neo4j_uri}")
    sys.exit(1)

logger.info(f"Neo4j连接URL: {config.DATABASE_URL}")

# SQLite/PostgreSQL配置
DB_URL = None
if config_data.get("use_postgres", False):
    pg_config = config_data.get("postgres_config", {})
    DB_URL = (
        f"postgres://{pg_config.get('user', 'postgres')}:"
        f"{pg_config.get('password', 'postgres')}@"
        f"{pg_config.get('host', 'localhost')}:"
        f"{pg_config.get('port', 5432)}/"
        f"{pg_config.get('database', 'postgres')}"
    )
else:
    db_path = config_data.get("db_path", "data/persona.db")
    DB_URL = f"sqlite://{db_path}"

async def setup_tortoise():
    """初始化Tortoise ORM连接"""
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["plugins.persona.storage.models"]}
    )
    logger.info(f"已连接到关系型数据库: {DB_URL}")

async def setup_neo4j():
    """测试Neo4j连接并创建必要的约束"""
    try:
        results, meta = db.cypher_query("MATCH (n) RETURN count(n) as count", {})
        logger.info(f"已连接到Neo4j数据库，当前有 {results[0][0]} 个节点")
        
        # 创建约束
        db.cypher_query("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.uid IS UNIQUE")
        db.cypher_query("CREATE CONSTRAINT IF NOT EXISTS FOR (n:CognitiveNode) REQUIRE n.uid IS UNIQUE")
        db.cypher_query("CREATE INDEX IF NOT EXISTS FOR (n:CognitiveNode) ON (n.conv_id, n.name)")
        
        logger.info("已创建Neo4j约束和索引")
    except Exception as e:
        logger.error(f"连接Neo4j失败: {e}")
        raise

async def migrate_nodes():
    """迁移认知节点数据"""
    # 获取所有节点
    old_nodes = await OldNode.all()
    node_count = len(old_nodes)
    logger.info(f"开始迁移 {node_count} 个认知节点")
    
    # 旧ID到新ID的映射
    node_id_map = {}
    
    migrated = 0
    for old_node in old_nodes:
        try:
            # 使用相同的ID创建新节点
            new_uid = str(old_node.id)
            node_id_map[str(old_node.id)] = new_uid
            
            # 查询是否已存在
            existing = CognitiveNode.nodes.get_or_none(uid=new_uid)
            if existing:
                logger.debug(f"节点已存在: {new_uid} ({old_node.name})")
                continue
                
            # 创建新节点
            new_node = CognitiveNode(
                uid=new_uid,
                name=old_node.name,
                conv_id=old_node.conv_id,
                act_lv=old_node.act_lv,
                is_permanent=old_node.is_permanent,
                created_at=old_node.created_at,
                last_accessed=old_node.last_accessed
            ).save()
            
            migrated += 1
            if migrated % 100 == 0:
                logger.info(f"已迁移 {migrated}/{node_count} 个节点")
                
        except Exception as e:
            logger.error(f"迁移节点失败 {old_node.id} ({old_node.name}): {e}")
    
    logger.info(f"完成节点迁移: {migrated}/{node_count}")
    return node_id_map

async def migrate_memories(node_id_map: Dict[str, str]):
    """迁移记忆数据"""
    # 获取所有记忆
    old_memories = await OldMemory.all()
    memory_count = len(old_memories)
    logger.info(f"开始迁移 {memory_count} 个记忆")
    
    # 记录节点-记忆关系
    node_memory_relations = []
    
    migrated = 0
    for old_memory in old_memories:
        try:
            # 使用相同的ID创建新记忆
            new_uid = str(old_memory.id)
            
            # 查询是否已存在
            existing = Memory.nodes.get_or_none(uid=new_uid)
            if existing:
                logger.debug(f"记忆已存在: {new_uid} ({old_memory.title})")
                continue
            
            # 创建新记忆
            new_memory = Memory(
                uid=new_uid,
                conv_id=old_memory.conv_id,
                title=old_memory.title,
                content=old_memory.content,
                weight=old_memory.weight,
                is_permanent=old_memory.is_permanent,
                created_at=old_memory.created_at,
                last_accessed=old_memory.last_accessed,
                metadata="{}" # 简化处理
            ).save()
            
            # 获取关联的节点
            related_nodes = await old_memory.nodes.all()
            for node in related_nodes:
                node_id = str(node.id)
                if node_id in node_id_map:
                    # 保存节点-记忆关系以便稍后创建
                    node_memory_relations.append((node_id_map[node_id], new_uid))
            
            migrated += 1
            if migrated % 100 == 0:
                logger.info(f"已迁移 {migrated}/{memory_count} 个记忆")
                
        except Exception as e:
            logger.error(f"迁移记忆失败 {old_memory.id} ({old_memory.title}): {e}")
    
    logger.info(f"完成记忆迁移: {migrated}/{memory_count}")
    return node_memory_relations

async def create_memory_node_relations(relations: List[tuple]):
    """创建记忆和节点之间的关系"""
    relation_count = len(relations)
    logger.info(f"开始创建 {relation_count} 个记忆-节点关系")
    
    created = 0
    for node_id, memory_id in relations:
        try:
            # 获取节点和记忆
            node = CognitiveNode.nodes.get_or_none(uid=node_id)
            memory = Memory.nodes.get_or_none(uid=memory_id)
            
            if node and memory:
                # 创建关系
                memory.nodes.connect(node)
                created += 1
                
                if created % 100 == 0:
                    logger.info(f"已创建 {created}/{relation_count} 个记忆-节点关系")
        except Exception as e:
            logger.error(f"创建记忆-节点关系失败 ({node_id}-{memory_id}): {e}")
    
    logger.info(f"完成记忆-节点关系创建: {created}/{relation_count}")

async def migrate_associations(node_id_map: Dict[str, str]):
    """迁移节点关联关系"""
    # 获取所有关联关系
    old_associations = await OldAssociation.all()
    assoc_count = len(old_associations)
    logger.info(f"开始迁移 {assoc_count} 个节点关联")
    
    migrated = 0
    for old_assoc in old_associations:
        try:
            source_id = str(old_assoc.source_id)
            target_id = str(old_assoc.target_id)
            
            if source_id in node_id_map and target_id in node_id_map:
                # 获取新的节点
                source_node = CognitiveNode.nodes.get_or_none(uid=node_id_map[source_id])
                target_node = CognitiveNode.nodes.get_or_none(uid=node_id_map[target_id])
                
                if source_node and target_node:
                    # 检查关系是否已存在
                    rel = source_node.associated_nodes.relationship(target_node)
                    if not rel:
                        # 创建关联关系，并设置属性
                        rel = source_node.associated_nodes.connect(target_node)
                        rel.strength = old_assoc.strength
                        rel.created_at = old_assoc.created_at
                        rel.updated_at = old_assoc.updated_at
                        rel.save()
                        migrated += 1
            
            if migrated % 100 == 0 and migrated > 0:
                logger.info(f"已迁移 {migrated}/{assoc_count} 个节点关联")
                
        except Exception as e:
            logger.error(f"迁移关联关系失败 {old_assoc.id}: {e}")
    
    logger.info(f"完成节点关联迁移: {migrated}/{assoc_count}")

async def main():
    """主函数"""
    try:
        logger.info("开始数据迁移...")
        
        # 初始化数据库连接
        await setup_tortoise()
        await setup_neo4j()
        
        # 清空Neo4j数据库 (慎用!)
        should_clear = input("是否清空Neo4j数据库? [y/N]: ").lower() == 'y'
        if should_clear:
            db.cypher_query("MATCH (n) DETACH DELETE n", {})
            logger.info("已清空Neo4j数据库")
        
        # 迁移数据
        node_id_map = await migrate_nodes()
        node_memory_relations = await migrate_memories(node_id_map)
        await create_memory_node_relations(node_memory_relations)
        await migrate_associations(node_id_map)
        
        logger.info("数据迁移完成")
        
    except Exception as e:
        logger.error(f"迁移过程出错: {e}")
    finally:
        # 关闭连接
        await Tortoise.close_connections()
        logger.info("已关闭所有数据库连接")

if __name__ == "__main__":
    asyncio.run(main()) 