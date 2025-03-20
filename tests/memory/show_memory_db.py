#!/usr/bin/env python3
"""
展示memory.db数据库内容的工具

这个脚本用于展示实际使用中的memory.db内容，读取并显示其中的各个表和数据。
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
import argparse

# 确保可以导入插件模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def connect_to_db(db_path):
    """连接到数据库"""
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def show_db_structure(conn):
    """展示数据库结构"""
    cursor = conn.cursor()
    
    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("\n=== 数据库表结构 ===")
    for table in tables:
        table_name = table['name']
        print(f"\n表名: {table_name}")
        
        # 获取表结构
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print("列信息:")
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")
        
        # 获取表数据量
        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        count = cursor.fetchone()['count']
        print(f"数据行数: {count}")

def show_memories(conn, limit=10):
    """展示记忆表内容"""
    cursor = conn.cursor()
    
    # 查询最新的记忆
    cursor.execute(
        "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", 
        (limit,)
    )
    
    memories = cursor.fetchall()
    
    print(f"\n=== 最新{limit}条记忆 ===")
    for i, memory in enumerate(memories):
        memory = dict(memory)
        print(f"\n记忆 {i+1}:")
        print(f"  ID: {memory['id']}")
        print(f"  用户: {memory['user_id']}")
        print(f"  内容: {memory['content']}")
        print(f"  上下文: {memory['context']}")
        print(f"  类型: {memory['type']}")
        print(f"  创建时间: {datetime.fromtimestamp(memory['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  最后访问: {datetime.fromtimestamp(memory['last_accessed']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  权重: {memory['weight']}")
        
        # 获取标签
        cursor.execute(
            "SELECT tag FROM memory_tags WHERE memory_id = ?",
            (memory['id'],)
        )
        tags = [r['tag'] for r in cursor.fetchall()]
        print(f"  标签: {tags}")
        
        # 获取元数据
        if memory['metadata']:
            try:
                metadata = json.loads(memory['metadata'])
                print(f"  元数据: {metadata}")
            except:
                print(f"  元数据: {memory['metadata']} (无法解析JSON)")

def show_associations(conn, limit=10):
    """展示记忆关联"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT a.source_id, s.content as source_content, 
               a.target_id, t.content as target_content, 
               a.strength, a.created_at
        FROM memory_associations a
        JOIN memories s ON a.source_id = s.id
        JOIN memories t ON a.target_id = t.id
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,))
    
    associations = cursor.fetchall()
    
    print(f"\n=== 最新{limit}条记忆关联 ===")
    print(f"关联数量: {len(associations)}")
    
    for i, assoc in enumerate(associations):
        print(f"\n关联 {i+1}:")
        print(f"  源记忆: {assoc['source_id']} - {assoc['source_content'][:30]}...")
        print(f"  目标记忆: {assoc['target_id']} - {assoc['target_content'][:30]}...")
        print(f"  关联强度: {assoc['strength']}")
        print(f"  创建时间: {datetime.fromtimestamp(assoc['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")

def show_message_queue(conn, limit=10):
    """展示消息队列"""
    cursor = conn.cursor()
    
    # 统计队列信息
    cursor.execute("SELECT COUNT(*) as total FROM message_queue")
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as count FROM message_queue WHERE processed = 1")
    processed = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM message_queue WHERE processed = 0 AND priority > 0")
    priority = cursor.fetchone()['count']
    
    print("\n=== 消息队列统计 ===")
    print(f"总消息数: {total}")
    print(f"已处理数: {processed}")
    print(f"未处理优先消息: {priority}")
    print(f"未处理普通消息: {total - processed - priority}")
    
    # 查询队列中的消息
    cursor.execute(
        """SELECT * FROM message_queue 
           WHERE processed = 0
           ORDER BY priority DESC, created_at ASC
           LIMIT ?""", 
        (limit,)
    )
    
    items = cursor.fetchall()
    
    print(f"\n=== 待处理队列(前{limit}条) ===")
    for i, item in enumerate(items):
        item = dict(item)
        print(f"\n消息 {i+1}:")
        print(f"  ID: {item['id']}")
        print(f"  用户: {item['user_id']}")
        print(f"  内容: {item['content']}")
        print(f"  上下文: {item['context']}")
        print(f"  群组: {item['group_id']}")
        print(f"  创建时间: {datetime.fromtimestamp(item['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  优先级: {item['priority']}")

def show_user_memories(conn, user_id, limit=10):
    """展示指定用户的记忆"""
    cursor = conn.cursor()
    
    # 查询用户记忆
    cursor.execute(
        """SELECT * FROM memories 
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""", 
        (user_id, limit)
    )
    
    memories = cursor.fetchall()
    
    print(f"\n=== 用户 {user_id} 的记忆 (最新{limit}条) ===")
    if not memories:
        print("该用户没有记忆")
        return
    
    for i, memory in enumerate(memories):
        memory = dict(memory)
        print(f"\n记忆 {i+1}:")
        print(f"  ID: {memory['id']}")
        print(f"  内容: {memory['content']}")
        print(f"  上下文: {memory['context']}")
        print(f"  创建时间: {datetime.fromtimestamp(memory['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取标签
        cursor.execute(
            "SELECT tag FROM memory_tags WHERE memory_id = ?",
            (memory['id'],)
        )
        tags = [r['tag'] for r in cursor.fetchall()]
        print(f"  标签: {tags}")

def show_context_memories(conn, context, limit=10):
    """展示指定上下文的记忆"""
    cursor = conn.cursor()
    
    # 查询上下文记忆
    cursor.execute(
        """SELECT * FROM memories 
           WHERE context = ?
           ORDER BY created_at DESC
           LIMIT ?""", 
        (context, limit)
    )
    
    memories = cursor.fetchall()
    
    print(f"\n=== 上下文 {context} 的记忆 (最新{limit}条) ===")
    if not memories:
        print("该上下文没有记忆")
        return
    
    for i, memory in enumerate(memories):
        memory = dict(memory)
        print(f"\n记忆 {i+1}:")
        print(f"  ID: {memory['id']}")
        print(f"  用户: {memory['user_id']}")
        print(f"  内容: {memory['content']}")
        print(f"  创建时间: {datetime.fromtimestamp(memory['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")

def show_popular_tags(conn, limit=10):
    """展示热门标签"""
    cursor = conn.cursor()
    
    # 查询标签统计
    cursor.execute(
        """SELECT tag, COUNT(*) as count
           FROM memory_tags
           GROUP BY tag
           ORDER BY count DESC
           LIMIT ?""", 
        (limit,)
    )
    
    tags = cursor.fetchall()
    
    print(f"\n=== 热门标签 (前{limit}个) ===")
    if not tags:
        print("没有标签数据")
        return
    
    for i, tag in enumerate(tags):
        print(f"{i+1}. {tag['tag']}: {tag['count']}条记忆")
        
        # 查询该标签下的一些记忆
        cursor.execute(
            """SELECT m.id, m.content, m.user_id, m.created_at
               FROM memory_tags t
               JOIN memories m ON t.memory_id = m.id
               WHERE t.tag = ?
               ORDER BY m.created_at DESC
               LIMIT 3""", 
            (tag['tag'],)
        )
        
        examples = cursor.fetchall()
        if examples:
            print("  示例记忆:")
            for ex in examples:
                print(f"  - {ex['content'][:50]}... (用户: {ex['user_id']})")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="展示memory.db数据库内容")
    parser.add_argument("--db", default="data/memory.db", help="数据库路径")
    parser.add_argument("--user", help="查看指定用户的记忆")
    parser.add_argument("--context", help="查看指定上下文的记忆")
    parser.add_argument("--limit", type=int, default=10, help="显示记录的数量限制")
    parser.add_argument("--summary", action="store_true", help="只显示摘要信息")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="显示所有内容")
    group.add_argument("--structure", action="store_true", help="只显示数据库结构")
    group.add_argument("--memories", action="store_true", help="只显示记忆内容")
    group.add_argument("--queue", action="store_true", help="只显示消息队列")
    group.add_argument("--tags", action="store_true", help="只显示标签信息")
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 连接到数据库
    try:
        conn = connect_to_db(args.db)
    except Exception as e:
        print(f"连接数据库失败: {e}")
        sys.exit(1)
    
    try:
        # 如果只查看特定用户的记忆
        if args.user:
            show_user_memories(conn, args.user, args.limit)
            return
        
        # 如果只查看特定上下文的记忆
        if args.context:
            show_context_memories(conn, args.context, args.limit)
            return
        
        # 如果只显示数据库结构
        if args.structure:
            show_db_structure(conn)
            return
        
        # 如果只显示记忆
        if args.memories:
            show_memories(conn, args.limit)
            return
        
        # 如果只显示队列
        if args.queue:
            show_message_queue(conn, args.limit)
            return
        
        # 如果只显示标签
        if args.tags:
            show_popular_tags(conn, args.limit)
            return
        
        # 显示摘要信息
        if args.summary:
            show_db_structure(conn)
            return
        
        # 显示所有信息
        show_db_structure(conn)
        show_memories(conn, args.limit)
        show_associations(conn, args.limit)
        show_message_queue(conn, args.limit)
        show_popular_tags(conn, args.limit)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main() 