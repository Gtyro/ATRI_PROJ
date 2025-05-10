"""
人格系统全局状态管理模块
"""

# 全局变量
persona_system = None
PERSONA_SYSTEM_ENABLED = False

def is_enabled():
    return PERSONA_SYSTEM_ENABLED