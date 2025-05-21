from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import (close_database, initialize_database_system)

router = APIRouter()

# @router.get("/")
# async def index():
#     return FileResponse(settings.PUBLIC_PATH / "index.html")
