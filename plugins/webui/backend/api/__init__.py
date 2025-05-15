import logging
import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm

from .core.config import settings
from .auth import auth_router
from .db import db_router
from .auth.utils import authenticate_user, create_access_token
from datetime import timedelta

# 创建FastAPI应用的工厂函数
def create_app():
    """
    工厂函数：创建并配置FastAPI应用
    根据不同环境返回适当配置的应用实例
    """
    fastapi_app = FastAPI(
        title="数据库管理WebUI",
        description="一个简单的数据库管理Web界面",
        version="0.1.0",
    )

    # 配置CORS
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_webui_path = (Path(__file__).parent.parent.parent / "static" / "webui").resolve()

    # 挂载静态文件
    fastapi_app.mount("/webui", StaticFiles(directory=static_webui_path, html=True), name="webui")

    # 添加路由
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(db_router)

    return fastapi_app

# 默认应用实例
app = create_app()

# # 健康检查端点
# @app.get("/")
# async def root():
#     return {"status": "ok", "message": "数据库管理WebUI API正常运行"}
