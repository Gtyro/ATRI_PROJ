"""NapCat/OneBot 图片拉取适配。"""

from __future__ import annotations

import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedImage:
    source: str
    mime: str
    image_bytes: bytes
    original_url: str = ""


def _mask_identifier(raw: str, *, keep: int = 4) -> str:
    value = str(raw or "")
    if len(value) <= keep * 2:
        return value
    return f"{value[:keep]}***{value[-keep:]}"


class NapcatImageResolver:
    """优先 URL 拉取，失败后 file_id 兜底。"""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def resolve(
        self,
        *,
        conv_id: str,
        message_id: Any,
        image_meta: Dict[str, Any],
    ) -> Optional[ResolvedImage]:
        url = str(image_meta.get("url") or "").strip()
        if url:
            image = await self._resolve_by_url(url, image_meta=image_meta)
            if image is not None:
                return image

        file_id = str(image_meta.get("file_id") or "").strip()
        if file_id:
            return await self._resolve_by_file_id(
                conv_id=conv_id,
                message_id=message_id,
                file_id=file_id,
                image_meta=image_meta,
            )
        return None

    async def _resolve_by_url(
        self,
        url: str,
        *,
        image_meta: Dict[str, Any],
    ) -> Optional[ResolvedImage]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            mime = (
                response.headers.get("content-type")
                or str(image_meta.get("mime") or "").strip()
                or "image/jpeg"
            )
            return ResolvedImage(
                source="url",
                mime=mime,
                image_bytes=response.content,
                original_url=url,
            )
        except ImportError:
            logger.warning("图片 URL 拉取失败：缺少 httpx 依赖")
            return None
        except Exception as exc:
            logger.warning("图片 URL 拉取失败，准备尝试 file_id 兜底: url=%s error=%s", url, exc)
            return None

    async def _resolve_by_file_id(
        self,
        *,
        conv_id: str,
        message_id: Any,
        file_id: str,
        image_meta: Dict[str, Any],
    ) -> Optional[ResolvedImage]:
        # 当前版本无法直接通过 OneBot/NapCat file_id API 拉取时，记录 warning 并降级尝试本地路径。
        logger.warning(
            "触发 file_id 兜底路径: conv_id=%s message_id=%s file_id=%s file_id_fallback_warning=1",
            conv_id,
            message_id,
            _mask_identifier(file_id),
        )
        local_path = self._resolve_local_path_from_file_id(file_id)
        if not local_path:
            return None

        try:
            with open(local_path, "rb") as f:
                image_bytes = f.read()
            mime = (
                str(image_meta.get("mime") or "").strip()
                or mimetypes.guess_type(local_path)[0]
                or "image/jpeg"
            )
            return ResolvedImage(
                source="file_id",
                mime=mime,
                image_bytes=image_bytes,
                original_url="",
            )
        except Exception as exc:
            logger.warning("file_id 本地路径拉取失败: path=%s error=%s", local_path, exc)
            return None

    @staticmethod
    def _resolve_local_path_from_file_id(file_id: str) -> str:
        if file_id.startswith("file://"):
            path = file_id[len("file://") :]
            return path if os.path.isfile(path) else ""
        if os.path.isabs(file_id) and os.path.isfile(file_id):
            return file_id
        return ""
