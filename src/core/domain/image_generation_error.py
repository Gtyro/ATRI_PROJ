"""Image generation failures shared by providers and reply handling."""

import re
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit


def _safe_url(match: re.Match) -> str:
    try:
        url = urlsplit(match.group())
        host = url.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if url.port:
            host += f":{url.port}"
        return urlunsplit((url.scheme, host, url.path, "", ""))
    except ValueError:
        return "[REDACTED_URL]"


def sanitize_image_error_detail(value: object, secrets: Iterable[str] = ()) -> str:
    """Keep bounded diagnostics without credentials, query strings or image data."""
    text = str(value or "")
    for secret in sorted({item for item in secrets if item}, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"data:[^\s;,]+;base64,[A-Za-z0-9+/=]+", "[REDACTED_IMAGE]", text)
    text = re.sub(r"[A-Za-z0-9+/]{128,}={0,2}", "[REDACTED_DATA]", text)
    text = re.sub(r"(?i)https?://[^\s<>\"']+", _safe_url, text)
    text = re.sub(r"(?i)\b(?:Bearer|Basic)\s+[^\s,;\"']+", "[REDACTED_AUTH]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED_KEY]", text)
    text = re.sub(
        r"(?i)((?:api[_-]?key|authorization|access[_-]?token|token|password|secret|"
        r"b64_json|base64|prompt)[\"']?\s*[:=]\s*)"
        r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    text = " ".join(text.split())
    return text[:500] + ("…" if len(text) > 500 else "")


def image_generation_failure_reply(code: str) -> str:
    """Give a factual, conversational explanation without raw provider output."""
    reasons = {
        "invalid_prompt": "绘图描述不完整，需要调整一下。",
        "configuration": "绘图服务还没配置好，需要检查配置。",
        "authentication": "绘图服务的凭据没通过验证，需要检查配置。",
        "forbidden": "绘图服务拒绝了这次请求，需要检查权限或绘图内容。",
        "payment_required": "绘图服务的额度不足，需要补充额度。",
        "not_found": "绘图服务找不到所请求的接口或模型，需要检查配置。",
        "rate_limit": "绘图服务的请求太频繁了，稍后再试吧。",
        "timeout": "绘图请求超时了，暂时没拿到图片。",
        "network": "没连上绘图服务，稍后再试吧。",
        "upstream_error": "绘图服务暂时出故障了，稍后再试吧。",
        "invalid_request": "绘图服务不接受这次请求，需要检查描述或模型设置。",
        "invalid_response": "绘图服务返回的内容无法读取，需要检查服务响应。",
        "html_response": "绘图服务返回了网页而不是图片数据，需要检查接口地址或代理。",
        "stream_response": "绘图服务返回了流式内容而不是图片数据，需要检查接口设置。",
        "no_image": "绘图服务没有返回图片，需要检查服务响应。",
        "invalid_image": "绘图服务返回的图片数据损坏了，需要检查服务响应。",
        "unsupported_response": "绘图服务只返回了图片链接，目前无法发送这种结果。",
        "reference_missing": "角色参考图没有找到，需要检查本地资源配置。",
        "reference_invalid": "角色参考图无法使用，需要检查图片文件。",
        "tool_unavailable": "当前会话的绘图功能不可用。",
        "tool_arguments": "没能整理好绘图描述，需要重新描述一下。",
    }
    return "这次没能画出来，" + reasons.get(code, "出了个意外，需要检查错误日志。")


class ImageGenerationError(RuntimeError):
    """A classified failure with sanitized diagnostic context."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "unknown",
        status_code: int | None = None,
        request_id: str = "",
        detail: str = "",
        endpoint: str = "",
        model: str = "",
        retryable: bool = False,
        secrets: Iterable[str] = (),
    ) -> None:
        secrets = tuple(secrets)
        message = sanitize_image_error_detail(message, secrets)
        self.code = sanitize_image_error_detail(code, secrets)
        self.status_code = status_code
        self.request_id = sanitize_image_error_detail(request_id, secrets)
        self.detail = sanitize_image_error_detail(detail, secrets)
        self.endpoint = sanitize_image_error_detail(endpoint, secrets)
        self.model = sanitize_image_error_detail(model, secrets)
        self.retryable = retryable
        self.user_message = image_generation_failure_reply(self.code)
        super().__init__(message + (f": {self.detail}" if self.detail else ""))

    def diagnostic_summary(self) -> str:
        return (
            f"code={self.code} status={self.status_code} retryable={self.retryable} "
            f"endpoint={self.endpoint or '-'} model={self.model or '-'} "
            f"request_id={self.request_id or '-'} reason={self}"
        )
