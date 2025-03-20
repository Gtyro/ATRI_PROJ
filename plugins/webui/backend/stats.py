import sqlite3
from datetime import datetime
import os
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.event import MetaEvent
from nonebot.message import event_preprocessor
from nonebot.typing import T_State
import json

driver = get_driver()

# 数据库路径，与api.py中的保持一致
WEBUI_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "webui.db")

# 统计类型
STAT_MESSAGE = "message"
STAT_COMMAND = "command"
STAT_GROUP_MESSAGE = "group_message"
STAT_PRIVATE_MESSAGE = "private_message"
STAT_ACTIVE_USER = "active_user"
STAT_ACTIVE_GROUP = "active_group"

# 格式化当前日期
def get_today():
    return datetime.now().date().isoformat()

# 增加统计计数
def increment_stat(metric, date=None, amount=1):
    if date is None:
        date = get_today()
    
    conn = None
    try:
        conn = sqlite3.connect(WEBUI_DB_PATH)
        cursor = conn.cursor()
        
        # 检查是否存在当前日期和指标的记录
        cursor.execute(
            "SELECT value FROM statistics WHERE date = ? AND metric = ?",
            (date, metric)
        )
        result = cursor.fetchone()
        
        if result:
            # 更新现有记录
            cursor.execute(
                "UPDATE statistics SET value = value + ? WHERE date = ? AND metric = ?",
                (amount, date, metric)
            )
        else:
            # 创建新记录
            cursor.execute(
                "INSERT INTO statistics (date, metric, value) VALUES (?, ?, ?)",
                (date, metric, amount)
            )
        
        conn.commit()
    except Exception as e:
        print(f"统计错误: {e}")
    finally:
        if conn:
            conn.close()

# 记录活跃用户和群组
def record_active_entity(entity_id, metric):
    today = get_today()
    
    conn = None
    try:
        conn = sqlite3.connect(WEBUI_DB_PATH)
        cursor = conn.cursor()
        
        # 使用JSON列表存储活跃实体ID
        cursor.execute(
            "SELECT value FROM statistics WHERE date = ? AND metric = ?",
            (today, metric)
        )
        result = cursor.fetchone()
        
        if result:
            try:
                # 尝试解析现有数据
                entities = json.loads(result[0]) if isinstance(result[0], str) else []
            except json.JSONDecodeError:
                entities = []
                
            # 确保实体是列表类型
            if not isinstance(entities, list):
                entities = []
                
            # 如果实体ID不在列表中，添加它
            if str(entity_id) not in entities:
                entities.append(str(entity_id))
                cursor.execute(
                    "UPDATE statistics SET value = ? WHERE date = ? AND metric = ?",
                    (json.dumps(entities), today, metric)
                )
        else:
            # 创建新记录
            cursor.execute(
                "INSERT INTO statistics (date, metric, value) VALUES (?, ?, ?)",
                (today, metric, json.dumps([str(entity_id)]))
            )
        
        conn.commit()
    except Exception as e:
        print(f"记录活跃实体错误: {e}")
    finally:
        if conn:
            conn.close()

# 消息预处理器 - 记录消息统计
@event_preprocessor
async def record_message_stat(event: MessageEvent, bot: Bot, state: T_State):
    # 排除元事件
    if isinstance(event, MetaEvent):
        return
    
    # 增加总消息计数
    increment_stat(STAT_MESSAGE)
    
    # 根据消息类型记录
    if isinstance(event, GroupMessageEvent):
        increment_stat(STAT_GROUP_MESSAGE)
        record_active_group(event.group_id)
    elif isinstance(event, PrivateMessageEvent):
        increment_stat(STAT_PRIVATE_MESSAGE)
    
    # 记录活跃用户
    record_active_user(event.user_id)
    
    # 检查是否是命令（以 / 或 ! 开头）
    if event.get_plaintext().strip().startswith(("/", "!")):
        increment_stat(STAT_COMMAND)

# 记录活跃用户
def record_active_user(user_id):
    record_active_entity(user_id, STAT_ACTIVE_USER)

# 记录活跃群组
def record_active_group(group_id):
    record_active_entity(group_id, STAT_ACTIVE_GROUP)

# 获取统计数据（用于API接口）
def get_stats_data(start_date, end_date):
    conn = None
    try:
        conn = sqlite3.connect(WEBUI_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT date, metric, value FROM statistics WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date)
        )
        
        results = cursor.fetchall()
        
        # 处理活跃用户和群组数据
        processed_results = []
        for date, metric, value in results:
            if metric in [STAT_ACTIVE_USER, STAT_ACTIVE_GROUP]:
                try:
                    entities = json.loads(value) if isinstance(value, str) else []
                    count = len(entities) if isinstance(entities, list) else 0
                    processed_results.append((date, metric, count))
                except (json.JSONDecodeError, TypeError):
                    processed_results.append((date, metric, 0))
            else:
                processed_results.append((date, metric, value))
        
        return processed_results
    except Exception as e:
        print(f"获取统计数据错误: {e}")
        return []
    finally:
        if conn:
            conn.close()

# 启动时执行
@driver.on_startup
async def stats_startup():
    print("统计模块已加载") 