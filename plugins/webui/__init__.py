from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="WebUI",
    description="提供基于Vue的Web管理界面",
    usage="/webui - 获取WebUI的访问链接",
    type="application",
    homepage="https://github.com/用户名/项目名/tree/main/plugins/webui",
    config=None,
)

# 获取全局驱动
driver = get_driver()
app: FastAPI = driver.server_app

# 配置跨域，允许所有来源访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 当前文件所在目录
WEBUI_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(WEBUI_PATH, "static")
TEMPLATES_PATH = os.path.join(WEBUI_PATH, "templates")

# 注册静态文件
app.mount("/webui/static", StaticFiles(directory=STATIC_PATH), name="webui_static")

# 导入API路由
from .backend.api import router as api_router
app.include_router(api_router, prefix="/api/webui")

# 前端入口
@app.get("/webui", include_in_schema=False)
async def webui_index():
    print("访问WebUI页面")
    return FileResponse(os.path.join(TEMPLATES_PATH, "index.html"))

@app.get("/webui/dashboard.html", include_in_schema=False)
async def webui_dashboard():
    print("访问仪表盘页面")
    return FileResponse(os.path.join(TEMPLATES_PATH, "dashboard.html"))

# 启动时执行
@driver.on_startup
async def webui_startup():
    print("WebUI 已成功加载！")
    print(f"访问地址: http://{driver.config.host}:{driver.config.port}/webui")
    print("默认管理员账户: admin/admin - 请登录后立即修改密码")

# 从NoneBot事件系统获取数据
@driver.on_bot_connect
async def on_bot_connect(bot):
    print(f"机器人 {bot.self_id} 已连接到WebUI") 