from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import initialize_database, close_database

router = APIRouter()

# @router.get("/")
# async def index():
#     return FileResponse(settings.PUBLIC_PATH / "index.html")

async def waitfor_nonebot_app(app: FastAPI):

    # 获取静态文件路径
    static_webui_path = Path(__file__).parent.parent.parent / "static" / "webui"

    # 挂载静态文件
    app.mount("/", StaticFiles(directory=static_webui_path, html=True), name="webui")

    # 初始化数据库连接
    await initialize_database()
    
    # 注册关闭事件，确保应用关闭时关闭数据库连接
    @app.on_event("shutdown")
    async def shutdown_db_client():
        await close_database()
