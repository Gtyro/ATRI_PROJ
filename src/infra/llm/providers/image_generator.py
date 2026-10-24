"""Text- and reference-image client for OpenAI-compatible Images APIs."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from src.core.domain.image_generation_error import (
    ImageGenerationError,
    sanitize_image_error_detail,
)
from src.infra.network.tracked_httpx import TrackedAsyncClient
from .manager_bridge import record_request


class ImageGenerator:
    """Generate an image and return its decoded bytes.

    The API is intentionally implemented with httpx instead of the chat client:
    plain prompts use ``/images/generations`` and configured character references
    use the standard multipart ``/images/edits`` endpoint.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        endpoint_path: str = "/images/generations",
        reference_endpoint_path: str = "/images/edits",
        reference_image_paths: tuple[str, ...] | list[str] = (),
        max_retries: int = 1,
        manager_provider_name: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url or "").rstrip("/")
        self.model = str(model or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.endpoint_path = str(endpoint_path or "/images/generations").strip()
        self.reference_endpoint_path = str(reference_endpoint_path or "/images/edits").strip()
        self.reference_image_paths = tuple(str(path).strip() for path in reference_image_paths if str(path).strip())
        self.max_retries = max(0, int(max_retries))
        self.manager_provider_name = manager_provider_name
        self._client = client

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/{self.endpoint_path.lstrip('/')}"

    @property
    def reference_endpoint(self) -> str:
        return f"{self.base_url}/{self.reference_endpoint_path.lstrip('/')}"

    async def generate(self, prompt: str, *, use_character_reference: bool = False) -> bytes:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise self._error("绘图描述不能为空", code="invalid_prompt")
        if not self.api_key:
            raise self._error("未配置 IMAGE_GENERATION_API_KEY", code="configuration")
        if not self.base_url or not self.model:
            raise self._error("图像生成服务配置不完整", code="configuration")

        reference_files = self._load_reference_files() if use_character_reference else []
        endpoint_path = self.reference_endpoint_path if reference_files else self.endpoint_path
        endpoint = self.reference_endpoint if reference_files else self.endpoint
        try:
            url = httpx.URL(self.base_url)
            if url.scheme not in {"http", "https"} or not url.host or url.query or url.fragment or url.userinfo:
                raise ValueError("Invalid image generation base URL")
            if not endpoint_path.strip("/"):
                raise ValueError("Invalid image generation endpoint path")
            endpoint_url = httpx.URL(endpoint_path)
            if (
                not endpoint_path.startswith("/")
                or endpoint_url.scheme
                or endpoint_url.host
                or endpoint_url.query
                or endpoint_url.fragment
            ):
                raise ValueError("Invalid image generation endpoint path")
        except (httpx.InvalidURL, ValueError) as exc:
            raise self._error(
                "图像生成服务地址无效", code="configuration",
                detail=str(exc), endpoint=endpoint,
            ) from exc

        payload = {
            "model": self.model,
            "prompt": normalized_prompt,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if not reference_files:
            headers["Content-Type"] = "application/json"

        if self._client is not None:
            return await self._request_with_retries(
                self._client, payload, headers, endpoint=endpoint, files=reference_files,
            )

        timeout = httpx.Timeout(self.timeout_seconds)
        async with TrackedAsyncClient(timeout=timeout) as client:
            return await self._request_with_retries(
                client, payload, headers, endpoint=endpoint, files=reference_files,
            )

    def _load_reference_files(self) -> list[tuple[str, tuple[str, bytes, str]]]:
        """Load configured local character references for a standard edit request."""
        if not self.reference_image_paths:
            return []

        project_root = Path.cwd().resolve()
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for raw_path in self.reference_image_paths:
            candidate = (project_root / raw_path).resolve()
            try:
                candidate.relative_to(project_root)
            except ValueError as exc:
                raise self._error(
                    "角色参考图必须位于项目目录内",
                    code="reference_invalid",
                    detail=raw_path,
                    endpoint=self.reference_endpoint,
                ) from exc
            if not candidate.is_file():
                raise self._error(
                    "角色参考图文件不存在",
                    code="reference_missing",
                    detail=raw_path,
                    endpoint=self.reference_endpoint,
                )
            try:
                image_bytes = candidate.read_bytes()
            except OSError as exc:
                raise self._error(
                    "角色参考图无法读取",
                    code="reference_invalid",
                    detail=f"{raw_path}: {type(exc).__name__}",
                    endpoint=self.reference_endpoint,
                ) from exc
            if not image_bytes or len(image_bytes) > 10 * 1024 * 1024:
                raise self._error(
                    "角色参考图文件无效或过大",
                    code="reference_invalid",
                    detail=raw_path,
                    endpoint=self.reference_endpoint,
                )
            mime_type, _ = mimetypes.guess_type(candidate.name)
            if mime_type not in self._REFERENCE_IMAGE_MEDIA_TYPES or not self._looks_like_image(image_bytes):
                raise self._error(
                    "角色参考图不是受支持的图片格式",
                    code="reference_invalid",
                    detail=raw_path,
                    endpoint=self.reference_endpoint,
                )
            files.append(("image", (candidate.name, image_bytes, mime_type)))
        return files

    async def _request_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        endpoint: str,
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> bytes:
        attempts = self.max_retries + 1
        started = time.monotonic()
        for attempt in range(attempts):
            try:
                image_bytes = await self._request(client, payload, headers, endpoint=endpoint, files=files)
            except ImageGenerationError as exc:
                if not exc.retryable or attempt >= self.max_retries:
                    if self.manager_provider_name:
                        await record_request(self.manager_provider_name, self.model, error=exc,
                                             attempts=attempt + 1,
                                             elapsed_ms=round((time.monotonic() - started) * 1000))
                    raise
                delay = min(2.0, 0.5 * (2 ** attempt))
                logging.warning(
                    "Image generation transient failure; retrying attempt=%s/%s delay=%.1fs %s",
                    attempt + 1, attempts, delay, exc.diagnostic_summary(),
                )
                await asyncio.sleep(delay)
            except Exception as exc:
                if self.manager_provider_name:
                    await record_request(self.manager_provider_name, self.model, error=exc,
                                         attempts=attempt + 1,
                                         elapsed_ms=round((time.monotonic() - started) * 1000))
                raise
            else:
                if self.manager_provider_name:
                    await record_request(self.manager_provider_name, self.model,
                                         attempts=attempt + 1,
                                         elapsed_ms=round((time.monotonic() - started) * 1000))
                return image_bytes
        raise AssertionError("image generation retry loop exited without a result")

    async def _request(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        endpoint: str,
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> bytes:
        try:
            if files:
                response = await client.post(endpoint, data=payload, files=files, headers=headers)
            else:
                response = await client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise self._error(
                "图像生成请求超时", code="timeout", retryable=True,
                detail=type(exc).__name__, prompt=payload["prompt"], endpoint=endpoint,
            ) from exc
        except httpx.HTTPError as exc:
            raise self._error(
                "图像生成服务连接失败", code="network", retryable=True,
                detail=f"{type(exc).__name__}: {exc}", prompt=payload["prompt"], endpoint=endpoint,
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise self._http_error(response, payload["prompt"], endpoint=endpoint)

        # The OpenAI-compatible contract normally wraps the image in JSON, but
        # a few gateways return the generated bytes directly.  Trying
        # ``response.json()`` first makes those perfectly valid 200 responses
        # look like malformed provider responses.
        raw_image = self._extract_raw_image(response)
        if raw_image is not None:
            if not raw_image:
                raise self._error(
                    "图像生成服务未返回图片数据", code="no_image", response=response,
                    prompt=payload["prompt"],
                    detail=self._response_diagnostics(response, reason="empty_image_body"),
                    endpoint=endpoint,
                )
            return raw_image

        response_kind = self._unexpected_success_response_kind(response)
        if response_kind is not None:
            code, reason = response_kind
            raise self._error(
                "图像生成服务返回了非图片响应", code=code, response=response,
                prompt=payload["prompt"],
                detail=self._response_diagnostics(response, reason=reason),
                endpoint=endpoint,
            )

        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise self._error(
                "图像生成服务返回了无效响应", code="invalid_response",
                response=response, prompt=payload["prompt"],
                detail=self._response_diagnostics(response, reason="json_decode_failed"),
                endpoint=endpoint,
            ) from exc

        # Some compatible services return a logical error with HTTP 200.
        if isinstance(data, dict) and data.get("error"):
            raise self._error(
                "图像生成服务返回错误", code="provider_error", response=response,
                detail=self._response_diagnostics(
                    response, reason=self._response_error(response), payload=data,
                ), prompt=payload["prompt"], endpoint=endpoint,
            )
        try:
            image_bytes = self._extract_image_bytes(data)
        except ImageGenerationError as exc:
            raise self._error(
                str(exc), code=exc.code, response=response, prompt=payload["prompt"],
                detail=self._response_diagnostics(response, reason=str(exc), payload=data),
                endpoint=endpoint,
            ) from exc
        if not image_bytes:
            raise self._error(
                "图像生成服务未返回图片数据", code="no_image",
                response=response, prompt=payload["prompt"],
                detail=self._response_diagnostics(response, reason="no_image", payload=data),
                endpoint=endpoint,
            )
        return image_bytes

    @classmethod
    def _unexpected_success_response_kind(cls, response: httpx.Response) -> tuple[str, str] | None:
        """Classify known non-image success bodies before JSON decoding."""
        media_type = cls._media_type(response)
        if media_type in {"text/html", "application/xhtml+xml"}:
            return "html_response", cls._html_response_kind(response)
        if media_type == "text/event-stream":
            return "stream_response", "event_stream"
        return None

    @classmethod
    def _extract_raw_image(cls, response: httpx.Response) -> Optional[bytes]:
        """Return direct image bytes when the response is not a JSON envelope."""
        media_type = cls._media_type(response)
        body = response.content
        if media_type in cls._RAW_IMAGE_MEDIA_TYPES:
            return body
        if media_type in {"", "application/octet-stream", "application/binary"} and cls._looks_like_image(body):
            return body
        return None

    _RAW_IMAGE_MEDIA_TYPES = frozenset({
        "image/avif",
        "image/bmp",
        "image/gif",
        "image/jpg",
        "image/jpeg",
        "image/png",
        "image/webp",
    })
    _REFERENCE_IMAGE_MEDIA_TYPES = _RAW_IMAGE_MEDIA_TYPES

    @staticmethod
    def _media_type(response: httpx.Response) -> str:
        return response.headers.get("content-type", "").split(";", 1)[0].strip().lower()

    @staticmethod
    def _looks_like_image(body: bytes) -> bool:
        return (
            body.startswith(b"\x89PNG\r\n\x1a\n")
            or body.startswith(b"\xff\xd8\xff")
            or body.startswith((b"GIF87a", b"GIF89a"))
            or (len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP")
            or (len(body) >= 12 and body[4:8] == b"ftyp" and body[8:12] in {b"avif", b"avis"})
        )

    @classmethod
    def _response_diagnostics(
        cls,
        response: httpx.Response,
        *,
        reason: str = "",
        payload: Any = None,
    ) -> str:
        """Describe a response without retaining its body or image data."""
        media_type = cls._media_type(response) or "unknown"
        body = response.content
        fields = [f"content_type={media_type}", f"bytes={len(body)}"]
        if reason:
            fields.append(f"reason={sanitize_image_error_detail(reason)}")

        if not body:
            fields.append("body=empty")
        elif payload is not None:
            fields.append(f"json_shape={cls._json_shape(payload)}")
        elif media_type.startswith("image/") or cls._looks_like_image(body):
            fields.append("body=binary_image")
        else:
            fields.append(f"body={cls._body_summary(body)}")
        return " ".join(fields)

    @classmethod
    def _html_response_kind(cls, response: httpx.Response) -> str:
        """Identify common HTML interception pages without logging page text."""
        body = response.content[:4096].decode("utf-8", errors="replace").lower()
        mitigated = response.headers.get("cf-mitigated", "").strip().lower()
        server = response.headers.get("server", "").strip().lower()
        if mitigated == "challenge" or "just a moment" in body or "cf-chl-" in body:
            return "cdn_challenge"
        if "cloudflare" in body or server == "cloudflare":
            return "cdn_html_page"
        if "access denied" in body or "forbidden" in body or "unauthorized" in body:
            return "access_denied_page"
        if "not found" in body or "404" in body:
            return "not_found_page"
        return "html_page"

    @staticmethod
    def _json_shape(payload: Any) -> str:
        if isinstance(payload, dict):
            keys = ",".join(sorted(str(key) for key in payload.keys())[:12]) or "empty_object"
            data = payload.get("data")
            if isinstance(data, list):
                if not data:
                    return f"object_keys={keys} data=empty_list"
                first = data[0]
                if isinstance(first, dict):
                    image_keys = ",".join(sorted(str(key) for key in first.keys())[:12])
                    return f"object_keys={keys} data_item_keys={image_keys or 'empty_object'}"
                return f"object_keys={keys} data_item={type(first).__name__}"
            return f"object_keys={keys}"
        if isinstance(payload, list):
            return f"list_items={len(payload)}"
        return type(payload).__name__

    @staticmethod
    def _body_summary(body: bytes) -> str:
        """Return a tiny safe classification/preview for non-JSON responses."""
        text = body[:240].decode("utf-8", errors="replace")
        compact = " ".join(text.split())
        lowered = compact.lower()
        if not compact:
            return "empty_text"
        if "<html" in lowered or lowered.startswith("<!doctype html"):
            return "html_document"
        if re.match(r"^(?:event:|data:\s)", lowered) or "text/event-stream" in lowered:
            return "sse_stream"
        # Do not put arbitrary response text (which can contain a prompt,
        # credential, or a short base64 value) into diagnostics.
        compact = re.sub(r"(?i)(?:data:)?[a-z0-9+/]{24,}={0,2}", "[REDACTED_DATA]", compact)
        return sanitize_image_error_detail(compact, ())[:120]

    def _error(
        self,
        message: str,
        *,
        code: str,
        response: httpx.Response | None = None,
        detail: str = "",
        prompt: str = "",
        retryable: bool = False,
        endpoint: str = "",
    ) -> ImageGenerationError:
        return ImageGenerationError(
            message, code=code,
            status_code=response.status_code if response is not None else None,
            request_id=self._request_id(response) if response is not None else "",
            detail=detail, endpoint=endpoint or self.endpoint, model=self.model,
            retryable=retryable, secrets=(self.api_key, prompt),
        )

    def _http_error(
        self,
        response: httpx.Response,
        prompt: str,
        *,
        endpoint: str,
    ) -> ImageGenerationError:
        status = response.status_code
        codes = {
            400: "invalid_request", 401: "authentication", 402: "payment_required",
            403: "forbidden", 404: "not_found", 408: "timeout", 422: "invalid_request",
            429: "rate_limit",
        }
        code = codes.get(status, "upstream_error" if status >= 500 else "provider_error")
        reasons = {
            "authentication": "，鉴权失败，请检查 IMAGE_GENERATION_API_KEY",
            "forbidden": "，请求被拒绝，请检查权限或绘图内容",
            "payment_required": "，请检查额度或计费状态",
            "not_found": "，请检查接口地址及模型是否可用",
            "rate_limit": "，请求受到限流",
            "invalid_request": "，请检查绘图参数及模型设置",
        }
        return self._error(
            f"图像生成服务返回 HTTP {status}{reasons.get(code, '')}",
            code=code, response=response, detail=self._response_error(response),
            prompt=prompt, retryable=status in {408, 429} or status >= 500,
            endpoint=endpoint,
        )

    @staticmethod
    def _request_id(response: httpx.Response) -> str:
        # OpenAI-compatible gateways commonly expose one of these headers.
        # Do not couple diagnostics to a provider or CDN-specific header.
        for name in ("x-request-id", "request-id"):
            if response.headers.get(name):
                return response.headers[name]
        try:
            payload = response.json()
        except (ValueError, TypeError):
            return ""
        if isinstance(payload, dict):
            error = payload.get("error")
            request_id = payload.get("request_id")
            if not request_id and isinstance(error, dict):
                request_id = error.get("request_id")
            if isinstance(request_id, str):
                return request_id
        return ""

    @staticmethod
    def _response_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except (ValueError, TypeError):
            if response.headers.get("content-type", "").startswith("text/plain"):
                return response.text
            return "服务返回了非 JSON 错误响应"
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                parts = [error.get("code"), error.get("message")]
                return ": ".join(str(part) for part in parts if isinstance(part, (str, int)))
            if isinstance(error, (str, int)):
                return str(error)
            message = payload.get("message")
            if isinstance(message, str):
                return message
        return ""

    @classmethod
    def _extract_image_bytes(cls, payload: Any) -> Optional[bytes]:
        if not isinstance(payload, dict):
            return None
        images = payload.get("data")
        if not isinstance(images, list) or not images:
            return None
        first = images[0]
        if not isinstance(first, dict):
            return None
        encoded = first.get("b64_json")
        if isinstance(encoded, str) and encoded.strip():
            try:
                return base64.b64decode(encoded.strip(), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ImageGenerationError(
                    "图像生成服务返回了无效的 base64 图片", code="invalid_image",
                ) from exc

        # Some compatible providers return a URL instead of inline bytes. The
        # bot deliberately requires inline data so it can send a self-contained
        # OneBot image segment without retaining a remote URL.
        image_url = first.get("url")
        if not isinstance(image_url, str) or not image_url.strip():
            return None
        raise ImageGenerationError(
            "图像生成服务返回了图片链接，当前未启用远程图片下载",
            code="unsupported_response",
        )


__all__ = ["ImageGenerationError", "ImageGenerator"]
