import uvicorn

try:
    from ..browser_entry import WEBUI_BROWSER_URL, WEBUI_HOST, WEBUI_PORT, app
except ImportError:
    from plugins.webui.browser_entry import WEBUI_BROWSER_URL, WEBUI_HOST, WEBUI_PORT, app


def main():
    print("启动数据库管理WebUI...")

    print(f"默认访问地址: {WEBUI_BROWSER_URL}")
    print("默认用户名: admin")
    print("默认密码: admin")
    print("按Ctrl+C停止服务...")

    # 启动服务
    uvicorn.run(app, host=WEBUI_HOST, port=WEBUI_PORT)

if __name__ == "__main__":
    main()
