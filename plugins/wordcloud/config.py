import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Extra

DEFAULT_CONFIG_PATH = Path("data/wordcloud/config.yaml")


def _load_defaults() -> dict:
    if not DEFAULT_CONFIG_PATH.exists():
        logging.warning(f"词云配置不存在: {DEFAULT_CONFIG_PATH}，将使用内置回退值")
        return {}
    with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        logging.warning("词云配置格式错误，需为字典结构，将使用内置回退值")
        return {}
    return data


_DEFAULTS = _load_defaults()


def _default(key: str, fallback):
    if key in _DEFAULTS:
        return _DEFAULTS[key]
    if _DEFAULTS:
        logging.warning(f"词云配置缺少 {key}，将使用内置回退值")
    return fallback

class Config(BaseModel, extra=Extra.ignore):
    # 默认获取过去24小时的消息
    wordcloud_hours: int = _default("wordcloud_hours", 24)
    # 最少显示的词数
    wordcloud_min_words: int = _default("wordcloud_min_words", 30)
    # 最多显示的词数
    wordcloud_max_words: int = _default("wordcloud_max_words", 100)
    # 是否过滤敏感词
    wordcloud_filter_sensitive: bool = _default("wordcloud_filter_sensitive", True)
    # 敏感词列表文件路径
    wordcloud_sensitive_words_file: str = _default(
        "wordcloud_sensitive_words_file",
        "data/wordcloud/sensitive_words.txt",
    )
    # 停用词列表文件路径
    wordcloud_stopwords_file: str = _default(
        "wordcloud_stopwords_file",
        "data/wordcloud/stopwords.txt",
    )
    # 是否开启新词发现
    wordcloud_new_words_discovery: bool = _default("wordcloud_new_words_discovery", True)
    # 最小词长度
    wordcloud_min_word_length: int = _default("wordcloud_min_word_length", 2)
