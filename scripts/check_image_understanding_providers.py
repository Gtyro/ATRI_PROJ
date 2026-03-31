"""Check image-understanding provider availability with Responses API.

This script validates each configured image-understanding provider by sending a
small multimodal request through the same Responses + structured output path
used by the runtime.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.domain import PersonaConfig
from src.infra.llm.providers.client import LLMClient
from src.infra.llm.providers.image_understander import DEFAULT_OBSERVATION_SCHEMA
from src.infra.llm.providers.types import LLMCallParams

DEFAULT_SAMPLE_IMAGE = ROOT / "assets" / "dashboard.png"


def _mask_key(api_key: str) -> str:
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check image-understanding providers.")
    parser.add_argument(
        "--config",
        default="data/persona/persona.yaml",
        help="Persona config path. Defaults to data/persona/persona.yaml",
    )
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="Only check the specified provider name. Can be passed multiple times.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-provider timeout in seconds. Defaults to 30.",
    )
    parser.add_argument(
        "--detail",
        default="auto",
        choices=["auto", "high", "low"],
        help="Image detail level for the healthcheck request.",
    )
    parser.add_argument(
        "--image",
        default=str(DEFAULT_SAMPLE_IMAGE),
        help="Local image path for the healthcheck request. Defaults to assets/dashboard.png",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1200,
        help="Max output tokens for the healthcheck response. Defaults to 1200.",
    )
    return parser.parse_args()


def _iter_selected_providers(config: PersonaConfig, selected_names: Iterable[str]):
    selected = {name.strip() for name in selected_names if str(name).strip()}
    providers = list(config.image_understanding.providers)
    if not providers:
        providers = [
            type(
                "FallbackProvider",
                (),
                {
                    "name": "primary",
                    "api_key": config.image_understanding.api_key,
                    "base_url": config.image_understanding.base_url,
                    "model": config.image_understanding.model,
                },
            )()
        ]
    if not selected:
        return providers
    return [provider for provider in providers if provider.name in selected]


def _build_image_data_url(image_path: str) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Healthcheck image not found: {path}")
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower())
    if mime_type is None:
        raise ValueError(f"Unsupported healthcheck image type: {path.suffix or '<none>'}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def _check_provider(
    provider,
    *,
    timeout: float,
    detail: str,
    image_data_url: str,
    max_tokens: int,
) -> tuple[bool, str]:
    if not str(getattr(provider, "api_key", "") or "").strip():
        return False, "api_key is empty"
    if not str(getattr(provider, "base_url", "") or "").strip():
        return False, "base_url is empty"
    if not str(getattr(provider, "model", "") or "").strip():
        return False, "model is empty"

    client = LLMClient(
        api_key=str(provider.api_key),
        base_url=str(provider.base_url),
        model=str(provider.model),
        provider_name=f"image_check.{provider.name}",
        timeout=timeout,
    )
    prompt = (
        "请只根据图片输出客观信息，并返回符合 schema 的 JSON。"
        "如果图片内容非常简单，也必须返回合法 JSON。"
    )
    output = await client.response_json(
        input_items=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url, "detail": detail},
                ],
            }
        ],
        schema=DEFAULT_OBSERVATION_SCHEMA,
        params=LLMCallParams(temperature=0.0, max_tokens=max_tokens),
        schema_name="image_observation",
        operation="image_understanding_healthcheck",
        usage_context={
            "plugin_name": "persona",
            "module_name": "image_understanding",
            "operation": "image_understanding_healthcheck",
            "detail": detail,
            "response_api": "responses",
        },
    )
    summary = str((output.data or {}).get("summary") or "").strip()
    return True, summary or "<empty summary>"


async def _run(args: argparse.Namespace) -> int:
    config = PersonaConfig.load(config_path=args.config)
    image_data_url = _build_image_data_url(args.image)
    providers = list(_iter_selected_providers(config, args.provider))
    if not providers:
        print("No matching image-understanding providers found.")
        return 1

    overall_ok = True
    config_path = Path(args.config).resolve()
    print(f"Config: {config_path}")
    for provider in providers:
        name = str(provider.name or "unnamed").strip() or "unnamed"
        base_url = str(provider.base_url or "").strip()
        model = str(provider.model or "").strip()
        masked_key = _mask_key(str(provider.api_key or "").strip())
        print(f"[CHECK] provider={name} base_url={base_url} model={model} api_key={masked_key}")
        try:
            ok, detail_text = await _check_provider(
                provider,
                timeout=args.timeout,
                detail=args.detail,
                image_data_url=image_data_url,
                max_tokens=args.max_tokens,
            )
        except Exception as exc:
            overall_ok = False
            print(f"[FAIL] provider={name} error={type(exc).__name__}: {exc}")
            continue
        if ok:
            print(f"[OK] provider={name} summary={detail_text}")
        else:
            overall_ok = False
            print(f"[SKIP] provider={name} reason={detail_text}")

    return 0 if overall_ok else 1


def main() -> int:
    args = _build_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
