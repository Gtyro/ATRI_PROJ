import logging

from nonebot import get_driver, on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.exception import MatcherException
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State

from .. import psstate
from ..psstate import is_enabled

# 设置拟人测试指令
test_persona = on_command("测试", aliases={"测试人格"}, permission=SUPERUSER, rule=to_me(), priority=5, block=True)
@test_persona.handle()
async def handle_test_persona(bot: Bot, event: Event):
    """测试拟人回复，对某个群组进行模拟处理，返回回复内容给超级用户"""
    # 如果系统未启用，返回错误信息
    if not is_enabled():
        await test_persona.finish("人格系统未启用，请检查配置和日志")

    # 解析参数获取群号和可选的测试消息
    args = str(event.get_plaintext()).strip().split(maxsplit=2)
    if len(args) < 2:
        await test_persona.finish("格式错误，正确格式：测试 [群号] [消息]，消息是可选的")

    group_id = args[1]
    if not group_id.isdigit():
        await test_persona.finish("群号格式不正确")

    # 构造会话ID
    conv_id = f"group_{group_id}"

    # 检查是否有测试消息
    test_message = args[2] if len(args) > 2 else None

    try:
        # 提示开始生成回复
        if test_message:
            await test_persona.send(f"正在为群 {group_id} 使用测试消息「{test_message}」生成模拟回复...")
        else:
            await test_persona.send(f"正在为群 {group_id} 生成模拟回复...")

        # 调用simulate_reply生成回复，直接传入测试消息
        reply_data = await psstate.persona_system.simulate_reply(conv_id, test_message)

        # 处理回复结果
        if reply_data and "reply_content" in reply_data:
            reply_content = reply_data["reply_content"]
            if reply_content:
                await test_persona.send(reply_content)
            else:
                await test_persona.finish("生成的回复内容为空")
        else:
            await test_persona.finish("模拟回复失败，请检查日志")
    except Exception as e:
        logging.error(f"测试人格回复异常: {e}")
        await test_persona.finish(f"模拟回复出错: {str(e)}")