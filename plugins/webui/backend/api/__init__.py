import logging
import os
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from .audit import router as audit_router
from .auth.router import router as auth_router
from .dashboard import dashboard_router
from .db.router import router as db_router
from .memory import router as memory_router
from .logs import router as logs_router
from .module_metrics import router as module_metrics_router
from .plugin_policy import router as plugin_policy_router
from .core.config import settings
from .core.database import close_database, initialize_database_system

WEBUI_HOST = os.getenv("WEBUI_HOST", "127.0.0.1")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", "8188"))
WEBUI_BROWSER_URL = f"http://{WEBUI_HOST}:{WEBUI_PORT}/webui"

def configure_app(app: FastAPI, is_nonebot_app: bool = False):
    """
    统一配置应用的函数，可用于独立FastAPI应用或NoneBot应用

    Args:
        app: 要配置的FastAPI应用实例
        is_nonebot_app: 是否为NoneBot应用
    """
    # 如果是独立应用，需要配置CORS
    if not is_nonebot_app:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 获取静态文件路径
    static_webui_path = (Path(__file__).parent.parent.parent / "static" / "webui").resolve()

    # The ATRI host stays on its internal port; the standalone WebUI host serves assets.
    if is_nonebot_app:
        @app.get("/webui", include_in_schema=False)
        @app.get("/webui/", include_in_schema=False)
        async def redirect_webui_browser():
            return RedirectResponse(url=WEBUI_BROWSER_URL)
    else:
        app.mount("/webui", StaticFiles(directory=static_webui_path, html=True), name="webui")

    # 添加所有路由
    app.include_router(auth_router)
    app.include_router(db_router)
    app.include_router(dashboard_router)
    app.include_router(memory_router)
    app.include_router(plugin_policy_router)
    app.include_router(logs_router)
    app.include_router(audit_router)
    app.include_router(module_metrics_router)

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return {"status": "ok"}

    # 注册主页重定向
    @app.get("/")
    async def redirect_to_webui():
        return RedirectResponse(url=WEBUI_BROWSER_URL if is_nonebot_app else "/webui")

    # 返回配置好的应用
    return app

# 创建FastAPI应用的工厂函数
def create_app():
    """
    工厂函数：创建并配置FastAPI应用
    根据不同环境返回适当配置的应用实例
    """
    # 创建基础FastAPI应用
    fastapi_app = FastAPI(
        title="数据库管理WebUI",
        description="一个简单的数据库管理Web界面",
        version="0.1.0",
    )

    # 配置应用
    configure_app(fastapi_app)

    # 注册启动和关闭事件
    @fastapi_app.on_event("startup")
    async def startup_event():
        # 初始化数据库连接
        await initialize_database_system()

    # 注册关闭事件
    @fastapi_app.on_event("shutdown")
    async def shutdown_event():
        await close_database()

    return fastapi_app

# 默认应用实例
app = create_app()
