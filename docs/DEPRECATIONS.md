# 方法弃用记录

本文档只记录：核心目标仍保留，但因已有明确问题而替换实现方法、实现策略或设计方案，且弃用理由会影响后续选型的事项。局部条件、字段名、默认值、回退分支、文件清理和功能下线不在此记录。

## 已确认记录

### 1. WebUI 初始化中的同步 `sqlite3` 直连

- **对象**：WebUI 示例数据库初始化使用 `sqlite3.connect`、手写 SQL 和同步提交的路径。
- **弃用原因及依据**：该路径与项目异步运行模型及统一模型注册不一致；`1a72bea`（2025-03-25）的提交说明明确为“迁移至 Tortoise ORM，优化异步处理”，并将初始化、模型创建和写入改为 Tortoise 异步 API。
- **当前替代方法**：Tortoise ORM，由 `plugins/db_core` 统一初始化和注册模型；当前入口见 [`plugins/db_core/db_manager.py`](../plugins/db_core/db_manager.py)。
- **适用范围**：WebUI 示例初始化及其所覆盖的模型访问路径；不表示脚本、基准工具或外部数据库工具一律禁止使用 `sqlite3`。
- **弃用日期**：2025-03-25
- **最后有使用记录的日期**：2025-03-24

### 2. 长期记忆全部放在关系型 ORM 的存储方案

- **对象**：用关系型 ORM 同时承载 `Memory`、`CognitiveNode`、`Association` 等长期记忆图数据的方案。
- **弃用原因及依据**：图数据检索和关联表达是该方案的明确瓶颈；`bceed98`（2025-05-10）将长期记忆迁移到 Neo4j，并明确保留关系型数据库承载高频消息队列，以使用图查询和降低两类数据的耦合。
- **当前替代方法**：长期记忆使用 Neo4j 存储库和网关，短期消息仍使用关系型存储；入口见 [`src/infra/db/neo4j/memory_repository.py`](../src/infra/db/neo4j/memory_repository.py) 和 [`src/infra/db/neo4j_gateway.py`](../src/infra/db/neo4j_gateway.py)。
- **适用范围**：Persona 长期记忆的节点、记忆和关联关系；不适用于短期消息队列或 Neo4j 不可用时的降级行为。
- **弃用日期**：2025-05-10
- **最后有使用记录的日期**：2025-05-05

### 3. 图片模块专用、固定指标页面与写入器

- **对象**：围绕图片模块硬编码 KPI、图表和专用事件写入函数的指标实现。
- **弃用原因及依据**：该方案把页面能力绑定到当前单个模块，新增模块需要重复改数据库写入和前端结构；归档方案明确要求以模块定义和 Provider 驱动渲染，并以通用事件写入器替换图片专用函数。依据见 [`WebUI 模块指标方案归档`](archive/2026-02-21/webui-module-metrics-plan.md) 及提交 `957e2d0`（2026-02-21）。
- **当前替代方法**：`ModuleMetricsProvider` 注册表、内置 Provider 和通用事件写入器；入口见 [`src/core/services/module_metrics_provider.py`](../src/core/services/module_metrics_provider.py) 和 [`src/infra/db/tortoise/module_metrics_event_writer.py`](../src/infra/db/tortoise/module_metrics_event_writer.py)。
- **适用范围**：WebUI 模块指标的后端查询、事件写入和前端图表渲染；不涉及单个指标字段的命名修正。
- **弃用日期**：2026-02-21
- **最后有使用记录的日期**：2026-02-20

### 4. 图片理解的单 Provider、非结构化短摘要调用

- **对象**：单一 LLM 客户端以聊天文本提示返回一句摘要的图片理解路径。
- **弃用原因及依据**：只返回自由文本无法稳定承载可见事实、OCR、表格和不确定性，也无法把 Provider 失败切换纳入统一结果；提交 `439f533`（2026-03-31）将其替换为结构化观察 schema、Responses 输入项和按顺序切换的多 Provider，并保留空结果降级。
- **当前替代方法**：`ImageUnderstander.inspect_images` 返回结构化观察结果，使用统一 `LLMClient.response_json`、schema 校验和 Provider fallback；入口见 [`src/infra/llm/providers/image_understander.py`](../src/infra/llm/providers/image_understander.py)。
- **适用范围**：Persona 回复阶段的图片理解及其缓存、usage 事件；不改变图片 URL/文件拉取顺序，也不把模型或 Provider 名称当作稳定业务字段。
- **弃用日期**：2026-03-31
- **最后有使用记录的日期**：2026-03-31

### 5. 独立脚本或直接单进程启动的服务生命周期管理

- **对象**：由旧 `scripts/restart/start_bot.sh`、`restart.sh` 或直接 `poetry run python bot.py` 各自创建和停止 screen/进程的生命周期方案。
- **弃用原因及依据**：多套入口无法统一管理 NapCat 与 bot、无法可靠校验会话归属，且停止操作可能误接管同名会话；`92ef339`（2026-10-09）建立受管 screen 生命周期，`629dd28`（2026-10-10）将重启和兼容入口统一委托给该管理器。
- **当前替代方法**：[`scripts/manage_processes.py`](../scripts/manage_processes.py) 的 `dev`、`start`、`restart_bot`、`status` 和 `stop` 接口；旧 `start_bot.sh` 仅作为兼容转发入口。
- **适用范围**：本项目 NapCat 与 `atri_bot` 的启动、停止、状态和重启；不接管同名非受管 screen 会话。
- **弃用日期**：2026-10-10
- **最后有使用记录的日期**：2026-10-09

### 6. 将 API 密钥和数据库密码作为 YAML 配置值读取

- **对象**：把 OpenAI、图片 Provider、Neo4j、PostgreSQL 及插件 API 密钥直接放入 `data/` YAML 并由配置对象读取的方案。
- **弃用原因及依据**：密钥不应进入仓库配置、调试输出或普通配置快照；提交 `f02f7de`（2026-10-12）移除敏感字段的序列化和必填要求，并增加从进程环境及选定 `.env.dev/.env.prod` 读取的统一入口与迁移警告。
- **当前替代方法**：使用 [`src/core/domain/runtime_settings.py`](../src/core/domain/runtime_settings.py) 从进程环境或选定 dotenv 文件读取密钥；YAML 仅保留非敏感参数。使用入口和安全约束见 [`README.md`](../README.md)。
- **适用范围**：本项目运行时密钥和密码；不改变非敏感模型、地址、超时和功能开关的 YAML 配置方式。
- **弃用日期**：2026-10-12
- **最后有使用记录的日期**：2026-10-11

### 7. 将 WebUI 浏览器入口嵌入 ATRI 共享的 `8080` 宿主

- **对象**：由 ATRI/NoneBot 的共享 `127.0.0.1:8080` 宿主同时提供 WebUI 静态页面和浏览器入口 `/webui` 的部署方式。
- **弃用原因及依据**：`8080` 同时承载 ATRI 的其它内部功能，迁移 WebUI 浏览器入口时不能整体迁移或中断该宿主；2026-10-19 的端口迁移将 WebUI 页面和 WebUI API 固定到独立的 `127.0.0.1:8188`，保留 `8080` 作为 ATRI 内部宿主及 Vite 开发代理上游。
- **当前替代方法**：由 `atri-webui.service` 运行独立 WebUI 浏览器端点；服务模板见 [`plugins/webui/deploy/systemd/atri-webui.service.example`](../plugins/webui/deploy/systemd/atri-webui.service.example)，健康检查为 [`plugins/webui/backend/healthcheck.py`](../plugins/webui/backend/healthcheck.py)。主宿主加载新版本后，旧 `/webui` 路由重定向到 `8188`。
- **适用范围**：仅限 WebUI 的浏览器页面、静态资源和 WebUI API 入口；ATRI/NoneBot 的其它内部 `8080` 路由及 WebUI 开发代理上游不受影响。
- **弃用日期**：2026-10-19
- **最后有使用记录的日期**：2026-10-19
