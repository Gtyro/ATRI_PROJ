"""将 Persona 回复发送到对应的群聊或私聊。"""

import asyncio
import logging
import random

from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError
from nonebot_plugin_alconna.uniseg import Target, UniMessage

from src.core.domain.image_generation_error import sanitize_image_error_detail

from .message_metadata import extract_onebot_sent_message_ids


def _send_error_detail(exc: Exception) -> str:
    if isinstance(exc, ActionFailed):
        # Keep platform diagnostics, never dump data containing the sent image.
        return " ".join(
            f"{key}={sanitize_image_error_detail(exc.info[key])}"
            for key in ("status", "retcode", "message", "wording")
            if isinstance(exc.info.get(key), (str, int))
        )
    if isinstance(exc, NetworkError):
        return sanitize_image_error_detail(exc.msg)
    return type(exc).__name__


async def persona_callback(conv_id: str, message_dict: dict) -> list[str]:
    """发送人格回复并返回去重后的平台消息 ID。"""
    sent_message_ids: list[str] = []
    try:
        target = Target(
            id=conv_id.split("_", 1)[1],
            private=conv_id.startswith("private_"),
        )
        if message_dict:
            for image in message_dict.get("images", []):
                try:
                    receipt = await UniMessage.image(raw=image).send(target)
                except Exception as exc:
                    logging.error(
                        "Persona 图片发送失败: conv_id=%s error=%s detail=%s",
                        conv_id, type(exc).__name__, _send_error_detail(exc),
                    )
                    reason = (
                        "图片画好了，但没连上消息服务，稍后再试吧。"
                        if isinstance(exc, NetworkError)
                        else "图片画好了，但没能发出去，需要检查发送日志。"
                    )
                    receipt = await UniMessage(reason).send(target)
                    sent_message_ids.extend(extract_onebot_sent_message_ids(receipt))
                    return list(dict.fromkeys(sent_message_ids))
                sent_message_ids.extend(extract_onebot_sent_message_ids(receipt))
                logging.info("Persona 图片已发送: conv_id=%s", conv_id)

            reply_content = message_dict.get("reply_content", "")

            if isinstance(reply_content, list):
                for reply in reply_content:
                    reply = str(reply).strip()
                    if not reply:
                        continue
                    receipt = await UniMessage(reply).send(target)
                    sent_message_ids.extend(extract_onebot_sent_message_ids(receipt))
                    # 多条消息之间添加随机间隔，模拟真人打字速度。
                    sleep_time = random.uniform(0.5 * len(reply), len(reply))
                    await asyncio.sleep(sleep_time)
            else:
                reply_content = str(reply_content).strip()
                if not reply_content:
                    return sent_message_ids
                receipt = await UniMessage(reply_content).send(target)
                sent_message_ids.extend(extract_onebot_sent_message_ids(receipt))
    except Exception as exc:
        logging.error(
            "Persona 回复发送失败: conv_id=%s error=%s detail=%s",
            conv_id, type(exc).__name__, _send_error_detail(exc),
        )
    return list(dict.fromkeys(sent_message_ids))
