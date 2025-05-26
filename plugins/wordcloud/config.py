from pydantic import BaseModel, Extra

class Config(BaseModel, extra=Extra.ignore):
    # 默认获取过去24小时的消息
    wordcloud_hours: int = 24
    # 最少显示的词数
    wordcloud_min_words: int = 30
    # 最多显示的词数
    wordcloud_max_words: int = 100
    # 是否过滤敏感词
    wordcloud_filter_sensitive: bool = True
    # 敏感词列表文件路径
    wordcloud_sensitive_words_file: str = "data/wordcloud/sensitive_words.txt"
    # 停用词列表文件路径
    wordcloud_stopwords_file: str = "data/wordcloud/stopwords.txt"
    # 是否开启新词发现
    wordcloud_new_words_discovery: bool = True
    # 最小词长度
    wordcloud_min_word_length: int = 2 