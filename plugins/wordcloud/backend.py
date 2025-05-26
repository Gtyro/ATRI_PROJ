from fastapi import FastAPI

from .api import router as wordcloud_router

def register_router(app: FastAPI):
    """注册词云插件的API路由"""
    app.include_router(wordcloud_router, prefix="/api", tags=["wordcloud"]) 