#!/usr/bin/env python3
"""
memory.db 单元测试文件
用于展示和测试记忆数据库的内容和功能
"""

import unittest
import os
import sys
import json
import sqlite3
from datetime import datetime

# 确保可以导入插件模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plugins.memory.storage import StorageManager
from plugins.memory.core import MemorySystem

class MemoryDBTest(unittest.TestCase):
    """测试memory.db数据库及相关功能"""
    
    def setUp(self):
        """测试前准备工作"""
        # 使用测试数据库文件路径
        self.test_db_path = "test_memory.db"
        
        # 创建或连接到测试数据库
        self.storage = StorageManager(self.test_db_path)
        self.storage.initialize_db()
        
        # 创建测试数据
        self._create_test_data()
    
    def tearDown(self):
        """测试后清理工作"""
        # 关闭连接
        self.storage.close()
        
        # 删除测试数据库文件
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
                print(f"已删除测试数据库: {self.test_db_path}")
            except Exception as e:
                print(f"无法删除测试数据库: {e}")
    
    def _create_test_data(self):
        """创建测试数据"""
        # 添加几条测试记忆
        test_memories = [
            {
                "id": "mem1",
                "user_id": "user1",
                "content": "今天天气真好",
                "context": "group_123456",
                "type": "chat",
                "created_at": datetime.now().timestamp() - 3600,  # 1小时前
                "tags": ["天气", "闲聊"]
            },
            {
                "id": "mem2",
                "user_id": "user2",
                "content": "推荐一本科幻小说吧",
                "context": "group_123456",
                "type": "chat",
                "created_at": datetime.now().timestamp() - 1800,  # 30分钟前
                "tags": ["推荐", "科幻", "小说"]
            },
            {
                "id": "mem3",
                "user_id": "user1",
                "content": "我喜欢三体这本书",
                "context": "private_user1",
                "type": "chat",
                "created_at": datetime.now().timestamp() - 900,  # 15分钟前
                "tags": ["三体", "科幻", "小说"]
            }
        ]
        
        # 添加记忆
        for memory in test_memories:
            self.storage._add_memory(memory)
        
        # 添加关联
        conn = self.storage._get_connection()
        cursor = conn.cursor()
        
        # 创建一些记忆之间的关联
        associations = [
            ("mem2", "mem3", 0.8),  # 科幻小说和三体的强关联
            ("mem1", "mem2", 0.3)   # 天气和科幻小说的弱关联
        ]
        
        for source, target, strength in associations:
            cursor.execute(
                """INSERT INTO memory_associations 
                   (source_id, target_id, strength, created_at)
                   VALUES (?, ?, ?, ?)""",
                (source, target, strength, datetime.now().timestamp())
            )
        
        # 添加一些消息到队列
        queue_items = [
            {
                "id": "q1",
                "user_id": "user3",
                "content": "人工智能的发展趋势",
                "context": "group_123456",
                "created_at": datetime.now().timestamp(),
                "priority": 0
            },
            {
                "id": "q2",
                "user_id": "user4",
                "content": "如何学习Python",
                "context": "private_user4",
                "created_at": datetime.now().timestamp() - 60,
                "priority": 1
            }
        ]
        
        for item in queue_items:
            self.storage._add_to_queue(item)
        
        conn.commit()
    
    def test_display_memory_tables(self):
        """展示记忆数据库的所有表和内容"""
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
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
            
            # 获取表数据
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            print(f"数据行数: {len(rows)}")
            if rows:
                print("数据示例:")
                for i, row in enumerate(rows[:5]):  # 最多显示5行
                    print(f"  行 {i+1}:")
                    row_dict = dict(row)
                    
                    # 对特殊字段进行格式化处理
                    for key, value in row_dict.items():
                        if key in ['created_at', 'last_accessed'] and value:
                            try:
                                row_dict[key] = f"{value} ({datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')})"
                            except:
                                pass
                        elif key == 'metadata' and value:
                            try:
                                row_dict[key] = json.loads(value)
                            except:
                                pass
                    
                    for key, value in row_dict.items():
                        print(f"    {key}: {value}")
                
                if len(rows) > 5:
                    print(f"    ... 还有 {len(rows)-5} 行未显示")
        
        conn.close()
    
    def test_get_user_memories(self):
        """测试获取用户记忆功能"""
        user_id = "user1"
        memories = self.storage._get_user_memories(user_id)
        
        print(f"\n=== 用户 {user_id} 的记忆 ===")
        print(f"记忆数量: {len(memories)}")
        for i, memory in enumerate(memories):
            print(f"\n记忆 {i+1}:")
            print(f"  内容: {memory['content']}")
            print(f"  上下文: {memory['context']}")
            print(f"  类型: {memory['type']}")
            print(f"  创建时间: {datetime.fromtimestamp(memory['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  标签: {memory['tags']}")
    
    def test_get_context_memories(self):
        """测试获取上下文记忆功能"""
        context = "group_123456"
        memories = self.storage._get_context_memories(context)
        
        print(f"\n=== 上下文 {context} 的记忆 ===")
        print(f"记忆数量: {len(memories)}")
        for i, memory in enumerate(memories):
            print(f"\n记忆 {i+1}:")
            print(f"  用户: {memory['user_id']}")
            print(f"  内容: {memory['content']}")
            print(f"  类型: {memory['type']}")
            print(f"  创建时间: {datetime.fromtimestamp(memory['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  标签: {memory['tags']}")
    
    def test_memory_associations(self):
        """测试记忆关联功能"""
        conn = self.storage._get_connection()
        cursor = conn.cursor()
        
        print("\n=== 记忆关联 ===")
        cursor.execute("""
            SELECT a.source_id, s.content as source_content, 
                   a.target_id, t.content as target_content, 
                   a.strength
            FROM memory_associations a
            JOIN memories s ON a.source_id = s.id
            JOIN memories t ON a.target_id = t.id
        """)
        
        associations = cursor.fetchall()
        print(f"关联数量: {len(associations)}")
        
        for i, assoc in enumerate(associations):
            print(f"\n关联 {i+1}:")
            print(f"  源记忆: {assoc['source_id']} - {assoc['source_content']}")
            print(f"  目标记忆: {assoc['target_id']} - {assoc['target_content']}")
            print(f"  关联强度: {assoc['strength']}")
    
    def test_message_queue(self):
        """测试消息队列功能"""
        queue_items = self.storage._get_queue_items()
        
        print("\n=== 消息队列 ===")
        print(f"队列长度: {len(queue_items)}")
        
        for i, item in enumerate(queue_items):
            print(f"\n消息 {i+1}:")
            print(f"  ID: {item['id']}")
            print(f"  用户: {item['user_id']}")
            print(f"  内容: {item['content']}")
            print(f"  上下文: {item['context']}")
            print(f"  创建时间: {datetime.fromtimestamp(item['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  优先级: {item['priority']}")
            print(f"  处理状态: {'已处理' if item['processed'] else '未处理'}")
    
    def test_memory_tags(self):
        """测试记忆标签功能"""
        conn = self.storage._get_connection()
        cursor = conn.cursor()
        
        print("\n=== 记忆标签统计 ===")
        cursor.execute("""
            SELECT tag, COUNT(*) as count
            FROM memory_tags
            GROUP BY tag
            ORDER BY count DESC
        """)
        
        tags = cursor.fetchall()
        print(f"不同标签数量: {len(tags)}")
        
        for tag in tags:
            print(f"  {tag['tag']}: {tag['count']}条记忆")
        
        print("\n=== 标签详情 ===")
        cursor.execute("""
            SELECT t.tag, m.id, m.content
            FROM memory_tags t
            JOIN memories m ON t.memory_id = m.id
            ORDER BY t.tag
        """)
        
        tag_details = cursor.fetchall()
        current_tag = None
        
        for detail in tag_details:
            if current_tag != detail['tag']:
                current_tag = detail['tag']
                print(f"\n标签: {current_tag}")
            
            print(f"  - {detail['id']}: {detail['content']}")

class MemorySystemTest(unittest.TestCase):
    """测试MemorySystem类的功能"""
    
    def setUp(self):
        """测试前准备工作"""
        # 使用测试数据库文件路径
        self.test_db_path = "test_memory_system.db"
        
        # 创建MemorySystem对象
        self.memory_system = MemorySystem(db_path=self.test_db_path)
    
    def tearDown(self):
        """测试后清理工作"""
        # 关闭连接
        self.memory_system.storage.close()
        
        # 删除测试数据库文件
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
                print(f"已删除测试数据库: {self.test_db_path}")
            except Exception as e:
                print(f"无法删除测试数据库: {e}")
    
    def test_system_initialization(self):
        """测试系统初始化"""
        print("\n=== 记忆系统初始化 ===")
        print(f"数据库路径: {self.memory_system.db_path}")
        print("配置信息:")
        for key, value in self.memory_system.config.items():
            print(f"  {key}: {value}")
    
    async def test_process_message(self):
        """测试消息处理功能"""
        print("\n=== 消息处理 ===")
        
        # 添加测试消息
        messages = [
            {"user_id": "test_user1", "content": "今天天气真好", "context": "test_chat"},
            {"user_id": "test_user2", "content": "我喜欢编程", "context": "test_chat"},
            {"user_id": "test_user1", "content": "你会什么编程语言？", "context": "test_chat", "is_priority": True}
        ]
        
        for msg in messages:
            user_id = msg["user_id"]
            content = msg["content"]
            context = msg["context"]
            is_priority = msg.get("is_priority", False)
            
            memory_id = await self.memory_system.process_message(
                user_id=user_id,
                message=content,
                context=context,
                is_priority=is_priority
            )
            
            if memory_id:
                print(f"立即处理消息: {content} (ID: {memory_id})")
            else:
                print(f"加入队列消息: {content}")
        
        # 处理队列
        processed = await self.memory_system.process_queue()
        print(f"处理队列消息数: {processed}")
        
        # 查看队列状态
        queue_status = await self.memory_system.get_queue_status()
        print("队列状态:")
        print(f"  总消息数: {queue_status['stats']['total']}")
        print(f"  优先消息: {queue_status['stats']['priority']}")
        print(f"  普通消息: {queue_status['stats']['normal']}")
        print(f"  下次处理时间: {queue_status['next_process_in']}秒后")

def main():
    """主函数"""
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    unittest.main()

if __name__ == "__main__":
    main() 