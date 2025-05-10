"""人格系统命令处理器包"""

# 从各个模块导入处理器，方便主文件一次性导入
from .message import message_handler
from .memory import memories, remember_permanent
from .management import process_now, persona_stats, switch_persona
from .test import test_persona

# 如果需要，也可以导出处理函数
from .message import handle_message
from .memory import handle_memories, handle_remember_permanent
from .management import handle_process_now, handle_persona_stats, handle_switch_persona
from .test import handle_test_persona

# 定义__all__列表，控制from handlers import *时导入的内容
__all__ = [
    "message_handler", 
    "memories", "remember_permanent",
    "process_now", "persona_stats", "switch_persona",
    "test_persona"
]