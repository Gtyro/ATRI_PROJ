# 记忆系统插件

这个插件为你的机器人提供记忆功能，让它能记住与用户的交流内容，提供更自然的对话体验。

## 功能特点

- **自动记忆**：记录机器人收到的所有消息，并进行语义分析
- **智能回复**：基于历史记忆，生成更有上下文感知的回复
- **记忆查询**：支持用户查询机器人过去的记忆内容
- **优先级处理**：私聊和@机器人的消息优先处理
- **批量处理**：群聊普通消息批量处理，减少资源占用
- **记忆衰减**：模拟人类记忆随时间淡化的特性
- **异步处理**：全异步实现，不阻塞机器人主进程
- **多数据库支持**：支持SQLite和PostgreSQL数据库

## 安装方法

1. 将整个 `memory` 目录复制到你的 NoneBot2 项目的 `plugins` 目录下
2. 安装依赖：
   ```bash
   pip install tortoise-orm aiosqlite asyncpg pydantic pyyaml
   ```
3. 创建配置文件，详见下面的配置说明

## 配置说明

首次启动时，插件会在 `data` 目录下创建 `memory_config.yaml` 配置文件，你需要编辑该文件：

```yaml
# API密钥（用于语义分析和回复生成）
api_key: your_api_key_here

# 使用的模型
model: deepseek-chat

# API基础URL
api_base: https://api.deepseek.com

# 数据库配置
# 设置为true使用PostgreSQL，false使用SQLite
use_postgres: false

# PostgreSQL数据库配置（仅当use_postgres为true时使用）
postgres_config:
  host: localhost
  port: 5432
  user: postgres
  password: your_password_here
  database: memories
```

### 数据库配置详解

插件支持两种数据库配置：

1. **SQLite**（默认）：轻量级，无需额外安装数据库服务器
   ```yaml
   use_postgres: false
   ```
   数据库文件位置：`data/memory.db`

2. **PostgreSQL**：支持高并发，适合大规模部署
   ```yaml
   use_postgres: true
   postgres_config:
     host: localhost     # 数据库服务器地址
     port: 5432          # 端口号
     user: postgres      # 用户名
     password: password  # 密码
     database: memories  # 数据库名
   ```
   注意：使用PostgreSQL前需要先创建对应的数据库

**重要**：配置数据库类型须在第一次启动插件前设置，后期切换数据库会导致已有记忆数据丢失

## 使用说明

### 基本命令

- `@机器人 记得/回忆/想起 [关键词]` - 让机器人回忆相关内容
- `@机器人 记忆统计` - 查看记忆系统状态 (仅超级用户)
- `@机器人 处理队列` - 立即处理消息队列 (仅超级用户)

### 工作原理

1. 记忆系统会记录机器人接收到的所有消息
2. 私聊和@机器人的消息会立即处理
3. 普通群聊消息会加入队列，定期批量处理
4. 记忆会随时间自动衰减，模拟人类记忆特性
5. 当用户查询时，机器人会从记忆中检索相关内容

## 开发计划

- [ ] 基于语义的记忆检索
- [ ] 记忆整合与关联网络
- [ ] Web管理界面
- [ ] 多模型支持
- [ ] 记忆导出与备份

## 故障排除

1. 如果消息无法被记录，检查日志中的错误信息
2. 确保配置文件中的API密钥正确设置
3. 使用PostgreSQL时，确保数据库服务器正常运行并且可以连接
4. 检查数据库权限，确保机器人有读写权限

## 贡献指南

欢迎提交Pull Request或Issues来帮助改进这个插件！ 