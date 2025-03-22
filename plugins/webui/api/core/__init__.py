from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .config import settings


async def waitfor_nonebot_app(app: FastAPI):

    # 获取静态文件路径
    static_webui_path = Path(__file__).parent.parent.parent / "static" / "webui"

    # 挂载静态文件
    app.mount("/webui", StaticFiles(directory=static_webui_path, html=True), name="webui")