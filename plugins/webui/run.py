import uvicorn
import os
import sqlite3
from api import create_app
from api.core.config import settings
from init_db import initialize_database

def main():
    print("启动数据库管理WebUI...")
    
    # 检查数据库文件是否存在
    db_path = settings.DATABASE_PATH
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        print(f"创建数据目录: {os.path.dirname(db_path)}")
    
    # 检查数据库是否存在并初始化
    if not os.path.exists(db_path):
        print(f"数据库文件 {db_path} 不存在，正在初始化示例数据库...")
        initialize_database()
    else:
        # 检查数据库是否包含表
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        if not tables:
            print("数据库文件存在但没有表，正在初始化示例数据...")
            initialize_database()
    
    print("默认访问地址: http://127.0.0.1:8080/webui")
    print("默认用户名: admin")
    print("默认密码: admin")
    print("按Ctrl+C停止服务...")
    
    # 创建独立运行的FastAPI应用
    app = create_app()
    
    # 启动服务
    uvicorn.run(app, host="127.0.0.1", port=8080)

if __name__ == "__main__":
    main() 