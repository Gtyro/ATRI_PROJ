from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm

from .core.config import settings
from .auth import auth_router
from .db import db_router
from .auth.utils import authenticate_user, create_access_token
from datetime import timedelta

# 创建FastAPI应用
app = FastAPI(
    title="数据库管理WebUI",
    description="一个简单的数据库管理Web界面",
    version="0.1.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/webui", StaticFiles(directory="static/webui", html=True), name="webui")

# 添加路由
app.include_router(auth_router)
app.include_router(db_router)

# 为了兼容旧的前端代码，添加一些兼容路由
@app.post("/token")
async def legacy_login(form_data: OAuth2PasswordRequestForm = Depends()):
    """兼容旧版登录API"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def legacy_get_user(response: Response):
    """重定向到新的获取用户API"""
    response.status_code = status.HTTP_307_TEMPORARY_REDIRECT
    response.headers["Location"] = "/auth/users/me"
    return {}

# 健康检查端点
@app.get("/")
async def root():
    return {"status": "ok", "message": "数据库管理WebUI API正常运行"}
