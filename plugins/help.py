from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER

# 注册帮助命令处理器
help_cmd = on_command("帮助", aliases={"help", "菜单", "功能"},permission=SUPERUSER,rule=to_me(), priority=1, block=True)

help_text = """
📋 机器人功能菜单 📋
------------------------
🔹 基础命令：
  - 你好/hello/hi：问候语
  - 帮助/help/菜单：显示本菜单

🔹 实用工具：
  - 天气 [城市]：查询指定城市天气

🔹 管理命令（管理员专属）：
  - 系统状态/status：查看系统资源使用情况

🔹 更多功能正在开发中...

使用方法示例：
发送 "天气 北京" 查询北京的天气
"""
@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    await help_cmd.finish(help_text) 