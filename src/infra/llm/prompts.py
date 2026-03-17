"""LLM prompts."""

TOPIC_EXTRACTION_PROMPT = """
你是一个高级对话分析专家。你的任务是分析一段对话历史，并将其结构化为已完结和未完结话题。

返回JSON格式结果，包含两个列表：
1. completed_topics: 已完结话题（讨论告一段落）
2. ongoing_topics: 未完结话题（需要后续参与）

字段要求：
completed_topics需包含：
- title: 话题标题
- summary: 详细摘要, 如果存在用户名，用户名需使用[用户名]表示
- keywords: 关键词
- message_ids: 相关消息编号
- start_time: 开始讨论时间
- end_time: 最后讨论时间

ongoing_topics需包含：
- keywords: 关键词
- message_ids: 相关消息编号
- continuation_probability: 延续概率 (0.0-1.0)

判断标准：
- 已完结话题：最后消息超过10分钟/有明确结论/消息序号较小
- 未完结话题：包含未回答问题/最近5分钟活跃/消息序号较大
- 所有消息必须被包含在message_ids中,不能遗漏
- 当前时间：TIME_PLACEHOLDER

示例响应：
{
  "completed_topics": [
    {
      "title": "周末计划讨论",
      "summary": "[xx]今天做了xx，[xx]下周有活动",
      "keywords": ["word1", "word2", "word3"], # 至少包含两个关键词，尽量是细分的，不要是宽泛的
      "message_ids": [0,1,2,3,4],
      "start_time": "2023-08-20 14:00",
      "end_time": "2023-08-20 14:30",
    }
  ],
  "ongoing_topics": [
    {
      "keywords": ["word1", "word2", "word3"], # 捕获未完结话题的关键词
      "message_ids": [5,6,7,8,9],
      "continuation_probability": 0.8
    }
  ]
}
"""

REPLY_HISTORY_KEYWORDS_PROMPT = """
你是对话分析助手，需要根据给定的最近消息历史提取“回复前关键词”。

要求：
- 只输出 JSON 数组，例如：["关键词1", "关键词2"]
- 优先提取具体实体（人名、作品名、地点、项目名、事件名）
- 关键词必须具体，不要出现过于宽泛的词
- 数量 3-8 个
"""

MEMORY_SELECTION_PROMPT = """
你是记忆重排助手。你的任务是根据当前查询，从候选记忆中选择最值得提供给回答模型参考的记忆。

要求：
- 只在给定候选中选择，不要臆造新的 id
- 优先选择与当前查询直接相关、信息具体、能够支撑回答的记忆
- 最多选择 3 条，如果都不相关可以返回空数组
- 只输出 JSON 对象，例如：{"selected_ids":["id1","id2"]}
"""
