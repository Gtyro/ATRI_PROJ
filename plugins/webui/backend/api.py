from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sqlite3
import os
import nonebot
from nonebot import get_driver
import json
import logging

# 创建日志记录器
logger = logging.getLogger("webui")

# 创建路由
router = APIRouter(tags=["webui"])

# 安全配置
SECRET_KEY = "请更改为随机字符串"  # 生产环境中应该使用环境变量加载一个安全的密钥
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 数据库路径，使用nonebot的数据目录
WEBUI_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "webui.db")

# 确保数据目录存在
os.makedirs(os.path.dirname(WEBUI_DB_PATH), exist_ok=True)

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Token获取工具
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/webui/token")

# 模型定义
class User(BaseModel):
    username: str
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class APIResponse(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

# 初始化数据库
def init_db():
    conn = sqlite3.connect(WEBUI_DB_PATH)
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        hashed_password TEXT NOT NULL,
        disabled INTEGER DEFAULT 0
    )
    ''')
    
    # 创建统计表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        date TEXT,
        metric TEXT,
        value INTEGER,
        PRIMARY KEY (date, metric)
    )
    ''')
    
    # 查询是否已有管理员账户
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        # 创建默认管理员账户，密码为admin
        hashed_password = pwd_context.hash("admin")
        cursor.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)",
                     ("admin", hashed_password))
        print("已创建默认管理员账户: admin/admin - 请登录后立即修改密码")
    
    conn.commit()
    conn.close()

# 验证密码
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 获取用户
def get_user(username: str):
    conn = sqlite3.connect(WEBUI_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, hashed_password, disabled FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return UserInDB(
            username=user[0],
            hashed_password=user[1],
            disabled=bool(user[2])
        )
    return None

# 认证用户
def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# 创建访问令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 获取当前用户
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# 获取当前活跃用户
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user

# 登录端点
@router.post("/login")
async def login(request: Request) -> dict:
    """处理用户登录请求并返回token"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return {"code": 400, "message": "请提供用户名和密码"}
        
        # 使用认证函数验证用户
        user = authenticate_user(username, password)
        if user:
            # 使用JWT生成token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": username}, expires_delta=access_token_expires
            )
            return {
                "code": 200, 
                "message": "登录成功", 
                "data": {"token": access_token, "type": "bearer"}
            }
        else:
            return {"code": 401, "message": "用户名或密码错误"}
    except Exception as e:
        logging.error(f"登录失败: {str(e)}")
        return {"code": 500, "message": f"服务器错误: {str(e)}"}

@router.get("/users/me")
async def get_current_user(current_user: User = Depends(get_current_user)) -> dict:
    """获取当前登录用户信息"""
    return {
        "code": 200,
        "message": "成功",
        "data": {
            "username": current_user.username
        }
    }

# 获取机器人状态
@router.get("/bot/status")
async def get_bot_status_api(current_user: User = Depends(get_current_user)) -> dict:
    """API endpoint获取机器人状态"""
    return get_bot_status()

def get_bot_status() -> dict:
    """获取所有机器人状态"""
    bots = []
    count = 0
    
    try:
        # 获取所有机器人
        bot_map = nonebot.get_bots()
        
        for bot_id, bot in bot_map.items():
            try:
                # 安全地获取昵称
                nickname = "未知"
                try:
                    if hasattr(bot, "nickname"):
                        if callable(bot.nickname):
                            nickname = bot.nickname()
                        else:
                            nickname = bot.nickname
                    elif hasattr(bot, "user_id"):
                        nickname = str(bot.user_id)
                except Exception:
                    pass
                
                # 创建可序列化的字典
                bot_info = {
                    "bot_id": str(bot_id),
                    "nickname": nickname,
                    "type": bot.__class__.__name__,
                    "connected": bool(getattr(bot, "connected", True))
                }
                
                bots.append(bot_info)
                
                # 只有在线的机器人才计数
                if bot_info["connected"]:
                    count += 1
                    
            except Exception as e:
                logger.error(f"获取机器人 {bot_id} 状态时出错: {e}")
                bots.append({
                    "bot_id": str(bot_id),
                    "nickname": "错误",
                    "type": "Unknown",
                    "connected": False,
                    "error": str(e)
                })
    except Exception as e:
        logger.error(f"获取机器人列表时出错: {e}")
        return {"code": 500, "message": f"获取机器人列表时出错: {e}"}
    
    return {
        "code": 200,
        "message": "成功",
        "data": {
            "count": count,
            "bots": bots
        }
    }

# 获取插件列表
@router.get("/plugins")
async def get_plugins(current_user: User = Depends(get_current_user)) -> dict:
    """获取所有已加载的插件"""
    try:
        plugins_list = []
        for plugin_name in nonebot.plugins.keys():
            plugin = nonebot.plugins[plugin_name]
            
            # 获取插件元数据
            metadata = {}
            if hasattr(plugin, "metadata"):
                if isinstance(plugin.metadata, dict):
                    metadata = plugin.metadata
            
            plugins_list.append({
                "name": plugin_name,
                "module_name": getattr(plugin, "__module__", "未知"),
                "metadata": metadata
            })
        
        return {
            "code": 200,
            "message": "成功",
            "data": {
                "count": len(plugins_list),
                "plugins": plugins_list
            }
        }
    except Exception as e:
        logger.error(f"获取插件列表时出错: {e}")
        return {"code": 500, "message": f"获取插件列表时出错: {e}"}

# 获取统计数据
@router.get("/stats")
async def get_statistics(
    days: int = Query(7, description="要获取的天数"), 
    current_user: User = Depends(get_current_user)
) -> dict:
    """获取统计数据"""
    try:
        # 模拟生成统计数据
        # 实际应用中应从数据库中获取
        import random
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        stats = []
        
        metrics = ["message_count", "command_count", "active_users"]
        
        for i in range(days):
            date = today - timedelta(days=i)
            stats.append({
                "date": date.strftime("%Y-%m-%d"),
                "message_count": random.randint(100, 500),
                "command_count": random.randint(10, 100),
                "active_users": random.randint(5, 50)
            })
        
        # 按日期排序
        stats.sort(key=lambda x: x["date"])
        
        return {
            "code": 200,
            "message": "获取统计数据成功",
            "data": {
                "stats": stats,
                "metrics": metrics
            }
        }
    except Exception as e:
        logger.error(f"获取统计数据时出错: {e}")
        return {"code": 500, "message": f"服务器错误: {str(e)}"}

# 查询数据库
@router.post("/database/query")
async def execute_database_query(request: Request, current_user: User = Depends(get_current_user)) -> dict:
    """执行数据库查询"""
    try:
        data = await request.json()
        query = data.get("query", "")
        params = data.get("params", [])
        
        # 安全检查，只允许SELECT语句
        if not query.strip().upper().startswith("SELECT"):
            return {"code": 403, "message": "只允许SELECT查询"}
        
        import sqlite3
        from pathlib import Path
        
        # 获取数据库文件路径
        db_path = Path("data") / "memory.db"
        if not db_path.exists():
            return {"code": 404, "message": "数据库文件不存在"}
        
        # 执行查询
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 处理结果
            result = []
            columns = []
            if rows:
                columns = list(rows[0].keys())
                for row in rows:
                    result.append({column: row[column] for column in columns})
            
            return {
                "code": 200,
                "message": "查询成功",
                "data": {
                    "count": len(result),
                    "columns": columns,
                    "rows": result
                }
            }
        finally:
            cursor.close()
            conn.close()
            
    except sqlite3.Error as e:
        return {"code": 400, "message": f"数据库错误: {str(e)}"}
    except Exception as e:
        logger.error(f"执行查询时出错: {e}")
        return {"code": 500, "message": f"服务器错误: {str(e)}"}

# 获取数据库表结构
@router.get("/database/schema", response_model=APIResponse)
async def get_database_schema(current_user: User = Depends(get_current_active_user)):
    try:
        conn = sqlite3.connect(WEBUI_DB_PATH)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        schema = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            schema[table_name] = []
            for col in columns:
                schema[table_name].append({
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2],
                    "notnull": col[3],
                    "default_value": col[4],
                    "pk": col[5]
                })
        
        return APIResponse(
            code=200,
            message="获取成功",
            data=schema
        )
    except Exception as e:
        return APIResponse(code=500, message=f"获取表结构错误: {str(e)}")
    finally:
        if conn:
            conn.close()

# 初始化数据库
init_db() 