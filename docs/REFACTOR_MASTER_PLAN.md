# ATRI_PROJ 重构总方案（精简版）

> 面向新接手者，仅保留未完成事项与后续风险
> 项目场景：NoneBot2 + OneBot V11 机器人（Persona、WebUI、词云等）

---

## 1. 预期项目结构

```
src/
  core/
    domain/
    ports/
    services/
    events/
    facade/
  infra/
    db/
      tortoise/
      neo4j/
    llm/
      providers/
    memory/
  adapters/
    nonebot/
    webui/
    scripts/

plugins/
  persona/
  message_basic/
  wordcloud/
  webui/
  ...
```

---

## 2. 当前剩余目标（高优先级）
1. **LLM Provider 抽象统一**
   - 统一 Tool Calling / Structured Output 能力入口
   - 多 Provider 注册与回退策略完善
   - 标准化调用参数、错误处理与日志
2. **测试与回归**
   - persona 初始化 / 自动回复 / 记忆检索 / WebUI 记忆页回归
   - 核心服务单测：Conversation / Reply / Memory

---

## 3. 中优先级
1. **配置治理深化**：移除 dict 兜底与魔法默认
2. **多模态扩展**：图像标签与检索接入主流程

---

## 4. 交付标准（剩余部分）
1. LLM Provider 可切换，Tool Calling 统一
2. 关键路径回归通过（persona + WebUI 记忆页）
3. 核心服务具备基础单测

---

## 5. 风险与对策（与剩余任务相关）

| 风险 | 影响 | 对策 |
|------|------|------|
| 新 AI 接口不稳定 | 回复质量波动 | 版本锁定 + 多 Provider fallback |
| 回归缺失 | 影响稳定性 | 建立回放脚本 + 关键路径测试 |
| 结构化输出解析失败 | 数据异常 | schema 校验 + 失败重试 |
