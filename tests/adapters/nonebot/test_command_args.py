from src.adapters.nonebot.command_args import normalize_alconna_tokens, parse_reply_send_mode


def test_normalize_alconna_tokens_treats_empty_tuple_as_empty():
    assert normalize_alconna_tokens(()) == []


def test_normalize_alconna_tokens_preserves_tuple_items():
    assert normalize_alconna_tokens(("摸摸", "晚安")) == ["摸摸", "晚安"]


def test_parse_reply_send_mode_defaults_to_preview():
    assert parse_reply_send_mode([]) == (False, None)
    assert parse_reply_send_mode(["摸摸"]) == (False, "摸摸")


def test_parse_reply_send_mode_requires_explicit_send_flag():
    assert parse_reply_send_mode(["发送"]) == (True, None)
    assert parse_reply_send_mode(["发送", "摸摸"]) == (True, "摸摸")
