from fastapi import APIRouter, Depends
from ..auth.utils import get_current_active_user
from .bot_info import router as bot_info_router
from .system_info import router as system_info_router

# 创建dashboard主路由
dashboard_router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_active_user)],
)

# 包含子路由
dashboard_router.include_router(bot_info_router)

# 将system_info路由包含到dashboard_router中
dashboard_router.include_router(system_info_router)
