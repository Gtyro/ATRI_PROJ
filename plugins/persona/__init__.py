import inspect
import os
import sys


# 判断当前代码是否在脚本模式下执行
def is_running_as_script():
    """检测代码是否在脚本模式下运行而非作为插件导入"""
    # 获取调用栈
    stack = inspect.stack()
    main_module = sys.modules['__main__']
    main_file = getattr(main_module, '__file__', '')

    # 检查是否从scripts目录执行
    if main_file and '/scripts/' in main_file:
        return True

    # 检查调用链是否来自script目录的模块
    for frame in stack:
        if '/scripts/' in frame.filename:
            return True

    return False

# 只有在非脚本模式下才导入完整的插件功能
if not is_running_as_script():
    from .core.persona_system import PersonaSystem
    from .plugin import *

    __all__ = ["PersonaSystem"]
else:
    # 仅导出迁移脚本所需的最小模块和函数
    from .storage import (CognitiveNode, Memory, MemoryRepository,
                          MessageQueue, MessageRepository, NodeAssociation)
    from .utils.config import check_config, load_config, save_config

    __all__ = ["load_config", "check_config", "save_config", "MemoryRepository", "MessageRepository", "MessageQueue", "Memory", "CognitiveNode", "NodeAssociation"]

# 插件元信息
__plugin_meta__ = {
    "name": "Persona",
    "description": "具有自主意识和记忆能力的智能系统",
    "usage": "自动记忆和回复群消息",
    "type": "application",
    "homepage": "https://github.com/username/ATRI_PROJ",
    "supported_adapters": {"~all"},
} 