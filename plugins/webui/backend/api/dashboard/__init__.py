from fastapi import APIRouter

# 导入dashboard下的所有路由
from .bot_info import router as bot_info_router

# 创建dashboard主路由
dashboard_router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
)

# 包含子路由
dashboard_router.include_router(bot_info_router) 