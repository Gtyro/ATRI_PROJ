#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter
import os
import logging

# 设置日志级别为DEBUG，方便排查问题
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 加载环境变量
config_path = os.path.join(os.path.dirname(__file__), ".env.prod")
if os.path.exists(config_path):
    print(f"加载配置文件：{config_path}")
    # 使用正确的配置加载方式
    nonebot.init(_env_file=config_path)
else:
    print("警告：找不到配置文件.env.prod，将使用默认配置")
    nonebot.init(debug=True)

# 注册适配器
driver = nonebot.get_driver()
# OneBot V11 适配器选项
onebot_config = {}  # V11 一般不需要特殊配置
driver.register_adapter(OneBot11Adapter)

# 打印重要配置信息
@driver.on_startup
async def print_config():
    print(f"OneBot V11 配置信息:")
    print(f"  - HOST: {driver.config.host}")
    print(f"  - PORT: {driver.config.port}")
    print(f"  - COMMAND_START: {driver.config.command_start}")
    print(f"  - COMMAND_SEP: {driver.config.command_sep}")
    print(f"  - SUPERUSERS: {driver.config.superusers}")
    print(f"  - NICKNAME: {driver.config.nickname}")
    print(f"  - DEBUG: {driver.config.debug}")

# 加载插件
nonebot.load_plugins("plugins")
nonebot.load_builtin_plugins()

# 定义异步启动函数
async def _start():
    print("机器人已成功启动！")
    print("请确保NapCatQQ已连接并配置正确")
    print("可用命令：帮助、你好、天气 [城市]")
    print("已启用自动回复功能：机器人会对非命令消息回复问候语")
    print("\n连接NapCatQQ的提示：")
    print("1. 确保NapCatQQ支持OneBot V11协议")
    print("2. 设置NapCatQQ的反向WS连接地址为 ws://127.0.0.1:8080/onebot/v11/ws")
    print("3. 如果连接仍有问题，请检查NapCatQQ的日志")

driver.on_startup(_start)

if __name__ == "__main__":
    nonebot.run() 