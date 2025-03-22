import sqlite3
import os
from .api.core.config import settings

def initialize_database():
    """初始化示例数据库"""
    db_path = settings.DATABASE_PATH
    
    # 确保数据目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 连接到数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建日志表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY,
        level TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建统计信息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        value INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 插入示例数据
    try:
        # 用户表示例数据
        cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", ("admin", "admin@example.com"))
        cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", ("user1", "user1@example.com"))
        cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", ("user2", "user2@example.com"))
        
        # 日志表示例数据
        cursor.execute("INSERT INTO logs (level, message) VALUES (?, ?)", ("INFO", "系统启动"))
        cursor.execute("INSERT INTO logs (level, message) VALUES (?, ?)", ("WARNING", "磁盘空间不足"))
        cursor.execute("INSERT INTO logs (level, message) VALUES (?, ?)", ("ERROR", "数据库连接失败"))
        cursor.execute("INSERT INTO logs (level, message) VALUES (?, ?)", ("INFO", "用户登录: admin"))
        cursor.execute("INSERT INTO logs (level, message) VALUES (?, ?)", ("INFO", "用户登出: admin"))
        
        # 统计信息表示例数据
        cursor.execute("INSERT INTO statistics (name, value) VALUES (?, ?)", ("活跃用户", 42))
        cursor.execute("INSERT INTO statistics (name, value) VALUES (?, ?)", ("每日查询", 1024))
        cursor.execute("INSERT INTO statistics (name, value) VALUES (?, ?)", ("错误率", 2))
    except sqlite3.IntegrityError:
        # 数据已存在，跳过
        pass
    
    # 提交事务并关闭连接
    conn.commit()
    conn.close()
    
    print(f"初始化数据库完成: {db_path}")

if __name__ == "__main__":
    initialize_database() 