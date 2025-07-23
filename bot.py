#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import re
from datetime import datetime

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter

# 创建一个更有效的日志过滤器类
class SystemInfoLogFilter(logging.Filter):
    def filter(self, record):
        return '/api/dashboard/system-info' not in record.getMessage()

# 创建自定义的FileHandler，应用过滤器
class FilteredFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        super().__init__(filename, mode, encoding, delay)
        self.addFilter(SystemInfoLogFilter())

# 设置日志记录
datestr = datetime.now().strftime("%Y-%m-%d %H:%M")

# 创建并配置根记录器
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(filename)s - %(lineno)d %(message)s",
    datefmt="%m-%d_%H:%M:%S",
    handlers=[
        FilteredFileHandler(f"logs/{datestr}.log"),  # 使用过滤后的文件处理器
        logging.StreamHandler()  # 控制台输出不过滤，便于调试
    ]
)

# 确保所有相关日志记录器都应用过滤器
for name in ['', 'uvicorn', 'uvicorn.access', 'fastapi', 'httptools_impl']:
    logger = logging.getLogger(name)
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.addFilter(SystemInfoLogFilter())
    # 如果记录器没有处理器，直接添加过滤器
    if not logger.handlers:
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