import asyncio
import base64
import json

import httpx
import pytest

from src.infra.llm.providers.image_generator import ImageGenerationError, ImageGenerator


def test_image_generator_posts_prompt_and_decodes_base64():
    image_bytes = b"fake-png"
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(image_bytes).decode()}]},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret",
                base_url="https://openrouter.ai/api/v1",
                model="qwen/qwen-image-3-pro",
                client=client,
            )
            return await generator.generate("雨夜中的赛博朋克猫")

    result = asyncio.run(run())

    assert result == image_bytes
    assert requests[0].url == "https://openrouter.ai/api/v1/images/generations"
    assert requests[0].headers["authorization"] == "Bearer secret"
    assert json.loads(requests[0].content) == {
        "model": "qwen/qwen-image-3-pro",
        "prompt": "雨夜中的赛博朋克猫",
    }


@pytest.mark.parametrize("media_type,image_bytes", [
    ("image/png", b"\x89PNG\r\n\x1a\nraw-png"),
    ("image/jpeg; charset=binary", b"\xff\xd8\xffraw-jpeg"),
    ("image/webp", b"RIFFxxxxWEBPraw-webp"),
])
def test_image_generator_accepts_direct_image_response(media_type, image_bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": media_type}, content=image_bytes)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret", base_url="https://images.test/v1", model="image-model", client=client,
            )
            return await generator.generate("a cat")

    assert asyncio.run(run()) == image_bytes


def test_image_generator_accepts_image_bytes_from_octet_stream():
    image_bytes = b"\x89PNG\r\n\x1a\nraw-png"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=image_bytes)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret", base_url="https://images.test/v1", model="image-model", client=client,
            )
            return await generator.generate("a cat")

    assert asyncio.run(run()) == image_bytes


def test_image_generator_detects_image_bytes_without_content_type():
    image_bytes = b"\x89PNG\r\n\x1a\nraw-png"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=image_bytes)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret", base_url="https://images.test/v1", model="image-model", client=client,
            )
            return await generator.generate("a cat")

    assert asyncio.run(run()) == image_bytes


def test_image_generator_uses_configured_endpoint_path():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"image").decode()}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret", base_url="https://images.test/v1", model="image-model",
                endpoint_path="/images", client=client,
            )
            return await generator.generate("a cat")

    assert asyncio.run(run()) == b"image"
    assert requests[0].url == "https://images.test/v1/images"


def test_image_generator_sends_local_references_to_standard_edit_endpoint(tmp_path, monkeypatch):
    reference_a = tmp_path / "subaru-front.png"
    reference_b = tmp_path / "subaru-angle.png"
    reference_a.write_bytes(b"\x89PNG\r\n\x1a\nfront-reference")
    reference_b.write_bytes(b"\x89PNG\r\n\x1a\nangle-reference")
    monkeypatch.chdir(tmp_path)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"image").decode()}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret", base_url="https://images.test/v1", model="image-model",
                reference_image_paths=["subaru-front.png", "subaru-angle.png"],
                client=client,
            )
            return await generator.generate("anime selfie", use_character_reference=True)

    assert asyncio.run(run()) == b"image"
    assert requests[0].url == "https://images.test/v1/images/edits"
    assert requests[0].headers["content-type"].startswith("multipart/form-data;")
    body = requests[0].content
    assert b'name="model"' in body
    assert b'image-model' in body
    assert b'name="prompt"' in body
    assert b'anime selfie' in body
    assert body.count(b'name="image"') == 2
    assert b'filename="subaru-front.png"' in body
    assert b'filename="subaru-angle.png"' in body


def test_character_references_are_not_sent_for_regular_generation(tmp_path, monkeypatch):
    reference = tmp_path / "subaru.png"
    reference.write_bytes(b"\x89PNG\r\n\x1a\nreference")
    monkeypatch.chdir(tmp_path)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"image").decode()}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret", base_url="https://images.test/v1", model="image-model",
                reference_image_paths=["subaru.png"], client=client,
            )
            return await generator.generate("a cat")

    assert asyncio.run(run()) == b"image"
    assert requests[0].url == "https://images.test/v1/images/generations"
    assert requests[0].headers["content-type"] == "application/json"
    assert json.loads(requests[0].content) == {"model": "image-model", "prompt": "a cat"}


def test_missing_configured_reference_is_reported_before_a_request(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generator = ImageGenerator(
        api_key="secret", base_url="https://images.test/v1", model="image-model",
        reference_image_paths=["missing.png"],
    )

    with pytest.raises(ImageGenerationError) as caught:
        asyncio.run(generator.generate("anime selfie", use_character_reference=True))

    assert caught.value.code == "reference_missing"
    assert caught.value.endpoint == "https://images.test/v1/images/edits"


def test_image_generator_reports_provider_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="bad",
                base_url="https://example.test/v1",
                model="image-model",
                client=client,
            )
            await generator.generate("a cat")

    with pytest.raises(ImageGenerationError, match="鉴权失败"):
        asyncio.run(run())


def test_image_generator_rejects_missing_image_data():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="secret",
                base_url="https://example.test/v1",
                model="image-model",
                client=client,
            )
            await generator.generate("a cat")

    with pytest.raises(ImageGenerationError, match="未返回图片"):
        asyncio.run(run())


def test_image_generator_requires_prompt_and_key():
    generator = ImageGenerator(
        api_key="",
        base_url="https://example.test/v1",
        model="image-model",
    )
    with pytest.raises(ImageGenerationError, match="不能为空"):
        asyncio.run(generator.generate(""))


def _failure(handler, *, api_key="test-key", prompt="a cat", max_retries=1):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key=api_key, base_url="https://images.test/v1", model="test-image-model",
                max_retries=max_retries, client=client,
            )
            with pytest.raises(ImageGenerationError) as caught:
                await generator.generate(prompt)
            return caught.value

    return asyncio.run(run())


def test_retryable_upstream_failure_retries_once():
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(502, text="temporary upstream failure")
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"image").decode()}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(
                api_key="test-key", base_url="https://images.test/v1", model="test-image-model",
                max_retries=1, client=client,
            )
            return await generator.generate("a cat")

    assert asyncio.run(run()) == b"image"
    assert len(requests) == 2


def test_non_retryable_failure_is_not_repeated():
    requests = []

    error = _failure(
        lambda request: (requests.append(request) or httpx.Response(400, json={"error": "bad request"})),
    )

    assert error.code == "invalid_request"
    assert len(requests) == 1


@pytest.mark.parametrize("status,code,retryable", [
    (400, "invalid_request", False),
    (401, "authentication", False),
    (402, "payment_required", False),
    (403, "forbidden", False),
    (404, "not_found", False),
    (408, "timeout", True),
    (422, "invalid_request", False),
    (429, "rate_limit", True),
    (500, "upstream_error", True),
    (502, "upstream_error", True),
    (503, "upstream_error", True),
])
def test_http_failures_preserve_status_reason_and_request_id(status, code, retryable):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"x-request-id": "req-test-123"},
            json={"error": {"code": "provider_failure", "message": "provider explanation"}},
        )

    error = _failure(handler)

    assert error.code == code
    assert error.status_code == status
    assert error.request_id == "req-test-123"
    assert error.retryable is retryable
    assert "provider_failure: provider explanation" in str(error)
    assert "https://images.test/v1/images/generations" in error.diagnostic_summary()
    assert "test-image-model" in error.diagnostic_summary()
    assert len(requests) == (2 if retryable else 1)
    if not retryable:
        assert "稍后再试" not in error.user_message
        assert "等会儿" not in error.user_message


def test_provider_diagnostics_do_not_expose_credentials_prompt_or_image_data():
    api_key = "synthetic-provider-credential"
    prompt = "private drawing description"
    bare_base64 = "A" * 160
    explanation = (
        f"No endpoints available; key={api_key}; prompt={prompt}; "
        "Authorization: Bearer other-secret; api_key=another-secret; "
        "https://user:password@images.test/v1/images/generations?token=url-secret#private; "
        f"data:image/png;base64,ZmFrZS1wbmc=; {bare_base64}\n"
        "Injected log line; " + "x" * 800
    )
    error = _failure(
        lambda request: httpx.Response(404, json={"error": {"message": explanation}}),
        api_key=api_key, prompt=prompt,
    )

    summary = error.diagnostic_summary()
    assert "No endpoints available" in summary
    assert "https://images.test/v1/images/generations" in summary
    for secret in [api_key, prompt, "other-secret", "another-secret", "url-secret", "user:password",
                   "#private", "ZmFrZS1wbmc=", bare_base64]:
        assert secret not in summary
    assert "\n" not in summary
    assert len(error.detail) <= 501


@pytest.mark.parametrize("headers,payload,expected_id", [
    ({"x-request-id": "req-header"}, {"error": "missing"}, "req-header"),
    ({}, {"error": {"message": "missing", "request_id": "req-nested"}}, "req-nested"),
    ({}, {"message": "missing", "request_id": "req-body"}, "req-body"),
])
def test_error_request_id_supports_common_response_locations(headers, payload, expected_id):
    error = _failure(lambda request: httpx.Response(404, headers=headers, json=payload))
    assert error.request_id == expected_id


@pytest.mark.parametrize("exception,code", [
    (httpx.ReadTimeout("timed out"), "timeout"),
    (httpx.ConnectError("DNS lookup failed"), "network"),
])
def test_transport_failures_have_distinct_codes(exception, code):
    def handler(request):
        raise exception

    error = _failure(handler)

    assert error.code == code
    assert error.retryable is True
    assert error.status_code is None
    assert type(exception).__name__ in error.detail
    assert error.__cause__ is exception


@pytest.mark.parametrize("payload,code", [
    ({"data": []}, "no_image"),
    ({"data": [{"b64_json": ""}]}, "no_image"),
    ({"data": [{"b64_json": "invalid!"}]}, "invalid_image"),
    ({"data": [{"url": "https://remote.test/image.png"}]}, "unsupported_response"),
    ({"error": {"code": "failed", "message": "logical error"}}, "provider_error"),
])
def test_invalid_success_responses_retain_error_context(payload, code):
    error = _failure(lambda request: httpx.Response(
        200, headers={"x-request-id": "req-invalid"}, json=payload,
    ))

    assert error.code == code
    assert error.status_code == 200
    assert error.request_id == "req-invalid"
    assert error.endpoint == "https://images.test/v1/images/generations"
    assert "等会儿" not in error.user_message


def test_invalid_json_response_has_specific_failure_code():
    error = _failure(lambda request: httpx.Response(
        200, headers={"x-request-id": "req-json", "content-type": "text/plain"}, text="not json",
    ))
    assert error.code == "invalid_response"
    assert error.request_id == "req-json"
    assert "content_type=text/plain" in error.detail
    assert "bytes=8" in error.detail
    assert "not json" in error.detail


@pytest.mark.parametrize("response,expected_code,expected_detail", [
    (httpx.Response(200, headers={"content-type": "text/html"}, text="<html>private body</html>"), "html_response", "html_page"),
    (httpx.Response(200, headers={"content-type": "text/html", "cf-mitigated": "challenge"}, text="<html>private body</html>"), "html_response", "cdn_challenge"),
    (httpx.Response(200, headers={"content-type": "text/event-stream"}, text="event: message\ndata: chunk"), "stream_response", "event_stream"),
    (httpx.Response(200, headers={"content-type": "application/json"}, content=b""), "invalid_response", "body=empty"),
])
def test_success_non_image_responses_include_safe_shape_diagnostics(response, expected_code, expected_detail):
    error = _failure(lambda request: response)
    assert error.code == expected_code
    assert "content_type=" in error.detail
    assert expected_detail in error.detail
    assert "private body" not in str(error)


def test_empty_direct_image_response_is_classified_without_content():
    error = _failure(lambda request: httpx.Response(
        200, headers={"content-type": "image/png"}, content=b"",
    ))
    assert error.code == "no_image"
    assert "body=empty" in error.detail


def test_html_error_body_is_not_logged_as_a_document():
    error = _failure(lambda request: httpx.Response(
        404, headers={"content-type": "text/html"}, text="<html>large private document</html>",
    ))
    assert error.code == "not_found"
    assert "非 JSON" in error.detail
    assert "private document" not in str(error)


def test_plain_text_error_body_preserves_diagnostic_reason():
    error = _failure(lambda request: httpx.Response(404, text="No such image route"))
    assert "No such image route" in error.detail


@pytest.mark.parametrize("base_url", [
    "invalid-url", "ftp://images.test/v1", "https://user:pass@images.test/v1",
    "https://images.test/v1?token=secret", "https://images.test/v1#private",
])
def test_invalid_service_address_fails_before_a_request(base_url):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(api_key="test", base_url=base_url, model="test", client=client)
            with pytest.raises(ImageGenerationError) as caught:
                await generator.generate("a cat")
            return caught.value

    error = asyncio.run(run())
    assert error.code == "configuration"
    assert requests == []
    assert "user:pass" not in error.diagnostic_summary()
    assert "token=secret" not in error.diagnostic_summary()


def test_openrouter_base_url_is_not_special_cased():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = ImageGenerator(api_key="test", base_url="https://openrouter.ai", model="test", client=client)
            with pytest.raises(ImageGenerationError):
                await generator.generate("a cat")

    asyncio.run(run())
    assert requests[0].url == "https://openrouter.ai/images/generations"


def test_missing_key_is_configuration_error():
    generator = ImageGenerator(api_key="", base_url="https://images.test/v1", model="test")
    with pytest.raises(ImageGenerationError) as caught:
        asyncio.run(generator.generate("a cat"))
    assert caught.value.code == "configuration"


def test_managed_image_generation_records_one_result_with_actual_attempts(monkeypatch):
    from src.infra.llm.providers import manager_bridge

    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "1")
    monkeypatch.delenv("LLM_REQUEST_KIT_SOCKET", raising=False)
    events = []
    monkeypatch.setattr(
        manager_bridge, "record_usage",
        lambda project, event: events.append((project, event)),
    )
    requests = []

    def success_after_retry(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(502, json={"error": "temporary failure"})
        return httpx.Response(
            200, json={"data": [{"b64_json": base64.b64encode(b"image").decode()}]},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(success_after_retry)) as client:
            generator = ImageGenerator(
                api_key="test", base_url="https://images.test/v1", model="image-model",
                manager_provider_name="draw_main", max_retries=1, client=client,
            )
            assert await generator.generate("a cat") == b"image"

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, json={"error": "invalid key"})
            )
        ) as client:
            generator = ImageGenerator(
                api_key="test", base_url="https://images.test/v1", model="image-model",
                manager_provider_name="draw_main", max_retries=1, client=client,
            )
            with pytest.raises(ImageGenerationError):
                await generator.generate("a cat")

        generator = ImageGenerator(
            api_key="", base_url="https://images.test/v1", model="image-model",
            manager_provider_name="draw_main",
        )
        with pytest.raises(ImageGenerationError):
            await generator.generate("a cat")

    asyncio.run(run())
    assert len(requests) == 2
    assert len(events) == 2
    assert all(project == "ATRI_PROJ" for project, _ in events)
    success, failure = [event for _, event in events]
    assert (success["provider"], success["model"], success["success"], success["attempts"]) == (
        "draw_main", "image-model", True, 2,
    )
    assert "input_tokens" not in success and "output_tokens" not in success
    assert success["elapsed_ms"] >= 0
    assert (failure["success"], failure["attempts"], failure["error_code"]) == (
        False, 1, "authentication",
    )
