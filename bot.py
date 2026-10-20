#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter
from src.adapters.nonebot.onebot_v11_logging import install_onebot_v11_restart_log_filter
from src.infra.logging import LoggingConfig, setup_logging
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent
SUPPORTED_ENVIRONMENTS = {"dev", "prod"}


def _runtime_environment() -> str:
    environment = os.getenv("ENVIRONMENT", "prod").strip().lower()
    if environment not in SUPPORTED_ENVIRONMENTS:
        raise RuntimeError("ENVIRONMENT 必须是 dev 或 prod。")
    return environment


def _config_path(environment: str) -> Path:
    path = PROJECT_ROOT / f".env.{environment}"
    if not path.is_file():
        raise RuntimeError(f"找不到运行配置文件：{path.name}。")
    return path


def _configured_log_level(config_path: Path) -> int:
    configured = os.getenv("LOG_LEVEL")
    if not configured:
        configured = dotenv_values(config_path).get("LOG_LEVEL")
    value = str(configured or "INFO").strip().upper()
    names = {
        "NOTSET": logging.NOTSET,
        "TRACE": 5,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "SUCCESS": 25,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "FATAL": logging.CRITICAL,
        "CRITICAL": logging.CRITICAL,
    }
    try:
        return int(value)
    except ValueError:
        try:
            return names[value]
        except KeyError as exc:
            raise RuntimeError("LOG_LEVEL 必须是有效的日志等级或数字。") from exc


_environment = _runtime_environment()
_config_path = _config_path(_environment)
os.environ.setdefault("ENVIRONMENT", _environment)


# 初始化日志系统
setup_logging(LoggingConfig(log_level=_configured_log_level(_config_path)))

# 加载环境变量
nonebot.init(_env_file=_config_path)

# 注册适配器
driver = nonebot.get_driver()
install_onebot_v11_restart_log_filter()
# OneBot V11 适配器选项
onebot_config = {}  # V11 一般不需要特殊配置
driver.register_adapter(OneBot11Adapter)

# 加载插件
nonebot.load_plugins("plugins")
nonebot.load_builtin_plugins()

if __name__ == "__main__":
    nonebot.run()
