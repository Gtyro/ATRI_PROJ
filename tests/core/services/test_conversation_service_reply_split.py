import pytest

from src.core.services.conversation_service import ConversationService


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "（表情突然变得认真）啊啦，这个问题...（稍作停顿，语气温和但坚定）作为艺人学校的在读生，我觉得还是专注于音乐和表演的话题比较好呢。",
            [
                "（表情突然变得认真）",
                "啊啦",
                "这个问题...",
                "（稍作停顿，语气温和但坚定）",
                "作为艺人学校的在读生",
                "我觉得还是专注于音乐和表演的话题比较好呢",
            ],
        ),
        (
            "你好，世界！今天怎么样？",
            ["你好", "世界", "今天怎么样"],
        ),
        (
            "（点头）(smile)好的...",
            ["（点头）", "(smile)", "好的..."],
        ),
        (
            "（无奈地叹了口气）都说了不是啦...（轻轻摇头）我是安和昴，TOGENASHI TOGEARI的鼓手哦。",
            [
                "（无奈地叹了口气）",
                "都说了不是啦...",
                "（轻轻摇头）",
                "我是安和昴",
                "TOGENASHI TOGEARI的鼓手哦",
            ],
        ),
        (
            "我最喜欢的作品是，GIRLS BAND CRY。",
            ["我最喜欢的作品是", "GIRLS BAND CRY"],
        ),
        (
            "旅行目的地，New York City！",
            ["旅行目的地", "New York City"],
        ),
        (
            "她来自，New York的布鲁克林。",
            ["她来自", "New York的布鲁克林"],
        ),
        (
            " \n  第一行\n第二行  ",
            ["第一行", "第二行"],
        ),
        (
            "（点头）",
            ["（点头）"],
        ),
        (
            None,
            [],
        ),
        (
            "",
            [],
        ),
        (
            "   ",
            [],
        ),
    ],
)
def test_split_reply_content_cases(content, expected):
    assert ConversationService._split_reply_content(content) == expected


def test_split_reply_content_never_returns_blank_segments():
    content = "（旁白）  \n  啊啦，，  这个问题...   "

    result = ConversationService._split_reply_content(content)

    assert result == ["（旁白）", "啊啦", "这个问题..."]
    assert all(item.strip() for item in result)
