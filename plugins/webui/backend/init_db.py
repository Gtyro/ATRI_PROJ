import os

from tortoise import Tortoise, run_async

from .api.core.config import settings
from .api.db.models import Log, Statistic, User


async def initialize_database():
    """初始化示例数据库"""
    db_path = settings.DATABASE_PATH

    # 确保数据目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # 初始化Tortoise ORM
    db_url = f"sqlite://{db_path}"
    await Tortoise.init(
        db_url=db_url,
        modules={'models': ['plugins.persona.storage.models', 'plugins.webui.api.db.models']}
    )

    # 创建表结构
    await Tortoise.generate_schemas()

    # 插入示例数据
    # 用户表示例数据
    await User.get_or_create(username="admin", defaults={"email": "admin@example.com"})
    await User.get_or_create(username="user1", defaults={"email": "user1@example.com"})
    await User.get_or_create(username="user2", defaults={"email": "user2@example.com"})

    # 日志表示例数据
    await Log.create(level="INFO", message="系统启动")
    await Log.create(level="WARNING", message="磁盘空间不足")
    await Log.create(level="ERROR", message="数据库连接失败")
    await Log.create(level="INFO", message="用户登录: admin")
    await Log.create(level="INFO", message="用户登出: admin")

    # 统计信息表示例数据
    await Statistic.get_or_create(name="活跃用户", defaults={"value": 42})
    await Statistic.get_or_create(name="每日查询", defaults={"value": 1024})
    await Statistic.get_or_create(name="错误率", defaults={"value": 2})

    # 关闭连接
    await Tortoise.close_connections()

    print(f"初始化数据库完成: {db_path}")

def init_db():
    """运行异步初始化函数"""
    run_async(initialize_database())

if __name__ == "__main__":
    init_db()