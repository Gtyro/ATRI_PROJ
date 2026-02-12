# 词云插件

## 简介

词云插件是一个用于统计和可视化聊天内容词频的工具。它会分析聊天记录，提取关键词并生成词云数据，可在前端直观地展示聊天中的热门话题。

## 特性

- 🕒 **定时统计**：每小时自动统计聊天内容词频
- 🔍 **智能分词**：使用jieba分词，支持中文分词和新词发现
- 🧹 **高级过滤**：过滤停用词、敏感词、链接和单字词
- 📊 **数据可视化**：支持在WebUI中展示词云
- 📋 **历史查询**：可查看历史词云数据
- 🛠️ **可配置**：支持自定义词云参数

## 使用方法

### 前端使用

1. 在管理面板中点击"聊天词云"菜单项
2. 查看自动生成的词云
3. 可以调整词数、刷新数据或查看历史数据

### 命令行使用

使用以下命令查看词云数据：

```
/wordcloud [词数]
```

示例：`/wordcloud 20` 显示频率最高的20个词

## 数据存储

- 词云数据存储在数据库的 `wordcloud_data` 表中
- 同时会保存为JSON文件在 `data/wordcloud/` 目录下
- 文件命名格式为 `{月-日}-{小时}.json`

## 配置项

```python
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
```

## 自定义词表

### 停用词

停用词是那些对词云没有实质意义的词，如"的"、"了"、"是"等。

编辑文件：`data/wordcloud/stopwords.txt`
每行一个词，例如：

```
的
了
是
```

### 敏感词

敏感词是那些不希望在词云中显示的词。

编辑文件：`data/wordcloud/sensitive_words.txt`
每行一个词。

### 用户词典

用户词典用于告诉分词器一些专有名词或新词，以改善分词效果。

编辑文件：`data/wordcloud/user_dict.txt`
格式为：`词语 词频`，例如：

```
人工智能 10
机器学习 10
```

## API接口

### 获取词云数据

```
GET /api/wordcloud/data?limit={limit}&refresh={refresh}
```

### 获取历史词云数据

```
GET /api/wordcloud/history?date={date}&hour={hour}
```

### 手动生成词云数据

```
POST /api/wordcloud/generate?word_limit={word_limit}&hours={hours}
```

## 开发者信息

- 插件依赖于 jieba 分词库和 echarts-wordcloud 前端组件
- 插件使用了统一的数据库管理机制（db_manager）
- 自动使用定时任务机制（nonebot_plugin_apscheduler）

## 依赖项

- jieba>=0.42.1
- nonebot2>=2.0.0
- nonebot-plugin-apscheduler>=0.3.0
- tortoise-orm>=0.19.0
- echarts>=5.4.3
- echarts-wordcloud>=2.1.0
