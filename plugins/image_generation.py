"""Bot command for generating and sending images from a text prompt."""

from __future__ import annotations

import logging
import re
from typing import Optional

from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.params import CommandArg, CommandStart
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER

from src.core.domain import PersonaConfig
from src.core.domain.image_generation_error import sanitize_image_error_detail
from src.infra.llm.providers.image_generator import ImageGenerationError, ImageGenerator
from src.adapters.nonebot.command_registry import register_command


__plugin_meta__ = PluginMetadata(
    name="图像生成",
    description="根据文字描述生成并发送图片",
    usage="画一张 [描述]",
    type="application",
    supported_adapters={"~onebot.v11"},
    extra={"policy": {"manageable": False, "default_enabled": True}},
)


async def _private_slash_command(
    event: MessageEvent,
    command_start: str = CommandStart(),
) -> bool:
    """Keep image generation restricted to ``/`` commands in private chats."""
    return isinstance(event, PrivateMessageEvent) and command_start == "/"


image_generation_cmd = register_command(
    "画一张",
    aliases={"画图", "生图"},
    role="superuser",
    scope="private_only",
    permission=SUPERUSER,
    rule=_private_slash_command,
    priority=5,
    block=True,
    description="根据文字描述生成图片",
    usage="画一张 [图片描述]",
    examples=["画一张 雨夜中的赛博朋克猫", "/画一张 星空下的海边小屋"],
)

_generator: Optional[ImageGenerator] = None
_generator_config_signature: Optional[tuple[str, str, str, float, str, str, tuple[str, ...], int, bool]] = None


def _get_generator() -> tuple[ImageGenerator, bool]:
    global _generator, _generator_config_signature
    config = PersonaConfig.load("data/persona/persona.yaml").image_generation
    signature = (
        config.api_key,
        config.base_url,
        config.model,
        config.timeout_seconds,
        config.endpoint_path,
        config.reference_endpoint_path,
        tuple(config.reference_images),
        config.max_retries,
        config.enabled,
    )
    if _generator is None or signature != _generator_config_signature:
        _generator = ImageGenerator(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            endpoint_path=config.endpoint_path,
            reference_endpoint_path=config.reference_endpoint_path,
            reference_image_paths=config.reference_images,
            max_retries=config.max_retries,
        )
        _generator_config_signature = signature
    return _generator, config.enabled


def _normalize_prompt(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", str(prompt or "").strip())
    if normalized == "图":
        return ""
    return normalized


async def _handle_generation(matcher, prompt: str) -> None:
    prompt = _normalize_prompt(prompt)
    if not prompt:
        await matcher.finish("请这样使用：画一张 雨夜中的赛博朋克猫")

    try:
        generator, enabled = _get_generator()
    except Exception as exc:
        logging.error("加载图像生成配置失败: error=%s", type(exc).__name__)
        await matcher.finish("图像生成功能暂时不可用，请检查机器人配置")
        return
    if not enabled:
        await matcher.finish("图像生成功能当前未启用")
        return

    try:
        image_bytes = await generator.generate(prompt)
    except ImageGenerationError as exc:
        logging.warning("图像生成失败: %s", exc.diagnostic_summary())
        request_info = f"\n请求标识：{exc.request_id}" if exc.request_id else ""
        await matcher.finish(f"图片生成失败：{exc}{request_info}")
        return
    except Exception as exc:
        logging.error(
            "图像生成异常: error=%s detail=%s", type(exc).__name__,
            sanitize_image_error_detail(exc, (getattr(generator, "api_key", ""), prompt)),
        )
        await matcher.finish("图片生成发生异常，请检查错误日志")
        return

    await matcher.finish(MessageSegment.image(image_bytes))


@image_generation_cmd.handle()
async def handle_image_generation(args: Message = CommandArg()):
    await _handle_generation(image_generation_cmd, args.extract_plain_text())


__all__ = ["image_generation_cmd"]
