"""NapCat/OneBot 图片拉取适配。"""

from __future__ import annotations

import base64
import hashlib
import inspect
import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


logger = logging.getLogger(__name__)
BotGetter = Callable[[str], Any]
UNSUPPORTED_ACTION_CODES = {1404, 10002, 10003}
UNSUPPORTED_ACTION_KEYWORDS = (
    "unsupported",
    "not supported",
    "unknown action",
    "unknown api",
    "api not found",
    "action not found",
    "不支持",
    "未实现",
    "接口不存在",
    "动作不存在",
)


@dataclass(frozen=True)
class ResolvedImage:
    source: str
    mime: str
    image_bytes: bytes
    original_url: str = ""


def _mask_identifier(raw: str, *, keep: int = 4) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if len(value) <= 2:
        return "*" * len(value)

    safe_keep = max(1, min(keep, (len(value) - 1) // 2))
    masked_len = max(1, len(value) - (safe_keep * 2))
    return f"{value[:safe_keep]}{'*' * masked_len}{value[-safe_keep:]}"


def _mask_url(raw: str) -> str:
    return _mask_identifier(raw, keep=8)


def _mask_file(raw: str) -> str:
    return _mask_identifier(raw, keep=6)


def _base64_digest_prefix(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


class NapcatImageResolver:
    """优先 URL 拉取，失败后尝试 get_image/get_file 与本地路径兜底。"""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        *,
        bot_getter: Optional[BotGetter] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._bot_getter: BotGetter = bot_getter or self._default_bot_getter
        self._bot_cache: Dict[str, Any] = {}
        self._unsupported_action_cache: Dict[str, set[str]] = {}

    async def resolve(
        self,
        *,
        conv_id: str,
        message_id: Any,
        image_meta: Dict[str, Any],
        onebot_self_id: str = "",
    ) -> Optional[ResolvedImage]:
        url = str(image_meta.get("url") or "").strip()
        if url:
            image = await self._resolve_by_url(url, image_meta=image_meta)
            if image is not None:
                return image

        file = str(image_meta.get("file") or "").strip()
        file_id = str(image_meta.get("file_id") or "").strip()
        onebot_self_id = str(onebot_self_id or "").strip()
        bot: Any = None
        bot_resolved = False

        def _get_bot() -> Any:
            nonlocal bot, bot_resolved
            if bot_resolved:
                return bot
            bot = self._resolve_bot(
                conv_id=conv_id,
                message_id=message_id,
                onebot_self_id=onebot_self_id,
            )
            bot_resolved = True
            return bot

        if file:
            image = await self._resolve_by_get_image(
                conv_id=conv_id,
                message_id=message_id,
                file=file,
                image_meta=image_meta,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
            )
            if image is not None:
                return image

        if file_id:
            image = await self._resolve_by_get_file(
                conv_id=conv_id,
                message_id=message_id,
                image_meta=image_meta,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
                source="get_file_by_file_id",
                file_id=file_id,
            )
            if image is not None:
                return image

        if file:
            image = await self._resolve_by_get_file(
                conv_id=conv_id,
                message_id=message_id,
                image_meta=image_meta,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
                source="get_file_by_file",
                file=file,
            )
            if image is not None:
                return image

        if file_id:
            return await self._resolve_by_file_id_local_path(
                conv_id=conv_id,
                message_id=message_id,
                file_id=file_id,
                image_meta=image_meta,
                bot=bot if bot_resolved else None,
            )
        return None

    async def _resolve_by_url(
        self,
        url: str,
        *,
        image_meta: Dict[str, Any],
        source: str = "url",
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
                source=source,
                mime=mime,
                image_bytes=response.content,
                original_url=url,
            )
        except ImportError:
            logger.warning("图片 URL 拉取失败：缺少 httpx 依赖")
            return None
        except Exception as exc:
            logger.warning(
                "图片 URL 拉取失败: url=%s error=%s",
                _mask_url(url),
                type(exc).__name__,
            )
            return None

    async def _resolve_by_get_image(
        self,
        *,
        conv_id: str,
        message_id: Any,
        file: str,
        image_meta: Dict[str, Any],
        bot: Any = None,
        bot_self_id: str = "",
    ) -> Optional[ResolvedImage]:
        if bot is None:
            return None
        response = await self._call_bot_api(
            bot=bot,
            bot_self_id=bot_self_id,
            action="get_image",
            conv_id=conv_id,
            message_id=message_id,
            file=file,
        )
        payload = self._unwrap_bot_payload(response)
        if not isinstance(payload, dict):
            return None

        url = str(payload.get("url") or "").strip()
        if url:
            image = await self._resolve_by_url(url, image_meta=image_meta, source="get_image")
            if image is not None:
                return image

        local_path = self._resolve_local_path_from_file_id(str(payload.get("file") or payload.get("path") or ""))
        if not local_path:
            return None
        return self._read_local_image(local_path, image_meta=image_meta, source="get_image")

    async def _resolve_by_get_file(
        self,
        *,
        conv_id: str,
        message_id: Any,
        image_meta: Dict[str, Any],
        bot: Any = None,
        bot_self_id: str = "",
        source: str,
        **params: Any,
    ) -> Optional[ResolvedImage]:
        if bot is None:
            return None
        response = await self._call_bot_api(
            bot=bot,
            bot_self_id=bot_self_id,
            action="get_file",
            conv_id=conv_id,
            message_id=message_id,
            **params,
        )
        payload = self._unwrap_bot_payload(response)
        if not isinstance(payload, dict):
            return None

        image_bytes = self._decode_base64_image_from_payload(
            payload,
            conv_id=conv_id,
            message_id=message_id,
            source=source,
        )
        if image_bytes is not None:
            return ResolvedImage(
                source=source,
                mime=self._resolve_mime_type(image_meta=image_meta, payload=payload),
                image_bytes=image_bytes,
                original_url="",
            )

        url = str(payload.get("url") or "").strip()
        if url:
            image = await self._resolve_by_url(url, image_meta=image_meta, source=source)
            if image is not None:
                return image

        local_path = self._resolve_local_path_from_file_id(str(payload.get("path") or payload.get("file") or ""))
        if not local_path:
            return None
        return self._read_local_image(local_path, image_meta=image_meta, source=source)

    async def _resolve_by_file_id_local_path(
        self,
        *,
        conv_id: str,
        message_id: Any,
        file_id: str,
        image_meta: Dict[str, Any],
        bot: Any = None,
    ) -> Optional[ResolvedImage]:
        # 当前版本无法直接通过 OneBot/NapCat file_id API 拉取时，记录 warning 并降级尝试本地路径。
        logger.warning(
            "触发 file_id 兜底路径: conv_id=%s message_id=%s file_id=%s bot_available=%s file_id_fallback_warning=1",
            conv_id,
            message_id,
            _mask_identifier(file_id),
            1 if bot is not None else 0,
        )
        local_path = self._resolve_local_path_from_file_id(file_id)
        if not local_path:
            return None

        return self._read_local_image(local_path, image_meta=image_meta, source="file_id_local_path")

    @staticmethod
    def _read_local_image(
        local_path: str,
        *,
        image_meta: Dict[str, Any],
        source: str,
    ) -> Optional[ResolvedImage]:
        try:
            with open(local_path, "rb") as f:
                image_bytes = f.read()
            mime = (
                str(image_meta.get("mime") or "").strip()
                or mimetypes.guess_type(local_path)[0]
                or "image/jpeg"
            )
            return ResolvedImage(
                source=source,
                mime=mime,
                image_bytes=image_bytes,
                original_url="",
            )
        except Exception as exc:
            logger.warning(
                "图片本地路径拉取失败: path=%s source=%s error=%s",
                _mask_file(local_path),
                source,
                type(exc).__name__,
            )
            return None

    @staticmethod
    def _resolve_local_path_from_file_id(file_id: str) -> str:
        if file_id.startswith("file://"):
            path = file_id[len("file://") :]
            return path if os.path.isfile(path) else ""
        if os.path.isabs(file_id) and os.path.isfile(file_id):
            return file_id
        return ""

    @staticmethod
    def _resolve_mime_type(
        *,
        image_meta: Dict[str, Any],
        payload: Optional[Dict[str, Any]] = None,
        local_path: str = "",
    ) -> str:
        payload = payload or {}
        return (
            str(payload.get("mime") or payload.get("mimetype") or payload.get("content_type") or "").strip()
            or str(image_meta.get("mime") or "").strip()
            or mimetypes.guess_type(local_path)[0]
            or "image/jpeg"
        )

    @staticmethod
    def _decode_base64_image_from_payload(
        payload: Dict[str, Any],
        *,
        conv_id: str,
        message_id: Any,
        source: str,
    ) -> Optional[bytes]:
        for key in ("base64", "file_base64", "data", "file_data", "content"):
            value = payload.get(key)
            if isinstance(value, (bytes, bytearray)):
                return bytes(value)
            if not isinstance(value, str):
                continue
            raw = value.strip()
            if not raw:
                continue
            if raw.startswith("base64://"):
                raw = raw[len("base64://") :]
            try:
                return base64.b64decode(raw, validate=True)
            except Exception:
                try:
                    padded = raw + ("=" * (-len(raw) % 4))
                    return base64.b64decode(padded, validate=False)
                except Exception as exc:
                    logger.warning(
                        "get_file base64 解码失败，改走 url/path: conv_id=%s message_id=%s source=%s "
                        "payload_key=%s base64_length=%s base64_sha256_prefix=%s error=%s",
                        conv_id,
                        message_id,
                        source,
                        key,
                        len(raw),
                        _base64_digest_prefix(raw),
                        type(exc).__name__,
                    )
        return None

    @staticmethod
    def _default_bot_getter(self_id: str) -> Any:
        import nonebot

        return nonebot.get_bot(self_id)

    async def _call_bot_api(
        self,
        *,
        bot: Any,
        bot_self_id: str,
        action: str,
        conv_id: str,
        message_id: Any,
        **params: Any,
    ) -> Any:
        cache_key = self._bot_action_cache_key(bot=bot, bot_self_id=bot_self_id)
        if self._is_action_marked_unsupported(cache_key=cache_key, action=action):
            logger.info(
                "OneBot 图片 API 能力不可用(已缓存)，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s",
                conv_id,
                message_id,
                action,
                _mask_identifier(bot_self_id),
            )
            return None

        method = getattr(bot, action, None)
        call_api = getattr(bot, "call_api", None)
        if not callable(method) and not callable(call_api):
            self._mark_action_unsupported(cache_key=cache_key, action=action)
            logger.info(
                "OneBot 图片 API 能力不可用，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s reason=no_callable_api",
                conv_id,
                message_id,
                action,
                _mask_identifier(bot_self_id),
            )
            return None

        try:
            if callable(method):
                response = await NapcatImageResolver._await_if_needed(method(**params))
                if self._is_unsupported_action_response(response):
                    self._mark_action_unsupported(cache_key=cache_key, action=action)
                    logger.info(
                        "OneBot 图片 API 返回不支持，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s",
                        conv_id,
                        message_id,
                        action,
                        _mask_identifier(bot_self_id),
                    )
                    return None
                return response
            if callable(call_api):
                response = await NapcatImageResolver._await_if_needed(call_api(action, **params))
                if self._is_unsupported_action_response(response):
                    self._mark_action_unsupported(cache_key=cache_key, action=action)
                    logger.info(
                        "OneBot 图片 API 返回不支持，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s",
                        conv_id,
                        message_id,
                        action,
                        _mask_identifier(bot_self_id),
                    )
                    return None
                return response
        except Exception as exc:
            if self._is_unsupported_action_error(exc):
                self._mark_action_unsupported(cache_key=cache_key, action=action)
                logger.info(
                    "OneBot 图片 API 不支持该动作，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s error=%s",
                    conv_id,
                    message_id,
                    action,
                    _mask_identifier(bot_self_id),
                    type(exc).__name__,
                )
                return None
            logger.warning(
                "调用 OneBot 图片 API 失败，跳过该分支: conv_id=%s message_id=%s action=%s error=%s",
                conv_id,
                message_id,
                action,
                type(exc).__name__,
            )
            return None
        return None

    @staticmethod
    def _bot_action_cache_key(*, bot: Any, bot_self_id: str) -> str:
        self_id = str(bot_self_id or "").strip()
        if self_id:
            return self_id
        return f"bot:{id(bot)}"

    def _is_action_marked_unsupported(self, *, cache_key: str, action: str) -> bool:
        return action in self._unsupported_action_cache.get(cache_key, set())

    def _mark_action_unsupported(self, *, cache_key: str, action: str) -> None:
        if not cache_key:
            return
        action_set = self._unsupported_action_cache.setdefault(cache_key, set())
        action_set.add(action)

    @classmethod
    def _is_unsupported_action_response(cls, response: Any) -> bool:
        if not isinstance(response, dict):
            return False
        raw_status = response.get("status")
        status = str(raw_status).strip().lower() if raw_status is not None else ""
        retcode = cls._coerce_int(response.get("retcode"))
        message = cls._coerce_message(response)
        unsupported_code = retcode in UNSUPPORTED_ACTION_CODES if retcode is not None else False
        unsupported_message = cls._contains_unsupported_hint(message)
        if not unsupported_code and not unsupported_message:
            return False
        if not status:
            return True
        return status in {"failed", "fail", "error"}

    @classmethod
    def _is_unsupported_action_error(cls, exc: Exception) -> bool:
        messages = [str(exc)]
        codes = []
        cls._collect_hints_from_object(getattr(exc, "info", None), messages=messages, codes=codes)
        for attr in ("retcode", "code", "status", "status_code"):
            value = cls._coerce_int(getattr(exc, attr, None))
            if value is not None:
                codes.append(value)
        for arg in getattr(exc, "args", ()):
            cls._collect_hints_from_object(arg, messages=messages, codes=codes)
        if any(code in UNSUPPORTED_ACTION_CODES for code in codes):
            return True
        return any(cls._contains_unsupported_hint(message) for message in messages if message)

    @classmethod
    def _collect_hints_from_object(cls, value: Any, *, messages: list[str], codes: list[int]) -> None:
        if isinstance(value, dict):
            for key in ("msg", "message", "wording", "detail", "error"):
                raw = value.get(key)
                if isinstance(raw, str):
                    messages.append(raw)
            for key in ("retcode", "code", "status", "status_code"):
                raw = cls._coerce_int(value.get(key))
                if raw is not None:
                    codes.append(raw)
        elif isinstance(value, str):
            messages.append(value)
        elif value is not None:
            rendered = str(value)
            if rendered:
                messages.append(rendered)

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_message(payload: Dict[str, Any]) -> str:
        for key in ("msg", "message", "wording", "detail", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    @staticmethod
    def _contains_unsupported_hint(message: str) -> bool:
        text = str(message or "").strip().lower()
        if not text:
            return False
        return any(keyword in text for keyword in UNSUPPORTED_ACTION_KEYWORDS)

    @staticmethod
    async def _await_if_needed(result: Any) -> Any:
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def _unwrap_bot_payload(response: Any) -> Any:
        if isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, dict):
                return data
        return response

    def _resolve_bot(
        self,
        *,
        conv_id: str,
        message_id: Any,
        onebot_self_id: str,
    ) -> Any:
        self_id = str(onebot_self_id or "").strip()
        if not self_id:
            return None
        if self_id in self._bot_cache:
            return self._bot_cache[self_id]
        try:
            bot = self._bot_getter(self_id)
        except Exception as exc:
            logger.warning(
                "图片 resolver 获取 bot 失败，跳过 OneBot 兜底分支: conv_id=%s message_id=%s self_id=%s error=%s",
                conv_id,
                message_id,
                _mask_identifier(self_id),
                type(exc).__name__,
            )
            return None
        self._bot_cache[self_id] = bot
        return bot
