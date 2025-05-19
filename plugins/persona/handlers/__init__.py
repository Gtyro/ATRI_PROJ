"""人格系统命令处理器包"""

# 从各个模块导入处理器，方便主文件一次性导入
from .management import (handle_persona_stats, handle_process_now,
                         handle_switch_persona, persona_stats, process_now,
                         switch_persona)
from .memory import (handle_memories, handle_remember_permanent, memories,
                     remember_permanent)
# 如果需要，也可以导出处理函数
from .message import handle_message, message_handler
from .test import handle_test_persona, test_persona

# 定义__all__列表，控制from handlers import *时导入的内容
__all__ = [
    "message_handler",
    "memories", "remember_permanent",
    "process_now", "persona_stats", "switch_persona",
    "test_persona"
]