README.md
# 🤖 SubaRobot QQ机器人 - 你的智能记忆型聊天伙伴

基于 NoneBot2 + OpenAI + NapCatQQ 构建，具备类人记忆和自主对话能力的智能机器人

[![NoneBot2](https://img.shields.io/badge/NoneBot2-2.0.0rc1-green.svg)](https://nonebot.dev/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## 🌟 核心卖点
- **有记忆的对话**：像真人一样记住聊天内容，告别"金鱼脑"机器人
- **智能上下文理解**：自动分析话题脉络，对话不再答非所问
- **全平台管理**：网页端+QQ端双通道管理，躺着也能维护机器人
- **一键式部署**：小白也能5分钟上手的配置流程，开箱即用

## 🚀 快速开始

### 环境准备
```bash
# 推荐使用 poetry 管理依赖
poetry install
# 或使用传统方式
pip install -r requirements.txt
```

### 三步极速启动
1. **配置密钥**  
   修改 `data/persona.yaml` 填入你的 [OpenAI API Key](https://platform.openai.com/)
   ```yaml
   api_key: "你的密钥"
   ```

2. **设置管理员**  
   在 `.env.prod` 中添加你的QQ号：
   ```
   SUPERUSERS=["123456789"]  # 替换为你的QQ号
   ```

3. **启动！**  
   ```bash
   python bot.py
   ```

### 🔥 首次启动必看
- 机器人上线后，私聊发送 `@机器人 状态` 检查运行状态
- 遇到问题？直接说"帮助"查看使用指南

## � 功能全景

### 🤖 Persona 人格系统（核心模块）
```text
📌 关键词触发：@机器人 记得/回忆/想起 [关键词]
```
- � 记忆系统
  - 7天短期记忆 + 永久长期记忆
  - 自动遗忘不重要内容（像真人一样！）
- 🧠 智能对话
  - 被@必回，群聊智能判断是否参与
  - 支持私聊/群聊双模式
- ⚙️ 管理命令
  - `@机器人 状态`：查看内存使用情况（管理员专属）
  - `@机器人 处理`：强制处理积压消息（管理员专属）

### 🌐 WebUI 控制台（管理神器）
```bash
访问地址：http://127.0.0.1:8080/webui
默认账号：admin/admin（首次登录后必须修改！）
```
- 📊 数据仪表盘：实时查看内存使用情况
- 🔍 记忆搜索引擎：按关键词/时间检索对话记录
- 🛠️ 数据库工具箱：在线执行SQL+批量操作
- 🔐 权限管理：多级用户权限控制

## 🚨 常见问题

### ❓ 机器人不响应怎么办？
1. 检查NapCatQQ是否正常连接
2. 确认已正确设置 `SUPERUSERS`
3. 查看 `data/persona.yaml` 的API密钥配置

### 💾 数据存储在哪？
- 默认使用SQLite：`~/ATRI_PROJ/data/persona.db`
- 支持PostgreSQL：修改配置开启高级数据库支持

## 📚 进阶指南
| 主题          | 文档链接                         |
|---------------|--------------------------------|
| 人格系统配置   | [persona模块文档](plugins/persona/README.md) |
| WebUI使用指南  | [WebUI文档](plugins/webui/README.md)      |
| 开发贡献指南   | CONTRIBUTING.md                |

## 🆘 技术支持
遇到难题？随时执行以下操作：
1. 群里 @机器人 并说"帮助"
2. 提交 [GitHub Issue]
3. 加开发者QQ群：123456789（示例）

---

> 📢 温馨提示：本机器人会持续学习进化，长时间使用会越来越聪明哦~