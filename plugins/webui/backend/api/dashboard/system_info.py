import os
import platform
import time
import sys
import psutil
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

# 创建API路由
router = APIRouter()

# 系统启动时间
start_time = time.time()

@router.get("/system-info")
async def get_system_info():
    """
    获取系统信息，包括CPU、内存、磁盘使用情况
    """
    try:
        # 获取CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # 获取内存信息
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used
        memory_total = memory.total
        
        # 获取磁盘信息
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used = disk.used
        disk_total = disk.total
        
        # 获取操作系统信息
        os_name = f"{platform.system()} {platform.release()}"
        python_version = sys.version.split()[0]
        
        # 计算运行时间
        uptime = int(time.time() - start_time)
        
        # 组合结果
        result = {
            "cpu": cpu_percent,
            "memory": memory_percent,
            "memory_used": memory_used,
            "memory_total": memory_total,
            "disk": disk_percent,
            "disk_used": disk_used,
            "disk_total": disk_total,
            "os_name": os_name,
            "python_version": python_version,
            "uptime": uptime,
            "timestamp": int(time.time() * 1000)  # 毫秒级时间戳
        }
        
        return JSONResponse(content=result)
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        ) 