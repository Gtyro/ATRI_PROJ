import uvicorn

from ..api import WEBUI_HOST, WEBUI_PORT, app

if __name__ == "__main__":
    print("main file is {}".format(__file__))
    uvicorn.run(app, host=WEBUI_HOST, port=WEBUI_PORT)
