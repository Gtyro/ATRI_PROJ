from plugins.wordcloud.window_policy import should_persist_wordcloud_snapshot


def test_should_persist_only_default_window():
    assert should_persist_wordcloud_snapshot(24, 24) is True
    assert should_persist_wordcloud_snapshot(48, 24) is False
    assert should_persist_wordcloud_snapshot(168, 24) is False
    assert should_persist_wordcloud_snapshot(720, 24) is False
