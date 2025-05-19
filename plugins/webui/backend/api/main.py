import uvicorn

from ..api import app

if __name__ == "__main__":
    print("main file is {}".format(__file__))
    uvicorn.run(app, host="127.0.0.1", port=8080)