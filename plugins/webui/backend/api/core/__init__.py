from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import (close_database, initialize_database_system,
                       register_models)

router = APIRouter()

# @router.get("/")
# async def index():
#     return FileResponse(settings.PUBLIC_PATH / "index.html")

async def waitfor_nonebot_app(app: FastAPI):

    # 获取静态文件路径
    static_webui_path = (Path(__file__).parent.parent.parent.parent / "static" / "webui").resolve()
    
    # 先注册所有模型，但不初始化
    await register_models()
    
    # 初始化数据库连接，这将应用所有已注册的模型
    await initialize_database_system()
    
    # 注册关闭事件，确保应用关闭时关闭数据库连接
    @app.on_event("shutdown")
    async def shutdown_db_client():
        await close_database()
        
    # 将静态文件挂载放在最后，确保API路由优先级更高
    # 修改挂载路径为"/webui"，避免干扰API路由
    app.mount("/webui", StaticFiles(directory=static_webui_path, html=True), name="static_webui")
    
    # 添加一个重定向路由，使根路径重定向到/webui
    @app.get("/")
    async def redirect_to_webui():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/webui")
