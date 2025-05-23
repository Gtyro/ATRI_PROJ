#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from datetime import datetime

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter

datestr = datetime.now().strftime("%Y-%m-%d %H:%M")
# 设置日志级别为DEBUG，方便排查问题
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(filename)s - %(lineno)d %(message)s",
    datefmt="%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"logs/{datestr}.log"),
        logging.StreamHandler()
    ]
)

# 添加过滤器，用于过滤system-info API请求日志
class SystemInfoLogFilter(logging.Filter):
    def filter(self, record):
        # 检查日志是否包含system-info请求
        message = str(record.msg) + str(getattr(record, "args", ""))
        if "GET /api/dashboard/system-info" in message and "httptools_impl.py" in message:
            return False  # 不记录system-info请求
        return True  # 记录其他所有日志

# 获取特定的日志记录器，如果存在的话
for logger_name in ["uvicorn", "uvicorn.access", "httptools_impl"]:
    logger = logging.getLogger(logger_name)
    if logger:
        logger.addFilter(SystemInfoLogFilter())

# 加载环境变量
config_path = os.path.join(os.path.dirname(__file__), ".env.dev")
if os.path.exists(config_path):
    # 使用正确的配置加载方式
    nonebot.init(_env_file=config_path)
else:
    logging.warning("警告：找不到配置文件.env.dev，将使用默认配置")
    nonebot.init(debug=True)

# 注册适配器
driver = nonebot.get_driver()
# OneBot V11 适配器选项
onebot_config = {}  # V11 一般不需要特殊配置
driver.register_adapter(OneBot11Adapter)

# 加载插件
nonebot.load_plugins("plugins")
nonebot.load_builtin_plugins()

if __name__ == "__main__":
    nonebot.run() 