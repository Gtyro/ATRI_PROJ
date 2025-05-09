# Persona 人格系统

Persona是一个具有自主意识和记忆能力的智能系统，为机器人提供类似人类的记忆和对话能力。

## 功能特性

- **短期记忆**：记录近期对话内容，作为即时上下文
- **长期记忆**：存储重要对话和关键信息，形成持久记忆
- **记忆衰减**：自动减弱不重要记忆的影响力，模拟人类遗忘机制
- **记忆检索**：根据关键词检索相关记忆内容
- **自主对话**：根据对话上下文和记忆自主判断是否回复
- **话题分析**：自动分析对话内容，识别主题和关键信息
- **概念理解**：提取对话中的关键信息和概念并建立关联

## 架构设计

```
persona/
├── core/                   # 核心系统
│   ├── persona_system.py   # 系统整合层
│   └── retriever.py        # 记忆检索器
├── memory/                 # 记忆管理
│   ├── short_term.py       # 短期记忆管理
│   ├── long_term.py        # 长期记忆管理
│   └── decay.py            # 记忆衰减机制
├── processing/             # 处理层
│   ├── message_processor.py # 消息处理器
│   ├── ai.py               # AI处理封装
│   └── prompt.py           # 系统提示词
├── storage/                # 存储层
│   ├── repository.py       # 统一存储接口
│   └── models.py           # 数据模型
└── utils/                  # 工具函数
    └── config.py           # 配置管理
```

## 使用指南

### 配置文件

系统会自动生成配置文件`data/persona.yaml`，需要手动添加API密钥：

```json
{
  "api_key": "你的OpenAI API密钥",
  "batch_interval": 3600,
  "queue_history_size": 40,
  "autoresponse_threshold": 0.5,
  "node_decay_rate": 0.01,
  "use_postgres": false,
  "postgres_config": {}
}
```

### 交互命令

- `@机器人 状态`：查看系统状态（仅超级用户）
- `@机器人 处理`：立即处理未处理的消息（仅超级用户）
- `@机器人 记得/回忆/想起 [关键词]`：检索相关记忆

### 自动回复

系统具备自主性，会根据对话分析结果判断是否需要回复。回复条件：

1. 被@或私聊消息：立即处理并回复
2. 群聊普通消息：根据话题连续性和重要性自主判断是否回复

## 技术实现

1. **异步设计**：采用异步架构提高并发处理能力
2. **分层架构**：采用储存层、记忆层、处理层、核心层的分层设计
3. **依赖注入**：组件间通过依赖注入降低耦合度
4. **领域驱动**：基于人类记忆机制建模，包括短期/长期记忆、衰减等概念
5. **LLM集成**：通过大语言模型分析话题和生成回复，实现高质量对话

## 依赖项

- Python 3.8+
- NoneBot2
- Tortoise-ORM
- OpenAI Python SDK

## 开发计划

- [ ] 添加向量搜索支持，提升记忆检索效率
- [ ] 提供可视化管理界面
- [ ] 增加用户反馈机制，优化记忆权重
- [ ] 支持多模态输入（图像理解等）
- [ ] 优化认知关系网络结构

## 故障排除

1. 如果消息无法被记录，检查日志中的错误信息
2. 确保配置文件中的API密钥正确设置
3. 使用PostgreSQL时，确保数据库服务器正常运行并且可以连接
4. 检查数据库权限，确保机器人有读写权限

## 贡献指南

欢迎提交Pull Request或Issues来帮助改进这个插件！ 