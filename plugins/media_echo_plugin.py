"""
媒体消息识图插件
功能：
1. 识别来自超级用户的 @ 图片消息
2. 调用 Gemini 多模态模型分析图片内容
3. 回复“图像试图展示什么信息”
"""

import base64
import logging
import mimetypes
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from nonebot import on_message
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me
from nonebot_plugin_alconna import Image, UniMessage, UniMsg

from src.adapters.nonebot.command_registry import register_alconna, register_auto_feature
from src.infra.llm.providers.client import LLMClient
from src.infra.llm.providers.errors import LLMProviderError
from src.infra.llm.providers.types import LLMCallParams

__plugin_meta__ = PluginMetadata(
    name="媒体识图插件",
    description="处理超级用户发送的图片消息，调用多模态模型生成图像意图描述",
    usage="发送图片并@机器人即可触发",
    extra={
        "policy": {
            "manageable": False,
        }
    },
)

logger = logging.getLogger(__name__)

register_auto_feature(
    "媒体消息识图",
    role="superuser",
    trigger_type="message",
)

# 参考 zhenxun_bot 的 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) "
    "AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:38.0) Gecko/20100101 Firefox/38.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0) "
    "AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11",
    "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
    "Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
]


def get_user_agent() -> dict[str, str]:
    """获取随机 User-Agent，参考 zhenxun_bot 的实现"""
    return {"User-Agent": random.choice(USER_AGENTS)}

@dataclass(frozen=True)
class ImageLLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    max_tokens: int


def load_image_config(path: str = "data/image.yaml") -> ImageLLMConfig:
    data: dict[str, Any] = {}
    config_path = Path(path)
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
                if isinstance(raw, dict):
                    data = raw
        except Exception as exc:
            logger.error("加载图片识图配置失败: %s", exc)
    else:
        logger.warning("图片识图配置文件不存在: %s", path)

    api_key = str(
        os.environ.get("OPENROUTER_API_KEY")
        or data.get("openrouter_apikey")
        or data.get("api_key")
        or ""
    ).strip()
    base_url = str(
        os.environ.get("OPENROUTER_BASE_URL")
        or data.get("openrouter_base_url")
        or data.get("base_url")
        or "https://openrouter.ai/api/v1"
    ).strip()
    model = str(
        os.environ.get("OPENROUTER_MODEL")
        or data.get("openrouter_model")
        or data.get("model")
        or "google/gemini-3-pro-preview"
    ).strip()
    timeout_seconds = float(data.get("timeout_seconds", 60))
    max_tokens = int(data.get("max_tokens", 300))

    return ImageLLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
    )


async def download_media_content(url: str) -> bytes | None:
    """
    下载媒体内容的完整字节数据
    参考 zhenxun_bot 的下载实现，为将来的 AI 分析功能做准备

    参数:
        url: 媒体资源的 URL

    返回:
        bytes | None: 媒体内容的字节数据，失败时返回 None
    """
    try:
        headers = get_user_agent()

        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            logger.info(f"成功下载媒体内容: {len(response.content)} 字节")
            return response.content

    except Exception as e:
        logger.error(f"下载媒体内容失败: {e}")
        return None


def _coerce_bytes(raw: Any) -> bytes | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if hasattr(raw, "read"):
        try:
            value = raw.read()
            return value if isinstance(value, bytes) else None
        except Exception:
            return None
    return None


def _guess_mime_type(image_segment: Image) -> str:
    for field_name in ("mimetype", "mime_type", "type"):
        value = getattr(image_segment, field_name, None)
        if isinstance(value, str) and value.startswith("image/"):
            return value

    for field_name in ("name", "path", "url"):
        value = getattr(image_segment, field_name, None)
        if not value:
            continue
        guessed, _ = mimetypes.guess_type(str(value))
        if guessed and guessed.startswith("image/"):
            return guessed
    return "image/jpeg"


async def _image_segment_to_llm_content(image_segment: Image) -> dict[str, Any] | None:
    raw = _coerce_bytes(getattr(image_segment, "raw", None))
    if raw:
        mime_type = _guess_mime_type(image_segment)
        b64 = base64.b64encode(raw).decode("utf-8")
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}

    path_value = getattr(image_segment, "path", None)
    if path_value:
        path = Path(str(path_value))
        if path.exists() and path.is_file():
            try:
                raw = path.read_bytes()
                mime_type = _guess_mime_type(image_segment)
                b64 = base64.b64encode(raw).decode("utf-8")
                return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
            except Exception as exc:
                logger.warning("读取本地图片失败: %s", exc)

    url = getattr(image_segment, "url", None)
    if url:
        url_str = str(url)
        media_content = await download_media_content(url_str)
        if media_content:
            mime_type = _guess_mime_type(image_segment)
            b64 = base64.b64encode(media_content).decode("utf-8")
            return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
        return {"type": "image_url", "image_url": {"url": url_str}}

    return None


_llm_config: ImageLLMConfig | None = None
_llm_client: LLMClient | None = None


def _get_llm_client() -> LLMClient:
    global _llm_config, _llm_client
    if _llm_config is None:
        _llm_config = load_image_config()
    if _llm_client is None:
        if not _llm_config.api_key:
            raise RuntimeError("未配置 OpenRouter API Key，请在 data/image.yaml 设置 openrouter_apikey")
        _llm_client = LLMClient(
            api_key=_llm_config.api_key,
            base_url=_llm_config.base_url,
            model=_llm_config.model,
            provider_name="openrouter_image",
            timeout=_llm_config.timeout_seconds,
        )
    return _llm_client


async def _describe_images(image_contents: list[dict[str, Any]]) -> str:
    if not image_contents:
        return ""

    client = _get_llm_client()
    if _llm_config is None:
        raise RuntimeError("图片识图配置初始化失败")

    prompt = (
        "请用简体中文回答：这些图像试图展示什么信息？"
        "给出1-2句简洁描述，不要输出额外前后缀。"
    )
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}, *image_contents],
        }
    ]
    params = LLMCallParams(
        temperature=0.2,
        max_tokens=_llm_config.max_tokens,
    )
    last_exc: LLMProviderError | None = None
    for attempt in range(2):
        try:
            return (await client.chat(messages, params=params, operation="image_understanding")).strip()
        except LLMProviderError as exc:
            last_exc = exc
            logger.warning("图像理解请求失败，准备重试: attempt=%s error=%s", attempt + 1, exc)

    if last_exc is not None:
        raise last_exc
    return ""


def _extract_images(message: UniMsg) -> list[Image]:
    images: list[Image] = []
    for segment in message:
        if isinstance(segment, Image):
            images.append(segment)
    return images


# 创建消息响应器，只响应超级用户的消息
media_matcher = on_message(
    permission=SUPERUSER,
    rule=to_me(),
    priority=10,
    block=False
)


@media_matcher.handle()
async def handle_media_message(bot: Bot, event: Event, message: UniMsg):
    """
    处理包含图片的消息，调用多模态模型返回图像意图
    """
    images = _extract_images(message)
    if not images:
        return

    try:
        image_contents: list[dict[str, Any]] = []
        for image_segment in images[:3]:
            content = await _image_segment_to_llm_content(image_segment)
            if content:
                image_contents.append(content)

        if not image_contents:
            await UniMessage("❌ 未能读取图片内容，无法识图").send()
            return

        result = await _describe_images(image_contents)
        if not result:
            result = "我暂时无法判断图像意图。"
        await UniMessage(f"图像试图展示：{result}").send()
    except Exception as e:
        logger.exception("图像理解失败: %s", e)
        await UniMessage("图像试图展示：我暂时无法判断图像意图，请稍后重试。").send()


# 可选：添加一个命令来测试插件是否工作
test_matcher = register_alconna(
    "媒体插件测试",
    role="superuser",
    permission=SUPERUSER,
    priority=5,
    block=True,
)

@test_matcher.handle()
async def test_plugin():
    """测试插件是否正常工作"""
    await UniMessage("✅ 媒体识图插件正常工作！\n发送图片并 @ 我即可触发。").send()
