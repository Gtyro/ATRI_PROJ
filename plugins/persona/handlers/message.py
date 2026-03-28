import logging
import os

from arclet.alconna import Args, Arparma, MultiVar
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent
from nonebot.internal.params import Depends
from nonebot.permission import SUPERUSER
from nonebot_plugin_uninfo import Uninfo

from .. import psstate
from ..psstate import is_enabled
from src.adapters.nonebot.command_args import normalize_alconna_tokens
from src.adapters.nonebot.command_registry import register_alconna, register_auto_feature
from src.adapters.nonebot.message_metadata import (
    build_onebot_metadata,
    extract_onebot_image_metadata,
    extract_onebot_mention_metadata,
    normalize_content_for_storage,
)


def UserName():
    """
    用户名称依赖函数
    """

    async def dependency(user_info: Uninfo):
        return user_info.user.nick or user_info.user.name or ""

    return Depends(dependency)

# 消息记录器，处理所有接收到的消息
message_handler = on_message(priority=15)
register_auto_feature(
    "人格消息入库",
    role="superuser",
    trigger_type="message",
)
@message_handler.handle()
async def handle_message(bot: Bot, event: Event, uname: str = UserName()):
    """
    记录所有接收到的消息并处理
    """
    # 如果人格系统未启用，跳过处理
    if not is_enabled():
        return

    user_id = event.get_user_id()
    plain_text = event.get_plaintext()
    message_segments = event.get_message()
    images = extract_onebot_image_metadata(message_segments)
    mentions = extract_onebot_mention_metadata(message_segments, self_id=bot.self_id)
    message = normalize_content_for_storage(
        plain_text,
        images,
        message_segments=message_segments,
    )

    # 忽略既无文本也无图片的消息
    if not message:
        return

    # 正确区分群聊和私聊
    is_group = isinstance(event, GroupMessageEvent)
    conv_type = "group" if is_group else "private"
    # 群组ID或用户ID
    conv_id = f"{conv_type}_{event.group_id if is_group else user_id}"
    # 尝试获取群组名称（仅群聊）
    group_name = None
    if is_group:
        try:
            group_info = await bot.get_group_info(group_id=event.group_id)
            group_name = group_info.get("group_name")
        except Exception as e:
            logging.warning(f"获取群组名称失败: {e}")

        try:
            ingest_enabled = await psstate.plugin_policy_service.is_ingest_enabled(
                str(event.group_id),
                "persona",
                group_name=group_name,
            )
            if not ingest_enabled:
                logging.info(f"群组 {event.group_id} 的 persona 入库已关闭，跳过处理")
                return
        except Exception as e:
            logging.error(f"群组策略检查失败: {e}")

    # 判断直接交互（@机器人或私聊）
    is_direct = False
    if event.is_tome() or not is_group:
        is_direct = True

    # 构建消息数据
    metadata = build_onebot_metadata(
        self_id=bot.self_id,
        message_id=getattr(event, "message_id", None),
        images=images,
        mentions=mentions,
    )

    message_data = { # 此处有8个字段+自动生成的id和created_at
        "conv_id": conv_id,
        "user_id": user_id,
        "user_name": uname,
        "content": message,
        "is_direct": is_direct,
        "is_bot": False,
        "is_processed": False,
        "metadata": metadata,
    }

    # 异步处理消息
    try:
        await psstate.message_ingestor.ingest(message_data, raw_event=event)
        # 注意：此处不需要再次发送回复，因为在persona_system的process_conversation中
        # 已经调用了reply_callback函数，会自动发送回复
    except Exception as e:
        logging.error(f"消息处理异常: {e}")

parse_history = register_alconna(
    "解析历史记录",
    role="superuser",
    permission=SUPERUSER,
    priority=5,
    block=True,
    use_cmd_start=True,
    use_cmd_sep=True,
    alconna_args=[Args["group_id?", str]["file_path", MultiVar(str, "*")]],
    description="将导出的聊天记录解析为 Persona 可用数据",
    usage="解析历史记录 [群号] [文件路径]",
    examples=["解析历史记录 123456 /tmp/chat.log"],
)
@parse_history.handle()
async def handle_parse_history(bot: Bot, event: Event, arp: Arparma):
    """处理解析历史记录命令"""
    if not is_enabled():
        await parse_history.finish("人格系统未启用")

    # 获取参数
    group_id = arp.all_matched_args.get("group_id")
    file_path_parts = normalize_alconna_tokens(arp.all_matched_args.get("file_path"))
    if not group_id or not file_path_parts:
        await parse_history.finish("参数不足，格式：解析历史记录 群号 文件路径")

    group_id = str(group_id)
    file_path = " ".join(file_path_parts).strip()  # 文件路径可能包含空格

    # 验证群是否存在
    try:
        group_info = await bot.get_group_info(group_id=group_id)
        group_name = group_info["group_name"]
    except Exception as e:
        await parse_history.finish(f"获取群信息失败: {e}")
        return

    # 构造会话ID
    conv_id = f"group_{group_id}"

    # 验证文件是否存在
    if not os.path.exists(file_path):
        await parse_history.finish(f"文件不存在: {file_path}")
        return

    # 获取bot ID
    bot_id = bot.self_id

    try:
        # 调用解析函数
        messages = await psstate.persona_system.parse_chat_history(bot_id, file_path, conv_id)
    except Exception as e:
        await parse_history.finish(f"解析消息记录失败: {e}")

    if not messages:
        await parse_history.finish("解析消息记录失败或记录为空")

    # 历史导入终态：仅导入短期记忆，不自动触发记忆构建和自动回复
    await parse_history.finish(
        f"成功解析消息记录，共 {len(messages)} 条消息\n"
        f"群名称: {group_name}\n"
        f"群号: {group_id}\n"
        "说明：本命令仅导入短期记忆（消息队列），不会自动触发记忆构建，也不会立即自动回复。"
    )
