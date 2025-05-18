#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter
import os
import logging
from datetime import datetime

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