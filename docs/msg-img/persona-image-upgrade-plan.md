# Persona 图片消息能力升级（归档摘要）

更新时间：2026-02-27
状态：已完成（计划文档已归档为稳定口径）

## 1. 已落地能力（保留）

1. 配置层：`image_understanding` 已接入 `PersonaConfig`，支持开关与模型参数。
2. 入库层：消息 metadata 支持结构化图片字段（`url/file/file_id/mime`）与 onebot 关键信息。
3. 回写层：支持 `update_message_metadata` 深合并回写识图结果。
4. 回复链路：仅在回复阶段构建图片上下文，不影响话题提取主链路。
5. 拉取链路：`url` + OneBot API 兜底 + 本地路径特判，失败不阻断回复。
6. 识图链路：独立 `ImageUnderstander` 调用，支持 usage 事件上报。
7. 可观测性：
   - 日志：`image_resolved_via(...)`、错误分类、分支重试。
   - metadata：`media.images[].understanding.resolved_via`。
   - 模块统计：`persona.image_fetch` 按 `resolved_via` 聚合。

## 2. 当前稳定约束（保留）

1. 识图触发时机：仅回复阶段。
2. 失败策略：任意图片分支失败不得中断主回复流程。
3. 脱敏要求：禁止完整输出 `url/file/file_id/base64`。
4. 预算要求：分支级 timeout/retry 必须受控。
5. 统计口径：统一使用 `resolved_via`，不再使用 `fetch_source`。

## 3. 保留的历史经验

1. URL 具有时效性，不可作为长期稳定唯一来源。
2. `file_id` 非稳定必有字段，兜底设计必须覆盖 `file`。
3. 排障应同时看字段分布与 `resolved_via` 分布，避免只看单点日志。

## 4. 相关资料

图片拉取与字段口径的当前细节见：

- [`image-url-fallback-spec-analysis-plan.md`](image-url-fallback-spec-analysis-plan.md)
- [`image-field-resolver-mime-guide.md`](image-field-resolver-mime-guide.md)
