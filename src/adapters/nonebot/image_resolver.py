"""NapCat/OneBot 图片拉取适配。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
NETWORK_ERROR_HINTS = (
    "dns",
    "name resolution",
    "connection",
    "network",
    "socket",
    "broken pipe",
    "connection reset",
    "connection refused",
)
ERROR_CATEGORY_KEYS = (
    "4xx",
    "5xx",
    "timeout",
    "network",
    "dependency_missing",
    "unsupported_action",
)
RETRYABLE_ERROR_CATEGORIES = {"5xx", "timeout", "network"}
BRANCH_URL_FETCH = "url_fetch"
BRANCH_GET_IMAGE_API = "get_image_api"
BRANCH_GET_FILE_API = "get_file_api"
BRANCH_REFRESH_NC_GET_RKEY = "refresh_nc_get_rkey"
BRANCH_REFRESH_GET_MSG = "refresh_get_msg"


@dataclass(frozen=True)
class ResolvedImage:
    source: str
    mime: str
    image_bytes: bytes
    original_url: str = ""


@dataclass(frozen=True)
class BranchBudget:
    timeout_seconds: float
    max_retries: int = 0


@dataclass
class _ResolveAttemptState:
    error_category_count: Dict[str, int] = field(default_factory=dict)
    retry_count_by_branch: Dict[str, int] = field(default_factory=dict)


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
        branch_budgets: Optional[Mapping[str, Mapping[str, Any] | BranchBudget]] = None,
    ) -> None:
        base_timeout = max(0.1, float(timeout_seconds))
        self.timeout_seconds = base_timeout
        self._bot_getter: BotGetter = bot_getter or self._default_bot_getter
        self._bot_cache: Dict[str, Any] = {}
        self._unsupported_action_cache: Dict[str, set[str]] = {}
        self._default_branch_budget = BranchBudget(timeout_seconds=base_timeout, max_retries=0)
        self._branch_budgets = self._build_branch_budgets(branch_budgets)

    async def resolve(
        self,
        *,
        conv_id: str,
        message_id: Any,
        image_meta: Dict[str, Any],
        onebot_self_id: str = "",
        onebot_message_id: str = "",
        telemetry: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResolvedImage]:
        state = _ResolveAttemptState()

        def _finalize(result: Optional[ResolvedImage]) -> Optional[ResolvedImage]:
            if telemetry is not None:
                telemetry["error_category_count"] = dict(state.error_category_count)
                telemetry["retry_count_by_branch"] = dict(state.retry_count_by_branch)
            return result

        url = str(image_meta.get("url") or "").strip()
        if url:
            image = await self._resolve_by_url(url, image_meta=image_meta, state=state)
            if image is not None:
                return _finalize(image)

        file = str(image_meta.get("file") or "").strip()
        file_id = str(image_meta.get("file_id") or "").strip()
        onebot_self_id = str(onebot_self_id or "").strip()
        onebot_message_id = str(onebot_message_id or "").strip()
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

        if url and onebot_message_id:
            image = await self._resolve_by_refreshed_url(
                conv_id=conv_id,
                message_id=message_id,
                image_meta=image_meta,
                url=url,
                file=file,
                file_id=file_id,
                onebot_message_id=onebot_message_id,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
                state=state,
            )
            if image is not None:
                return _finalize(image)

        if file:
            image = await self._resolve_by_get_image(
                conv_id=conv_id,
                message_id=message_id,
                file=file,
                image_meta=image_meta,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
                state=state,
            )
            if image is not None:
                return _finalize(image)

        if file_id:
            image = await self._resolve_by_get_file(
                conv_id=conv_id,
                message_id=message_id,
                image_meta=image_meta,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
                source="get_file_by_file_id",
                file_id=file_id,
                state=state,
            )
            if image is not None:
                return _finalize(image)

        if file:
            image = await self._resolve_by_get_file(
                conv_id=conv_id,
                message_id=message_id,
                image_meta=image_meta,
                bot=_get_bot(),
                bot_self_id=onebot_self_id,
                source="get_file_by_file",
                file=file,
                state=state,
            )
            if image is not None:
                return _finalize(image)

        if file_id:
            image = await self._resolve_by_file_id_local_path(
                conv_id=conv_id,
                message_id=message_id,
                file_id=file_id,
                image_meta=image_meta,
                bot=bot if bot_resolved else None,
            )
            return _finalize(image)
        return _finalize(None)

    async def _resolve_by_url(
        self,
        url: str,
        *,
        image_meta: Dict[str, Any],
        source: str = "url",
        state: Optional[_ResolveAttemptState] = None,
    ) -> Optional[ResolvedImage]:
        budget = self._resolve_branch_budget(BRANCH_URL_FETCH)
        for attempt in range(1, budget.max_retries + 2):
            try:
                import httpx

                async with httpx.AsyncClient(timeout=budget.timeout_seconds, follow_redirects=True) as client:
                    response = await asyncio.wait_for(client.get(url), timeout=budget.timeout_seconds)
                status_code = self._coerce_int(getattr(response, "status_code", None))
                status_category = self._classify_http_status_code(status_code)
                if status_category:
                    self._record_error_category(state=state, category=status_category)
                    should_retry = (
                        status_category in RETRYABLE_ERROR_CATEGORIES and attempt <= budget.max_retries
                    )
                    if should_retry:
                        self._record_retry(state=state, branch=BRANCH_URL_FETCH)
                        logger.info(
                            "图片 URL 拉取命中可重试状态码，准备重试: url=%s status_code=%s "
                            "attempt=%s/%s",
                            _mask_url(url),
                            status_code,
                            attempt,
                            budget.max_retries + 1,
                        )
                        continue
                    logger.warning(
                        "图片 URL 拉取失败: url=%s status_code=%s error_category=%s",
                        _mask_url(url),
                        status_code,
                        status_category,
                    )
                    return None
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
                self._record_error_category(state=state, category="dependency_missing")
                logger.warning("图片 URL 拉取失败：缺少 httpx 依赖")
                return None
            except Exception as exc:
                error_category = self._classify_exception(exc)
                self._record_error_category(state=state, category=error_category)
                should_retry = (
                    error_category in RETRYABLE_ERROR_CATEGORIES and attempt <= budget.max_retries
                )
                if should_retry:
                    self._record_retry(state=state, branch=BRANCH_URL_FETCH)
                    logger.info(
                        "图片 URL 拉取失败，准备重试: url=%s error=%s error_category=%s attempt=%s/%s",
                        _mask_url(url),
                        type(exc).__name__,
                        error_category or "unknown",
                        attempt,
                        budget.max_retries + 1,
                    )
                    continue
                logger.warning(
                    "图片 URL 拉取失败: url=%s error=%s error_category=%s",
                    _mask_url(url),
                    type(exc).__name__,
                    error_category or "unknown",
                )
                return None
        return None

    async def _resolve_by_refreshed_url(
        self,
        *,
        conv_id: str,
        message_id: Any,
        image_meta: Dict[str, Any],
        url: str,
        file: str,
        file_id: str,
        onebot_message_id: str,
        bot: Any = None,
        bot_self_id: str = "",
        state: Optional[_ResolveAttemptState] = None,
    ) -> Optional[ResolvedImage]:
        if bot is None:
            return None
        refreshed_url = await self._refresh_url_via_nc_get_rkey(
            conv_id=conv_id,
            message_id=message_id,
            url=url,
            file=file,
            file_id=file_id,
            bot=bot,
            bot_self_id=bot_self_id,
            state=state,
        )
        if refreshed_url and refreshed_url != url:
            image = await self._resolve_by_url(
                refreshed_url,
                image_meta=image_meta,
                source="url",
                state=state,
            )
            if image is not None:
                return image

        refreshed_url = await self._refresh_url_via_get_msg(
            conv_id=conv_id,
            message_id=message_id,
            onebot_message_id=onebot_message_id,
            original_url=url,
            file=file,
            file_id=file_id,
            bot=bot,
            bot_self_id=bot_self_id,
            state=state,
        )
        if refreshed_url and refreshed_url != url:
            return await self._resolve_by_url(
                refreshed_url,
                image_meta=image_meta,
                source="url",
                state=state,
            )
        return None

    async def _refresh_url_via_nc_get_rkey(
        self,
        *,
        conv_id: str,
        message_id: Any,
        url: str,
        file: str,
        file_id: str,
        bot: Any,
        bot_self_id: str,
        state: Optional[_ResolveAttemptState] = None,
    ) -> str:
        request_candidates: list[dict[str, Any]] = []
        if url:
            request_candidates.append({"url": url})
        if file:
            request_candidates.append({"file": file})
        if file_id:
            request_candidates.append({"file_id": file_id})
        if url and file:
            request_candidates.append({"url": url, "file": file})
        if url and file_id:
            request_candidates.append({"url": url, "file_id": file_id})

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for params in request_candidates:
            key = tuple(sorted((name, str(value)) for name, value in params.items()))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(params)

        for params in deduped:
            response = await self._call_bot_api(
                bot=bot,
                bot_self_id=bot_self_id,
                action="nc_get_rkey",
                branch=BRANCH_REFRESH_NC_GET_RKEY,
                conv_id=conv_id,
                origin_message_id=message_id,
                state=state,
                **params,
            )
            payload = self._unwrap_bot_payload(response)
            refreshed_url = self._extract_refreshed_url_from_rkey_payload(payload, original_url=url)
            if refreshed_url:
                logger.info(
                    "图片 URL 刷新成功: conv_id=%s message_id=%s via=nc_get_rkey url=%s",
                    conv_id,
                    message_id,
                    _mask_url(refreshed_url),
                )
                return refreshed_url
        return ""

    async def _refresh_url_via_get_msg(
        self,
        *,
        conv_id: str,
        message_id: Any,
        onebot_message_id: str,
        original_url: str,
        file: str,
        file_id: str,
        bot: Any,
        bot_self_id: str,
        state: Optional[_ResolveAttemptState] = None,
    ) -> str:
        if not onebot_message_id:
            return ""

        onebot_message_id_value: Any = self._coerce_int(onebot_message_id)
        if onebot_message_id_value is None:
            onebot_message_id_value = onebot_message_id
        response = await self._call_bot_api(
            bot=bot,
            bot_self_id=bot_self_id,
            action="get_msg",
            branch=BRANCH_REFRESH_GET_MSG,
            conv_id=conv_id,
            origin_message_id=message_id,
            state=state,
            message_id=onebot_message_id_value,
        )
        payload = self._unwrap_bot_payload(response)
        refreshed_url = self._extract_image_url_from_get_msg_payload(
            payload,
            expected_file=file,
            expected_file_id=file_id,
            fallback_url=original_url,
        )
        if refreshed_url:
            logger.info(
                "图片 URL 刷新成功: conv_id=%s message_id=%s via=get_msg url=%s",
                conv_id,
                message_id,
                _mask_url(refreshed_url),
            )
        return refreshed_url

    async def _resolve_by_get_image(
        self,
        *,
        conv_id: str,
        message_id: Any,
        file: str,
        image_meta: Dict[str, Any],
        bot: Any = None,
        bot_self_id: str = "",
        state: Optional[_ResolveAttemptState] = None,
    ) -> Optional[ResolvedImage]:
        if bot is None:
            return None
        response = await self._call_bot_api(
            bot=bot,
            bot_self_id=bot_self_id,
            action="get_image",
            branch=BRANCH_GET_IMAGE_API,
            conv_id=conv_id,
            origin_message_id=message_id,
            state=state,
            file=file,
        )
        payload = self._unwrap_bot_payload(response)
        if not isinstance(payload, dict):
            return None

        url = str(payload.get("url") or "").strip()
        if url:
            image = await self._resolve_by_url(
                url,
                image_meta=image_meta,
                source="get_image",
                state=state,
            )
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
        state: Optional[_ResolveAttemptState] = None,
        **params: Any,
    ) -> Optional[ResolvedImage]:
        if bot is None:
            return None
        response = await self._call_bot_api(
            bot=bot,
            bot_self_id=bot_self_id,
            action="get_file",
            branch=BRANCH_GET_FILE_API,
            conv_id=conv_id,
            origin_message_id=message_id,
            state=state,
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
            image = await self._resolve_by_url(
                url,
                image_meta=image_meta,
                source=source,
                state=state,
            )
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
        branch: str,
        conv_id: str,
        origin_message_id: Any,
        state: Optional[_ResolveAttemptState] = None,
        **params: Any,
    ) -> Any:
        cache_key = self._bot_action_cache_key(bot=bot, bot_self_id=bot_self_id)
        if self._is_action_marked_unsupported(cache_key=cache_key, action=action):
            self._record_error_category(state=state, category="unsupported_action")
            logger.info(
                "OneBot 图片 API 能力不可用(已缓存)，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s",
                conv_id,
                origin_message_id,
                action,
                _mask_identifier(bot_self_id),
            )
            return None

        method = getattr(bot, action, None)
        call_api = getattr(bot, "call_api", None)
        if not callable(method) and not callable(call_api):
            self._mark_action_unsupported(cache_key=cache_key, action=action)
            self._record_error_category(state=state, category="unsupported_action")
            logger.info(
                "OneBot 图片 API 能力不可用，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s reason=no_callable_api",
                conv_id,
                origin_message_id,
                action,
                _mask_identifier(bot_self_id),
            )
            return None

        budget = self._resolve_branch_budget(branch)
        for attempt in range(1, budget.max_retries + 2):
            try:
                if callable(method):
                    response = await asyncio.wait_for(
                        NapcatImageResolver._await_if_needed(method(**params)),
                        timeout=budget.timeout_seconds,
                    )
                else:
                    response = await asyncio.wait_for(
                        NapcatImageResolver._await_if_needed(call_api(action, **params)),
                        timeout=budget.timeout_seconds,
                    )
                if self._is_unsupported_action_response(response):
                    self._mark_action_unsupported(cache_key=cache_key, action=action)
                    self._record_error_category(state=state, category="unsupported_action")
                    logger.info(
                        "OneBot 图片 API 返回不支持，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s",
                        conv_id,
                        origin_message_id,
                        action,
                        _mask_identifier(bot_self_id),
                    )
                    return None

                response_error_category = self._classify_action_response(response)
                self._record_error_category(state=state, category=response_error_category)
                should_retry = (
                    response_error_category in RETRYABLE_ERROR_CATEGORIES
                    and attempt <= budget.max_retries
                )
                if should_retry:
                    self._record_retry(state=state, branch=branch)
                    logger.info(
                        "OneBot 图片 API 返回可重试错误，准备重试: conv_id=%s message_id=%s action=%s "
                        "error_category=%s attempt=%s/%s",
                        conv_id,
                        origin_message_id,
                        action,
                        response_error_category,
                        attempt,
                        budget.max_retries + 1,
                    )
                    continue
                return response

            except Exception as exc:
                if self._is_unsupported_action_error(exc):
                    self._mark_action_unsupported(cache_key=cache_key, action=action)
                    self._record_error_category(state=state, category="unsupported_action")
                    logger.info(
                        "OneBot 图片 API 不支持该动作，跳过该分支: conv_id=%s message_id=%s action=%s self_id=%s "
                        "error=%s",
                        conv_id,
                        origin_message_id,
                        action,
                        _mask_identifier(bot_self_id),
                        type(exc).__name__,
                    )
                    return None

                error_category = self._classify_exception(exc)
                self._record_error_category(state=state, category=error_category)
                should_retry = (
                    error_category in RETRYABLE_ERROR_CATEGORIES and attempt <= budget.max_retries
                )
                if should_retry:
                    self._record_retry(state=state, branch=branch)
                    logger.info(
                        "调用 OneBot 图片 API 失败，准备重试: conv_id=%s message_id=%s action=%s "
                        "error=%s error_category=%s attempt=%s/%s",
                        conv_id,
                        origin_message_id,
                        action,
                        type(exc).__name__,
                        error_category or "unknown",
                        attempt,
                        budget.max_retries + 1,
                    )
                    continue
                logger.warning(
                    "调用 OneBot 图片 API 失败，跳过该分支: conv_id=%s message_id=%s action=%s error=%s "
                    "error_category=%s",
                    conv_id,
                    origin_message_id,
                    action,
                    type(exc).__name__,
                    error_category or "unknown",
                )
                return None
        return None

    def _build_branch_budgets(
        self,
        branch_budgets: Optional[Mapping[str, Mapping[str, Any] | BranchBudget]],
    ) -> Dict[str, BranchBudget]:
        defaults = {
            BRANCH_URL_FETCH: BranchBudget(timeout_seconds=self.timeout_seconds, max_retries=1),
            BRANCH_GET_IMAGE_API: BranchBudget(timeout_seconds=self.timeout_seconds, max_retries=1),
            BRANCH_GET_FILE_API: BranchBudget(timeout_seconds=self.timeout_seconds, max_retries=1),
            BRANCH_REFRESH_NC_GET_RKEY: BranchBudget(timeout_seconds=self.timeout_seconds, max_retries=0),
            BRANCH_REFRESH_GET_MSG: BranchBudget(timeout_seconds=self.timeout_seconds, max_retries=0),
        }
        if not branch_budgets:
            return defaults

        merged = dict(defaults)
        for branch, raw in branch_budgets.items():
            default_budget = defaults.get(branch, self._default_branch_budget)
            merged[branch] = self._merge_branch_budget(default_budget=default_budget, raw=raw)
        return merged

    @staticmethod
    def _merge_branch_budget(
        *,
        default_budget: BranchBudget,
        raw: Mapping[str, Any] | BranchBudget,
    ) -> BranchBudget:
        if isinstance(raw, BranchBudget):
            timeout_seconds = max(0.1, float(raw.timeout_seconds))
            return BranchBudget(
                timeout_seconds=timeout_seconds,
                max_retries=max(0, int(raw.max_retries)),
            )
        timeout_raw = raw.get("timeout_seconds", default_budget.timeout_seconds)
        retry_raw = raw.get("max_retries", default_budget.max_retries)
        try:
            timeout_seconds = max(0.1, float(timeout_raw))
        except (TypeError, ValueError):
            timeout_seconds = default_budget.timeout_seconds
        try:
            max_retries = max(0, int(retry_raw))
        except (TypeError, ValueError):
            max_retries = default_budget.max_retries
        return BranchBudget(timeout_seconds=timeout_seconds, max_retries=max_retries)

    def _resolve_branch_budget(self, branch: str) -> BranchBudget:
        return self._branch_budgets.get(branch, self._default_branch_budget)

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

    @classmethod
    def _classify_action_response(cls, response: Any) -> Optional[str]:
        if not isinstance(response, dict):
            return None
        if cls._is_unsupported_action_response(response):
            return "unsupported_action"

        raw_status = response.get("status")
        status = str(raw_status).strip().lower() if raw_status is not None else ""
        retcode = cls._coerce_int(response.get("retcode"))
        if status in {"failed", "fail", "error"} and retcode is not None:
            return cls._classify_http_status_code(retcode)
        return None

    @classmethod
    def _classify_exception(cls, exc: Exception) -> Optional[str]:
        if isinstance(exc, ImportError):
            return "dependency_missing"
        status_code = cls._extract_status_code_from_exception(exc)
        status_category = cls._classify_http_status_code(status_code)
        if status_category:
            return status_category
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return "timeout"

        error_type = type(exc).__name__.lower()
        message = str(exc).lower()
        if "timeout" in error_type or "timed out" in message:
            return "timeout"
        if any(hint in error_type or hint in message for hint in NETWORK_ERROR_HINTS):
            return "network"
        return None

    @staticmethod
    def _classify_http_status_code(status_code: Optional[int]) -> Optional[str]:
        if status_code is None:
            return None
        if 400 <= status_code < 500:
            return "4xx"
        if 500 <= status_code < 600:
            return "5xx"
        return None

    @classmethod
    def _extract_status_code_from_exception(cls, exc: Exception) -> Optional[int]:
        response = getattr(exc, "response", None)
        if response is not None:
            status = cls._coerce_int(getattr(response, "status_code", None))
            if status is not None:
                return status
        for attr in ("status_code", "retcode", "code"):
            status = cls._coerce_int(getattr(exc, attr, None))
            if status is not None:
                return status
        for arg in getattr(exc, "args", ()):
            if isinstance(arg, dict):
                for key in ("status_code", "retcode", "code"):
                    status = cls._coerce_int(arg.get(key))
                    if status is not None:
                        return status
        return None

    @staticmethod
    def _record_error_category(*, state: Optional[_ResolveAttemptState], category: Optional[str]) -> None:
        if state is None:
            return
        if category not in ERROR_CATEGORY_KEYS:
            return
        state.error_category_count[category] = state.error_category_count.get(category, 0) + 1

    @staticmethod
    def _record_retry(*, state: Optional[_ResolveAttemptState], branch: str) -> None:
        if state is None:
            return
        state.retry_count_by_branch[branch] = state.retry_count_by_branch.get(branch, 0) + 1

    @staticmethod
    def _apply_rkey_to_url(url: str, rkey: str) -> str:
        if not url:
            return ""
        parsed = urlsplit(url)
        query_items = parse_qsl(parsed.query, keep_blank_values=True)
        replaced = False
        normalized: list[tuple[str, str]] = []
        for key, value in query_items:
            if key.lower() == "rkey":
                normalized.append((key, rkey))
                replaced = True
            else:
                normalized.append((key, value))
        if not replaced:
            normalized.append(("rkey", rkey))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(normalized), parsed.fragment))

    @classmethod
    def _extract_refreshed_url_from_rkey_payload(cls, payload: Any, *, original_url: str) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in ("url", "download_url", "image_url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        rkey = payload.get("rkey") or payload.get("r_key") or payload.get("RKey") or payload.get("RKEY")
        if isinstance(rkey, str) and rkey.strip() and original_url:
            return cls._apply_rkey_to_url(original_url, rkey.strip())
        nested = payload.get("data")
        if isinstance(nested, dict):
            return cls._extract_refreshed_url_from_rkey_payload(nested, original_url=original_url)
        return ""

    @classmethod
    def _extract_image_url_from_get_msg_payload(
        cls,
        payload: Any,
        *,
        expected_file: str,
        expected_file_id: str,
        fallback_url: str,
    ) -> str:
        if not isinstance(payload, dict):
            return ""
        message = payload.get("message")
        if not isinstance(message, list):
            return ""
        first_url = ""
        for segment in message:
            if cls._segment_type(segment) != "image":
                continue
            data = cls._segment_data(segment)
            if not isinstance(data, dict):
                continue
            url = str(data.get("url") or "").strip()
            if not url:
                continue
            if not first_url:
                first_url = url
            segment_file = str(data.get("file") or "").strip()
            segment_file_id = str(data.get("file_id") or "").strip()
            if expected_file and segment_file == expected_file:
                return url
            if expected_file_id and segment_file_id == expected_file_id:
                return url
            if fallback_url and url != fallback_url:
                return url
        return first_url

    @staticmethod
    def _segment_type(segment: Any) -> str:
        value = getattr(segment, "type", None)
        if isinstance(value, str):
            return value
        if isinstance(segment, dict):
            raw = segment.get("type")
            return str(raw) if raw is not None else ""
        return ""

    @staticmethod
    def _segment_data(segment: Any) -> Dict[str, Any]:
        value = getattr(segment, "data", None)
        if isinstance(value, dict):
            return value
        if isinstance(segment, dict):
            raw = segment.get("data")
            if isinstance(raw, dict):
                return raw
        return {}

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
