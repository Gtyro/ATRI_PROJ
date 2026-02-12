"""
模型注册辅助模块
提供去中心化的模型注册入口
"""

import logging
from typing import List, Tuple

from .db_manager import db_manager

_registered_modules: List[Tuple[str, str]] = []
_registered_module_set = set()

# 回退用的默认注册列表（兼容旧逻辑）
_default_modules: List[Tuple[str, str]] = [
    ("models", "plugins.models"),
    ("models", "plugins.message_basic.models"),
    ("models", "src.infra.db.tortoise.message_models"),
    ("models", "plugins.webui.backend.api.db.models"),
    ("models", "plugins.wordcloud.models"),
]


def register_model_module(app_name: str, module_path: str) -> None:
    """供插件自注册模型模块路径。"""
    if module_path not in _registered_module_set:
        _registered_modules.append((app_name, module_path))
        _registered_module_set.add(module_path)
        logging.debug(f"已登记模型模块: {module_path}")
    else:
        logging.debug(f"模型模块已登记，跳过: {module_path}")


def get_registered_model_modules() -> List[Tuple[str, str]]:
    """获取已登记的模型模块列表。"""
    return list(_registered_modules)


def register_all_models():
    """
    注册应用中所有已登记的模型
    如果没有任何登记，则回退到默认列表
    """
    modules = get_registered_model_modules()
    if not modules:
        logging.warning("未检测到自注册模型，回退到集中注册列表")
        modules = list(_default_modules)

    for app_name, module_path in modules:
        db_manager.register_models(app_name, [module_path])

    registered_modules = db_manager.get_registered_modules()
    logging.debug(f"已注册全部 {len(registered_modules)} 个数据库模型")
    return registered_modules