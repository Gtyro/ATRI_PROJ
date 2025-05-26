import re
import json
import os
from datetime import datetime
from collections import Counter
from pathlib import Path

import jieba
import jieba.analyse
from nonebot import get_driver

from .config import Config
from .models import get_messages, save_word_cloud_data

# 获取配置
driver = get_driver()
config = driver.config # driver.config 已经是 Config 对象

# 停用词和敏感词列表
stopwords = set()
sensitive_words = set()

# 初始化停用词和敏感词
def init_word_lists():
    # 创建目录
    os.makedirs(os.path.dirname(config.wordcloud_stopwords_file), exist_ok=True)
    os.makedirs(os.path.dirname(config.wordcloud_sensitive_words_file), exist_ok=True)
    
    # 初始化停用词
    if not os.path.exists(config.wordcloud_stopwords_file):
        with open(config.wordcloud_stopwords_file, 'w', encoding='utf-8') as f:
            f.write('的\n了\n是\n在\n我\n有\n和\n就\n不\n人\n都\n一\n一个\n上\n也\n很\n到\n说\n要\n去\n你\n会\n着\n没有\n看\n好\n自己\n这\n么\n')
    
    # 初始化敏感词
    if not os.path.exists(config.wordcloud_sensitive_words_file):
        with open(config.wordcloud_sensitive_words_file, 'w', encoding='utf-8') as f:
            f.write('')
    
    # 加载停用词
    with open(config.wordcloud_stopwords_file, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word:
                stopwords.add(word)
    
    # 加载敏感词
    if config.wordcloud_filter_sensitive:
        with open(config.wordcloud_sensitive_words_file, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if word:
                    sensitive_words.add(word)

# 初始化分词器
def init_jieba():
    # 加载自定义词典
    user_dict_path = Path("data/wordcloud/user_dict.txt")
    if not user_dict_path.exists():
        user_dict_path.parent.mkdir(exist_ok=True)
        with open(user_dict_path, 'w', encoding='utf-8') as f:
            f.write('')
    
    jieba.load_userdict(str(user_dict_path))
    
    # 启用新词发现
    if config.wordcloud_new_words_discovery:
        jieba.enable_parallel(4)  # 启用并行分词

# 过滤URL
def filter_urls(text):
    url_pattern = re.compile(r'https?://\S+|www\.\S+')
    return url_pattern.sub('', text)

# 过滤特殊字符
def filter_special_chars(text):
    # 过滤掉特殊字符和数字
    return re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', ' ', text)

# 分词和过滤
def tokenize_and_filter(text):
    # 过滤URL
    text = filter_urls(text)
    
    # 过滤特殊字符
    text = filter_special_chars(text)
    
    # 分词
    words = jieba.lcut(text)
    
    # 过滤停用词、敏感词和长度为1的词
    filtered_words = []
    for word in words:
        if (len(word) >= config.wordcloud_min_word_length and 
            word not in stopwords and 
            (not config.wordcloud_filter_sensitive or word not in sensitive_words) and
            not word.isdigit()):  # 过滤纯数字
            filtered_words.append(word)
    
    return filtered_words

# 识别新词并添加到用户词典
def discover_new_words(texts, top_n=20):
    if not config.wordcloud_new_words_discovery:
        return
    
    # 合并所有文本
    all_text = ' '.join(texts)
    
    # 使用jieba的新词发现功能
    new_words = jieba.analyse.extract_tags(all_text, topK=top_n, withWeight=False)
    
    # 将新词添加到用户词典
    user_dict_path = Path("data/wordcloud/user_dict.txt")
    with open(user_dict_path, 'a', encoding='utf-8') as f:
        for word in new_words:
            if (len(word) >= config.wordcloud_min_word_length and 
                word not in stopwords and 
                word not in sensitive_words):
                f.write(f"{word} 10\n")  # 10是词频，越高权重越大
    
    # 重新加载用户词典
    jieba.load_userdict(str(user_dict_path))

# 生成词云数据
async def generate_word_cloud_data(conv_id, word_limit=None, hours=None):
    """
    生成词云数据
    
    参数:
        conv_id: 会话ID
        word_limit: 词云中显示的词数量，None表示使用配置中的默认值
        hours: 获取多少小时前的消息，None表示使用配置中的默认值
    
    返回:
        生成的词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    # 使用配置中的默认值
    if word_limit is None:
        word_limit = config.wordcloud_max_words
    if hours is None:
        hours = config.wordcloud_hours
    
    # 初始化
    init_word_lists()
    init_jieba()
    
    # 获取消息
    messages = await get_messages(conv_id, hours)
    
    if not messages:
        return []
    
    # 提取消息内容
    texts = [msg.content for msg in messages]
    
    # 发现新词
    discover_new_words(texts)
    
    # 分词和过滤
    all_words = []
    for text in texts:
        words = tokenize_and_filter(text)
        all_words.extend(words)
    
    # 统计词频
    word_counts = Counter(all_words)
    
    # 取出词频最高的N个词
    min_words = config.wordcloud_min_words
    max_words = config.wordcloud_max_words if word_limit > config.wordcloud_max_words else word_limit
    
    # 确保至少有min_words个词
    if len(word_counts) < min_words:
        top_words = word_counts.most_common(len(word_counts))
    else:
        top_words = word_counts.most_common(max_words)
    
    # 格式化结果
    result = [{"word": word, "weight": count} for word, count in top_words]
    
    # 获取当前时间
    now = datetime.now()
    current_date = now.date()
    current_hour = now.hour
    
    # 保存到数据库
    await save_word_cloud_data(result, conv_id, current_date, current_hour)
    
    return result

# 获取词云数据函数（提供给前端和命令使用）
async def get_word_cloud_data(conv_id, limit=None):
    """
    获取词云数据
    
    参数:
        conv_id: 会话ID
        limit: 返回的词数量，None表示使用配置中的默认值
    
    返回:
        词云数据列表 [{word: "词", weight: 频率}, ...]
    """
    from .models import get_latest_word_cloud_data
    
    # 获取最新的词云数据
    data = await get_latest_word_cloud_data(conv_id)
    
    if not data:
        # 如果没有缓存的数据，则实时生成
        return await generate_word_cloud_data(conv_id, word_limit=limit)
    
    word_data = data.word_data
    
    # 如果指定了限制，则只返回前N个
    if limit and len(word_data) > limit:
        word_data = word_data[:limit]
    
    return word_data 