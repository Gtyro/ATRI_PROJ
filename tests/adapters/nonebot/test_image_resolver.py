import asyncio
import logging

from src.adapters.nonebot.image_resolver import NapcatImageResolver


def test_resolve_logs_file_id_fallback_warning(caplog):
    resolver = NapcatImageResolver(timeout_seconds=0.1)

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            resolver.resolve(
                conv_id="group_1",
                message_id=99,
                image_meta={"file_id": "abc123456789"},
            )
        )

    assert result is None
    assert "file_id_fallback_warning=1" in caplog.text
    assert "abc1***6789" in caplog.text
