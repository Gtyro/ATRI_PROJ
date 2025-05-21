from fastapi import APIRouter
from .bot_info import router as bot_info_router
from .system_info import router as system_info_router

# 创建dashboard主路由
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# 包含子路由
dashboard_router.include_router(bot_info_router)

# 将system_info路由包含到dashboard_router中
dashboard_router.include_router(system_info_router) 